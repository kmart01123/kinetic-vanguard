"""Active control state and weight-free primitive normalization.

This module deliberately knows nothing about action selection or primitive weights.  It
stores every mechanically active component, applies authority-declared transitions in
their required order, and explains which primitive source is visible at a requested
event window.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from math import floor
from typing import Any, Iterable, Mapping, Sequence


NORMALIZATION_RULES_VERSION = "1.0.0"
MOVEMENT_MODES = ("walk", "fly", "swim", "climb", "burrow")


class ControlStateError(ValueError):
    """Raised when state cannot be normalized without inventing mechanics."""


@dataclass
class ActiveComponent:
    """One component instance on one target.

    IDs from Control Authority are model-local.  ``instance_id`` therefore carries
    invocation identity in addition to the effect/component/target tuple.
    """

    instance_id: str
    effect_id: str
    component_id: str
    target_id: str
    magnitude: dict[str, Any]
    duration: dict[str, Any]
    stacking: dict[str, Any]
    source_actor_id: str
    applied_event_id: str
    expiry_event_id: str | None = None
    remaining_tokens: int | None = None
    contributed_windows: set[tuple[str, str]] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "effect_id": self.effect_id,
            "component_id": self.component_id,
            "target_id": self.target_id,
            "magnitude": deepcopy(self.magnitude),
            "duration": deepcopy(self.duration),
            "stacking": deepcopy(self.stacking),
            "source_actor_id": self.source_actor_id,
            "applied_event_id": self.applied_event_id,
            "expiry_event_id": self.expiry_event_id,
            "remaining_tokens": self.remaining_tokens,
        }


@dataclass(frozen=True)
class PrimitiveContribution:
    family: str
    primitive_id: str
    unit: str
    quantity: float
    target_id: str
    event_or_window_id: str
    source_component_ids: tuple[str, ...]
    active_source_effect_id: str
    context: Mapping[str, Any]
    disposition: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "primitive_id": self.primitive_id,
            "unit": self.unit,
            "quantity": self.quantity,
            "target_id": self.target_id,
            "event_or_window_id": self.event_or_window_id,
            "source_component_ids": list(self.source_component_ids),
            "active_source_effect_id": self.active_source_effect_id,
            "context": dict(self.context),
            "disposition": self.disposition,
        }


@dataclass(frozen=True)
class SuppressionRecord:
    target_id: str
    event_or_window_id: str
    primitive_id: str
    dominant_source_component_ids: tuple[str, ...]
    suppressed_source_component_ids: tuple[str, ...]
    reason: str
    context: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "event_or_window_id": self.event_or_window_id,
            "primitive_id": self.primitive_id,
            "dominant_source_component_ids": list(self.dominant_source_component_ids),
            "suppressed_source_component_ids": list(self.suppressed_source_component_ids),
            "reason": self.reason,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class NormalizationResult:
    contributions: tuple[PrimitiveContribution, ...]
    suppressions: tuple[SuppressionRecord, ...]

    def by_family(self) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {
            "denial": [],
            "enablement": [],
            "retained_unpriced": [],
        }
        for contribution in self.contributions:
            result[contribution.family].append(contribution.to_dict())
        return result


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _value(value: Any, *names: str, default: Any = None) -> Any:
    row = _plain(value)
    if isinstance(row, Mapping):
        for name in names:
            if name in row:
                return row[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
    return default


def _source_key(component: ActiveComponent) -> str:
    return f"{component.effect_id}:{component.component_id}"


def _canonical_context(value: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Stable identity for contextual overlap without requiring values to be hashable."""

    ignored = {
        "unresolved_requirements",
        "source_condition_ids",
        "source_context_by_actor_id",
    }
    return tuple(
        (key, repr(value[key])) for key in sorted(value) if key not in ignored
    )


def _primitive_overlap_context(
    contribution: PrimitiveContribution,
) -> tuple[tuple[str, str], ...]:
    """Return mechanic identity after source-relative predicates are resolved.

    A Frightened source's identity is required to select its own line-of-sight
    context. Once that predicate passes, however, the resulting attack/check
    Disadvantage is the same boolean mechanic regardless of which visible source
    supplied it. Source identity remains material for the geometry-sensitive
    approach restriction and for conditions such as Charmed.
    """

    context = dict(contribution.context)
    source_conditions = set(context.get("source_condition_ids", ()))
    if (
        "frightened" in source_conditions
        and contribution.primitive_id
        in {"offensive_impairment_all_attacks", "ability_check_impairment"}
    ):
        context.pop("source_actor_id", None)
    return _canonical_context(context)


def _normalize_sense_resolution(value: Any) -> dict[str, Any]:
    """Return a JSON-safe copy of a typed or mapping sense-query result."""

    if isinstance(value, Mapping):
        normalized: Any = value
    else:
        as_dict_method = getattr(value, "as_dict", None)
        if not callable(as_dict_method):
            raise ControlStateError(
                "sense_resolution must be a SenseQueryResult-like value or an object"
            )
        normalized = as_dict_method()
    if not isinstance(normalized, Mapping):
        raise ControlStateError("sense_resolution.as_dict() must return an object")
    return deepcopy(dict(normalized))

