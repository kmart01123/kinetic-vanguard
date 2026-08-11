"""Active control state and weight-free primitive normalization.

This module deliberately knows nothing about action selection or primitive weights.  It
stores every mechanically active component, applies authority-declared transitions in
their required order, and explains which primitive source is visible at a requested
event window.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass, replace
import hashlib
import json
from math import floor
from typing import Any, Iterable, Mapping, Sequence


NORMALIZATION_RULES_VERSION = "2.0.0"
MOVEMENT_MODES = ("walk", "fly", "swim", "climb", "burrow")
OUTGOING_ATTACK_WINDOWS = frozenset({
    "attack_opportunity",
    "target_attack_opportunity",
    "controller_attack_opportunity",
})
INCOMING_ATTACK_WINDOWS = frozenset({
    "attack_opportunity",
    "incoming_attack_opportunity",
    "controller_attack_opportunity",
})


class ControlStateError(ValueError):
    """Raised when state cannot be normalized without inventing mechanics."""


@dataclass
class ActiveComponent:
    """One component instance on one target.

    IDs from Control Authority are model-local. ``source_invocation_id`` keeps
    runtime selection typed; ``instance_id`` remains the exact component identity.
    """

    instance_id: str
    effect_id: str
    component_id: str
    target_id: str
    magnitude: dict[str, Any]
    duration: dict[str, Any]
    stacking: dict[str, Any]
    source_actor_id: str
    source_invocation_id: str
    applied_event_id: str
    expiry_event_id: str | None = None
    remaining_tokens: int | None = None
    contributed_windows: set[tuple[str, str]] = field(default_factory=set)
    condition_instance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "instance_id": self.instance_id,
            "effect_id": self.effect_id,
            "component_id": self.component_id,
            "target_id": self.target_id,
            "magnitude": deepcopy(self.magnitude),
            "duration": deepcopy(self.duration),
            "stacking": deepcopy(self.stacking),
            "source_actor_id": self.source_actor_id,
            "source_invocation_id": self.source_invocation_id,
            "applied_event_id": self.applied_event_id,
            "expiry_event_id": self.expiry_event_id,
            "remaining_tokens": self.remaining_tokens,
        }
        if self.condition_instance_id is not None:
            result["condition_instance_id"] = self.condition_instance_id
        return result


def _condition_identity_payload(
    *,
    condition_id: str,
    target_id: str,
    source_actor_id: str,
    source_program_id: str,
    source_effect_id: str,
    source_invocation_id: str,
    source_component_id: str,
    application_event_id: str,
    application_sequence: int,
    duration: Mapping[str, Any],
    expiry_event_id: str | None,
    parent_condition_instance_id: str | None,
    inclusion_edge_id: str | None,
    issuance_id: str,
    provenance_id: str,
) -> dict[str, Any]:
    return {
        "condition_id": condition_id,
        "target_id": target_id,
        "source_actor_id": source_actor_id,
        "source_program_id": source_program_id,
        "source_effect_id": source_effect_id,
        "source_invocation_id": source_invocation_id,
        "source_component_id": source_component_id,
        "application_event_id": application_event_id,
        "application_sequence": application_sequence,
        "duration": deepcopy(dict(duration)),
        "expiry_event_id": expiry_event_id,
        "parent_condition_instance_id": parent_condition_instance_id,
        "inclusion_edge_id": inclusion_edge_id,
        "issuance_id": issuance_id,
        "provenance_id": provenance_id,
    }


def condition_instance_id_for(
    *,
    condition_id: str,
    target_id: str,
    source_actor_id: str,
    source_program_id: str,
    source_effect_id: str,
    source_invocation_id: str,
    source_component_id: str,
    application_event_id: str,
    application_sequence: int,
    duration: Mapping[str, Any],
    expiry_event_id: str | None,
    parent_condition_instance_id: str | None = None,
    inclusion_edge_id: str | None = None,
    issuance_id: str,
    provenance_id: str,
) -> str:
    """Return the canonical identity for one exact condition application.

    The identity covers provenance, duration, and inclusion lineage. A replayed
    record whose identity-bearing fields were rewritten therefore cannot be
    silently accepted under its old instance ID.
    """

    string_fields = {
        "condition_id": condition_id,
        "target_id": target_id,
        "source_actor_id": source_actor_id,
        "source_program_id": source_program_id,
        "source_effect_id": source_effect_id,
        "source_invocation_id": source_invocation_id,
        "source_component_id": source_component_id,
        "application_event_id": application_event_id,
        "issuance_id": issuance_id,
        "provenance_id": provenance_id,
    }
    invalid_strings = sorted(
        label
        for label, value in string_fields.items()
        if not isinstance(value, str) or not value
    )
    if invalid_strings:
        raise ControlStateError(
            "Condition identity fields must be non-empty strings: "
            f"{invalid_strings}"
        )
    if (
        isinstance(application_sequence, bool)
        or not isinstance(application_sequence, int)
        or application_sequence < -1
    ):
        raise ControlStateError(
            "Condition application_sequence must be an integer at least -1"
        )
    if not isinstance(duration, Mapping):
        raise ControlStateError("Condition duration must be an object")
    if expiry_event_id is not None and (
        not isinstance(expiry_event_id, str) or not expiry_event_id
    ):
        raise ControlStateError(
            "Condition expiry_event_id must be a non-empty string or null"
        )
    lineage_values = (
        parent_condition_instance_id,
        inclusion_edge_id,
    )
    if (lineage_values[0] is None) != (lineage_values[1] is None):
        raise ControlStateError(
            "Condition parent identity and inclusion edge must both be null or "
            "both be present"
        )
    if any(
        value is not None and (not isinstance(value, str) or not value)
        for value in lineage_values
    ):
        raise ControlStateError(
            "Condition parent identity and inclusion edge must be non-empty strings"
        )

    payload = _condition_identity_payload(
        condition_id=condition_id,
        target_id=target_id,
        source_actor_id=source_actor_id,
        source_program_id=source_program_id,
        source_effect_id=source_effect_id,
        source_invocation_id=source_invocation_id,
        source_component_id=source_component_id,
        application_event_id=application_event_id,
        application_sequence=application_sequence,
        duration=duration,
        expiry_event_id=expiry_event_id,
        parent_condition_instance_id=parent_condition_instance_id,
        inclusion_edge_id=inclusion_edge_id,
        issuance_id=issuance_id,
        provenance_id=provenance_id,
    )
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ControlStateError(
            "Condition identity fields must be finite JSON values"
        ) from error
    return f"condition_{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class ConditionInstance:
    """One persistent condition lifecycle record, including inclusion lineage."""

    instance_id: str
    condition_id: str
    target_id: str
    source_actor_id: str
    source_program_id: str
    source_effect_id: str
    source_invocation_id: str
    source_component_id: str
    application_event_id: str
    application_sequence: int
    duration: Mapping[str, Any]
    expiry_event_id: str | None
    status: str
    end_event_id: str | None
    end_sequence: int | None
    end_reason: str | None
    parent_condition_instance_id: str | None
    inclusion_edge_id: str | None
    issuance_id: str
    provenance_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "condition_id": self.condition_id,
            "target_id": self.target_id,
            "source_actor_id": self.source_actor_id,
            "source_program_id": self.source_program_id,
            "source_effect_id": self.source_effect_id,
            "source_invocation_id": self.source_invocation_id,
            "source_component_id": self.source_component_id,
            "application_event_id": self.application_event_id,
            "application_sequence": self.application_sequence,
            "duration": deepcopy(dict(self.duration)),
            "expiry_event_id": self.expiry_event_id,
            "status": self.status,
            "end_event_id": self.end_event_id,
            "end_sequence": self.end_sequence,
            "end_reason": self.end_reason,
            "parent_condition_instance_id": self.parent_condition_instance_id,
            "inclusion_edge_id": self.inclusion_edge_id,
            "issuance_id": self.issuance_id,
            "provenance_id": self.provenance_id,
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
    if component.condition_instance_id is not None:
        return f"condition_instance:{component.condition_instance_id}"
    return f"{component.effect_id}:{component.component_id}"


def _condition_component_instance_id(
    *,
    source_invocation_id: str,
    source_effect_id: str,
    target_id: str,
    source_component_id: str,
    application_sequence: int,
    condition_instance_id: str,
) -> str:
    """Build an active condition-component identity from typed fields."""

    return (
        f"{source_invocation_id}:{source_effect_id}:{target_id}:"
        f"{source_component_id}:condition:{application_sequence}:"
        f"{condition_instance_id}"
    )


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

    def __init__(self, catalog: Any | None = None) -> None:
        self._active: dict[str, list[ActiveComponent]] = {}
        self.audit_ledger: list[dict[str, Any]] = []
        self.refresh_records: list[dict[str, Any]] = []
        self.replacement_records: list[dict[str, Any]] = []
        self.suppression_records: list[SuppressionRecord] = []
        self._relationships: dict[str, dict[str, set[str]]] = {}
        self._catalog = catalog
        self._condition_instances: dict[str, ConditionInstance] = {}
        self._condition_lifecycle: list[dict[str, Any]] = []
        self._next_condition_sequence = 0

    def __deepcopy__(self, memo: dict[int, Any]) -> "ControlState":
        """Clone mutable execution state while sharing the immutable catalog.

        Catalog definitions intentionally contain mapping proxies.  They are a
        validated read-only contract, not execution state, so atomic preflight
        clones must retain that exact object while independently copying every
        mutable state and audit store.
        """

        clone = type(self)(catalog=self._catalog)
        memo[id(self)] = clone
        for name, value in self.__dict__.items():
            if name == "_catalog":
                continue
            setattr(clone, name, deepcopy(value, memo))
        return clone

    @staticmethod
    def _condition_sequence(value: int | None, fallback: int) -> int:
        if value is None:
            return fallback
        if isinstance(value, bool) or not isinstance(value, int) or value < -1:
            raise ControlStateError(
                "Condition event sequence must be an integer at least -1"
            )
        return value

    @staticmethod
    def _condition_text(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise ControlStateError(f"{label} must be a non-empty string")
        return value

    def _condition_catalog(self) -> Any:
        if self._catalog is None:
            from harness.control_catalog import load_control_catalog

            self._catalog = load_control_catalog()
        return self._catalog

    def _catalog_conditions(self) -> Mapping[str, Any]:
        catalog = self._condition_catalog()
        if isinstance(catalog, Mapping):
            conditions = catalog.get("conditions")
        else:
            conditions = getattr(catalog, "conditions", None)
        if not isinstance(conditions, Mapping):
            raise ControlStateError("Condition catalog must expose a conditions object")
        return conditions

    @staticmethod
    def _definition_includes(definition: Any, label: str) -> tuple[str, ...]:
        includes = _value(definition, "includes", default=None)
        if (
            not isinstance(includes, Sequence)
            or isinstance(includes, (str, bytes))
            or any(not isinstance(item, str) or not item for item in includes)
        ):
            raise ControlStateError(f"{label}.includes must be an array of condition IDs")
        normalized = tuple(includes)
        if len(normalized) != len(set(normalized)):
            raise ControlStateError(f"{label}.includes contains duplicate lineage")
        return normalized

    def _build_condition_instances(
        self,
        *,
        condition_id: str,
        target_id: str,
        source_actor_id: str,
        source_program_id: str,
        source_effect_id: str,
        source_invocation_id: str,
        source_component_id: str,
        application_event_id: str,
        application_sequence: int,
        duration: Mapping[str, Any],
        expiry_event_id: str | None,
        issuance_id: str,
        provenance_id: str,
        supplied_root_instance_id: str | None,
    ) -> tuple[ConditionInstance, ...]:
        """Preflight and build one complete inclusion lineage without mutation."""

        conditions = self._catalog_conditions()
        planned: list[ConditionInstance] = []
        path: list[str] = []
        seen_conditions: dict[str, str] = {}

        def visit(
            current_condition_id: str,
            *,
            parent: ConditionInstance | None,
            edge_index: int | None,
        ) -> None:
            if current_condition_id in path:
                cycle_start = path.index(current_condition_id)
                cycle = (*path[cycle_start:], current_condition_id)
                raise ControlStateError(
                    f"Condition inclusion cycle: {' -> '.join(cycle)}"
                )
            if current_condition_id in seen_conditions:
                raise ControlStateError(
                    "Condition inclusion lineage repeats condition "
                    f"{current_condition_id!r}"
                )
            try:
                definition = conditions[current_condition_id]
            except KeyError as error:
                owner = parent.condition_id if parent is not None else condition_id
                raise ControlStateError(
                    f"Broken condition inclusion from {owner!r} to "
                    f"unknown condition {current_condition_id!r}"
                ) from error
            inclusion_edge_id = None
            parent_instance_id = None
            if parent is not None:
                parent_instance_id = parent.instance_id
                inclusion_edge_id = (
                    f"{parent.condition_id}:includes:{edge_index}:"
                    f"{current_condition_id}"
                )
            computed_id = condition_instance_id_for(
                condition_id=current_condition_id,
                target_id=target_id,
                source_actor_id=source_actor_id,
                source_program_id=source_program_id,
                source_effect_id=source_effect_id,
                source_invocation_id=source_invocation_id,
                source_component_id=source_component_id,
                application_event_id=application_event_id,
                application_sequence=application_sequence,
                duration=duration,
                expiry_event_id=expiry_event_id,
                parent_condition_instance_id=parent_instance_id,
                inclusion_edge_id=inclusion_edge_id,
                issuance_id=issuance_id,
                provenance_id=provenance_id,
            )
            if parent is None and supplied_root_instance_id is not None:
                if supplied_root_instance_id != computed_id:
                    raise ControlStateError(
                        "Supplied condition_instance_id does not match its "
                        "canonical condition identity"
                    )
            if computed_id in self._condition_instances or any(
                item.instance_id == computed_id for item in planned
            ):
                raise ControlStateError(
                    f"Duplicate condition instance ID: {computed_id}"
                )
            instance = ConditionInstance(
                instance_id=computed_id,
                condition_id=current_condition_id,
                target_id=target_id,
                source_actor_id=source_actor_id,
                source_program_id=source_program_id,
                source_effect_id=source_effect_id,
                source_invocation_id=source_invocation_id,
                source_component_id=source_component_id,
                application_event_id=application_event_id,
                application_sequence=application_sequence,
                duration=deepcopy(dict(duration)),
                expiry_event_id=expiry_event_id,
                status="active",
                end_event_id=None,
                end_sequence=None,
                end_reason=None,
                parent_condition_instance_id=parent_instance_id,
                inclusion_edge_id=inclusion_edge_id,
                issuance_id=issuance_id,
                provenance_id=provenance_id,
            )
            planned.append(instance)
            seen_conditions[current_condition_id] = instance.instance_id
            path.append(current_condition_id)
            includes = self._definition_includes(
                definition,
                f"conditions.{current_condition_id}",
            )
            for index, child_condition_id in enumerate(includes):
                visit(
                    child_condition_id,
                    parent=instance,
                    edge_index=index,
                )
            path.pop()

        visit(condition_id, parent=None, edge_index=None)
        return tuple(planned)

    def _validate_condition_registry(self) -> None:
        conditions = self._catalog_conditions() if self._condition_instances else {}
        children_by_parent: dict[str, list[ConditionInstance]] = {}
        active_root_ids: set[str] = set()
        for instance in self._condition_instances.values():
            expected_id = condition_instance_id_for(
                condition_id=instance.condition_id,
                target_id=instance.target_id,
                source_actor_id=instance.source_actor_id,
                source_program_id=instance.source_program_id,
                source_effect_id=instance.source_effect_id,
                source_invocation_id=instance.source_invocation_id,
                source_component_id=instance.source_component_id,
                application_event_id=instance.application_event_id,
                application_sequence=instance.application_sequence,
                duration=instance.duration,
                expiry_event_id=instance.expiry_event_id,
                parent_condition_instance_id=instance.parent_condition_instance_id,
                inclusion_edge_id=instance.inclusion_edge_id,
                issuance_id=instance.issuance_id,
                provenance_id=instance.provenance_id,
            )
            if instance.instance_id != expected_id:
                raise ControlStateError(
                    f"Condition instance identity was rewritten: {instance.instance_id}"
                )
            if instance.status not in {"active", "ended"}:
                raise ControlStateError(
                    f"Condition instance {instance.instance_id} has invalid status"
                )
            end_values = (
                instance.end_event_id,
                instance.end_sequence,
                instance.end_reason,
            )
            if instance.status == "active" and any(
                value is not None for value in end_values
            ):
                raise ControlStateError(
                    f"Active condition instance {instance.instance_id} has end metadata"
                )
            if instance.status == "ended" and any(
                value is None for value in end_values
            ):
                raise ControlStateError(
                    f"Ended condition instance {instance.instance_id} lacks end metadata"
                )
            if (
                instance.end_sequence is not None
                and instance.end_sequence < instance.application_sequence
            ):
                raise ControlStateError(
                    f"Condition instance {instance.instance_id} ends before application"
                )
            parent_id = instance.parent_condition_instance_id
            if parent_id is None:
                if instance.inclusion_edge_id is not None:
                    raise ControlStateError(
                        f"Root condition instance {instance.instance_id} has an inclusion edge"
                    )
                if instance.status == "active":
                    active_root_ids.add(instance.instance_id)
                continue
            parent = self._condition_instances.get(parent_id)
            if parent is None:
                raise ControlStateError(
                    f"Condition instance {instance.instance_id} has a broken parent chain"
                )
            for field_name in (
                "target_id",
                "source_actor_id",
                "source_program_id",
                "source_effect_id",
                "source_invocation_id",
                "source_component_id",
                "application_event_id",
                "application_sequence",
                "duration",
                "expiry_event_id",
                "issuance_id",
                "provenance_id",
            ):
                if getattr(instance, field_name) != getattr(parent, field_name):
                    raise ControlStateError(
                        f"Condition lineage rewrites {field_name} at "
                        f"{instance.instance_id}"
                    )
            try:
                parent_definition = conditions[parent.condition_id]
            except KeyError as error:
                raise ControlStateError(
                    f"Condition lineage has unknown parent {parent.condition_id!r}"
                ) from error
            includes = self._definition_includes(
                parent_definition,
                f"conditions.{parent.condition_id}",
            )
            matching_indexes = [
                index
                for index, child_id in enumerate(includes)
                if child_id == instance.condition_id
            ]
            if len(matching_indexes) != 1:
                raise ControlStateError(
                    f"Condition lineage edge from {parent.condition_id!r} to "
                    f"{instance.condition_id!r} is invalid"
                )
            expected_edge = (
                f"{parent.condition_id}:includes:{matching_indexes[0]}:"
                f"{instance.condition_id}"
            )
            if instance.inclusion_edge_id != expected_edge:
                raise ControlStateError(
                    f"Condition instance {instance.instance_id} has a rewritten "
                    "inclusion edge"
                )
            if (
                instance.status,
                instance.end_event_id,
                instance.end_sequence,
                instance.end_reason,
            ) != (
                parent.status,
                parent.end_event_id,
                parent.end_sequence,
                parent.end_reason,
            ):
                raise ControlStateError(
                    f"Included condition {instance.instance_id} lifecycle diverges "
                    f"from parent {parent.instance_id}"
                )
            children_by_parent.setdefault(parent_id, []).append(instance)

        for parent_id, children in children_by_parent.items():
            condition_ids = [child.condition_id for child in children]
            edge_ids = [child.inclusion_edge_id for child in children]
            if len(condition_ids) != len(set(condition_ids)) or len(edge_ids) != len(
                set(edge_ids)
            ):
                raise ControlStateError(
                    f"Condition parent {parent_id} has duplicate lineage"
                )

        for root in (
            item
            for item in self._condition_instances.values()
            if item.parent_condition_instance_id is None
        ):
            seen_conditions: set[str] = set()
            visiting: set[str] = set()

            def walk(current: ConditionInstance) -> None:
                if current.instance_id in visiting:
                    raise ControlStateError("Condition registry contains a lineage cycle")
                if current.condition_id in seen_conditions:
                    raise ControlStateError(
                        f"Condition lineage repeats condition {current.condition_id!r}"
                    )
                seen_conditions.add(current.condition_id)
                visiting.add(current.instance_id)
                for child in children_by_parent.get(current.instance_id, ()):
                    walk(child)
                visiting.remove(current.instance_id)

            walk(root)

        condition_components = tuple(
            component
            for component in self.active_components()
            if component.magnitude.get("kind") == "condition"
        )
        component_root_ids = {
            component.condition_instance_id
            for component in condition_components
        }
        component_instance_ids = {
            component.instance_id for component in condition_components
        }
        if (
            len(component_instance_ids) != len(condition_components)
            or len(component_root_ids) != len(condition_components)
        ):
            raise ControlStateError(
                "Active condition components must map one-to-one to unique roots"
            )
        if None in component_root_ids:
            raise ControlStateError(
                "Active condition component lacks a condition instance identity"
            )
        if component_root_ids != active_root_ids:
            raise ControlStateError(
                "Active condition components and condition roots diverge"
            )
        for component in condition_components:
            root = self._condition_instances.get(
                component.condition_instance_id or ""
            )
            if root is None or root.parent_condition_instance_id is not None:
                raise ControlStateError(
                    "Active condition component has a broken root identity"
                )
            if (
                component.target_id,
                component.effect_id,
                component.component_id,
                component.source_actor_id,
                component.source_invocation_id,
                component.applied_event_id,
                component.duration,
                component.expiry_event_id,
            ) != (
                root.target_id,
                root.source_effect_id,
                root.source_component_id,
                root.source_actor_id,
                root.source_invocation_id,
                root.application_event_id,
                root.duration,
                root.expiry_event_id,
            ):
                raise ControlStateError(
                    "Active condition component source identity diverges from "
                    f"root {root.instance_id}"
                )
            if (
                component.magnitude != {
                    "kind": "condition",
                    "condition": root.condition_id,
                }
                or component.remaining_tokens is not None
                or component.instance_id
                != _condition_component_instance_id(
                    source_invocation_id=root.source_invocation_id,
                    source_effect_id=root.source_effect_id,
                    target_id=root.target_id,
                    source_component_id=root.source_component_id,
                    application_sequence=root.application_sequence,
                    condition_instance_id=root.instance_id,
                )
            ):
                raise ControlStateError(
                    "Active condition component mechanics or identity diverges "
                    f"from root {root.instance_id}"
                )

    def instance_registry(
        self,
        target_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        self._validate_condition_registry()
        instances = (
            item
            for item in self._condition_instances.values()
            if target_id is None or item.target_id == target_id
        )
        return tuple(
            item.to_dict()
            for item in sorted(
                instances,
                key=lambda item: (
                    item.application_sequence,
                    item.target_id,
                    item.instance_id,
                ),
            )
        )

    def active_condition_instances(
        self,
        target_id: str | None = None,
    ) -> tuple[ConditionInstance, ...]:
        self._validate_condition_registry()
        return tuple(
            deepcopy(item)
            for item in sorted(
                (
                    instance
                    for instance in self._condition_instances.values()
                    if instance.status == "active"
                    and (target_id is None or instance.target_id == target_id)
                ),
                key=lambda item: (
                    item.application_sequence,
                    item.target_id,
                    item.instance_id,
                ),
            )
        )

    def derived_current_conditions(self, target_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    item.condition_id
                    for item in self.active_condition_instances(target_id)
                }
            )
        )

    def lineage_records(
        self,
        target_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        self._validate_condition_registry()
        records = []
        for child in self._condition_instances.values():
            if child.parent_condition_instance_id is None:
                continue
            if target_id is not None and child.target_id != target_id:
                continue
            parent = self._condition_instances[child.parent_condition_instance_id]
            records.append({
                "parent_condition_instance_id": parent.instance_id,
                "parent_condition_id": parent.condition_id,
                "child_condition_instance_id": child.instance_id,
                "child_condition_id": child.condition_id,
                "inclusion_edge_id": child.inclusion_edge_id,
                "target_id": child.target_id,
                "source_actor_id": child.source_actor_id,
                "source_program_id": child.source_program_id,
                "source_effect_id": child.source_effect_id,
                "source_invocation_id": child.source_invocation_id,
                "source_component_id": child.source_component_id,
                "application_event_id": child.application_event_id,
                "application_sequence": child.application_sequence,
                "expiry_event_id": child.expiry_event_id,
                "issuance_id": child.issuance_id,
                "provenance_id": child.provenance_id,
            })
        return tuple(
            sorted(
                records,
                key=lambda row: (
                    row["target_id"],
                    row["parent_condition_instance_id"],
                    row["inclusion_edge_id"],
                    row["child_condition_instance_id"],
                ),
            )
        )

    def condition_lifecycle_records(
        self,
        target_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        self._validate_condition_registry()
        records = (
            deepcopy(record)
            for record in self._condition_lifecycle
            if target_id is None or record["target_id"] == target_id
        )
        # A resolved branch terminates/replaces before it applies. Preserve that
        # order when both lifecycle phases share one timeline sequence.
        phase_order = {"condition_end": 0, "condition_application": 1}

        def lineage_position(instance_id: str) -> tuple[str, int]:
            instance = self._condition_instances[instance_id]
            depth = 0
            while instance.parent_condition_instance_id is not None:
                instance = self._condition_instances[
                    instance.parent_condition_instance_id
                ]
                depth += 1
            return instance.instance_id, depth

        def lifecycle_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
            root_id, depth = lineage_position(row["condition_instance_id"])
            phase = phase_order[row["kind"]]
            lineage_order = -depth if row["kind"] == "condition_end" else depth
            return (
                row["sequence"],
                phase,
                root_id,
                lineage_order,
                row["condition_instance_id"],
            )

        return tuple(
            sorted(
                records,
                key=lifecycle_key,
            )
        )

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
        instance_id: str | None = None,
        source_invocation_id: str | None = None,
        condition_instance_id: str | None = None,
    ) -> list[ActiveComponent]:
        return [
            component for component in self._active.get(target_id, [])
            if component.component_id == component_id
            and (effect_id is None or component.effect_id == effect_id)
            and (instance_id is None or component.instance_id == instance_id)
            and (
                source_invocation_id is None
                or component.source_invocation_id == source_invocation_id
            )
            and (
                condition_instance_id is None
                or component.condition_instance_id == condition_instance_id
            )
        ]

    def _plan_condition_application(
        self,
        *,
        condition_id: str,
        target_id: str,
        source_actor_id: str,
        source_program_id: str | None,
        source_effect_id: str,
        source_invocation_id: str,
        source_component_id: str,
        application_event_id: str,
        application_sequence: int | None,
        duration: Any,
        expiry_event_id: str | None,
        condition_instance_id: str | None,
        issuance_id: str | None,
        provenance_id: str | None,
    ) -> tuple[
        int,
        str,
        str,
        str,
        tuple[ConditionInstance, ...],
    ]:
        condition = self._condition_text(condition_id, "condition")
        target = self._condition_text(target_id, "target_id")
        source_actor = self._condition_text(
            source_actor_id,
            "source_actor_id",
        )
        if condition in {"charmed", "frightened"} and source_actor == target:
            raise ControlStateError(
                f"Condition {condition!r} requires an exact non-self source actor"
            )
        sequence = self._condition_sequence(
            application_sequence,
            self._next_condition_sequence,
        )
        source_program = self._condition_text(
            source_program_id
            if source_program_id is not None
            else source_effect_id,
            "source_program_id",
        )
        issuance = self._condition_text(
            issuance_id
            if issuance_id is not None
            else (
                f"issuance:{source_invocation_id}:{application_event_id}:"
                f"{sequence}:{source_effect_id}:{source_component_id}"
            ),
            "issuance_id",
        )
        provenance = self._condition_text(
            provenance_id if provenance_id is not None else issuance,
            "provenance_id",
        )
        if not isinstance(duration, Mapping):
            raise ControlStateError("Condition component duration must be an object")
        instances = self._build_condition_instances(
            condition_id=condition,
            target_id=target,
            source_actor_id=source_actor,
            source_program_id=source_program,
            source_effect_id=self._condition_text(
                source_effect_id,
                "effect_id",
            ),
            source_invocation_id=self._condition_text(
                source_invocation_id,
                "invocation_id",
            ),
            source_component_id=self._condition_text(
                source_component_id,
                "component_id",
            ),
            application_event_id=self._condition_text(
                application_event_id,
                "event_id",
            ),
            application_sequence=sequence,
            duration=duration,
            expiry_event_id=expiry_event_id,
            issuance_id=issuance,
            provenance_id=provenance,
            supplied_root_instance_id=condition_instance_id,
        )
        return sequence, source_program, issuance, provenance, instances

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
        application_sequence: int | None = None,
        condition_instance_id: str | None = None,
        source_program_id: str | None = None,
        issuance_id: str | None = None,
        provenance_id: str | None = None,
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

        condition_plan: tuple[
            int,
            str,
            str,
            str,
            tuple[ConditionInstance, ...],
        ] | None = None
        if condition is not None:
            condition_plan = self._plan_condition_application(
                condition_id=condition,
                target_id=target_id,
                source_actor_id=source_actor_id,
                source_program_id=source_program_id,
                source_effect_id=effect_id,
                source_invocation_id=invocation_id,
                source_component_id=component_id,
                application_event_id=event_id,
                application_sequence=application_sequence,
                duration=component.get("duration"),
                expiry_event_id=expiry_event_id,
                condition_instance_id=condition_instance_id,
                issuance_id=issuance_id,
                provenance_id=provenance_id,
            )

        stacking = deepcopy(dict(component["stacking"]))
        key = str(stacking["key"])
        # Condition lifecycle identity is independent from derived mechanical
        # overlap. Every separately issued condition application commits its own
        # root and inclusion lineage; normalization collapses identical primitive
        # consequences later. Generic component stacking must never end, refresh,
        # or suppress a different condition application.
        existing = [] if condition is not None else [
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
        condition_instances: tuple[ConditionInstance, ...] = ()
        root_condition_instance_id: str | None = None
        component_instance_id = f"{invocation_id}:{effect_id}:{target_id}:{component_id}"
        if condition is not None:
            if condition_plan is None:  # pragma: no cover - magnitude invariant
                raise ControlStateError("Condition application lacks a condition plan")
            sequence, _, _, _, condition_instances = condition_plan
            root_condition_instance_id = condition_instances[0].instance_id
            component_instance_id = _condition_component_instance_id(
                source_invocation_id=invocation_id,
                source_effect_id=effect_id,
                target_id=target_id,
                source_component_id=component_id,
                application_sequence=sequence,
                condition_instance_id=root_condition_instance_id,
            )
        active = ActiveComponent(
            instance_id=component_instance_id,
            effect_id=effect_id,
            component_id=component_id,
            target_id=target_id,
            magnitude=magnitude,
            duration=deepcopy(dict(component["duration"])),
            stacking=stacking,
            source_actor_id=source_actor_id,
            source_invocation_id=invocation_id,
            applied_event_id=event_id,
            expiry_event_id=expiry_event_id,
            remaining_tokens=remaining_tokens,
            condition_instance_id=root_condition_instance_id,
        )

        # The complete condition lineage was validated before either state store is
        # mutated. Committing these adjacent writes cannot expose a partial lineage.
        self._active.setdefault(target_id, []).append(active)
        self._active[target_id].sort(key=lambda item: (item.effect_id, item.component_id, item.instance_id))
        if condition_instances:
            for instance in condition_instances:
                self._condition_instances[instance.instance_id] = instance
                self._condition_lifecycle.append({
                    "kind": "condition_application",
                    "event_id": instance.application_event_id,
                    "sequence": instance.application_sequence,
                    "target_id": instance.target_id,
                    "condition_instance_id": instance.instance_id,
                    "condition_id": instance.condition_id,
                    "parent_condition_instance_id": (
                        instance.parent_condition_instance_id
                    ),
                    "inclusion_edge_id": instance.inclusion_edge_id,
                    "source_actor_id": instance.source_actor_id,
                    "source_program_id": instance.source_program_id,
                    "source_effect_id": instance.source_effect_id,
                    "source_invocation_id": instance.source_invocation_id,
                    "source_component_id": instance.source_component_id,
                    "issuance_id": instance.issuance_id,
                    "provenance_id": instance.provenance_id,
                })
            self._next_condition_sequence = max(
                self._next_condition_sequence,
                condition_instances[0].application_sequence + 1,
            )
        self.audit_ledger.append({
            "event_id": event_id,
            "operation": "apply",
            "target_id": target_id,
            "component": active.to_dict(),
        })
        return active

    def _condition_lineage(
        self,
        root_instance_id: str,
    ) -> tuple[ConditionInstance, ...]:
        root = self._condition_instances.get(root_instance_id)
        if root is None:
            raise ControlStateError(
                f"Unknown or stale condition instance ID: {root_instance_id}"
            )
        result: list[ConditionInstance] = []

        def append_lineage(instance: ConditionInstance) -> None:
            result.append(instance)
            children = sorted(
                (
                    child
                    for child in self._condition_instances.values()
                    if child.parent_condition_instance_id == instance.instance_id
                ),
                key=lambda child: child.instance_id,
            )
            for child in children:
                append_lineage(child)

        append_lineage(root)
        return tuple(result)

    def _refresh_condition_lineage_expiry(
        self,
        root_instance_id: str,
        expiry_event_id: str | None,
    ) -> None:
        self._validate_condition_registry()
        for instance in self._condition_lineage(root_instance_id):
            if (
                instance.status == "active"
                and instance.expiry_event_id != expiry_event_id
            ):
                raise ControlStateError(
                    "Condition expiry is identity-bound; refresh by applying a "
                    "new condition instance with application provenance"
                )

    def end_condition_instance(
        self,
        condition_instance_id: str,
        *,
        event_id: str,
        event_sequence: int,
        reason: str,
        expected_source_actor_id: str,
        expected_issuance_id: str | None = None,
    ) -> tuple[ConditionInstance, ...]:
        """End one exact instance and only its inclusion descendants.

        Raw condition names are intentionally not accepted. The expected source
        and optional issuance identity make a foreign or stale end request fail
        before either component or lifecycle state is mutated.
        """

        self._validate_condition_registry()
        instance_id = self._condition_text(
            condition_instance_id,
            "condition_instance_id",
        )
        instance = self._condition_instances.get(instance_id)
        if instance is None:
            raise ControlStateError(
                f"Unknown or stale condition instance ID: {instance_id}"
            )
        if instance.status != "active":
            raise ControlStateError(
                f"Condition instance {instance_id} already ended"
            )
        if instance.parent_condition_instance_id is not None:
            raise ControlStateError(
                "Included condition instances end only through their exact root "
                "lineage"
            )
        expected_source = self._condition_text(
            expected_source_actor_id,
            "expected_source_actor_id",
        )
        if instance.source_actor_id != expected_source:
            raise ControlStateError(
                f"Condition instance {instance_id} source actor mismatch"
            )
        if (
            expected_issuance_id is not None
            and instance.issuance_id != expected_issuance_id
        ):
            raise ControlStateError(
                f"Condition instance {instance_id} issuance mismatch"
            )
        end_event = self._condition_text(event_id, "event_id")
        end_reason = self._condition_text(reason, "reason")
        sequence = self._condition_sequence(event_sequence, 0)
        lineage = self._condition_lineage(instance_id)
        active_lineage = tuple(
            item for item in lineage if item.status == "active"
        )
        if any(sequence < item.application_sequence for item in active_lineage):
            raise ControlStateError(
                f"Condition end sequence {sequence} precedes its application"
            )

        linked_component: ActiveComponent | None = None
        if instance.parent_condition_instance_id is None:
            linked = [
                component
                for component in self._active.get(instance.target_id, ())
                if component.condition_instance_id == instance.instance_id
            ]
            if len(linked) != 1:
                raise ControlStateError(
                    f"Active condition root {instance.instance_id} has a broken "
                    "component link"
                )
            linked_component = linked[0]

        ended: list[ConditionInstance] = []
        for current in reversed(active_lineage):
            updated = replace(
                current,
                status="ended",
                end_event_id=end_event,
                end_sequence=sequence,
                end_reason=end_reason,
            )
            self._condition_instances[current.instance_id] = updated
            ended.append(updated)
            self._condition_lifecycle.append({
                "kind": "condition_end",
                "event_id": end_event,
                "sequence": sequence,
                "target_id": current.target_id,
                "condition_instance_id": current.instance_id,
                "condition_id": current.condition_id,
                "parent_condition_instance_id": (
                    current.parent_condition_instance_id
                ),
                "inclusion_edge_id": current.inclusion_edge_id,
                "source_actor_id": current.source_actor_id,
                "source_program_id": current.source_program_id,
                "source_effect_id": current.source_effect_id,
                "source_invocation_id": current.source_invocation_id,
                "source_component_id": current.source_component_id,
                "issuance_id": current.issuance_id,
                "provenance_id": current.provenance_id,
                "reason": end_reason,
            })
        if linked_component is not None:
            self._active[instance.target_id] = [
                component
                for component in self._active[instance.target_id]
                if component is not linked_component
            ]
        self._next_condition_sequence = max(
            self._next_condition_sequence,
            sequence + 1,
        )
        self.audit_ledger.append({
            "event_id": end_event,
            "event_sequence": sequence,
            "operation": "condition_end",
            "target_id": instance.target_id,
            "condition_instance_id": instance.instance_id,
            "ended_condition_instance_ids": [
                item.instance_id for item in ended
            ],
            "reason": end_reason,
        })
        return tuple(deepcopy(item) for item in ended)

    def terminate(
        self,
        *,
        target_id: str,
        component_id: str,
        event_id: str,
        effect_id: str | None = None,
        reason: str = "explicit_termination",
        instance_id: str | None = None,
        source_invocation_id: str | None = None,
        condition_instance_id: str | None = None,
        event_sequence: int | None = None,
    ) -> tuple[ActiveComponent, ...]:
        for label, value in (
            ("instance_id", instance_id),
            ("source_invocation_id", source_invocation_id),
            ("condition_instance_id", condition_instance_id),
        ):
            if value is not None:
                self._condition_text(value, label)
        removed = self._matching(
            target_id,
            component_id,
            effect_id,
            instance_id,
            source_invocation_id,
            condition_instance_id,
        )
        if not removed and any(
            value is not None
            for value in (
                instance_id,
                source_invocation_id,
                condition_instance_id,
            )
        ):
            raise ControlStateError(
                "Exact component, invocation, or condition selector is stale"
            )
        condition_components = [
            item
            for item in removed
            if item.condition_instance_id is not None
        ]
        if condition_components and all(
            value is None
            for value in (
                instance_id,
                source_invocation_id,
                condition_instance_id,
            )
        ):
            raise ControlStateError(
                "Condition component termination requires an exact instance or "
                "source invocation selector"
            )
        if len(condition_components) > 1:
            raise ControlStateError(
                "Ambiguous condition component termination requires an exact "
                "component instance_id"
            )
        ended_condition_instances: tuple[ConditionInstance, ...] = ()
        if condition_components:
            component = condition_components[0]
            sequence = self._condition_sequence(
                event_sequence,
                self._next_condition_sequence,
            )
            ended_condition_instances = self.end_condition_instance(
                component.condition_instance_id or "",
                event_id=event_id,
                event_sequence=sequence,
                reason=reason,
                expected_source_actor_id=component.source_actor_id,
            )
        noncondition_ids = {
            item.instance_id
            for item in removed
            if item.condition_instance_id is None
        }
        if noncondition_ids:
            self._active[target_id] = [
                item
                for item in self._active[target_id]
                if item.instance_id not in noncondition_ids
            ]
        self.audit_ledger.append({
            "event_id": event_id,
            "operation": "terminate",
            "target_id": target_id,
            "effect_id": effect_id,
            "component_id": component_id,
            "reason": reason,
            "selected_instance_id": instance_id,
            "selected_source_invocation_id": source_invocation_id,
            "selected_condition_instance_id": condition_instance_id,
            "removed_instance_ids": [item.instance_id for item in removed],
            "ended_condition_instance_ids": [
                item.instance_id for item in ended_condition_instances
            ],
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
        instance_id: str | None = None,
        source_invocation_id: str | None = None,
        condition_instance_id: str | None = None,
    ) -> tuple[ActiveComponent, ...]:
        for label, value in (
            ("instance_id", instance_id),
            ("source_invocation_id", source_invocation_id),
            ("condition_instance_id", condition_instance_id),
        ):
            if value is not None:
                self._condition_text(value, label)
        matches = self._matching(
            target_id,
            component_id,
            effect_id,
            instance_id,
            source_invocation_id,
            condition_instance_id,
        )
        if not matches:
            raise ControlStateError(
                f"Cannot refresh inactive component {component_id!r} on target {target_id!r}"
            )
        condition_matches = [
            component
            for component in matches
            if component.condition_instance_id is not None
        ]
        if condition_matches and all(
            value is None
            for value in (
                instance_id,
                source_invocation_id,
                condition_instance_id,
            )
        ):
            raise ControlStateError(
                "Condition component refresh requires an exact instance or "
                "source invocation selector"
            )
        if len(condition_matches) > 1:
            raise ControlStateError(
                "Ambiguous condition component refresh requires an exact "
                "component or condition instance ID"
            )
        for component in matches:
            if (
                component.condition_instance_id is not None
                and expiry_event_id is not None
                and expiry_event_id != component.expiry_event_id
            ):
                raise ControlStateError(
                    "Condition expiry is identity-bound; refresh by applying a "
                    "new condition instance with application provenance"
                )
        for component in matches:
            previous = component.expiry_event_id
            new_expiry = expiry_event_id if expiry_event_id is not None else previous
            if component.condition_instance_id is not None:
                self._refresh_condition_lineage_expiry(
                    component.condition_instance_id,
                    new_expiry,
                )
            component.expiry_event_id = new_expiry
            record = {
                "event_id": event_id,
                "target_id": target_id,
                "effect_id": component.effect_id,
                "component_id": component.component_id,
                "reason": "explicit_refresh",
                "selected_instance_id": instance_id,
                "selected_source_invocation_id": source_invocation_id,
                "selected_condition_instance_id": condition_instance_id,
                "refreshed_instance_id": component.instance_id,
                "previous_expiry_event_id": previous,
                "new_expiry_event_id": component.expiry_event_id,
                "immediate_persistent_contribution": False,
            }
            self.refresh_records.append(record)
            self.audit_ledger.append({"operation": "refresh", **record})
        return tuple(matches)

    def expire(
        self,
        event_id: str,
        *,
        event_sequence: int | None = None,
    ) -> tuple[ActiveComponent, ...]:
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
                        instance_id=component.instance_id,
                        source_invocation_id=component.source_invocation_id,
                        condition_instance_id=component.condition_instance_id,
                        event_sequence=event_sequence,
                    ))
        return tuple(expired)

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
        application_sequence: int | None = None,
        condition_instance_id: str | None = None,
        source_program_id: str | None = None,
        issuance_id: str | None = None,
        provenance_id: str | None = None,
        _atomic_preflight: bool = True,
    ) -> dict[str, Any]:
        """Apply one already-resolved authority branch in mandated transition order."""

        if _atomic_preflight:
            preview = deepcopy(self)
            record = preview.apply_branch(
                effect_id=effect_id,
                branch=branch,
                components_by_id=components_by_id,
                target_id=target_id,
                source_actor_id=source_actor_id,
                event_id=event_id,
                invocation_id=invocation_id,
                required_active_component_ids=required_active_component_ids,
                expiry_event_ids=expiry_event_ids,
                condition_immunities=condition_immunities,
                relationships=relationships,
                application_sequence=application_sequence,
                condition_instance_id=condition_instance_id,
                source_program_id=source_program_id,
                issuance_id=issuance_id,
                provenance_id=provenance_id,
                _atomic_preflight=False,
            )
            for name, value in preview.__dict__.items():
                if name != "_catalog":
                    setattr(self, name, value)
            return record

        before = self.snapshot(target_id)
        pre_ids = {
            item["component_id"]
            for item in before
            if item["effect_id"] == effect_id
            and item["source_invocation_id"] == invocation_id
        }
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
        applied_condition_ids = [
            str(component_id)
            for component_id in branch.get("applies", [])
            if (
                str(component_id) in components_by_id
                and _value(
                    components_by_id[str(component_id)].get("magnitude", {}),
                    "kind",
                )
                == "condition"
            )
        ]
        if condition_instance_id is not None and len(applied_condition_ids) != 1:
            raise ControlStateError(
                "condition_instance_id requires exactly one applied condition "
                "component in the branch"
            )

        def condition_transition_invocation(
            component_id: str,
        ) -> str | None:
            definition = components_by_id.get(component_id)
            if definition is None:
                return None
            magnitude = definition.get("magnitude", {})
            if not isinstance(magnitude, Mapping):
                return None
            return invocation_id if magnitude.get("kind") == "condition" else None

        # Resolve every condition transition selector before the first mutation.
        # A branch owns only condition components from its exact invocation; if
        # that still names multiple issued applications, the compiled transition
        # is underspecified and must fail atomically.
        for transition_name in ("terminates", "replaces", "refreshes"):
            for raw_component_id in branch.get(transition_name, []):
                transition_component_id = str(raw_component_id)
                selected_invocation = condition_transition_invocation(
                    transition_component_id
                )
                if selected_invocation is None:
                    continue
                matches = self._matching(
                    target_id,
                    transition_component_id,
                    effect_id,
                    source_invocation_id=selected_invocation,
                )
                condition_matches = [
                    component
                    for component in matches
                    if component.condition_instance_id is not None
                ]
                if len(condition_matches) > 1:
                    raise ControlStateError(
                        f"Branch {transition_name} for condition component "
                        f"{transition_component_id!r} is ambiguous within "
                        f"invocation {selected_invocation!r}"
                    )

        # 4. explicit terminates
        for component_id in branch.get("terminates", []):
            component_id = str(component_id)
            self.terminate(
                target_id=target_id,
                component_id=component_id,
                event_id=event_id,
                effect_id=effect_id,
                source_invocation_id=condition_transition_invocation(
                    component_id
                ),
                event_sequence=application_sequence,
            )

        # 5. explicit replaces
        for component_id in branch.get("replaces", []):
            component_id = str(component_id)
            selected_invocation = condition_transition_invocation(component_id)
            removed = self.terminate(
                target_id=target_id,
                component_id=component_id,
                event_id=event_id,
                effect_id=effect_id,
                reason="explicit_branch_replacement",
                source_invocation_id=selected_invocation,
                event_sequence=application_sequence,
            )
            record = {
                "event_id": event_id,
                "target_id": target_id,
                "effect_id": effect_id,
                "branch_id": branch.get("branch_id"),
                "dominant_component_ids": list(branch.get("applies", [])),
                "replaced_component_id": component_id,
                "selected_source_invocation_id": selected_invocation,
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
                application_sequence=application_sequence,
                condition_instance_id=(
                    condition_instance_id
                    if component_id in applied_condition_ids
                    else None
                ),
                source_program_id=source_program_id,
                issuance_id=issuance_id,
                provenance_id=provenance_id,
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
                source_invocation_id=condition_transition_invocation(
                    component_id
                ),
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

    def _condition_specs(self, condition_id: str, catalog: Any) -> list[Any]:
        conditions = (
            catalog.get("conditions")
            if isinstance(catalog, Mapping)
            else getattr(catalog, "conditions", None)
        )
        if not isinstance(conditions, Mapping) or condition_id not in conditions:
            raise ControlStateError(
                f"Unknown condition ID in live state: {condition_id!r}"
            )
        primitives = _value(
            conditions[condition_id],
            "primitives",
            default=None,
        )
        if (
            not isinstance(primitives, Sequence)
            or isinstance(primitives, (str, bytes))
        ):
            raise ControlStateError(
                f"conditions.{condition_id}.primitives must be an array"
            )
        return list(primitives)

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
            "offensive_impairment_next_attack": set(OUTGOING_ATTACK_WINDOWS),
            "offensive_impairment_all_attacks": set(OUTGOING_ATTACK_WINDOWS),
            "target_choice_restriction": {"action_proposal"},
            "sight_option_denial": {"sight_opportunity", "target_active_turn_opportunity"},
            "geometry_sensitive_approach_restriction": {"target_movement_opportunity", "target_active_turn_opportunity"},
            "defensive_attack_advantage": set(INCOMING_ATTACK_WINDOWS),
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
            "prone_incoming_attack_context": set(INCOMING_ATTACK_WINDOWS),
            "initiative_disadvantage": {"initiative_opportunity"},
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
            if scope == "next_attack" and window_kind in OUTGOING_ATTACK_WINDOWS and (component.remaining_tokens or 0) > 0:
                add("denial", "offensive_impairment_next_attack", "attack_opportunity")
            elif scope == "all_attacks" and window_kind in OUTGOING_ATTACK_WINDOWS:
                add("denial", "offensive_impairment_all_attacks", "attack_opportunity")
        elif kind == "reaction_denial" and window_kind == "reaction_window":
            add("denial", "reaction_denial", "reaction_window")
        elif kind == "movement_option_denial" and window_kind == "target_movement_opportunity":
            for mode in magnitude["movement_modes"]:
                add("denial", "movement_mode_denial", "denied_movement_mode_window", movement_mode=mode)
        elif kind == "numerical_modifier" and window_kind in INCOMING_ATTACK_WINDOWS:
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
        if any(item.magnitude.get("kind") == "condition" for item in active):
            self._validate_condition_registry()
            if catalog is None:
                catalog = self._condition_catalog()
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
                if component.condition_instance_id is None:
                    raise ControlStateError(
                        "Active condition component lacks a condition instance identity"
                    )
                for condition_instance in self._condition_lineage(
                    component.condition_instance_id
                ):
                    if condition_instance.status != "active":
                        continue
                    condition_component = replace(
                        component,
                        magnitude={
                            "kind": "condition",
                            "condition": condition_instance.condition_id,
                        },
                        condition_instance_id=condition_instance.instance_id,
                    )
                    for spec in self._condition_specs(
                        condition_instance.condition_id,
                        catalog,
                    ):
                        if str(_value(spec, "primitive_id", "id")) == "active_turn_denial":
                            denial_probe = self._candidate_from_spec(
                                condition_component,
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
                            condition_component,
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
            active_by_component_id: dict[str, list[ActiveComponent]] = {}
            for component in active:
                if component.effect_id == effect_id:
                    active_by_component_id.setdefault(
                        component.component_id,
                        [],
                    ).append(component)
            for dominant_id, dominated_ids in edges.items():
                dominant_components = active_by_component_id.get(dominant_id, ())
                if not dominant_components:
                    continue
                dominant_sources = tuple(
                    sorted(_source_key(component) for component in dominant_components)
                )
                for dominated_id in sorted(
                    dominated_ids & active_by_component_id.keys()
                ):
                    dominated_sources = tuple(
                        sorted(
                            _source_key(component)
                            for component in active_by_component_id[dominated_id]
                        )
                    )
                    suppressed_sources.update(dominated_sources)
                    suppressions.append(SuppressionRecord(
                        target_id,
                        window_id,
                        "authority_component_dominance",
                        dominant_sources,
                        dominated_sources,
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
            and window_kind in OUTGOING_ATTACK_WINDOWS
        )
        if dominant_sources and window_kind in OUTGOING_ATTACK_WINDOWS:
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
            window_kind in OUTGOING_ATTACK_WINDOWS
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
                            instance_id=component.instance_id,
                            source_invocation_id=component.source_invocation_id,
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
        target_ids = set(self._active)
        target_ids.update(
            instance.target_id for instance in self._condition_instances.values()
        )
        for target_id in sorted(target_ids):
            result[target_id] = {
                "active_components": self.snapshot(target_id),
                "conditions": list(self.derived_current_conditions(target_id)),
                "area_movement_cost_multiplier": self.area_movement_cost_multiplier(target_id),
            }
        return result


def concentration_check_dc(damage: int | float) -> int:
    """Shared exact SRD concentration DC formula for later-damage events."""

    if isinstance(damage, bool) or not isinstance(damage, (int, float)) or damage < 0:
        raise ControlStateError("Concentration damage must be a non-negative number")
    return min(30, max(10, floor(damage / 2)))
