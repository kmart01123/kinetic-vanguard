"""Public facade for the shared control consequence and timeline engine.

The runtime is intentionally a coordinator, not a planner. Callers choose an
effect, targets, legal choices, probability inputs, event order, initiative,
area convention, and displacement function. This module validates those
boundaries and packages the independently testable graph, state, and timeline
layers into one deterministic JSON result.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from harness.authority import DEFAULT_AUTHORITY
from harness.control_catalog import (
    DEFAULT_CONTROL_CATALOG,
    DEFAULT_CONTROL_PROVENANCE,
    DEFAULT_ENGINE_CONFIG,
    DIAGNOSTIC_FAMILIES,
    PRIMITIVE_CONTRACT,
    ControlCatalog,
    ControlEngineConfig,
    load_control_catalog,
    load_engine_config,
)
from harness.control_graph import (
    CONTROL_MAGNITUDE_KINDS,
    CompiledAuthority,
    CompiledComponent,
    CompiledEffect,
    ControlGraphError,
    ProbabilityContext,
    ProbabilityKernel,
    ReliabilityEvent,
    ReliabilityResult,
    ReliabilityTarget,
    SelectorContext,
    evaluate_reliability,
    load_compiled_control_authority,
    validate_selector_membership,
)
from harness.control_state import (
    MOVEMENT_MODES,
    NORMALIZATION_RULES_VERSION,
    ControlState,
    ControlStateError,
    NormalizationResult,
    PrimitiveContribution,
    SuppressionRecord,
)
from harness.control_targets import (
    DEFAULT_CONTROL_PROVENANCE as DEFAULT_TARGET_PROVENANCE,
    DEFAULT_CONTROL_SUPPLEMENT,
    ControlTarget,
    load_control_targets,
)
from harness.control_timeline import (
    AREA_RESPONSE_CONVENTIONS,
    DISPLACEMENT_FUNCTIONS,
    INITIATIVE_CONVENTIONS,
    TIMELINE_ENGINE_VERSION,
    ConcentrationTracker,
    DisplacementEpochs,
    TimelineError,
    TimelineEvent,
    TimelineSchedule,
    area_entry,
    area_response,
    build_schedule,
    displacement_function,
    prone_movement_response,
    resolve_expiry_index,
    typed_event_matches,
    vertical_displacement_vector,
)
from harness.model import DEFAULT_ROSTER, file_sha256


ENGINE_VERSION = "1.0.0"
DEFAULT_FIXTURE_CORPUS = (
    Path(__file__).resolve().parent / "tests" / "fixtures" / "control_engine_v1.json"
)

_EXPECTED_FIXTURE_CATEGORIES = MappingProxyType(
    {
        "catalog_and_senses": 8,
        "partial_reliability": 7,
        "overlap_and_dominance": 9,
        "prone": 6,
        "timing_and_initiative": 7,
        "repeat_saves": 5,
        "concentration": 6,
        "areas": 8,
        "displacement": 7,
        "weight_and_scope_boundary": 4,
    }
)
_FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "weights",
        "weight",
        "primitive_weight",
        "primitive_weights",
        "final_primitive_weights",
        "control_value",
        "combined_control_value",
        "classification",
        "balance_classification",
        "temperature",
        "optimized_action",
        "optimized_tier",
        "optimized_target",
        "optimized_resource",
        "optimized_comparator",
        "hot",
        "ideal",
        "cold",
        "sensitive",
    }
)


class ControlEngineError(ValueError):
    """Raised when the public facade would need to invent scenario policy."""


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ControlEngineError(f"{label} must be a non-empty trimmed string")
    return value


def _fraction_record(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _positive_fraction(value: Any, label: str) -> Fraction:
    """Parse one exact positive scenario multiplier."""

    if isinstance(value, bool):
        raise ControlEngineError(
            f"{label} must be a positive finite number"
        )
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int):
        result = Fraction(value)
    elif isinstance(value, float) and math.isfinite(value):
        result = Fraction(str(value))
    elif (
        isinstance(value, Mapping)
        and set(value) == {"numerator", "denominator"}
    ):
        numerator = value["numerator"]
        denominator = value["denominator"]
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int)
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or denominator <= 0
        ):
            raise ControlEngineError(f"{label} has an invalid exact fraction")
        result = Fraction(numerator, denominator)
    else:
        raise ControlEngineError(
            f"{label} must be a positive finite number"
        )
    if result <= 0:
        raise ControlEngineError(f"{label} must be positive")
    return result


def _json_safe(value: Any) -> Any:
    """Convert immutable runtime records to deterministic JSON values."""

    if isinstance(value, Fraction):
        return _fraction_record(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ControlEngineError("Engine results cannot contain non-finite numbers")
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(item) for item in sorted(value, key=repr)]
    if is_dataclass(value):
        return {
            field.name: _json_safe(getattr(value, field.name))
            for field in fields(value)
        }
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    raise ControlEngineError(
        f"Engine result contains a non-JSON value: {type(value).__name__}"
    )


def _assert_weight_free(value: Any, path: str = "result") -> None:
    if isinstance(value, Mapping):
        forbidden = sorted(
            str(key)
            for key in value
            if str(key).lower() in _FORBIDDEN_RESULT_KEYS
        )
        if forbidden:
            raise ControlEngineError(
                f"{path} contains forbidden weighted/planner fields: {forbidden}"
            )
        for key, item in value.items():
            _assert_weight_free(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _assert_weight_free(item, f"{path}[{index}]")


@dataclass(frozen=True)
class VersionProvenance:
    engine_version: str
    authority_projection_version: str
    authority_projection_digest: str
    target_supplement_digest: str
    consequence_catalog_version: str
    consequence_catalog_digest: str
    primitive_contract_version: str
    normalization_rules_version: str
    timeline_engine_version: str
    engine_config_version: str
    engine_config_digest: str
    initiative_convention: str
    initiative_convention_version: str
    area_response_convention: str
    area_response_convention_version: str
    displacement_function_id: str
    displacement_function_version: str

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(self)


@dataclass(frozen=True)
class ScenarioConvention:
    horizon_rounds: int
    initiative_convention: str
    area_response_convention: str
    displacement_function_id: str
    scripted_events_only: bool = True
    action_optimization: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(self)


@dataclass(frozen=True)
class DisplacementRequest:
    source_effect_id: str
    source_component_id: str
    target_id: str
    distance_feet: float
    distance_mode: str
    movement_mode: str
    reference_point: str
    axis: str
    direction: str
    destination: Mapping[str, Any]
    path: Mapping[str, Any]
    resolution_order: str
    caller_vector_required: bool
    derived_vector_feet: tuple[float, float, float] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_effect_id": self.source_effect_id,
            "source_component_id": self.source_component_id,
            "target_id": self.target_id,
            "distance_feet": self.distance_feet,
            "distance_mode": self.distance_mode,
            "movement_mode": self.movement_mode,
            "reference_point": self.reference_point,
            "axis": self.axis,
            "direction": self.direction,
            "destination": _json_safe(self.destination),
            "path": _json_safe(self.path),
            "resolution_order": self.resolution_order,
            "caller_vector_required": self.caller_vector_required,
            "derived_vector_feet": (
                list(self.derived_vector_feet)
                if self.derived_vector_feet is not None
                else None
            ),
        }



@dataclass(frozen=True)
class _ConcentrationAuthorityContext:
    """Engine-owned authority facts for one tracked concentration slot."""

    program: CompiledEffect
    schedule: TimelineSchedule
    selector_membership: Mapping[str, tuple[str, ...]]
    selector_context: SelectorContext
    invocation_id: str
    source_actor_id: str
    start_event_id: str
    choices: Mapping[str, str]
    concentration_component_ids: tuple[str, ...]
    area_ids: tuple[str, ...]
    area_component_ids: tuple[str, ...]
    maximum_duration: Mapping[str, Any]
    concentration_end_gate_ids: tuple[str, ...]
    fall_component_ids: tuple[str, ...]
    duration_boundary: Mapping[str, Any]


@dataclass(frozen=True)
class ControlEngineResult:
    """Weight-free, JSON-serializable result assembled from the runtime layers."""

    version_provenance: VersionProvenance
    scenario_convention: ScenarioConvention
    compiled_program_id: str
    target_ids: tuple[str, ...]
    gate_probabilities: tuple[Mapping[str, Any], ...]
    branch_probabilities: tuple[Mapping[str, Any], ...]
    component_reliability: tuple[Mapping[str, Any], ...]
    any_candidate_reliability: Mapping[str, Any]
    any_component_reliability: Mapping[str, Any]
    timeline: Mapping[str, Any]
    event_state_transitions: tuple[Mapping[str, Any], ...]
    audit_ledger: tuple[Mapping[str, Any], ...]
    primitive_contributions: Mapping[str, tuple[Mapping[str, Any], ...]]
    suppression_and_dominance_records: tuple[Mapping[str, Any], ...]
    refresh_and_replacement_records: tuple[Mapping[str, Any], ...]
    repeat_save_records: tuple[Mapping[str, Any], ...]
    area_membership_and_route_records: tuple[Mapping[str, Any], ...]
    prone_standing_records: tuple[Mapping[str, Any], ...]
    concentration_records: tuple[Mapping[str, Any], ...]
    displacement_epoch_records: tuple[Mapping[str, Any], ...]
    final_normalized_state: Mapping[str, Any]
    explored_state_count: int

    def __post_init__(self) -> None:
        if not self.compiled_program_id:
            raise ControlEngineError("compiled_program_id must be non-empty")
        if not self.target_ids or len(self.target_ids) != len(set(self.target_ids)):
            raise ControlEngineError("target_ids must be non-empty and unique")
        if set(self.primitive_contributions) != set(DIAGNOSTIC_FAMILIES):
            raise ControlEngineError(
                "primitive_contributions must expose all three diagnostic families"
            )
        if (
            isinstance(self.explored_state_count, bool)
            or not isinstance(self.explored_state_count, int)
            or self.explored_state_count < 1
        ):
            raise ControlEngineError(
                "explored_state_count must be a positive integer"
            )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "version_provenance": self.version_provenance.to_dict(),
            "scenario_convention": self.scenario_convention.to_dict(),
            "compiled_program_id": self.compiled_program_id,
            "target_ids": list(self.target_ids),
            "gate_probabilities": self.gate_probabilities,
            "branch_probabilities": self.branch_probabilities,
            "component_reliability": self.component_reliability,
            "any_candidate_reliability": self.any_candidate_reliability,
            "any_component_reliability": self.any_component_reliability,
            "timeline": self.timeline,
            "event_state_transitions": self.event_state_transitions,
            "audit_ledger": self.audit_ledger,
            "primitive_contributions": self.primitive_contributions,
            "suppression_and_dominance_records": self.suppression_and_dominance_records,
            "refresh_and_replacement_records": self.refresh_and_replacement_records,
            "repeat_save_records": self.repeat_save_records,
            "area_membership_and_route_records": self.area_membership_and_route_records,
            "prone_standing_records": self.prone_standing_records,
            "concentration_records": self.concentration_records,
            "displacement_epoch_records": self.displacement_epoch_records,
            "final_normalized_state": self.final_normalized_state,
            "explored_state_count": self.explored_state_count,
        }
        safe = _json_safe(result)
        _assert_weight_free(safe)
        return safe


def reliability_result_to_dict(result: ReliabilityResult) -> dict[str, Any]:
    """Serialize exact graph probabilities without replacing fractions by floats."""

    if not isinstance(result, ReliabilityResult):
        raise TypeError("result must be ReliabilityResult")
    return {
        "effect_id": result.effect_id,
        "target_ids": list(result.target_ids),
        "gate_probabilities": [
            {
                "event_id": row.event_id,
                "gate_id": row.gate_id,
                "target_ids": list(row.target_ids),
                "probability": _fraction_record(row.probability),
            }
            for row in result.gate_probabilities
        ],
        "branch_probabilities": [
            {
                "event_id": row.event_id,
                "gate_id": row.gate_id,
                "branch_id": row.branch_id,
                "outcome": row.outcome,
                "target_ids": list(row.target_ids),
                "probability": _fraction_record(row.probability),
            }
            for row in result.branch_probabilities
        ],
        "component_reliability": [
            {
                "component_id": row.component_id,
                "qualified_component_id": str(row.qualified_id),
                "target_id": row.target_id,
                "initially_applied": _fraction_record(row.initially_applied),
                "ever_applied": _fraction_record(row.ever_applied),
                "active_by_window": [
                    {
                        "window_id": window_id,
                        "probability": _fraction_record(probability),
                    }
                    for window_id, probability in row.active_by_window
                ],
            }
            for row in result.component_reliability
        ],
        "repeat_save_records": [
            {
                "event_id": row.event_id,
                "gate_id": row.gate_id,
                "target_id": row.target_id,
                "probability": _fraction_record(row.probability),
            }
            for row in result.repeat_survival
        ],
        "immunity_suppressions": [
            {
                "event_id": row.event_id,
                "gate_id": row.gate_id,
                "branch_id": row.branch_id,
                "target_id": row.target_id,
                "component_id": row.component_id,
                "condition": row.condition,
                "probability": _fraction_record(row.probability),
            }
            for row in result.immunity_suppressions
        ],
        "any_candidate_probability": _fraction_record(
            result.any_candidate_probability
        ),
        "any_component_probability": _fraction_record(
            result.any_component_probability
        ),
        "any_candidate_by_target": [
            {
                "target_id": target_id,
                "probability": _fraction_record(probability),
            }
            for target_id, probability in result.any_candidate_by_target
        ],
        "any_component_by_target": [
            {
                "target_id": target_id,
                "probability": _fraction_record(probability),
            }
            for target_id, probability in result.any_component_by_target
        ],
        "explored_state_count": result.final_world_count,
    }


class ControlEngine:
    """Validated single-runtime entrypoint for graph, state, and timeline consumers."""

    def __init__(
        self,
        *,
        catalog: ControlCatalog,
        config: ControlEngineConfig,
        authority: CompiledAuthority,
        targets: Sequence[ControlTarget],
        target_supplement_digest: str,
    ) -> None:
        self.catalog = catalog
        self.config = config
        self.authority = authority
        self.targets = tuple(targets)
        self._concentration_contexts: dict[
            ConcentrationTracker,
            _ConcentrationAuthorityContext,
        ] = {}
        self.target_supplement_digest = target_supplement_digest

    @classmethod
    def load(
        cls,
        *,
        authority_path: str | Path = DEFAULT_AUTHORITY,
        catalog_path: str | Path = DEFAULT_CONTROL_CATALOG,
        catalog_provenance_path: str | Path = DEFAULT_CONTROL_PROVENANCE,
        config_path: str | Path = DEFAULT_ENGINE_CONFIG,
        roster_path: Path = DEFAULT_ROSTER,
        target_supplement_path: Path = DEFAULT_CONTROL_SUPPLEMENT,
        target_provenance_path: Path = DEFAULT_TARGET_PROVENANCE,
    ) -> "ControlEngine":
        catalog = load_control_catalog(catalog_path, catalog_provenance_path)
        config = load_engine_config(config_path)
        authority = load_compiled_control_authority(authority_path)
        targets = load_control_targets(
            roster_path,
            target_supplement_path,
            target_provenance_path,
        )
        return cls(
            catalog=catalog,
            config=config,
            authority=authority,
            targets=targets,
            target_supplement_digest=file_sha256(target_supplement_path),
        )

    def program(self, effect_id: str) -> CompiledEffect:
        return self.authority.program(effect_id)

    def program_for(self, entity_id: str, tier: int) -> CompiledEffect:
        return self.authority.program_for(entity_id, tier)

    def new_state(self) -> ControlState:
        return ControlState()

    def new_displacement_epochs(self) -> DisplacementEpochs:
        return DisplacementEpochs()

    def candidate_component_ids(
        self,
        effect: CompiledEffect | str,
    ) -> tuple[str, ...]:
        """Return the mechanically derived denial/enablement candidate set.

        Condition components are candidates only when their catalog expansion
        contains a candidate denial or enablement primitive. Direct magnitude
        kinds map through the primitive contract. Retained-only fall and
        persistent-elevation components are deliberately excluded. Explicit
        candidate IDs may affirm this mechanical set, but cannot reclassify a
        retained-only component or demote a mechanical candidate.
        """

        program = self._canonical_effect(effect)
        result: list[str] = []
        for component in program.components:
            magnitude = component.magnitude.data.to_dict()
            kind = component.magnitude.kind
            primitive_ids: tuple[str, ...]
            if kind == "condition":
                condition_id = str(magnitude["condition"])
                primitive_ids = tuple(
                    spec.primitive_id
                    for spec in self.catalog.expand(condition_id)
                    if spec.status == "candidate"
                    and spec.family in {"denial", "enablement"}
                )
            elif kind == "forced_movement":
                primitive_ids = ("forced_displacement",)
            elif kind in {"speed_reduction", "speed_zero", "difficult_terrain"}:
                primitive_ids = ("mobility_loss_feet",)
            elif kind == "attack_disadvantage":
                scope = magnitude.get("scope")
                if scope == "next_attack":
                    primitive_ids = ("offensive_impairment_next_attack",)
                elif scope == "all_attacks":
                    primitive_ids = ("offensive_impairment_all_attacks",)
                else:
                    raise ControlEngineError(
                        f"Component {component.component_id!r} has an attack scope "
                        "without reviewed mechanical candidate semantics"
                    )
            elif kind == "reaction_denial":
                primitive_ids = ("reaction_denial",)
            elif kind == "movement_option_denial":
                primitive_ids = ("movement_mode_denial",)
            elif kind == "numerical_modifier":
                value = magnitude.get("value")
                if (
                    magnitude.get("target") == "armor_class"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and value < 0
                ):
                    primitive_ids = ("defense_numerical_reduction",)
                else:
                    raise ControlEngineError(
                        f"Component {component.component_id!r} has a numerical "
                        "modifier without reviewed mechanical candidate "
                        "semantics"
                    )
            elif kind in {"persistent_elevation", "fall"}:
                primitive_ids = ()
            else:
                raise ControlEngineError(
                    f"Component {component.component_id!r} lacks reviewed mechanical "
                    "candidate semantics"
                )
            for primitive_id in primitive_ids:
                definition = PRIMITIVE_CONTRACT[primitive_id]
                if (
                    definition.default_status != "candidate"
                    or definition.family not in {"denial", "enablement"}
                ):
                    raise ControlEngineError(
                        f"Primitive {primitive_id!r} is not a denial/enablement candidate"
                    )
            if primitive_ids:
                result.append(component.component_id)
        return tuple(result)

    @staticmethod
    def _state_component_definition(
        component: CompiledComponent,
    ) -> dict[str, Any]:
        return {
            "component_id": component.component_id,
            "magnitude": component.magnitude.data.to_dict(),
            "duration": component.duration.to_dict(),
            "stacking": component.stacking.data.to_dict(),
        }

    @staticmethod
    def _validated_selector_membership_for_targets(
        program: CompiledEffect,
        selector_membership: Mapping[str, Sequence[str]],
        target_ids: Iterable[str],
        selector_context: SelectorContext,
    ) -> dict[str, tuple[str, ...]]:
        try:
            validated = validate_selector_membership(
                program,
                target_ids=target_ids,
                selector_membership=selector_membership,
                selector_context=selector_context,
            )
        except (ControlGraphError, TypeError) as error:
            raise ControlEngineError(
                f"Selector membership is invalid: {error}"
            ) from error
        return dict(validated)

    @staticmethod
    def _validated_selector_membership(
        program: CompiledEffect,
        selector_membership: Mapping[str, Sequence[str]],
        schedule: TimelineSchedule,
        selector_context: SelectorContext,
    ) -> dict[str, tuple[str, ...]]:
        return ControlEngine._validated_selector_membership_for_targets(
            program,
            selector_membership,
            schedule.target_ids,
            selector_context,
        )

    @staticmethod
    def _gate_reachability(
        *,
        state: ControlState,
        program: CompiledEffect,
        gate_id: str,
        target_id: str,
        invocation_id: str,
        event_id: str,
        schedule: TimelineSchedule,
    ) -> dict[str, Any]:
        gate = program.gate(gate_id)
        matching_rows = [
            row
            for row in state.audit_ledger
            if row.get("effect_id") == program.effect_id
            and row.get("invocation_id") == invocation_id
            and row.get("gate_id") == gate_id
        ]
        if gate_id in program.root_gate_ids:
            if gate.role != "recurring" and any(
                row.get("target_id") == target_id for row in matching_rows
            ):
                raise ControlEngineError(
                    f"Root gate {gate_id!r} was already resolved for target "
                    f"{target_id!r} in invocation {invocation_id!r}"
                )
            return {"kind": "root_gate", "predecessor_gate_id": None}

        current_sequence = schedule.event(event_id).sequence
        for row in reversed(state.audit_ledger):
            if (
                row.get("operation") != "branch_transition"
                or row.get("effect_id") != program.effect_id
                or row.get("invocation_id") != invocation_id
                or gate_id not in row.get("next_gate_ids", ())
            ):
                continue
            try:
                predecessor_sequence = schedule.event(str(row["event_id"])).sequence
            except Exception:
                continue
            if predecessor_sequence <= current_sequence:
                return {
                    "kind": "branch_edge",
                    "predecessor_gate_id": row.get("gate_id"),
                    "predecessor_branch_id": row.get("branch_id"),
                    "predecessor_target_id": row.get("target_id"),
                    "predecessor_event_id": row.get("event_id"),
                }
        raise ControlEngineError(
            f"Gate {gate_id!r} is not a root and has no prior reachable branch "
            f"edge in invocation {invocation_id!r}"
        )

    def apply_resolved_branch(
        self,
        *,
        state: ControlState,
        effect: CompiledEffect | str,
        gate_id: str,
        outcome: str,
        target_id: str,
        source_actor_id: str,
        event_id: str,
        invocation_id: str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        choices: Mapping[str, str] | None = None,
        condition_immunities: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Apply one observed, reachable branch for one selected target.

        The caller must supply the same explicit selector membership used by the
        reliability layer. Branch arrays are filtered independently because an
        authority edge may fan out from a primary selector to secondary targets.
        """

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        target = _identifier(target_id, "target_id")
        source_actor = _identifier(source_actor_id, "source_actor_id")
        event = _identifier(event_id, "event_id")
        invocation = _identifier(invocation_id, "invocation_id")
        program = self._canonical_effect(effect)
        bindings = program.bind_choices(choices)
        gate = program.gate(_identifier(gate_id, "gate_id"))
        branch = gate.branch_for_outcome(_identifier(outcome, "outcome"))
        if target not in schedule.target_ids:
            raise ControlEngineError(
                f"target_id {target!r} is not part of the supplied schedule"
            )
        membership = self._validated_selector_membership(
            program,
            selector_membership,
            schedule,
            selector_context,
        )
        if not any(target in membership[selector_id] for selector_id in gate.selector_ids):
            raise ControlEngineError(
                f"Target {target!r} is not a member of any selector for gate "
                f"{gate.gate_id!r}"
            )
        try:
            schedule_event = schedule.event(event)
            event_matches = typed_event_matches(
                schedule_event,
                gate.trigger.data.to_dict(),
                target_id=target,
                triggering_turn_id=schedule_event.turn_id,
            )
        except Exception as error:
            raise ControlEngineError(
                f"Unable to validate event {event!r} for gate {gate.gate_id!r}: {error}"
            ) from error
        if not event_matches:
            raise ControlEngineError(
                f"Schedule event {event!r} does not match gate {gate.gate_id!r} "
                "trigger/owner/target semantics"
            )
        target_required = gate.trigger.kind in {"save", "hit", "damage_context"}
        if (
            (target_required and schedule_event.target_id != target)
            or (
                schedule_event.target_id is not None
                and schedule_event.target_id != target
            )
        ):
            raise ControlEngineError(
                f"Schedule event {event!r} targets {schedule_event.target_id!r}, "
                f"not {target!r}"
            )
        reachability = self._gate_reachability(
            state=state,
            program=program,
            gate_id=gate.gate_id,
            target_id=target,
            invocation_id=invocation,
            event_id=event,
            schedule=schedule,
        )

        enabled: dict[str, CompiledComponent] = {}
        for component in program.components:
            if (
                component.choice_id is None
                or bindings[component.choice_id] == component.choice_option_id
            ):
                enabled[component.component_id] = component

        def applies_to_target(component_id: str) -> bool:
            component = enabled.get(component_id)
            return component is not None and any(
                target in membership[selector_id]
                for selector_id in component.target_selector_ids
            )

        applies = [
            component_id
            for component_id in branch.applies
            if applies_to_target(component_id)
        ]
        replaces = [
            component_id
            for component_id in branch.replaces
            if applies_to_target(component_id)
        ]
        terminates = [
            component_id
            for component_id in branch.terminates
            if applies_to_target(component_id)
        ]
        refreshes = [
            component_id
            for component_id in branch.refreshes
            if applies_to_target(component_id)
        ]
        branch_definition = {
            "branch_id": branch.branch_id,
            "outcome": branch.outcome,
            "applies": applies,
            "replaces": replaces,
            "terminates": terminates,
            "refreshes": refreshes,
            "next_gate_ids": list(branch.next_gate_ids),
        }
        expiry_event_ids: dict[str, str | None] = {}
        for component_id in dict.fromkeys([*applies, *refreshes]):
            component = enabled[component_id]
            expiry_index = resolve_expiry_index(
                schedule,
                event,
                component.duration.to_dict(),
                target_id=target,
            )
            expiry_event_ids[component_id] = (
                schedule.events[expiry_index].event_id
                if expiry_index is not None
                else None
            )
        relationships = {
            "replacement_groups": [
                {
                    "group_id": group_id,
                    "component_ids": list(component_ids),
                }
                for group_id, component_ids
                in program.relationships.replacement_groups
            ],
            "dominance": [
                {
                    "dominant_component_id": dominant_id,
                    "suppressed_component_ids": list(suppressed_ids),
                }
                for dominant_id, suppressed_ids
                in program.relationships.dominance
            ],
        }
        transition = state.apply_branch(
            effect_id=program.effect_id,
            branch=branch_definition,
            components_by_id={
                component_id: self._state_component_definition(component)
                for component_id, component in enabled.items()
            },
            target_id=target,
            source_actor_id=source_actor,
            event_id=event,
            invocation_id=invocation,
            required_active_component_ids=gate.requires_active_component_ids,
            expiry_event_ids=expiry_event_ids,
            condition_immunities=condition_immunities,
            relationships=relationships,
        )
        transition.update(
            {
                "invocation_id": invocation,
                "gate_id": gate.gate_id,
                "next_gate_ids": list(branch.next_gate_ids),
                "gate_reachability": reachability,
                "filtered_branch": branch_definition,
                "refresh_expiry_event_ids": {
                    component_id: expiry_event_ids[component_id]
                    for component_id in refreshes
                },
            }
        )
        if transition.get("operation") != "branch_transition":
            return transition

        # ControlState emits its transition before this facade can resolve an
        # instantaneous magnitude. Move the same live ledger record behind the
        # termination rows so its after-snapshot is the true post-event state.
        if state.audit_ledger and state.audit_ledger[-1] is transition:
            state.audit_ledger.pop()
        instantaneous_contributions: list[dict[str, Any]] = []
        pending_displacement_requests: list[dict[str, Any]] = []
        instantaneous_resolutions: list[dict[str, Any]] = []
        active_identities = {
            (component.effect_id, component.component_id)
            for component in state.active_components(target)
        }
        for component_id in applies:
            component = enabled[component_id]
            if (
                not component.instantaneous
                or (program.effect_id, component_id) not in active_identities
            ):
                continue
            magnitude = component.magnitude.data.to_dict()
            if component.magnitude.kind == "fall":
                contribution = PrimitiveContribution(
                    family="retained_unpriced",
                    primitive_id="fall_transition",
                    unit="current_position_transition",
                    quantity=1.0,
                    target_id=target,
                    event_or_window_id=event,
                    source_component_ids=(component_id,),
                    active_source_effect_id=program.effect_id,
                    context={
                        "origin": magnitude["origin"],
                        "resolution": "instantaneous",
                    },
                    disposition="retained_unpriced",
                ).to_dict()
                instantaneous_contributions.append(contribution)
                resolution = "retained_fall_contribution"
            elif component.magnitude.kind == "forced_movement":
                pending_displacement_requests.append(
                    self.displacement_request(
                        component=component,
                        target_id=target,
                    ).to_dict()
                )
                resolution = "pending_typed_displacement_request"
            else:
                resolution = "instantaneous_state_termination"
            removed = state.terminate(
                target_id=target,
                component_id=component_id,
                event_id=event,
                effect_id=program.effect_id,
                reason="instantaneous_resolution",
            )
            instantaneous_resolutions.append(
                {
                    "component_id": component_id,
                    "magnitude_kind": component.magnitude.kind,
                    "resolution": resolution,
                    "removed_instance_ids": [item.instance_id for item in removed],
                }
            )
        transition["instantaneous_contributions"] = instantaneous_contributions
        transition["pending_displacement_requests"] = pending_displacement_requests
        transition["instantaneous_resolutions"] = instantaneous_resolutions
        transition["active_components_after"] = state.snapshot(target)
        if instantaneous_resolutions:
            transition["transition_order"] = [
                item
                for item in transition["transition_order"]
                if item not in {"canonical_dominance", "generic_primitive_overlap"}
            ] + [
                "instantaneous_resolution",
                "canonical_dominance",
                "generic_primitive_overlap",
            ]
        state.audit_ledger.append(transition)
        return transition

    def _component_source_id(
        self,
        component: CompiledComponent,
    ) -> str:
        namespace = component.qualified_id.namespace
        try:
            known = self.authority.program(namespace).component(
                component.component_id
            )
        except Exception:
            try:
                known = self.authority.mastery(namespace).component
            except Exception as error:
                raise ControlEngineError(
                    "Compiled component is not part of the loaded authority"
                ) from error
        if known != component:
            raise ControlEngineError(
                "Compiled component does not match the loaded authority"
            )
        return namespace

    def displacement_request(
        self,
        *,
        component: CompiledComponent,
        target_id: str,
    ) -> DisplacementRequest:
        """Create the typed geometry boundary for one authority movement component."""

        if not isinstance(component, CompiledComponent):
            raise TypeError("component must be CompiledComponent")
        target = _identifier(target_id, "target_id")
        source_effect_id = self._component_source_id(component)
        if component.magnitude.kind != "forced_movement":
            raise ControlEngineError(
                f"Component {component.component_id!r} is not forced movement"
            )
        magnitude = component.magnitude.data.to_dict()
        distance = float(magnitude["distance_feet"])
        movement_mode = str(magnitude["movement_mode"])
        axis = str(magnitude["axis"])
        derived = (
            vertical_displacement_vector(distance)
            if movement_mode == "lift" and axis == "vertical"
            else None
        )
        return DisplacementRequest(
            source_effect_id=source_effect_id,
            source_component_id=component.component_id,
            target_id=target,
            distance_feet=distance,
            distance_mode=str(magnitude["distance_mode"]),
            movement_mode=movement_mode,
            reference_point=str(magnitude["reference_point"]),
            axis=axis,
            direction=str(magnitude["direction"]),
            destination=dict(magnitude["destination"]),
            path=dict(magnitude["path"]),
            resolution_order=str(magnitude["resolution_order"]),
            caller_vector_required=derived is None,
            derived_vector_feet=derived,
        )

    def resolve_displacement(
        self,
        *,
        component: CompiledComponent,
        target_id: str,
        event_id: str,
        epochs: DisplacementEpochs,
        displacement_function_id: str,
        vector_feet: Sequence[int | float] | None = None,
    ) -> dict[str, Any]:
        """Apply a legal caller vector and emit one selected weight-free primitive."""

        if not isinstance(epochs, DisplacementEpochs):
            raise TypeError("epochs must be DisplacementEpochs")
        event = _identifier(event_id, "event_id")
        if displacement_function_id not in self.config.displacement_functions:
            raise ControlEngineError(
                f"Unknown displacement function: {displacement_function_id!r}"
            )
        request = self.displacement_request(
            component=component,
            target_id=target_id,
        )
        supplied = (
            request.derived_vector_feet
            if vector_feet is None
            else vector_feet
        )
        if supplied is None:
            raise ControlEngineError(
                "Caller must supply a legal displacement vector for this request"
            )
        if (
            not isinstance(supplied, Sequence)
            or isinstance(supplied, (str, bytes))
            or len(supplied) not in {2, 3}
        ):
            raise ControlEngineError(
                "displacement vector must contain two or three feet components"
            )
        vector: list[float] = []
        for value in supplied:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ControlEngineError(
                    "displacement vector components must be finite numbers"
                )
            vector.append(float(value))
        if len(vector) == 2:
            vector.append(0.0)
        if request.axis == "vertical" and (
            not math.isclose(vector[0], 0.0)
            or not math.isclose(vector[1], 0.0)
        ):
            raise ControlEngineError(
                "A vertical authority displacement requires a vertical vector"
            )
        if request.axis == "horizontal" and not math.isclose(
            vector[2],
            0.0,
        ):
            raise ControlEngineError(
                "A horizontal authority displacement requires a horizontal vector"
            )
        distance = math.sqrt(sum(value * value for value in vector))
        if request.distance_mode == "exact" and not math.isclose(
            distance,
            request.distance_feet,
            abs_tol=1e-9,
        ):
            raise ControlEngineError(
                "Exact authority displacement vector has the wrong distance"
            )
        if (
            request.distance_mode == "up_to"
            and distance > request.distance_feet + 1e-9
        ):
            raise ControlEngineError(
                "Authority displacement vector exceeds its maximum distance"
            )
        record = epochs.apply(
            target_id=request.target_id,
            vector_ft=vector,
            source_component_id=request.source_component_id,
        )
        selected = next(
            row
            for row in record["functions"]
            if row["function_id"] == displacement_function_id
        )
        selected_record = {
            key: value
            for key, value in record.items()
            if key != "functions"
        }
        selected_record["event_id"] = event
        selected_record["function_id"] = selected["function_id"]
        selected_record["function_version"] = selected["version"]
        selected_record["incremental_function_value"] = selected[
            "incremental_value"
        ]
        contribution = PrimitiveContribution(
            family="denial",
            primitive_id="forced_displacement",
            unit="selected_displacement_function_units",
            quantity=float(selected["incremental_value"]),
            target_id=request.target_id,
            event_or_window_id=event,
            source_component_ids=(request.source_component_id,),
            active_source_effect_id=request.source_effect_id,
            context={
                "movement_mode": request.movement_mode,
                "axis": request.axis,
                "reference_point": request.reference_point,
                "direction": request.direction,
                "destination": _json_safe(request.destination),
                "path": _json_safe(request.path),
                "resolution_order": request.resolution_order,
                "epoch": record["epoch"],
                "raw_vector_feet": list(vector),
                "raw_net_feet": record["raw_net_feet"],
                "previous_epoch_maximum_feet": (
                    record["previous_epoch_maximum_feet"]
                ),
                "new_epoch_maximum_feet": (
                    record["new_epoch_maximum_feet"]
                ),
                "displacement_function_id": displacement_function_id,
                "displacement_function_version": selected["version"],
            },
        )
        return {
            "request": request.to_dict(),
            "record": selected_record,
            "contribution": contribution.to_dict(),
        }



    def resolve_self_movement_epoch(
        self,
        *,
        epochs: DisplacementEpochs,
        state: ControlState,
        schedule: TimelineSchedule,
        target_id: str,
        event_id: str,
        legal: bool,
        base_speeds_ft: Mapping[str, int],
        movement_mode: str,
        mixed_speed_operation_order: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Apply a typed self-movement opportunity as an epoch boundary."""

        if not isinstance(epochs, DisplacementEpochs):
            raise TypeError("epochs must be DisplacementEpochs")
        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        target = _identifier(target_id, "target_id")
        event = schedule.event(_identifier(event_id, "event_id"))
        if (
            event.kind != "target_movement_opportunity"
            or event.target_id != target
        ):
            raise ControlEngineError(
                "Epoch boundaries require the target's typed movement opportunity"
            )
        movement_mode_value = _identifier(movement_mode, "movement_mode")
        if movement_mode_value not in MOVEMENT_MODES:
            raise ControlEngineError(
                f"movement_mode is unsupported: {movement_mode_value!r}"
            )
        movement_authority = self._movement_state_authority(
            state=state,
            target_id=target,
            base_speeds_ft=base_speeds_ft,
            mixed_speed_operation_order=mixed_speed_operation_order,
        )
        effective_speeds = movement_authority["effective_speeds_ft"]
        if movement_mode_value not in effective_speeds:
            raise ControlEngineError(
                "base_speeds_ft must supply the selected movement_mode"
            )
        movement_denied = (
            movement_mode_value in movement_authority["denied_modes"]
        )
        speed_zero = (
            effective_speeds[movement_mode_value] == 0
            and not movement_denied
        )
        record = epochs.self_movement_opportunity(
            target_id=target,
            legal=legal,
            speed_zero=speed_zero,
            movement_denied=movement_denied,
        )
        return {
            "record": {
                **record,
                "event_id": event.event_id,
                "source": "typed_self_movement_opportunity",
                "movement_mode": movement_mode_value,
                "movement_authority": movement_authority,
            },
        }

    @staticmethod
    def _movement_state_authority(
        *,
        state: ControlState,
        target_id: str,
        base_speeds_ft: Mapping[str, int],
        mixed_speed_operation_order: Sequence[str] | None,
    ) -> dict[str, Any]:
        """Derive effective movement facts exclusively from active state."""

        if not isinstance(base_speeds_ft, Mapping):
            raise ControlEngineError("base_speeds_ft must be an object")
        unknown_modes = [
            mode for mode in base_speeds_ft
            if mode not in MOVEMENT_MODES
        ]
        if unknown_modes:
            raise ControlEngineError(
                "base_speeds_ft contains unsupported movement modes: "
                f"{sorted(unknown_modes, key=repr)!r}"
            )
        base: dict[str, int] = {}
        for mode in MOVEMENT_MODES:
            if mode not in base_speeds_ft:
                continue
            value = base_speeds_ft[mode]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ControlEngineError(
                    f"base_speeds_ft.{mode} must be a non-negative integer"
                )
            base[mode] = value

        operation_order: tuple[str, ...] | None = None
        if mixed_speed_operation_order is not None:
            if (
                not isinstance(mixed_speed_operation_order, Sequence)
                or isinstance(mixed_speed_operation_order, (str, bytes))
            ):
                raise ControlEngineError(
                    "mixed_speed_operation_order must be an array"
                )
            operation_order = tuple(mixed_speed_operation_order)
            if operation_order not in (
                ("flat", "fraction"),
                ("fraction", "flat"),
            ):
                raise ControlEngineError(
                    "mixed_speed_operation_order must be flat/fraction "
                    "or fraction/flat"
                )
        try:
            effective_all = state.effective_speeds(
                target_id,
                base,
                mixed_operation_order=operation_order,
            )
        except (ControlStateError, KeyError, TypeError, ValueError) as error:
            raise ControlEngineError(
                f"Active movement state cannot be resolved: {error}"
            ) from error
        effective = {
            mode: effective_all[mode]
            for mode in MOVEMENT_MODES
            if mode in base
        }

        speed_zero_modes: set[str] = set()
        denied_modes: set[str] = set()
        source_component_ids: set[str] = set()
        for component in state.active_components(target_id):
            magnitude = component.magnitude
            kind = magnitude.get("kind")
            if kind == "condition" and magnitude.get("condition") == "restrained":
                speed_zero_modes.update(MOVEMENT_MODES)
                source_component_ids.add(component.component_id)
                continue
            if kind not in {
                "speed_zero",
                "speed_reduction",
                "movement_option_denial",
            }:
                continue
            modes = magnitude.get("movement_modes", MOVEMENT_MODES)
            if (
                not isinstance(modes, Sequence)
                or isinstance(modes, (str, bytes))
                or any(mode not in MOVEMENT_MODES for mode in modes)
            ):
                raise ControlEngineError(
                    f"Active component {component.component_id!r} has invalid "
                    "movement_modes"
                )
            normalized_modes = {str(mode) for mode in modes}
            if kind == "speed_zero":
                speed_zero_modes.update(normalized_modes)
            elif kind == "movement_option_denial":
                denied_modes.update(normalized_modes)
            source_component_ids.add(component.component_id)

        return {
            "source": "active_control_state",
            "base_speeds_ft": base,
            "effective_speeds_ft": effective,
            "speed_zero_modes": sorted(speed_zero_modes),
            "denied_modes": sorted(denied_modes),
            "mixed_speed_operation_order": (
                list(operation_order) if operation_order is not None else None
            ),
            "source_component_ids": sorted(source_component_ids),
        }

    @staticmethod
    def _state_adjusted_routes(
        *,
        state: ControlState,
        target_id: str,
        routes: Sequence[Mapping[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
        """Apply active difficult terrain to caller-supplied base route facts."""

        terrain_multiplier_value = state.area_movement_cost_multiplier(target_id)
        terrain_multiplier = _positive_fraction(
            terrain_multiplier_value,
            "active area movement-cost multiplier",
        )
        terrain_source_ids = sorted({
            component.component_id
            for component in state.active_components(target_id)
            if component.magnitude.get("kind") == "difficult_terrain"
        })
        if routes is None:
            return None, {
                "active_area_movement_cost_multiplier": terrain_multiplier,
                "terrain_source_component_ids": terrain_source_ids,
                "route_multipliers": [],
            }
        if (
            not isinstance(routes, Sequence)
            or isinstance(routes, (str, bytes))
        ):
            raise ControlEngineError("routes must be an array")
        adjusted: list[dict[str, Any]] = []
        multiplier_records: list[dict[str, Any]] = []
        for index, route in enumerate(routes):
            if not isinstance(route, Mapping):
                raise ControlEngineError(f"routes[{index}] must be an object")
            if "movement_cost_multiplier" not in route:
                raise ControlEngineError(
                    f"routes[{index}] must supply a base movement_cost_multiplier"
                )
            base_multiplier = _positive_fraction(
                route["movement_cost_multiplier"],
                f"routes[{index}].movement_cost_multiplier",
            )
            effective_multiplier = max(
                base_multiplier,
                terrain_multiplier,
            )
            adjusted.append({
                **dict(route),
                "movement_cost_multiplier": effective_multiplier,
            })
            multiplier_records.append({
                "route_index": index,
                "base_movement_cost_multiplier": base_multiplier,
                "effective_movement_cost_multiplier": effective_multiplier,
            })
        return adjusted, {
            "active_area_movement_cost_multiplier": terrain_multiplier,
            "terrain_source_component_ids": terrain_source_ids,
            "route_multipliers": multiplier_records,
        }

    def resolve_prone_movement(
        self,
        *,
        state: ControlState,
        schedule: TimelineSchedule,
        target_id: str,
        event_id: str,
        base_speeds_ft: Mapping[str, int],
        movement_mode: str,
        mixed_speed_operation_order: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Resolve the first legal Prone response and keep active state in sync."""

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        target = _identifier(target_id, "target_id")
        event = schedule.event(_identifier(event_id, "event_id"))
        if (
            event.kind != "target_movement_opportunity"
            or event.target_id != target
        ):
            raise ControlEngineError(
                "Prone movement requires the target's typed movement opportunity"
            )
        movement_mode_value = _identifier(movement_mode, "movement_mode")
        if movement_mode_value not in MOVEMENT_MODES:
            raise ControlEngineError(
                f"movement_mode is unsupported: {movement_mode_value!r}"
            )
        movement_authority = self._movement_state_authority(
            state=state,
            target_id=target,
            base_speeds_ft=base_speeds_ft,
            mixed_speed_operation_order=mixed_speed_operation_order,
        )
        effective_speeds = movement_authority["effective_speeds_ft"]
        if movement_mode_value not in effective_speeds:
            raise ControlEngineError(
                "base_speeds_ft must supply the selected movement_mode"
            )
        current_speed_ft = effective_speeds[movement_mode_value]
        movement_denied = (
            movement_mode_value in movement_authority["denied_modes"]
        )
        prone_before = [
            component
            for component in state.active_components(target)
            if component.magnitude.get("kind") == "condition"
            and component.magnitude.get("condition") == "prone"
        ]
        response = prone_movement_response(
            target_id=target,
            prone=bool(prone_before),
            current_speed_ft=current_speed_ft,
            movement_denied=movement_denied,
        )
        if response["stood"]:
            state.end_condition(
                target,
                "prone",
                event.event_id,
                "legal_stand",
            )
        active_after = state.snapshot(target)
        active_instance_ids = {row["instance_id"] for row in active_after}
        record = {
            "kind": "prone_movement_response",
            "event_id": event.event_id,
            "movement_mode": movement_mode_value,
            "movement_authority": movement_authority,
            **response,
            "ended_component_ids": sorted({
                component.component_id
                for component in prone_before
                if component.instance_id not in active_instance_ids
            }),
            "active_components_after": active_after,
        }
        state.audit_ledger.append({"operation": "prone_movement_response", **record})
        return record

    def resolve_compiled_area_entry(
        self,
        *,
        effect: CompiledEffect | str,
        target_ids: Sequence[str],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        target_id: str,
        turn_id: str,
        was_member: bool,
        is_member: bool,
        caused_by_area_movement: bool,
        prior_trigger_turn_ids: Iterable[str] = (),
        area_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve entry policy without accepting caller-authored authority fields."""

        program = self._canonical_effect(effect)
        target = _identifier(target_id, "target_id")
        validated_membership = self._validated_selector_membership_for_targets(
            program,
            selector_membership,
            target_ids,
            selector_context,
        )
        areas = {
            selector.area.area_id: selector.area
            for selector in program.selectors
            if selector.area is not None
        }
        if area_id is None:
            if len(areas) != 1:
                raise ControlEngineError(
                    "area_id is required unless the effect has exactly one area"
                )
            selected_area_id = next(iter(areas))
        else:
            selected_area_id = _identifier(area_id, "area_id")
            if selected_area_id not in areas:
                raise ControlEngineError(
                    "area_id is not part of the compiled effect"
                )
        area_selector_ids = {
            selector.selector_id
            for selector in program.selectors
            if selector.area is not None
            and selector.area.area_id == selected_area_id
        }
        if not any(
            target in validated_membership[selector_id]
            for selector_id in area_selector_ids
        ):
            raise ControlEngineError(
                f"Target {target!r} is not a member of the compiled area selector"
            )
        area = areas[selected_area_id]
        if area.entry_policy is None:
            raise ControlEngineError("The compiled area has no entry policy")
        policy = area.entry_policy.to_dict()
        if set(policy) != {"frequency", "moved_area_counts_as_entry"}:
            raise ControlEngineError(
                "The compiled area entry policy is unsupported"
            )
        response = area_entry(
            target_id=target,
            turn_id=turn_id,
            was_member=was_member,
            is_member=is_member,
            caused_by_area_movement=caused_by_area_movement,
            moved_area_counts_as_entry=policy["moved_area_counts_as_entry"],
            frequency=policy["frequency"],
            prior_trigger_turn_ids=prior_trigger_turn_ids,
        )
        matching_gate_ids = [
            gate.gate_id
            for gate in program.gates
            if gate.trigger.kind == "entry"
            and any(
                program.selector(selector_id).area is not None
                and program.selector(selector_id).area.area_id
                == selected_area_id
                for selector_id in gate.selector_ids
            )
        ]
        return {
            "kind": "compiled_area_entry",
            "effect_id": program.effect_id,
            "area_id": selected_area_id,
            "entry_policy": policy,
            **response,
            "gate_opportunity_ids": (
                matching_gate_ids if response["triggered"] else []
            ),
        }

    def resolve_area_response(
        self,
        *,
        state: ControlState,
        schedule: TimelineSchedule,
        effect: CompiledEffect | str,
        target_ids: Sequence[str],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        target_id: str,
        event_id: str,
        area_response_convention: str,
        membership: bool,
        effect_active: bool,
        post_movement_membership: bool | None = None,
        routes: Sequence[Mapping[str, Any]] | None = None,
        base_speeds_ft: Mapping[str, int] | None = None,
        mixed_speed_operation_order: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Resolve compiled area mechanics using base routes and active state.

        Callers supply geometry and base speeds, never effective control mechanics.
        """

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        target = _identifier(target_id, "target_id")
        if target not in schedule.target_ids:
            raise ControlEngineError(
                f"target_id {target!r} is not part of the supplied schedule"
            )
        if not isinstance(effect_active, bool):
            raise ControlEngineError("effect_active must be a boolean")
        if not isinstance(membership, bool):
            raise ControlEngineError("membership must be a boolean")
        if post_movement_membership is not None and not isinstance(
            post_movement_membership,
            bool,
        ):
            raise ControlEngineError(
                "post_movement_membership must be a boolean or null"
            )
        event = schedule.event(_identifier(event_id, "event_id"))
        active_target_exit = effect_active and event.kind == "exit"
        if effect_active:
            if active_target_exit:
                if area_response_convention != "shortest_route_v1":
                    raise ControlEngineError(
                        "An active typed exit requires shortest_route_v1"
                    )
                if (
                    event.target_id != target
                    or event.turn_owner != "target"
                    or event.actor_id != target
                ):
                    raise ControlEngineError(
                        "An active area exit requires the target's exact typed "
                        "exit event"
                    )
                if (
                    membership is not True
                    or post_movement_membership is not False
                ):
                    raise ControlEngineError(
                        "An active area exit requires membership before true "
                        "and explicit post_movement_membership false"
                    )
                if (
                    routes is not None
                    or base_speeds_ft is not None
                    or mixed_speed_operation_order is not None
                ):
                    raise ControlEngineError(
                        "An active area exit does not accept movement or route "
                        "inference"
                    )
            elif (
                event.kind != "target_movement_opportunity"
                or event.target_id != target
            ):
                raise ControlEngineError(
                    "An active area response requires the target's typed "
                    "movement opportunity"
                )
            elif post_movement_membership is not None:
                raise ControlEngineError(
                    "post_movement_membership is valid only for an active typed "
                    "exit"
                )
        elif (
            event.kind not in {"concentration_end", "exit"}
            or (
                event.target_id is not None
                and event.target_id != target
            )
        ):
            raise ControlEngineError(
                "An area-end response requires a typed concentration_end or "
                "matching target exit event"
            )
        elif post_movement_membership is not None:
            raise ControlEngineError(
                "post_movement_membership is valid only for an active typed exit"
            )
        program = self._canonical_effect(effect)
        validated_membership = self._validated_selector_membership_for_targets(
            program,
            selector_membership,
            target_ids,
            selector_context,
        )
        compiled_area_ids = tuple(dict.fromkeys(
            selector.area.area_id
            for selector in program.selectors
            if selector.area is not None
        ))
        if len(compiled_area_ids) != 1:
            raise ControlEngineError(
                "resolve_area_response requires exactly one compiled selector area"
            )
        area_id = compiled_area_ids[0]
        area_selector_ids = {
            selector.selector_id
            for selector in program.selectors
            if selector.area is not None and selector.area.area_id == area_id
        }
        if not any(
            target in validated_membership[selector_id]
            for selector_id in area_selector_ids
        ):
            raise ControlEngineError(
                f"Target {target!r} is not a member of the compiled area selector"
            )
        area_bindings = self._compiled_area_bindings(program)
        definitions = {
            component.component_id: component for component in program.components
        }
        active = [
            component
            for component in state.active_components(target)
            if component.effect_id == program.effect_id
            and component.component_id in definitions
        ]
        while_in_area_ids = sorted({
            component.component_id
            for component in active
            if area_id in area_bindings.get(component.component_id, ())
        })
        independent_ids = sorted({
            component.component_id
            for component in active
            if component.component_id not in while_in_area_ids
        })
        movement_authority: dict[str, Any] | None = None
        resolved_routes = routes
        effective_speeds: Mapping[str, int] | None = None
        derived_denied_modes: tuple[str, ...] = ()
        if (
            membership is True
            and effect_active is True
            and not active_target_exit
            and area_response_convention == "shortest_route_v1"
        ):
            if base_speeds_ft is None:
                raise ControlEngineError(
                    "shortest_route_v1 requires caller-supplied base_speeds_ft"
                )
            movement_authority = self._movement_state_authority(
                state=state,
                target_id=target,
                base_speeds_ft=base_speeds_ft,
                mixed_speed_operation_order=mixed_speed_operation_order,
            )
            resolved_routes, route_authority = self._state_adjusted_routes(
                state=state,
                target_id=target,
                routes=routes,
            )
            movement_authority = {**movement_authority, **route_authority}
            effective_speeds = movement_authority["effective_speeds_ft"]
            derived_denied_modes = tuple(movement_authority["denied_modes"])
        prone = any(
            component.magnitude.get("kind") == "condition"
            and component.magnitude.get("condition") == "prone"
            for component in state.active_components(target)
        )
        if active_target_exit:
            if area_response_convention not in AREA_RESPONSE_CONVENTIONS:
                raise ControlEngineError(
                    "area_response_convention is unsupported"
                )
            response = {
                "convention": area_response_convention,
                "target_id": target,
                "membership_before": True,
                "membership_after": False,
                "exited": True,
                "selected_route": None,
                "ended_component_ids": while_in_area_ids,
                "retained_component_ids": independent_ids,
                "events": [{
                    "kind": "exit",
                    "owner": "target",
                    "turn_anchor": "during_turn",
                    "reason": "post_movement_membership",
                }],
                "reason": "typed_target_exit",
            }
        else:
            response = area_response(
                area_response_convention,
                target_id=target,
                membership=membership,
                effect_active=effect_active,
                routes=resolved_routes,
                effective_speeds_ft=effective_speeds,
                denied_modes=derived_denied_modes,
                speed_zero=False,
                prone=prone,
                while_in_area_component_ids=while_in_area_ids,
                independent_component_ids=independent_ids,
            )
        ended_instances: list[dict[str, Any]] = []
        for component_id in response["ended_component_ids"]:
            removed = state.terminate(
                target_id=target,
                component_id=component_id,
                event_id=event.event_id,
                effect_id=program.effect_id,
                reason="area_exit" if response["reason"] != "effect_ended" else "area_end",
            )
            ended_instances.extend(
                {
                    "target_id": item.target_id,
                    "component_id": item.component_id,
                    "instance_id": item.instance_id,
                }
                for item in removed
            )
        prone_response = (
            response.get("selected_route") or {}
        ).get("prone_response")
        if isinstance(prone_response, Mapping) and prone_response.get("stood"):
            state.end_condition(
                target,
                "prone",
                event.event_id,
                "legal_stand_during_area_response",
            )
        record = {
            "kind": "area_response",
            "event_id": event.event_id,
            "effect_id": program.effect_id,
            "area_id": area_id,
            "area_bound_component_ids": while_in_area_ids,
            "movement_authority": (
                _json_safe(movement_authority)
                if movement_authority is not None else None
            ),
            **response,
            "ended_state_instances": ended_instances,
            "active_components_after": state.snapshot(target),
        }
        state.audit_ledger.append({"operation": "area_response", **record})
        return record

    def _canonical_effect(
        self,
        effect: CompiledEffect | str,
    ) -> CompiledEffect:
        if isinstance(effect, str):
            return self.program(effect)
        if not isinstance(effect, CompiledEffect):
            raise TypeError("effect must be CompiledEffect or an effect ID")
        canonical = self.program(effect.effect_id)
        if effect != canonical:
            raise ControlEngineError(
                "Compiled effect does not match the loaded authority projection"
            )
        return canonical

    def _compiled_area_bindings(
        self,
        program: CompiledEffect,
        *,
        enabled_component_ids: Iterable[str] | None = None,
    ) -> dict[str, tuple[str, ...]]:
        """Derive area-bound state from selector areas and component mechanics."""

        enabled = (
            {component.component_id for component in program.components}
            if enabled_component_ids is None
            else set(enabled_component_ids)
        )
        result: dict[str, tuple[str, ...]] = {}
        for component in program.components:
            if component.component_id not in enabled:
                continue
            selector_area_ids = tuple(dict.fromkeys(
                program.selector(selector_id).area.area_id
                for selector_id in component.target_selector_ids
                if program.selector(selector_id).area is not None
            ))
            duration = component.duration.to_dict()
            magnitude = component.magnitude.data.to_dict()
            bound_area_ids: tuple[str, ...] = ()
            if duration.get("kind") == "while_in_area":
                duration_area_id = _identifier(
                    duration.get("area_id"),
                    f"{component.component_id}.duration.area_id",
                )
                if duration_area_id not in selector_area_ids:
                    raise ControlEngineError(
                        f"Component {component.component_id!r} names an area that "
                        "is not supplied by its compiled selectors"
                    )
                bound_area_ids = (duration_area_id,)
            elif magnitude.get("scope") == "area":
                if not selector_area_ids:
                    raise ControlEngineError(
                        f"Area-scoped component {component.component_id!r} has no "
                        "compiled selector area"
                    )
                bound_area_ids = selector_area_ids
            if bound_area_ids:
                result[component.component_id] = bound_area_ids
        return result

    @staticmethod
    def _concentration_duration_anchor(
        schedule: TimelineSchedule,
        start: TimelineEvent,
    ) -> TimelineEvent:
        if start.kind != "activation" or start.turn_owner not in {
            "controller",
            "target",
        }:
            raise ControlEngineError(
                "Concentration startup has no canonical containing turn"
            )
        anchor_kind = (
            "controller_turn_start"
            if start.turn_owner == "controller"
            else "target_turn_start"
        )
        matches = [
            event
            for event in schedule.events
            if event.kind == anchor_kind
            and event.round == start.round
            and event.turn_id == start.turn_id
            and event.turn_owner == start.turn_owner
            and event.actor_id == start.actor_id
            and (
                start.turn_owner == "controller"
                or event.target_id == start.target_id
            )
            and event.sequence <= start.sequence
        ]
        if len(matches) != 1:
            raise ControlEngineError(
                "Concentration startup must resolve one canonical duration anchor"
            )
        return matches[0]

    @staticmethod
    def _concentration_duration_boundary(
        *,
        program: CompiledEffect,
        schedule: TimelineSchedule,
        start_event_id: str,
        maximum_duration: Mapping[str, Any],
    ) -> dict[str, Any]:
        start = schedule.event(start_event_id)
        duration_anchor = ControlEngine._concentration_duration_anchor(
            schedule,
            start,
        )
        value = maximum_duration.get("value")
        unit = maximum_duration.get("unit")
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ControlEngineError(
                f"{program.effect_id} has an invalid concentration maximum value"
            )
        round_multipliers = {"round": 1, "minute": 10, "hour": 600}
        if unit not in round_multipliers:
            raise ControlEngineError(
                f"{program.effect_id} has an unsupported concentration duration unit"
            )
        duration_rounds = value * round_multipliers[str(unit)]
        expiry_round = start.round + duration_rounds
        try:
            expiry_index = resolve_expiry_index(
                schedule,
                duration_anchor.event_id,
                {
                    "kind": "concentration",
                    "maximum_value": value,
                    "unit": unit,
                },
            )
        except TimelineError as error:
            raise ControlEngineError(
                f"Compiled concentration expiry cannot be represented: {error}"
            ) from error
        expiry_event = (
            schedule.events[expiry_index]
            if expiry_index is not None
            else None
        )
        return {
            "kind": "concentration_maximum_duration_boundary",
            "source": "compiled_effect",
            "start_event_id": start.event_id,
            "duration_anchor_event_id": duration_anchor.event_id,
            "start_round": start.round,
            "maximum_duration": dict(maximum_duration),
            "duration_rounds": duration_rounds,
            "computed_expiry_round": expiry_round,
            "horizon_rounds": schedule.rounds,
            "horizon_end_event_id": schedule.events[-1].event_id,
            "status": (
                "in_horizon" if expiry_event is not None else "beyond_horizon"
            ),
            "expiry_event_id": (
                expiry_event.event_id if expiry_event is not None else None
            ),
        }

    def _build_concentration_context(
        self,
        *,
        effect: CompiledEffect | str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        start_event_id: str,
        choices: Mapping[str, str] | None,
    ) -> _ConcentrationAuthorityContext:
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        program = self._canonical_effect(effect)
        invocation = _identifier(invocation_id, "invocation_id")
        source_actor = _identifier(source_actor_id, "source_actor_id")
        start_event = schedule.event(_identifier(start_event_id, "event_id"))
        if start_event.kind != "activation":
            raise ControlEngineError(
                "Concentration startup must bind to a typed activation event"
            )
        concentration = program.concentration.to_dict()
        if concentration.get("kind") != "required":
            raise ControlEngineError(
                f"Effect {program.effect_id!r} does not require concentration"
            )
        if (
            concentration.get("startup") != "on_activation"
            or concentration.get("occupancy") != "one_controller_slot"
            or concentration.get("replacement") != "new_effect_ends_existing"
        ):
            raise ControlEngineError(
                f"Effect {program.effect_id!r} has unsupported concentration policy"
            )
        maximum_duration = concentration.get("maximum_duration")
        if (
            not isinstance(maximum_duration, Mapping)
            or set(maximum_duration) != {"value", "unit"}
        ):
            raise ControlEngineError(
                f"Effect {program.effect_id!r} has invalid maximum_duration authority"
            )
        membership = self._validated_selector_membership(
            program,
            selector_membership,
            schedule,
            selector_context,
        )
        bindings = dict(program.bind_choices(choices))
        concentration_component_ids: list[str] = []
        for component in program.components:
            duration = component.duration.to_dict()
            if duration.get("kind") != "concentration":
                continue
            if (
                duration.get("maximum_value") != maximum_duration["value"]
                or duration.get("unit") != maximum_duration["unit"]
            ):
                raise ControlEngineError(
                    f"Component {component.component_id!r} concentration duration "
                    "does not match its compiled effect maximum"
                )
            concentration_component_ids.append(component.component_id)

        persistent_area_ids = tuple(dict.fromkeys(
            selector.area.area_id
            for selector in program.selectors
            if selector.area is not None and selector.area.persistent
        ))
        area_bindings = self._compiled_area_bindings(program)
        area_component_ids = tuple(
            component.component_id
            for component in program.components
            if component.component_id in area_bindings
            and any(
                area_id in persistent_area_ids
                for area_id in area_bindings[component.component_id]
            )
        )
        end_gates = tuple(
            gate for gate in program.gates
            if gate.trigger.kind == "concentration_end"
        )
        fall_component_ids: list[str] = []
        for gate in end_gates:
            if (
                gate.resolution_kind != "no_save"
                or len(gate.branches) != 1
                or gate.branches[0].outcome != "no_save"
            ):
                raise ControlEngineError(
                    f"Concentration-end gate {gate.gate_id!r} is not deterministic"
                )
            for component_id in gate.branches[0].applies:
                component = program.component(component_id)
                if component.magnitude.kind == "fall":
                    if not component.instantaneous:
                        raise ControlEngineError(
                            f"Fall component {component_id!r} must be instantaneous"
                        )
                    fall_component_ids.append(component_id)

        duration_boundary = self._concentration_duration_boundary(
            program=program,
            schedule=schedule,
            start_event_id=start_event.event_id,
            maximum_duration=maximum_duration,
        )
        return _ConcentrationAuthorityContext(
            program=program,
            schedule=schedule,
            selector_membership=MappingProxyType(dict(membership)),
            selector_context=selector_context,
            invocation_id=invocation,
            source_actor_id=source_actor,
            start_event_id=start_event.event_id,
            choices=MappingProxyType(dict(bindings)),
            concentration_component_ids=tuple(concentration_component_ids),
            area_ids=persistent_area_ids,
            area_component_ids=area_component_ids,
            maximum_duration=MappingProxyType(dict(maximum_duration)),
            concentration_end_gate_ids=tuple(
                gate.gate_id for gate in end_gates
            ),
            fall_component_ids=tuple(dict.fromkeys(fall_component_ids)),
            duration_boundary=MappingProxyType(duration_boundary),
        )

    @staticmethod
    def _concentration_authority_metadata(
        context: _ConcentrationAuthorityContext,
    ) -> dict[str, Any]:
        return {
            "source": "compiled_effect",
            "effect_id": context.program.effect_id,
            "selector_context": context.selector_context.to_dict(),
            "concentration_component_ids": list(
                context.concentration_component_ids
            ),
            "area_ids": list(context.area_ids),
            "area_component_ids": list(context.area_component_ids),
            "maximum_duration": dict(context.maximum_duration),
            "concentration_end_gate_ids": list(
                context.concentration_end_gate_ids
            ),
            "fall_component_ids": list(context.fall_component_ids),
            "duration_boundary": dict(context.duration_boundary),
        }

    def _active_concentration_context(
        self,
        *,
        tracker: ConcentrationTracker,
        effect: CompiledEffect | str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        choices: Mapping[str, str] | None,
    ) -> _ConcentrationAuthorityContext:
        context = self._concentration_contexts.get(tracker)
        if context is None:
            raise ControlEngineError(
                "The tracker has no engine-owned concentration authority context"
            )
        program = self._canonical_effect(effect)
        membership = self._validated_selector_membership(
            program,
            selector_membership,
            schedule,
            selector_context,
        )
        bindings = dict(program.bind_choices(choices))
        if (
            tracker.active_effect_id != context.program.effect_id
            or program.effect_id != context.program.effect_id
            or schedule != context.schedule
            or membership != dict(context.selector_membership)
            or selector_context != context.selector_context
            or _identifier(invocation_id, "invocation_id") != context.invocation_id
            or _identifier(source_actor_id, "source_actor_id")
            != context.source_actor_id
            or bindings != dict(context.choices)
        ):
            raise ControlEngineError(
                "Supplied concentration facts do not match the active compiled slot"
            )
        return context

    @staticmethod
    def _concentration_event_after_start(
        context: _ConcentrationAuthorityContext,
        event_id: str,
        label: str,
    ) -> TimelineEvent:
        event = context.schedule.event(_identifier(event_id, label))
        start = context.schedule.event(context.start_event_id)
        if event.sequence <= start.sequence:
            raise ControlEngineError(
                f"{label} must occur after concentration startup"
            )
        return event

    @staticmethod
    def _require_immediate_successor(
        earlier: TimelineEvent,
        later: TimelineEvent,
        label: str,
    ) -> None:
        if later.sequence != earlier.sequence + 1:
            raise ControlEngineError(
                f"{label} must be the immediate next timeline event"
            )

    @staticmethod
    def _recomputed_concentration_expiry_event_id(
        context: _ConcentrationAuthorityContext,
    ) -> str | None:
        expected_boundary = ControlEngine._concentration_duration_boundary(
            program=context.program,
            schedule=context.schedule,
            start_event_id=context.start_event_id,
            maximum_duration=context.maximum_duration,
        )
        if dict(context.duration_boundary) != expected_boundary:
            raise ControlEngineError(
                "Engine-owned concentration duration boundary is inconsistent"
            )
        return expected_boundary["expiry_event_id"]

    def _concentration_gate_schedule(
        self,
        *,
        context: _ConcentrationAuthorityContext,
        event_id: str,
        reason: str,
    ) -> TimelineSchedule:
        event = context.schedule.event(_identifier(event_id, "event_id"))
        if reason != "duration_expiry":
            if event.kind != "concentration_end":
                raise ControlEngineError(
                    "Concentration termination must bind to a typed "
                    "concentration_end event"
                )
            return context.schedule
        expected = self._recomputed_concentration_expiry_event_id(context)
        if expected is None or event.event_id != expected:
            raise ControlEngineError(
                "duration_expiry event does not match the compiled boundary"
            )
        if event.kind == "concentration_end":
            return context.schedule
        gate_event = replace(event, kind="concentration_end")
        return replace(
            context.schedule,
            events=tuple(
                gate_event if row.event_id == event.event_id else row
                for row in context.schedule.events
            ),
        )

    def _concentration_end_plan(
        self,
        *,
        state: ControlState,
        context: _ConcentrationAuthorityContext,
        event_id: str,
        reason: str,
    ) -> tuple[tuple[str, str, str], ...]:
        gate_schedule = self._concentration_gate_schedule(
            context=context,
            event_id=event_id,
            reason=reason,
        )
        event = gate_schedule.event(_identifier(event_id, "event_id"))
        plans: list[tuple[str, str, str]] = []
        planned_targets: set[str] = set()
        for gate_id in context.concentration_end_gate_ids:
            gate = context.program.gate(gate_id)
            branch = gate.branches[0]
            target_ids = [
                target_id
                for target_id in context.schedule.target_ids
                if any(
                    target_id in context.selector_membership[selector_id]
                    for selector_id in gate.selector_ids
                )
            ]
            for target_id in target_ids:
                active_ids = {
                    component.component_id
                    for component in state.active_components(target_id)
                    if component.effect_id == context.program.effect_id
                }
                if not set(gate.requires_active_component_ids).issubset(active_ids):
                    continue
                if target_id in planned_targets:
                    raise ControlEngineError(
                        "Multiple concentration-end gates would resolve for one "
                        "target; no outcome may be invented"
                    )
                if event.target_id is not None and event.target_id != target_id:
                    raise ControlEngineError(
                        "The concentration_end event target does not cover every "
                        "active compiled end gate"
                    )
                if not typed_event_matches(
                    event,
                    gate.trigger.data.to_dict(),
                    target_id=target_id,
                    triggering_turn_id=event.turn_id,
                ):
                    raise ControlEngineError(
                        f"Event {event.event_id!r} does not match {gate.gate_id!r}"
                    )
                self._gate_reachability(
                    state=state,
                    program=context.program,
                    gate_id=gate.gate_id,
                    target_id=target_id,
                    invocation_id=context.invocation_id,
                    event_id=event.event_id,
                    schedule=gate_schedule,
                )
                planned_targets.add(target_id)
                plans.append((gate.gate_id, target_id, branch.outcome))
        return tuple(plans)

    def _apply_concentration_end_record(
        self,
        *,
        state: ControlState,
        record: Mapping[str, Any],
        context: _ConcentrationAuthorityContext,
        plans: Sequence[tuple[str, str, str]],
    ) -> dict[str, Any]:
        """Apply one tracker record using only engine-owned authority metadata."""

        if not isinstance(record, Mapping) or record.get("kind") != "concentration_end":
            raise ControlEngineError("record must be a concentration_end record")
        result = dict(_json_safe(record))
        event = _identifier(result.get("event_id"), "record.event_id")
        gate_schedule = self._concentration_gate_schedule(
            context=context,
            event_id=event,
            reason=_identifier(result.get("reason"), "record.reason"),
        )
        if not result.get("changed"):
            raise ControlEngineError(
                "An active compiled concentration context produced an unchanged end"
            )
        if result.get("effect_id") != context.program.effect_id:
            raise ControlEngineError(
                "concentration_end effect_id does not match compiled authority"
            )
        expected_fields = {
            "ended_component_ids": list(context.concentration_component_ids),
            "ended_area_ids": list(context.area_ids),
            "fall_transitions": [],
        }
        for field_name, expected in expected_fields.items():
            if result.get(field_name) != expected:
                raise ControlEngineError(
                    f"Tracker {field_name} does not match engine-derived authority"
                )
        if result.get("execute_concentration_end_gates") is not True:
            raise ControlEngineError(
                "Tracker must request compiled concentration-end gate execution"
            )

        active_before = {
            component.instance_id: component
            for component in state.active_components()
            if component.effect_id == context.program.effect_id
        }
        gate_transitions: list[dict[str, Any]] = []
        for gate_id, target_id, outcome in plans:
            transition = self.apply_resolved_branch(
                state=state,
                effect=context.program,
                gate_id=gate_id,
                outcome=outcome,
                target_id=target_id,
                source_actor_id=context.source_actor_id,
                event_id=event,
                invocation_id=context.invocation_id,
                schedule=gate_schedule,
                selector_membership=context.selector_membership,
                selector_context=context.selector_context,
                choices=context.choices,
            )
            if transition.get("operation") != "branch_transition":
                raise ControlEngineError(
                    f"Compiled concentration-end gate {gate_id!r} was suppressed"
                )
            gate_transitions.append(transition)

        cleanup_ids = set(context.concentration_component_ids) | set(
            context.area_component_ids
        )
        for component in tuple(state.active_components()):
            if (
                component.effect_id == context.program.effect_id
                and component.component_id in cleanup_ids
            ):
                state.terminate(
                    target_id=component.target_id,
                    component_id=component.component_id,
                    event_id=event,
                    effect_id=context.program.effect_id,
                    reason="concentration_end",
                )
        remaining_instance_ids = {
            component.instance_id
            for component in state.active_components()
            if component.effect_id == context.program.effect_id
        }
        ended_instances = [
            {
                "target_id": component.target_id,
                "component_id": component.component_id,
                "instance_id": component.instance_id,
            }
            for instance_id, component in sorted(active_before.items())
            if instance_id not in remaining_instance_ids
        ]
        fall_transitions = [
            {
                "target_id": transition["target_id"],
                "kind": "fall_transition",
                "origin": contribution.get("context", {}).get(
                    "origin",
                    "current_position",
                ),
                "damage": None,
                "altitude_ft": None,
                "reason": "concentration_end",
                "source_component_ids": contribution["source_component_ids"],
            }
            for transition in gate_transitions
            for contribution in transition.get("instantaneous_contributions", ())
            if contribution.get("primitive_id") == "fall_transition"
        ]
        result.update({
            "ended_component_ids": list(context.concentration_component_ids),
            "ended_area_ids": list(context.area_ids),
            "fall_transitions": fall_transitions,
            "authority_metadata": self._concentration_authority_metadata(context),
            "concentration_end_gate_transitions": gate_transitions,
            "ended_state_instances": ended_instances,
            "active_components_after": state.snapshot(),
        })
        return self._audited_lifecycle_result(
            state,
            "concentration_end",
            result,
        )

    @staticmethod
    def _audited_lifecycle_result(
        state: ControlState,
        operation: str,
        row: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append and return independent deep JSON copies of one lifecycle."""

        serialized = _json_safe(row)
        if not isinstance(serialized, Mapping):
            raise ControlEngineError("Lifecycle result must be an object")
        audit = _json_safe({"operation": operation, **dict(serialized)})
        returned = _json_safe(serialized)
        if not isinstance(audit, Mapping) or not isinstance(returned, Mapping):
            raise ControlEngineError("Lifecycle serialization must be an object")
        state.audit_ledger.append(dict(audit))
        return dict(returned)

    def start_concentration(
        self,
        *,
        state: ControlState,
        tracker: ConcentrationTracker,
        effect: CompiledEffect | str,
        event_id: str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        startup_blood_tax: int = 0,
        replacement_end_event_id: str | None = None,
        choices: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Start one compiled slot, atomically ending any prior compiled slot."""

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(tracker, ConcentrationTracker):
            raise TypeError("tracker must be ConcentrationTracker")
        if (
            isinstance(startup_blood_tax, bool)
            or not isinstance(startup_blood_tax, int)
            or startup_blood_tax < 0
        ):
            raise ControlEngineError(
                "startup_blood_tax must be a non-negative integer"
            )
        new_context = self._build_concentration_context(
            effect=effect,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=source_actor_id,
            start_event_id=event_id,
            choices=choices,
        )
        first_record_index = len(tracker.records)
        applied_transitions: list[dict[str, Any]] = []
        if tracker.active_effect_id is not None:
            old_context = self._concentration_contexts.get(tracker)
            if (
                old_context is None
                or tracker.active_effect_id != old_context.program.effect_id
            ):
                raise ControlEngineError(
                    "Cannot replace concentration without the prior compiled context"
                )
            if replacement_end_event_id is None:
                raise ControlEngineError(
                    "replacement_end_event_id is required for an active slot"
                )
            if new_context.schedule != old_context.schedule:
                raise ControlEngineError(
                    "Concentration replacement must use the active canonical schedule"
                )
            replacement_end_event = self._concentration_event_after_start(
                old_context,
                replacement_end_event_id,
                "replacement_end_event_id",
            )
            replacement_start_event = new_context.schedule.event(
                new_context.start_event_id
            )
            self._require_immediate_successor(
                replacement_end_event,
                replacement_start_event,
                "Concentration replacement activation",
            )
            plans = self._concentration_end_plan(
                state=state,
                context=old_context,
                event_id=replacement_end_event_id,
                reason="new_concentration_replacement",
            )
            end_record = tracker.end(
                reason="new_concentration_replacement",
                event_id=replacement_end_event_id,
            )
            applied_transitions.append(self._apply_concentration_end_record(
                state=state,
                record=end_record,
                context=old_context,
                plans=plans,
            ))
            del self._concentration_contexts[tracker]
        elif replacement_end_event_id is not None:
            raise ControlEngineError(
                "replacement_end_event_id is invalid without an active slot"
            )

        start_record = tracker.start(
            new_context.program.effect_id,
            event_id=event_id,
            startup_blood_tax=startup_blood_tax,
            concentration_component_ids=new_context.concentration_component_ids,
            area_ids=new_context.area_ids,
            fall_target_ids=(),
            maximum_duration=new_context.maximum_duration,
        )
        self._concentration_contexts[tracker] = new_context
        enriched_start = {
            **start_record,
            "authority_metadata": self._concentration_authority_metadata(
                new_context
            ),
        }
        records = [
            dict(_json_safe(record))
            for record in tracker.records[first_record_index:]
        ]
        lifecycle = {
            "kind": "concentration_start_lifecycle",
            "start_record": enriched_start,
            "tracker_records": records,
            "applied_end_transitions": applied_transitions,
            "active_effect_id": tracker.active_effect_id,
            "active_components_after": state.snapshot(),
        }
        return self._audited_lifecycle_result(
            state,
            "concentration_start_lifecycle",
            lifecycle,
        )

    def check_concentration(
        self,
        *,
        state: ControlState,
        tracker: ConcentrationTracker,
        effect: CompiledEffect | str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        amount: int | float,
        source: str,
        event_id: str,
        outcome: str,
        concentration_end_event_id: str | None = None,
        success_probability: Any | None = None,
        roll_kernel: Sequence[Mapping[str, Any]] | None = None,
        choices: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Resolve a check and apply a deterministic compiled end on failure."""

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(tracker, ConcentrationTracker):
            raise TypeError("tracker must be ConcentrationTracker")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount < 0
        ):
            raise ControlEngineError(
                "amount must be a non-negative finite number"
            )
        if isinstance(tracker.save_bonus, bool) or not isinstance(
            tracker.save_bonus,
            int,
        ):
            raise ControlEngineError("tracker save_bonus must be an integer")
        context = self._active_concentration_context(
            tracker=tracker,
            effect=effect,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=source_actor_id,
            choices=choices,
        )
        cause_event = self._concentration_event_after_start(
            context,
            event_id,
            "concentration check event_id",
        )
        if cause_event.kind != "damage_context":
            raise ControlEngineError(
                "A later concentration check requires a typed damage_context event"
            )
        plans: tuple[tuple[str, str, str], ...] = ()
        resolved_end_event_id: str | None = None
        if outcome == "failure":
            if concentration_end_event_id is None:
                raise ControlEngineError(
                    "concentration_end_event_id is required on check failure"
                )
            resolved_end_event_id = _identifier(
                concentration_end_event_id,
                "concentration_end_event_id",
            )
            resolved_end_event = self._concentration_event_after_start(
                context,
                resolved_end_event_id,
                "concentration_end_event_id",
            )
            self._require_immediate_successor(
                cause_event,
                resolved_end_event,
                "concentration_end_event_id",
            )
            plans = self._concentration_end_plan(
                state=state,
                context=context,
                event_id=resolved_end_event_id,
                reason="failed_concentration_save",
            )
        elif outcome == "success":
            if concentration_end_event_id is not None:
                raise ControlEngineError(
                    "concentration_end_event_id is invalid on check success"
                )
        else:
            raise ControlEngineError("outcome must be success or failure")
        first_record_index = len(tracker.records)
        check_record = tracker.check(
            amount=amount,
            source=source,
            event_id=cause_event.event_id,
            outcome=outcome,
            success_probability=success_probability,
            roll_kernel=roll_kernel,
        )
        if outcome == "failure":
            generated = tracker.records[first_record_index:]
            if (
                len(generated) != 2
                or generated[0].get("kind") != "concentration_check"
                or generated[1].get("kind") != "concentration_end"
                or generated[1].get("event_id") != cause_event.event_id
            ):
                raise ControlEngineError(
                    "Tracker did not atomically emit the failed-check lifecycle"
                )
            generated[1]["event_id"] = resolved_end_event_id
        applied_transitions: list[dict[str, Any]] = []
        for record in tracker.records[first_record_index:]:
            if record.get("kind") == "concentration_end":
                applied_transitions.append(self._apply_concentration_end_record(
                    state=state,
                    record=record,
                    context=context,
                    plans=plans,
                ))
        if tracker.active_effect_id is None:
            del self._concentration_contexts[tracker]
        records = [
            dict(_json_safe(record))
            for record in tracker.records[first_record_index:]
        ]
        lifecycle = {
            "kind": "concentration_check_lifecycle",
            "check_record": check_record,
            "tracker_records": records,
            "applied_end_transitions": applied_transitions,
            "active_effect_id": tracker.active_effect_id,
            "active_components_after": state.snapshot(),
        }
        return self._audited_lifecycle_result(
            state,
            "concentration_check_lifecycle",
            lifecycle,
        )

    def end_concentration(
        self,
        *,
        state: ControlState,
        tracker: ConcentrationTracker,
        effect: CompiledEffect | str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        reason: str,
        event_id: str,
        choices: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """End one active compiled slot and execute its deterministic end gates."""

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(tracker, ConcentrationTracker):
            raise TypeError("tracker must be ConcentrationTracker")
        context = self._active_concentration_context(
            tracker=tracker,
            effect=effect,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=source_actor_id,
            choices=choices,
        )
        end_event = self._concentration_event_after_start(
            context,
            event_id,
            "concentration end event_id",
        )
        if reason == "duration_expiry":
            expiry_event_id = self._recomputed_concentration_expiry_event_id(
                context
            )
            if expiry_event_id is None:
                raise ControlEngineError(
                    "Compiled concentration expiry is beyond the maintained "
                    "timeline horizon; an early or late manual expiry is invalid"
                )
            if end_event.event_id != expiry_event_id:
                raise ControlEngineError(
                    "duration_expiry event does not match the compiled boundary"
                )
        plans = self._concentration_end_plan(
            state=state,
            context=context,
            event_id=end_event.event_id,
            reason=reason,
        )
        record = tracker.end(reason=reason, event_id=end_event.event_id)
        result = self._apply_concentration_end_record(
            state=state,
            record=record,
            context=context,
            plans=plans,
        )
        del self._concentration_contexts[tracker]
        return result
    def reconcile_concentration_duration(
        self,
        *,
        state: ControlState,
        tracker: ConcentrationTracker,
        effect: CompiledEffect | str,
        schedule: TimelineSchedule,
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        invocation_id: str,
        source_actor_id: str,
        event_id: str,
        choices: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """End concentration only at its mechanically derived duration boundary."""

        context = self._active_concentration_context(
            tracker=tracker,
            effect=effect,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=source_actor_id,
            choices=choices,
        )
        current = self._concentration_event_after_start(
            context,
            event_id,
            "duration reconciliation event_id",
        )
        expiry_event_id = self._recomputed_concentration_expiry_event_id(
            context
        )
        if expiry_event_id is None:
            lifecycle = {
                "kind": "concentration_duration_reconciliation",
                "event_id": current.event_id,
                "status": "beyond_horizon",
                "expected_expiry_event_id": None,
                "ended": False,
                "active_effect_id": tracker.active_effect_id,
                "active_components_after": state.snapshot(),
            }
            return self._audited_lifecycle_result(
                state,
                "concentration_duration_reconciliation",
                lifecycle,
            )
        expiry = schedule.event(expiry_event_id)
        if current.sequence < expiry.sequence:
            lifecycle = {
                "kind": "concentration_duration_reconciliation",
                "event_id": current.event_id,
                "status": "before_expiry",
                "expected_expiry_event_id": expiry.event_id,
                "ended": False,
                "active_effect_id": tracker.active_effect_id,
                "active_components_after": state.snapshot(),
            }
            return self._audited_lifecycle_result(
                state,
                "concentration_duration_reconciliation",
                lifecycle,
            )
        if current.event_id != expiry.event_id:
            raise ControlEngineError(
                "Concentration duration reconciliation missed the exact "
                "compiled boundary"
            )
        return self.end_concentration(
            state=state,
            tracker=tracker,
            effect=context.program,
            schedule=schedule,
            selector_membership=context.selector_membership,
            selector_context=context.selector_context,
            invocation_id=context.invocation_id,
            source_actor_id=context.source_actor_id,
            reason="duration_expiry",
            event_id=expiry.event_id,
            choices=context.choices,
        )

    def version_provenance(
        self,
        *,
        initiative_convention: str,
        area_response_convention: str,
        displacement_function_id: str,
    ) -> VersionProvenance:
        try:
            schedule = self.config.initiative_schedules[initiative_convention]
        except KeyError as error:
            raise ControlEngineError(
                f"Unknown initiative convention: {initiative_convention!r}"
            ) from error
        try:
            area = self.config.area_response_conventions[area_response_convention]
        except KeyError as error:
            raise ControlEngineError(
                f"Unknown area-response convention: {area_response_convention!r}"
            ) from error
        try:
            displacement = self.config.displacement_functions[
                displacement_function_id
            ]
        except KeyError as error:
            raise ControlEngineError(
                f"Unknown displacement function: {displacement_function_id!r}"
            ) from error
        return VersionProvenance(
            ENGINE_VERSION,
            self.authority.projection_version,
            self.authority.authority_sha256,
            self.target_supplement_digest,
            self.catalog.catalog_version,
            self.catalog.digest,
            self.catalog.primitive_contract_version,
            NORMALIZATION_RULES_VERSION,
            TIMELINE_ENGINE_VERSION,
            self.config.config_version,
            self.config.digest,
            initiative_convention,
            schedule.version,
            area_response_convention,
            area.version,
            displacement_function_id,
            displacement.version,
        )

    def schedule(
        self,
        initiative_convention: str,
        target_ids: Sequence[str],
        *,
        controller_events_by_round: (
            Mapping[int | str, Sequence[Mapping[str, Any]]] | None
        ) = None,
        target_events_by_round: (
            Mapping[
                str,
                Mapping[int | str, Sequence[Mapping[str, Any]]],
            ]
            | None
        ) = None,
        target_attack_counts: Mapping[str, Any],
        initial_reaction_availability: Mapping[str, bool] | None = None,
    ) -> TimelineSchedule:
        if initiative_convention not in self.config.initiative_schedules:
            raise ControlEngineError(
                f"Unknown initiative convention: {initiative_convention!r}"
            )
        return build_schedule(
            initiative_convention,
            target_ids,
            controller_events_by_round=controller_events_by_round,
            target_events_by_round=target_events_by_round,
            target_attack_counts=target_attack_counts,
            initial_reaction_availability=initial_reaction_availability,
            rounds=self.config.horizon_rounds,
        )

    def normalize_scheduled_window(
        self,
        *,
        state: ControlState,
        schedule: TimelineSchedule,
        target_id: str,
        event_id: str,
        context: Mapping[str, Any] | None = None,
    ) -> NormalizationResult:
        """Normalize a typed window with schedule-owned reaction facts."""

        if not isinstance(state, ControlState):
            raise TypeError("state must be ControlState")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        target = _identifier(target_id, "target_id")
        event = schedule.event(_identifier(event_id, "event_id"))
        if event.target_id != target or event.window_id is None:
            raise ControlEngineError(
                "Scheduled normalization requires a typed window for the target"
            )
        if context is None:
            normalized_context: dict[str, Any] = {}
        elif not isinstance(context, Mapping):
            raise TypeError("context must be a mapping")
        else:
            normalized_context = dict(context)

        reserved_reaction_facts = {
            "reaction_available",
            "reaction_interval_id",
        }
        forged = reserved_reaction_facts & set(normalized_context)
        if forged:
            raise ControlEngineError(
                "Reaction availability facts are derived from the schedule, not "
                f"caller context: {sorted(forged)!r}"
            )

        normalization_window_id = event.window_id
        if event.kind == "reaction_window":
            intervals = [
                interval
                for interval in schedule.reaction_intervals
                if interval.interval_id == event.reaction_interval_id
                and interval.target_id == target
            ]
            if len(intervals) != 1:
                raise ControlEngineError(
                    "Reaction event must resolve exactly one target interval"
                )
            interval = intervals[0]
            start_sequence = schedule.event(interval.start_event_id).sequence
            end_sequence = schedule.event(interval.end_before_event_id).sequence
            if not start_sequence <= event.sequence < end_sequence:
                raise ControlEngineError(
                    "Reaction event lies outside its declared interval"
                )
            if not isinstance(interval.initially_available, bool):
                raise ControlEngineError(
                    "Reaction interval availability is not explicit"
                )

            # This target-turn marker opens/resets an interval. Only caller-
            # scripted reaction events are actual normalization opportunities.
            if (
                not interval.horizon_entry_partial
                and event.event_id == interval.window_id
            ):
                return NormalizationResult((), ())

            normalization_window_id = interval.interval_id
            normalized_context.update({
                "reaction_available": interval.initially_available,
                "reaction_interval_id": interval.interval_id,
            })

        result = state.normalize_for_window(
            target_id=target,
            window_id=normalization_window_id,
            window_kind=event.kind,
            context=normalized_context,
            catalog=self.catalog,
        )
        if (
            event.kind != "reaction_window"
            or normalized_context["reaction_available"]
        ):
            return result

        retained = tuple(
            contribution
            for contribution in result.contributions
            if contribution.primitive_id != "reaction_denial"
        )
        denied = tuple(
            contribution
            for contribution in result.contributions
            if contribution.primitive_id == "reaction_denial"
        )
        if not denied:
            return result
        availability_suppressions = tuple(
            SuppressionRecord(
                target_id=target,
                event_or_window_id=normalization_window_id,
                primitive_id="reaction_denial",
                dominant_source_component_ids=(),
                suppressed_source_component_ids=(
                    contribution.source_component_ids
                ),
                reason="reaction_unavailable_at_interval_start",
                context={
                    "reaction_available": False,
                    "reaction_interval_id": normalization_window_id,
                },
            )
            for contribution in denied
        )
        return NormalizationResult(
            retained,
            (*result.suppressions, *availability_suppressions),
        )

    def reliability(
        self,
        effect: CompiledEffect | str,
        *,
        targets: Sequence[ReliabilityTarget],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        kernel: ProbabilityKernel | None = None,
        context: ProbabilityContext = ProbabilityContext(),
        choices: Mapping[str, str] | None = None,
        events: Sequence[ReliabilityEvent] = (),
        candidate_component_ids: Iterable[str] | None = None,
        include_initial: bool = True,
    ) -> ReliabilityResult:
        program = self._canonical_effect(effect)
        target_ids = tuple(target.target_id for target in targets)
        self._validated_selector_membership_for_targets(
            program,
            selector_membership,
            target_ids,
            selector_context,
        )
        mechanical_candidates = self.candidate_component_ids(program)
        if candidate_component_ids is None:
            candidates = mechanical_candidates
        else:
            if isinstance(candidate_component_ids, (str, bytes)):
                raise ControlEngineError(
                    "candidate_component_ids must be an iterable of component IDs"
                )
            try:
                explicit_candidates = tuple(
                    _identifier(value, f"candidate_component_ids[{index}]")
                    for index, value in enumerate(candidate_component_ids)
                )
            except TypeError as exc:
                raise ControlEngineError(
                    "candidate_component_ids must be an iterable of component IDs"
                ) from exc
            if (
                len(explicit_candidates) != len(set(explicit_candidates))
                or frozenset(explicit_candidates) != frozenset(mechanical_candidates)
            ):
                raise ControlEngineError(
                    "candidate_component_ids cannot reclassify mechanically derived "
                    "candidate or retained-only components"
                )
            candidates = mechanical_candidates
        return evaluate_reliability(
            program,
            targets=targets,
            selector_membership=selector_membership,
            selector_context=selector_context,
            kernel=kernel,
            context=context,
            choices=choices,
            events=events,
            candidate_component_ids=candidates,
            include_initial=include_initial,
        )

    def assemble_result(
        self,
        *,
        effect: CompiledEffect | str,
        reliability: ReliabilityResult,
        schedule: TimelineSchedule,
        area_response_convention: str,
        displacement_function_id: str,
        state: ControlState,
        normalization_results: Sequence[NormalizationResult] = (),
        event_state_transitions: Sequence[Mapping[str, Any]] = (),
        repeat_save_records: Sequence[Mapping[str, Any]] = (),
        area_records: Sequence[Mapping[str, Any]] = (),
        prone_records: Sequence[Mapping[str, Any]] = (),
        concentration_records: Sequence[Mapping[str, Any]] = (),
        displacement_records: Sequence[Mapping[str, Any]] = (),
    ) -> ControlEngineResult:
        program = self._canonical_effect(effect)
        if reliability.effect_id != program.effect_id:
            raise ControlEngineError(
                "Reliability result does not belong to the compiled program"
            )
        reliability_targets = tuple(reliability.target_ids)
        schedule_targets = tuple(schedule.target_ids)
        if (
            len(reliability_targets) != len(set(reliability_targets))
            or set(reliability_targets) != set(schedule_targets)
        ):
            raise ControlEngineError(
                "Reliability and timeline target IDs must contain the same identities"
            )
        target_rank = {
            target_id: index for index, target_id in enumerate(schedule_targets)
        }
        schedule_event_rank = {
            event.event_id: event.sequence for event in schedule.events
        }
        serialized = reliability_result_to_dict(reliability)

        serialized_audit_ledger = tuple(
            _json_safe(row) for row in state.audit_ledger
        )

        def require_exact_keys(
            row: Mapping[str, Any],
            expected: set[str],
            label: str,
        ) -> None:
            if set(row) != expected:
                raise ControlEngineError(
                    f"{label} has an invalid closed record shape; "
                    f"missing={sorted(expected - set(row))}, "
                    f"unknown={sorted(set(row) - expected)}"
                )

        def validate_identifier_list(value: Any, label: str) -> None:
            if (
                not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or len(value) != len(set(value))
            ):
                raise ControlEngineError(
                    f"{label} must be a unique identifier array"
                )

        def validate_active_snapshot(value: Any, label: str) -> None:
            expected = {
                "instance_id",
                "effect_id",
                "component_id",
                "target_id",
                "magnitude",
                "duration",
                "stacking",
                "source_actor_id",
                "applied_event_id",
                "expiry_event_id",
                "remaining_tokens",
            }
            if not isinstance(value, list):
                raise ControlEngineError(f"{label} must be an array")
            for index, item in enumerate(value):
                if not isinstance(item, Mapping):
                    raise ControlEngineError(
                        f"{label}[{index}] must be an object"
                    )
                require_exact_keys(item, expected, f"{label}[{index}]")
                for field_name in (
                    "instance_id",
                    "effect_id",
                    "component_id",
                    "target_id",
                    "source_actor_id",
                    "applied_event_id",
                ):
                    if (
                        not isinstance(item[field_name], str)
                        or not item[field_name]
                    ):
                        raise ControlEngineError(
                            f"{label}[{index}].{field_name} is invalid"
                        )
                if not all(
                    isinstance(item[field_name], Mapping)
                    for field_name in ("magnitude", "duration", "stacking")
                ):
                    raise ControlEngineError(
                        f"{label}[{index}] component authority is invalid"
                    )
                if item["expiry_event_id"] is not None and not isinstance(
                    item["expiry_event_id"],
                    str,
                ):
                    raise ControlEngineError(
                        f"{label}[{index}].expiry_event_id is invalid"
                    )
                remaining = item["remaining_tokens"]
                if (
                    remaining is not None
                    and (
                        isinstance(remaining, bool)
                        or not isinstance(remaining, int)
                        or remaining < 0
                    )
                ):
                    raise ControlEngineError(
                        f"{label}[{index}].remaining_tokens is invalid"
                    )

        def validate_exact_fraction(value: Any, label: str) -> None:
            if (
                not isinstance(value, Mapping)
                or set(value) != {"numerator", "denominator"}
                or isinstance(value["numerator"], bool)
                or not isinstance(value["numerator"], int)
                or isinstance(value["denominator"], bool)
                or not isinstance(value["denominator"], int)
                or value["denominator"] <= 0
            ):
                raise ControlEngineError(
                    f"{label} must be an exact fraction record"
                )

        def validate_movement_authority(
            value: Any,
            *,
            extended: bool,
            label: str,
        ) -> None:
            base_fields = {
                "source",
                "base_speeds_ft",
                "effective_speeds_ft",
                "speed_zero_modes",
                "denied_modes",
                "mixed_speed_operation_order",
                "source_component_ids",
            }
            extended_fields = {
                "active_area_movement_cost_multiplier",
                "terrain_source_component_ids",
                "route_multipliers",
            }
            expected = base_fields | (extended_fields if extended else set())
            if not isinstance(value, Mapping):
                raise ControlEngineError(f"{label} must be an object")
            require_exact_keys(value, expected, label)
            base = value["base_speeds_ft"]
            effective = value["effective_speeds_ft"]
            if (
                value["source"] != "active_control_state"
                or not isinstance(base, Mapping)
                or not isinstance(effective, Mapping)
                or set(base) != set(effective)
                or not set(base).issubset(MOVEMENT_MODES)
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, int)
                    or item < 0
                    for item in (*base.values(), *effective.values())
                )
            ):
                raise ControlEngineError(f"{label} speed authority is invalid")
            for field_name in (
                "speed_zero_modes",
                "denied_modes",
                "source_component_ids",
            ):
                validate_identifier_list(value[field_name], f"{label}.{field_name}")
            if (
                set(value["speed_zero_modes"]) - set(MOVEMENT_MODES)
                or set(value["denied_modes"]) - set(MOVEMENT_MODES)
            ):
                raise ControlEngineError(f"{label} movement modes are invalid")
            order = value["mixed_speed_operation_order"]
            if order not in (None, ["flat", "fraction"], ["fraction", "flat"]):
                raise ControlEngineError(f"{label} operation order is invalid")
            if not extended:
                return
            validate_exact_fraction(
                value["active_area_movement_cost_multiplier"],
                f"{label}.active_area_movement_cost_multiplier",
            )
            validate_identifier_list(
                value["terrain_source_component_ids"],
                f"{label}.terrain_source_component_ids",
            )
            multipliers = value["route_multipliers"]
            if not isinstance(multipliers, list):
                raise ControlEngineError(
                    f"{label}.route_multipliers must be an array"
                )
            for index, multiplier in enumerate(multipliers):
                if not isinstance(multiplier, Mapping):
                    raise ControlEngineError(
                        f"{label}.route_multipliers[{index}] is invalid"
                    )
                require_exact_keys(
                    multiplier,
                    {
                        "route_index",
                        "base_movement_cost_multiplier",
                        "effective_movement_cost_multiplier",
                    },
                    f"{label}.route_multipliers[{index}]",
                )
                route_index = multiplier["route_index"]
                if (
                    isinstance(route_index, bool)
                    or not isinstance(route_index, int)
                    or route_index < 0
                ):
                    raise ControlEngineError(
                        f"{label}.route_multipliers[{index}].route_index is invalid"
                    )
                validate_exact_fraction(
                    multiplier["base_movement_cost_multiplier"],
                    f"{label}.route_multipliers[{index}].base",
                )
                validate_exact_fraction(
                    multiplier["effective_movement_cost_multiplier"],
                    f"{label}.route_multipliers[{index}].effective",
                )

        def validate_prone_payload(
            row: Mapping[str, Any],
            label: str,
        ) -> None:
            if row.get("target_id") not in target_rank:
                raise ControlEngineError(
                    f"{label}.target_id is not part of the schedule"
                )
            if (
                not all(
                    isinstance(row.get(field_name), bool)
                    for field_name in ("was_prone", "stood", "prone_after")
                )
                or any(
                    isinstance(row.get(field_name), bool)
                    or not isinstance(row.get(field_name), int)
                    or row[field_name] < 0
                    for field_name in (
                        "standing_cost_ft",
                        "remaining_movement_ft",
                    )
                )
                or row.get("reason") not in {
                    "not_prone",
                    "speed_zero",
                    "movement_denied",
                    "first_legal_movement_opportunity",
                }
            ):
                raise ControlEngineError(f"{label} prone response is invalid")

        def validate_response_shape(
            row: Mapping[str, Any],
            *,
            kind: str,
            label: str,
        ) -> None:
            if kind == "prone_movement_response":
                require_exact_keys(
                    row,
                    {
                        "kind",
                        "event_id",
                        "movement_mode",
                        "movement_authority",
                        "target_id",
                        "was_prone",
                        "stood",
                        "standing_cost_ft",
                        "remaining_movement_ft",
                        "prone_after",
                        "reason",
                        "ended_component_ids",
                        "active_components_after",
                    },
                    label,
                )
                if row["movement_mode"] not in MOVEMENT_MODES:
                    raise ControlEngineError(
                        f"{label}.movement_mode is unsupported"
                    )
                validate_movement_authority(
                    row["movement_authority"],
                    extended=False,
                    label=f"{label}.movement_authority",
                )
                if row["movement_mode"] not in row[
                    "movement_authority"
                ]["effective_speeds_ft"]:
                    raise ControlEngineError(
                        f"{label}.movement_mode has no speed authority"
                    )
                validate_prone_payload(row, label)
            else:
                base_fields = {
                    "kind",
                    "event_id",
                    "effect_id",
                    "area_id",
                    "area_bound_component_ids",
                    "movement_authority",
                    "convention",
                    "target_id",
                    "membership_before",
                    "membership_after",
                    "exited",
                    "selected_route",
                    "ended_component_ids",
                    "retained_component_ids",
                    "events",
                    "reason",
                    "ended_state_instances",
                    "active_components_after",
                }
                reason = row.get("reason")
                optional_fields: set[str] = set()
                if reason == "shortest_legal_route":
                    optional_fields = {"prone_after"}
                elif reason == "movement_unavailable":
                    optional_fields = {"blocked_routes", "prone_after"}
                require_exact_keys(row, base_fields | optional_fields, label)
                if (
                    reason not in {
                        "not_in_area",
                        "effect_ended",
                        "typed_target_exit",
                        "fixed_occupancy",
                        "movement_unavailable",
                        "shortest_legal_route",
                    }
                    or row.get("convention") not in AREA_RESPONSE_CONVENTIONS
                    or row.get("convention") != area_response_convention
                    or not all(
                        isinstance(row.get(field_name), bool)
                        for field_name in (
                            "membership_before",
                            "membership_after",
                            "exited",
                        )
                    )
                ):
                    raise ControlEngineError(f"{label} area response is invalid")
                route_required = reason == "shortest_legal_route"
                authority_required = reason in {
                    "movement_unavailable",
                    "shortest_legal_route",
                }
                if authority_required:
                    validate_movement_authority(
                        row["movement_authority"],
                        extended=True,
                        label=f"{label}.movement_authority",
                    )
                elif row["movement_authority"] is not None:
                    raise ControlEngineError(
                        f"{label}.movement_authority must be null"
                    )
                if route_required:
                    route = row["selected_route"]
                    route_fields = {
                        "route_id",
                        "mode",
                        "environment",
                        "movement_cost_multiplier",
                        "movement_cost_multiplier_exact",
                        "distance_before_ft",
                        "distance_before_exact",
                        "progress_ft",
                        "progress_exact",
                        "remaining_distance_ft",
                        "remaining_distance_exact",
                        "prone_response",
                    }
                    if not isinstance(route, Mapping):
                        raise ControlEngineError(
                            f"{label}.selected_route must be an object"
                        )
                    require_exact_keys(
                        route,
                        route_fields,
                        f"{label}.selected_route",
                    )
                    if (
                        route["mode"] not in MOVEMENT_MODES
                        or not isinstance(route["route_id"], str)
                        or not route["route_id"]
                        or not isinstance(route["environment"], str)
                    ):
                        raise ControlEngineError(
                            f"{label}.selected_route identity is invalid"
                        )
                    for field_name in (
                        "movement_cost_multiplier_exact",
                        "distance_before_exact",
                        "progress_exact",
                        "remaining_distance_exact",
                    ):
                        validate_exact_fraction(
                            route[field_name],
                            f"{label}.selected_route.{field_name}",
                        )
                    prone_response = route["prone_response"]
                    if not isinstance(prone_response, Mapping):
                        raise ControlEngineError(
                            f"{label}.selected_route.prone_response is invalid"
                        )
                    require_exact_keys(
                        prone_response,
                        {
                            "target_id",
                            "was_prone",
                            "stood",
                            "standing_cost_ft",
                            "remaining_movement_ft",
                            "prone_after",
                            "reason",
                        },
                        f"{label}.selected_route.prone_response",
                    )
                    validate_prone_payload(
                        prone_response,
                        f"{label}.selected_route.prone_response",
                    )
                elif row["selected_route"] is not None:
                    raise ControlEngineError(
                        f"{label}.selected_route must be null"
                    )
                if "prone_after" in row and not isinstance(
                    row["prone_after"],
                    bool,
                ):
                    raise ControlEngineError(f"{label}.prone_after is invalid")
                if "blocked_routes" in row:
                    validate_identifier_list(
                        row["blocked_routes"],
                        f"{label}.blocked_routes",
                    )
                if not isinstance(row["events"], list) or any(
                    not isinstance(item, Mapping) for item in row["events"]
                ):
                    raise ControlEngineError(f"{label}.events is invalid")
                instances = row["ended_state_instances"]
                if not isinstance(instances, list):
                    raise ControlEngineError(
                        f"{label}.ended_state_instances is invalid"
                    )
                for instance_index, instance in enumerate(instances):
                    if not isinstance(instance, Mapping):
                        raise ControlEngineError(
                            f"{label}.ended_state_instances[{instance_index}] is invalid"
                        )
                    require_exact_keys(
                        instance,
                        {"target_id", "component_id", "instance_id"},
                        f"{label}.ended_state_instances[{instance_index}]",
                    )
                    if instance["target_id"] != row["target_id"]:
                        raise ControlEngineError(
                            f"{label}.ended_state_instances target is invalid"
                        )
                validate_identifier_list(
                    row["area_bound_component_ids"],
                    f"{label}.area_bound_component_ids",
                )
                validate_identifier_list(
                    row["retained_component_ids"],
                    f"{label}.retained_component_ids",
                )
            validate_identifier_list(
                row["ended_component_ids"],
                f"{label}.ended_component_ids",
            )
            validate_active_snapshot(
                row["active_components_after"],
                f"{label}.active_components_after",
            )

        def require_response_audit(
            row: Mapping[str, Any],
            *,
            operation: str,
            label: str,
        ) -> None:
            expected = {"operation": operation, **dict(row)}
            if expected not in serialized_audit_ledger:
                raise ControlEngineError(
                    f"{label} does not match the final state audit ledger"
                )
        def validated_response_records(
            rows: Sequence[Mapping[str, Any]],
            *,
            kind: str,
            label: str,
        ) -> list[dict[str, Any]]:
            validated: list[dict[str, Any]] = []
            identities: dict[tuple[str, ...], str] = {}
            compiled_area_ids = {
                selector.area.area_id
                for selector in program.selectors
                if selector.area is not None
            }
            for index, value in enumerate(rows):
                if not isinstance(value, Mapping):
                    raise TypeError(f"{label} must contain mappings")
                row = _json_safe(value)
                if not isinstance(row, Mapping) or row.get("kind") != kind:
                    raise ControlEngineError(
                        f"{label}[{index}] must be a {kind} record"
                    )
                validate_response_shape(
                    row,
                    kind=kind,
                    label=f"{label}[{index}]",
                )
                target_id = row.get("target_id")
                if target_id not in target_rank:
                    raise ControlEngineError(
                        f"{label}[{index}] target is not part of the schedule"
                    )
                try:
                    event = schedule.event(str(row.get("event_id")))
                except Exception as error:
                    raise ControlEngineError(
                        f"{label}[{index}] event is not in the schedule"
                    ) from error
                if kind == "prone_movement_response":
                    valid_event = (
                        event.kind == "target_movement_opportunity"
                        and event.target_id == target_id
                    )
                else:
                    if (
                        row.get("effect_id") != program.effect_id
                        or row.get("area_id") not in compiled_area_ids
                    ):
                        raise ControlEngineError(
                            f"{label}[{index}] does not belong to the compiled area"
                        )
                    if row.get("reason") == "typed_target_exit":
                        valid_event = (
                            event.kind == "exit"
                            and event.target_id == target_id
                            and event.turn_owner == "target"
                            and event.actor_id == target_id
                        )
                    elif row.get("reason") == "effect_ended":
                        valid_event = (
                            event.kind in {"concentration_end", "exit"}
                            and (
                                event.target_id is None
                                or event.target_id == target_id
                            )
                        )
                    else:
                        valid_event = (
                            event.kind == "target_movement_opportunity"
                            and event.target_id == target_id
                        )
                if not valid_event:
                    raise ControlEngineError(
                        f"{label}[{index}] is not bound to its typed target event"
                    )
                copied = dict(row)
                canonical = json.dumps(
                    copied,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                identity = (
                    (kind, str(target_id), event.event_id)
                    if kind == "prone_movement_response"
                    else (
                        kind,
                        str(row["effect_id"]),
                        str(row["area_id"]),
                        str(target_id),
                        event.event_id,
                    )
                )
                prior = identities.get(identity)
                if prior is not None and prior != canonical:
                    raise ControlEngineError(
                        f"{label}[{index}] conflicts with the same semantic identity"
                    )
                require_response_audit(
                    copied,
                    operation=(
                        "prone_movement_response"
                        if kind == "prone_movement_response"
                        else "area_response"
                    ),
                    label=f"{label}[{index}]",
                )
                if prior is None:
                    identities[identity] = canonical
                    validated.append(copied)
            validated.sort(
                key=lambda row: (
                    schedule_event_rank[str(row["event_id"])],
                    target_rank[str(row["target_id"])],
                    json.dumps(row, sort_keys=True),
                )
            )
            return validated

        validated_area_records = validated_response_records(
            area_records,
            kind="area_response",
            label="area_records",
        )
        validated_prone_records = validated_response_records(
            prone_records,
            kind="prone_movement_response",
            label="prone_records",
        )
        concentration_end_fields = {
            "kind",
            "event_id",
            "effect_id",
            "reason",
            "changed",
            "ended_component_ids",
            "ended_area_ids",
            "execute_concentration_end_gates",
            "fall_transitions",
        }
        concentration_end_reasons = {
            "new_concentration_replacement",
            "voluntary_end",
            "duration_expiry",
            "controller_incapacitated",
            "controller_death",
            "failed_concentration_save",
        }

        def validate_concentration_metadata(
            value: Any,
            label: str,
        ) -> tuple[CompiledEffect, Mapping[str, Any]]:
            expected = {
                "source",
                "effect_id",
                "selector_context",
                "concentration_component_ids",
                "area_ids",
                "area_component_ids",
                "maximum_duration",
                "concentration_end_gate_ids",
                "fall_component_ids",
                "duration_boundary",
            }
            if not isinstance(value, Mapping):
                raise ControlEngineError(f"{label} must be an object")
            require_exact_keys(value, expected, label)
            if value["source"] != "compiled_effect":
                raise ControlEngineError(f"{label}.source is invalid")
            try:
                authority_program = self.program(str(value["effect_id"]))
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.effect_id is not canonical"
                ) from error
            concentration = authority_program.concentration.to_dict()
            maximum_duration = concentration.get("maximum_duration")
            if (
                concentration.get("kind") != "required"
                or not isinstance(maximum_duration, Mapping)
                or value["maximum_duration"] != dict(maximum_duration)
                or not isinstance(value["selector_context"], Mapping)
            ):
                raise ControlEngineError(
                    f"{label} does not match canonical concentration authority"
                )
            for field_name in (
                "concentration_component_ids",
                "area_ids",
                "area_component_ids",
                "concentration_end_gate_ids",
                "fall_component_ids",
            ):
                validate_identifier_list(
                    value[field_name],
                    f"{label}.{field_name}",
                )
            expected_concentration_ids = [
                component.component_id
                for component in authority_program.components
                if component.duration.get("kind") == "concentration"
                and component.duration.get("maximum_value")
                == maximum_duration.get("value")
                and component.duration.get("unit")
                == maximum_duration.get("unit")
            ]
            if (
                value["concentration_component_ids"]
                != expected_concentration_ids
            ):
                raise ControlEngineError(
                    f"{label}.concentration_component_ids are invalid"
                )
            expected_area_ids = list(dict.fromkeys(
                selector.area.area_id
                for selector in authority_program.selectors
                if selector.area is not None and selector.area.persistent
            ))
            if value["area_ids"] != expected_area_ids:
                raise ControlEngineError(f"{label}.area_ids are invalid")
            area_bindings = self._compiled_area_bindings(authority_program)
            expected_area_component_ids = [
                component.component_id
                for component in authority_program.components
                if component.component_id in area_bindings
                and any(
                    area_id in expected_area_ids
                    for area_id in area_bindings[component.component_id]
                )
            ]
            if value["area_component_ids"] != expected_area_component_ids:
                raise ControlEngineError(
                    f"{label}.area_component_ids are invalid"
                )
            end_gates = [
                gate
                for gate in authority_program.gates
                if gate.trigger.kind == "concentration_end"
            ]
            if value["concentration_end_gate_ids"] != [
                gate.gate_id for gate in end_gates
            ]:
                raise ControlEngineError(
                    f"{label}.concentration_end_gate_ids are invalid"
                )
            expected_fall_ids = list(dict.fromkeys(
                component_id
                for gate in end_gates
                for branch in gate.branches
                for component_id in branch.applies
                if authority_program.component(component_id).magnitude.kind
                == "fall"
            ))
            if value["fall_component_ids"] != expected_fall_ids:
                raise ControlEngineError(
                    f"{label}.fall_component_ids are invalid"
                )
            boundary = value["duration_boundary"]
            if not isinstance(boundary, Mapping):
                raise ControlEngineError(
                    f"{label}.duration_boundary must be an object"
                )
            try:
                start_event_id = _identifier(
                    boundary.get("start_event_id"),
                    f"{label}.duration_boundary.start_event_id",
                )
                expected_boundary = self._concentration_duration_boundary(
                    program=authority_program,
                    schedule=schedule,
                    start_event_id=start_event_id,
                    maximum_duration=maximum_duration,
                )
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.duration_boundary is not canonical"
                ) from error
            if dict(boundary) != expected_boundary:
                raise ControlEngineError(
                    f"{label}.duration_boundary is inconsistent"
                )
            return authority_program, boundary

        def validate_raw_concentration_start(
            row: Mapping[str, Any],
            label: str,
        ) -> None:
            require_exact_keys(
                row,
                {
                    "kind",
                    "event_id",
                    "effect_id",
                    "startup_blood_tax",
                    "check_required",
                    "reason",
                },
                label,
            )
            try:
                event = schedule.event(str(row["event_id"]))
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.event_id is not in the schedule"
                ) from error
            tax = row["startup_blood_tax"]
            if (
                row["kind"] != "concentration_start"
                or event.kind != "activation"
                or row["effect_id"] != program.effect_id
                or isinstance(tax, bool)
                or not isinstance(tax, int)
                or tax < 0
                or row["check_required"] is not False
                or row["reason"]
                != ("startup_blood_tax_exemption" if tax else "activation")
            ):
                raise ControlEngineError(f"{label} is invalid")

        def validate_raw_concentration_check(
            row: Mapping[str, Any],
            label: str,
        ) -> None:
            require_exact_keys(
                row,
                {
                    "kind",
                    "event_id",
                    "effect_id",
                    "source",
                    "amount",
                    "dc",
                    "save_bonus",
                    "success_probability",
                    "failure_probability",
                    "kernel",
                    "outcome",
                },
                label,
            )
            try:
                event = schedule.event(str(row["event_id"]))
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.event_id is not in the schedule"
                ) from error
            if (
                row["kind"] != "concentration_check"
                or event.kind != "damage_context"
                or row["effect_id"] != program.effect_id
                or row["source"] not in {"damage", "later_blood_tax"}
                or row["outcome"] not in {"success", "failure"}
                or not isinstance(row["kernel"], Mapping)
            ):
                raise ControlEngineError(f"{label} is invalid")
            validate_exact_fraction(
                row["success_probability"],
                f"{label}.success_probability",
            )
            validate_exact_fraction(
                row["failure_probability"],
                f"{label}.failure_probability",
            )
            amount = row["amount"]
            save_bonus = row["save_bonus"]
            dc = row["dc"]
            if (
                isinstance(amount, bool)
                or not isinstance(amount, (int, float))
                or not math.isfinite(amount)
                or amount < 0
                or isinstance(save_bonus, bool)
                or not isinstance(save_bonus, int)
                or isinstance(dc, bool)
                or not isinstance(dc, int)
                or dc != min(30, max(10, math.floor(amount / 2)))
            ):
                raise ControlEngineError(
                    f"{label} check numerics are invalid"
                )
            success = Fraction(
                row["success_probability"]["numerator"],
                row["success_probability"]["denominator"],
            )
            failure = Fraction(
                row["failure_probability"]["numerator"],
                row["failure_probability"]["denominator"],
            )
            if not (0 <= success <= 1) or failure != 1 - success:
                raise ControlEngineError(
                    f"{label} probabilities are invalid"
                )
            kernel = row["kernel"]
            if kernel.get("kind") == "branch_probability":
                require_exact_keys(
                    kernel,
                    {"kind", "success_probability"},
                    f"{label}.kernel",
                )
                validate_exact_fraction(
                    kernel["success_probability"],
                    f"{label}.kernel.success_probability",
                )
                kernel_success = Fraction(
                    kernel["success_probability"]["numerator"],
                    kernel["success_probability"]["denominator"],
                )
                if kernel_success != success:
                    raise ControlEngineError(
                        f"{label} kernel is inconsistent"
                    )
            elif kernel.get("kind") == "exact_roll_kernel":
                require_exact_keys(
                    kernel,
                    {"kind", "rows"},
                    f"{label}.kernel",
                )
                kernel_rows = kernel["rows"]
                if not isinstance(kernel_rows, list) or not kernel_rows:
                    raise ControlEngineError(
                        f"{label} kernel rows are invalid"
                    )
                total = Fraction()
                computed_success = Fraction()
                seen_rolls: set[int] = set()
                for kernel_index, kernel_row in enumerate(kernel_rows):
                    if not isinstance(kernel_row, Mapping):
                        raise ControlEngineError(
                            f"{label} kernel row is invalid"
                        )
                    require_exact_keys(
                        kernel_row,
                        {"roll", "probability"},
                        f"{label}.kernel.rows[{kernel_index}]",
                    )
                    roll = kernel_row["roll"]
                    validate_exact_fraction(
                        kernel_row["probability"],
                        f"{label}.kernel.rows[{kernel_index}].probability",
                    )
                    probability = Fraction(
                        kernel_row["probability"]["numerator"],
                        kernel_row["probability"]["denominator"],
                    )
                    if (
                        isinstance(roll, bool)
                        or not isinstance(roll, int)
                        or roll < 1
                        or roll > 20
                        or roll in seen_rolls
                        or probability < 0
                    ):
                        raise ControlEngineError(
                            f"{label} kernel row is invalid"
                        )
                    seen_rolls.add(roll)
                    total += probability
                    if roll + save_bonus >= dc:
                        computed_success += probability
                if total != 1 or computed_success != success:
                    raise ControlEngineError(
                        f"{label} kernel is inconsistent"
                    )
            else:
                raise ControlEngineError(f"{label} kernel is invalid")

        def validate_raw_concentration_end(
            row: Mapping[str, Any],
            label: str,
            *,
            duration_boundary: Mapping[str, Any] | None = None,
        ) -> None:
            require_exact_keys(row, concentration_end_fields, label)
            try:
                event = schedule.event(str(row["event_id"]))
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.event_id is not in the schedule"
                ) from error
            reason = row["reason"]
            if (
                row["kind"] != "concentration_end"
                or reason not in concentration_end_reasons
                or row["changed"] is not True
                or row["execute_concentration_end_gates"] is not True
            ):
                raise ControlEngineError(f"{label} is invalid")
            try:
                self.program(str(row["effect_id"]))
            except Exception as error:
                raise ControlEngineError(
                    f"{label}.effect_id is not canonical"
                ) from error
            if reason == "duration_expiry":
                if (
                    duration_boundary is None
                    or event.event_id
                    != duration_boundary.get("expiry_event_id")
                ):
                    raise ControlEngineError(
                        f"{label} is not bound to its canonical duration boundary"
                    )
            elif event.kind != "concentration_end":
                raise ControlEngineError(
                    f"{label} is not bound to a typed concentration_end event"
                )
            for field_name in ("ended_component_ids", "ended_area_ids"):
                validate_identifier_list(
                    row[field_name],
                    f"{label}.{field_name}",
                )
            if (
                not isinstance(row["fall_transitions"], list)
                or any(
                    not isinstance(item, Mapping)
                    for item in row["fall_transitions"]
                )
            ):
                raise ControlEngineError(
                    f"{label}.fall_transitions is invalid"
                )

        def validate_enriched_concentration_end(
            row: Mapping[str, Any],
            label: str,
        ) -> None:
            require_exact_keys(
                row,
                concentration_end_fields
                | {
                    "authority_metadata",
                    "concentration_end_gate_transitions",
                    "ended_state_instances",
                    "active_components_after",
                },
                label,
            )
            authority_program, boundary = validate_concentration_metadata(
                row["authority_metadata"],
                f"{label}.authority_metadata",
            )
            raw = {
                field_name: row[field_name]
                for field_name in concentration_end_fields
            }
            validate_raw_concentration_end(
                raw,
                label,
                duration_boundary=boundary,
            )
            if (
                row["effect_id"] != authority_program.effect_id
                or row["ended_component_ids"]
                != row["authority_metadata"]["concentration_component_ids"]
                or row["ended_area_ids"]
                != row["authority_metadata"]["area_ids"]
                or not isinstance(
                    row["concentration_end_gate_transitions"],
                    list,
                )
                or any(
                    not isinstance(item, Mapping)
                    for item in row["concentration_end_gate_transitions"]
                )
            ):
                raise ControlEngineError(
                    f"{label} does not match its compiled authority"
                )
            instances = row["ended_state_instances"]
            if not isinstance(instances, list):
                raise ControlEngineError(
                    f"{label}.ended_state_instances is invalid"
                )
            for index, instance in enumerate(instances):
                if not isinstance(instance, Mapping):
                    raise ControlEngineError(
                        f"{label}.ended_state_instances[{index}] is invalid"
                    )
                require_exact_keys(
                    instance,
                    {"target_id", "component_id", "instance_id"},
                    f"{label}.ended_state_instances[{index}]",
                )
            validate_active_snapshot(
                row["active_components_after"],
                f"{label}.active_components_after",
            )
            expected_audit = {"operation": "concentration_end", **dict(row)}
            if expected_audit not in serialized_audit_ledger:
                raise ControlEngineError(
                    f"{label} does not match the final state audit ledger"
                )

        def validated_concentration_records(
            rows: Sequence[Mapping[str, Any]],
        ) -> list[dict[str, Any]]:
            validated: list[dict[str, Any]] = []
            identities: dict[tuple[str, str, str], str] = {}
            for index, value in enumerate(rows):
                label = f"concentration_records[{index}]"
                if not isinstance(value, Mapping):
                    raise TypeError(
                        "concentration_records must contain mappings"
                    )
                row = _json_safe(value)
                if not isinstance(row, Mapping):
                    raise ControlEngineError(f"{label} must be an object")
                kind = row.get("kind")
                effect_id: str
                event_id: str
                if kind == "concentration_start_lifecycle":
                    require_exact_keys(
                        row,
                        {
                            "kind",
                            "start_record",
                            "tracker_records",
                            "applied_end_transitions",
                            "active_effect_id",
                            "active_components_after",
                        },
                        label,
                    )
                    start_record = row["start_record"]
                    if not isinstance(start_record, Mapping):
                        raise ControlEngineError(
                            f"{label}.start_record is invalid"
                        )
                    require_exact_keys(
                        start_record,
                        {
                            "kind",
                            "event_id",
                            "effect_id",
                            "startup_blood_tax",
                            "check_required",
                            "reason",
                            "authority_metadata",
                        },
                        f"{label}.start_record",
                    )
                    authority_program, _boundary = validate_concentration_metadata(
                        start_record["authority_metadata"],
                        f"{label}.start_record.authority_metadata",
                    )
                    raw_start = {
                        field_name: start_record[field_name]
                        for field_name in start_record
                        if field_name != "authority_metadata"
                    }
                    validate_raw_concentration_start(
                        raw_start,
                        f"{label}.start_record",
                    )
                    if authority_program.effect_id != program.effect_id:
                        raise ControlEngineError(
                            f"{label} does not start the assembled program"
                        )
                    tracker_records = row["tracker_records"]
                    transitions = row["applied_end_transitions"]
                    if (
                        not isinstance(tracker_records, list)
                        or not tracker_records
                        or tracker_records[-1] != raw_start
                        or not isinstance(transitions, list)
                        or len(tracker_records) != len(transitions) + 1
                    ):
                        raise ControlEngineError(
                            f"{label} tracker lifecycle is invalid"
                        )
                    for record_index, transition in enumerate(transitions):
                        raw_end = tracker_records[record_index]
                        if (
                            not isinstance(raw_end, Mapping)
                            or not isinstance(transition, Mapping)
                        ):
                            raise ControlEngineError(
                                f"{label} replacement lifecycle is invalid"
                            )
                        validate_raw_concentration_end(
                            raw_end,
                            f"{label}.tracker_records[{record_index}]",
                        )
                        validate_enriched_concentration_end(
                            transition,
                            f"{label}.applied_end_transitions[{record_index}]",
                        )
                        if any(
                            transition[field_name] != raw_end[field_name]
                            for field_name in (
                                concentration_end_fields - {"fall_transitions"}
                            )
                        ):
                            raise ControlEngineError(
                                f"{label} replacement records disagree"
                            )
                    if row["active_effect_id"] != program.effect_id:
                        raise ControlEngineError(
                            f"{label}.active_effect_id is invalid"
                        )
                    validate_active_snapshot(
                        row["active_components_after"],
                        f"{label}.active_components_after",
                    )
                    effect_id = str(start_record["effect_id"])
                    event_id = str(start_record["event_id"])
                elif kind == "concentration_check_lifecycle":
                    require_exact_keys(
                        row,
                        {
                            "kind",
                            "check_record",
                            "tracker_records",
                            "applied_end_transitions",
                            "active_effect_id",
                            "active_components_after",
                        },
                        label,
                    )
                    check_record = row["check_record"]
                    if not isinstance(check_record, Mapping):
                        raise ControlEngineError(
                            f"{label}.check_record is invalid"
                        )
                    validate_raw_concentration_check(
                        check_record,
                        f"{label}.check_record",
                    )
                    tracker_records = row["tracker_records"]
                    transitions = row["applied_end_transitions"]
                    if (
                        not isinstance(tracker_records, list)
                        or not tracker_records
                        or tracker_records[0] != check_record
                        or not isinstance(transitions, list)
                    ):
                        raise ControlEngineError(
                            f"{label} tracker lifecycle is invalid"
                        )
                    failed = check_record["outcome"] == "failure"
                    if (
                        len(tracker_records) != (2 if failed else 1)
                        or len(transitions) != (1 if failed else 0)
                        or row["active_effect_id"]
                        != (None if failed else program.effect_id)
                    ):
                        raise ControlEngineError(
                            f"{label} outcome lifecycle is invalid"
                        )
                    if failed:
                        raw_end = tracker_records[1]
                        transition = transitions[0]
                        if (
                            not isinstance(raw_end, Mapping)
                            or not isinstance(transition, Mapping)
                        ):
                            raise ControlEngineError(
                                f"{label} failed lifecycle is invalid"
                            )
                        validate_raw_concentration_end(
                            raw_end,
                            f"{label}.tracker_records[1]",
                        )
                        validate_enriched_concentration_end(
                            transition,
                            f"{label}.applied_end_transitions[0]",
                        )
                        if any(
                            transition[field_name] != raw_end[field_name]
                            for field_name in (
                                concentration_end_fields - {"fall_transitions"}
                            )
                        ):
                            raise ControlEngineError(
                                f"{label} failure records disagree"
                            )
                    validate_active_snapshot(
                        row["active_components_after"],
                        f"{label}.active_components_after",
                    )
                    effect_id = str(check_record["effect_id"])
                    event_id = str(check_record["event_id"])
                elif kind == "concentration_duration_reconciliation":
                    require_exact_keys(
                        row,
                        {
                            "kind",
                            "event_id",
                            "status",
                            "expected_expiry_event_id",
                            "ended",
                            "active_effect_id",
                            "active_components_after",
                        },
                        label,
                    )
                    try:
                        current = schedule.event(str(row["event_id"]))
                    except Exception as error:
                        raise ControlEngineError(
                            f"{label}.event_id is not in the schedule"
                        ) from error
                    status = row["status"]
                    expected_expiry = row["expected_expiry_event_id"]
                    valid_timing = (
                        status == "beyond_horizon"
                        and expected_expiry is None
                    )
                    if status == "before_expiry":
                        try:
                            expiry = schedule.event(str(expected_expiry))
                        except Exception as error:
                            raise ControlEngineError(
                                f"{label}.expected_expiry_event_id is invalid"
                            ) from error
                        valid_timing = current.sequence < expiry.sequence
                    if (
                        not valid_timing
                        or row["ended"] is not False
                        or row["active_effect_id"] != program.effect_id
                    ):
                        raise ControlEngineError(f"{label} is invalid")
                    validate_active_snapshot(
                        row["active_components_after"],
                        f"{label}.active_components_after",
                    )
                    effect_id = program.effect_id
                    event_id = current.event_id
                elif kind == "concentration_end":
                    validate_enriched_concentration_end(row, label)
                    effect_id = str(row["effect_id"])
                    event_id = str(row["event_id"])
                else:
                    raise ControlEngineError(
                        f"{label} has an unsupported concentration record kind"
                    )
                expected_audit = {"operation": str(kind), **dict(row)}
                if expected_audit not in serialized_audit_ledger:
                    raise ControlEngineError(
                        f"{label} does not match the final state audit ledger"
                    )
                canonical = json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                identity = (str(kind), effect_id, event_id)
                prior = identities.get(identity)
                if prior is not None and prior != canonical:
                    raise ControlEngineError(
                        f"{label} conflicts with the same semantic identity"
                    )
                if prior is None:
                    identities[identity] = canonical
                    validated.append(dict(row))
            validated.sort(
                key=lambda row: (
                    schedule_event_rank[
                        str(
                            row.get("event_id")
                            or row.get("start_record", {}).get("event_id")
                            or row.get("check_record", {}).get("event_id")
                        )
                    ],
                    str(row["kind"]),
                    json.dumps(row, sort_keys=True),
                )
            )
            return validated

        validated_concentration_records = validated_concentration_records(
            concentration_records
        )
        def order_scoped_targets(
            rows: Sequence[Mapping[str, Any]],
        ) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            for row in rows:
                copied = dict(row)
                scoped = copied.get("target_ids")
                if scoped is not None:
                    unknown = set(scoped) - set(schedule_targets)
                    if unknown:
                        raise ControlEngineError(
                            f"Reliability scope contains unknown targets: {sorted(unknown)}"
                        )
                    copied["target_ids"] = sorted(
                        scoped,
                        key=target_rank.__getitem__,
                    )
                result.append(copied)
            result.sort(
                key=lambda row: (
                    schedule_event_rank.get(
                        str(row.get("event_id")),
                        len(schedule_event_rank),
                    ),
                    str(row.get("event_id", "")),
                    str(row.get("gate_id", "")),
                    tuple(
                        target_rank[target_id]
                        for target_id in row.get("target_ids", ())
                    ),
                    str(row.get("branch_id", "")),
                    str(row.get("outcome", "")),
                )
            )
            return result

        gate_probabilities = order_scoped_targets(
            serialized["gate_probabilities"]
        )
        branch_probabilities = order_scoped_targets(
            serialized["branch_probabilities"]
        )
        component_rank = {
            component.component_id: index
            for index, component in enumerate(program.components)
        }
        component_reliability = [
            dict(row) for row in serialized["component_reliability"]
        ]
        invalid_component_rows = [
            row
            for row in component_reliability
            if row.get("target_id") not in target_rank
            or row.get("component_id") not in component_rank
        ]
        if invalid_component_rows:
            raise ControlEngineError(
                "component_reliability contains an unknown target or component"
            )
        component_reliability.sort(
            key=lambda row: (
                component_rank.get(str(row["component_id"]), len(component_rank)),
                target_rank[str(row["target_id"])],
            )
        )

        def ordered_target_probabilities(
            rows: Sequence[Mapping[str, Any]],
            label: str,
        ) -> list[dict[str, Any]]:
            copied = [dict(row) for row in rows]
            target_ids = [str(row.get("target_id")) for row in copied]
            if len(target_ids) != len(set(target_ids)) or set(target_ids) != set(
                schedule_targets
            ):
                raise ControlEngineError(
                    f"{label} must cover every schedule target exactly once"
                )
            copied.sort(key=lambda row: target_rank[str(row["target_id"])])
            return copied

        any_candidate_by_target = ordered_target_probabilities(
            serialized["any_candidate_by_target"],
            "any_candidate_by_target",
        )
        any_component_by_target = ordered_target_probabilities(
            serialized["any_component_by_target"],
            "any_component_by_target",
        )

        by_family: dict[str, list[Mapping[str, Any]]] = {
            family: [] for family in DIAGNOSTIC_FAMILIES
        }
        seen_contributions: set[str] = set()

        def add_contribution(value: Mapping[str, Any], label: str) -> None:
            if not isinstance(value, Mapping):
                raise ControlEngineError(f"{label} must be an object")
            row = _json_safe(value)
            family = row.get("family")
            primitive_id = row.get("primitive_id")
            if family not in DIAGNOSTIC_FAMILIES:
                raise ControlEngineError(
                    f"{label}.family is unsupported: {family!r}"
                )
            if primitive_id not in PRIMITIVE_CONTRACT:
                raise ControlEngineError(
                    f"{label}.primitive_id is unsupported: {primitive_id!r}"
                )
            if row.get("target_id") not in target_rank:
                raise ControlEngineError(
                    f"{label}.target_id is not part of the schedule"
                )
            if not isinstance(row.get("event_or_window_id"), str) or not row[
                "event_or_window_id"
            ]:
                raise ControlEngineError(
                    f"{label}.event_or_window_id must be non-empty"
                )
            source_ids = row.get("source_component_ids")
            if (
                not isinstance(source_ids, list)
                or not source_ids
                or any(not isinstance(item, str) or not item for item in source_ids)
            ):
                raise ControlEngineError(
                    f"{label}.source_component_ids must be a non-empty string array"
                )
            canonical = json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if canonical in seen_contributions:
                return
            seen_contributions.add(canonical)
            by_family[str(family)].append(row)

        for result_index, result in enumerate(normalization_results):
            if not isinstance(result, NormalizationResult):
                raise TypeError(
                    "normalization_results must contain NormalizationResult values"
                )
            for contribution_index, contribution in enumerate(result.contributions):
                add_contribution(
                    contribution.to_dict(),
                    f"normalization_results[{result_index}].contributions"
                    f"[{contribution_index}]",
                )
        for transition_index, transition in enumerate(event_state_transitions):
            if not isinstance(transition, Mapping):
                raise TypeError("event_state_transitions must contain mappings")
            contributions = transition.get("instantaneous_contributions", ())
            if (
                not isinstance(contributions, Sequence)
                or isinstance(contributions, (str, bytes))
            ):
                raise ControlEngineError(
                    "instantaneous_contributions must be an array"
                )
            for contribution_index, contribution in enumerate(contributions):
                add_contribution(
                    contribution,
                    f"event_state_transitions[{transition_index}]"
                    f".instantaneous_contributions[{contribution_index}]",
                )

        displacement_epoch_records: list[Mapping[str, Any]] = []
        seen_displacement_records: set[str] = set()
        displacement_identities: dict[tuple[Any, ...], str] = {}
        for index, resolution in enumerate(displacement_records):
            if not isinstance(resolution, Mapping):
                raise TypeError("displacement_records must contain mappings")
            if "record" not in resolution:
                raise ControlEngineError(
                    "displacement_records must contain a record field"
                )
            record = _json_safe(resolution["record"])
            if not isinstance(record, Mapping):
                raise ControlEngineError(
                    f"displacement_records[{index}].record must be an object"
                )
            if record.get("kind") == "displacement_epoch_boundary":
                if set(resolution) != {"record"}:
                    raise ControlEngineError(
                        "Epoch boundary results contain only a record"
                    )
                expected = {
                    "kind",
                    "target_id",
                    "previous_epoch",
                    "new_epoch",
                    "reset",
                    "reason",
                    "event_id",
                    "source",
                    "movement_mode",
                    "movement_authority",
                }
                if set(record) != expected:
                    raise ControlEngineError(
                        "displacement epoch boundary has an invalid shape"
                    )
                target_id = record["target_id"]
                try:
                    boundary_event = schedule.event(str(record["event_id"]))
                except Exception as error:
                    raise ControlEngineError(
                        "displacement epoch boundary event is not in the schedule"
                    ) from error
                previous_epoch = record["previous_epoch"]
                new_epoch = record["new_epoch"]
                reset = record["reset"]
                movement_mode = record["movement_mode"]
                movement_authority = record["movement_authority"]
                expected_authority_fields = {
                    "source",
                    "base_speeds_ft",
                    "effective_speeds_ft",
                    "speed_zero_modes",
                    "denied_modes",
                    "mixed_speed_operation_order",
                    "source_component_ids",
                }
                if (
                    not isinstance(movement_mode, str)
                    or movement_mode not in MOVEMENT_MODES
                    or not isinstance(movement_authority, Mapping)
                    or set(movement_authority) != expected_authority_fields
                    or movement_authority["source"] != "active_control_state"
                ):
                    raise ControlEngineError(
                        "displacement epoch movement authority is invalid"
                    )
                base_speeds = movement_authority["base_speeds_ft"]
                effective_speeds = movement_authority["effective_speeds_ft"]
                speed_zero_modes = movement_authority["speed_zero_modes"]
                denied_modes = movement_authority["denied_modes"]
                source_component_ids = movement_authority[
                    "source_component_ids"
                ]
                operation_order_value = movement_authority[
                    "mixed_speed_operation_order"
                ]
                operation_order = (
                    tuple(operation_order_value)
                    if isinstance(operation_order_value, list)
                    else operation_order_value
                )
                valid_speed_maps = (
                    isinstance(base_speeds, Mapping)
                    and isinstance(effective_speeds, Mapping)
                    and set(base_speeds) == set(effective_speeds)
                    and set(base_speeds).issubset(MOVEMENT_MODES)
                    and movement_mode in effective_speeds
                    and all(
                        not isinstance(value, bool)
                        and isinstance(value, int)
                        and value >= 0
                        for value in (
                            *base_speeds.values(),
                            *effective_speeds.values(),
                        )
                    )
                )
                valid_speed_zero_modes = (
                    isinstance(speed_zero_modes, list)
                    and all(
                        isinstance(mode, str) for mode in speed_zero_modes
                    )
                    and len(speed_zero_modes) == len(set(speed_zero_modes))
                    and set(speed_zero_modes).issubset(MOVEMENT_MODES)
                )
                valid_denied_modes = (
                    isinstance(denied_modes, list)
                    and all(isinstance(mode, str) for mode in denied_modes)
                    and len(denied_modes) == len(set(denied_modes))
                    and set(denied_modes).issubset(MOVEMENT_MODES)
                )
                valid_mode_lists = (
                    valid_speed_zero_modes and valid_denied_modes
                )
                valid_sources = (
                    isinstance(source_component_ids, list)
                    and all(
                        isinstance(source_id, str) and source_id
                        for source_id in source_component_ids
                    )
                    and len(source_component_ids)
                    == len(set(source_component_ids))
                )
                if (
                    not valid_speed_maps
                    or not valid_mode_lists
                    or not valid_sources
                    or operation_order not in (
                        None,
                        ("flat", "fraction"),
                        ("fraction", "flat"),
                    )
                ):
                    raise ControlEngineError(
                        "displacement epoch movement authority facts are invalid"
                    )
                selected_effective_speed = effective_speeds[movement_mode]
                derived_movement_denied = movement_mode in denied_modes
                derived_speed_zero = (
                    selected_effective_speed == 0
                    and not derived_movement_denied
                )
                if (
                    (derived_movement_denied and selected_effective_speed != 0)
                    or (
                        movement_mode in speed_zero_modes
                        and selected_effective_speed != 0
                    )
                ):
                    raise ControlEngineError(
                        "displacement epoch movement authority is inconsistent"
                    )
                if (
                    target_id not in target_rank
                    or boundary_event.kind != "target_movement_opportunity"
                    or boundary_event.target_id != target_id
                    or record["source"] != "typed_self_movement_opportunity"
                    or isinstance(previous_epoch, bool)
                    or not isinstance(previous_epoch, int)
                    or previous_epoch < 0
                    or isinstance(new_epoch, bool)
                    or not isinstance(new_epoch, int)
                    or not isinstance(reset, bool)
                ):
                    raise ControlEngineError(
                        "displacement epoch boundary is not a typed target event"
                    )
                if reset:
                    valid = (
                        new_epoch == previous_epoch + 1
                        and record["reason"] == "legal_self_movement_response"
                        and selected_effective_speed > 0
                        and not derived_movement_denied
                    )
                else:
                    reason = record["reason"]
                    valid = (
                        new_epoch == previous_epoch
                        and (
                            (reason == "speed_zero" and derived_speed_zero)
                            or (
                                reason == "movement_denied"
                                and derived_movement_denied
                            )
                            or (
                                reason == "no_legal_response"
                                and selected_effective_speed > 0
                                and not derived_movement_denied
                            )
                        )
                    )
                if not valid:
                    raise ControlEngineError(
                        "displacement epoch boundary transition is inconsistent"
                    )
                canonical_record = json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                if canonical_record not in seen_displacement_records:
                    seen_displacement_records.add(canonical_record)
                    displacement_epoch_records.append(record)
                continue
            if "contribution" not in resolution:
                raise ControlEngineError(
                    "Forced displacement results require a contribution field"
                )
            contribution = _json_safe(resolution["contribution"])
            if not isinstance(contribution, Mapping):
                raise ControlEngineError(
                    f"displacement_records[{index}] has an invalid result shape"
                )
            if (
                record.get("function_id") != displacement_function_id
                or contribution.get("primitive_id") != "forced_displacement"
                or contribution.get("family") != "denial"
                or contribution.get("active_source_effect_id") != program.effect_id
                or contribution.get("target_id") not in target_rank
                or contribution.get("event_or_window_id") != record.get("event_id")
                or not isinstance(contribution.get("context"), Mapping)
                or contribution["context"].get("displacement_function_id")
                != displacement_function_id
            ):
                raise ControlEngineError(
                    f"displacement_records[{index}] does not match the selected "
                    "program, targets, event, or displacement function"
                )
            source_ids = contribution.get("source_component_ids")
            if (
                not isinstance(source_ids, list)
                or len(source_ids) != 1
            ):
                raise ControlEngineError(
                    f"displacement_records[{index}] must identify one source component"
                )
            try:
                source_component = program.component(str(source_ids[0]))
            except Exception as error:
                raise ControlEngineError(
                    f"displacement_records[{index}] references an unknown component"
                ) from error
            if source_component.magnitude.kind != "forced_movement":
                raise ControlEngineError(
                    f"displacement_records[{index}] source is not forced movement"
                )
            canonical_contribution = json.dumps(
                contribution,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            identity = (
                contribution["target_id"],
                contribution["event_or_window_id"],
                tuple(source_ids),
                contribution["primitive_id"],
            )
            previous = displacement_identities.get(identity)
            if previous is not None and previous != canonical_contribution:
                raise ControlEngineError(
                    f"displacement_records[{index}] conflicts with a duplicate event identity"
                )
            displacement_identities[identity] = canonical_contribution
            add_contribution(
                contribution,
                f"displacement_records[{index}].contribution",
            )
            canonical_record = json.dumps(
                record,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if canonical_record not in seen_displacement_records:
                seen_displacement_records.add(canonical_record)
                displacement_epoch_records.append(record)

        for family in by_family:
            by_family[family].sort(
                key=lambda row: (
                    target_rank[str(row["target_id"])],
                    str(row["event_or_window_id"]),
                    str(row["primitive_id"]),
                    tuple(row["source_component_ids"]),
                    json.dumps(row.get("context", {}), sort_keys=True),
                )
            )
        refresh_replacement = [
            *state.refresh_records,
            *state.replacement_records,
        ]
        refresh_replacement.sort(
            key=lambda row: json.dumps(row, sort_keys=True)
        )
        suppression_records: list[dict[str, Any]] = []
        seen_suppression_records: set[str] = set()

        def add_suppression_record(row: Mapping[str, Any]) -> None:
            serialized_row = dict(_json_safe(row))
            canonical = json.dumps(
                serialized_row,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if canonical not in seen_suppression_records:
                seen_suppression_records.add(canonical)
                suppression_records.append(serialized_row)

        normalization_suppressions = [
            suppression
            for result in normalization_results
            for suppression in result.suppressions
        ]
        for row in [
            *state.suppression_records,
            *normalization_suppressions,
        ]:
            add_suppression_record({
                "record_type": "state_suppression_or_dominance",
                **row.to_dict(),
            })
        for row in serialized["immunity_suppressions"]:
            add_suppression_record({
                "record_type": "reliability_immunity_suppression",
                "reason": "target_condition_immunity",
                **row,
            })
        suppression_records.sort(
            key=lambda row: (
                target_rank.get(str(row.get("target_id")), len(target_rank)),
                str(row.get("event_id", row.get("event_or_window_id", ""))),
                json.dumps(row, sort_keys=True),
            )
        )
        combined_repeat_records = [
            *serialized["repeat_save_records"],
            *repeat_save_records,
        ]
        combined_repeat_records.sort(
            key=lambda row: (
                schedule_event_rank.get(
                    str(row.get("event_id")),
                    len(schedule_event_rank),
                ),
                str(row.get("event_id", "")),
                str(row.get("gate_id", "")),
                target_rank.get(str(row.get("target_id")), len(target_rank)),
                json.dumps(row, sort_keys=True),
            )
        )
        return ControlEngineResult(
            version_provenance=self.version_provenance(
                initiative_convention=schedule.convention,
                area_response_convention=area_response_convention,
                displacement_function_id=displacement_function_id,
            ),
            scenario_convention=ScenarioConvention(
                self.config.horizon_rounds,
                schedule.convention,
                area_response_convention,
                displacement_function_id,
            ),
            compiled_program_id=program.effect_id,
            target_ids=schedule_targets,
            gate_probabilities=tuple(gate_probabilities),
            branch_probabilities=tuple(branch_probabilities),
            component_reliability=tuple(component_reliability),
            any_candidate_reliability={
                "overall": serialized["any_candidate_probability"],
                "by_target": any_candidate_by_target,
            },
            any_component_reliability={
                "overall": serialized["any_component_probability"],
                "by_target": any_component_by_target,
            },
            timeline=schedule.to_dict(),
            event_state_transitions=tuple(event_state_transitions),
            audit_ledger=tuple(state.audit_ledger),
            primitive_contributions={
                family: tuple(by_family[family])
                for family in DIAGNOSTIC_FAMILIES
            },
            suppression_and_dominance_records=tuple(suppression_records),
            refresh_and_replacement_records=tuple(refresh_replacement),
            repeat_save_records=tuple(combined_repeat_records),
            area_membership_and_route_records=tuple(validated_area_records),
            prone_standing_records=tuple(validated_prone_records),
            concentration_records=tuple(validated_concentration_records),
            displacement_epoch_records=tuple(displacement_epoch_records),
            final_normalized_state=state.final_normalized_state(
                self.catalog
            ),
            explored_state_count=reliability.final_world_count,
        )


def validate_fixture_corpus(
    path: str | Path = DEFAULT_FIXTURE_CORPUS,
) -> dict[str, Any]:
    """Validate the compact 67-case reviewed fixture contract and variants."""

    fixture_path = Path(path)
    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ControlEngineError(
            f"Unable to load control-engine fixtures: {error}"
        ) from error
    if (
        not isinstance(data, dict)
        or set(data) != {"format_version", "engine_version", "cases"}
    ):
        raise ControlEngineError(
            "Fixture corpus keys must be format_version, engine_version, and cases"
        )
    if (
        data["format_version"] != 1
        or isinstance(data["format_version"], bool)
    ):
        raise ControlEngineError("Fixture corpus format_version must be 1")
    if data["engine_version"] != ENGINE_VERSION:
        raise ControlEngineError(
            f"Fixture corpus engine_version must be {ENGINE_VERSION}"
        )
    cases = data["cases"]
    if not isinstance(cases, list) or len(cases) != 67:
        raise ControlEngineError(
            "Fixture corpus must contain exactly 67 reviewed cases"
        )
    expected_keys = {
        "id",
        "category",
        "invariant",
        "operation",
        "input",
        "expected",
    }
    counts = {
        category: 0
        for category in _EXPECTED_FIXTURE_CATEGORIES
    }
    invariants: set[str] = set()
    operations: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or set(case) != expected_keys:
            raise ControlEngineError(
                f"Fixture case {index} has invalid keys"
            )
        if case["id"] != index or isinstance(case["id"], bool):
            raise ControlEngineError(
                "Fixture case IDs must be exact sequential integers 1 through 67"
            )
        category = case["category"]
        if category not in counts:
            raise ControlEngineError(
                f"Fixture case {index} has unknown category {category!r}"
            )
        counts[category] += 1
        invariant = _identifier(
            case["invariant"],
            f"fixture case {index}.invariant",
        )
        operation = _identifier(
            case["operation"],
            f"fixture case {index}.operation",
        )
        if invariant in invariants:
            raise ControlEngineError(
                f"Fixture invariant names must be unique: {invariant!r}"
            )
        invariants.add(invariant)
        operations.add(operation)
        if (
            not isinstance(case["input"], dict)
            or not isinstance(case["expected"], dict)
        ):
            raise ControlEngineError(
                f"Fixture case {index} input and expected must be objects"
            )
    if counts != dict(_EXPECTED_FIXTURE_CATEGORIES):
        raise ControlEngineError(
            f"Fixture category inventory is invalid: {counts}"
        )

    schedules: dict[str, int] = {}
    for convention in INITIATIVE_CONVENTIONS:
        schedule = build_schedule(
            convention,
            ["fixture_alpha", "fixture_beta"],
            target_attack_counts={
                "fixture_alpha": [1, 0, 2],
                "fixture_beta": [0, 1, 1],
            },
            rounds=3,
        )
        schedules[convention] = len(schedule.events)
    shortest = area_response(
        "shortest_route_v1",
        target_id="fixture_alpha",
        membership=True,
        effect_active=True,
        routes=[
            {
                "route_id": "walk_exit",
                "mode": "walk",
                "distance_to_exit_ft": 10,
                "compatible": True,
                "movement_cost_multiplier": 1,
                "environment": "grounded",
            }
        ],
        effective_speeds_ft={"walk": 30},
    )
    fixed = area_response(
        "fixed_occupancy_v1",
        target_id="fixture_alpha",
        membership=True,
        effect_active=True,
    )
    if not shortest["exited"] or not fixed["membership_after"]:
        raise ControlEngineError(
            "Area convention probes did not preserve their named semantics"
        )
    displacement = {
        function_id: displacement_function(function_id, 10)
        for function_id in DISPLACEMENT_FUNCTIONS
    }
    if any(value <= 0 for value in displacement.values()):
        raise ControlEngineError(
            "Every displacement function must represent a 10-foot push"
        )
    return {
        "fixture_cases": len(cases),
        "fixture_categories": counts,
        "fixture_operations": len(operations),
        "initiative_schedules": schedules,
        "area_response_conventions": list(AREA_RESPONSE_CONVENTIONS),
        "displacement_functions": displacement,
    }


def validate_engine(
    *,
    fixture_path: str | Path = DEFAULT_FIXTURE_CORPUS,
) -> dict[str, Any]:
    """Run the cheap deterministic runtime/configuration validation used by CI."""

    engine = ControlEngine.load()
    if len(engine.catalog.conditions) != 7 or len(PRIMITIVE_CONTRACT) != 23:
        raise ControlEngineError(
            "Catalog scope must remain seven conditions and 23 primitives"
        )
    if len(engine.authority.programs) != 35:
        raise ControlEngineError(
            "Control Authority must compile exactly 35 modeled programs"
        )
    if len(engine.authority.masteries) != 3:
        raise ControlEngineError(
            "Control Authority must compile exactly three masteries"
        )
    if len(engine.authority.exclusions) != 14:
        raise ControlEngineError(
            "Control Authority must preserve exactly 14 profile exclusions"
        )
    if len(engine.targets) != 28:
        raise ControlEngineError(
            "Control target inputs must remain an exact 28-row join"
        )
    encountered_kinds: set[str] = set()
    for program in engine.authority.programs:
        program.bind_choices(
            {
                choice.choice_id: choice.options[0]
                for choice in program.choices
            }
        )
        encountered_kinds.update(
            component.magnitude.kind
            for component in program.components
        )
    encountered_kinds.update(
        mastery.component.magnitude.kind
        for mastery in engine.authority.masteries
    )
    unknown = encountered_kinds - CONTROL_MAGNITUDE_KINDS
    if unknown:
        raise ControlEngineError(
            f"Compiled authority contains unsupported magnitudes: {sorted(unknown)}"
        )
    fixtures = validate_fixture_corpus(fixture_path)
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "authority_projection_version": engine.authority.projection_version,
        "compiled_programs": len(engine.authority.programs),
        "compiled_masteries": len(engine.authority.masteries),
        "preserved_exclusions": len(engine.authority.exclusions),
        "control_target_rows": len(engine.targets),
        "catalog_version": engine.catalog.catalog_version,
        "catalog_conditions": len(engine.catalog.conditions),
        "primitive_contract_version": (
            engine.catalog.primitive_contract_version
        ),
        "primitive_count": len(PRIMITIVE_CONTRACT),
        "normalization_rules_version": NORMALIZATION_RULES_VERSION,
        "timeline_engine_version": TIMELINE_ENGINE_VERSION,
        "engine_config_version": engine.config.config_version,
        "supported_magnitude_kinds": sorted(
            CONTROL_MAGNITUDE_KINDS
        ),
        "encountered_magnitude_kinds": sorted(
            encountered_kinds
        ),
        **fixtures,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="validate all engine inputs and fixtures",
    )
    mode.add_argument(
        "--fixtures-only",
        action="store_true",
        help="validate only the reviewed fixture corpus",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_CORPUS,
    )
    args = parser.parse_args(argv)
    summary = (
        validate_fixture_corpus(args.fixture_path)
        if args.fixtures_only
        else validate_engine(fixture_path=args.fixture_path)
    )
    print(
        json.dumps(
            summary,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ControlEngine",
    "ControlEngineError",
    "ControlEngineResult",
    "DisplacementRequest",
    "ENGINE_VERSION",
    "ScenarioConvention",
    "VersionProvenance",
    "main",
    "reliability_result_to_dict",
    "validate_engine",
    "validate_fixture_corpus",
]