class ControlState:
    """Mutable event state with deterministic, JSON-safe audit records."""

    def __init__(self) -> None:
        self._active: dict[str, list[ActiveComponent]] = {}
        self.audit_ledger: list[dict[str, Any]] = []
        self.refresh_records: list[dict[str, Any]] = []
        self.replacement_records: list[dict[str, Any]] = []
        self.suppression_records: list[SuppressionRecord] = []
        self._relationships: dict[str, dict[str, set[str]]] = {}

    def register_relationships(self, effect_id: str, relationships: Mapping[str, Any]) -> None:
        dominance: dict[str, set[str]] = {}
        for row in relationships.get("dominance", []):
            dominant = str(row["dominant_component_id"])
            dominance.setdefault(dominant, set()).update(
                str(item) for item in row["suppressed_component_ids"]
            )
        self._relationships[effect_id] = dominance

    def active_components(self, target_id: str | None = None) -> tuple[ActiveComponent, ...]:
        if target_id is not None:
            return tuple(self._active.get(target_id, ()))
        return tuple(
            component
            for current_target in sorted(self._active)
            for component in self._active[current_target]
        )

    def snapshot(self, target_id: str | None = None) -> list[dict[str, Any]]:
        return [component.to_dict() for component in self.active_components(target_id)]

    def _matching(
        self,
        target_id: str,
        component_id: str,
        effect_id: str | None = None,
    ) -> list[ActiveComponent]:
        return [
            component for component in self._active.get(target_id, [])
            if component.component_id == component_id
            and (effect_id is None or component.effect_id == effect_id)
        ]

    def apply_component(
        self,
        *,
        effect_id: str,
        component: Mapping[str, Any],
        target_id: str,
        source_actor_id: str,
        event_id: str,
        invocation_id: str,
        expiry_event_id: str | None = None,
        condition_immunities: Iterable[str] = (),
    ) -> ActiveComponent | None:
        component_id = str(component["component_id"])
        magnitude = deepcopy(dict(component["magnitude"]))
        condition = magnitude.get("condition") if magnitude.get("kind") == "condition" else None
        if condition is not None and condition in set(condition_immunities):
            record = SuppressionRecord(
                target_id,
                event_id,
                f"condition:{condition}",
                (),
                (f"{effect_id}:{component_id}",),
                "target_condition_immunity",
                {"condition": condition, "effect_id": effect_id},
            )
            self.suppression_records.append(record)
            self.audit_ledger.append({
                "event_id": event_id,
                "operation": "condition_immunity",
                "target_id": target_id,
                "effect_id": effect_id,
                "component_id": component_id,
                "condition": condition,
            })
            return None

        stacking = deepcopy(dict(component["stacking"]))
        key = str(stacking["key"])
        existing = [
            item for item in self._active.get(target_id, [])
            if item.effect_id == effect_id and item.stacking.get("key") == key
        ]
        if existing and stacking.get("mode") != "independent":
            if stacking.get("refresh") != "duration":
                self.audit_ledger.append({
                    "event_id": event_id,
                    "operation": "nonstacking_reapplication_suppressed",
                    "target_id": target_id,
                    "effect_id": effect_id,
                    "component_id": component_id,
                    "existing_component_ids": sorted(item.component_id for item in existing),
                })
                return existing[0]
            refreshed = existing[0]
            previous_expiry = refreshed.expiry_event_id
            refreshed.expiry_event_id = expiry_event_id
            record = {
                "event_id": event_id,
                "target_id": target_id,
                "effect_id": effect_id,
                "component_id": refreshed.component_id,
                "reason": "duration_refresh",
                "previous_expiry_event_id": previous_expiry,
                "new_expiry_event_id": expiry_event_id,
                "immediate_persistent_contribution": False,
            }
            self.refresh_records.append(record)
            self.audit_ledger.append({"operation": "refresh", **record})
            return refreshed

        remaining_tokens: int | None = None
        if magnitude.get("kind") == "attack_disadvantage" and magnitude.get("scope") == "next_attack":
            remaining_tokens = int(magnitude.get("count", 1))
        active = ActiveComponent(
            instance_id=f"{invocation_id}:{effect_id}:{target_id}:{component_id}",
            effect_id=effect_id,
            component_id=component_id,
            target_id=target_id,
            magnitude=magnitude,
            duration=deepcopy(dict(component["duration"])),
            stacking=stacking,
            source_actor_id=source_actor_id,
            applied_event_id=event_id,
            expiry_event_id=expiry_event_id,
            remaining_tokens=remaining_tokens,
        )
        self._active.setdefault(target_id, []).append(active)
        self._active[target_id].sort(key=lambda item: (item.effect_id, item.component_id, item.instance_id))
        self.audit_ledger.append({
            "event_id": event_id,
            "operation": "apply",
            "target_id": target_id,
            "component": active.to_dict(),
        })
        return active

    def terminate(
        self,
        *,
        target_id: str,
        component_id: str,
        event_id: str,
        effect_id: str | None = None,
        reason: str = "explicit_termination",
    ) -> tuple[ActiveComponent, ...]:
        removed = self._matching(target_id, component_id, effect_id)
        if removed:
            removed_ids = {item.instance_id for item in removed}
            self._active[target_id] = [
                item for item in self._active[target_id] if item.instance_id not in removed_ids
            ]
        self.audit_ledger.append({
            "event_id": event_id,
            "operation": "terminate",
            "target_id": target_id,
            "effect_id": effect_id,
            "component_id": component_id,
            "reason": reason,
            "removed_instance_ids": [item.instance_id for item in removed],
        })
        return tuple(removed)

    def refresh(
        self,
        *,
        target_id: str,
        component_id: str,
        event_id: str,
        effect_id: str | None = None,
        expiry_event_id: str | None = None,
    ) -> tuple[ActiveComponent, ...]:
        matches = self._matching(target_id, component_id, effect_id)
        if not matches:
            raise ControlStateError(
                f"Cannot refresh inactive component {component_id!r} on target {target_id!r}"
            )
        for component in matches:
            previous = component.expiry_event_id
            component.expiry_event_id = expiry_event_id if expiry_event_id is not None else previous
            record = {
                "event_id": event_id,
                "target_id": target_id,
                "effect_id": component.effect_id,
                "component_id": component.component_id,
                "reason": "explicit_refresh",
                "previous_expiry_event_id": previous,
                "new_expiry_event_id": component.expiry_event_id,
                "immediate_persistent_contribution": False,
            }
            self.refresh_records.append(record)
            self.audit_ledger.append({"operation": "refresh", **record})
        return tuple(matches)

    def expire(self, event_id: str) -> tuple[ActiveComponent, ...]:
        expired: list[ActiveComponent] = []
        for target_id in sorted(self._active):
            for component in tuple(self._active[target_id]):
                if component.expiry_event_id == event_id:
                    expired.extend(self.terminate(
                        target_id=target_id,
                        component_id=component.component_id,
                        event_id=event_id,
                        effect_id=component.effect_id,
                        reason="duration_expiry",
                    ))
        return tuple(expired)

    def end_condition(self, target_id: str, condition: str, event_id: str, reason: str) -> None:
        for component in tuple(self._active.get(target_id, ())):
            if component.magnitude == {"kind": "condition", "condition": condition}:
                self.terminate(
                    target_id=target_id,
                    component_id=component.component_id,
                    event_id=event_id,
                    effect_id=component.effect_id,
                    reason=reason,
                )

    def apply_branch(
        self,
        *,
        effect_id: str,
        branch: Mapping[str, Any],
        components_by_id: Mapping[str, Mapping[str, Any]],
        target_id: str,
        source_actor_id: str,
        event_id: str,
        invocation_id: str,
        required_active_component_ids: Sequence[str] = (),
        expiry_event_ids: Mapping[str, str | None] | None = None,
        condition_immunities: Iterable[str] = (),
        relationships: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply one already-resolved authority branch in mandated transition order."""

        before = self.snapshot(target_id)
        pre_ids = {item["component_id"] for item in before if item["effect_id"] == effect_id}
        missing_guards = sorted(set(required_active_component_ids) - pre_ids)
        if missing_guards:
            record = {
                "event_id": event_id,
                "operation": "guard_suppressed",
                "target_id": target_id,
                "effect_id": effect_id,
                "branch_id": branch.get("branch_id"),
                "missing_active_component_ids": missing_guards,
                "active_components_before": before,
                "active_components_after": before,
            }
            self.audit_ledger.append(record)
            return record

        expiry_event_ids = expiry_event_ids or {}
        if relationships is not None:
            self.register_relationships(effect_id, relationships)

        # 4. explicit terminates
        for component_id in branch.get("terminates", []):
            self.terminate(
                target_id=target_id,
                component_id=str(component_id),
                event_id=event_id,
                effect_id=effect_id,
            )

        # 5. explicit replaces
        for component_id in branch.get("replaces", []):
            removed = self.terminate(
                target_id=target_id,
                component_id=str(component_id),
                event_id=event_id,
                effect_id=effect_id,
                reason="explicit_branch_replacement",
            )
            record = {
                "event_id": event_id,
                "target_id": target_id,
                "effect_id": effect_id,
                "branch_id": branch.get("branch_id"),
                "dominant_component_ids": list(branch.get("applies", [])),
                "replaced_component_id": str(component_id),
                "replaced_instance_ids": [item.instance_id for item in removed],
                "reason": "explicit_branch_replacement",
            }
            self.replacement_records.append(record)

        # 6. apply new components
        for component_id in branch.get("applies", []):
            component_id = str(component_id)
            try:
                component = components_by_id[component_id]
            except KeyError as error:
                raise ControlStateError(f"Branch applies unknown component {component_id!r}") from error
            self.apply_component(
                effect_id=effect_id,
                component=component,
                target_id=target_id,
                source_actor_id=source_actor_id,
                event_id=event_id,
                invocation_id=invocation_id,
                expiry_event_id=expiry_event_ids.get(component_id),
                condition_immunities=condition_immunities,
            )

        # 7. explicit refreshes
        for component_id in branch.get("refreshes", []):
            component_id = str(component_id)
            self.refresh(
                target_id=target_id,
                component_id=component_id,
                event_id=event_id,
                effect_id=effect_id,
                expiry_event_id=expiry_event_ids.get(component_id),
            )

        # 8/9. canonical dominance and primitive overlap are evaluated as a
        # non-destructive normalized view, so weaker longer state can resume.
        after = self.snapshot(target_id)
        record = {
            "event_id": event_id,
            "operation": "branch_transition",
            "target_id": target_id,
            "effect_id": effect_id,
            "branch_id": branch.get("branch_id"),
            "outcome": branch.get("outcome"),
            "active_components_before": before,
            "active_components_after": after,
            "transition_order": [
                "capture_pre_event_state",
                "evaluate_active_guards",
                "resolve_gate_branch",
                "terminates",
                "replaces",
                "applies",
                "refreshes",
                "canonical_dominance",
                "generic_primitive_overlap",
            ],
        }
        self.audit_ledger.append(record)
        return record

    def effective_speeds(
        self,
        target_id: str,
        base_speeds: Mapping[str, int | None],
        *,
        mixed_operation_order: Sequence[str] | None = None,
    ) -> dict[str, int | None]:
        """Apply typed mobility operations and fail closed on an unresolved mix."""

        unknown = sorted(set(base_speeds) - set(MOVEMENT_MODES))
        if unknown:
            raise ControlStateError(f"Unknown movement modes: {', '.join(unknown)}")
        active = self._active.get(target_id, [])
        zeros: dict[str, bool] = {mode: False for mode in MOVEMENT_MODES}
        denied: dict[str, bool] = {mode: False for mode in MOVEMENT_MODES}
        flat_groups: dict[str, dict[str, int]] = {mode: {} for mode in MOVEMENT_MODES}
        fractions: dict[str, list[tuple[int, int]]] = {mode: [] for mode in MOVEMENT_MODES}

        for component in active:
            magnitude = component.magnitude
            kind = magnitude.get("kind")
            modes = magnitude.get("movement_modes", MOVEMENT_MODES)
            if kind == "condition" and magnitude.get("condition") == "restrained":
                for mode in MOVEMENT_MODES:
                    zeros[mode] = True
            elif kind == "speed_zero":
                for mode in modes:
                    zeros[str(mode)] = True
            elif kind == "movement_option_denial":
                for mode in modes:
                    denied[str(mode)] = True
            elif kind == "speed_reduction":
                reduction = magnitude["reduction"]
                reduction_kind = reduction["kind"]
                for mode_value in modes:
                    mode = str(mode_value)
                    if reduction_kind == "flat_feet":
                        local_key = str(component.stacking.get("key", component.component_id))
                        key = f"{component.effect_id}:{local_key}"
                        value = int(reduction["value"])
                        if component.stacking.get("mode") in {"stacks", "independent"}:
                            key = component.instance_id
                        flat_groups[mode][key] = max(flat_groups[mode].get(key, 0), value)
                    elif reduction_kind == "fraction":
                        fractions[mode].append((int(reduction["numerator"]), int(reduction["denominator"])))
                    elif reduction_kind == "terrain_multiplier":
                        # This is a movement-cost operation, never a Speed change.
                        continue

        unresolved_mixed_modes = [
            mode for mode in MOVEMENT_MODES
            if not zeros[mode]
            and not denied[mode]
            and flat_groups[mode]
            and fractions[mode]
        ]
        if unresolved_mixed_modes:
            if tuple(mixed_operation_order or ()) not in {("flat", "fraction"), ("fraction", "flat")}:
                raise ControlStateError(
                    "Mixed flat and fractional Speed changes require explicit flat/fraction operation order"
                )
        operation_order = tuple(mixed_operation_order or ("flat", "fraction"))

        result: dict[str, int | None] = {}
        for mode in MOVEMENT_MODES:
            base = base_speeds.get(mode)
            if base is None:
                result[mode] = None
                continue
            if zeros[mode] or denied[mode]:
                result[mode] = 0
                continue
            speed = int(base)
            flat = sum(flat_groups[mode].values())

            def apply_flat(value: int) -> int:
                return max(0, value - flat)

            def apply_fraction(value: int) -> int:
                current = value
                for numerator, denominator in fractions[mode]:
                    current = floor(current * (denominator - numerator) / denominator)
                return max(0, current)

            for operation in operation_order:
                speed = apply_flat(speed) if operation == "flat" else apply_fraction(speed)
            result[mode] = speed
        return result

    def area_movement_cost_multiplier(self, target_id: str) -> float:
        multipliers = [
            float(component.magnitude["movement_cost_multiplier"])
            for component in self._active.get(target_id, [])
            if component.magnitude.get("kind") == "difficult_terrain"
        ]
        return max([1.0, *multipliers])

    def _condition_specs(self, component: ActiveComponent, catalog: Any) -> list[Any]:
        from harness.control_catalog import expand_condition

        return list(expand_condition(catalog, str(component.magnitude["condition"])))

    @staticmethod
    def _predicate_result(predicate: Any, context: Mapping[str, Any]) -> bool | None:
        predicate = _plain(predicate)
        if isinstance(predicate, str):
            if predicate == "target_is_concentrating":
                if "target_is_concentrating" in context:
                    return bool(context["target_is_concentrating"])
                if "target_concentrating" in context:
                    return bool(context["target_concentrating"])
                return None
            if predicate == "target_airborne_without_hover":
                if "target_airborne" not in context:
                    return None
                fall_prevention = context.get(
                    "hover_or_explicit_fall_prevention",
                    context.get("target_can_hover", False),
                )
                return bool(context["target_airborne"]) and not bool(fall_prevention)
            key_map = {
                "fear_source_in_line_of_sight": "fear_source_in_line_of_sight",
                "no_effective_sight": "effective_sight",
                "attacker_within_5_feet": "attacker_distance_ft",
                "attacker_farther_than_5_feet": "attacker_distance_ft",
            }
            key = key_map.get(predicate, predicate)
            if key not in context:
                return None
            value = context[key]
            if predicate == "no_effective_sight":
                return not bool(value)
            if predicate == "attacker_within_5_feet":
                return float(value) <= 5
            if predicate == "attacker_farther_than_5_feet":
                return float(value) > 5
            return bool(value)
        if isinstance(predicate, Mapping):
            predicate_id = predicate.get("predicate_id")
            expected = predicate.get("value", True)
            aliases = {
                "alternative_sight_available": "alternative_sight_resolution",
                "target_is_concentrating": "target_concentrating",
                "target_is_airborne": "target_airborne",
                "hover_or_explicit_fall_prevention": "target_can_hover",
            }
            key = predicate.get("context_key", predicate.get("key"))
            if key is None:
                key = (
                    predicate_id
                    if predicate_id in context
                    else aliases.get(predicate_id, predicate_id)
                )
            if predicate_id == "attacker_distance_band":
                if "attacker_distance_ft" not in context:
                    return None
                actual_band = (
                    "within_5_feet"
                    if float(context["attacker_distance_ft"]) <= 5
                    else "farther_than_5_feet"
                )
                return actual_band == expected
            if not isinstance(key, str) or key not in context:
                return None
            actual = context[key]
            if predicate_id == "alternative_sight_available":
                if isinstance(actual, Mapping):
                    actual = actual.get("alternative_sight", actual.get("available"))
                elif hasattr(actual, "alternative_sight"):
                    actual = actual.alternative_sight
                if actual is None:
                    return None
                if isinstance(actual, str):
                    if actual in {"unresolved", "unknown"}:
                        return None
                    actual = actual in {"available", "yes", "true"}
            operator = predicate.get("operator", "equals")
            if operator == "equals":
                return actual == expected
            if operator == "not_equals":
                return actual != expected
            if operator == "at_most":
                return float(actual) <= float(expected)
            if operator == "greater_than":
                return float(actual) > float(expected)
            if operator == "truthy":
                return bool(actual)
            if operator == "falsy":
                return not bool(actual)
            raise ControlStateError(f"Unknown consequence predicate operator {operator!r}")
        raise ControlStateError(f"Unsupported consequence predicate {predicate!r}")

    def _candidate_from_spec(
        self,
        component: ActiveComponent,
        spec: Any,
        *,
        target_id: str,
        window_id: str,
        window_kind: str,
        context: Mapping[str, Any],
    ) -> PrimitiveContribution | None:
        primitive_id = str(_value(spec, "primitive_id", "id"))
        family = str(_value(spec, "family", "default_family"))
        unit = str(_value(spec, "unit"))
        disposition = str(_value(spec, "status", "disposition", default="candidate"))
        requirements = tuple(_value(spec, "context_requirements", "contextual_requirements", default=()) or ())
        requirement_aliases = {
            "target_is_concentrating": "target_concentrating",
            "target_airborne": "target_airborne",
            "hover_or_explicit_fall_prevention": "target_can_hover",
        }
        missing = [
            str(item)
            for item in requirements
            if str(item) not in context
            and requirement_aliases.get(str(item), str(item)) not in context
        ]
        predicates = _value(spec, "predicates", "conditional_predicates", default=()) or ()
        if isinstance(predicates, Mapping):
            predicates = [
                {"context_key": key, "operator": "equals", "value": value}
                for key, value in predicates.items()
            ]
        source_sensitive = (
            "source_actor_id" in {str(item) for item in requirements}
            or any(
                str(_value(predicate, "predicate_id", "context_key", "key", default=""))
                in {
                    "source_actor_id",
                    "source_in_line_of_sight",
                    "fear_source_in_line_of_sight",
                }
                for predicate in predicates
            )
        )
        failed = False
        unresolved = list(missing)
        for predicate in predicates:
            result = self._predicate_result(predicate, context)
            if result is None:
                unresolved.append(str(_value(predicate, "context_key", "key", default=predicate)))
            elif not result:
                failed = True
        if failed:
            return None
        contribution_context = dict(context)
        contribution_context.pop("source_context_by_actor_id", None)
        if not source_sensitive:
            contribution_context.pop("source_actor_id", None)
        qualifiers = _value(spec, "qualifiers", default=()) or ()
        qualifier_values: dict[str, Any] = {}
        for qualifier in qualifiers:
            qualifier = _plain(qualifier)
            if isinstance(qualifier, Mapping):
                qualifier_id = str(qualifier["qualifier_id"])
                qualifier_values[qualifier_id] = deepcopy(qualifier["value"])
                contribution_context[qualifier_id] = deepcopy(qualifier["value"])
        if primitive_id in {"save_disadvantage", "save_auto_failure"}:
            opportunity_ability = context.get("save_ability")
            primitive_ability = qualifier_values.get("save_ability")
            if opportunity_ability is not None and primitive_ability != opportunity_ability:
                return None
        source_conditions = _value(spec, "source_condition_ids", default=()) or ()
        if source_conditions:
            contribution_context["source_condition_ids"] = list(source_conditions)
        if unresolved:
            contribution_context["unresolved_requirements"] = sorted(set(unresolved))
            family = "retained_unpriced"
            disposition = "retained_unpriced"

        allowed_windows: dict[str, set[str]] = {
            "active_turn_denial": {"target_active_turn_opportunity"},
            "reaction_denial": {"reaction_window"},
            "offensive_impairment_next_attack": {"target_attack_opportunity"},
            "offensive_impairment_all_attacks": {"target_active_turn_opportunity"},
            "target_choice_restriction": {"target_active_turn_opportunity"},
            "sight_option_denial": {"sight_opportunity", "target_active_turn_opportunity"},
            "geometry_sensitive_approach_restriction": {"target_movement_opportunity", "target_active_turn_opportunity"},
            "defensive_attack_advantage": {"incoming_attack_opportunity", "controller_attack_opportunity"},
            "save_disadvantage": {"save_opportunity"},
            "save_auto_failure": {"save_opportunity"},
            "sight_dependent_opportunity": {"sight_opportunity", "controller_attack_opportunity"},
            "ability_check_impairment": {"ability_check_opportunity"},
            "speech_denial": {"speech_opportunity", "target_active_turn_opportunity"},
            "social_interaction_advantage": {"social_interaction_opportunity"},
            "concentration_break": {"condition_application", "concentration_window"},
            "persistent_elevation": {"state_window"},
            "fall_transition": {"instantaneous_resolution"},
            "nonsight_location_awareness": {"sight_opportunity", "location_opportunity"},
            "prone_incoming_attack_context": {"incoming_attack_opportunity", "controller_attack_opportunity"},
        }
        if primitive_id in allowed_windows and window_kind not in allowed_windows[primitive_id]:
            return None
        if primitive_id == "mobility_loss_feet":
            # Aggregate effective Speed is calculated once from every active source.
            return None
        if primitive_id == "concentration_break" and not context.get(
            "target_is_concentrating",
            context.get("target_concentrating", False),
        ):
            return None

        contextual_key = _value(spec, "context_key", default=None)
        if contextual_key is not None:
            contribution_context["context_key"] = contextual_key
        return PrimitiveContribution(
            family=family,
            primitive_id=primitive_id,
            unit=unit,
            quantity=float(_value(spec, "quantity", default=1.0)),
            target_id=target_id,
            event_or_window_id=window_id,
            source_component_ids=(_source_key(component),),
            active_source_effect_id=component.effect_id,
            context=contribution_context,
            disposition=disposition,
        )

    def _direct_candidates(
        self,
        component: ActiveComponent,
        *,
        target_id: str,
        window_id: str,
        window_kind: str,
        context: Mapping[str, Any],
    ) -> list[PrimitiveContribution]:
        magnitude = component.magnitude
        kind = magnitude.get("kind")
        result: list[PrimitiveContribution] = []
        candidate_context = dict(context)
        candidate_context.pop("source_actor_id", None)
        candidate_context.pop("source_context_by_actor_id", None)

        def add(family: str, primitive_id: str, unit: str, quantity: float = 1.0, **extra: Any) -> None:
            result.append(PrimitiveContribution(
                family,
                primitive_id,
                unit,
                float(quantity),
                target_id,
                window_id,
                (_source_key(component),),
                component.effect_id,
                {**candidate_context, **extra},
                "candidate" if family != "retained_unpriced" else "retained_unpriced",
            ))

        if kind == "attack_disadvantage":
            scope = magnitude["scope"]
            if scope == "next_attack" and window_kind == "target_attack_opportunity" and (component.remaining_tokens or 0) > 0:
                add("denial", "offensive_impairment_next_attack", "attack_opportunity_token")
            elif scope == "all_attacks" and window_kind == "target_active_turn_opportunity":
                add("denial", "offensive_impairment_all_attacks", "affected_target_turn")
        elif kind == "reaction_denial" and window_kind == "reaction_window":
            add("denial", "reaction_denial", "reaction_window")
        elif kind == "movement_option_denial" and window_kind == "target_movement_opportunity":
            for mode in magnitude["movement_modes"]:
                add("denial", "movement_mode_denial", "denied_movement_mode_window", movement_mode=mode)
        elif kind == "numerical_modifier" and window_kind in {"incoming_attack_opportunity", "controller_attack_opportunity"}:
            if magnitude.get("target") == "armor_class" and float(magnitude["value"]) < 0:
                add(
                    "enablement",
                    "defense_numerical_reduction",
                    "defense_point_opportunity",
                    abs(float(magnitude["value"])),
                    defense="armor_class",
                )
        elif kind == "persistent_elevation" and window_kind == "state_window":
            add("retained_unpriced", "persistent_elevation", "elevated_state_window")
        elif kind == "fall" and window_kind == "instantaneous_resolution":
            add("retained_unpriced", "fall_transition", "current_position_transition", origin=magnitude["origin"])
        return result

    def _mobility_candidates(
        self,
        target_id: str,
        window_id: str,
        context: Mapping[str, Any],
    ) -> tuple[list[PrimitiveContribution], list[SuppressionRecord]]:
        if "movement_mode_speeds_ft" in context:
            base_speeds = context["movement_mode_speeds_ft"]
        elif "base_speeds" in context:
            base_speeds = context["base_speeds"]
        else:
            raise ControlStateError(
                "Movement opportunity requires movement_mode_speeds_ft context"
            )
        effective = self.effective_speeds(
            target_id,
            base_speeds,
            mixed_operation_order=context.get("mixed_speed_operation_order"),
        )
        contributions: list[PrimitiveContribution] = []
        suppressions: list[SuppressionRecord] = []
        for mode in MOVEMENT_MODES:
            base = base_speeds.get(mode)
            current = effective.get(mode)
            if base is None or current is None or current >= base:
                continue
            dominant_sources: list[str] = []
            reduction_sources: list[str] = []
            for component in self._active.get(target_id, []):
                magnitude = component.magnitude
                kind = magnitude.get("kind")
                modes = magnitude.get("movement_modes", MOVEMENT_MODES)
                source = _source_key(component)
                if kind == "condition" and magnitude.get("condition") == "restrained":
                    dominant_sources.append(source)
                elif kind in {"speed_zero", "movement_option_denial"} and mode in modes:
                    dominant_sources.append(source)
                elif (
                    kind == "speed_reduction"
                    and mode in modes
                    and magnitude.get("reduction", {}).get("kind") in {"flat_feet", "fraction"}
                ):
                    reduction_sources.append(source)
            sources = sorted(set(dominant_sources or reduction_sources))
            if dominant_sources and reduction_sources:
                suppressions.append(SuppressionRecord(
                    target_id,
                    window_id,
                    "mobility_loss_feet",
                    tuple(sorted(set(dominant_sources))),
                    tuple(sorted(set(reduction_sources))),
                    "full_mobility_denial_dominates_speed_reduction",
                    {"movement_mode": mode},
                ))
            effect_ids = sorted({
                component.effect_id for component in self._active.get(target_id, [])
                if _source_key(component) in sources
            })
            contributions.append(PrimitiveContribution(
                "denial",
                "mobility_loss_feet",
                "feet_unavailable_at_movement_opportunity",
                float(base - current),
                target_id,
                window_id,
                tuple(sources),
                effect_ids[0] if len(effect_ids) == 1 else "multiple_effects",
                {**context, "movement_mode": mode, "base_speed_feet": base, "effective_speed_feet": current},
            ))
        terrain_multiplier = self.area_movement_cost_multiplier(target_id)
        if terrain_multiplier > 1 and "planned_route_feet" in context:
            planned = float(context["planned_route_feet"])
            sources = sorted({
                _source_key(component) for component in self._active.get(target_id, [])
                if component.magnitude.get("kind") == "difficult_terrain"
            })
            contributions.append(PrimitiveContribution(
                "denial",
                "mobility_loss_feet",
                "feet_unavailable_at_movement_opportunity",
                planned * (terrain_multiplier - 1),
                target_id,
                window_id,
                tuple(sources),
                "multiple_effects" if len(sources) > 1 else (
                    next(
                        component.effect_id for component in self._active[target_id]
                        if _source_key(component) == sources[0]
                    ) if sources else "area"
                ),
                {**context, "movement_cost_multiplier": terrain_multiplier, "cause": "difficult_terrain"},
            ))
        return contributions, suppressions


    @staticmethod
    def _sense_candidates(
        target_id: str,
        window_id: str,
        window_kind: str,
        context: Mapping[str, Any],
        sense_resolution: Mapping[str, Any] | None,
    ) -> list[PrimitiveContribution]:
        if (
            sense_resolution is None
            or window_kind not in {"location_opportunity", "sight_opportunity"}
        ):
            return []
        location_detection = sense_resolution.get("location_detection")
        if location_detection is False:
            return []
        if location_detection is not None and location_detection is not True:
            raise ControlStateError(
                "sense_resolution.location_detection must be true, false, or null"
            )

        missing = list(
            sense_resolution.get("location_detection_missing_context", ()) or ()
        )
        evidence = list(
            sense_resolution.get("location_detection_evidence", ()) or ()
        )
        contribution_context = {
            **context,
            "location_detection": location_detection,
            "location_detection_evidence": evidence,
            "location_detection_missing_context": missing,
        }
        if location_detection is None:
            contribution_context["unresolved_requirements"] = sorted(set(missing))
        return [PrimitiveContribution(
            family="retained_unpriced",
            primitive_id="nonsight_location_awareness",
            unit="location_detection_opportunity",
            quantity=1.0,
            target_id=target_id,
            event_or_window_id=window_id,
            source_component_ids=(f"target_sense:{target_id}:tremorsense",),
            active_source_effect_id=f"target_sense:{target_id}",
            context=contribution_context,
            disposition="retained_unpriced",
        )]
    def normalize_for_window(
        self,
        *,
        target_id: str,
        window_id: str,
        window_kind: str,
        context: Mapping[str, Any] | None = None,
        catalog: Any | None = None,
    ) -> NormalizationResult:
        context = dict(context or {})
        sense_resolution: dict[str, Any] | None = None
        if "sense_resolution" in context:
            sense_resolution = _normalize_sense_resolution(context["sense_resolution"])
            context["sense_resolution"] = sense_resolution
        if (
            sense_resolution is not None
            and "alternative_sight_resolution" not in context
        ):
            context["alternative_sight_resolution"] = sense_resolution

        active = list(self._active.get(target_id, []))
        if catalog is None and any(item.magnitude.get("kind") == "condition" for item in active):
            from harness.control_catalog import load_control_catalog

            catalog = load_control_catalog()
        candidates: list[PrimitiveContribution] = []
        suppressions: list[SuppressionRecord] = []
        active_turn_denial_sources: set[str] = set()
        for component in active:
            component_context = dict(context)
            source_contexts = context.get("source_context_by_actor_id")
            if source_contexts is not None:
                if not isinstance(source_contexts, Mapping):
                    raise ControlStateError(
                        "source_context_by_actor_id must be an object"
                    )
                source_context = source_contexts.get(
                    component.source_actor_id,
                    {},
                )
                if not isinstance(source_context, Mapping):
                    raise ControlStateError(
                        "Each source-specific context must be an object"
                    )
                component_context.update(source_context)
            component_context["source_actor_id"] = component.source_actor_id

            if component.magnitude.get("kind") == "condition":
                for spec in self._condition_specs(component, catalog):
                    if str(_value(spec, "primitive_id", "id")) == "active_turn_denial":
                        denial_probe = self._candidate_from_spec(
                            component,
                            spec,
                            target_id=target_id,
                            window_id=window_id,
                            window_kind="target_active_turn_opportunity",
                            context=component_context,
                        )
                        if denial_probe is not None and denial_probe.family == "denial":
                            active_turn_denial_sources.update(
                                denial_probe.source_component_ids
                            )
                    contribution = self._candidate_from_spec(
                        component,
                        spec,
                        target_id=target_id,
                        window_id=window_id,
                        window_kind=window_kind,
                        context=component_context,
                    )
                    if contribution is not None:
                        candidates.append(contribution)
            else:
                candidates.extend(self._direct_candidates(
                    component,
                    target_id=target_id,
                    window_id=window_id,
                    window_kind=window_kind,
                    context=component_context,
                ))
        if window_kind == "target_movement_opportunity":
            mobility_candidates, mobility_suppressions = self._mobility_candidates(
                target_id,
                window_id,
                context,
            )
            candidates.extend(mobility_candidates)
            suppressions.extend(mobility_suppressions)
        candidates.extend(self._sense_candidates(
            target_id,
            window_id,
            window_kind,
            context,
            sense_resolution,
        ))

        # Authority dominance is evaluated before generic overlap, without deleting
        # the suppressed active component.
        suppressed_sources: set[str] = set()
        for effect_id, edges in self._relationships.items():
            active_ids = {
                component.component_id for component in active if component.effect_id == effect_id
            }
            for dominant_id, dominated_ids in edges.items():
                if dominant_id not in active_ids:
                    continue
                for dominated_id in sorted(dominated_ids & active_ids):
                    suppressed_key = f"{effect_id}:{dominated_id}"
                    suppressed_sources.add(suppressed_key)
                    suppressions.append(SuppressionRecord(
                        target_id,
                        window_id,
                        "authority_component_dominance",
                        (f"{effect_id}:{dominant_id}",),
                        (suppressed_key,),
                        "explicit_authority_dominance",
                        {"effect_id": effect_id},
                    ))
        candidates = [
            contribution for contribution in candidates
            if not any(
                source in suppressed_sources
                for source in contribution.source_component_ids
            )
        ]

        # Active-turn denial removes every attack opportunity in that turn. A
        # caller may still script the unavailable window for audit purposes, so
        # suppress its impairment candidates and preserve next-attack tokens.
        dominant_sources = tuple(
            sorted(active_turn_denial_sources - suppressed_sources)
        )
        attack_opportunity_denied = (
            bool(dominant_sources)
            and window_kind == "target_attack_opportunity"
        )
        if dominant_sources and window_kind in {
            "target_active_turn_opportunity",
            "target_attack_opportunity",
        }:
            retained: list[PrimitiveContribution] = []
            for item in candidates:
                if item.primitive_id in {
                    "offensive_impairment_all_attacks",
                    "offensive_impairment_next_attack",
                }:
                    suppressions.append(SuppressionRecord(
                        target_id,
                        window_id,
                        item.primitive_id,
                        dominant_sources,
                        item.source_component_ids,
                        "active_turn_denial_removes_attack_opportunity",
                    ))
                else:
                    retained.append(item)
            candidates = retained

        # Automatic failure dominates Disadvantage for the same ability/opportunity.
        auto_abilities = {
            str(item.context.get("save_ability", item.context.get("ability")))
            for item in candidates if item.primitive_id == "save_auto_failure"
        }
        if auto_abilities:
            retained = []
            for item in candidates:
                ability = str(item.context.get("save_ability", item.context.get("ability")))
                if item.primitive_id == "save_disadvantage" and ability in auto_abilities:
                    dominant = tuple(sorted({
                        source for candidate in candidates
                        if candidate.primitive_id == "save_auto_failure"
                        and str(candidate.context.get("save_ability", candidate.context.get("ability"))) == ability
                        for source in candidate.source_component_ids
                    }))
                    suppressions.append(SuppressionRecord(
                        target_id,
                        window_id,
                        item.primitive_id,
                        dominant,
                        item.source_component_ids,
                        "automatic_failure_dominates_disadvantage",
                        {"save_ability": ability},
                    ))
                else:
                    retained.append(item)
            candidates = retained

        # A guaranteed candidate makes an otherwise identical unresolved candidate
        # unnecessary, while retaining an explicit account of the uncertainty that
        # was suppressed. Family/disposition are excluded only for this certainty
        # comparison.
        certainty_groups: dict[tuple[Any, ...], list[PrimitiveContribution]] = {}
        for item in candidates:
            certainty_key = (
                item.primitive_id,
                item.unit,
                _primitive_overlap_context(item),
            )
            certainty_groups.setdefault(certainty_key, []).append(item)
        certainty_retained: list[PrimitiveContribution] = []
        for group in certainty_groups.values():
            known = [
                item for item in group
                if item.disposition != "retained_unpriced"
                and item.family != "retained_unpriced"
            ]
            unresolved = [
                item for item in group
                if "unresolved_requirements" in item.context
            ]
            if not known or not unresolved:
                certainty_retained.extend(group)
                continue
            certainty_retained.extend(
                item for item in group if item not in unresolved
            )
            dominant_sources = tuple(sorted({
                source for item in known for source in item.source_component_ids
            }))
            for item in unresolved:
                suppressions.append(SuppressionRecord(
                    target_id,
                    window_id,
                    item.primitive_id,
                    dominant_sources,
                    item.source_component_ids,
                    "known_primitive_dominates_unresolved_duplicate",
                ))
        candidates = certainty_retained

        # Identical boolean/context primitives use maximum presence.  Quantitative
        # mobility has already been calculated from aggregate effective Speed.
        grouped: dict[tuple[Any, ...], list[PrimitiveContribution]] = {}
        for item in candidates:
            key = (
                item.family,
                item.primitive_id,
                item.unit,
                _primitive_overlap_context(item),
            )
            grouped.setdefault(key, []).append(item)
        normalized: list[PrimitiveContribution] = []
        for key in sorted(grouped, key=repr):
            group = grouped[key]
            if len(group) == 1 or group[0].primitive_id == "mobility_loss_feet":
                normalized.extend(group)
                continue
            dominant = sorted(
                group,
                key=lambda item: (-item.quantity, item.active_source_effect_id, item.source_component_ids),
            )[0]
            all_sources = tuple(sorted({source for item in group for source in item.source_component_ids}))
            merged_context = dict(dominant.context)
            if (
                "frightened" in set(merged_context.get("source_condition_ids", ()))
                and dominant.primitive_id
                in {"offensive_impairment_all_attacks", "ability_check_impairment"}
                and len({
                    item.context.get("source_actor_id") for item in group
                }) > 1
            ):
                merged_context.pop("source_actor_id", None)
            normalized.append(PrimitiveContribution(
                dominant.family,
                dominant.primitive_id,
                dominant.unit,
                max(item.quantity for item in group),
                dominant.target_id,
                dominant.event_or_window_id,
                all_sources,
                dominant.active_source_effect_id if len({item.active_source_effect_id for item in group}) == 1 else "multiple_effects",
                merged_context,
                dominant.disposition,
            ))
            for item in group:
                if item is dominant:
                    continue
                suppressions.append(SuppressionRecord(
                    target_id,
                    window_id,
                    item.primitive_id,
                    dominant.source_component_ids,
                    item.source_component_ids,
                    "identical_primitive_maximum_presence",
                ))

        # Consume every next-attack token that participated in this opportunity.
        if (
            window_kind == "target_attack_opportunity"
            and not attack_opportunity_denied
        ):
            for component in tuple(active):
                if (
                    component.magnitude.get("kind") == "attack_disadvantage"
                    and component.magnitude.get("scope") == "next_attack"
                    and (component.remaining_tokens or 0) > 0
                ):
                    component.remaining_tokens = (component.remaining_tokens or 0) - 1
                    if component.remaining_tokens == 0:
                        self.terminate(
                            target_id=target_id,
                            component_id=component.component_id,
                            event_id=window_id,
                            effect_id=component.effect_id,
                            reason="next_attack_token_consumed",
                        )

        normalized.sort(key=lambda item: (
            item.family,
            item.primitive_id,
            repr(_canonical_context(item.context)),
            item.source_component_ids,
        ))
        suppressions.sort(key=lambda item: (
            item.reason,
            item.primitive_id,
            item.dominant_source_component_ids,
            item.suppressed_source_component_ids,
        ))
        self.suppression_records.extend(suppressions)
        return NormalizationResult(tuple(normalized), tuple(suppressions))

    def final_normalized_state(self, catalog: Any | None = None) -> dict[str, Any]:
        """Return active mechanics, not a reward or combined Control Value."""

        result: dict[str, Any] = {}
        for target_id in sorted(self._active):
            result[target_id] = {
                "active_components": self.snapshot(target_id),
                "conditions": sorted({
                    component.magnitude["condition"]
                    for component in self._active[target_id]
                    if component.magnitude.get("kind") == "condition"
                }),
                "area_movement_cost_multiplier": self.area_movement_cost_multiplier(target_id),
            }
        return result


def concentration_check_dc(damage: int | float) -> int:
    """Shared exact SRD concentration DC formula for later-damage events."""

    if isinstance(damage, bool) or not isinstance(damage, (int, float)) or damage < 0:
        raise ControlStateError("Concentration damage must be a non-negative number")
    return min(30, max(10, floor(damage / 2)))
