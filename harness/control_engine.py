"""Public facade for the shared control consequence and timeline engine.

The runtime is intentionally a coordinator, not a planner. Callers choose an
effect, targets, legal choices, probability inputs, event order, initiative,
area convention, and displacement function. This module validates those
boundaries and packages the independently testable graph, state, and timeline
layers into one deterministic JSON result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass, replace
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
    D20ProbabilityKernel,
    ProbabilityContext,
    ProbabilityKernel,
    ReliabilityEvent,
    ReliabilityResult,
    ReliabilityTarget,
    SelectorContext,
    evaluate_reliability,
    load_compiled_control_authority,
    reliability_result_issuance_token,
    resolve_roll_mode,
    validate_reliability_result,
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
    condition_instance_id_for,
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
    ENVIRONMENTS,
    INITIATIVE_CONVENTIONS,
    TIMELINE_ENGINE_VERSION,
    ConcentrationTracker,
    DisplacementEpochs,
    ReactionInterval,
    TimelineError,
    TimelineEvent,
    TimelineSchedule,
    area_entry,
    area_response,
    airborne_fall_transition,
    build_schedule,
    displacement_function,
    enumerate_prone_movement_operations,
    prone_movement_response,
    resolve_expiry_index,
    typed_event_matches,
    vertical_displacement_vector,
)
from harness.model import DEFAULT_ROSTER, file_sha256


ENGINE_VERSION = "2.0.0"
DEFAULT_FIXTURE_CORPUS = (
    Path(__file__).resolve().parent / "tests" / "fixtures" / "control_engine_v2.json"
)

_EXPECTED_FIXTURE_CATEGORIES = MappingProxyType(
    {
        "catalog_and_senses": 8,
        "partial_reliability": 7,
        "overlap_and_dominance": 9,
        "prone": 8,
        "timing_and_initiative": 8,
        "repeat_saves": 5,
        "concentration": 6,
        "areas": 10,
        "displacement": 7,
        "weight_and_scope_boundary": 4,
    }
)
_SESSION_TIMELINE_EVENT_KINDS = frozenset({
    "action_proposal",
    "activation",
    "attack_opportunity",
    "condition_application",
    "condition_end",
    "concentration_end",
    "controller_attack_opportunity",
    "controller_turn_end",
    "controller_turn_start",
    "damage_context",
    "declaration",
    "entry",
    "exit",
    "hit",
    "instantaneous_resolution",
    "initiative_opportunity",
    "reaction_window",
    "round_end",
    "round_start",
    "save_opportunity",
    "fall_transition",
    "target_active_turn_opportunity",
    "target_attack_opportunity",
    "target_movement_opportunity",
    "target_turn_end",
    "target_turn_start",
})
_SESSION_STRUCTURAL_EVENT_KINDS = frozenset({
    "controller_turn_end",
    "controller_turn_start",
    "round_end",
    "round_start",
    "target_active_turn_opportunity",
    "target_attack_opportunity",
    "target_movement_opportunity",
    "target_turn_end",
    "target_turn_start",
})
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
_RESULT_CONSTRUCTION_TOKEN = object()
_RESULT_CONSTRUCTION_DEPTH = 0


class ControlEngineError(ValueError):
    """Raised when the public facade would need to invent scenario policy."""


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ControlEngineError(f"{label} must be a non-empty trimmed string")
    return value


def _fraction_record(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_number(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


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


def _nonnegative_fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool):
        raise ControlEngineError(f"{label} must be a non-negative finite number")
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int):
        result = Fraction(value)
    elif isinstance(value, float) and math.isfinite(value):
        result = Fraction(str(value))
    elif (
        isinstance(value, Mapping)
        and set(value) == {"numerator", "denominator"}
        and isinstance(value["numerator"], int)
        and not isinstance(value["numerator"], bool)
        and isinstance(value["denominator"], int)
        and not isinstance(value["denominator"], bool)
        and value["denominator"] > 0
    ):
        result = Fraction(value["numerator"], value["denominator"])
    else:
        raise ControlEngineError(f"{label} must be a non-negative finite number")
    if result < 0:
        raise ControlEngineError(f"{label} must be non-negative")
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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_record(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_string_mapping_keys(value: Any, path: str) -> None:
    """Reject lossy JSON key coercion in scenario identity inputs."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if (
                not isinstance(key, str)
                or not key
                or key.strip() != key
            ):
                raise ControlEngineError(
                    f"{path} contains an invalid JSON object key: {key!r}"
                )
            _require_string_mapping_keys(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _require_string_mapping_keys(item, f"{path}[{index}]")


def _strict_json_copy(value: Any, path: str) -> Any:
    """Validate caller-owned scenario data without any lossy coercion."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ControlEngineError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, list):
        return [
            _strict_json_copy(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if (
                not isinstance(key, str)
                or not key
                or key.strip() != key
            ):
                raise ControlEngineError(
                    f"{path} contains an invalid JSON object key: {key!r}"
                )
            result[key] = _strict_json_copy(item, f"{path}.{key}")
        return result
    raise ControlEngineError(
        f"{path} must contain only strict JSON values; got "
        f"{type(value).__name__}"
    )


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            key: _deep_freeze(item) for key, item in value.items()
        })
    if isinstance(value, (tuple, list)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


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
    engine_implementation_digest: str
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
class AreaRouteGeometry:
    """One exact, caller-observed exit route normalized at scenario binding."""

    route_id: str
    mode: str
    distance_to_exit_ft: Fraction | int | float | Mapping[str, int]
    compatible: bool
    movement_cost_multiplier: Fraction | int | float | Mapping[str, int]
    environment: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", _identifier(self.route_id, "route_id"))
        if self.mode not in MOVEMENT_MODES:
            raise ControlEngineError(f"Unsupported route movement mode: {self.mode!r}")
        if self.environment not in ENVIRONMENTS:
            raise ControlEngineError(f"Unsupported route environment: {self.environment!r}")
        if not isinstance(self.compatible, bool):
            raise ControlEngineError("route compatibility must be boolean")
        object.__setattr__(
            self,
            "distance_to_exit_ft",
            _nonnegative_fraction(self.distance_to_exit_ft, "distance_to_exit_ft"),
        )
        object.__setattr__(
            self,
            "movement_cost_multiplier",
            _positive_fraction(
                self.movement_cost_multiplier,
                "movement_cost_multiplier",
            ),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], label: str) -> "AreaRouteGeometry":
        if not isinstance(value, Mapping):
            raise ControlEngineError(f"{label} must be an object")
        expected = {
            "route_id",
            "mode",
            "distance_to_exit_ft",
            "compatible",
            "movement_cost_multiplier",
            "environment",
        }
        if set(value) != expected:
            raise ControlEngineError(
                f"{label} keys are invalid; missing={sorted(expected - set(value))}, "
                f"unknown={sorted(set(value) - expected)}"
            )
        try:
            return cls(**dict(value))
        except (ControlEngineError, TypeError, ValueError) as error:
            raise ControlEngineError(f"{label} is invalid: {error}") from error

    def route_input(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "mode": self.mode,
            "distance_to_exit_ft": _fraction_record(self.distance_to_exit_ft),
            "compatible": self.compatible,
            "movement_cost_multiplier": _fraction_record(
                self.movement_cost_multiplier
            ),
            "environment": self.environment,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.route_input(),
            "distance_to_exit_exact": _fraction_record(self.distance_to_exit_ft),
            "movement_cost_multiplier_exact": _fraction_record(
                self.movement_cost_multiplier
            ),
        }


@dataclass(frozen=True)
class AreaGeometryUpdate:
    """Scenario-bound geometry supplied for one compiled moving-area event."""

    effect_id: str
    area_id: str
    target_id: str
    event_id: str
    event_sequence: int
    new_membership: bool
    routes: tuple[AreaRouteGeometry, ...]

    def __post_init__(self) -> None:
        for name in ("effect_id", "area_id", "target_id", "event_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        if (
            isinstance(self.event_sequence, bool)
            or not isinstance(self.event_sequence, int)
            or self.event_sequence < 0
        ):
            raise ControlEngineError("event_sequence must be a non-negative integer")
        if not isinstance(self.new_membership, bool):
            raise ControlEngineError("new_membership must be boolean")
        route_rows = tuple(self.routes)
        if any(not isinstance(route, AreaRouteGeometry) for route in route_rows):
            raise ControlEngineError("routes must contain AreaRouteGeometry values")
        route_ids = tuple(route.route_id for route in route_rows)
        if len(route_ids) != len(set(route_ids)):
            raise ControlEngineError("routes must contain unique route IDs")
        if self.new_membership and not route_rows:
            raise ControlEngineError("member geometry updates require at least one route")
        if not self.new_membership and route_rows:
            raise ControlEngineError("non-member geometry updates cannot retain routes")
        object.__setattr__(self, "routes", route_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "area_id": self.area_id,
            "target_id": self.target_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "new_membership": self.new_membership,
            "routes": [route.to_dict() for route in self.routes],
        }


@dataclass(frozen=True)
class AreaEntryTransition:
    """One scenario-bound false-to-true compiled-area membership transition."""

    effect_id: str
    area_id: str
    target_id: str
    event_id: str
    event_sequence: int
    cause: str
    turn_id: str
    routes: tuple[AreaRouteGeometry, ...]
    moved_area_counts_as_entry: bool

    def __post_init__(self) -> None:
        for name in (
            "effect_id",
            "area_id",
            "target_id",
            "event_id",
            "turn_id",
        ):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        if (
            isinstance(self.event_sequence, bool)
            or not isinstance(self.event_sequence, int)
            or self.event_sequence < 0
        ):
            raise ControlEngineError("event_sequence must be a non-negative integer")
        if self.cause not in {
            "ordinary_movement",
            "forced_movement",
            "area_movement",
        }:
            raise ControlEngineError(
                f"Unsupported area-entry cause: {self.cause!r}"
            )
        if not isinstance(self.moved_area_counts_as_entry, bool):
            raise ControlEngineError(
                "moved_area_counts_as_entry must be boolean"
            )
        route_rows = tuple(self.routes)
        if any(not isinstance(route, AreaRouteGeometry) for route in route_rows):
            raise ControlEngineError("routes must contain AreaRouteGeometry values")
        route_ids = tuple(route.route_id for route in route_rows)
        if len(route_ids) != len(set(route_ids)):
            raise ControlEngineError("routes must contain unique route IDs")
        object.__setattr__(self, "routes", route_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "area_id": self.area_id,
            "target_id": self.target_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "cause": self.cause,
            "turn_id": self.turn_id,
            "routes": [route.to_dict() for route in self.routes],
            "moved_area_counts_as_entry": self.moved_area_counts_as_entry,
        }


@dataclass(frozen=True)
class _AreaRouteState:
    effect_id: str
    area_id: str
    target_id: str
    membership: bool
    routes: tuple[AreaRouteGeometry, ...]
    selected_route_id: str | None
    movement_mode: str | None
    environment: str | None
    remaining_distance_ft: Fraction | None
    movement_cost_basis: Mapping[str, Any] | None
    closed_reason: str | None
    last_update_event_id: str
    last_update_event_sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_id": self.effect_id,
            "area_id": self.area_id,
            "target_id": self.target_id,
            "membership": self.membership,
            "routes": [route.to_dict() for route in self.routes],
            "selected_route_id": self.selected_route_id,
            "movement_mode": self.movement_mode,
            "environment": self.environment,
            "remaining_distance_ft": (
                None
                if self.remaining_distance_ft is None
                else _fraction_number(self.remaining_distance_ft)
            ),
            "remaining_distance_exact": (
                None
                if self.remaining_distance_ft is None
                else _fraction_record(self.remaining_distance_ft)
            ),
            "movement_cost_basis": _json_safe(self.movement_cost_basis),
            "closed_reason": self.closed_reason,
            "last_update_event_id": self.last_update_event_id,
            "last_update_event_sequence": self.last_update_event_sequence,
        }


@dataclass(frozen=True)
class _IssuedControlRecord:
    """Opaque proof that one record was emitted by one execution session.

    The public representation deliberately omits the issuer token.  The token
    and object identity are checked again by ``ControlExecutionSession.result``;
    copying the serialized mapping therefore cannot manufacture provenance.
    """

    scenario_digest: str
    event_id: str
    event_sequence: int
    operation_sequence: int
    target_id: str | None
    record_kind: str
    pre_event_state_json: str
    pre_operation_state_json: str
    post_operation_state_json: str
    pre_event_route_state_json: str
    pre_operation_route_state_json: str
    post_operation_route_state_json: str
    payload_json: str
    payload_sha256: str
    record_sha256: str
    _issuer: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_digest": self.scenario_digest,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "operation_sequence": self.operation_sequence,
            "target_id": self.target_id,
            "record_kind": self.record_kind,
            "pre_event_state": json.loads(self.pre_event_state_json),
            "pre_operation_state": json.loads(self.pre_operation_state_json),
            "post_operation_state": json.loads(self.post_operation_state_json),
            "pre_event_route_state": json.loads(self.pre_event_route_state_json),
            "pre_operation_route_state": json.loads(
                self.pre_operation_route_state_json
            ),
            "post_operation_route_state": json.loads(
                self.post_operation_route_state_json
            ),
            "payload": json.loads(self.payload_json),
            "payload_sha256": self.payload_sha256,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class _SessionEventReference:
    event_id: str
    event_sequence: int
    scenario_digest: str
    _issuer: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class _ClosedEventSnapshot:
    scenario_digest: str
    event_id: str
    event_sequence: int
    pre_event_state_json: str
    post_event_state_json: str
    pre_event_route_state_json: str
    post_event_route_state_json: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_digest": self.scenario_digest,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "pre_event_state": json.loads(self.pre_event_state_json),
            "post_event_state": json.loads(self.post_event_state_json),
            "pre_event_route_state": json.loads(self.pre_event_route_state_json),
            "post_event_route_state": json.loads(self.post_event_route_state_json),
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
class _PendingConcentrationFailure:
    """Session-issued proof of one deferred failed-check termination."""

    scenario_digest: str
    effect_id: str
    invocation_id: str
    source_actor_id: str
    damage_event_id: str
    damage_event_sequence: int
    end_event_id: str
    end_event_sequence: int
    check_operation_sequence: int
    check_record_json: str
    tracker_pre_state_json: str
    tracker_post_check_state_json: str
    tracker_end_record_json: str
    authority_metadata_json: str
    end_plan: tuple[tuple[str, str, str], ...]
    affected_target_ids: tuple[str, ...]
    pending_sha256: str
    _issuer: object = field(repr=False, compare=False)

    def identity(self) -> dict[str, Any]:
        return {
            "scenario_digest": self.scenario_digest,
            "effect_id": self.effect_id,
            "invocation_id": self.invocation_id,
            "source_actor_id": self.source_actor_id,
            "damage_event_id": self.damage_event_id,
            "damage_event_sequence": self.damage_event_sequence,
            "end_event_id": self.end_event_id,
            "end_event_sequence": self.end_event_sequence,
            "check_operation_sequence": self.check_operation_sequence,
            "check_record": json.loads(self.check_record_json),
            "tracker_pre_state": json.loads(self.tracker_pre_state_json),
            "tracker_post_check_state": json.loads(
                self.tracker_post_check_state_json
            ),
            "tracker_end_record": json.loads(self.tracker_end_record_json),
            "authority_metadata": json.loads(self.authority_metadata_json),
            "compiled_end_plan": [
                {
                    "gate_id": gate_id,
                    "target_id": target_id,
                    "outcome": outcome,
                }
                for gate_id, target_id, outcome in self.end_plan
            ],
            "affected_target_ids": list(self.affected_target_ids),
        }

    def computed_sha256(self) -> str:
        return _sha256_record(self.identity())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity(),
            "pending_sha256": self.pending_sha256,
        }


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
    prone_operation_records: tuple[Mapping[str, Any], ...]
    concentration_records: tuple[Mapping[str, Any], ...]
    displacement_epoch_records: tuple[Mapping[str, Any], ...]
    final_normalized_state: Mapping[str, Any]
    explored_state_count: int
    scenario_digest: str = ""
    scenario_record: Mapping[str, Any] = field(default_factory=dict)
    execution_records: tuple[Mapping[str, Any], ...] = ()
    event_snapshots: tuple[Mapping[str, Any], ...] = ()
    area_route_transitions: tuple[Mapping[str, Any], ...] = ()
    final_area_route_states: tuple[Mapping[str, Any], ...] = ()
    condition_instance_registry: tuple[Mapping[str, Any], ...] = ()
    condition_lifecycle_records: tuple[Mapping[str, Any], ...] = ()
    inclusion_lineage_records: tuple[Mapping[str, Any], ...] = ()
    opportunity_roll_records: tuple[Mapping[str, Any], ...] = ()
    source_relative_legality_records: tuple[Mapping[str, Any], ...] = ()
    condition_concentration_records: tuple[Mapping[str, Any], ...] = ()
    fall_transition_records: tuple[Mapping[str, Any], ...] = ()
    _construction_token: object | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if _RESULT_CONSTRUCTION_DEPTH <= 0:
            raise ControlEngineError(
                "ControlEngineResult values are issued only by an execution session"
            )
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
        if self.scenario_digest and (
            len(self.scenario_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.scenario_digest)
        ):
            raise ControlEngineError("scenario_digest must be a lowercase SHA-256 digest")
        for result_field in fields(self):
            value = getattr(self, result_field.name)
            if isinstance(value, (Mapping, tuple, list, set, frozenset)):
                object.__setattr__(
                    self,
                    result_field.name,
                    _deep_freeze(value),
                )

    def to_dict(self) -> dict[str, Any]:
        if self._construction_token is not _RESULT_CONSTRUCTION_TOKEN:
            raise ControlEngineError(
                "ControlEngineResult value is not engine/session-issued"
            )
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
            "prone_operation_records": self.prone_operation_records,
            "concentration_records": self.concentration_records,
            "displacement_epoch_records": self.displacement_epoch_records,
            "final_normalized_state": self.final_normalized_state,
            "explored_state_count": self.explored_state_count,
            "scenario_digest": self.scenario_digest or None,
            "scenario_record": self.scenario_record or None,
            "execution_records": self.execution_records,
            "event_snapshots": self.event_snapshots,
            "area_route_transitions": self.area_route_transitions,
            "final_area_route_states": self.final_area_route_states,
            "condition_instance_registry": self.condition_instance_registry,
            "condition_lifecycle_records": self.condition_lifecycle_records,
            "inclusion_lineage_records": self.inclusion_lineage_records,
            "opportunity_roll_records": self.opportunity_roll_records,
            "source_relative_legality_records": (
                self.source_relative_legality_records
            ),
            "condition_concentration_records": (
                self.condition_concentration_records
            ),
            "fall_transition_records": self.fall_transition_records,
        }
        safe = _json_safe(result)
        _assert_weight_free(safe)
        return safe


def _construct_control_engine_result(**values: Any) -> ControlEngineResult:
    global _RESULT_CONSTRUCTION_DEPTH
    _RESULT_CONSTRUCTION_DEPTH += 1
    try:
        result = ControlEngineResult(**values)
    finally:
        _RESULT_CONSTRUCTION_DEPTH -= 1
    object.__setattr__(result, "_construction_token", _RESULT_CONSTRUCTION_TOKEN)
    return result


def _replace_control_engine_result(
    result: ControlEngineResult,
    **changes: Any,
) -> ControlEngineResult:
    if result._construction_token is not _RESULT_CONSTRUCTION_TOKEN:
        raise ControlEngineError("Cannot replace an unattested engine result")
    global _RESULT_CONSTRUCTION_DEPTH
    _RESULT_CONSTRUCTION_DEPTH += 1
    try:
        issued = replace(result, **changes)
    finally:
        _RESULT_CONSTRUCTION_DEPTH -= 1
    object.__setattr__(issued, "_construction_token", _RESULT_CONSTRUCTION_TOKEN)
    return issued


def reliability_result_to_dict(result: ReliabilityResult) -> dict[str, Any]:
    """Serialize exact graph probabilities without replacing fractions by floats."""

    if not isinstance(result, ReliabilityResult):
        raise TypeError("result must be ReliabilityResult")
    return {
        "effect_id": result.effect_id,
        "scenario_digest": result.scenario_digest,
        "scenario": (
            result.scenario.canonical_record()
            if result.scenario is not None else None
        ),
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
        self._execution_tokens: set[object] = set()
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

    def _new_state(self) -> ControlState:
        return ControlState()

    def new_state(self) -> ControlState:
        raise ControlEngineError(
            "Independent mutable state is not a supported facade; use "
            "ControlEngine.execution_session()"
        )

    def _new_displacement_epochs(self) -> DisplacementEpochs:
        return DisplacementEpochs()

    def new_displacement_epochs(self) -> DisplacementEpochs:
        raise ControlEngineError(
            "Independent displacement epochs are not a supported facade; use "
            "ControlEngine.execution_session()"
        )

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

    @staticmethod
    def _unsupported_independent_operation(name: str) -> None:
        raise ControlEngineError(
            f"{name} is session-owned; use ControlEngine.execution_session()"
        )

    def apply_resolved_branch(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("apply_resolved_branch")

    def resolve_displacement(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("resolve_displacement")

    def resolve_self_movement_epoch(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("resolve_self_movement_epoch")

    def resolve_prone_movement(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("resolve_prone_movement")

    def resolve_compiled_area_entry(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("resolve_compiled_area_entry")

    def resolve_area_response(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("resolve_area_response")

    def start_concentration(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("start_concentration")

    def check_concentration(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("check_concentration")

    def end_concentration(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("end_concentration")

    def reconcile_concentration_duration(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("reconcile_concentration_duration")

    def normalize_scheduled_window(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("normalize_scheduled_window")

    def _apply_resolved_branch(
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
        _active_guard_snapshot: Sequence[Mapping[str, Any]] | None = None,
        _allow_reachable_same_event: bool = False,
        _suppressed_application_component_ids: Iterable[str] = (),
        source_program_id: str | None = None,
        issuance_id: str | None = None,
        provenance_id: str | None = None,
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
        if not event_matches and not _allow_reachable_same_event:
            raise ControlEngineError(
                f"Schedule event {event!r} does not match gate {gate.gate_id!r} "
                "trigger/owner/target semantics"
            )
        target_required = gate.trigger.kind in {"save", "hit", "damage_context"}
        if (
            not _allow_reachable_same_event
            and (
            (target_required and schedule_event.target_id != target)
            or (
                schedule_event.target_id is not None
                and schedule_event.target_id != target
            )
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

        suppressed_application_component_ids = frozenset(
            _identifier(
                component_id,
                "_suppressed_application_component_ids item",
            )
            for component_id in _suppressed_application_component_ids
        )
        invalid_suppressions = sorted(
            suppressed_application_component_ids - set(branch.applies)
        )
        if invalid_suppressions:
            raise ControlEngineError(
                "Suppressed branch applications are not present in the "
                f"compiled branch: {invalid_suppressions}"
            )
        applies = [
            component_id
            for component_id in branch.applies
            if applies_to_target(component_id)
            and component_id not in suppressed_application_component_ids
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
        required_active_component_ids = gate.requires_active_component_ids
        if _active_guard_snapshot is not None:
            pre_guard_ids = {
                str(item.get("component_id"))
                for item in _active_guard_snapshot
                if item.get("effect_id") == program.effect_id
                and item.get("target_id") == target
            }
            missing_guards = sorted(
                set(required_active_component_ids) - pre_guard_ids
            )
            if missing_guards:
                before = state.snapshot(target)
                transition = {
                    "event_id": event,
                    "operation": "guard_suppressed",
                    "target_id": target,
                    "effect_id": program.effect_id,
                    "branch_id": branch.branch_id,
                    "missing_active_component_ids": missing_guards,
                    "active_components_before": before,
                    "active_components_after": before,
                    "guard_snapshot": "session_pre_event",
                }
                state.audit_ledger.append(transition)
                return transition
            required_active_component_ids = ()

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
            required_active_component_ids=required_active_component_ids,
            expiry_event_ids=expiry_event_ids,
            condition_immunities=condition_immunities,
            relationships=relationships,
            application_sequence=schedule_event.sequence,
            source_program_id=(
                program.effect_id
                if source_program_id is None else source_program_id
            ),
            issuance_id=(
                f"branch:{invocation}:{event}:{gate.gate_id}:{target}"
                if issuance_id is None else issuance_id
            ),
            provenance_id=(
                program.authority_sha256
                if provenance_id is None else provenance_id
            ),
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

    def _resolve_displacement(
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



    def _resolve_self_movement_epoch(
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

    def _resolve_prone_movement(
        self,
        *,
        state: ControlState,
        schedule: TimelineSchedule,
        target_id: str,
        event_id: str,
        base_speeds_ft: Mapping[str, int],
        movement_mode: str,
        prone_operation: Mapping[str, Any],
        movement_budget_ft: int,
        difficult_terrain: bool = False,
        mixed_speed_operation_order: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Validate one explicit Prone response and keep active state in sync."""

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
        if "walk" not in effective_speeds:
            raise ControlEngineError(
                "Prone operations require an explicit current walking Speed"
            )
        current_speed_ft = effective_speeds["walk"]
        movement_denied = (
            movement_mode_value in movement_authority["denied_modes"]
        )
        if not isinstance(prone_operation, Mapping):
            raise ControlEngineError("prone_operation must be an object")
        prone_before = [
            component
            for component in state.active_components(target)
            if component.magnitude.get("kind") == "condition"
            and component.magnitude.get("condition") == "prone"
        ]
        response = prone_movement_response(
            target_id=target,
            actor_id=target,
            kind=str(prone_operation.get("kind")),
            prone=bool(prone_before),
            current_speed_ft=current_speed_ft,
            movement_budget_ft=movement_budget_ft,
            distance_feet=prone_operation.get("distance_feet"),
            difficult_terrain=difficult_terrain,
            movement_denied=movement_denied,
        )
        if response["dropped_prone"]:
            raise ControlEngineError(
                "Voluntary drop Prone requires session-issued provenance"
            )
        ended_condition_instances: list[Any] = []
        if response["stood"]:
            for instance in tuple(state.active_condition_instances(target)):
                if instance.condition_id != "prone":
                    continue
                ended_condition_instances.extend(state.end_condition_instance(
                    instance.instance_id,
                    event_id=event.event_id,
                    event_sequence=event.sequence,
                    reason="explicit_stand_operation",
                    expected_source_actor_id=instance.source_actor_id,
                    expected_issuance_id=instance.issuance_id,
                ))
        active_after = state.snapshot(target)
        active_instance_ids = {row["instance_id"] for row in active_after}
        record = {
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "proposal_operation_sequence": None,
            "proposal_record_sha256": None,
            "movement_mode": movement_mode_value,
            "movement_authority": movement_authority,
            "area_response_operation": False,
            **response,
            "kind": "prone_operation",
            "ended_component_ids": sorted({
                component.component_id
                for component in prone_before
                if component.instance_id not in active_instance_ids
            }),
            "ended_condition_instance_ids": sorted(
                instance.instance_id for instance in ended_condition_instances
            ),
            "active_conditions_after": list(
                state.derived_current_conditions(target)
            ),
            "created_condition_instances": [],
            "fall_transition": None,
            "active_components_after": active_after,
        }
        state.audit_ledger.append({
            "operation": "prone_operation",
            "prone_operation": record["operation"],
            **{
                field_name: value
                for field_name, value in record.items()
                if field_name != "operation"
            },
        })
        return record

    def _resolve_compiled_area_entry(
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

    def _resolve_area_response(
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
        prone_operation: Mapping[str, Any] | None = None,
        prone_current_speed_ft: int | None = None,
        movement_budget_ft: int | None = None,
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
            for component in state.active_components(target)
            if not (
                component.effect_id == program.effect_id
                and component.component_id in while_in_area_ids
            )
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
                prone_operation=prone_operation,
                current_speed_ft=prone_current_speed_ft,
                movement_budget_ft=movement_budget_ft,
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
        ).get("prone_response") or response.get("prone_response")
        if isinstance(prone_response, Mapping) and prone_response.get("stood"):
            for instance in tuple(
                state.active_condition_instances(target)
            ):
                if instance.condition_id != "prone":
                    continue
                state.end_condition_instance(
                    instance.instance_id,
                    event_id=event.event_id,
                    event_sequence=event.sequence,
                    reason="explicit_stand_operation",
                    expected_source_actor_id=instance.source_actor_id,
                    expected_issuance_id=instance.issuance_id,
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
            or tracker.owner_actor_id != context.source_actor_id
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
        if reason not in {"duration_expiry", "controller_incapacitated"}:
            if event.kind != "concentration_end":
                raise ControlEngineError(
                    "Concentration termination must bind to a typed "
                    "concentration_end event"
                )
            return context.schedule
        if reason == "duration_expiry":
            expected = self._recomputed_concentration_expiry_event_id(context)
            if expected is None or event.event_id != expected:
                raise ControlEngineError(
                    "duration_expiry event does not match the compiled boundary"
                )
        # Incapacitated may be activated by a compiled save/hit branch or by a
        # standalone typed condition-application event.  The caller proves the
        # exact newly created Incapacitated instance before requesting this
        # destructive transition; the concentration gate sees the same event
        # through its canonical concentration_end trigger shape.
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
        if result.get("owner_actor_id") != context.source_actor_id:
            raise ControlEngineError(
                "concentration_end owner_actor_id does not match compiled authority"
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
            transition = self._apply_resolved_branch(
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

    def _start_concentration(
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
        if tracker.owner_actor_id != new_context.source_actor_id:
            raise ControlEngineError(
                "Concentration tracker owner does not match source_actor_id"
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

    def _check_concentration(
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

    def _end_concentration(
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
        record = tracker.end(
            reason=reason,
            event_id=end_event.event_id,
            owner_actor_id=(
                source_actor_id
                if reason == "controller_incapacitated"
                else None
            ),
        )
        result = self._apply_concentration_end_record(
            state=state,
            record=record,
            context=context,
            plans=plans,
        )
        del self._concentration_contexts[tracker]
        return result
    def _reconcile_concentration_duration(
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
        return self._end_concentration(
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
            file_sha256(Path(__file__)),
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

    def execution_session(
        self,
        effect: CompiledEffect | str,
        *,
        targets: Sequence[ReliabilityTarget],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        schedule: TimelineSchedule,
        target_mechanics: Mapping[str, Mapping[str, Any]],
        area_response_convention: str,
        displacement_function_id: str,
        kernel: ProbabilityKernel | None = None,
        probability_context: ProbabilityContext = ProbabilityContext(),
        choices: Mapping[str, str] | None = None,
        reliability_events: Sequence[ReliabilityEvent] = (),
        candidate_component_ids: Iterable[str] | None = None,
        include_initial: bool = True,
        source_actor_id: str = "controller",
        invocation_id: str = "control_invocation",
        operation_inputs_by_event: (
            Mapping[str, Mapping[str, Any]] | None
        ) = None,
        area_geometry_updates: Sequence[AreaGeometryUpdate] = (),
        area_entry_transitions: Sequence[AreaEntryTransition] = (),
        concentration_save_bonus: int | None = None,
    ) -> "ControlExecutionSession":
        """Create the sole supported mutable execution and result boundary."""

        session = ControlExecutionSession(
            self,
            effect=effect,
            targets=targets,
            selector_membership=selector_membership,
            selector_context=selector_context,
            schedule=schedule,
            target_mechanics=target_mechanics,
            area_response_convention=area_response_convention,
            displacement_function_id=displacement_function_id,
            kernel=kernel,
            probability_context=probability_context,
            choices=choices,
            reliability_events=reliability_events,
            candidate_component_ids=candidate_component_ids,
            include_initial=include_initial,
            source_actor_id=source_actor_id,
            invocation_id=invocation_id,
            operation_inputs_by_event=operation_inputs_by_event,
            area_geometry_updates=area_geometry_updates,
            area_entry_transitions=area_entry_transitions,
            concentration_save_bonus=concentration_save_bonus,
        )
        self._execution_tokens.add(session._issuer)
        return session

    def _normalize_scheduled_window(
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

    def assemble_result(self, *args: Any, **kwargs: Any) -> None:
        self._unsupported_independent_operation("assemble_result")

    def _assemble_result_legacy(
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
            required = {
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
            allowed = required | {"condition_instance_id"}
            if not isinstance(value, list):
                raise ControlEngineError(f"{label} must be an array")
            for index, item in enumerate(value):
                if not isinstance(item, Mapping):
                    raise ControlEngineError(
                        f"{label}[{index}] must be an object"
                    )
                if not required.issubset(item) or set(item) - allowed:
                    raise ControlEngineError(
                        f"{label}[{index}] has an invalid closed record shape; "
                        f"missing={sorted(required - set(item))}, "
                        f"unknown={sorted(set(item) - allowed)}"
                    )
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
                condition_instance_id = item.get("condition_instance_id")
                if condition_instance_id is not None and (
                    not isinstance(condition_instance_id, str)
                    or not condition_instance_id
                ):
                    raise ControlEngineError(
                        f"{label}[{index}].condition_instance_id is invalid"
                    )
                if not all(
                    isinstance(item[field_name], Mapping)
                    for field_name in ("magnitude", "duration", "stacking")
                ):
                    raise ControlEngineError(
                        f"{label}[{index}] component authority is invalid"
                    )
                if (
                    item["magnitude"].get("kind") == "condition"
                ) != (condition_instance_id is not None):
                    raise ControlEngineError(
                        f"{label}[{index}] condition instance binding is invalid"
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
            *,
            record: bool = False,
        ) -> str:
            response_fields = {
                "operation",
                "target_id",
                "actor_id",
                "kind",
                "was_prone",
                "stood",
                "dropped_prone",
                "crawled",
                "distance_feet",
                "action_cost",
                "standing_cost_ft",
                "crawl_extra_cost_ft",
                "movement_cost_ft",
                "movement_budget_before_ft",
                "remaining_movement_ft",
                "prone_after",
                "reason",
            }
            record_fields = {
                "event_id",
                "event_sequence",
                "proposal_operation_sequence",
                "proposal_record_sha256",
                "movement_mode",
                "movement_authority",
                "area_response_operation",
                "ended_component_ids",
                "ended_condition_instance_ids",
                "active_conditions_after",
                "created_condition_instances",
                "fall_transition",
                "active_components_after",
            }
            require_exact_keys(
                row,
                response_fields | (record_fields if record else set()),
                label,
            )
            operation = row.get("operation")
            if not isinstance(operation, Mapping):
                raise ControlEngineError(f"{label}.operation must be an object")
            operation_kind = operation.get("kind")
            if operation_kind not in {
                "remain_prone",
                "stand",
                "drop_prone",
                "crawl",
            }:
                raise ControlEngineError(
                    f"{label}.operation.kind is unsupported"
                )
            operation_fields = {"kind", "actor_id", "target_id"}
            if operation_kind == "crawl":
                operation_fields.add("distance_feet")
            require_exact_keys(
                operation,
                operation_fields,
                f"{label}.operation",
            )
            if row.get("target_id") not in target_rank:
                raise ControlEngineError(
                    f"{label}.target_id is not part of the schedule"
                )
            if (
                row.get("actor_id") != row["target_id"]
                or operation.get("actor_id") != row["actor_id"]
                or operation.get("target_id") != row["target_id"]
                or row.get("kind")
                != ("prone_operation" if record else operation_kind)
                or row.get("reason") != operation_kind
            ):
                raise ControlEngineError(
                    f"{label} Prone operation identity is invalid"
                )
            integer_fields = (
                "distance_feet",
                "action_cost",
                "standing_cost_ft",
                "crawl_extra_cost_ft",
                "movement_cost_ft",
                "movement_budget_before_ft",
                "remaining_movement_ft",
            )
            if (
                not all(
                    isinstance(row.get(field_name), bool)
                    for field_name in (
                        "was_prone",
                        "stood",
                        "dropped_prone",
                        "crawled",
                        "prone_after",
                    )
                )
                or any(
                    isinstance(row.get(field_name), bool)
                    or not isinstance(row.get(field_name), int)
                    or row[field_name] < 0
                    for field_name in integer_fields
                )
            ):
                raise ControlEngineError(f"{label} prone response is invalid")
            distance = row["distance_feet"]
            standing_cost = row["standing_cost_ft"]
            crawl_extra = row["crawl_extra_cost_ft"]
            movement_cost = row["movement_cost_ft"]
            budget = row["movement_budget_before_ft"]
            if (
                row["action_cost"] != 0
                or movement_cost != standing_cost + (
                    distance + crawl_extra
                    if operation_kind == "crawl" else 0
                )
                or row["remaining_movement_ft"] != budget - movement_cost
                or movement_cost > budget
                or row["stood"] != (operation_kind == "stand")
                or row["dropped_prone"] != (operation_kind == "drop_prone")
                or row["crawled"] != (operation_kind == "crawl")
            ):
                raise ControlEngineError(
                    f"{label} Prone operation costs are inconsistent"
                )
            if operation_kind == "stand":
                valid_transition = (
                    row["was_prone"]
                    and not row["prone_after"]
                    and distance == 0
                    and crawl_extra == 0
                    and movement_cost == standing_cost
                )
            elif operation_kind == "drop_prone":
                valid_transition = (
                    not row["was_prone"]
                    and row["prone_after"]
                    and distance == 0
                    and standing_cost == 0
                    and crawl_extra == 0
                    and movement_cost == 0
                )
            elif operation_kind == "crawl":
                valid_transition = (
                    row["was_prone"]
                    and row["prone_after"]
                    and distance > 0
                    and operation.get("distance_feet") == distance
                    and standing_cost == 0
                    and crawl_extra in {distance, distance * 2}
                    and movement_cost == distance + crawl_extra
                )
            else:
                valid_transition = (
                    row["was_prone"]
                    and row["prone_after"]
                    and distance == 0
                    and standing_cost == 0
                    and crawl_extra == 0
                    and movement_cost == 0
                )
            if not valid_transition:
                raise ControlEngineError(
                    f"{label} Prone transition is impossible"
                )
            return str(operation_kind)

        def validate_response_shape(
            row: Mapping[str, Any],
            *,
            kind: str,
            label: str,
        ) -> None:
            if kind == "prone_operation":
                operation_kind = validate_prone_payload(
                    row,
                    label,
                    record=True,
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
                effective_speeds = row["movement_authority"][
                    "effective_speeds_ft"
                ]
                walking_speed = effective_speeds.get("walk")
                movement_denied = row["movement_mode"] in set(
                    row["movement_authority"]["denied_modes"]
                )
                if (
                    isinstance(walking_speed, bool)
                    or not isinstance(walking_speed, int)
                    or walking_speed < 0
                    or (
                        operation_kind == "stand"
                        and (
                            walking_speed == 0
                            or movement_denied
                            or row["standing_cost_ft"] != walking_speed // 2
                        )
                    )
                    or (
                        operation_kind == "crawl"
                        and (walking_speed == 0 or movement_denied)
                    )
                    or (
                        operation_kind == "drop_prone"
                        and walking_speed == 0
                    )
                ):
                    raise ControlEngineError(
                        f"{label} does not match exact walking-Speed authority"
                    )
                if (
                    isinstance(row["event_sequence"], bool)
                    or not isinstance(row["event_sequence"], int)
                    or row["event_sequence"] < 0
                    or not isinstance(row["area_response_operation"], bool)
                    or (
                        row["proposal_operation_sequence"] is None
                    ) != (row["proposal_record_sha256"] is None)
                ):
                    raise ControlEngineError(
                        f"{label} Prone record metadata is invalid"
                    )
                if row["proposal_operation_sequence"] is not None and (
                    isinstance(row["proposal_operation_sequence"], bool)
                    or not isinstance(row["proposal_operation_sequence"], int)
                    or row["proposal_operation_sequence"] < 1
                    or not isinstance(row["proposal_record_sha256"], str)
                    or len(row["proposal_record_sha256"]) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in row["proposal_record_sha256"]
                    )
                ):
                    raise ControlEngineError(
                        f"{label} Prone proposal identity is invalid"
                    )
                for field_name in (
                    "ended_component_ids",
                    "ended_condition_instance_ids",
                    "active_conditions_after",
                ):
                    validate_identifier_list(
                        row[field_name],
                        f"{label}.{field_name}",
                    )
                if (
                    ("prone" in row["active_conditions_after"])
                    != row["prone_after"]
                    or not isinstance(row["created_condition_instances"], list)
                    or any(
                        not isinstance(item, Mapping)
                        for item in row["created_condition_instances"]
                    )
                    or (
                        row["fall_transition"] is not None
                        and not isinstance(row["fall_transition"], Mapping)
                    )
                    or (
                        operation_kind == "drop_prone"
                        and not row["created_condition_instances"]
                    )
                    or (
                        operation_kind != "drop_prone"
                        and (
                            row["created_condition_instances"]
                            or row["fall_transition"] is not None
                        )
                    )
                ):
                    raise ControlEngineError(
                        f"{label} Prone condition-state result is invalid"
                    )
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
                optional_allowed = {
                    "blocked_routes",
                    "prone_after",
                    "prone_response",
                    "route_transition",
                }
                optional_fields = set(row) & optional_allowed
                require_exact_keys(row, base_fields | optional_fields, label)
                if "route_transition" in row and not isinstance(
                    row["route_transition"],
                    Mapping,
                ):
                    raise ControlEngineError(
                        f"{label}.route_transition must be an object"
                    )
                if (
                    reason not in {
                        "not_in_area",
                        "effect_ended",
                        "typed_target_exit",
                        "fixed_occupancy",
                        "movement_unavailable",
                        "shortest_legal_route",
                        "remain_prone",
                        "drop_prone",
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
                } or (
                    reason in {"remain_prone", "drop_prone"}
                    and row["convention"] == "shortest_route_v1"
                )
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
                    if prone_response is not None and not isinstance(
                        prone_response,
                        Mapping,
                    ):
                        raise ControlEngineError(
                            f"{label}.selected_route.prone_response is invalid"
                        )
                    if prone_response is not None:
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
                if "prone_response" in row:
                    prone_response = row["prone_response"]
                    if not isinstance(prone_response, Mapping):
                        raise ControlEngineError(
                            f"{label}.prone_response is invalid"
                        )
                    top_prone_kind = validate_prone_payload(
                        prone_response,
                        f"{label}.prone_response",
                    )
                else:
                    top_prone_kind = None
                route_prone_response = (
                    row["selected_route"].get("prone_response")
                    if isinstance(row["selected_route"], Mapping)
                    else None
                )
                top_prone_response = row.get("prone_response")
                if (
                    route_prone_response is not None
                    and top_prone_response != route_prone_response
                ):
                    raise ControlEngineError(
                        f"{label} Prone area payloads disagree"
                    )
                if top_prone_kind in {"stand", "crawl"} and (
                    reason != "shortest_legal_route"
                    or not isinstance(row["selected_route"], Mapping)
                    or route_prone_response != top_prone_response
                ):
                    raise ControlEngineError(
                        f"{label} route-dependent Prone operation has no usable route"
                    )
                if top_prone_kind in {"stand", "crawl"}:
                    area_speeds = row["movement_authority"][
                        "effective_speeds_ft"
                    ]
                    area_walking_speed = area_speeds.get("walk")
                    if (
                        isinstance(area_walking_speed, bool)
                        or not isinstance(area_walking_speed, int)
                        or area_walking_speed <= 0
                    ):
                        raise ControlEngineError(
                            f"{label} has no explicit positive walking Speed"
                        )
                    if (
                        top_prone_kind == "stand"
                        and top_prone_response["standing_cost_ft"]
                        != area_walking_speed // 2
                    ):
                        raise ControlEngineError(
                            f"{label} standing cost does not match walking Speed"
                        )
                    if top_prone_kind == "crawl":
                        multiplier_record = row["selected_route"][
                            "movement_cost_multiplier_exact"
                        ]
                        route_multiplier = Fraction(
                            multiplier_record["numerator"],
                            multiplier_record["denominator"],
                        )
                        crawl_distance = top_prone_response["distance_feet"]
                        expected_extra = crawl_distance * (
                            2 if route_multiplier == 2 else 1
                        )
                        if (
                            route_multiplier not in {Fraction(1), Fraction(2)}
                            or top_prone_response["crawl_extra_cost_ft"]
                            != expected_extra
                        ):
                            raise ControlEngineError(
                                f"{label} crawl cost does not match route terrain"
                            )
                if top_prone_kind in {"remain_prone", "drop_prone"} and (
                    reason != top_prone_kind
                    or row["selected_route"] is not None
                ):
                    raise ControlEngineError(
                        f"{label} route-free Prone operation has invalid area semantics"
                    )
                if reason in {"remain_prone", "drop_prone"} and (
                    not isinstance(top_prone_response, Mapping)
                    or top_prone_kind != reason
                    or top_prone_response.get("reason") != reason
                    or row.get("prone_after")
                    != top_prone_response.get("prone_after")
                ):
                    raise ControlEngineError(
                        f"{label} explicit Prone area response is invalid"
                    )
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
            if operation == "prone_operation":
                expected = {
                    "operation": operation,
                    "prone_operation": row["operation"],
                    **{
                        field_name: value
                        for field_name, value in row.items()
                        if field_name != "operation"
                    },
                }
            else:
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
                if kind == "prone_operation":
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
                    if kind == "prone_operation"
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
                        "prone_operation"
                        if kind == "prone_operation"
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
            kind="prone_operation",
            label="prone_records",
        )
        concentration_end_fields = {
            "kind",
            "event_id",
            "effect_id",
            "owner_actor_id",
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
        concentration_owner_actor_id: str | None = None

        def validate_concentration_owner(value: Any, label: str) -> None:
            nonlocal concentration_owner_actor_id
            if (
                not isinstance(value, str)
                or not value
                or value.strip() != value
            ):
                raise ControlEngineError(f"{label} is invalid")
            if concentration_owner_actor_id is None:
                concentration_owner_actor_id = value
            elif value != concentration_owner_actor_id:
                raise ControlEngineError(
                    f"{label} does not match the exact concentration owner"
                )

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
                    "owner_actor_id",
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
            validate_concentration_owner(
                row["owner_actor_id"],
                f"{label}.owner_actor_id",
            )

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
                    "owner_actor_id",
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
            validate_concentration_owner(
                row["owner_actor_id"],
                f"{label}.owner_actor_id",
            )
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
            validate_concentration_owner(
                row["owner_actor_id"],
                f"{label}.owner_actor_id",
            )
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
            elif (
                reason != "controller_incapacitated"
                and event.kind != "concentration_end"
            ):
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
                            "owner_actor_id",
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
        return _construct_control_engine_result(
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
            prone_operation_records=tuple(validated_prone_records),
            concentration_records=tuple(validated_concentration_records),
            displacement_epoch_records=tuple(displacement_epoch_records),
            final_normalized_state=state.final_normalized_state(
                self.catalog
            ),
            explored_state_count=reliability.final_world_count,
        )


_MISSING = object()
_SESSION_RECORD_KINDS = frozenset({
    "action_legality",
    "area_entry",
    "area_geometry_update",
    "area_route_transition",
    "area_response",
    "branch_transition",
    "condition_application",
    "condition_application_proposal",
    "condition_end",
    "component_expiry",
    "concentration_check",
    "concentration_check_pending_end",
    "concentration_duration_reconciliation",
    "concentration_end",
    "concentration_start",
    "displacement",
    "displacement_epoch_boundary",
    "normalization",
    "opportunity_roll",
    "prone_operation",
    "prone_operation_proposal",
    "condition_concentration_end",
    "fall_transition",
})


class ControlExecutionSession:
    """One immutable scenario and one monotonic chronological execution.

    Mutable control state is intentionally not exposed.  Callers advance the
    schedule, execute legal operations at the current event, close that event,
    and finally ask the session to issue a result.  Every returned operation
    record is opaque and is accepted only by the session that created it.
    """

    @staticmethod
    def _compiled_area_gate_bindings(
        program: CompiledEffect,
        component_area_bindings: Mapping[str, tuple[str, ...]],
    ) -> dict[str, tuple[str, ...]]:
        """Derive gates whose structured authority depends on area membership."""

        persistent_selector_area_ids = {
            selector.selector_id: selector.area.area_id
            for selector in program.selectors
            if selector.area is not None and selector.area.persistent
        }
        compiled_areas = {
            selector.area.area_id: selector.area
            for selector in program.selectors
            if selector.area is not None and selector.area.persistent
        }
        result: dict[str, tuple[str, ...]] = {}
        for gate in program.gates:
            area_ids: set[str] = set()
            area_selector_ids = {
                persistent_selector_area_ids[selector_id]
                for selector_id in gate.selector_ids
                if selector_id in persistent_selector_area_ids
            }
            recurring_area_gate = bool(
                gate.role == "recurring"
                or (
                    gate.trigger.kind == "turn"
                    and gate.trigger.owner == "target"
                    and gate.trigger.turn_anchor == "start"
                )
            )
            if gate.trigger.kind == "entry" or recurring_area_gate:
                area_ids.update(area_selector_ids)
            for component_id in gate.requires_active_component_ids:
                area_ids.update(
                    area_id
                    for area_id in component_area_bindings.get(component_id, ())
                    if area_id in compiled_areas
                )
            if gate.trigger.kind == "entry" and not area_ids:
                area_ids.update(
                    area_id
                    for area_id, area in compiled_areas.items()
                    if gate.trigger.key in {
                        trigger.key for trigger in area.triggers
                    }
                )
            if area_ids:
                result[gate.gate_id] = tuple(sorted(area_ids))
        return result

    def __init__(
        self,
        engine: ControlEngine,
        *,
        effect: CompiledEffect | str,
        targets: Sequence[ReliabilityTarget],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        schedule: TimelineSchedule,
        target_mechanics: Mapping[str, Mapping[str, Any]],
        area_response_convention: str,
        displacement_function_id: str,
        kernel: ProbabilityKernel | None,
        probability_context: ProbabilityContext,
        choices: Mapping[str, str] | None,
        reliability_events: Sequence[ReliabilityEvent],
        candidate_component_ids: Iterable[str] | None,
        include_initial: bool,
        source_actor_id: str,
        invocation_id: str,
        operation_inputs_by_event: Mapping[str, Mapping[str, Any]] | None,
        area_geometry_updates: Sequence[AreaGeometryUpdate],
        area_entry_transitions: Sequence[AreaEntryTransition],
        concentration_save_bonus: int | None,
    ) -> None:
        if not isinstance(engine, ControlEngine):
            raise TypeError("engine must be ControlEngine")
        if not isinstance(schedule, TimelineSchedule):
            raise TypeError("schedule must be TimelineSchedule")
        if not isinstance(selector_context, SelectorContext):
            raise TypeError("selector_context must be SelectorContext")
        if not isinstance(probability_context, ProbabilityContext):
            raise TypeError("probability_context must be ProbabilityContext")
        if not isinstance(include_initial, bool):
            raise ControlEngineError("include_initial must be boolean")
        if (
            schedule.convention not in engine.config.initiative_schedules
            or isinstance(schedule.rounds, bool)
            or not isinstance(schedule.rounds, int)
            or schedule.rounds != engine.config.horizon_rounds
            or not schedule.target_ids
            or len(schedule.target_ids) != len(set(schedule.target_ids))
            or any(
                not isinstance(target_id, str)
                or not target_id
                or target_id.strip() != target_id
                for target_id in schedule.target_ids
            )
            or not schedule.events
            or any(
                not isinstance(event, TimelineEvent)
                for event in schedule.events
            )
            or tuple(event.sequence for event in schedule.events)
            != tuple(range(len(schedule.events)))
        ):
            raise ControlEngineError(
                "Timeline schedule shape, convention, horizon, or sequence is invalid"
            )
        event_ids = tuple(event.event_id for event in schedule.events)
        window_ids = tuple(
            event.window_id for event in schedule.events
            if event.window_id is not None
        )
        if (
            len(event_ids) != len(set(event_ids))
            or len(window_ids) != len(set(window_ids))
            or any(
                isinstance(event.sequence, bool)
                or not isinstance(event.sequence, int)
                or isinstance(event.round, bool)
                or not isinstance(event.round, int)
                or event.round < 1
                or event.round > schedule.rounds
                or event.kind not in _SESSION_TIMELINE_EVENT_KINDS
                or not isinstance(event.payload, Mapping)
                or (
                    event.kind in {
                        "action_proposal",
                        "attack_opportunity",
                        "controller_attack_opportunity",
                        "initiative_opportunity",
                        "reaction_window",
                        "save_opportunity",
                    }
                    and event.window_id is None
                )
                or (
                    event.kind == "reaction_window"
                    and event.payload.get("availability_interval") is True
                    and not (
                        event.turn_owner == "target"
                        and event.target_id is not None
                        and event.event_id
                        == (
                            f"r{event.round}:target:{event.target_id}:"
                            "reaction_window"
                        )
                    )
                )
                or not isinstance(event.event_id, str)
                or not event.event_id
                or event.event_id.strip() != event.event_id
                or any(
                    value is not None
                    and (
                        not isinstance(value, str)
                        or not value
                        or value.strip() != value
                    )
                    for value in (
                        event.turn_id,
                        event.turn_owner,
                        event.actor_id,
                        event.target_id,
                        event.window_id,
                        event.reaction_interval_id,
                    )
                )
                or (
                    event.target_id is not None
                    and event.target_id not in schedule.target_ids
                )
                for event in schedule.events
            )
        ):
            raise ControlEngineError(
                "Timeline schedule event identities or ownership are invalid"
            )
        for event in schedule.events:
            if event.kind in {"round_start", "round_end"}:
                suffix = "start" if event.kind == "round_start" else "end"
                expected_payload = (
                    {"previous_round": event.round - 1 or None}
                    if event.kind == "round_start"
                    else {
                        "next_round": (
                            event.round + 1
                            if event.round < schedule.rounds
                            else None
                        )
                    }
                )
                if (
                    event.event_id != f"r{event.round}:round:{suffix}"
                    or event.turn_id is not None
                    or event.turn_owner is not None
                    or event.actor_id is not None
                    or event.target_id is not None
                    or event.window_id is not None
                    or event.reaction_interval_id is not None
                    or dict(event.payload) != expected_payload
                ):
                    raise ControlEngineError(
                        "Timeline round boundary identity is invalid"
                    )
            elif event.kind in {
                "controller_turn_start",
                "controller_turn_end",
            }:
                suffix = (
                    "start"
                    if event.kind == "controller_turn_start"
                    else "end"
                )
                expected_turn_id = f"r{event.round}:controller:turn"
                if (
                    event.event_id != f"{expected_turn_id}:{suffix}"
                    or event.turn_id != expected_turn_id
                    or event.turn_owner != "controller"
                    or event.actor_id != "controller"
                    or event.target_id is not None
                    or event.window_id is not None
                    or event.reaction_interval_id is not None
                    or dict(event.payload)
                ):
                    raise ControlEngineError(
                        "Timeline controller boundary identity is invalid"
                    )
            elif event.kind in {
                "target_turn_start",
                "target_movement_opportunity",
                "target_active_turn_opportunity",
                "target_attack_opportunity",
                "target_turn_end",
            }:
                target_id = event.target_id
                if target_id is None:
                    raise ControlEngineError(
                        "Timeline target structural event is missing target identity"
                    )
                expected_turn_id = (
                    f"r{event.round}:target:{target_id}:turn"
                )
                expected_reaction_id = (
                    f"r{event.round}:target:{target_id}:reaction_interval"
                )
                expected_event_id: str
                expected_window_id: str | None
                expected_payload: dict[str, Any]
                if event.kind == "target_turn_start":
                    expected_event_id = f"{expected_turn_id}:start"
                    expected_window_id = None
                    expected_payload = {}
                elif event.kind == "target_movement_opportunity":
                    expected_event_id = f"{expected_turn_id}:movement"
                    expected_window_id = f"{expected_event_id}:window"
                    expected_payload = {}
                elif event.kind == "target_active_turn_opportunity":
                    expected_event_id = f"{expected_turn_id}:active_turn"
                    expected_window_id = f"{expected_event_id}:window"
                    expected_payload = {}
                elif event.kind == "target_turn_end":
                    expected_event_id = f"{expected_turn_id}:end"
                    expected_window_id = None
                    expected_payload = {}
                else:
                    attack_index = event.payload.get("attack_index")
                    if (
                        isinstance(attack_index, bool)
                        or not isinstance(attack_index, int)
                        or attack_index < 1
                    ):
                        raise ControlEngineError(
                            "Timeline target attack index is invalid"
                        )
                    expected_event_id = (
                        f"{expected_turn_id}:attack:{attack_index:03d}"
                    )
                    expected_window_id = f"{expected_event_id}:window"
                    expected_payload = {"attack_index": attack_index}
                if (
                    event.event_id != expected_event_id
                    or event.turn_id != expected_turn_id
                    or event.turn_owner != "target"
                    or event.actor_id != target_id
                    or event.window_id != expected_window_id
                    or event.reaction_interval_id != expected_reaction_id
                    or dict(event.payload) != expected_payload
                ):
                    raise ControlEngineError(
                        "Timeline target structural event identity is invalid"
                    )
        if any(
            not isinstance(interval, ReactionInterval)
            for interval in schedule.reaction_intervals
        ):
            raise ControlEngineError(
                "Timeline schedule reaction intervals must be typed"
            )
        for round_number in range(1, schedule.rounds + 1):
            round_starts = [
                event for event in schedule.events
                if event.round == round_number and event.kind == "round_start"
            ]
            round_ends = [
                event for event in schedule.events
                if event.round == round_number and event.kind == "round_end"
            ]
            controller_starts = [
                event for event in schedule.events
                if event.round == round_number
                and event.kind == "controller_turn_start"
            ]
            controller_ends = [
                event for event in schedule.events
                if event.round == round_number
                and event.kind == "controller_turn_end"
            ]
            if (
                len(round_starts) != 1
                or len(round_ends) != 1
                or len(controller_starts) != 1
                or len(controller_ends) != 1
            ):
                raise ControlEngineError(
                    "Timeline schedule must contain one round and controller turn block"
                )
            round_start = round_starts[0]
            round_end = round_ends[0]
            controller_start = controller_starts[0]
            controller_end = controller_ends[0]
            expected_round_start_sequence = (
                0
                if round_number == 1
                else next(
                    event.sequence
                    for event in schedule.events
                    if event.round == round_number - 1
                    and event.kind == "round_end"
                ) + 1
            )
            round_sequences = tuple(
                event.sequence
                for event in schedule.events
                if event.round == round_number
            )
            if (
                not (
                    round_start.sequence
                    < controller_start.sequence
                    < controller_end.sequence
                    < round_end.sequence
                )
                or round_start.sequence != expected_round_start_sequence
                or round_sequences != tuple(range(
                    round_start.sequence,
                    round_end.sequence + 1,
                ))
                or (
                    round_number == schedule.rounds
                    and round_end.sequence != len(schedule.events) - 1
                )
                or controller_start.turn_id != controller_end.turn_id
                or controller_start.turn_owner != "controller"
                or controller_end.turn_owner != "controller"
                or controller_start.actor_id != "controller"
                or controller_end.actor_id != "controller"
            ):
                raise ControlEngineError(
                    "Timeline controller turn order is invalid"
                )
            controller_block = schedule.events[
                controller_start.sequence:controller_end.sequence + 1
            ]
            if any(
                event.round != round_number
                or event.turn_id != controller_start.turn_id
                or event.turn_owner != "controller"
                or event.actor_id != "controller"
                or (
                    event.kind in _SESSION_STRUCTURAL_EVENT_KINDS
                    and event.kind not in {
                        "controller_turn_start",
                        "controller_turn_end",
                    }
                )
                or (
                    event.kind == "reaction_window"
                    and event.reaction_interval_id is None
                )
                or (
                    event.kind != "reaction_window"
                    and event.reaction_interval_id is not None
                )
                for event in controller_block
            ):
                raise ControlEngineError(
                    "Timeline controller turn contains a foreign-owned event"
                )
            prior_target_end = round_start.sequence
            target_boundaries: dict[str, tuple[TimelineEvent, TimelineEvent]] = {}
            for target_id in schedule.target_ids:
                target_events = [
                    event for event in schedule.events
                    if event.round == round_number
                    and event.target_id == target_id
                ]
                starts = [
                    event for event in target_events
                    if event.kind == "target_turn_start"
                ]
                movements = [
                    event for event in target_events
                    if event.kind == "target_movement_opportunity"
                ]
                active_turns = [
                    event for event in target_events
                    if event.kind == "target_active_turn_opportunity"
                ]
                attacks = [
                    event for event in target_events
                    if event.kind == "target_attack_opportunity"
                ]
                ends = [
                    event for event in target_events
                    if event.kind == "target_turn_end"
                ]
                if not all(
                    len(rows) == 1
                    for rows in (starts, movements, active_turns, ends)
                ):
                    raise ControlEngineError(
                        "Timeline schedule must contain one complete target turn "
                        "per target and round"
                    )
                start, movement, active_turn, end = (
                    starts[0],
                    movements[0],
                    active_turns[0],
                    ends[0],
                )
                target_boundaries[target_id] = (start, end)
                target_block = schedule.events[
                    start.sequence:end.sequence + 1
                ]
                reaction_openings = [
                    event for event in target_block
                    if event.kind == "reaction_window"
                    and event.payload.get("availability_interval") is True
                ]
                target_intervals = [
                    interval for interval in schedule.reaction_intervals
                    if interval.target_id == target_id
                    and interval.round == round_number
                    and not interval.horizon_entry_partial
                ]
                expected_interval_end_id = (
                    next(
                        event.event_id
                        for event in schedule.events
                        if event.kind == "target_turn_start"
                        and event.target_id == target_id
                        and event.round == round_number + 1
                    )
                    if round_number < schedule.rounds
                    else round_end.event_id
                )
                if not (
                    round_start.sequence < start.sequence
                    < movement.sequence < active_turn.sequence < end.sequence
                    < round_end.sequence
                    and all(
                        active_turn.sequence < attack.sequence < end.sequence
                        for attack in attacks
                    )
                    and (
                        not attacks or max(
                            attack.sequence for attack in attacks
                        ) < end.sequence
                    )
                    and start.sequence > prior_target_end
                    and len(reaction_openings) == 1
                    and len(target_intervals) == 1
                    and reaction_openings[0].sequence == start.sequence + 1
                    and reaction_openings[0].event_id
                    == f"r{round_number}:target:{target_id}:reaction_window"
                    and reaction_openings[0].window_id
                    == reaction_openings[0].event_id
                    and dict(reaction_openings[0].payload)
                    == {"availability_interval": True}
                    and start.reaction_interval_id
                    == target_intervals[0].interval_id
                    and target_intervals[0].start_event_id == start.event_id
                    and target_intervals[0].end_before_event_id
                    == expected_interval_end_id
                    and target_intervals[0].window_id
                    == reaction_openings[0].window_id
                    and target_intervals[0].initially_available is True
                    and [
                        attack.payload.get("attack_index")
                        for attack in sorted(attacks, key=lambda row: row.sequence)
                    ] == list(range(1, len(attacks) + 1))
                    and [
                        attack.sequence
                        for attack in sorted(attacks, key=lambda row: row.sequence)
                    ] == list(range(
                        active_turn.sequence + 1,
                        active_turn.sequence + 1 + len(attacks),
                    ))
                    and all(
                        event.turn_id == start.turn_id
                        and event.turn_owner == "target"
                        and event.actor_id == target_id
                        and event.target_id == target_id
                        and event.reaction_interval_id
                        == start.reaction_interval_id
                        for event in (
                            start,
                            reaction_openings[0],
                            movement,
                            active_turn,
                            *attacks,
                            end,
                        )
                    )
                    and all(
                        event.round == round_number
                        and event.turn_id == start.turn_id
                        and event.turn_owner == "target"
                        and event.actor_id == target_id
                        and event.target_id == target_id
                        and event.reaction_interval_id
                        == start.reaction_interval_id
                        for event in target_block
                    )
                ):
                    raise ControlEngineError(
                        "Timeline target turn must order movement before active "
                        "turn and attacks"
                    )
                prior_target_end = end.sequence
                if schedule.convention == "fighter_first_v1" and not (
                    controller_end.sequence < start.sequence
                ):
                    raise ControlEngineError(
                        "fighter_first_v1 schedule order is invalid"
                    )
                if schedule.convention == "target_before_fighter_v1" and not (
                    end.sequence < controller_start.sequence
                ):
                    raise ControlEngineError(
                        "target_before_fighter_v1 schedule order is invalid"
                    )
            ordered_blocks = (
                [(controller_start, controller_end)]
                + [
                    target_boundaries[target_id]
                    for target_id in schedule.target_ids
                ]
                if schedule.convention == "fighter_first_v1"
                else [
                    target_boundaries[target_id]
                    for target_id in schedule.target_ids
                ] + [(controller_start, controller_end)]
            )
            expected_block_start = round_start.sequence + 1
            for block_start, block_end in ordered_blocks:
                if block_start.sequence != expected_block_start:
                    raise ControlEngineError(
                        "Timeline turn blocks must be ordered and noninterleaved"
                    )
                expected_block_start = block_end.sequence + 1
            if round_end.sequence != expected_block_start:
                raise ControlEngineError(
                    "Timeline round contains an event outside its owning turn"
                )
        interval_ids = tuple(
            interval.interval_id for interval in schedule.reaction_intervals
        )
        intervals_by_id = {
            interval.interval_id: interval
            for interval in schedule.reaction_intervals
        }
        events_by_id = {event.event_id: event for event in schedule.events}
        if (
            len(interval_ids) != len(set(interval_ids))
            or any(
                not isinstance(interval.interval_id, str)
                or not interval.interval_id
                or interval.interval_id.strip() != interval.interval_id
                or (
                    interval.window_id is not None
                    and (
                        not isinstance(interval.window_id, str)
                        or not interval.window_id
                        or interval.window_id.strip() != interval.window_id
                    )
                )
                or not isinstance(interval.target_id, str)
                or not interval.target_id
                or interval.target_id.strip() != interval.target_id
                or isinstance(interval.round, bool)
                or not isinstance(interval.round, int)
                or not isinstance(interval.start_event_id, str)
                or not interval.start_event_id
                or interval.start_event_id.strip() != interval.start_event_id
                or not isinstance(interval.end_before_event_id, str)
                or not interval.end_before_event_id
                or interval.end_before_event_id.strip()
                != interval.end_before_event_id
                or (
                    interval.initially_available is not None
                    and not isinstance(interval.initially_available, bool)
                )
                or not isinstance(interval.horizon_entry_partial, bool)
                or interval.target_id not in schedule.target_ids
                or interval.round < 1
                or interval.round > schedule.rounds
                or interval.start_event_id not in events_by_id
                or interval.end_before_event_id not in events_by_id
                or events_by_id[interval.start_event_id].sequence
                >= events_by_id[interval.end_before_event_id].sequence
                for interval in schedule.reaction_intervals
            )
            or any(
                event.reaction_interval_id is not None
                and (
                    event.reaction_interval_id not in intervals_by_id
                    or (
                        event.target_id is not None
                        and intervals_by_id[event.reaction_interval_id].target_id
                        != event.target_id
                    )
                    or (
                        event.reaction_interval_id in intervals_by_id
                        and not (
                            events_by_id[
                                intervals_by_id[
                                    event.reaction_interval_id
                                ].start_event_id
                            ].sequence
                            <= event.sequence
                            < events_by_id[
                                intervals_by_id[
                                    event.reaction_interval_id
                                ].end_before_event_id
                            ].sequence
                        )
                    )
                    or (
                        event.kind == "reaction_window"
                        and event.reaction_interval_id in intervals_by_id
                        and intervals_by_id[
                            event.reaction_interval_id
                        ].initially_available is None
                    )
                )
                for event in schedule.events
            )
        ):
            raise ControlEngineError(
                "Timeline schedule reaction ownership is invalid"
            )
        horizon_intervals = [
            interval for interval in schedule.reaction_intervals
            if interval.horizon_entry_partial
        ]
        first_round_start = next(
            event for event in schedule.events
            if event.kind == "round_start" and event.round == 1
        )
        if (
            len(horizon_intervals) != len(schedule.target_ids)
            or {interval.target_id for interval in horizon_intervals}
            != set(schedule.target_ids)
            or any(
                interval.round != 1
                or interval.window_id is not None
                or (
                    interval.initially_available is not None
                    and not isinstance(interval.initially_available, bool)
                )
                or interval.start_event_id != first_round_start.event_id
                or interval.end_before_event_id
                != next(
                    event.event_id
                    for event in schedule.events
                    if event.kind == "target_turn_start"
                    and event.round == 1
                    and event.target_id == interval.target_id
                )
                for interval in horizon_intervals
            )
            or (
                any(
                    interval.initially_available is None
                    for interval in horizon_intervals
                )
                and any(
                    isinstance(interval.initially_available, bool)
                    for interval in horizon_intervals
                )
            )
        ):
            raise ControlEngineError(
                "Timeline schedule horizon reaction ownership is invalid"
            )
        schedule_record = _strict_json_copy(
            schedule.to_dict(),
            "timeline_schedule",
        )

        program = engine._canonical_effect(effect)
        target_rows = tuple(targets)
        if any(not isinstance(target, ReliabilityTarget) for target in target_rows):
            raise TypeError("targets must contain ReliabilityTarget values")
        target_ids = tuple(target.target_id for target in target_rows)
        if len(target_ids) != len(set(target_ids)):
            raise ControlEngineError("targets must contain unique target IDs")
        if set(target_ids) != set(schedule.target_ids):
            raise ControlEngineError(
                "Reliability targets and schedule targets must contain the same identities"
            )
        targets_by_id = {target.target_id: target for target in target_rows}

        membership = engine._validated_selector_membership(
            program,
            selector_membership,
            schedule,
            selector_context,
        )
        bindings = dict(program.bind_choices(choices))
        engine.version_provenance(
            initiative_convention=schedule.convention,
            area_response_convention=area_response_convention,
            displacement_function_id=displacement_function_id,
        )

        if not isinstance(target_mechanics, Mapping):
            raise ControlEngineError("target_mechanics must be an object")
        _require_string_mapping_keys(target_mechanics, "target_mechanics")
        if set(target_mechanics) != set(schedule.target_ids):
            raise ControlEngineError(
                "target_mechanics must cover every schedule target exactly once"
            )
        safe_target_mechanics: dict[str, dict[str, Any]] = {}
        for target_id in schedule.target_ids:
            value = target_mechanics[target_id]
            if not isinstance(value, Mapping):
                raise ControlEngineError(
                    f"target_mechanics.{target_id} must be an object"
                )
            safe = _strict_json_copy(value, f"target_mechanics.{target_id}")
            if not isinstance(safe, dict):  # pragma: no cover - mapping conversion
                raise ControlEngineError(
                    f"target_mechanics.{target_id} must be an object"
                )
            safe_target_mechanics[target_id] = safe

        compiled_areas = {
            selector.area.area_id: selector.area
            for selector in program.selectors
            if selector.area is not None
        }
        if len(compiled_areas) > 1:
            raise ControlEngineError(
                "Execution sessions do not support programs with multiple "
                f"compiled areas: {sorted(compiled_areas)}"
            )
        area_selector_ids_by_area = {
            area_id: tuple(sorted(
                selector.selector_id
                for selector in program.selectors
                if selector.area is not None
                and selector.area.area_id == area_id
            ))
            for area_id in compiled_areas
        }
        area_target_ids_by_area = {
            area_id: tuple(sorted({
                target_id
                for selector_id in selector_ids
                for target_id in membership[selector_id]
            }))
            for area_id, selector_ids in area_selector_ids_by_area.items()
        }
        component_area_bindings = engine._compiled_area_bindings(program)
        area_gate_bindings = self._compiled_area_gate_bindings(
            program,
            component_area_bindings,
        )
        initial_area_route_states: list[_AreaRouteState] = []
        if len(compiled_areas) == 1:
            area_id = next(iter(compiled_areas))
            area_targets = set(area_target_ids_by_area[area_id])
            forbidden_target_overrides = {
                "area_routes_by_event",
                "area_membership_by_event",
                "movement_mode_by_event",
                "environment_by_event",
                "route_compatibility_by_event",
                "movement_cost_multiplier_by_event",
                "distance_to_exit_ft_by_event",
                "was_member",
                "was_member_by_event",
                "is_member",
                "is_member_by_event",
                "prior_trigger_turn_ids",
                "prior_trigger_turn_ids_by_event",
                "caused_by_area_movement",
                "caused_by_area_movement_by_event",
            }
            for target_id in schedule.target_ids:
                mechanics = safe_target_mechanics[target_id]
                forbidden = sorted(set(mechanics) & forbidden_target_overrides)
                if forbidden:
                    raise ControlEngineError(
                        f"target_mechanics.{target_id} contains raw route or "
                        f"caller-authored area-entry overrides: {forbidden}"
                    )
                if target_id not in area_targets:
                    continue
                member = mechanics.get(
                    "area_membership",
                    True if area_response_convention == "fixed_occupancy_v1" else None,
                )
                if not isinstance(member, bool):
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_membership must be boolean"
                    )
                raw_routes = mechanics.get("area_routes", ())
                if (
                    not isinstance(raw_routes, Sequence)
                    or isinstance(raw_routes, (str, bytes))
                ):
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes must be an array"
                    )
                try:
                    routes = tuple(
                        AreaRouteGeometry.from_mapping(
                            route,
                            f"target_mechanics.{target_id}.area_routes[{index}]",
                        )
                        for index, route in enumerate(raw_routes)
                    )
                except ControlEngineError as error:
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes are invalid: "
                        f"{error}"
                    ) from error
                route_ids = tuple(route.route_id for route in routes)
                if len(route_ids) != len(set(route_ids)):
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes contains duplicate "
                        "route IDs"
                    )
                if (
                    area_response_convention == "shortest_route_v1"
                    and member
                    and not routes
                ):
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes must be non-empty"
                    )
                base_speeds = mechanics.get("base_speeds_ft")
                if area_response_convention == "shortest_route_v1" and member and (
                    not isinstance(base_speeds, Mapping)
                    or any(route.mode not in base_speeds for route in routes)
                ):
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.base_speeds_ft must cover "
                        "every initial area route mode"
                    )
                if not member and routes:
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes cannot be supplied "
                        "for a non-member"
                    )
                if area_response_convention == "fixed_occupancy_v1" and routes:
                    raise ControlEngineError(
                        f"target_mechanics.{target_id}.area_routes cannot be supplied "
                        "under fixed_occupancy_v1"
                    )
                initial_area_route_states.append(_AreaRouteState(
                    effect_id=program.effect_id,
                    area_id=area_id,
                    target_id=target_id,
                    membership=member,
                    routes=routes,
                    selected_route_id=None,
                    movement_mode=None,
                    environment=None,
                    remaining_distance_ft=None,
                    movement_cost_basis=None,
                    closed_reason=None if member else "initial_nonmember",
                    last_update_event_id="session_initial_area_geometry",
                    last_update_event_sequence=-1,
                ))

        raw_operation_inputs = (
            {} if operation_inputs_by_event is None else operation_inputs_by_event
        )
        if not isinstance(raw_operation_inputs, Mapping):
            raise ControlEngineError("operation_inputs_by_event must be an object")
        _require_string_mapping_keys(
            raw_operation_inputs,
            "operation_inputs_by_event",
        )
        known_event_ids = {event.event_id for event in schedule.events}
        unknown_input_events = sorted(set(raw_operation_inputs) - known_event_ids)
        if unknown_input_events:
            raise ControlEngineError(
                "operation_inputs_by_event references unknown schedule events: "
                f"{unknown_input_events}"
            )
        safe_operation_inputs: dict[str, dict[str, Any]] = {}
        for event_id, value in raw_operation_inputs.items():
            if not isinstance(value, Mapping):
                raise ControlEngineError(
                    f"operation_inputs_by_event.{event_id} must be an object"
                )
            safe_value = _strict_json_copy(
                value,
                f"operation_inputs_by_event.{event_id}",
            )
            if not isinstance(safe_value, dict):  # pragma: no cover
                raise ControlEngineError(
                    f"operation_inputs_by_event.{event_id} must be an object"
                )
            safe_operation_inputs[event_id] = safe_value

        legacy_entry_truth_keys = {
            "area_membership",
            "was_member",
            "was_member_by_event",
            "is_member",
            "is_member_by_event",
            "prior_trigger_turn_ids",
            "prior_trigger_turn_ids_by_event",
            "caused_by_area_movement",
            "caused_by_area_movement_by_event",
        }
        for event_id, inputs in safe_operation_inputs.items():
            legacy = sorted(set(inputs) & legacy_entry_truth_keys)
            if legacy:
                raise ControlEngineError(
                    f"operation_inputs_by_event.{event_id} contains caller-authored "
                    f"area-entry truth: {legacy}; use AreaEntryTransition"
                )

        if compiled_areas:
            forbidden_event_geometry = {
                "area_routes",
                "area_membership",
                "movement_mode",
                "environment",
                "compatible",
                "movement_cost_multiplier",
                "distance_to_exit_ft",
            }
            for event_id, inputs in safe_operation_inputs.items():
                forbidden = sorted(set(inputs) & forbidden_event_geometry)
                if forbidden:
                    raise ControlEngineError(
                        f"operation_inputs_by_event.{event_id} contains raw route "
                        f"overrides: {forbidden}; use AreaGeometryUpdate"
                    )

        if not isinstance(area_geometry_updates, Sequence) or isinstance(
            area_geometry_updates,
            (str, bytes),
        ):
            raise ControlEngineError("area_geometry_updates must be an array")
        bound_area_geometry_updates = tuple(area_geometry_updates)
        if any(
            not isinstance(update, AreaGeometryUpdate)
            for update in bound_area_geometry_updates
        ):
            raise ControlEngineError(
                "area_geometry_updates must contain AreaGeometryUpdate values"
            )
        if bound_area_geometry_updates and not compiled_areas:
            raise ControlEngineError(
                "AreaGeometryUpdate is invalid for a program with zero compiled areas"
            )
        update_identities: set[tuple[str, str, str, str]] = set()
        movement_events_by_turn: dict[tuple[str, str], str] = {}
        for update in bound_area_geometry_updates:
            if area_response_convention != "shortest_route_v1":
                raise ControlEngineError(
                    "AreaGeometryUpdate requires shortest_route_v1"
                )
            if update.effect_id != program.effect_id:
                raise ControlEngineError(
                    "AreaGeometryUpdate effect does not match the session program"
                )
            area = compiled_areas.get(update.area_id)
            if area is None or update.target_id not in targets_by_id:
                raise ControlEngineError(
                    "AreaGeometryUpdate references a foreign area or target"
                )
            event = schedule.event(update.event_id)
            if event.sequence != update.event_sequence:
                raise ControlEngineError(
                    "AreaGeometryUpdate event sequence is stale or malformed"
                )
            movement = None if area.movement is None else area.movement.to_dict()
            if (
                not area.persistent
                or not isinstance(movement, Mapping)
                or movement.get("kind") != "controller_reposition"
                or event.kind != "instantaneous_resolution"
                or event.turn_owner != "controller"
                or event.actor_id != "controller"
                or not typed_event_matches(event, movement.get("timing", {}))
            ):
                raise ControlEngineError(
                    "AreaGeometryUpdate is not bound to the compiled moving-area "
                    "authority and compatible controller event"
                )
            if not any(
                state.effect_id == update.effect_id
                and state.area_id == update.area_id
                and state.target_id == update.target_id
                for state in initial_area_route_states
            ):
                raise ControlEngineError(
                    "AreaGeometryUpdate target is not bound to the compiled area selector"
                )
            identity = (
                update.effect_id,
                update.area_id,
                update.target_id,
                update.event_id,
            )
            if identity in update_identities:
                raise ControlEngineError("AreaGeometryUpdate identity is duplicated")
            update_identities.add(identity)
            turn_key = (update.area_id, str(event.turn_id))
            prior_event_id = movement_events_by_turn.setdefault(
                turn_key,
                event.event_id,
            )
            if prior_event_id != event.event_id:
                raise ControlEngineError(
                    "A compiled area may move at most once per controller turn"
                )

        if not isinstance(area_entry_transitions, Sequence) or isinstance(
            area_entry_transitions,
            (str, bytes),
        ):
            raise ControlEngineError("area_entry_transitions must be an array")
        supplied_area_entry_transitions = tuple(area_entry_transitions)
        if any(
            not isinstance(transition, AreaEntryTransition)
            for transition in supplied_area_entry_transitions
        ):
            raise ControlEngineError(
                "area_entry_transitions must contain AreaEntryTransition values"
            )
        entry_identities: set[tuple[str, str, str, str]] = set()
        validated_area_entry_transitions: list[AreaEntryTransition] = []
        updates_by_identity = {
            (
                update.effect_id,
                update.area_id,
                update.target_id,
                update.event_id,
            ): update
            for update in bound_area_geometry_updates
        }
        for transition in supplied_area_entry_transitions:
            identity = (
                transition.effect_id,
                transition.area_id,
                transition.target_id,
                transition.event_id,
            )
            if identity in entry_identities:
                raise ControlEngineError("AreaEntryTransition identity is duplicated")
            entry_identities.add(identity)
            if transition.effect_id != program.effect_id:
                raise ControlEngineError(
                    "AreaEntryTransition effect does not match the session program"
                )
            area = compiled_areas.get(transition.area_id)
            if area is None or transition.target_id not in targets_by_id:
                raise ControlEngineError(
                    "AreaEntryTransition references a foreign area or target"
                )
            if (
                not area.persistent
                or transition.target_id
                not in area_target_ids_by_area[transition.area_id]
            ):
                raise ControlEngineError(
                    "AreaEntryTransition target is not bound to a compiled "
                    "persistent-area selector"
                )
            event = schedule.event(transition.event_id)
            if event.sequence != transition.event_sequence:
                raise ControlEngineError(
                    "AreaEntryTransition event sequence is stale or malformed"
                )
            if event.turn_id != transition.turn_id:
                raise ControlEngineError(
                    "AreaEntryTransition turn identity does not match its event"
                )
            policy = None if area.entry_policy is None else area.entry_policy.to_dict()
            if (
                not isinstance(policy, Mapping)
                or policy.get("frequency") not in {"once_per_turn", "unlimited"}
                or not isinstance(policy.get("moved_area_counts_as_entry"), bool)
                or transition.moved_area_counts_as_entry
                != policy["moved_area_counts_as_entry"]
            ):
                raise ControlEngineError(
                    "AreaEntryTransition does not match compiled entry policy"
                )
            if transition.cause == "area_movement":
                update = updates_by_identity.get(identity)
                if (
                    update is None
                    or not update.new_membership
                    or update.routes != transition.routes
                    or event.kind != "instantaneous_resolution"
                ):
                    raise ControlEngineError(
                        "Area-movement entry transition must exactly match a bound "
                        "false-to-true-capable AreaGeometryUpdate"
                    )
            elif (
                event.kind != "entry"
                or event.target_id != transition.target_id
                or identity in updates_by_identity
            ):
                raise ControlEngineError(
                    "Ordinary or forced AreaEntryTransition requires its exact "
                    "target-owned entry event"
                )
            mechanics = safe_target_mechanics[transition.target_id]
            if area_response_convention == "shortest_route_v1":
                base_speeds = mechanics.get("base_speeds_ft")
                if not isinstance(base_speeds, Mapping) or not base_speeds:
                    raise ControlEngineError(
                        "AreaEntryTransition under shortest_route_v1 requires "
                        "bound base_speeds_ft"
                    )
                available_modes = set(base_speeds)
                route_modes = {route.mode for route in transition.routes}
                compatible_modes = {
                    route.mode for route in transition.routes if route.compatible
                }
                if (
                    not transition.routes
                    or route_modes - available_modes
                    or available_modes - compatible_modes
                ):
                    raise ControlEngineError(
                        "AreaEntryTransition route geometry must cover every "
                        "available movement mode without adding an unbound mode"
                    )
            elif transition.routes:
                raise ControlEngineError(
                    "AreaEntryTransition under fixed_occupancy_v1 cannot create "
                    "nominal exit-route progress"
                )
            validated_area_entry_transitions.append(transition)

        for update in bound_area_geometry_updates:
            if not update.new_membership:
                continue
            identity = (
                update.effect_id,
                update.area_id,
                update.target_id,
                update.event_id,
            )
            if identity in entry_identities:
                continue
            area = compiled_areas[update.area_id]
            policy = None if area.entry_policy is None else area.entry_policy.to_dict()
            event = schedule.event(update.event_id)
            if not isinstance(policy, Mapping) or event.turn_id is None:
                raise ControlEngineError(
                    "AreaGeometryUpdate cannot derive a canonical area-entry transition"
                )
            if policy.get("moved_area_counts_as_entry") is True:
                # A policy-true movement requires an explicit transition only
                # when the scenario means to permit a false-to-true entry.  A
                # plain true-to-true geometry refresh is not an entry and must
                # not require a fictional reliability gate binding.
                continue
            base_speeds = safe_target_mechanics[update.target_id].get(
                "base_speeds_ft"
            )
            compatible_modes = {
                route.mode for route in update.routes if route.compatible
            }
            if (
                not isinstance(base_speeds, Mapping)
                or not base_speeds
                or {route.mode for route in update.routes} - set(base_speeds)
                or set(base_speeds) - compatible_modes
            ):
                raise ControlEngineError(
                    "AreaGeometryUpdate entry geometry must cover every "
                    "available movement mode without adding an unbound mode"
                )
            derived = AreaEntryTransition(
                effect_id=update.effect_id,
                area_id=update.area_id,
                target_id=update.target_id,
                event_id=update.event_id,
                event_sequence=update.event_sequence,
                cause="area_movement",
                turn_id=event.turn_id,
                routes=update.routes,
                moved_area_counts_as_entry=bool(
                    policy.get("moved_area_counts_as_entry")
                ),
            )
            entry_identities.add(identity)
            validated_area_entry_transitions.append(derived)
        bound_area_entry_transitions = tuple(validated_area_entry_transitions)

        if concentration_save_bonus is not None and (
            isinstance(concentration_save_bonus, bool)
            or not isinstance(concentration_save_bonus, int)
        ):
            raise ControlEngineError(
                "concentration_save_bonus must be an integer or null"
            )
        concentration = program.concentration.to_dict()
        concentration_required = concentration.get("kind") == "required"
        concentration_start_event_id: str | None = None
        if concentration_required:
            if concentration.get("startup") != "on_activation":
                raise ControlEngineError(
                    f"Effect {program.effect_id!r} has unsupported concentration startup"
                )
            if concentration_save_bonus is None:
                raise ControlEngineError(
                    f"Effect {program.effect_id!r} requires a bound "
                    "concentration_save_bonus"
                )
            activation_events = tuple(
                event for event in schedule.events if event.kind == "activation"
            )
            if len(activation_events) != 1:
                raise ControlEngineError(
                    f"Effect {program.effect_id!r} requires exactly one typed "
                    "activation event for concentration startup"
                )
            concentration_start_event_id = activation_events[0].event_id
            for event_id, inputs in safe_operation_inputs.items():
                declared = inputs.get("required_operations", ())
                if (
                    isinstance(declared, Sequence)
                    and not isinstance(declared, (str, bytes))
                    and "concentration_start" in declared
                    and event_id != concentration_start_event_id
                ):
                    raise ControlEngineError(
                        "concentration_start must be bound to the typed activation event"
                    )
        elif concentration_save_bonus is not None:
            raise ControlEngineError(
                f"Effect {program.effect_id!r} does not accept concentration inputs"
            )
        source_actor = _identifier(source_actor_id, "source_actor_id")
        invocation = _identifier(invocation_id, "invocation_id")
        initial_condition_instances_by_target: dict[
            str, tuple[dict[str, Any], ...]
        ] = {}
        initial_instance_ids: set[str] = set()
        for target_id in schedule.target_ids:
            mechanics = safe_target_mechanics[target_id]
            if "initial_conditions" in mechanics:
                raise ControlEngineError(
                    f"target_mechanics.{target_id}.initial_conditions was removed "
                    "by control_execution_session_v2; supply explicit "
                    "initial_condition_instances"
                )
            raw_instances = mechanics.get("initial_condition_instances", [])
            if not isinstance(raw_instances, list):
                raise ControlEngineError(
                    f"target_mechanics.{target_id}.initial_condition_instances "
                    "must be an array"
                )
            bound_instances: list[dict[str, Any]] = []
            required_fields = {
                "instance_id",
                "condition_id",
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
            }
            for index, raw_instance in enumerate(raw_instances):
                label = (
                    f"target_mechanics.{target_id}."
                    f"initial_condition_instances[{index}]"
                )
                if not isinstance(raw_instance, Mapping):
                    raise ControlEngineError(f"{label} must be an object")
                if set(raw_instance) != required_fields:
                    raise ControlEngineError(
                        f"{label} must contain exactly {sorted(required_fields)}"
                    )
                instance = _strict_json_copy(raw_instance, label)
                for field_name in (
                    "instance_id",
                    "condition_id",
                    "target_id",
                    "source_actor_id",
                    "source_program_id",
                    "source_effect_id",
                    "source_invocation_id",
                    "source_component_id",
                    "application_event_id",
                    "issuance_id",
                    "provenance_id",
                ):
                    _identifier(instance[field_name], f"{label}.{field_name}")
                condition = instance["condition_id"]
                if condition not in engine.catalog.conditions:
                    raise ControlEngineError(
                        f"Unknown initial condition {condition!r} for {target_id!r}"
                    )
                if instance["target_id"] != target_id:
                    raise ControlEngineError(
                        f"{label}.target_id must match its target_mechanics owner"
                    )
                if instance["instance_id"] in initial_instance_ids:
                    raise ControlEngineError(
                        "Initial condition instance IDs must be globally unique"
                    )
                initial_instance_ids.add(instance["instance_id"])
                if (
                    condition in {"charmed", "frightened"}
                    and instance["source_actor_id"] == target_id
                ):
                    raise ControlEngineError(
                        f"Initial {condition!r} requires an exact non-self source actor"
                    )
                if condition in targets_by_id[target_id].condition_immunities:
                    raise ControlEngineError(
                        f"Target {target_id!r} cannot start with immune condition "
                        f"{condition!r}"
                    )
                if (
                    instance["application_event_id"] != "session_initial_state"
                    or instance["application_sequence"] != -1
                ):
                    raise ControlEngineError(
                        f"{label} must bind session_initial_state at sequence -1"
                    )
                duration = instance["duration"]
                if (
                    not isinstance(duration, Mapping)
                    or not isinstance(duration.get("kind"), str)
                    or not duration["kind"]
                ):
                    raise ControlEngineError(
                        f"{label}.duration must be a typed duration object"
                    )
                expiry_event_id = instance["expiry_event_id"]
                if expiry_event_id is not None:
                    _identifier(expiry_event_id, f"{label}.expiry_event_id")
                    if expiry_event_id not in known_event_ids:
                        raise ControlEngineError(
                            f"{label}.expiry_event_id is not a schedule event"
                        )
                bound_instances.append(instance)
            initial_condition_instances_by_target[target_id] = tuple(
                bound_instances
            )
        initial_control_state = ControlState(catalog=engine.catalog)
        for target_id in schedule.target_ids:
            for instance in initial_condition_instances_by_target[target_id]:
                applied = initial_control_state.apply_component(
                    effect_id=instance["source_effect_id"],
                    component={
                        "component_id": instance["source_component_id"],
                        "magnitude": {
                            "kind": "condition",
                            "condition": instance["condition_id"],
                        },
                        "duration": instance["duration"],
                        "stacking": {
                            "key": f"condition_instance:{instance['instance_id']}",
                            "mode": "independent",
                            "refresh": "none",
                        },
                    },
                    target_id=target_id,
                    source_actor_id=instance["source_actor_id"],
                    event_id=instance["application_event_id"],
                    invocation_id=instance["source_invocation_id"],
                    expiry_event_id=instance["expiry_event_id"],
                    condition_immunities=(
                        targets_by_id[target_id].condition_immunities
                    ),
                    application_sequence=instance["application_sequence"],
                    condition_instance_id=instance["instance_id"],
                    source_program_id=instance["source_program_id"],
                    issuance_id=instance["issuance_id"],
                    provenance_id=instance["provenance_id"],
                )
                if applied is None:  # pragma: no cover - immunity preflight above
                    raise ControlEngineError(
                        "Initial condition instance was unexpectedly suppressed"
                    )
        initial_state_rows = initial_control_state.snapshot()
        initial_condition_registry_rows = initial_control_state.instance_registry()
        chosen_kernel = D20ProbabilityKernel() if kernel is None else kernel
        if getattr(getattr(chosen_kernel, "identity", None), "test_only", False):
            raise ControlEngineError(
                "Public execution sessions reject test-only probability kernels"
            )
        mechanical_candidates = engine.candidate_component_ids(program)
        candidates = (
            mechanical_candidates
            if candidate_component_ids is None
            else tuple(candidate_component_ids)
        )
        reliability = engine.reliability(
            program,
            targets=target_rows,
            selector_membership=membership,
            selector_context=selector_context,
            kernel=chosen_kernel,
            context=probability_context,
            choices=bindings,
            events=reliability_events,
            candidate_component_ids=candidates,
            include_initial=include_initial,
        )
        if reliability.scenario is None or reliability.scenario_digest is None:
            raise ControlEngineError(
                "Engine reliability did not produce canonical scenario provenance"
            )
        reliability_token = reliability_result_issuance_token(reliability)
        try:
            validate_reliability_result(
                program,
                reliability,
                expected_scenario_digest=reliability.scenario_digest,
                expected_issuance_token=reliability_token,
            )
        except (ControlGraphError, TypeError) as error:
            raise ControlEngineError(
                f"Reliability provenance is invalid: {error}"
            ) from error

        explicit_reliability_bindings: dict[str, str] = {}
        known_reliability_event_ids = set(reliability.scenario.event_ids)
        for schedule_event_id, inputs in safe_operation_inputs.items():
            bound_ids = inputs.get("reliability_event_ids", ())
            if not isinstance(bound_ids, Sequence) or isinstance(
                bound_ids,
                (str, bytes),
            ):
                raise ControlEngineError(
                    f"operation_inputs_by_event.{schedule_event_id}."
                    "reliability_event_ids must be an array"
                )
            for reliability_event_id in bound_ids:
                event_name = _identifier(
                    reliability_event_id,
                    f"operation_inputs_by_event.{schedule_event_id}."
                    "reliability_event_ids item",
                )
                if event_name not in known_reliability_event_ids:
                    raise ControlEngineError(
                        f"Unknown reliability event binding: {event_name!r}"
                    )
                if event_name in explicit_reliability_bindings:
                    raise ControlEngineError(
                        f"Reliability event {event_name!r} is bound more than once"
                    )
                explicit_reliability_bindings[event_name] = schedule_event_id

        gate_rows_by_reliability_event: dict[str, list[Any]] = {}
        for gate_row in reliability.gate_probabilities:
            if gate_row.probability > 0:
                gate_rows_by_reliability_event.setdefault(
                    gate_row.event_id,
                    [],
                ).append(gate_row)
        reliability_timeline_bindings: dict[str, str] = {}
        reliability_events_by_id = {
            event.event_id: event for event in reliability.scenario.event_script
        }
        for reliability_event_id, gate_rows in gate_rows_by_reliability_event.items():
            reliability_event = reliability_events_by_id[reliability_event_id]
            explicit_event_id = explicit_reliability_bindings.get(
                reliability_event_id
            )
            candidates_for_event: list[str] = []
            for schedule_event in schedule.events:
                if (
                    explicit_event_id is not None
                    and schedule_event.event_id != explicit_event_id
                ):
                    continue
                for gate_row in gate_rows:
                    gate = program.gate(gate_row.gate_id)
                    scoped_targets = gate_row.target_ids or (None,)
                    moved_area_entry_continuation = bool(
                        explicit_event_id == schedule_event.event_id
                        and gate.trigger.kind == "entry"
                        and reliability_event.trigger.kind == "entry"
                        and any(
                            target_id is not None
                            and any(
                                transition.event_id == schedule_event.event_id
                                and transition.target_id == target_id
                                and transition.cause == "area_movement"
                                and transition.moved_area_counts_as_entry
                                and transition.area_id
                                in area_gate_bindings.get(gate.gate_id, ())
                                and (
                                    transition.effect_id,
                                    transition.area_id,
                                    transition.target_id,
                                    transition.event_id,
                                ) in updates_by_identity
                                for transition in bound_area_entry_transitions
                            )
                            for target_id in scoped_targets
                        )
                    )
                    try:
                        matches = moved_area_entry_continuation or any(
                            typed_event_matches(
                                schedule_event,
                                reliability_event.trigger.data.to_dict(),
                                target_id=target_id,
                                triggering_turn_id=schedule_event.turn_id,
                            )
                            and (
                                target_id is None
                                or schedule_event.target_id in {None, target_id}
                            )
                            for target_id in scoped_targets
                        )
                    except (TimelineError, TypeError, ValueError):
                        matches = False
                    if matches and gate.trigger.kind == reliability_event.trigger.kind:
                        candidates_for_event.append(schedule_event.event_id)
                        break
            candidates_for_event = list(dict.fromkeys(candidates_for_event))
            if len(candidates_for_event) != 1:
                raise ControlEngineError(
                    f"Reliability event {reliability_event_id!r} must bind "
                    "exactly one compatible timeline event; "
                    f"matches={candidates_for_event!r}"
                )
            reliability_timeline_bindings[reliability_event_id] = (
                candidates_for_event[0]
            )
        for transition in bound_area_entry_transitions:
            if (
                transition.cause == "area_movement"
                and not transition.moved_area_counts_as_entry
            ):
                continue
            entry_gate_ids = tuple(sorted(
                gate.gate_id
                for gate in program.gates
                if gate.trigger.kind == "entry"
                and transition.area_id
                in area_gate_bindings.get(gate.gate_id, ())
            ))
            missing_entry_gate_bindings = [
                gate_id
                for gate_id in entry_gate_ids
                if not any(
                    row.gate_id == gate_id
                    and row.probability > 0
                    and reliability_timeline_bindings.get(row.event_id)
                    == transition.event_id
                    and (
                        not row.target_ids
                        or transition.target_id in row.target_ids
                    )
                    for row in reliability.gate_probabilities
                )
            ]
            if missing_entry_gate_bindings:
                raise ControlEngineError(
                    "AreaEntryTransition has no exact same-event reliability "
                    f"binding for entry gates: {missing_entry_gate_bindings}"
                )
        for reliability_event_id, gate_rows in gate_rows_by_reliability_event.items():
            event_id = reliability_timeline_bindings[reliability_event_id]
            for gate_row in gate_rows:
                gate = program.gate(gate_row.gate_id)
                if (
                    gate.trigger.kind != "entry"
                    or gate.gate_id not in program.root_gate_ids
                ):
                    continue
                selected_targets = (
                    tuple(gate_row.target_ids)
                    if gate_row.target_ids
                    else tuple(sorted({
                        target_id
                        for selector_id in gate.selector_ids
                        for target_id in membership[selector_id]
                    }))
                )
                for target_id in selected_targets:
                    transition = next((
                        value
                        for value in bound_area_entry_transitions
                        if value.event_id == event_id
                        and value.target_id == target_id
                        and value.area_id
                        in area_gate_bindings.get(gate.gate_id, ())
                    ), None)
                    if transition is None:
                        raise ControlEngineError(
                            "Entry-gate reliability binding lacks its exact "
                            "scenario-bound AreaEntryTransition"
                        )
        if concentration_start_event_id is not None:
            start_sequence = schedule.event(
                concentration_start_event_id
            ).sequence
            premature_events = sorted(
                reliability_event_id
                for reliability_event_id, schedule_event_id
                in reliability_timeline_bindings.items()
                if schedule.event(schedule_event_id).sequence < start_sequence
            )
            if premature_events:
                raise ControlEngineError(
                    "Concentration gate events cannot precede the bound startup: "
                    f"{premature_events}"
                )

        required_operation_plan: dict[str, list[str]] = {}
        for reliability_event_id, gate_rows in gate_rows_by_reliability_event.items():
            schedule_event_id = reliability_timeline_bindings[
                reliability_event_id
            ]
            for gate_row in gate_rows:
                if gate_row.gate_id not in program.root_gate_ids:
                    continue
                if gate_row.target_ids:
                    for target_id in gate_row.target_ids:
                        required_operation_plan.setdefault(
                            schedule_event_id,
                            [],
                        ).append(f"branch:{gate_row.gate_id}:{target_id}")
                else:
                    gate = program.gate(gate_row.gate_id)
                    selected_targets = sorted({
                        target_id
                        for selector_id in gate.selector_ids
                        for target_id in membership[selector_id]
                    })
                    for target_id in selected_targets:
                        required_operation_plan.setdefault(
                            schedule_event_id,
                            [],
                        ).append(f"branch:{gate_row.gate_id}:{target_id}")
        for event_id, inputs in safe_operation_inputs.items():
            declared = inputs.get("required_operations", ())
            if (
                not isinstance(declared, Sequence)
                or isinstance(declared, (str, bytes))
            ):
                raise ControlEngineError(
                    f"operation_inputs_by_event.{event_id}.required_operations "
                    "must be an array"
                )
            for index, operation in enumerate(declared):
                required_operation_plan.setdefault(event_id, []).append(
                    _identifier(
                        operation,
                        f"operation_inputs_by_event.{event_id}."
                        f"required_operations[{index}]",
                    )
                )
            normalization_targets = inputs.get("normalization_target_ids", ())
            if (
                not isinstance(normalization_targets, Sequence)
                or isinstance(normalization_targets, (str, bytes))
            ):
                raise ControlEngineError(
                    f"operation_inputs_by_event.{event_id}."
                    "normalization_target_ids must be an array"
                )
            for target_id in normalization_targets:
                if target_id not in targets_by_id:
                    raise ControlEngineError(
                        f"Required normalization references unknown target {target_id!r}"
                    )
                required_operation_plan.setdefault(event_id, []).append(
                    f"normalization:{target_id}"
                )
        if concentration_start_event_id is not None:
            required_operation_plan.setdefault(
                concentration_start_event_id,
                [],
            ).append("concentration_start")
        for update in bound_area_geometry_updates:
            required_operation_plan.setdefault(update.event_id, []).append(
                f"area_geometry_update:{update.target_id}"
            )
        for transition in bound_area_entry_transitions:
            required_operation_plan.setdefault(transition.event_id, []).append(
                f"area_entry:{transition.target_id}"
            )
        canonical_required_plan = {
            event_id: list(dict.fromkeys(operations))
            for event_id, operations in sorted(required_operation_plan.items())
        }

        provenance = engine.version_provenance(
            initiative_convention=schedule.convention,
            area_response_convention=area_response_convention,
            displacement_function_id=displacement_function_id,
        )
        scenario_record = {
            "session_contract": "control_execution_session_v2",
            "compiled_program": {
                "effect_id": program.effect_id,
                "entity_id": program.entity_id,
                "tier": program.tier,
                "authority_sha256": program.authority_sha256,
            },
            "versions": provenance.to_dict(),
            "target_ids": list(schedule.target_ids),
            "target_mechanics": safe_target_mechanics,
            "initial_state": initial_state_rows,
            "initial_condition_registry": list(
                initial_condition_registry_rows
            ),
            "selector_membership": {
                selector_id: sorted(membership[selector_id])
                for selector_id in sorted(membership)
            },
            "selector_context": selector_context.to_dict(),
            "choice_bindings": bindings,
            "probability_context": probability_context.canonical_record(),
            "probability_kernel": (
                reliability.scenario.kernel_identity.canonical_record()
            ),
            "candidate_component_ids": list(
                reliability.scenario.candidate_component_ids
            ),
            "ordered_reliability_events": [
                event.canonical_record() for event in reliability.scenario.event_script
            ],
            "include_initial": include_initial,
            "reliability_scenario_digest": reliability.scenario_digest,
            "reliability_scenario": reliability.scenario.canonical_record(),
            "timeline_schedule": schedule_record,
            "initiative_convention": schedule.convention,
            "area_response_convention": area_response_convention,
            "displacement_function_id": displacement_function_id,
            "source_actor_id": source_actor,
            "invocation_id": invocation,
            "operation_inputs_by_event": safe_operation_inputs,
            "initial_area_route_states": [
                state.to_dict() for state in initial_area_route_states
            ],
            "area_geometry_updates": [
                update.to_dict() for update in bound_area_geometry_updates
            ],
            "area_entry_transitions": [
                transition.to_dict()
                for transition in bound_area_entry_transitions
            ],
            "area_gate_bindings": {
                gate_id: list(area_ids)
                for gate_id, area_ids in sorted(area_gate_bindings.items())
            },
            "area_target_ids_by_area": {
                area_id: list(target_ids)
                for area_id, target_ids in sorted(
                    area_target_ids_by_area.items()
                )
            },
            "persistent_area_ids": sorted(
                area_id
                for area_id, area in compiled_areas.items()
                if area.persistent
            ),
            "required_operation_plan": canonical_required_plan,
            "reliability_timeline_bindings": reliability_timeline_bindings,
            "concentration_save_bonus": concentration_save_bonus,
            "concentration_lifecycle": {
                "required": concentration_required,
                "start_event_id": concentration_start_event_id,
                "startup": concentration.get("startup"),
            },
        }
        scenario_json = _canonical_json(scenario_record)

        self._engine = engine
        self._program = program
        self._targets = target_rows
        self._targets_by_id = targets_by_id
        self._membership = membership
        self._selector_context = selector_context
        self._schedule = schedule
        self._schedule_json = _canonical_json(schedule_record)
        self._target_mechanics_json = _canonical_json(safe_target_mechanics)
        self._operation_inputs_json = _canonical_json(safe_operation_inputs)
        self._area_geometry_updates_json = _canonical_json(
            [update.to_dict() for update in bound_area_geometry_updates]
        )
        self._area_entry_transitions_json = _canonical_json(
            [
                transition.to_dict()
                for transition in bound_area_entry_transitions
            ]
        )
        self._area_gate_bindings = MappingProxyType(dict(area_gate_bindings))
        self._area_gate_bindings_json = _canonical_json({
            gate_id: list(area_ids)
            for gate_id, area_ids in sorted(area_gate_bindings.items())
        })
        self._area_target_ids_by_area = MappingProxyType(
            dict(area_target_ids_by_area)
        )
        self._area_target_ids_by_area_json = _canonical_json({
            area_id: list(target_ids)
            for area_id, target_ids in sorted(area_target_ids_by_area.items())
        })
        self._persistent_area_ids = frozenset(
            area_id
            for area_id, area in compiled_areas.items()
            if area.persistent
        )
        self._persistent_area_ids_json = _canonical_json(
            sorted(self._persistent_area_ids)
        )
        self._required_operation_plan_json = _canonical_json(
            canonical_required_plan
        )
        self._reliability_timeline_bindings_json = _canonical_json(
            reliability_timeline_bindings
        )
        self._area_response_convention = area_response_convention
        self._displacement_function_id = displacement_function_id
        self._choices = MappingProxyType(bindings)
        self._source_actor_id = source_actor
        self._known_actor_ids = frozenset({
            *schedule.target_ids,
            source_actor,
            *(
                event.actor_id
                for event in schedule.events
                if event.actor_id is not None
            ),
            *(
                instance["source_actor_id"]
                for rows in initial_condition_instances_by_target.values()
                for instance in rows
            ),
        })
        self._invocation_id = invocation
        self._concentration_required = concentration_required
        self._concentration_start_event_id = concentration_start_event_id
        self._reliability = reliability
        self._reliability_token = reliability_token
        self._reliability_digest = reliability.scenario_digest
        self._scenario_json = scenario_json
        self._scenario_digest = hashlib.sha256(
            scenario_json.encode("utf-8")
        ).hexdigest()
        self._issuer = object()
        self._state = initial_control_state
        self._area_route_states = {
            (state.effect_id, state.area_id, state.target_id): state
            for state in initial_area_route_states
        }
        self._initial_area_route_state_json = _canonical_json(
            [state.to_dict() for state in initial_area_route_states]
        )
        self._area_geometry_updates = {
            (update.event_id, update.target_id): update
            for update in bound_area_geometry_updates
        }
        self._area_entry_transitions = {
            (transition.event_id, transition.target_id): transition
            for transition in bound_area_entry_transitions
        }
        self._initial_state_json = _canonical_json(self._state.snapshot())
        if self._initial_state_json != _canonical_json(initial_state_rows):
            raise ControlEngineError(
                "Scenario-bound initial condition state is not canonical"
            )
        self._initial_condition_registry_json = _canonical_json(
            self._state.instance_registry()
        )
        if self._initial_condition_registry_json != _canonical_json(
            initial_condition_registry_rows
        ):
            raise ControlEngineError(
                "Scenario-bound initial condition registry is not canonical"
            )
        self._state.audit_ledger.clear()
        self._epochs = DisplacementEpochs()
        self._concentration_tracker = (
            ConcentrationTracker(
                save_bonus=concentration_save_bonus,
                owner_actor_id=source_actor,
            )
            if concentration_save_bonus is not None
            else None
        )
        self._cursor = -1
        self._current_event: TimelineEvent | None = None
        self._current_event_expiry_complete = False
        self._current_pre_state_json: str | None = None
        self._current_pre_route_state_json: str | None = None
        self._operation_sequence = 0
        self._issued_records: list[_IssuedControlRecord] = []
        self._issued_record_originals: list[_IssuedControlRecord] = []
        self._issued_record_attestations: list[str] = []
        self._event_snapshots: list[_ClosedEventSnapshot] = []
        self._normalization_results: list[NormalizationResult] = []
        self._event_state_transitions: list[dict[str, Any]] = []
        self._repeat_save_records: list[dict[str, Any]] = []
        self._area_records: list[dict[str, Any]] = []
        self._area_route_transitions: list[dict[str, Any]] = []
        self._prone_records: list[dict[str, Any]] = []
        self._condition_operation_records: list[dict[str, Any]] = []
        self._opportunity_roll_records: list[dict[str, Any]] = []
        self._source_relative_legality_records: list[dict[str, Any]] = []
        self._condition_concentration_records: list[dict[str, Any]] = []
        self._fall_transition_records: list[dict[str, Any]] = []
        self._concentration_records: list[dict[str, Any]] = []
        self._displacement_records: list[dict[str, Any]] = []
        self._pending_displacements: set[tuple[str, str]] = set()
        self._displaced_targets: set[str] = set()
        self._movement_response_required = False
        self._movement_response_consumed = False
        self._pending_prone_proposals: dict[str, _IssuedControlRecord] = {}
        self._consumed_prone_proposal_sequences: set[int] = set()
        self._pending_condition_proposals: dict[str, _IssuedControlRecord] = {}
        self._consumed_condition_proposal_sequences: set[int] = set()
        self._fall_transition_identities: set[tuple[str, str]] = set()
        self._current_required_operations: set[str] = set()
        self._future_required_operations: dict[str, set[str]] = {}
        self._pending_concentration_failure: (
            _PendingConcentrationFailure | None
        ) = None
        self._pending_concentration_failure_original: (
            _PendingConcentrationFailure | None
        ) = None
        self._pending_concentration_failure_attestation: str | None = None
        self._area_effect_started = False
        self._area_effect_ended = False
        self._shared_gate_outcomes: dict[tuple[str, str], str] = {}
        self._same_event_gate_overrides: set[tuple[str, str]] = set()
        self._area_entry_trigger_history: set[
            tuple[str, str, str, str]
        ] = set()
        self._cached_result: ControlEngineResult | None = None

    @property
    def scenario_digest(self) -> str:
        return self._scenario_digest

    @property
    def scenario_record(self) -> Mapping[str, Any]:
        return MappingProxyType(json.loads(self._scenario_json))

    @property
    def schedule(self) -> TimelineSchedule:
        return self._schedule

    @property
    def current_event(self) -> TimelineEvent | None:
        return self._current_event

    @property
    def cursor(self) -> int:
        return self._cursor

    def state_snapshot(self, target_id: str | None = None) -> tuple[Mapping[str, Any], ...]:
        if target_id is not None and target_id not in self._known_actor_ids:
            raise ControlEngineError(f"Unknown session actor: {target_id!r}")
        return tuple(
            MappingProxyType(row)
            for row in json.loads(_canonical_json(self._state.snapshot(target_id)))
        )

    def condition_instance_snapshot(
        self,
        target_id: str | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        """Expose immutable condition identity/lifecycle state, never mutation."""

        if target_id is not None and target_id not in self._known_actor_ids:
            raise ControlEngineError(f"Unknown session actor: {target_id!r}")
        return tuple(
            MappingProxyType(row)
            for row in json.loads(
                _canonical_json(self._state.instance_registry(target_id))
            )
        )

    def _area_route_state_rows(
        self,
        target_id: str | None = None,
        *,
        public: bool = False,
    ) -> list[dict[str, Any]]:
        target_rank = {
            value: index for index, value in enumerate(self._schedule.target_ids)
        }
        states = [
            state
            for state in self._area_route_states.values()
            if target_id is None or state.target_id == target_id
        ]
        states.sort(key=lambda state: (
            target_rank[state.target_id],
            state.effect_id,
            state.area_id,
        ))
        return [state.to_dict() for state in states]

    def _area_route_state_json(self) -> str:
        return _canonical_json(self._area_route_state_rows())

    def area_route_snapshot(
        self,
        target_id: str | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        if target_id is not None and target_id not in self._targets_by_id:
            raise ControlEngineError(f"Unknown session target: {target_id!r}")
        return tuple(
            MappingProxyType(row)
            for row in json.loads(_canonical_json(
                self._area_route_state_rows(target_id, public=True)
            ))
        )

    def _area_route_state_or_none(
        self,
        target_id: str,
        *,
        area_id: str | None = None,
    ) -> _AreaRouteState | None:
        matches = [
            state
            for state in self._area_route_states.values()
            if state.effect_id == self._program.effect_id
            and state.target_id == target_id
            and (area_id is None or state.area_id == area_id)
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise ControlEngineError(
                f"Target {target_id!r} has ambiguous bound area-route state"
            )
        return matches[0]

    def _area_route_state(self, target_id: str) -> _AreaRouteState:
        state = self._area_route_state_or_none(target_id)
        if state is None:
            raise ControlEngineError(
                f"Target {target_id!r} does not have exactly one bound area-route state"
            )
        return state

    def _canonical_area_gate_bindings(
        self,
    ) -> dict[str, tuple[str, ...]]:
        return self._compiled_area_gate_bindings(
            self._program,
            self._engine._compiled_area_bindings(self._program),
        )

    def _canonical_area_target_ids_by_area(
        self,
    ) -> dict[str, tuple[str, ...]]:
        membership = self._reliability.scenario.canonical_record()[
            "selector_membership"
        ]
        area_ids = {
            selector.area.area_id
            for selector in self._program.selectors
            if selector.area is not None
        }
        return {
            area_id: tuple(sorted({
                target_id
                for selector in self._program.selectors
                if selector.area is not None
                and selector.area.area_id == area_id
                for target_id in membership[selector.selector_id]
            }))
            for area_id in area_ids
        }

    def _canonical_persistent_area_ids(self) -> frozenset[str]:
        return frozenset(
            selector.area.area_id
            for selector in self._program.selectors
            if selector.area is not None and selector.area.persistent
        )

    def _area_effect_is_active(self, area_id: str) -> bool:
        if area_id not in self._canonical_persistent_area_ids():
            return False
        if self._concentration_required:
            return bool(
                self._concentration_tracker is not None
                and self._concentration_tracker.active_effect_id
                == self._program.effect_id
            )
        return self._area_effect_started and not self._area_effect_ended

    def _area_gate_eligibility(
        self,
        *,
        gate_id: str,
        target_id: str,
    ) -> tuple[bool, str | None]:
        area_gate_bindings = self._canonical_area_gate_bindings()
        area_ids = area_gate_bindings.get(gate_id, ())
        if not area_ids:
            return True, None
        for area_id in area_ids:
            route_state = self._area_route_state_or_none(
                target_id,
                area_id=area_id,
            )
            if route_state is None:
                raise ControlEngineError(
                    f"Area-owned gate {gate_id!r} has no authoritative area "
                    f"membership state for target {target_id!r} and area "
                    f"{area_id!r}"
                )
            member = route_state.membership
            if not member:
                return False, (
                    f"target {target_id!r} is a nonmember according to "
                    f"authoritative area membership for area {area_id!r}"
                )
            if not self._area_effect_is_active(area_id):
                return False, (
                    f"compiled area {area_id!r} is not active at the current event"
                )
        return True, None

    def _require_area_gate_eligible(
        self,
        *,
        gate_id: str,
        target_id: str,
    ) -> None:
        eligible, reason = self._area_gate_eligibility(
            gate_id=gate_id,
            target_id=target_id,
        )
        if not eligible:
            raise ControlEngineError(
                f"Area-owned gate {gate_id!r} is ineligible because {reason}"
            )

    def _prune_future_area_gate_operations(
        self,
        *,
        area_id: str,
        target_id: str,
    ) -> None:
        area_gate_bindings = self._canonical_area_gate_bindings()

        def retained(operation: str) -> bool:
            parts = operation.split(":", 2)
            if len(parts) != 3 or parts[0] not in {
                "branch",
                "concentration_end",
            }:
                return True
            gate_id, operation_target = parts[1], parts[2]
            return not (
                operation_target == target_id
                and area_id in area_gate_bindings.get(gate_id, ())
            )

        self._current_required_operations = {
            operation
            for operation in self._current_required_operations
            if retained(operation)
        }
        for event_id in tuple(self._future_required_operations):
            remaining = {
                operation
                for operation in self._future_required_operations[event_id]
                if retained(operation)
            }
            if remaining:
                self._future_required_operations[event_id] = remaining
            else:
                del self._future_required_operations[event_id]

    def _set_area_route_state(self, state: _AreaRouteState) -> None:
        key = (state.effect_id, state.area_id, state.target_id)
        if key not in self._area_route_states:
            raise ControlEngineError("Area-route transition references unknown state")
        self._area_route_states[key] = state

    def _entry_gate_ids(
        self,
        transition: AreaEntryTransition,
    ) -> tuple[str, ...]:
        bindings = self._canonical_area_gate_bindings()
        return tuple(sorted(
            gate.gate_id
            for gate in self._program.gates
            if gate.trigger.kind == "entry"
            and transition.area_id in bindings.get(gate.gate_id, ())
        ))

    def _ambient_area_component_ids(
        self,
        *,
        area_id: str,
        target_id: str,
    ) -> tuple[str, ...]:
        """Return selected area-bound components applied by activation cadence."""

        if area_id not in self._persistent_area_ids:
            return ()
        bindings = self._engine._compiled_area_bindings(self._program)
        area_selector_ids = {
            selector.selector_id
            for selector in self._program.selectors
            if selector.area is not None
            and selector.area.persistent
            and selector.area.area_id == area_id
        }
        return tuple(sorted(
            component.component_id
            for component in self._program.components
            if area_id in bindings.get(component.component_id, ())
            and any(cadence.kind == "activation" for cadence in component.cadence_apply)
            and (
                component.choice_id is None
                or self._choices[component.choice_id] == component.choice_option_id
            )
            and any(
                selector_id in area_selector_ids
                and target_id in self._membership[selector_id]
                for selector_id in component.target_selector_ids
            )
        ))

    def _ambient_component_canonically_suppressed(
        self,
        *,
        component_id: str,
        target_id: str,
    ) -> bool:
        component = self._program.component(component_id)
        return bool(
            component.magnitude.kind == "condition"
            and component.magnitude.data.get("condition")
            in self._targets_by_id[target_id].condition_immunities
        )

    def _ambient_activation_evidence(
        self,
        *,
        area_id: str,
        target_id: str,
        component_id: str,
        before_sequence: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Return canonical realized-or-membership-filtered activation rows."""

        rows: list[dict[str, Any]] = []
        for transition in self._event_state_transitions:
            event_id = transition.get("event_id")
            gate_id = transition.get("gate_id")
            if not isinstance(event_id, str) or not isinstance(gate_id, str):
                continue
            event = self._schedule.event(event_id)
            if before_sequence is not None and event.sequence >= before_sequence:
                continue
            try:
                gate = self._program.gate(gate_id)
            except Exception:
                continue
            if (
                gate.trigger.kind != "activation"
                or transition.get("operation") != "branch_transition"
                or transition.get("effect_id") != self._program.effect_id
                or transition.get("target_id") != target_id
            ):
                continue
            filtered_applies = transition.get("filtered_branch", {}).get(
                "applies",
                (),
            )
            suppression = next((
                dict(item)
                for item in transition.get(
                    "outside_compiled_area_membership_suppressions",
                    (),
                )
                if item.get("kind") == "outside_compiled_area_membership"
                and item.get("area_id") == area_id
                and item.get("component_id") == component_id
                and item.get("target_id") == target_id
            ), None)
            if component_id not in filtered_applies and suppression is None:
                continue
            rows.append({
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "gate_id": gate.gate_id,
                "branch_id": transition.get("branch_id"),
                "component_id": component_id,
                "area_id": area_id,
                "target_id": target_id,
                "membership_filtered": suppression is not None,
            })
        return tuple(rows)

    def _ambient_evidence_is_live(
        self,
        *,
        component_id: str,
        target_id: str,
        evidence: Mapping[str, Any],
    ) -> bool:
        component = self._program.component(component_id)
        expiry_index = resolve_expiry_index(
            self._schedule,
            str(evidence["event_id"]),
            component.duration.to_dict(),
            target_id=target_id,
        )
        if expiry_index is None:
            return True
        if self._current_event is not None:
            if self._current_event_expiry_complete:
                return expiry_index > self._current_event.sequence
            return expiry_index >= self._current_event.sequence
        return expiry_index > self._cursor

    def _activation_gate_pending_for_target(self, target_id: str) -> bool:
        if self._current_event is None:
            return False
        for operation in self._current_required_operations:
            parts = operation.split(":", 2)
            if len(parts) < 2 or parts[0] != "branch":
                continue
            if len(parts) == 3 and parts[2] != target_id:
                continue
            try:
                gate = self._program.gate(parts[1])
            except Exception:
                continue
            if gate.trigger.kind == "activation":
                return True
        return False

    def _validate_ambient_membership_state(self) -> None:
        """Fail closed when live component state disagrees with area authority."""

        bindings = self._engine._compiled_area_bindings(self._program)
        active_by_target = {
            target_id: {
                component.component_id
                for component in self._state.active_components(target_id)
                if component.effect_id == self._program.effect_id
            }
            for target_id in self._schedule.target_ids
        }
        for target_id, active_ids in active_by_target.items():
            for component_id in sorted(active_ids & set(bindings)):
                area_ids = bindings[component_id]
                if not any(
                    self._area_route_state_or_none(
                        target_id,
                        area_id=area_id,
                    ) is not None
                    for area_id in area_ids
                ):
                    raise ControlEngineError(
                        "Active area-bound component lacks authoritative area-route "
                        f"state: target={target_id!r}, component={component_id!r}"
                    )
            for area_id in sorted(self._persistent_area_ids):
                route_state = self._area_route_state_or_none(
                    target_id,
                    area_id=area_id,
                )
                if route_state is None:
                    continue
                area_active_ids = {
                    component_id
                    for component_id in active_ids
                    if area_id in bindings.get(component_id, ())
                }
                ambient_ids = set(self._ambient_area_component_ids(
                    area_id=area_id,
                    target_id=target_id,
                ))
                active_ambient_ids = ambient_ids & active_ids
                if not route_state.membership and area_active_ids:
                    raise ControlEngineError(
                        "Active ambient or other area components contradict "
                        "authoritative membership for nonmember "
                        f"target {target_id!r} and area {area_id!r}: "
                        f"{sorted(area_active_ids)}"
                    )
                area_is_active = bool(
                    self._area_effect_is_active(area_id)
                    or (
                        self._current_event is not None
                        and self._current_event.kind == "activation"
                        and not self._activation_gate_pending_for_target(
                            target_id
                        )
                    )
                )
                if not area_is_active and active_ambient_ids:
                    raise ControlEngineError(
                        "Active ambient area components outlive their compiled "
                        f"persistent area: {sorted(active_ambient_ids)}"
                    )
                if not route_state.membership or not area_is_active:
                    continue
                missing: list[str] = []
                for component_id in sorted(ambient_ids):
                    if self._ambient_component_canonically_suppressed(
                        component_id=component_id,
                        target_id=target_id,
                    ):
                        continue
                    evidence = self._ambient_activation_evidence(
                        area_id=area_id,
                        target_id=target_id,
                        component_id=component_id,
                    )
                    if len(evidence) > 1:
                        raise ControlEngineError(
                            "Ambient component has ambiguous activation chronology: "
                            f"target={target_id!r}, component={component_id!r}"
                        )
                    if not evidence:
                        continue
                    if (
                        self._ambient_evidence_is_live(
                            component_id=component_id,
                            target_id=target_id,
                            evidence=evidence[0],
                        )
                        and component_id not in active_ids
                    ):
                        missing.append(component_id)
                if missing:
                    raise ControlEngineError(
                        "Authoritative area member lacks applicable ambient "
                        f"components for area {area_id!r}: {missing}"
                    )

    def _live_ambient_area_component_plan(
        self,
        *,
        area_id: str,
        target_id: str,
        event_sequence: int,
    ) -> tuple[tuple[CompiledComponent, str | None, str], ...]:
        """Resolve canonical activation provenance and unexpired duration."""

        rows: list[tuple[CompiledComponent, str | None, str]] = []
        for component_id in self._ambient_area_component_ids(
            area_id=area_id,
            target_id=target_id,
        ):
            if self._ambient_component_canonically_suppressed(
                component_id=component_id,
                target_id=target_id,
            ):
                continue
            evidence = self._ambient_activation_evidence(
                area_id=area_id,
                target_id=target_id,
                component_id=component_id,
                before_sequence=event_sequence,
            )
            if len(evidence) > 1:
                raise ControlEngineError(
                    f"Ambient area component {component_id!r} requires exactly "
                    "one prior realized or membership-filtered activation"
                )
            if not evidence:
                continue
            activation_event_id = str(evidence[0]["event_id"])
            component = self._program.component(component_id)
            expiry_index = resolve_expiry_index(
                self._schedule,
                activation_event_id,
                component.duration.to_dict(),
                target_id=target_id,
            )
            if expiry_index is not None and expiry_index < event_sequence:
                continue
            rows.append((
                component,
                (
                    self._schedule.events[expiry_index].event_id
                    if expiry_index is not None else None
                ),
                activation_event_id,
            ))
        return tuple(rows)

    def _ambient_area_restoration_plan(
        self,
        *,
        transition: AreaEntryTransition,
        event: TimelineEvent,
    ) -> dict[str, Any]:
        """Preflight exact ambient restoration before membership mutation."""

        authority_rows = self._live_ambient_area_component_plan(
            area_id=transition.area_id,
            target_id=transition.target_id,
            event_sequence=event.sequence,
        )
        ambient_ids = tuple(
            component.component_id
            for component, _expiry_event_id, _activation_event_id
            in authority_rows
        )
        active_ids = {
            component.component_id
            for component in self._state.active_components(transition.target_id)
            if component.effect_id == transition.effect_id
        }
        restore_rows = tuple(
            row for row in authority_rows
            if row[0].component_id not in active_ids
        )
        occupied_nonindependent_keys = {
            str(component.stacking.get("key"))
            for component in self._state.active_components(
                transition.target_id
            )
            if component.effect_id == transition.effect_id
            and component.stacking.get("mode") != "independent"
        }
        planned_nonindependent_keys: set[str] = set()
        for component, _expiry_event_id, _activation_event_id in restore_rows:
            stacking = component.stacking.data.to_dict()
            if stacking.get("mode") == "independent":
                continue
            key = str(stacking.get("key"))
            if (
                key in occupied_nonindependent_keys
                or key in planned_nonindependent_keys
            ):
                raise ControlEngineError(
                    "Ambient restoration has a nonstacking conflict before "
                    f"membership mutation: component={component.component_id!r}, "
                    f"stacking_key={key!r}"
                )
            planned_nonindependent_keys.add(key)
        return {
            "ambient_component_ids": ambient_ids,
            "retained_component_ids": tuple(
                component_id
                for component_id in ambient_ids
                if component_id in active_ids
            ),
            "restore_rows": restore_rows,
        }

    def _restore_ambient_area_components(
        self,
        *,
        plan: Mapping[str, Any],
        transition: AreaEntryTransition,
        event: TimelineEvent,
    ) -> tuple[str, ...]:
        restored: list[str] = []
        for component, expiry_event_id, _activation_event_id in plan["restore_rows"]:
            applied = self._state.apply_component(
                effect_id=self._program.effect_id,
                component=self._engine._state_component_definition(component),
                target_id=transition.target_id,
                source_actor_id=self._source_actor_id,
                event_id=event.event_id,
                invocation_id=self._invocation_id,
                expiry_event_id=expiry_event_id,
                condition_immunities=self._targets_by_id[
                    transition.target_id
                ].condition_immunities,
                application_sequence=event.sequence,
                source_program_id=self._program.effect_id,
                issuance_id=(
                    f"{self._scenario_digest}:{event.event_id}:"
                    f"ambient_restore:{self._operation_sequence + 1}"
                ),
                provenance_id=self._scenario_digest,
            )
            if applied is None or applied.component_id != component.component_id:
                raise ControlEngineError(
                    "Compiled ambient area component could not be restored"
                )
            restored.append(component.component_id)
        return tuple(restored)

    def _entry_decision(
        self,
        *,
        transition: AreaEntryTransition,
        old_state: _AreaRouteState,
        event: TimelineEvent,
    ) -> dict[str, Any]:
        """Validate one exact entry and decide frequency before any mutation."""

        label = f"area_entry:{transition.target_id}"
        if label not in self._current_required_operations:
            raise ControlEngineError(
                "The scenario-bound AreaEntryTransition was already consumed"
            )
        if (
            transition.event_id != event.event_id
            or transition.event_sequence != event.sequence
            or transition.effect_id != self._program.effect_id
            or old_state.effect_id != transition.effect_id
            or old_state.area_id != transition.area_id
            or old_state.target_id != transition.target_id
        ):
            raise ControlEngineError(
                "AreaEntryTransition is foreign, stale, or bound to another event"
            )
        if old_state.membership:
            raise ControlEngineError(
                "AreaEntryTransition requires authoritative pre-entry membership false"
            )
        if not self._area_effect_is_active(transition.area_id):
            raise ControlEngineError(
                "AreaEntryTransition requires an active compiled persistent area"
            )
        area = next(
            selector.area
            for selector in self._program.selectors
            if selector.area is not None
            and selector.area.area_id == transition.area_id
        )
        policy = None if area.entry_policy is None else area.entry_policy.to_dict()
        if (
            not isinstance(policy, Mapping)
            or policy.get("frequency") not in {"once_per_turn", "unlimited"}
            or policy.get("moved_area_counts_as_entry")
            != transition.moved_area_counts_as_entry
        ):
            raise ControlEngineError(
                "AreaEntryTransition no longer matches compiled entry policy"
            )
        frequency_key = (
            transition.effect_id,
            transition.area_id,
            transition.target_id,
            transition.turn_id,
        )
        previously_triggered = frequency_key in self._area_entry_trigger_history
        frequency_permitted = bool(
            policy["frequency"] == "unlimited" or not previously_triggered
        )
        movement_counts = bool(
            transition.cause != "area_movement"
            or transition.moved_area_counts_as_entry
        )
        triggered = bool(movement_counts and frequency_permitted)
        if not movement_counts:
            frequency_decision = "area_movement_does_not_count"
        elif not frequency_permitted:
            frequency_decision = "once_per_turn_already_triggered"
        elif policy["frequency"] == "once_per_turn":
            frequency_decision = "first_qualifying_entry_this_turn"
        else:
            frequency_decision = "unlimited_entry"
        gate_ids = self._entry_gate_ids(transition)
        if triggered:
            bindings = json.loads(self._reliability_timeline_bindings_json)
            missing_gate_bindings = [
                gate_id
                for gate_id in gate_ids
                if not any(
                    row.gate_id == gate_id
                    and row.probability > 0
                    and bindings.get(row.event_id) == event.event_id
                    and (
                        not row.target_ids
                        or transition.target_id in row.target_ids
                    )
                    for row in self._reliability.gate_probabilities
                )
            ]
            if missing_gate_bindings:
                raise ControlEngineError(
                    "AreaEntryTransition has no exact reliability binding for "
                    f"entry gates: {missing_gate_bindings}"
                )
        return {
            "entry_policy": dict(policy),
            "frequency_key": {
                "effect_id": frequency_key[0],
                "area_id": frequency_key[1],
                "target_id": frequency_key[2],
                "turn_id": frequency_key[3],
            },
            "previously_triggered_this_turn": previously_triggered,
            "frequency_permitted": frequency_permitted,
            "frequency_decision": frequency_decision,
            "frequency_history_consumed": triggered,
            "triggered": triggered,
            "gate_ids": gate_ids,
            "frequency_key_tuple": frequency_key,
        }

    def _commit_entry_decision(
        self,
        *,
        transition: AreaEntryTransition,
        decision: Mapping[str, Any],
    ) -> None:
        gate_ids = tuple(decision["gate_ids"])
        if decision["triggered"]:
            if decision["frequency_history_consumed"]:
                self._area_entry_trigger_history.add(
                    tuple(decision["frequency_key_tuple"])
                )
            for gate_id in gate_ids:
                self._current_required_operations.add(
                    f"branch:{gate_id}:{transition.target_id}"
                )
                if transition.cause == "area_movement":
                    self._same_event_gate_overrides.add(
                        (gate_id, transition.target_id)
                    )
        else:
            for gate_id in gate_ids:
                self._current_required_operations.discard(
                    f"branch:{gate_id}:{transition.target_id}"
                )
                self._current_required_operations.discard(f"branch:{gate_id}")
                gate = self._program.gate(gate_id)
                if gate.resolution_kind == "saving_throw":
                    self._current_required_operations.discard(
                        f"opportunity_roll:save:{transition.target_id}"
                    )
                elif gate.resolution_kind == "attack_roll":
                    self._current_required_operations.discard(
                        f"opportunity_roll:attack:{transition.target_id}"
                    )
        self._current_required_operations.discard(
            f"area_entry:{transition.target_id}"
        )

    def _require_entry_gate_attested(
        self,
        *,
        gate_id: str,
        target_id: str,
        event: TimelineEvent,
    ) -> _IssuedControlRecord:
        matches: list[_IssuedControlRecord] = []
        for record in self._issued_records:
            if (
                record.record_kind != "area_entry"
                or record.event_id != event.event_id
                or record.target_id != target_id
            ):
                continue
            self._require_locally_issued_record(record)
            payload = json.loads(record.payload_json)
            if (
                payload.get("triggered") is True
                and payload.get("frequency_permitted") is True
                and gate_id in payload.get("gate_requirement_ids", ())
            ):
                matches.append(record)
        if len(matches) != 1:
            raise ControlEngineError(
                f"Entry gate {gate_id!r}/{target_id!r} requires one earlier "
                "attested false-to-true AreaEntryTransition"
            )
        record = matches[0]
        payload = json.loads(record.payload_json)
        bound = self._area_entry_transitions.get((event.event_id, target_id))
        if (
            bound is None
            or payload.get("bound_transition") != bound.to_dict()
            or payload.get("area_id")
            not in self._canonical_area_gate_bindings().get(gate_id, ())
            or record.operation_sequence >= self._operation_sequence + 1
        ):
            raise ControlEngineError(
                "Entry gate transition attestation is foreign, stale, or out of order"
            )
        pre_rows = json.loads(record.pre_event_route_state_json)
        pre_matches = [
            row for row in pre_rows
            if row.get("effect_id") == bound.effect_id
            and row.get("area_id") == bound.area_id
            and row.get("target_id") == bound.target_id
        ]
        current = self._area_route_state_or_none(
            target_id,
            area_id=bound.area_id,
        )
        if (
            len(pre_matches) != 1
            or pre_matches[0].get("membership") is not False
            or payload.get("membership_before") is not False
            or payload.get("membership_after") is not True
            or current is None
            or not current.membership
            or not self._area_effect_is_active(bound.area_id)
        ):
            raise ControlEngineError(
                "Entry gate lacks continuous false-to-true authoritative membership"
            )
        return record

    def _route_transition(
        self,
        *,
        transition_kind: str,
        event: TimelineEvent,
        old_state: _AreaRouteState,
        new_state: _AreaRouteState,
        pre_route_state_json: str,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        post_route_state_json = self._area_route_state_json()
        transition = {
            "transition_kind": transition_kind,
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "effect_id": old_state.effect_id,
            "area_id": old_state.area_id,
            "target_id": old_state.target_id,
            "old_route_state": old_state.to_dict(),
            "new_route_state": new_state.to_dict(),
            "pre_route_state_sha256": hashlib.sha256(
                pre_route_state_json.encode("utf-8")
            ).hexdigest(),
            "post_route_state_sha256": hashlib.sha256(
                post_route_state_json.encode("utf-8")
            ).hexdigest(),
            **dict(_json_safe(extra or {})),
        }
        self._area_route_transitions.append(transition)
        return transition

    def _close_area_routes_for_effect_end(
        self,
        *,
        event: TimelineEvent,
        reason: str,
    ) -> tuple[_IssuedControlRecord, ...]:
        issued: list[_IssuedControlRecord] = []
        for old_state in tuple(self._area_route_states.values()):
            if not old_state.membership:
                continue
            pre = _canonical_json(self._state.snapshot())
            pre_route = self._area_route_state_json()
            new_state = replace(
                old_state,
                membership=False,
                closed_reason=reason,
                last_update_event_id=event.event_id,
                last_update_event_sequence=event.sequence,
            )
            self._set_area_route_state(new_state)
            self._prune_future_area_gate_operations(
                area_id=old_state.area_id,
                target_id=old_state.target_id,
            )
            transition = self._route_transition(
                transition_kind="effect_end",
                event=event,
                old_state=old_state,
                new_state=new_state,
                pre_route_state_json=pre_route,
                extra={"canonical_reason": reason},
            )
            payload = {
                "kind": "area_route_transition",
                "canonical_reason": reason,
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "effect_id": old_state.effect_id,
                "area_id": old_state.area_id,
                "target_id": old_state.target_id,
                "route_transition": transition,
            }
            self._state.audit_ledger.append({
                "operation": "area_route_transition",
                **payload,
            })
            issued.append(self._issue(
                record_kind="area_route_transition",
                payload=payload,
                pre_operation_state_json=pre,
                pre_operation_route_state_json=pre_route,
                target_id=old_state.target_id,
            ))
        return tuple(issued)

    def issued_records(self) -> tuple[_IssuedControlRecord, ...]:
        return tuple(self._issued_records)

    def event_reference(self, event_id: str) -> _SessionEventReference:
        try:
            event = self._schedule.event(_identifier(event_id, "event_id"))
        except TimelineError as error:
            raise ControlEngineError(f"Unknown session event ID: {event_id!r}") from error
        return _SessionEventReference(
            event_id=event.event_id,
            event_sequence=event.sequence,
            scenario_digest=self._scenario_digest,
            _issuer=self._issuer,
        )

    def _target_mechanics(self, target_id: str) -> dict[str, Any]:
        return json.loads(self._target_mechanics_json)[target_id]

    def _operation_inputs(self, event_id: str) -> dict[str, Any]:
        return json.loads(self._operation_inputs_json).get(event_id, {})

    @staticmethod
    def _target_snapshot_slice_json(
        snapshot_json: str,
        target_id: str,
    ) -> str:
        """Return one target's exact canonical slice from a state snapshot."""

        return _canonical_json([
            row
            for row in json.loads(snapshot_json)
            if row.get("target_id") == target_id
        ])

    @staticmethod
    def _target_route_snapshot_slice_json(
        snapshot_json: str,
        target_id: str,
    ) -> str:
        """Return one target's exact canonical slice from a route snapshot."""

        return _canonical_json([
            row
            for row in json.loads(snapshot_json)
            if row.get("target_id") == target_id
        ])

    def _require_pending_normalization_complete_before_mutation(
        self,
        *target_ids: str,
    ) -> None:
        """Phase-lock target mutations behind their required normalization."""

        targets = {
            _identifier(target_id, "normalization mutation target_id")
            for target_id in target_ids
        }
        blocked = sorted(
            target_id
            for target_id in targets
            if f"normalization:{target_id}"
            in self._current_required_operations
        )
        if "normalization" in self._current_required_operations:
            blocked = sorted(targets)
        if blocked:
            raise ControlEngineError(
                "Pending required normalization must complete before "
                "mechanically relevant target or route mutation: "
                f"{blocked}"
            )

    def _require_unchanged_pre_event_normalization_basis(
        self,
        target_id: str,
    ) -> None:
        """Require the complete target and route basis captured at event open."""

        if self._current_pre_state_json is None:  # pragma: no cover - invariant
            raise ControlEngineError("Current event has no pre-event snapshot")
        if self._current_pre_route_state_json is None:  # pragma: no cover
            raise ControlEngineError(
                "Current event has no pre-event route snapshot"
            )
        target = _identifier(target_id, "normalization target_id")
        pre_event_target_json = self._target_snapshot_slice_json(
            self._current_pre_state_json,
            target,
        )
        current_target_json = _canonical_json(self._state.snapshot(target))
        pre_event_route_json = self._target_route_snapshot_slice_json(
            self._current_pre_route_state_json,
            target,
        )
        current_route_json = _canonical_json(
            self._area_route_state_rows(target)
        )
        if (
            current_target_json != pre_event_target_json
            or current_route_json != pre_event_route_json
        ):
            raise ControlEngineError(
                "Normalization requires the unchanged pre-event target and "
                "route state"
            )

    def _require_unchanged_pre_event_condition_basis(
        self,
        target_id: str,
    ) -> None:
        """Require the closed event-open condition/component state for a roll."""

        if self._current_pre_state_json is None:  # pragma: no cover - invariant
            raise ControlEngineError("Current event has no pre-event snapshot")
        target = _identifier(target_id, "opportunity target_id")
        if _canonical_json(self._state.snapshot(target)) != (
            self._target_snapshot_slice_json(
                self._current_pre_state_json,
                target,
            )
        ):
            raise ControlEngineError(
                "Opportunity resolution requires the unchanged closed "
                "pre-event condition state"
            )

    def _require_unchanged_attested_entry_condition_basis(
        self,
        target_id: str,
        entry_record: _IssuedControlRecord,
    ) -> None:
        """Require the exact post-entry state issued before an entry-gate roll."""

        target = _identifier(target_id, "entry opportunity target_id")
        self._require_locally_issued_record(entry_record)
        if (
            entry_record.record_kind != "area_entry"
            or entry_record.event_id
            != self._require_current().event_id
            or entry_record.target_id != target
        ):
            raise ControlEngineError(
                "Entry opportunity condition basis lacks its exact local "
                "AreaEntryTransition attestation"
            )
        expected_target_json = self._target_snapshot_slice_json(
            entry_record.post_operation_state_json,
            target,
        )
        if _canonical_json(self._state.snapshot(target)) != expected_target_json:
            raise ControlEngineError(
                "Entry opportunity resolution requires the unchanged "
                "attested post-entry condition state"
            )

    def _effect_mutation_target_ids(
        self,
        *,
        additional_target_ids: Iterable[str] = (),
    ) -> tuple[str, ...]:
        """Return targets one program-wide end transition can mutate."""

        targets = {
            component.target_id
            for component in self._state.active_components()
            if component.effect_id == self._program.effect_id
        }
        targets.update(
            state.target_id
            for state in self._area_route_states.values()
            if state.effect_id == self._program.effect_id and state.membership
        )
        targets.update(
            _identifier(target_id, "effect mutation target_id")
            for target_id in additional_target_ids
        )
        return tuple(sorted(targets))

    def _concentration_end_mutation_target_ids(
        self,
        *,
        context: _ConcentrationAuthorityContext,
        plans: Iterable[tuple[str, str, str]],
    ) -> tuple[str, ...]:
        """Return only targets the compiled concentration end can mutate."""

        cleanup_ids = set(context.concentration_component_ids) | set(
            context.area_component_ids
        )
        targets = {
            component.target_id
            for component in self._state.active_components()
            if component.effect_id == context.program.effect_id
            and component.component_id in cleanup_ids
        }
        targets.update(
            state.target_id
            for state in self._area_route_states.values()
            if state.effect_id == context.program.effect_id
            and state.area_id in context.area_ids
            and state.membership
        )
        targets.update(target_id for _gate_id, target_id, _outcome in plans)
        return tuple(sorted(targets))

    @staticmethod
    def _concentration_tracker_state_json(
        tracker: ConcentrationTracker,
    ) -> str:
        """Serialize the complete active tracker slot, including end authority."""

        return _canonical_json({
            "active_effect_id": tracker.active_effect_id,
            "active_metadata": deepcopy(tracker._active_metadata),
            "owner_actor_id": tracker.owner_actor_id,
            "save_bonus": tracker.save_bonus,
            "records": deepcopy(tracker.records),
        })

    def _preview_failed_concentration_tracker_records(
        self,
        *,
        tracker: ConcentrationTracker,
        amount: int | float,
        source: str,
        damage_event_id: str,
        end_event_id: str,
        success_probability: Any | None,
        roll_kernel: Sequence[Mapping[str, Any]] | None,
    ) -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Validate a failure on an isolated tracker without ending the live slot."""

        tracker_pre_state_json = self._concentration_tracker_state_json(tracker)
        simulated = deepcopy(tracker)
        first_record_index = len(simulated.records)
        check_record = simulated.check(
            amount=amount,
            source=source,
            event_id=damage_event_id,
            outcome="failure",
            success_probability=success_probability,
            roll_kernel=roll_kernel,
        )
        generated = simulated.records[first_record_index:]
        if (
            len(generated) != 2
            or generated[0] != check_record
            or generated[0].get("kind") != "concentration_check"
            or generated[1].get("kind") != "concentration_end"
            or generated[1].get("reason") != "failed_concentration_save"
            or generated[1].get("event_id") != damage_event_id
        ):
            raise ControlEngineError(
                "Tracker did not preview the canonical failed-check lifecycle"
            )
        end_record = dict(_json_safe(generated[1]))
        end_record["event_id"] = end_event_id
        tracker_pre_state = json.loads(tracker_pre_state_json)
        tracker_post_check_state = {
            **tracker_pre_state,
            "records": [
                *tracker_pre_state["records"],
                dict(_json_safe(check_record)),
            ],
        }
        return (
            dict(_json_safe(check_record)),
            end_record,
            tracker_pre_state_json,
            _canonical_json(tracker_post_check_state),
        )

    @staticmethod
    def _require_failed_tracker_end_matches_context(
        record: Mapping[str, Any],
        *,
        context: _ConcentrationAuthorityContext,
        end_event_id: str,
    ) -> None:
        expected = {
            "kind": "concentration_end",
            "event_id": end_event_id,
            "effect_id": context.program.effect_id,
            "owner_actor_id": context.source_actor_id,
            "reason": "failed_concentration_save",
            "changed": True,
            "ended_component_ids": list(context.concentration_component_ids),
            "ended_area_ids": list(context.area_ids),
            "execute_concentration_end_gates": True,
            "fall_transitions": [],
        }
        if dict(_json_safe(record)) != expected:
            raise ControlEngineError(
                "Failed concentration tracker end does not match compiled authority"
            )

    def _new_pending_concentration_failure(
        self,
        *,
        event: TimelineEvent,
        end_event: TimelineEvent,
        check_record: Mapping[str, Any],
        tracker_pre_state_json: str,
        tracker_post_check_state_json: str,
        tracker_end_record: Mapping[str, Any],
        context: _ConcentrationAuthorityContext,
        plans: Sequence[tuple[str, str, str]],
        affected_target_ids: Sequence[str],
    ) -> _PendingConcentrationFailure:
        pending = _PendingConcentrationFailure(
            scenario_digest=self._scenario_digest,
            effect_id=self._program.effect_id,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            damage_event_id=event.event_id,
            damage_event_sequence=event.sequence,
            end_event_id=end_event.event_id,
            end_event_sequence=end_event.sequence,
            check_operation_sequence=self._operation_sequence + 1,
            check_record_json=_canonical_json(check_record),
            tracker_pre_state_json=tracker_pre_state_json,
            tracker_post_check_state_json=tracker_post_check_state_json,
            tracker_end_record_json=_canonical_json(tracker_end_record),
            authority_metadata_json=_canonical_json(
                self._engine._concentration_authority_metadata(context)
            ),
            end_plan=tuple(tuple(plan) for plan in plans),
            affected_target_ids=tuple(sorted(affected_target_ids)),
            pending_sha256="",
            _issuer=self._issuer,
        )
        return replace(pending, pending_sha256=pending.computed_sha256())

    def _require_locally_issued_pending_concentration_failure(
        self,
        pending: _PendingConcentrationFailure,
        *,
        event: TimelineEvent,
        tracker: ConcentrationTracker,
    ) -> None:
        """Reject a foreign, stale, or rewritten pending failure before mutation."""

        try:
            computed_sha256 = pending.computed_sha256()
        except Exception as error:
            raise ControlEngineError(
                "Pending concentration failure is malformed or rewritten"
            ) from error
        if (
            not isinstance(pending, _PendingConcentrationFailure)
            or pending is not self._pending_concentration_failure_original
            or pending._issuer is not self._issuer
            or pending.scenario_digest != self._scenario_digest
            or pending.effect_id != self._program.effect_id
            or pending.invocation_id != self._invocation_id
            or pending.source_actor_id != self._source_actor_id
            or pending.pending_sha256 != computed_sha256
            or self._pending_concentration_failure_attestation
            != pending.pending_sha256
        ):
            raise ControlEngineError(
                "Pending concentration failure is foreign, stale, or rewritten"
            )
        if (
            pending.end_event_id != event.event_id
            or pending.end_event_sequence != event.sequence
            or event.kind != "concentration_end"
        ):
            raise ControlEngineError(
                "Pending concentration failure belongs to a different typed end event"
            )
        damage_event = self._schedule.event(pending.damage_event_id)
        if (
            damage_event.sequence != pending.damage_event_sequence
            or damage_event.kind != "damage_context"
            or event.sequence != damage_event.sequence + 1
        ):
            raise ControlEngineError(
                "Pending concentration failure does not bind an immediate typed end"
            )
        malformed_plan = (
            not isinstance(pending.end_plan, tuple)
            or any(
                not isinstance(plan, tuple)
                or len(plan) != 3
                or not all(isinstance(value, str) and value for value in plan)
                for plan in pending.end_plan
            )
        )
        if (
            tuple(sorted(set(pending.affected_target_ids)))
            != pending.affected_target_ids
            or set(pending.affected_target_ids) - set(self._schedule.target_ids)
            or malformed_plan
            or len(set(pending.end_plan)) != len(pending.end_plan)
        ):
            raise ControlEngineError(
                "Pending concentration failure has malformed affected targets or plan"
            )
        for value in (
            pending.check_record_json,
            pending.tracker_pre_state_json,
            pending.tracker_post_check_state_json,
            pending.tracker_end_record_json,
            pending.authority_metadata_json,
        ):
            if _canonical_json(json.loads(value)) != value:
                raise ControlEngineError(
                    "Pending concentration failure serialization is not canonical"
                )
        if (
            self._concentration_tracker_state_json(tracker)
            != pending.tracker_post_check_state_json
        ):
            raise ControlEngineError(
                "Pending concentration failure tracker continuity is stale"
            )
        record_index = pending.check_operation_sequence - 1
        if record_index < 0 or record_index >= len(self._issued_records):
            raise ControlEngineError(
                "Pending concentration failure lacks its issued check record"
            )
        issued = self._issued_records[record_index]
        self._require_locally_issued_record(issued)
        if (
            issued.record_kind != "concentration_check_pending_end"
            or issued.event_id != pending.damage_event_id
            or issued.event_sequence != pending.damage_event_sequence
            or json.loads(issued.payload_json) != {
                "kind": "concentration_check_pending_end",
                "pending_failure": pending.to_dict(),
            }
        ):
            raise ControlEngineError(
                "Pending concentration failure does not match its issued check"
            )

    def _bound_input(
        self,
        name: str,
        *,
        target_id: str | None = None,
        default: Any = _MISSING,
    ) -> Any:
        if self._current_event is None:
            raise ControlEngineError("No schedule event is currently open")
        event_inputs = self._operation_inputs(self._current_event.event_id)
        if name in event_inputs:
            return event_inputs[name]
        if target_id is not None:
            mechanics = self._target_mechanics(target_id)
            per_event_name = f"{name}_by_event"
            per_event = mechanics.get(per_event_name)
            if isinstance(per_event, Mapping) and self._current_event.event_id in per_event:
                return per_event[self._current_event.event_id]
            if name in mechanics:
                return mechanics[name]
        if default is not _MISSING:
            return default
        raise ControlEngineError(
            f"Scenario does not bind {name!r} for event "
            f"{self._current_event.event_id!r}"
        )

    def _require_current(
        self,
        *,
        target_id: str | None = None,
        kinds: Iterable[str] | None = None,
    ) -> TimelineEvent:
        self._validate_scenario_identity()
        self._validate_ambient_membership_state()
        event = self._current_event
        if event is None:
            raise ControlEngineError(
                "Operation requires an explicitly advanced, open schedule event"
            )
        if target_id is not None:
            target = _identifier(target_id, "target_id")
            if target not in self._known_actor_ids:
                raise ControlEngineError(f"Unknown session actor: {target!r}")
            if (
                event.target_id is not None
                and event.target_id != target
                and event.actor_id != target
            ):
                raise ControlEngineError(
                    f"Current event neither targets nor belongs to {target!r}"
                )
        if kinds is not None and event.kind not in set(kinds):
            raise ControlEngineError(
                f"Current event {event.event_id!r} has kind {event.kind!r}, "
                f"expected one of {sorted(set(kinds))!r}"
            )
        return event

    def _issue(
        self,
        *,
        record_kind: str,
        payload: Any,
        pre_operation_state_json: str,
        pre_operation_route_state_json: str | None = None,
        target_id: str | None = None,
    ) -> _IssuedControlRecord:
        event = self._require_current(target_id=target_id)
        if self._current_pre_state_json is None:  # pragma: no cover - invariant
            raise ControlEngineError("Current event has no pre-event snapshot")
        if self._current_pre_route_state_json is None:  # pragma: no cover
            raise ControlEngineError("Current event has no pre-event route snapshot")
        pre_route_json = (
            self._area_route_state_json()
            if pre_operation_route_state_json is None
            else pre_operation_route_state_json
        )
        payload_json = _canonical_json(payload)
        normalized_kind = _identifier(record_kind, "record_kind")
        if normalized_kind not in _SESSION_RECORD_KINDS:
            raise ControlEngineError(
                f"Unsupported session record kind: {normalized_kind!r}"
            )
        self._operation_sequence += 1
        post_operation_state_json = _canonical_json(self._state.snapshot())
        post_operation_route_state_json = self._area_route_state_json()
        record_identity = {
            "scenario_digest": self._scenario_digest,
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "operation_sequence": self._operation_sequence,
            "target_id": target_id,
            "record_kind": normalized_kind,
            "pre_event_state": json.loads(self._current_pre_state_json),
            "pre_operation_state": json.loads(pre_operation_state_json),
            "post_operation_state": json.loads(post_operation_state_json),
            "pre_event_route_state": json.loads(
                self._current_pre_route_state_json
            ),
            "pre_operation_route_state": json.loads(pre_route_json),
            "post_operation_route_state": json.loads(
                post_operation_route_state_json
            ),
            "payload": json.loads(payload_json),
        }
        record = _IssuedControlRecord(
            scenario_digest=self._scenario_digest,
            event_id=event.event_id,
            event_sequence=event.sequence,
            operation_sequence=self._operation_sequence,
            target_id=target_id,
            record_kind=normalized_kind,
            pre_event_state_json=self._current_pre_state_json,
            pre_operation_state_json=pre_operation_state_json,
            post_operation_state_json=post_operation_state_json,
            pre_event_route_state_json=self._current_pre_route_state_json,
            pre_operation_route_state_json=pre_route_json,
            post_operation_route_state_json=post_operation_route_state_json,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            record_sha256=_sha256_record(record_identity),
            _issuer=self._issuer,
        )
        self._issued_records.append(record)
        self._issued_record_originals.append(record)
        self._issued_record_attestations.append(record.record_sha256)
        self._cached_result = None
        return record

    def _require_locally_issued_record(
        self,
        record: _IssuedControlRecord,
    ) -> None:
        """Reject a foreign, replaced, or rewritten record before live use."""

        index = record.operation_sequence - 1
        if (
            record._issuer is not self._issuer
            or record.scenario_digest != self._scenario_digest
            or index < 0
            or index >= len(self._issued_records)
            or index >= len(self._issued_record_originals)
            or index >= len(self._issued_record_attestations)
            or self._issued_records[index] is not record
            or self._issued_record_originals[index] is not record
            or self._issued_record_attestations[index] != record.record_sha256
            or hashlib.sha256(record.payload_json.encode("utf-8")).hexdigest()
            != record.payload_sha256
        ):
            raise ControlEngineError(
                "Live operation record is foreign, replaced, or differs from "
                "its local issuance attestation"
            )
        record_identity = {
            "scenario_digest": record.scenario_digest,
            "event_id": record.event_id,
            "event_sequence": record.event_sequence,
            "operation_sequence": record.operation_sequence,
            "target_id": record.target_id,
            "record_kind": record.record_kind,
            "pre_event_state": json.loads(record.pre_event_state_json),
            "pre_operation_state": json.loads(record.pre_operation_state_json),
            "post_operation_state": json.loads(record.post_operation_state_json),
            "pre_event_route_state": json.loads(
                record.pre_event_route_state_json
            ),
            "pre_operation_route_state": json.loads(
                record.pre_operation_route_state_json
            ),
            "post_operation_route_state": json.loads(
                record.post_operation_route_state_json
            ),
            "payload": json.loads(record.payload_json),
        }
        if _sha256_record(record_identity) != record.record_sha256:
            raise ControlEngineError(
                "Live operation record envelope differs from its local issuance"
            )

    def _active_area_component_ids(self, target_id: str) -> tuple[str, ...]:
        bindings = self._engine._compiled_area_bindings(self._program)
        return tuple(sorted({
            component.component_id
            for component in self._state.active_components(target_id)
            if component.effect_id == self._program.effect_id
            and component.component_id in bindings
        }))

    def _outside_membership_ambient_suppressions(
        self,
        *,
        gate: Any,
        branch: Any,
        target_id: str,
        event: TimelineEvent,
    ) -> tuple[dict[str, Any], ...]:
        """Derive activation applications barred by authoritative membership."""

        return self._outside_membership_ambient_suppressions_from_routes(
            gate=gate,
            branch=branch,
            target_id=target_id,
            event=event,
            route_rows=self._area_route_state_rows(),
        )

    def _outside_membership_ambient_suppressions_from_routes(
        self,
        *,
        gate: Any,
        branch: Any,
        target_id: str,
        event: TimelineEvent,
        route_rows: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        """Purely derive membership filtering from one attested route snapshot."""

        if gate.trigger.kind != "activation":
            return ()
        rows: list[dict[str, Any]] = []
        for area_id in sorted(self._persistent_area_ids):
            ambient_ids = set(self._ambient_area_component_ids(
                area_id=area_id,
                target_id=target_id,
            ))
            component_ids = sorted(ambient_ids & set(branch.applies))
            if not component_ids:
                continue
            matches = [
                row for row in route_rows
                if row.get("effect_id") == self._program.effect_id
                and row.get("area_id") == area_id
                and row.get("target_id") == target_id
            ]
            if len(matches) != 1:
                raise ControlEngineError(
                    "Ambient area application lacks authoritative area-route "
                    f"state for target {target_id!r} and area {area_id!r}"
                )
            if matches[0].get("membership") is True:
                continue
            if matches[0].get("membership") is not False:
                raise ControlEngineError(
                    "Ambient area application has malformed authoritative "
                    "membership state"
                )
            rows.extend({
                "kind": "outside_compiled_area_membership",
                "effect_id": self._program.effect_id,
                "area_id": area_id,
                "target_id": target_id,
                "source_gate_id": gate.gate_id,
                "source_branch_id": branch.branch_id,
                "component_id": component_id,
                "authoritative_membership": False,
                "event_id": event.event_id,
                "event_sequence": event.sequence,
            } for component_id in component_ids)
        return tuple(rows)

    def _validate_branch_area_application_membership(
        self,
        *,
        branch: Any,
        target_id: str,
        suppressed_component_ids: Iterable[str],
    ) -> None:
        """Reject impossible nonmember area applications before state mutation."""

        suppressed = set(suppressed_component_ids)
        bindings = self._engine._compiled_area_bindings(self._program)
        for component_id in branch.applies:
            component = self._program.component(component_id)
            if (
                component.choice_id is not None
                and self._choices[component.choice_id]
                != component.choice_option_id
            ):
                continue
            if not any(
                target_id in self._membership[selector_id]
                for selector_id in component.target_selector_ids
            ):
                continue
            for area_id in bindings.get(component_id, ()):
                route_state = self._area_route_state_or_none(
                    target_id,
                    area_id=area_id,
                )
                if route_state is None:
                    raise ControlEngineError(
                        "Area-bound branch application lacks authoritative "
                        f"area-route state for target {target_id!r}"
                    )
                if (
                    not route_state.membership
                    and component_id not in suppressed
                ):
                    raise ControlEngineError(
                        "Nonmember area-bound branch application is forbidden "
                        "before state mutation: "
                        f"target={target_id!r}, area={area_id!r}, "
                        f"component={component_id!r}"
                    )

    def _plan_reachable_gate(
        self,
        *,
        gate_id: str,
        target_id: str,
        after_sequence: int,
    ) -> tuple[TimelineEvent, str, bool]:
        gate = self._program.gate(gate_id)
        self._require_area_gate_eligible(
            gate_id=gate.gate_id,
            target_id=target_id,
        )
        bindings = json.loads(self._reliability_timeline_bindings_json)
        matching_events: list[TimelineEvent] = []
        for gate_row in self._reliability.gate_probabilities:
            if (
                gate_row.gate_id != gate.gate_id
                or gate_row.probability <= 0
                or (
                    gate_row.target_ids
                    and target_id not in gate_row.target_ids
                )
                or gate_row.event_id not in bindings
            ):
                continue
            candidate = self._schedule.event(bindings[gate_row.event_id])
            if candidate.sequence < after_sequence:
                continue
            same_event_continuation = (
                self._current_event is not None
                and candidate.event_id == self._current_event.event_id
                and gate.trigger.kind
                in {"save", "damage_context", "instantaneous_resolution"}
            )
            try:
                matches = same_event_continuation or typed_event_matches(
                    candidate,
                    gate.trigger.data.to_dict(),
                    target_id=target_id,
                    triggering_turn_id=candidate.turn_id,
                )
            except (TimelineError, TypeError, ValueError):
                matches = False
            if matches and candidate.target_id in {None, target_id}:
                matching_events.append(candidate)
        matching_events.sort(key=lambda row: row.sequence)
        matching_events = list({
            row.event_id: row for row in matching_events
        }.values())
        if not matching_events:
            raise ControlEngineError(
                f"Reachable gate {gate_id!r} for target {target_id!r} has no "
                "remaining bound reliability/timeline event"
            )
        selected = matching_events[0]
        label = (
            f"concentration_end:{gate_id}:{target_id}"
            if gate.trigger.kind == "concentration_end"
            else f"branch:{gate_id}:{target_id}"
        )
        same_event = bool(
            self._current_event is not None
            and selected.event_id == self._current_event.event_id
        )
        allow_trigger_override = bool(
            same_event
            and gate.trigger.kind
            in {"save", "damage_context", "instantaneous_resolution"}
        )
        return selected, label, allow_trigger_override

    def _commit_reachable_gate(
        self,
        plan: tuple[TimelineEvent, str, bool],
        *,
        gate_id: str,
        target_id: str,
    ) -> None:
        selected, label, allow_trigger_override = plan
        gate = self._program.gate(gate_id)
        opportunity_label = (
            f"opportunity_roll:save:{target_id}"
            if gate.resolution_kind == "saving_throw"
            else f"opportunity_roll:attack:{target_id}"
            if gate.resolution_kind == "attack_roll"
            else None
        )
        if (
            self._current_event is not None
            and selected.event_id == self._current_event.event_id
        ):
            self._current_required_operations.add(label)
            if opportunity_label is not None:
                self._current_required_operations.add(opportunity_label)
            if allow_trigger_override:
                self._same_event_gate_overrides.add((gate_id, target_id))
        else:
            self._future_required_operations.setdefault(
                selected.event_id,
                set(),
            ).add(label)
            if opportunity_label is not None:
                self._future_required_operations.setdefault(
                    selected.event_id,
                    set(),
                ).add(opportunity_label)

    def _current_resolution_gate_ids(
        self,
        *,
        resolution_kind: str,
        target_id: str,
    ) -> tuple[str, ...]:
        """Return exact currently required gates for one roll target."""

        target = _identifier(target_id, "opportunity target_id")
        gate_ids: set[str] = set()
        for operation in self._current_required_operations:
            if not operation.startswith("branch:"):
                continue
            parts = operation.split(":", 2)
            if len(parts) not in {2, 3}:
                continue
            gate = self._program.gate(parts[1])
            operation_target = (
                parts[2]
                if len(parts) == 3
                else (
                    self._current_event.target_id
                    if self._current_event is not None else None
                )
            )
            if (
                operation_target == target
                and gate.resolution_kind == resolution_kind
            ):
                gate_ids.add(gate.gate_id)
        return tuple(sorted(gate_ids))

    def _next_gate_targets(
        self,
        gate: Any,
        next_gate: Any,
        target_id: str,
    ) -> tuple[str, ...]:
        """Mirror graph evaluator selector-overlap target propagation exactly."""

        selected: list[str] = []
        source_selectors = set(gate.selector_ids)
        for selector_id in next_gate.selector_ids:
            for scheduled_target in self._membership[selector_id]:
                if (
                    selector_id in source_selectors
                    and scheduled_target != target_id
                ):
                    continue
                if scheduled_target not in selected:
                    selected.append(scheduled_target)
        return tuple(sorted(selected))

    def advance(
        self,
        event_id: str | _SessionEventReference,
    ) -> TimelineEvent:
        """Advance exactly one schedule position; skipping is never implicit."""

        self._validate_scenario_identity()
        self._validate_ambient_membership_state()
        if isinstance(event_id, _SessionEventReference):
            if (
                event_id._issuer is not self._issuer
                or event_id.scenario_digest != self._scenario_digest
            ):
                raise ControlEngineError(
                    "Schedule event reference belongs to another execution session"
                )
            event_name = event_id.event_id
        else:
            event_name = _identifier(event_id, "event_id")
        try:
            event = self._schedule.event(event_name)
        except TimelineError as error:
            raise ControlEngineError(f"Unknown session event ID: {event_name!r}") from error
        if (
            isinstance(event_id, _SessionEventReference)
            and event.sequence != event_id.event_sequence
        ):
            raise ControlEngineError("Schedule event reference is stale or malformed")
        if self._current_event is not None:
            raise ControlEngineError(
                f"Event {self._current_event.event_id!r} must be explicitly closed "
                "before advancing"
            )
        if event.sequence <= self._cursor:
            raise ControlEngineError(
                f"Cannot move the session cursor backward to event {event_name!r}"
            )
        expected_sequence = self._cursor + 1
        if event.sequence != expected_sequence:
            expected = self._schedule.events[expected_sequence]
            raise ControlEngineError(
                f"Cannot skip future event {expected.event_id!r}; advance it first"
            )

        self._current_event = event
        self._current_event_expiry_complete = False
        self._current_pre_state_json = _canonical_json(self._state.snapshot())
        self._current_pre_route_state_json = self._area_route_state_json()
        self._current_required_operations = set(
            json.loads(self._required_operation_plan_json).get(event.event_id, ())
        )
        self._current_required_operations.update(
            self._future_required_operations.pop(event.event_id, set())
        )
        if event.kind in {"condition_application", "condition_end"}:
            self._current_required_operations.add(event.kind)
        elif event.kind in {
            "attack_opportunity",
            "controller_attack_opportunity",
            "target_attack_opportunity",
            "save_opportunity",
            "initiative_opportunity",
        }:
            self._current_required_operations.add("opportunity_roll")
        elif event.kind == "action_proposal":
            self._current_required_operations.add("action_legality")
        elif event.kind == "fall_transition":
            self._current_required_operations.add("fall_transition")
        for (entry_event_id, target_id), transition in (
            self._area_entry_transitions.items()
        ):
            if (
                entry_event_id != event.event_id
                or self._area_effect_is_active(transition.area_id)
            ):
                continue
            self._current_required_operations.discard(
                f"area_entry:{target_id}"
            )
            for gate_id in self._entry_gate_ids(transition):
                self._current_required_operations.discard(
                    f"branch:{gate_id}:{target_id}"
                )
                self._current_required_operations.discard(
                    f"branch:{gate_id}"
                )
        pre_event_rows = json.loads(self._current_pre_state_json)
        for operation in tuple(self._current_required_operations):
            if not operation.startswith(("branch:", "concentration_end:")):
                continue
            parts = operation.split(":", 2)
            gate = self._program.gate(parts[1])
            target_id = parts[2] if len(parts) == 3 else event.target_id
            if target_id is None:
                continue
            bound_entry = self._area_entry_transitions.get(
                (event.event_id, target_id)
            )
            same_event_entry = bool(
                gate.trigger.kind == "entry"
                and bound_entry is not None
                and bound_entry.area_id
                in self._canonical_area_gate_bindings().get(gate.gate_id, ())
            )
            if not same_event_entry:
                area_eligible, _area_reason = self._area_gate_eligibility(
                    gate_id=gate.gate_id,
                    target_id=target_id,
                )
                if not area_eligible:
                    self._current_required_operations.discard(operation)
                    continue
            if not gate.requires_active_component_ids:
                continue
            active_ids = {
                row["component_id"]
                for row in pre_event_rows
                if row.get("target_id") == target_id
                and row.get("effect_id") == self._program.effect_id
            }
            if set(gate.requires_active_component_ids) - active_ids:
                self._current_required_operations.discard(operation)
        for operation in tuple(self._current_required_operations):
            if not operation.startswith("branch:"):
                continue
            parts = operation.split(":", 2)
            gate = self._program.gate(parts[1])
            operation_target = (
                parts[2] if len(parts) == 3 else event.target_id
            )
            if operation_target is None:
                continue
            if gate.resolution_kind == "saving_throw":
                self._current_required_operations.add(
                    f"opportunity_roll:save:{operation_target}"
                )
            elif gate.resolution_kind == "attack_roll":
                self._current_required_operations.add(
                    f"opportunity_roll:attack:{operation_target}"
                )
        self._movement_response_consumed = False
        self._movement_response_required = False
        if event.kind == "target_movement_opportunity" and event.target_id is not None:
            target = event.target_id
            prone = any(
                component.magnitude.get("kind") == "condition"
                and component.magnitude.get("condition") == "prone"
                for component in self._state.active_components(target)
            )
            area_component_ids = self._active_area_component_ids(target)
            route_state = self._area_route_state_or_none(target)
            if area_component_ids and route_state is None:
                raise ControlEngineError(
                    "Active area-bound components lack authoritative live area "
                    f"membership for target {target!r}"
                )
            live_area_membership = bool(
                route_state is not None
                and route_state.membership
                and self._area_effect_is_active(route_state.area_id)
            )
            self._movement_response_required = bool(
                prone
                or (
                    self._area_response_convention == "shortest_route_v1"
                    and live_area_membership
                )
                or (
                    self._area_response_convention != "shortest_route_v1"
                    and bool(area_component_ids)
                    and route_state is not None
                    and (
                        route_state.membership
                        and self._area_effect_is_active(route_state.area_id)
                    )
                )
                or target in self._displaced_targets
            )
        if (
            event.kind == "concentration_end"
            and self._concentration_tracker is not None
            and self._concentration_tracker.active_effect_id
            == self._program.effect_id
        ):
            self._current_required_operations.add("concentration_end")
        return event

    def advance_to(self, event_id: str) -> TimelineEvent:
        """Advance through inert events, stopping if an operation is required."""

        target = self._schedule.event(_identifier(event_id, "event_id"))
        while self._cursor < target.sequence:
            next_event = self._schedule.events[self._cursor + 1]
            self.advance(next_event.event_id)
            if next_event.sequence == target.sequence:
                return next_event
            self.close_event()
        raise ControlEngineError(
            f"Event {event_id!r} is not later than the current cursor"
        )

    def close_event(self) -> _ClosedEventSnapshot:
        event = self._require_current()
        # Expiry is an engine-owned end-of-event operation, never a caller task.
        self._current_required_operations.discard("component_expiry")
        unresolved: list[str] = []
        unresolved.extend(sorted(self._current_required_operations))
        if self._pending_displacements:
            unresolved.append("instantaneous displacement")
        if self._movement_response_required and not self._movement_response_consumed:
            unresolved.append("target movement response")
        if (
            self._pending_concentration_failure is not None
            and self._pending_concentration_failure.end_event_id
            == event.event_id
        ):
            unresolved.append("concentration end")
        if unresolved:
            raise ControlEngineError(
                f"Event {event.event_id!r} has unresolved required operations: "
                f"{', '.join(unresolved)}"
            )
        if self._current_pre_state_json is None:  # pragma: no cover
            raise ControlEngineError("Current event has no pre-event snapshot")
        pre_expiry = _canonical_json(self._state.snapshot())
        self._current_event_expiry_complete = True
        expired = self._state.expire(
            event.event_id,
            event_sequence=event.sequence,
        )
        if expired:
            self._issue(
                record_kind="component_expiry",
                target_id=event.target_id,
                pre_operation_state_json=pre_expiry,
                payload={
                    "kind": "component_expiry",
                    "event_id": event.event_id,
                    "expired_instance_ids": [item.instance_id for item in expired],
                    "expired_component_ids": sorted({
                        item.component_id for item in expired
                    }),
                },
            )
        if event.kind == "activation" and not self._concentration_required:
            self._area_effect_started = True
            self._area_effect_ended = False
        self._validate_ambient_membership_state()
        self._current_required_operations.discard("component_expiry")
        snapshot = _ClosedEventSnapshot(
            scenario_digest=self._scenario_digest,
            event_id=event.event_id,
            event_sequence=event.sequence,
            pre_event_state_json=self._current_pre_state_json,
            post_event_state_json=_canonical_json(self._state.snapshot()),
            pre_event_route_state_json=self._current_pre_route_state_json,
            post_event_route_state_json=self._area_route_state_json(),
        )
        self._event_snapshots.append(snapshot)
        self._cursor = event.sequence
        self._current_event = None
        self._current_event_expiry_complete = False
        self._current_pre_state_json = None
        self._current_pre_route_state_json = None
        self._current_required_operations = set()
        self._cached_result = None
        return snapshot

    def complete(self) -> None:
        """Consume all remaining inert events without inventing operations."""

        if self._current_event is not None:
            self.close_event()
        while self._cursor + 1 < len(self._schedule.events):
            event = self._schedule.events[self._cursor + 1]
            self.advance(event.event_id)
            self.close_event()

    def apply_branch(
        self,
        *,
        gate_id: str,
        outcome: str,
        target_id: str,
    ) -> _IssuedControlRecord:
        event = self._require_current(target_id=target_id)
        gate = self._program.gate(_identifier(gate_id, "gate_id"))
        mutation_target_ids = {target_id}
        if gate.gate_scope == "shared":
            for operation in self._current_required_operations:
                parts = operation.split(":", 2)
                if (
                    len(parts) == 3
                    and parts[0] == "branch"
                    and parts[1] == gate.gate_id
                ):
                    mutation_target_ids.add(parts[2])
        self._require_pending_normalization_complete_before_mutation(
            *mutation_target_ids
        )
        if gate.trigger.kind == "concentration_end":
            raise ControlEngineError(
                "Concentration-end gates are owned by end_concentration()"
            )
        if gate.trigger.kind == "entry":
            self._require_entry_gate_attested(
                gate_id=gate.gate_id,
                target_id=target_id,
                event=event,
            )
        self._require_area_gate_eligible(
            gate_id=gate.gate_id,
            target_id=target_id,
        )
        observed_outcome = _identifier(outcome, "outcome")
        pre_event_rows = json.loads(self._current_pre_state_json or "[]")
        active_guard_ids = {
            row["component_id"]
            for row in pre_event_rows
            if row.get("target_id") == target_id
            and row.get("effect_id") == self._program.effect_id
        }
        missing_guards = sorted(
            set(gate.requires_active_component_ids) - active_guard_ids
        )
        if missing_guards:
            raise ControlEngineError(
                f"Gate {gate.gate_id!r} source component was absent from the "
                f"pre-event state: {missing_guards}"
            )
        if self._concentration_required and (
            self._concentration_tracker is None
            or self._concentration_tracker.active_effect_id
            != self._program.effect_id
        ):
            raise ControlEngineError(
                "Concentration startup must execute before concentration-program "
                "branches"
            )
        exact_requirement = f"branch:{gate.gate_id}:{target_id}"
        shared_requirement = f"branch:{gate.gate_id}"
        if not ({exact_requirement, shared_requirement} & self._current_required_operations):
            raise ControlEngineError(
                f"Gate {gate.gate_id!r}/{target_id!r} is not a required "
                "operation at the current event"
            )
        save_automatic_failure = False
        if gate.resolution_kind == "saving_throw":
            opportunity_rows = [
                row
                for row in self._opportunity_roll_records
                if row.get("kind") == "save_opportunity"
                and row.get("event_id") == event.event_id
                and row.get("actor_id") == target_id
                and gate.gate_id in row.get("save_gate_ids", ())
            ]
            if len(opportunity_rows) != 1:
                raise ControlEngineError(
                    "A save gate requires its exact live save-opportunity "
                    "resolution before branch execution"
                )
            if (
                opportunity_rows[0].get("automatic_failure") is True
                and observed_outcome != "save_failure"
            ):
                raise ControlEngineError(
                    "An automatically failed save cannot execute a success branch"
                )
            save_automatic_failure = (
                opportunity_rows[0].get("automatic_failure") is True
            )
        elif gate.resolution_kind == "attack_roll":
            opportunity_rows = [
                row
                for row in self._opportunity_roll_records
                if row.get("kind") == "attack_opportunity"
                and row.get("event_id") == event.event_id
                and row.get("defender_id") == target_id
                and gate.gate_id in row.get("attack_gate_ids", ())
            ]
            if len(opportunity_rows) != 1:
                raise ControlEngineError(
                    "An attack-roll gate requires its exact live attack "
                    "opportunity before branch execution"
                )
            if opportunity_rows[0].get("roll_created") is not True:
                raise ControlEngineError(
                    "A prohibited attack cannot execute an attack-roll branch"
                )
        branch = gate.branch_for_outcome(observed_outcome)
        reliability_bindings = json.loads(
            self._reliability_timeline_bindings_json
        )
        possible_observation = (
            save_automatic_failure
            and observed_outcome == "save_failure"
        ) or any(
            row.gate_id == gate.gate_id
            and row.branch_id == branch.branch_id
            and row.outcome == observed_outcome
            and row.probability > 0
            and reliability_bindings.get(row.event_id) == event.event_id
            and (not row.target_ids or target_id in row.target_ids)
            for row in self._reliability.branch_probabilities
        )
        if not possible_observation:
            raise ControlEngineError(
                f"Observed branch {branch.branch_id!r} has zero or absent "
                "probability in the bound reliability event"
            )
        shared_key = (event.event_id, gate.gate_id)
        if gate.gate_scope == "shared":
            prior_outcome = self._shared_gate_outcomes.get(shared_key)
            if prior_outcome is not None and prior_outcome != observed_outcome:
                raise ControlEngineError(
                    f"Shared gate {gate.gate_id!r} already resolved as "
                    f"{prior_outcome!r} at this event"
                )
        next_gate_plans: list[
            tuple[str, str, tuple[TimelineEvent, str, bool]]
        ] = []
        for next_gate_id in branch.next_gate_ids:
            next_gate = self._program.gate(next_gate_id)
            next_targets = self._next_gate_targets(gate, next_gate, target_id)
            if not next_targets:
                continue
            for next_target in next_targets:
                next_eligible, _next_reason = self._area_gate_eligibility(
                    gate_id=next_gate.gate_id,
                    target_id=next_target,
                )
                if not next_eligible:
                    continue
                next_gate_plans.append((
                    next_gate.gate_id,
                    next_target,
                    self._plan_reachable_gate(
                        gate_id=next_gate.gate_id,
                        target_id=next_target,
                        after_sequence=event.sequence,
                    ),
                ))
        outside_membership_suppressions = (
            self._outside_membership_ambient_suppressions(
                gate=gate,
                branch=branch,
                target_id=target_id,
                event=event,
            )
        )
        self._validate_branch_area_application_membership(
            branch=branch,
            target_id=target_id,
            suppressed_component_ids=(
                row["component_id"]
                for row in outside_membership_suppressions
            ),
        )
        pre = _canonical_json(self._state.snapshot())
        before_registry_ids = {
            row["instance_id"] for row in self._state.instance_registry()
        }
        branch_issuance_id = (
            f"{self._scenario_digest}:{event.event_id}:branch:"
            f"{gate.gate_id}:{target_id}:{self._operation_sequence + 1}"
        )
        branch_application = dict(
            effect=self._program,
            gate_id=gate_id,
            outcome=outcome,
            target_id=target_id,
            source_actor_id=self._source_actor_id,
            event_id=event.event_id,
            invocation_id=self._invocation_id,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            choices=self._choices,
            condition_immunities=self._targets_by_id[target_id].condition_immunities,
            _active_guard_snapshot=json.loads(
                self._current_pre_state_json or "[]"
            ),
            _allow_reachable_same_event=(
                gate.gate_id,
                target_id,
            ) in self._same_event_gate_overrides,
            _suppressed_application_component_ids=tuple(
                row["component_id"]
                for row in outside_membership_suppressions
            ),
            source_program_id=self._program.effect_id,
            issuance_id=branch_issuance_id,
            provenance_id=self._scenario_digest,
        )

        # Condition activation, any destructive concentration cleanup, and the
        # corresponding fall decision form one event transaction.  Run the
        # complete state portion against an isolated copy before mutating the
        # live session so an invalid child lineage, source, duration, or cleanup
        # plan cannot leave a partial branch behind.
        preview_state = deepcopy(self._state)
        try:
            preview_transition = self._engine._apply_resolved_branch(
                state=preview_state,
                **branch_application,
            )
        except (ControlStateError, ControlEngineError, TypeError, ValueError) as error:
            raise ControlEngineError(
                f"Branch transition failed atomic preflight: {error}"
            ) from error
        preview_new_instances = tuple(
            row
            for row in preview_state.instance_registry()
            if row["instance_id"] not in before_registry_ids
        )
        applies_fall_condition = any(
            row["condition_id"] in {"prone", "incapacitated"}
            for row in preview_new_instances
        )
        fly_speed_zero_sources, pre_transition_fly_speed = (
            self._fly_speed_zero_transition_sources(
                before_state=self._state,
                after_state=preview_state,
                target_id=target_id,
            )
        )
        fall_context = self._validated_fall_context(
            self._bound_input(
                "fall_context",
                target_id=target_id,
                default=None,
            ),
            required=applies_fall_condition or bool(fly_speed_zero_sources),
        )
        if (
            fly_speed_zero_sources
            and fall_context is not None
            and fall_context["fly_speed_ft"] != pre_transition_fly_speed
        ):
            raise ControlEngineError(
                "fall_context.fly_speed_ft differs from pre-transition Fly Speed"
            )

        tracker = self._concentration_tracker
        concentration_preview: tuple[
            _ConcentrationAuthorityContext,
            tuple[tuple[str, str, str], ...],
            Mapping[str, Any],
            Mapping[str, Any],
        ] | None = None
        applies_incapacitated = any(
            row["condition_id"] == "incapacitated"
            for row in preview_new_instances
        )
        if (
            applies_incapacitated
            and tracker is not None
            and tracker.active_effect_id is not None
            and tracker.owner_actor_id == target_id
        ):
            context = self._engine._active_concentration_context(
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                choices=self._choices,
            )
            plans = self._engine._concentration_end_plan(
                state=preview_state,
                context=context,
                event_id=event.event_id,
                reason="controller_incapacitated",
            )
            affected = self._concentration_end_mutation_target_ids(
                context=context,
                plans=plans,
            )
            self._require_pending_normalization_complete_before_mutation(*affected)
            preview_tracker = deepcopy(tracker)
            end_record = preview_tracker.end(
                reason="controller_incapacitated",
                event_id=event.event_id,
                owner_actor_id=target_id,
            )
            cleanup_transition = self._engine._apply_concentration_end_record(
                state=preview_state,
                record=end_record,
                context=context,
                plans=plans,
            )
            concentration_preview = (
                context,
                plans,
                end_record,
                cleanup_transition,
            )

        fall_record = self._condition_application_fall_record(
            event=event,
            target_id=target_id,
            new_instances=preview_new_instances,
            fall_context=fall_context,
            fly_speed_zero_sources=fly_speed_zero_sources,
        )

        transition = self._engine._apply_resolved_branch(
            state=self._state,
            **branch_application,
        )
        if transition != preview_transition:
            raise ControlEngineError(
                "Branch transition differed from its atomic preflight"
            )
        committed_new_instances = tuple(
            row
            for row in self._state.instance_registry()
            if row["instance_id"] not in before_registry_ids
        )
        if committed_new_instances != preview_new_instances:
            raise ControlEngineError(
                "Branch condition lineage differed from its atomic preflight"
            )

        concentration_record: dict[str, Any] | None = None
        if concentration_preview is not None:
            if tracker is None:  # pragma: no cover - guarded above
                raise ControlEngineError("Concentration tracker disappeared")
            context, plans, expected_end, expected_cleanup = concentration_preview
            end_record = tracker.end(
                reason="controller_incapacitated",
                event_id=event.event_id,
                owner_actor_id=target_id,
            )
            if end_record != expected_end:
                raise ControlEngineError(
                    "Concentration end differed from its atomic preflight"
                )
            cleanup_transition = self._engine._apply_concentration_end_record(
                state=self._state,
                record=end_record,
                context=context,
                plans=plans,
            )
            if cleanup_transition != expected_cleanup:
                raise ControlEngineError(
                    "Concentration cleanup differed from its atomic preflight"
                )
            self._engine._concentration_contexts.pop(tracker, None)
            concentration_record = {
                "kind": "condition_concentration_end",
                "condition_instance_ids": sorted(
                    row["instance_id"]
                    for row in committed_new_instances
                    if row["condition_id"] == "incapacitated"
                ),
                "owner_actor_id": target_id,
                "tracker_end_record": end_record,
                "cleanup_transition": cleanup_transition,
                "active_effect_id": None,
            }
            self._concentration_records.append(
                dict(_json_safe(cleanup_transition))
            )
            self._condition_concentration_records.append(concentration_record)
            self._area_effect_ended = True

        if fall_record is not None:
            if fall_record["executed"]:
                self._fall_transition_identities.add((event.event_id, target_id))
            self._fall_transition_records.append(fall_record)
        transition.update({
            "created_condition_instances": list(committed_new_instances),
            "condition_concentration_end": concentration_record,
            "fall_transition": fall_record,
            "active_conditions_after": list(
                self._state.derived_current_conditions(target_id)
            ),
            "active_components_after": self._state.snapshot(target_id),
        })
        transition["outside_compiled_area_membership_suppressions"] = [
            dict(row) for row in outside_membership_suppressions
        ]
        self._same_event_gate_overrides.discard((gate.gate_id, target_id))
        if gate.gate_scope == "shared":
            self._shared_gate_outcomes[shared_key] = observed_outcome
        if tuple(transition.get("next_gate_ids", ())) != branch.next_gate_ids:
            raise ControlEngineError(
                "Resolved branch next-gate plan diverged from compiled authority"
            )
        for planned_gate_id, planned_target, plan in next_gate_plans:
            self._commit_reachable_gate(
                plan,
                gate_id=planned_gate_id,
                target_id=planned_target,
            )
        self._current_required_operations.discard(
            f"branch:{_identifier(gate_id, 'gate_id')}"
        )
        self._current_required_operations.discard(
            f"branch:{_identifier(gate_id, 'gate_id')}:{target_id}"
        )
        self._current_required_operations.discard("branch")
        for request in transition.get("pending_displacement_requests", ()):
            self._pending_displacements.add(
                (str(request["target_id"]), str(request["source_component_id"]))
            )
        record = self._issue(
            record_kind="branch_transition",
            payload=transition,
            pre_operation_state_json=pre,
            target_id=target_id,
        )
        if gate.trigger.kind == "activation":
            self._area_effect_started = True
            self._area_effect_ended = False
        self._event_state_transitions.append(transition)
        if concentration_record is not None:
            self._close_area_routes_for_effect_end(
                event=event,
                reason="effect_ended",
            )
        return record

    def normalize(
        self,
        *,
        target_id: str,
    ) -> _IssuedControlRecord:
        event = self._require_current(target_id=target_id)
        context = self._bound_input(
            "normalization_context",
            target_id=target_id,
            default={},
        )
        if not isinstance(context, Mapping):
            raise ControlEngineError("normalization_context must be an object")
        self._require_unchanged_pre_event_normalization_basis(target_id)
        pre = _canonical_json(self._state.snapshot())
        pre_event_rows = json.loads(self._current_pre_state_json or "[]")
        active_sources = {
            (
                f"condition_instance:{row['condition_instance_id']}"
                if row.get("condition_instance_id") is not None
                else f"{row['effect_id']}:{row['component_id']}"
            )
            for row in pre_event_rows
            if row.get("target_id") == target_id
        }
        result = self._engine._normalize_scheduled_window(
            state=self._state,
            schedule=self._schedule,
            target_id=target_id,
            event_id=event.event_id,
            context=context,
        )
        for contribution in result.contributions:
            invalid_sources = [
                source_id
                for source_id in contribution.source_component_ids
                if source_id not in active_sources
                and not source_id.startswith(f"target_sense:{target_id}:")
            ]
            if invalid_sources:
                raise ControlEngineError(
                    "Normalization source was not active in the event pre-state: "
                    f"{invalid_sources}"
                )
        self._normalization_results.append(result)
        self._current_required_operations.discard(f"normalization:{target_id}")
        self._current_required_operations.discard("normalization")
        return self._issue(
            record_kind="normalization",
            payload=result,
            pre_operation_state_json=pre,
            target_id=target_id,
        )

    def _condition_immunities(self, actor_id: str) -> tuple[str, ...]:
        target = self._targets_by_id.get(actor_id)
        return () if target is None else target.condition_immunities

    def _condition_includes_any(
        self,
        condition_id: str,
        candidates: set[str],
    ) -> bool:
        pending = [condition_id]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in candidates:
                return True
            pending.extend(self._engine.catalog.conditions[current].includes)
        return False

    @staticmethod
    def _validated_fall_context(
        value: Mapping[str, Any] | None,
        *,
        required: bool,
    ) -> dict[str, Any] | None:
        if value is None:
            if required:
                raise ControlEngineError(
                    "A Prone, Incapacitated, or Fly-Speed-0 transition "
                    "requires exact fall_context"
                )
            return None
        if not isinstance(value, Mapping):
            raise ControlEngineError("fall_context must be an object")
        expected = {
            "airborne",
            "can_hover",
            "explicit_prevents_fall",
            "fly_speed_ft",
        }
        if set(value) != expected:
            raise ControlEngineError(
                f"fall_context must contain exactly {sorted(expected)}"
            )
        result = _strict_json_copy(value, "fall_context")
        for name in ("airborne", "can_hover", "explicit_prevents_fall"):
            if not isinstance(result[name], bool):
                raise ControlEngineError(f"fall_context.{name} must be boolean")
        fly_speed = result["fly_speed_ft"]
        if (
            fly_speed is not None
            and (
                isinstance(fly_speed, bool)
                or not isinstance(fly_speed, int)
                or fly_speed < 0
            )
        ):
            raise ControlEngineError(
                "fall_context.fly_speed_ft must be a non-negative integer or null"
            )
        return result

    def propose_condition_application(
        self,
        *,
        condition_id: str,
        target_id: str,
        source_actor_id: str,
        source_program_id: str,
        source_effect_id: str,
        source_invocation_id: str,
        source_component_id: str,
        duration: Mapping[str, Any],
        expiry_event_id: str | None = None,
        provenance_id: str | None = None,
        fall_context: Mapping[str, Any] | None = None,
    ) -> _IssuedControlRecord:
        """Issue one immutable, exact-source condition application proposal."""

        event = self._require_current(
            target_id=target_id,
            kinds={"condition_application"},
        )
        target = _identifier(target_id, "target_id")
        condition = _identifier(condition_id, "condition_id")
        if condition not in self._engine.catalog.conditions:
            raise ControlEngineError(f"Unknown condition ID: {condition!r}")
        source_actor = _identifier(source_actor_id, "source_actor_id")
        if condition in {"charmed", "frightened"} and source_actor == target:
            raise ControlEngineError(
                f"{condition!r} requires an exact non-self source actor"
            )
        if condition in self._condition_immunities(target):
            raise ControlEngineError(
                f"Actor {target!r} is immune to condition {condition!r}"
            )
        if not isinstance(duration, Mapping) or not isinstance(
            duration.get("kind"),
            str,
        ):
            raise ControlEngineError("duration must be a typed object")
        duration_record = _strict_json_copy(duration, "duration")
        if expiry_event_id is not None:
            expiry_event_id = _identifier(expiry_event_id, "expiry_event_id")
            try:
                expiry_event = self._schedule.event(expiry_event_id)
            except TimelineError as error:
                raise ControlEngineError(
                    "expiry_event_id is not a session schedule event"
                ) from error
            if expiry_event.sequence < event.sequence:
                raise ControlEngineError(
                    "expiry_event_id precedes the application event"
                )
        requires_condition_fall = self._condition_includes_any(
            condition,
            {"prone", "incapacitated"},
        )
        mechanics = self._target_mechanics(target)
        base_speeds = mechanics.get("base_speeds_ft", {})
        current_fly_speed: int | None = None
        if isinstance(base_speeds, Mapping) and "fly" in base_speeds:
            current_authority = self._engine._movement_state_authority(
                state=self._state,
                target_id=target,
                base_speeds_ft=base_speeds,
                mixed_speed_operation_order=mechanics.get(
                    "mixed_speed_operation_order"
                ),
            )
            current_fly_speed = current_authority["effective_speeds_ft"].get(
                "fly"
            )
        requires_speed_zero_fall = bool(
            condition == "restrained"
            and current_fly_speed is not None
            and current_fly_speed > 0
        )
        fall = self._validated_fall_context(
            fall_context,
            required=requires_condition_fall or requires_speed_zero_fall,
        )
        if (
            fall is not None
            and current_fly_speed is not None
            and fall["fly_speed_ft"] != current_fly_speed
        ):
            raise ControlEngineError(
                "fall_context.fly_speed_ft differs from the live movement state"
            )
        issuance_id = (
            f"{self._scenario_digest}:{event.event_id}:"
            f"condition_proposal:{self._operation_sequence + 1}"
        )
        provenance = _identifier(
            provenance_id or self._scenario_digest,
            "provenance_id",
        )
        identity_fields = {
            "condition_id": condition,
            "target_id": target,
            "source_actor_id": source_actor,
            "source_program_id": _identifier(
                source_program_id,
                "source_program_id",
            ),
            "source_effect_id": _identifier(
                source_effect_id,
                "source_effect_id",
            ),
            "source_invocation_id": _identifier(
                source_invocation_id,
                "source_invocation_id",
            ),
            "source_component_id": _identifier(
                source_component_id,
                "source_component_id",
            ),
            "application_event_id": event.event_id,
            "application_sequence": event.sequence,
            "duration": duration_record,
            "expiry_event_id": expiry_event_id,
            "issuance_id": issuance_id,
            "provenance_id": provenance,
        }
        instance_id = condition_instance_id_for(**identity_fields)
        if instance_id in self._pending_condition_proposals:
            raise ControlEngineError(
                "An identical condition application proposal is already pending"
            )
        pre = _canonical_json(self._state.snapshot())
        proposal = self._issue(
            record_kind="condition_application_proposal",
            payload={
                "kind": "condition_application_proposal",
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "target_id": target,
                "condition_instance": {
                    "instance_id": instance_id,
                    **identity_fields,
                },
                "fall_context": fall,
            },
            pre_operation_state_json=pre,
            target_id=target,
        )
        self._pending_condition_proposals[instance_id] = proposal
        self._current_required_operations.add("condition_application")
        return proposal

    def _require_pending_condition_application(
        self,
        proposal: _IssuedControlRecord,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._require_locally_issued_record(proposal)
        if proposal.record_kind != "condition_application_proposal":
            raise ControlEngineError("record is not a condition application proposal")
        payload = json.loads(proposal.payload_json)
        instance = payload.get("condition_instance")
        if not isinstance(instance, Mapping):
            raise ControlEngineError("Condition proposal payload is malformed")
        instance_id = instance.get("instance_id")
        if (
            not isinstance(instance_id, str)
            or self._pending_condition_proposals.get(instance_id) is not proposal
            or proposal.operation_sequence
            in self._consumed_condition_proposal_sequences
            or proposal.event_id
            != (self._current_event.event_id if self._current_event else None)
            or proposal.post_operation_state_json
            != _canonical_json(self._state.snapshot())
            or proposal.post_operation_route_state_json
            != self._area_route_state_json()
        ):
            raise ControlEngineError(
                "Condition proposal is foreign, stale, consumed, or rewritten"
            )
        identity = {key: value for key, value in instance.items() if key != "instance_id"}
        if condition_instance_id_for(**identity) != instance_id:
            raise ControlEngineError("Condition proposal identity is rewritten")
        return dict(instance), payload

    def _condition_application_fall_record(
        self,
        *,
        event: TimelineEvent,
        target_id: str,
        new_instances: Sequence[Mapping[str, Any]],
        fall_context: Mapping[str, Any] | None,
        fly_speed_zero_sources: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        triggering = [
            row for row in new_instances
            if row["condition_id"] in {"prone", "incapacitated"}
        ]
        speed_sources = tuple(fly_speed_zero_sources)
        if not triggering and not speed_sources:
            return None
        if fall_context is None:  # pragma: no cover - proposal preflight
            raise ControlEngineError("Condition fall context was not bound")
        source_component_ids = sorted(
            {
                str(row["source_component_id"]) for row in triggering
            }
            | {str(component.component_id) for component in speed_sources}
        )
        transition = airborne_fall_transition(
            target_id=target_id,
            airborne=bool(fall_context["airborne"]),
            can_hover=bool(fall_context["can_hover"]),
            prone=any(row["condition_id"] == "prone" for row in triggering),
            incapacitated=any(
                row["condition_id"] == "incapacitated" for row in triggering
            ),
            fly_speed_ft=(
                0 if speed_sources else fall_context["fly_speed_ft"]
            ),
            explicit_prevents_fall=bool(
                fall_context["explicit_prevents_fall"]
            ),
            source_component_id=(
                source_component_ids[0]
                if len(source_component_ids) == 1 else None
            ),
        )
        identity = (event.event_id, target_id)
        duplicate = transition["falls"] and identity in self._fall_transition_identities
        return {
            "kind": "fall_transition",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "target_id": target_id,
            "trigger_condition_instance_ids": sorted(
                str(row["instance_id"]) for row in triggering
            ),
            "trigger_fly_speed_zero_source_component_ids": sorted(
                str(component.component_id) for component in speed_sources
            ),
            "source_actor_ids": sorted(
                {str(row["source_actor_id"]) for row in triggering}
                | {
                    str(component.source_actor_id)
                    for component in speed_sources
                }
            ),
            "source_effect_ids": sorted(
                {str(row["source_effect_id"]) for row in triggering}
                | {str(component.effect_id) for component in speed_sources}
            ),
            "source_component_ids": source_component_ids,
            "duplicate_trigger_collapsed": duplicate,
            "executed": bool(transition["falls"] and not duplicate),
            "transition": transition,
        }

    def _fly_speed_zero_transition_sources(
        self,
        *,
        before_state: ControlState,
        after_state: ControlState,
        target_id: str,
    ) -> tuple[tuple[Any, ...], int | None]:
        """Return exact active sources when this mutation reaches Fly Speed 0."""

        mechanics = self._target_mechanics(target_id)
        base_speeds = mechanics.get("base_speeds_ft", {})
        if not isinstance(base_speeds, Mapping) or "fly" not in base_speeds:
            return (), None
        mixed_order = mechanics.get("mixed_speed_operation_order")
        before = self._engine._movement_state_authority(
            state=before_state,
            target_id=target_id,
            base_speeds_ft=base_speeds,
            mixed_speed_operation_order=mixed_order,
        )
        after = self._engine._movement_state_authority(
            state=after_state,
            target_id=target_id,
            base_speeds_ft=base_speeds,
            mixed_speed_operation_order=mixed_order,
        )
        before_fly = before["effective_speeds_ft"].get("fly")
        after_fly = after["effective_speeds_ft"].get("fly")
        if (
            before_fly is None
            or before_fly <= 0
            or after_fly != 0
            or "fly" in after["denied_modes"]
        ):
            return (), before_fly
        sources = []
        for component in after_state.active_components(target_id):
            magnitude = component.magnitude
            kind = magnitude.get("kind")
            modes = magnitude.get("movement_modes", MOVEMENT_MODES)
            affects_fly = "fly" in modes
            if (
                kind == "condition"
                and magnitude.get("condition") == "restrained"
            ):
                sources.append(component)
            elif kind == "speed_zero" and affects_fly:
                sources.append(component)
            elif (
                kind == "speed_reduction"
                and affects_fly
                and magnitude.get("reduction", {}).get("kind")
                != "terrain_multiplier"
            ):
                sources.append(component)
        if not sources:
            raise ControlEngineError(
                "Fly Speed reached 0 without exact active source provenance"
            )
        return tuple(sorted(
            sources,
            key=lambda component: (
                component.effect_id,
                component.component_id,
                component.instance_id,
            ),
        )), before_fly

    def apply_condition_application(
        self,
        proposal: _IssuedControlRecord,
    ) -> _IssuedControlRecord:
        """Atomically apply one issued condition root and all lifecycle effects."""

        event = self._require_current(kinds={"condition_application"})
        instance, proposal_payload = self._require_pending_condition_application(
            proposal
        )
        target = str(instance["target_id"])
        self._require_pending_normalization_complete_before_mutation(target)
        before_registry_ids = {
            row["instance_id"] for row in self._state.instance_registry()
        }

        def apply_to(state: ControlState) -> None:
            applied = state.apply_component(
                effect_id=str(instance["source_effect_id"]),
                component={
                    "component_id": str(instance["source_component_id"]),
                    "magnitude": {
                        "kind": "condition",
                        "condition": str(instance["condition_id"]),
                    },
                    "duration": instance["duration"],
                    "stacking": {
                        "key": f"condition_instance:{instance['instance_id']}",
                        "mode": "independent",
                        "refresh": "none",
                    },
                },
                target_id=target,
                source_actor_id=str(instance["source_actor_id"]),
                event_id=event.event_id,
                invocation_id=str(instance["source_invocation_id"]),
                expiry_event_id=instance["expiry_event_id"],
                condition_immunities=self._condition_immunities(target),
                application_sequence=event.sequence,
                condition_instance_id=str(instance["instance_id"]),
                source_program_id=str(instance["source_program_id"]),
                issuance_id=str(instance["issuance_id"]),
                provenance_id=str(instance["provenance_id"]),
            )
            if applied is None:
                raise ControlEngineError(
                    "Condition application was unexpectedly suppressed"
                )

        preview_state = deepcopy(self._state)
        try:
            apply_to(preview_state)
        except (ControlStateError, TypeError, ValueError) as error:
            raise ControlEngineError(
                f"Condition application failed preflight: {error}"
            ) from error
        preview_registry = preview_state.instance_registry()
        new_instances = tuple(
            row for row in preview_registry
            if row["instance_id"] not in before_registry_ids
        )
        if not new_instances:
            raise ControlEngineError("Condition application created no instances")
        fly_speed_zero_sources, pre_transition_fly_speed = (
            self._fly_speed_zero_transition_sources(
                before_state=self._state,
                after_state=preview_state,
                target_id=target,
            )
        )
        proposal_fall_context = proposal_payload.get("fall_context")
        if fly_speed_zero_sources and proposal_fall_context is None:
            raise ControlEngineError(
                "A condition-induced Fly-Speed-0 transition lacks fall_context"
            )
        if (
            fly_speed_zero_sources
            and proposal_fall_context is not None
            and proposal_fall_context.get("fly_speed_ft")
            != pre_transition_fly_speed
        ):
            raise ControlEngineError(
                "fall_context.fly_speed_ft differs from pre-transition Fly Speed"
            )

        tracker = self._concentration_tracker
        concentration_preview: tuple[
            _ConcentrationAuthorityContext,
            tuple[tuple[str, str, str], ...],
            Mapping[str, Any],
            Mapping[str, Any],
        ] | None = None
        applies_incapacitated = any(
            row["condition_id"] == "incapacitated" for row in new_instances
        )
        if (
            applies_incapacitated
            and tracker is not None
            and tracker.active_effect_id is not None
            and tracker.owner_actor_id == target
        ):
            context = self._engine._active_concentration_context(
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                choices=self._choices,
            )
            plans = self._engine._concentration_end_plan(
                state=preview_state,
                context=context,
                event_id=event.event_id,
                reason="controller_incapacitated",
            )
            affected = self._concentration_end_mutation_target_ids(
                context=context,
                plans=plans,
            )
            self._require_pending_normalization_complete_before_mutation(*affected)
            preview_tracker = deepcopy(tracker)
            end_record = preview_tracker.end(
                reason="controller_incapacitated",
                event_id=event.event_id,
                owner_actor_id=target,
            )
            transition = self._engine._apply_concentration_end_record(
                state=preview_state,
                record=end_record,
                context=context,
                plans=plans,
            )
            concentration_preview = (context, plans, end_record, transition)

        fall_record = self._condition_application_fall_record(
            event=event,
            target_id=target,
            new_instances=new_instances,
            fall_context=proposal_fall_context,
            fly_speed_zero_sources=fly_speed_zero_sources,
        )

        pre = _canonical_json(self._state.snapshot())
        apply_to(self._state)
        concentration_record: dict[str, Any] | None = None
        if concentration_preview is not None:
            if tracker is None:  # pragma: no cover
                raise ControlEngineError("Concentration tracker disappeared")
            context, plans, expected_end, expected_transition = concentration_preview
            end_record = tracker.end(
                reason="controller_incapacitated",
                event_id=event.event_id,
                owner_actor_id=target,
            )
            if end_record != expected_end:
                raise ControlEngineError(
                    "Concentration end differed from its atomic preflight"
                )
            transition = self._engine._apply_concentration_end_record(
                state=self._state,
                record=end_record,
                context=context,
                plans=plans,
            )
            if transition != expected_transition:
                raise ControlEngineError(
                    "Concentration cleanup differed from its atomic preflight"
                )
            self._engine._concentration_contexts.pop(tracker, None)
            concentration_record = {
                "kind": "condition_concentration_end",
                "condition_instance_ids": sorted(
                    row["instance_id"]
                    for row in new_instances
                    if row["condition_id"] == "incapacitated"
                ),
                "owner_actor_id": target,
                "tracker_end_record": end_record,
                "cleanup_transition": transition,
                "active_effect_id": None,
            }
            self._concentration_records.append(
                dict(_json_safe(transition))
            )
            self._condition_concentration_records.append(concentration_record)
            self._area_effect_ended = True

        committed_registry = self._state.instance_registry()
        committed_new_instances = tuple(
            row for row in committed_registry
            if row["instance_id"] not in before_registry_ids
        )
        if committed_new_instances != new_instances:
            raise ControlEngineError(
                "Condition application differed from its atomic preflight"
            )
        if fall_record is not None:
            if fall_record["executed"]:
                self._fall_transition_identities.add((event.event_id, target))
            self._fall_transition_records.append(fall_record)
        payload = {
            "kind": "condition_application",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "target_id": target,
            "proposal_operation_sequence": proposal.operation_sequence,
            "proposal_record_sha256": proposal.record_sha256,
            "root_condition_instance_id": instance["instance_id"],
            "created_condition_instances": list(committed_new_instances),
            "condition_concentration_end": concentration_record,
            "fall_transition": fall_record,
            "active_conditions_after": list(
                self._state.derived_current_conditions(target)
            ),
        }
        self._condition_operation_records.append(payload)
        issued = self._issue(
            record_kind="condition_application",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=target,
        )
        self._consumed_condition_proposal_sequences.add(
            proposal.operation_sequence
        )
        self._pending_condition_proposals.pop(str(instance["instance_id"]), None)
        self._current_required_operations.discard("condition_application")
        if concentration_record is not None:
            self._close_area_routes_for_effect_end(
                event=event,
                reason="effect_ended",
            )
        return issued

    def end_condition_instance(
        self,
        *,
        condition_instance_id: str,
        expected_source_actor_id: str,
        expected_issuance_id: str | None = None,
        reason: str = "source_end",
    ) -> _IssuedControlRecord:
        """End one exact live instance and only its inclusion descendants."""

        event = self._require_current(kinds={"condition_end"})
        instance_id = _identifier(
            condition_instance_id,
            "condition_instance_id",
        )
        preview = deepcopy(self._state)
        try:
            expected = preview.end_condition_instance(
                instance_id,
                event_id=event.event_id,
                event_sequence=event.sequence,
                reason=_identifier(reason, "reason"),
                expected_source_actor_id=_identifier(
                    expected_source_actor_id,
                    "expected_source_actor_id",
                ),
                expected_issuance_id=(
                    None
                    if expected_issuance_id is None
                    else _identifier(
                        expected_issuance_id,
                        "expected_issuance_id",
                    )
                ),
            )
        except ControlStateError as error:
            raise ControlEngineError(f"Condition end failed preflight: {error}") from error
        target_ids = {item.target_id for item in expected}
        self._require_pending_normalization_complete_before_mutation(*target_ids)
        pre = _canonical_json(self._state.snapshot())
        ended = self._state.end_condition_instance(
            instance_id,
            event_id=event.event_id,
            event_sequence=event.sequence,
            reason=reason,
            expected_source_actor_id=expected_source_actor_id,
            expected_issuance_id=expected_issuance_id,
        )
        if tuple(item.to_dict() for item in ended) != tuple(
            item.to_dict() for item in expected
        ):
            raise ControlEngineError("Condition end differed from its atomic preflight")
        target = ended[0].target_id
        payload = {
            "kind": "condition_end",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "target_id": target,
            "root_condition_instance_id": instance_id,
            "ended_condition_instances": [item.to_dict() for item in ended],
            "active_conditions_after": list(
                self._state.derived_current_conditions(target)
            ),
        }
        self._condition_operation_records.append(payload)
        self._current_required_operations.discard("condition_end")
        return self._issue(
            record_kind="condition_end",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=target,
        )

    @staticmethod
    def _opportunity_source_ids(
        values: Sequence[str],
        label: str,
    ) -> tuple[str, ...]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ControlEngineError(f"{label} must be an array of source IDs")
        return tuple(sorted({
            _identifier(value, f"{label} source") for value in values
        }))

    @staticmethod
    def _normalization_record(result: NormalizationResult) -> dict[str, Any]:
        return {
            "contributions": [
                contribution.to_dict() for contribution in result.contributions
            ],
            "suppressions": [
                suppression.to_dict() for suppression in result.suppressions
            ],
        }

    @staticmethod
    def _require_resolved_condition_context(
        result: NormalizationResult,
        *,
        primitive_ids: set[str],
    ) -> None:
        unresolved = [
            {
                "primitive_id": contribution.primitive_id,
                "source_component_ids": list(
                    contribution.source_component_ids
                ),
                "unresolved_requirements": contribution.context.get(
                    "unresolved_requirements"
                ),
            }
            for contribution in result.contributions
            if contribution.primitive_id in primitive_ids
            and contribution.context.get("unresolved_requirements")
        ]
        if unresolved:
            raise ControlEngineError(
                "Condition opportunity context is unresolved; exact source, "
                f"relation, distance, or sight facts are required: {unresolved}"
            )

    def _action_legality_decision(
        self,
        *,
        actor_id: str,
        proposal_target_id: str | None,
        action_economy: str,
        category: str,
    ) -> dict[str, Any]:
        actor = _identifier(actor_id, "actor_id")
        if actor not in self._known_actor_ids:
            raise ControlEngineError(f"Unknown session actor: {actor!r}")
        if action_economy not in {
            "action",
            "bonus_action",
            "reaction",
            "movement",
            "other",
        }:
            raise ControlEngineError(
                f"Unsupported action_economy: {action_economy!r}"
            )
        if category not in {
            "attack",
            "damaging_ability",
            "damaging_magical_effect",
            "non_damaging_effect",
            "other",
        }:
            raise ControlEngineError(f"Unsupported action category: {category!r}")
        proposal_target = (
            None
            if proposal_target_id is None
            else _identifier(proposal_target_id, "proposal_target_id")
        )
        active = self._state.active_condition_instances(actor)
        incapacitated_sources = [
            instance for instance in active
            if instance.condition_id == "incapacitated"
        ]
        charmed_sources = [
            instance for instance in active
            if instance.condition_id == "charmed"
        ]
        denial_reasons: list[dict[str, Any]] = []
        if incapacitated_sources and action_economy in {
            "action",
            "bonus_action",
            "reaction",
        }:
            denial_reasons.append({
                "reason": "incapacitated_action_economy_denial",
                "condition_instance_ids": sorted(
                    instance.instance_id for instance in incapacitated_sources
                ),
                "denied_action_economy": action_economy,
            })
        prohibited_categories = {
            "attack",
            "damaging_ability",
            "damaging_magical_effect",
        }
        matching_charmers = [
            instance for instance in charmed_sources
            if proposal_target == instance.source_actor_id
        ]
        if (
            category in prohibited_categories
            and charmed_sources
            and proposal_target is None
        ):
            denial_reasons.append({
                "reason": "charmed_target_identity_unresolved",
                "condition_instance_ids": sorted(
                    instance.instance_id for instance in charmed_sources
                ),
                "charmer_actor_ids": sorted({
                    instance.source_actor_id for instance in charmed_sources
                }),
                "prohibited_category": category,
            })
        elif category in prohibited_categories and matching_charmers:
            denial_reasons.append({
                "reason": "charmed_exact_source_target_restriction",
                "condition_instance_ids": sorted(
                    instance.instance_id for instance in matching_charmers
                ),
                "charmer_actor_ids": sorted({
                    instance.source_actor_id for instance in matching_charmers
                }),
                "prohibited_category": category,
            })
        return {
            "kind": "source_relative_action_legality",
            "actor_id": actor,
            "proposal_target_id": proposal_target,
            "action_economy": action_economy,
            "category": category,
            "allowed": not denial_reasons,
            "denial_reasons": denial_reasons,
            "active_charmed_instance_ids": sorted(
                instance.instance_id for instance in charmed_sources
            ),
            "active_incapacitated_instance_ids": sorted(
                instance.instance_id for instance in incapacitated_sources
            ),
        }

    def resolve_action_proposal(
        self,
        *,
        actor_id: str,
        proposal_target_id: str | None,
        action_economy: str,
        category: str,
    ) -> _IssuedControlRecord:
        event = self._require_current(kinds={"action_proposal"})
        if any(
            record.record_kind == "action_legality"
            and record.event_id == event.event_id
            for record in self._issued_records
        ):
            raise ControlEngineError("This action proposal was already resolved")
        self._require_unchanged_pre_event_condition_basis(actor_id)
        decision = self._action_legality_decision(
            actor_id=actor_id,
            proposal_target_id=proposal_target_id,
            action_economy=action_economy,
            category=category,
        )
        if event.actor_id != decision["actor_id"]:
            raise ControlEngineError(
                "Action proposal actor does not own the typed event"
            )
        payload = {
            **decision,
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "resolution_created": bool(decision["allowed"]),
        }
        pre = _canonical_json(self._state.snapshot())
        self._source_relative_legality_records.append(payload)
        self._current_required_operations.discard("action_legality")
        return self._issue(
            record_kind="action_legality",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=str(decision["actor_id"]),
        )

    def resolve_attack_opportunity(
        self,
        *,
        attacker_id: str,
        defender_id: str,
        context: Mapping[str, Any] | None = None,
        advantage_source_ids: Sequence[str] = (),
        disadvantage_source_ids: Sequence[str] = (),
        category: str = "attack",
        action_economy: str = "action",
    ) -> _IssuedControlRecord:
        event = self._require_current()
        attacker = _identifier(attacker_id, "attacker_id")
        defender = _identifier(defender_id, "defender_id")
        attack_gate_ids = self._current_resolution_gate_ids(
            resolution_kind="attack_roll",
            target_id=defender,
        )
        scripted_attack = event.kind in {
            "attack_opportunity",
            "controller_attack_opportunity",
            "target_attack_opportunity",
        }
        if not scripted_attack and not attack_gate_ids:
            raise ControlEngineError(
                "The current event has no typed attack opportunity"
            )
        if any(
            row.get("kind") == "attack_opportunity"
            and row.get("event_id") == event.event_id
            and row.get("attacker_id") == attacker
            and row.get("defender_id") == defender
            for row in self._opportunity_roll_records
        ):
            raise ControlEngineError(
                "This attack opportunity was already resolved"
            )
        if attacker not in self._known_actor_ids or defender not in self._known_actor_ids:
            raise ControlEngineError(
                "Attack opportunity actors must belong to the session"
            )
        event_actor_id = (
            self._source_actor_id
            if event.actor_id == "controller"
            else event.actor_id
        )
        if event_actor_id is not None and event_actor_id != attacker:
            raise ControlEngineError(
                "Attack opportunity attacker does not own the typed event"
            )
        if attack_gate_ids:
            if (
                attacker != self._source_actor_id
                or event.target_id not in {None, defender}
            ):
                raise ControlEngineError(
                    "Compiled attack opportunity actor/target differs from its gate"
                )
        elif event.kind in {"controller_attack_opportunity", "attack_opportunity"}:
            if event.target_id is not None and event.target_id != defender:
                raise ControlEngineError(
                    "Attack opportunity defender differs from the typed event target"
                )
        elif event.target_id != attacker:
            raise ControlEngineError(
                "Structural target attack does not match its actor"
            )
        if not isinstance(context, Mapping) and context is not None:
            raise ControlEngineError("attack context must be an object")
        attack_context = dict(_strict_json_copy(context or {}, "attack context"))
        self._require_unchanged_pre_event_condition_basis(attacker)
        self._require_unchanged_pre_event_condition_basis(defender)
        legality = self._action_legality_decision(
            actor_id=attacker,
            proposal_target_id=defender,
            action_economy=action_economy,
            category=category,
        )
        legality_record = {
            **legality,
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "resolution_created": bool(legality["allowed"]),
        }
        pre = _canonical_json(self._state.snapshot())
        if not legality["allowed"]:
            payload = {
                "kind": "attack_opportunity",
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "attacker_id": attacker,
                "defender_id": defender,
                "attack_gate_ids": list(attack_gate_ids),
                "legality": legality,
                "roll_created": False,
                "roll_mode": None,
                "advantage_sources": [],
                "disadvantage_sources": [],
                "outgoing_normalization": None,
                "incoming_normalization": None,
            }
        else:
            window_id = event.window_id or event.event_id
            outgoing_kind = (
                "target_attack_opportunity"
                if event.kind == "target_attack_opportunity"
                else "controller_attack_opportunity"
                if event.kind == "controller_attack_opportunity"
                else "attack_opportunity"
            )
            preview_state = deepcopy(self._state)
            try:
                preview_outgoing = preview_state.normalize_for_window(
                    target_id=attacker,
                    window_id=window_id,
                    window_kind=outgoing_kind,
                    context=attack_context,
                    catalog=self._engine.catalog,
                )
                preview_incoming = preview_state.normalize_for_window(
                    target_id=defender,
                    window_id=window_id,
                    window_kind="incoming_attack_opportunity",
                    context=attack_context,
                    catalog=self._engine.catalog,
                )
            except ControlStateError as error:
                raise ControlEngineError(
                    f"Attack opportunity normalization failed: {error}"
                ) from error
            self._require_resolved_condition_context(
                preview_outgoing,
                primitive_ids={
                    "offensive_impairment_all_attacks",
                    "offensive_impairment_next_attack",
                },
            )
            self._require_resolved_condition_context(
                preview_incoming,
                primitive_ids={
                    "defensive_attack_advantage",
                    "prone_incoming_attack_context",
                },
            )
            advantage = set(self._opportunity_source_ids(
                advantage_source_ids,
                "advantage_source_ids",
            ))
            disadvantage = set(self._opportunity_source_ids(
                disadvantage_source_ids,
                "disadvantage_source_ids",
            ))
            for contribution in preview_outgoing.contributions:
                if contribution.primitive_id in {
                    "offensive_impairment_all_attacks",
                    "offensive_impairment_next_attack",
                }:
                    disadvantage.update(contribution.source_component_ids)
            for contribution in preview_incoming.contributions:
                if contribution.primitive_id == "defensive_attack_advantage":
                    advantage.update(contribution.source_component_ids)
                elif contribution.primitive_id == "prone_incoming_attack_context":
                    disadvantage.update(contribution.source_component_ids)
            try:
                outgoing = self._state.normalize_for_window(
                    target_id=attacker,
                    window_id=window_id,
                    window_kind=outgoing_kind,
                    context=attack_context,
                    catalog=self._engine.catalog,
                )
                incoming = self._state.normalize_for_window(
                    target_id=defender,
                    window_id=window_id,
                    window_kind="incoming_attack_opportunity",
                    context=attack_context,
                    catalog=self._engine.catalog,
                )
            except ControlStateError as error:  # pragma: no cover - preflight parity
                raise ControlEngineError(
                    f"Attack opportunity commit failed after preflight: {error}"
                ) from error
            if (
                self._normalization_record(outgoing)
                != self._normalization_record(preview_outgoing)
                or self._normalization_record(incoming)
                != self._normalization_record(preview_incoming)
            ):
                raise ControlEngineError(
                    "Attack opportunity differed from its atomic preflight"
                )
            payload = {
                "kind": "attack_opportunity",
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "attacker_id": attacker,
                "defender_id": defender,
                "attack_gate_ids": list(attack_gate_ids),
                "legality": legality,
                "roll_created": True,
                "roll_mode": resolve_roll_mode(
                    len(advantage),
                    len(disadvantage),
                ),
                "advantage_sources": sorted(advantage),
                "disadvantage_sources": sorted(disadvantage),
                "outgoing_normalization": self._normalization_record(outgoing),
                "incoming_normalization": self._normalization_record(incoming),
            }
        self._source_relative_legality_records.append(legality_record)
        self._opportunity_roll_records.append(payload)
        self._current_required_operations.discard("opportunity_roll")
        self._current_required_operations.discard(
            f"opportunity_roll:attack:{defender}"
        )
        if not legality["allowed"]:
            for gate_id in attack_gate_ids:
                self._current_required_operations.discard(
                    f"branch:{gate_id}:{defender}"
                )
                self._current_required_operations.discard(f"branch:{gate_id}")
        return self._issue(
            record_kind="opportunity_roll",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=attacker,
        )

    def resolve_save_opportunity(
        self,
        *,
        actor_id: str,
        ability: str,
        context: Mapping[str, Any] | None = None,
        advantage_source_ids: Sequence[str] = (),
        disadvantage_source_ids: Sequence[str] = (),
    ) -> _IssuedControlRecord:
        event = self._require_current()
        actor = _identifier(actor_id, "actor_id")
        save_gate_ids = self._current_resolution_gate_ids(
            resolution_kind="saving_throw",
            target_id=actor,
        )
        if event.kind != "save_opportunity" and not save_gate_ids:
            raise ControlEngineError(
                "The current event has no typed saving-throw opportunity"
            )
        if any(
            row.get("kind") == "save_opportunity"
            and row.get("event_id") == event.event_id
            and row.get("actor_id") == actor
            for row in self._opportunity_roll_records
        ):
            raise ControlEngineError(
                "This saving-throw opportunity was already resolved"
            )
        if actor not in self._known_actor_ids:
            raise ControlEngineError(f"Unknown session actor: {actor!r}")
        if event.target_id is not None and event.target_id != actor:
            raise ControlEngineError(
                "Saving throw actor differs from the typed event target"
            )
        save_ability = _identifier(ability, "ability").lower()
        canonical_abilities = {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        }
        gate_abilities = {
            self._program.gate(gate_id).ability for gate_id in save_gate_ids
        }
        if (
            gate_abilities
            and gate_abilities != {save_ability}
        ):
            raise ControlEngineError(
                "Saving throw ability differs from its compiled gate authority"
            )
        if save_ability not in canonical_abilities and not gate_abilities:
            raise ControlEngineError(f"Unsupported saving throw ability: {ability!r}")
        entry_gate_ids = tuple(
            gate_id
            for gate_id in save_gate_ids
            if self._program.gate(gate_id).trigger.kind == "entry"
        )
        entry_records: list[_IssuedControlRecord] = []
        for gate_id in entry_gate_ids:
            entry_records.append(self._require_entry_gate_attested(
                gate_id=gate_id,
                target_id=actor,
                event=event,
            ))
        if entry_gate_ids and len(entry_gate_ids) != len(save_gate_ids):
            raise ControlEngineError(
                "A saving-throw opportunity cannot combine entry-attested and "
                "event-open gate authority"
            )
        if not isinstance(context, Mapping) and context is not None:
            raise ControlEngineError("save context must be an object")
        save_context = dict(_strict_json_copy(context or {}, "save context"))
        save_context["save_ability"] = save_ability
        if entry_records:
            entry_record_ids = {
                record.record_sha256 for record in entry_records
            }
            if len(entry_record_ids) != 1:
                raise ControlEngineError(
                    "Entry saving-throw gates do not share one exact "
                    "AreaEntryTransition attestation"
                )
            self._require_unchanged_attested_entry_condition_basis(
                actor,
                entry_records[0],
            )
        else:
            self._require_unchanged_pre_event_condition_basis(actor)
        pre = _canonical_json(self._state.snapshot())
        try:
            normalized = self._state.normalize_for_window(
                target_id=actor,
                window_id=event.window_id or event.event_id,
                window_kind="save_opportunity",
                context=save_context,
                catalog=self._engine.catalog,
            )
        except ControlStateError as error:
            raise ControlEngineError(
                f"Saving throw normalization failed: {error}"
            ) from error
        self._require_resolved_condition_context(
            normalized,
            primitive_ids={"save_disadvantage", "save_auto_failure"},
        )
        advantage = set(self._opportunity_source_ids(
            advantage_source_ids,
            "advantage_source_ids",
        ))
        disadvantage = set(self._opportunity_source_ids(
            disadvantage_source_ids,
            "disadvantage_source_ids",
        ))
        auto_failure: set[str] = set()
        for contribution in normalized.contributions:
            if contribution.primitive_id == "save_disadvantage":
                disadvantage.update(contribution.source_component_ids)
            elif contribution.primitive_id == "save_auto_failure":
                auto_failure.update(contribution.source_component_ids)
        for suppression in normalized.suppressions:
            if (
                suppression.primitive_id == "save_disadvantage"
                and suppression.reason == "automatic_failure_dominates_disadvantage"
            ):
                disadvantage.update(suppression.suppressed_source_component_ids)
        payload = {
            "kind": "save_opportunity",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "actor_id": actor,
            "ability": save_ability,
            "save_gate_ids": list(save_gate_ids),
            "roll_created": not auto_failure,
            "automatic_failure": bool(auto_failure),
            "automatic_failure_sources": sorted(auto_failure),
            "roll_mode": (
                None
                if auto_failure
                else resolve_roll_mode(len(advantage), len(disadvantage))
            ),
            "advantage_sources": sorted(advantage),
            "disadvantage_sources": sorted(disadvantage),
            "normalization": self._normalization_record(normalized),
            "probability_branch_created": not auto_failure,
        }
        self._opportunity_roll_records.append(payload)
        self._current_required_operations.discard("opportunity_roll")
        self._current_required_operations.discard(
            f"opportunity_roll:save:{actor}"
        )
        return self._issue(
            record_kind="opportunity_roll",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=actor,
        )

    def resolve_initiative_opportunity(
        self,
        *,
        actor_id: str,
        advantage_source_ids: Sequence[str] = (),
        disadvantage_source_ids: Sequence[str] = (),
    ) -> _IssuedControlRecord:
        event = self._require_current(kinds={"initiative_opportunity"})
        actor = _identifier(actor_id, "actor_id")
        if any(
            row.get("kind") == "initiative_opportunity"
            and row.get("event_id") == event.event_id
            and row.get("actor_id") == actor
            for row in self._opportunity_roll_records
        ):
            raise ControlEngineError(
                "This initiative opportunity was already resolved"
            )
        if actor not in self._known_actor_ids or event.actor_id != actor:
            raise ControlEngineError(
                "Initiative opportunity actor does not own the typed event"
            )
        self._require_unchanged_pre_event_condition_basis(actor)
        pre = _canonical_json(self._state.snapshot())
        normalized = self._state.normalize_for_window(
            target_id=actor,
            window_id=event.window_id or event.event_id,
            window_kind="initiative_opportunity",
            context={},
            catalog=self._engine.catalog,
        )
        advantage = set(self._opportunity_source_ids(
            advantage_source_ids,
            "advantage_source_ids",
        ))
        disadvantage = set(self._opportunity_source_ids(
            disadvantage_source_ids,
            "disadvantage_source_ids",
        ))
        for contribution in normalized.contributions:
            if contribution.primitive_id == "initiative_disadvantage":
                disadvantage.update(contribution.source_component_ids)
        payload = {
            "kind": "initiative_opportunity",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "actor_id": actor,
            "roll_created": True,
            "roll_mode": resolve_roll_mode(len(advantage), len(disadvantage)),
            "advantage_sources": sorted(advantage),
            "disadvantage_sources": sorted(disadvantage),
            "normalization": self._normalization_record(normalized),
        }
        self._opportunity_roll_records.append(payload)
        self._current_required_operations.discard("opportunity_roll")
        return self._issue(
            record_kind="opportunity_roll",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=actor,
        )

    def resolve_fall_transition(
        self,
        *,
        target_id: str,
        source_actor_id: str,
        source_effect_id: str,
        source_component_id: str,
        source_issuance_id: str,
        fall_context: Mapping[str, Any],
    ) -> _IssuedControlRecord:
        """Execute one explicit Fly-Speed-0/current-position fall opportunity."""

        event = self._require_current(
            target_id=target_id,
            kinds={"fall_transition"},
        )
        target = _identifier(target_id, "target_id")
        if any(
            row.get("event_id") == event.event_id
            and row.get("target_id") == target
            for row in self._fall_transition_records
        ):
            raise ControlEngineError(
                "A fall transition was already resolved for this target/event"
            )
        context = self._validated_fall_context(fall_context, required=True)
        bound_context = self._validated_fall_context(
            self._bound_input(
                "fall_context",
                target_id=target,
                default=None,
            ),
            required=True,
        )
        if context != bound_context:
            raise ControlEngineError(
                "Fall context differs from the scenario-bound event input"
            )
        if context is None or context["fly_speed_ft"] != 0:
            raise ControlEngineError(
                "Standalone fall_transition requires exact Fly Speed 0"
            )
        supplied_source = {
            "source_actor_id": _identifier(
                source_actor_id,
                "source_actor_id",
            ),
            "source_effect_id": _identifier(
                source_effect_id,
                "source_effect_id",
            ),
            "source_component_id": _identifier(
                source_component_id,
                "source_component_id",
            ),
            "source_issuance_id": _identifier(
                source_issuance_id,
                "source_issuance_id",
            ),
        }
        bound_source = self._bound_input(
            "fall_source",
            target_id=target,
            default=None,
        )
        if not isinstance(bound_source, Mapping) or set(bound_source) != set(
            supplied_source
        ):
            raise ControlEngineError(
                "fall_source must bind exact source actor/effect/component/issuance"
            )
        if _strict_json_copy(bound_source, "fall_source") != supplied_source:
            raise ControlEngineError(
                "Fall source differs from the scenario-bound event input"
            )
        identity = (event.event_id, target)
        if identity in self._fall_transition_identities:
            raise ControlEngineError(
                "A fall transition already executed for this target/event"
            )
        transition = airborne_fall_transition(
            target_id=target,
            airborne=context["airborne"],
            can_hover=context["can_hover"],
            fly_speed_ft=0,
            explicit_prevents_fall=context["explicit_prevents_fall"],
            source_component_id=_identifier(
                source_component_id,
                "source_component_id",
            ),
        )
        payload = {
            "kind": "fall_transition",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "target_id": target,
            **supplied_source,
            "duplicate_trigger_collapsed": False,
            "executed": bool(transition["falls"]),
            "transition": transition,
        }
        if transition["falls"]:
            self._fall_transition_identities.add(identity)
        self._fall_transition_records.append(payload)
        self._current_required_operations.discard("fall_transition")
        pre = _canonical_json(self._state.snapshot())
        return self._issue(
            record_kind="fall_transition",
            payload=payload,
            pre_operation_state_json=pre,
            target_id=target,
        )

    def resolve_displacement(
        self,
        *,
        target_id: str,
        component_id: str,
    ) -> _IssuedControlRecord:
        event = self._require_current(target_id=target_id)
        self._require_pending_normalization_complete_before_mutation(
            target_id
        )
        component = self._program.component(_identifier(component_id, "component_id"))
        identity = (target_id, component.component_id)
        if identity not in self._pending_displacements:
            raise ControlEngineError(
                "Displacement must resolve a pending request issued at the current event"
            )
        vectors = self._bound_input(
            "displacement_vectors",
            target_id=target_id,
            default={},
        )
        vector = None
        if isinstance(vectors, Mapping) and component.component_id in vectors:
            vector = vectors[component.component_id]
        pre = _canonical_json(self._state.snapshot())
        resolution = self._engine._resolve_displacement(
            component=component,
            target_id=target_id,
            event_id=event.event_id,
            epochs=self._epochs,
            displacement_function_id=self._displacement_function_id,
            vector_feet=vector,
        )
        self._pending_displacements.remove(identity)
        self._current_required_operations.discard("displacement")
        self._displaced_targets.add(target_id)
        self._displacement_records.append(resolution)
        return self._issue(
            record_kind="displacement",
            payload=resolution,
            pre_operation_state_json=pre,
            target_id=target_id,
        )

    def resolve_area_entry(self, *, target_id: str) -> _IssuedControlRecord:
        event = self._require_current(target_id=target_id, kinds={"entry"})
        self._require_pending_normalization_complete_before_mutation(
            target_id
        )
        target = _identifier(target_id, "target_id")
        transition = self._area_entry_transitions.get((event.event_id, target))
        if transition is None or transition.cause == "area_movement":
            raise ControlEngineError(
                "The current event has no scenario-bound ordinary or forced "
                f"AreaEntryTransition for target {target!r}"
            )
        old_state = self._area_route_state(target)
        decision = self._entry_decision(
            transition=transition,
            old_state=old_state,
            event=event,
        )
        ambient_plan = self._ambient_area_restoration_plan(
            transition=transition,
            event=event,
        )
        pre = _canonical_json(self._state.snapshot())
        pre_route = self._area_route_state_json()
        new_state = replace(
            old_state,
            membership=True,
            routes=(
                transition.routes
                if self._area_response_convention == "shortest_route_v1"
                else ()
            ),
            selected_route_id=None,
            movement_mode=None,
            environment=None,
            remaining_distance_ft=None,
            movement_cost_basis=None,
            closed_reason=None,
            last_update_event_id=event.event_id,
            last_update_event_sequence=event.sequence,
        )
        self._set_area_route_state(new_state)
        restored_ambient_ids = self._restore_ambient_area_components(
            plan=ambient_plan,
            transition=transition,
            event=event,
        )
        route_transition = self._route_transition(
            transition_kind="area_entry",
            event=event,
            old_state=old_state,
            new_state=new_state,
            pre_route_state_json=pre_route,
            extra={
                "entry_cause": transition.cause,
                "turn_id": transition.turn_id,
            },
        )
        self._commit_entry_decision(
            transition=transition,
            decision=decision,
        )
        gate_ids = list(decision["gate_ids"])
        result = {
            "kind": "area_entry",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "effect_id": transition.effect_id,
            "area_id": transition.area_id,
            "target_id": transition.target_id,
            "entry_cause": transition.cause,
            "turn_id": transition.turn_id,
            "entry_policy": decision["entry_policy"],
            "frequency_key": decision["frequency_key"],
            "previously_triggered_this_turn": decision[
                "previously_triggered_this_turn"
            ],
            "frequency_permitted": decision["frequency_permitted"],
            "frequency_decision": decision["frequency_decision"],
            "frequency_history_consumed": decision[
                "frequency_history_consumed"
            ],
            "triggered": decision["triggered"],
            "gate_opportunity_ids": gate_ids if decision["triggered"] else [],
            "gate_requirement_ids": gate_ids if decision["triggered"] else [],
            "ambient_area_component_ids": list(
                ambient_plan["ambient_component_ids"]
            ),
            "retained_ambient_component_ids": list(
                ambient_plan["retained_component_ids"]
            ),
            "restored_ambient_component_ids": list(restored_ambient_ids),
            "membership_before": False,
            "membership_after": True,
            "old_route_state": old_state.to_dict(),
            "new_route_state": new_state.to_dict(),
            "pre_route_state_sha256": route_transition[
                "pre_route_state_sha256"
            ],
            "post_route_state_sha256": route_transition[
                "post_route_state_sha256"
            ],
            "bound_transition": transition.to_dict(),
            "route_transition": route_transition,
        }
        self._state.audit_ledger.append({
            "operation": "area_entry",
            **result,
        })
        return self._issue(
            record_kind="area_entry",
            payload=result,
            pre_operation_state_json=pre,
            pre_operation_route_state_json=pre_route,
            target_id=target,
        )

    def apply_area_geometry_update(
        self,
        *,
        target_id: str,
    ) -> _IssuedControlRecord:
        event = self._require_current(
            target_id=target_id,
            kinds={"instantaneous_resolution"},
        )
        self._require_pending_normalization_complete_before_mutation(
            target_id
        )
        target = _identifier(target_id, "target_id")
        update = self._area_geometry_updates.get((event.event_id, target))
        if update is None:
            raise ControlEngineError(
                "The current event has no scenario-bound AreaGeometryUpdate for "
                f"target {target!r}"
            )
        label = f"area_geometry_update:{target}"
        if label not in self._current_required_operations:
            raise ControlEngineError(
                "The scenario-bound area geometry update was already consumed"
            )
        old_state = self._area_route_state(target)
        if old_state.area_id != update.area_id:
            raise ControlEngineError("AreaGeometryUpdate route state is foreign")
        if not self._area_effect_is_active(update.area_id):
            raise ControlEngineError(
                "AreaGeometryUpdate requires an active compiled persistent area"
            )
        area = next(
            selector.area
            for selector in self._program.selectors
            if selector.area is not None
            and selector.area.area_id == update.area_id
        )
        movement_authority = (
            None if area.movement is None else area.movement.to_dict()
        )
        if (
            not isinstance(movement_authority, Mapping)
            or movement_authority.get("kind") != "controller_reposition"
            or event.turn_owner != "controller"
            or event.actor_id != "controller"
            or not typed_event_matches(
                event,
                movement_authority.get("timing", {}),
            )
        ):
            raise ControlEngineError(
                "AreaGeometryUpdate no longer matches compiled moving-area authority"
            )
        bound_entry = self._area_entry_transitions.get(
            (event.event_id, target)
        )
        entry_decision: dict[str, Any] | None = None
        ambient_plan: dict[str, Any] | None = None
        if not old_state.membership and update.new_membership:
            if (
                bound_entry is None
                or bound_entry.cause != "area_movement"
                or bound_entry.effect_id != update.effect_id
                or bound_entry.area_id != update.area_id
                or bound_entry.routes != update.routes
            ):
                raise ControlEngineError(
                    "False-to-true AreaGeometryUpdate lacks its exact "
                    "scenario-bound AreaEntryTransition"
                )
            entry_decision = self._entry_decision(
                transition=bound_entry,
                old_state=old_state,
                event=event,
            )
            ambient_plan = self._ambient_area_restoration_plan(
                transition=bound_entry,
                event=event,
            )
        pre = _canonical_json(self._state.snapshot())
        pre_route = self._area_route_state_json()
        ended_instances: list[dict[str, Any]] = []
        ended_component_ids: list[str] = []
        if old_state.membership and not update.new_membership:
            bindings = self._engine._compiled_area_bindings(self._program)
            for component in tuple(self._state.active_components(target)):
                if (
                    component.effect_id != self._program.effect_id
                    or update.area_id
                    not in bindings.get(component.component_id, ())
                ):
                    continue
                removed = self._state.terminate(
                    target_id=target,
                    component_id=component.component_id,
                    event_id=event.event_id,
                    effect_id=self._program.effect_id,
                    reason="compiled_area_reposition_exit",
                )
                ended_component_ids.append(component.component_id)
                ended_instances.extend({
                    "target_id": item.target_id,
                    "component_id": item.component_id,
                    "instance_id": item.instance_id,
                } for item in removed)
        new_state = _AreaRouteState(
            effect_id=old_state.effect_id,
            area_id=old_state.area_id,
            target_id=old_state.target_id,
            membership=update.new_membership,
            routes=update.routes,
            selected_route_id=None,
            movement_mode=None,
            environment=None,
            remaining_distance_ft=None,
            movement_cost_basis=None,
            closed_reason=None if update.new_membership else "explicit_area_exit",
            last_update_event_id=event.event_id,
            last_update_event_sequence=event.sequence,
        )
        self._set_area_route_state(new_state)
        restored_ambient_ids: tuple[str, ...] = ()
        if ambient_plan is not None and bound_entry is not None:
            restored_ambient_ids = self._restore_ambient_area_components(
                plan=ambient_plan,
                transition=bound_entry,
                event=event,
            )
        if old_state.membership and not new_state.membership:
            self._prune_future_area_gate_operations(
                area_id=old_state.area_id,
                target_id=target,
            )
        entry_policy = (
            None if area.entry_policy is None else area.entry_policy.to_dict()
        )
        moved_area_counts_as_entry = bool(
            isinstance(entry_policy, Mapping)
            and entry_policy.get("moved_area_counts_as_entry")
        )
        entry_gate_ids = (
            list(entry_decision["gate_ids"])
            if entry_decision is not None and entry_decision["triggered"]
            else []
        )
        exit_gate_ids = sorted({
            gate.gate_id
            for gate in self._program.gates
            if gate.trigger.kind == "exit"
            and old_state.membership
            and not update.new_membership
        })
        transition = self._route_transition(
            transition_kind="explicit_geometry_update",
            event=event,
            old_state=old_state,
            new_state=new_state,
            pre_route_state_json=pre_route,
            extra={
                "canonical_reason": "controller_reposition",
                "compiled_movement_authority": movement_authority,
                "moved_area_counts_as_entry": moved_area_counts_as_entry,
                "entry_gate_opportunity_ids": entry_gate_ids,
                "exit_gate_opportunity_ids": exit_gate_ids,
            },
        )
        payload = {
            "kind": "area_geometry_update",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "effect_id": self._program.effect_id,
            "area_id": update.area_id,
            "target_id": target,
            "canonical_reason": "controller_reposition",
            "compiled_movement_authority": movement_authority,
            "moved_area_counts_as_entry": moved_area_counts_as_entry,
            "membership_before": old_state.membership,
            "membership_after": new_state.membership,
            "entry_gate_opportunity_ids": entry_gate_ids,
            "ambient_area_component_ids": (
                list(ambient_plan["ambient_component_ids"])
                if ambient_plan is not None else []
            ),
            "retained_ambient_component_ids": (
                list(ambient_plan["retained_component_ids"])
                if ambient_plan is not None else []
            ),
            "restored_ambient_component_ids": list(restored_ambient_ids),
            "exit_gate_opportunity_ids": exit_gate_ids,
            "ended_component_ids": sorted(set(ended_component_ids)),
            "ended_state_instances": ended_instances,
            "old_route_state": old_state.to_dict(),
            "new_route_state": new_state.to_dict(),
            "pre_route_state_sha256": transition["pre_route_state_sha256"],
            "post_route_state_sha256": transition["post_route_state_sha256"],
            "route_transition": transition,
        }
        self._state.audit_ledger.append({
            "operation": "area_geometry_update",
            **payload,
        })
        self._current_required_operations.discard(label)
        geometry_record = self._issue(
            record_kind="area_geometry_update",
            payload=payload,
            pre_operation_state_json=pre,
            pre_operation_route_state_json=pre_route,
            target_id=target,
        )
        if entry_decision is None:
            if bound_entry is not None:
                for gate_id in self._entry_gate_ids(bound_entry):
                    self._current_required_operations.discard(
                        f"branch:{gate_id}:{target}"
                    )
                    self._current_required_operations.discard(f"branch:{gate_id}")
                self._current_required_operations.discard(
                    f"area_entry:{target}"
                )
            return geometry_record

        assert bound_entry is not None  # validated before mutation
        self._commit_entry_decision(
            transition=bound_entry,
            decision=entry_decision,
        )
        entry_payload = {
            "kind": "area_entry",
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "effect_id": bound_entry.effect_id,
            "area_id": bound_entry.area_id,
            "target_id": bound_entry.target_id,
            "entry_cause": bound_entry.cause,
            "turn_id": bound_entry.turn_id,
            "entry_policy": entry_decision["entry_policy"],
            "frequency_key": entry_decision["frequency_key"],
            "previously_triggered_this_turn": entry_decision[
                "previously_triggered_this_turn"
            ],
            "frequency_permitted": entry_decision["frequency_permitted"],
            "frequency_decision": entry_decision["frequency_decision"],
            "frequency_history_consumed": entry_decision[
                "frequency_history_consumed"
            ],
            "triggered": entry_decision["triggered"],
            "gate_opportunity_ids": (
                list(entry_decision["gate_ids"])
                if entry_decision["triggered"] else []
            ),
            "gate_requirement_ids": (
                list(entry_decision["gate_ids"])
                if entry_decision["triggered"] else []
            ),
            "ambient_area_component_ids": list(
                ambient_plan["ambient_component_ids"]
            ),
            "retained_ambient_component_ids": list(
                ambient_plan["retained_component_ids"]
            ),
            "restored_ambient_component_ids": list(restored_ambient_ids),
            "membership_before": False,
            "membership_after": True,
            "old_route_state": old_state.to_dict(),
            "new_route_state": new_state.to_dict(),
            "pre_route_state_sha256": transition["pre_route_state_sha256"],
            "post_route_state_sha256": transition["post_route_state_sha256"],
            "bound_transition": bound_entry.to_dict(),
            "geometry_operation_sequence": geometry_record.operation_sequence,
            "geometry_record_sha256": geometry_record.record_sha256,
        }
        entry_pre = _canonical_json(self._state.snapshot())
        entry_pre_route = self._area_route_state_json()
        self._state.audit_ledger.append({
            "operation": "area_entry",
            **entry_payload,
        })
        self._issue(
            record_kind="area_entry",
            payload=entry_payload,
            pre_operation_state_json=entry_pre,
            pre_operation_route_state_json=entry_pre_route,
            target_id=target,
        )
        return geometry_record

    def enumerate_prone_operations(
        self,
        *,
        target_id: str,
    ) -> _IssuedControlRecord:
        """Issue the complete legal Prone operation set from the closed pre-event state."""

        event = self._require_current(
            target_id=target_id,
            kinds={"target_movement_opportunity"},
        )
        target = _identifier(target_id, "target_id")
        if target in self._pending_prone_proposals:
            raise ControlEngineError(
                "A Prone operation proposal is already pending for this actor"
            )
        base_speeds = self._bound_input(
            "base_speeds_ft",
            target_id=target,
            default={},
        )
        movement_mode = _identifier(
            self._bound_input(
                "movement_mode",
                target_id=target,
                default="walk",
            ),
            "movement_mode",
        )
        mixed_order = self._bound_input(
            "mixed_speed_operation_order",
            target_id=target,
            default=None,
        )
        authority = self._engine._movement_state_authority(
            state=self._state,
            target_id=target,
            base_speeds_ft=base_speeds,
            mixed_speed_operation_order=mixed_order,
        )
        if movement_mode not in authority["effective_speeds_ft"]:
            raise ControlEngineError(
                "The selected movement mode has no scenario-bound current Speed"
            )
        if "walk" not in authority["effective_speeds_ft"]:
            raise ControlEngineError(
                "Prone operations require an explicit current walking Speed"
            )
        current_speed = authority["effective_speeds_ft"]["walk"]
        selected_mode_speed = authority["effective_speeds_ft"][movement_mode]
        movement_budget = self._bound_input(
            "movement_budget_ft",
            target_id=target,
            default=selected_mode_speed,
        )
        if (
            isinstance(movement_budget, bool)
            or not isinstance(movement_budget, int)
            or movement_budget < 0
        ):
            raise ControlEngineError(
                "movement_budget_ft must be a non-negative integer"
            )
        difficult_terrain = self._bound_input(
            "difficult_terrain",
            target_id=target,
            default=False,
        )
        if not isinstance(difficult_terrain, bool):
            raise ControlEngineError("difficult_terrain must be boolean")
        route_state = self._area_route_state_or_none(target)
        live_area_membership = bool(
            route_state is not None
            and route_state.membership
            and self._area_effect_is_active(route_state.area_id)
        )
        usable_route = True
        crawl_route_usable = True
        if live_area_membership and self._area_response_convention != "shortest_route_v1":
            # Fixed occupancy has no route-selection authority.  Retaining
            # Prone and dropping Prone remain explicit options, but standing
            # and crawling cannot borrow the stored geometry as a usable route.
            usable_route = False
            crawl_route_usable = False
        elif live_area_membership:
            assert route_state is not None
            adjusted_routes, _route_authority = (
                self._engine._state_adjusted_routes(
                    state=self._state,
                    target_id=target,
                    routes=[route.route_input() for route in route_state.routes],
                )
            )
            usable_rows = [
                row
                for row in (adjusted_routes or ())
                if row["compatible"]
                and authority["effective_speeds_ft"].get(row["mode"], 0) > 0
                and row["mode"] not in set(authority["denied_modes"])
            ]
            usable_route = bool(usable_rows)
            crawl_route_usable = any(
                _positive_fraction(
                    row["movement_cost_multiplier"],
                    "area route movement_cost_multiplier",
                )
                in {Fraction(1), Fraction(2)}
                for row in usable_rows
            )
            if usable_rows:
                difficult_terrain = all(
                    _positive_fraction(
                        row["movement_cost_multiplier"],
                        "area route movement_cost_multiplier",
                    ) == 2
                    for row in usable_rows
                )
        prone = "prone" in self._state.derived_current_conditions(target)
        proposals = enumerate_prone_movement_operations(
            target_id=target,
            actor_id=target,
            prone=prone,
            current_speed_ft=current_speed,
            movement_budget_ft=movement_budget,
            difficult_terrain=difficult_terrain,
            movement_denied=movement_mode in set(authority["denied_modes"]),
            actor_owns_opportunity=(
                event.actor_id == target
                and event.target_id == target
                and event.turn_owner == "target"
            ),
            usable_route=usable_route,
        )
        if not crawl_route_usable:
            proposals = [
                proposal
                for proposal in proposals
                if proposal["kind"] != "crawl"
            ]
        if (
            "prone" in self._targets_by_id[target].condition_immunities
            and not prone
        ):
            proposals = [
                proposal
                for proposal in proposals
                if proposal["kind"] != "drop_prone"
            ]
        drop_fall_context: dict[str, Any] | None = None
        if any(proposal["kind"] == "drop_prone" for proposal in proposals):
            drop_fall_context = self._validated_fall_context(
                self._bound_input(
                    "fall_context",
                    target_id=target,
                    default=None,
                ),
                required=True,
            )
        pre = _canonical_json(self._state.snapshot())
        proposal = self._issue(
            record_kind="prone_operation_proposal",
            payload={
                "kind": "prone_operation_proposal",
                "event_id": event.event_id,
                "event_sequence": event.sequence,
                "target_id": target,
                "actor_id": target,
                "prone_before": prone,
                "movement_mode": movement_mode,
                "current_speed_ft": current_speed,
                "movement_budget_ft": movement_budget,
                "difficult_terrain": difficult_terrain,
                "usable_route": usable_route,
                "movement_authority": authority,
                "operations": proposals,
                "drop_prone_fall_context": drop_fall_context,
            },
            pre_operation_state_json=pre,
            target_id=target,
        )
        self._pending_prone_proposals[target] = proposal
        self._movement_response_required = True
        return proposal

    def _require_pending_prone_operation(
        self,
        *,
        target_id: str,
        proposal: _IssuedControlRecord,
        operation: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._require_locally_issued_record(proposal)
        pending = self._pending_prone_proposals.get(target_id)
        if (
            pending is not proposal
            or proposal.record_kind != "prone_operation_proposal"
            or proposal.operation_sequence in self._consumed_prone_proposal_sequences
            or proposal.event_id
            != (self._current_event.event_id if self._current_event else None)
            or proposal.post_operation_state_json
            != _canonical_json(self._state.snapshot())
            or proposal.post_operation_route_state_json
            != self._area_route_state_json()
        ):
            raise ControlEngineError(
                "Prone operation proposal is foreign, stale, consumed, or rewritten"
            )
        if not isinstance(operation, Mapping):
            raise ControlEngineError("prone_operation must be an object")
        selected = _strict_json_copy(operation, "prone_operation")
        payload = json.loads(proposal.payload_json)
        if selected not in payload["operations"]:
            raise ControlEngineError(
                "Selected Prone operation was not in the issued proposal set"
            )
        return selected, payload

    def _end_prone_for_operation(
        self,
        *,
        target_id: str,
        event: TimelineEvent,
        reason: str,
    ) -> tuple[Mapping[str, Any], ...]:
        ended: list[Mapping[str, Any]] = []
        for instance in tuple(self._state.active_condition_instances(target_id)):
            if instance.condition_id != "prone":
                continue
            ended.extend(self._state.end_condition_instance(
                instance.instance_id,
                event_id=event.event_id,
                event_sequence=event.sequence,
                reason=reason,
                expected_source_actor_id=instance.source_actor_id,
                expected_issuance_id=instance.issuance_id,
            ))
        return tuple(ended)

    def _apply_voluntary_drop_prone(
        self,
        *,
        target_id: str,
        event: TimelineEvent,
        proposal: _IssuedControlRecord,
    ) -> tuple[dict[str, Any], ...]:
        before = {
            row["instance_id"] for row in self._state.instance_registry()
        }
        applied = self._state.apply_component(
            effect_id="prone_operation",
            component={
                "component_id": f"{event.event_id}:drop_prone",
                "magnitude": {"kind": "condition", "condition": "prone"},
                "duration": {"kind": "until_condition_response"},
                "stacking": {
                    "key": f"prone_operation:{proposal.record_sha256}",
                    "mode": "independent",
                    "refresh": "none",
                },
            },
            target_id=target_id,
            source_actor_id=target_id,
            event_id=event.event_id,
            invocation_id=self._invocation_id,
            condition_immunities=(
                self._targets_by_id[target_id].condition_immunities
            ),
            application_sequence=event.sequence,
            source_program_id="control_execution_session_v2",
            issuance_id=proposal.record_sha256,
            provenance_id=self._scenario_digest,
        )
        if applied is None:
            raise ControlEngineError(
                "Voluntary drop Prone was unexpectedly suppressed"
            )
        return tuple(
            row for row in self._state.instance_registry()
            if row["instance_id"] not in before
        )

    def _record_voluntary_drop_fall(
        self,
        *,
        event: TimelineEvent,
        target_id: str,
        instances: Sequence[Mapping[str, Any]],
        proposal_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        record = self._condition_application_fall_record(
            event=event,
            target_id=target_id,
            new_instances=instances,
            fall_context=proposal_payload.get("drop_prone_fall_context"),
        )
        if record is None:  # pragma: no cover - drop always creates Prone
            raise ControlEngineError("Voluntary drop omitted its fall transition")
        if record["executed"]:
            self._fall_transition_identities.add((event.event_id, target_id))
        self._fall_transition_records.append(record)
        return record

    def _completed_prone_operation_record(
        self,
        *,
        event: TimelineEvent,
        target_id: str,
        movement_mode: str,
        proposal: _IssuedControlRecord,
        proposal_payload: Mapping[str, Any],
        response: Mapping[str, Any],
        area_response_operation: bool,
        prone_components_before: Sequence[Any],
        created_condition_instances: Sequence[Mapping[str, Any]],
        fall_transition: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Build and audit one canonical explicit Prone-operation result."""

        active_components_after = self._state.snapshot(target_id)
        active_component_instance_ids = {
            row["instance_id"] for row in active_components_after
        }
        active_condition_instance_ids = {
            instance.instance_id
            for instance in self._state.active_condition_instances(target_id)
        }
        ended_condition_instance_ids = sorted({
            component.condition_instance_id
            for component in prone_components_before
            if component.condition_instance_id is not None
            and component.condition_instance_id not in active_condition_instance_ids
        })
        record = {
            "event_id": event.event_id,
            "event_sequence": event.sequence,
            "proposal_operation_sequence": proposal.operation_sequence,
            "proposal_record_sha256": proposal.record_sha256,
            "movement_mode": movement_mode,
            "movement_authority": proposal_payload["movement_authority"],
            "area_response_operation": area_response_operation,
            **dict(_json_safe(response)),
            "kind": "prone_operation",
            "ended_component_ids": sorted({
                component.component_id
                for component in prone_components_before
                if component.instance_id not in active_component_instance_ids
            }),
            "ended_condition_instance_ids": ended_condition_instance_ids,
            "active_conditions_after": list(
                self._state.derived_current_conditions(target_id)
            ),
            "created_condition_instances": list(
                _json_safe(created_condition_instances)
            ),
            "fall_transition": (
                None
                if fall_transition is None
                else dict(_json_safe(fall_transition))
            ),
            "active_components_after": active_components_after,
        }
        self._state.audit_ledger.append({
            "operation": "prone_operation",
            "prone_operation": record["operation"],
            **{
                field_name: value
                for field_name, value in record.items()
                if field_name != "operation"
            },
        })
        return record

    def resolve_movement_response(
        self,
        *,
        target_id: str,
        prone_proposal: _IssuedControlRecord | None = None,
        prone_operation: Mapping[str, Any] | None = None,
    ) -> tuple[_IssuedControlRecord, ...]:
        event = self._require_current(
            target_id=target_id,
            kinds={"target_movement_opportunity"},
        )
        self._require_pending_normalization_complete_before_mutation(
            target_id
        )
        if self._movement_response_consumed:
            raise ControlEngineError(
                "The current event's movement budget was already consumed"
            )
        target = _identifier(target_id, "target_id")
        base_speeds = self._bound_input(
            "base_speeds_ft",
            target_id=target,
            default={},
        )
        movement_mode = self._bound_input(
            "movement_mode",
            target_id=target,
            default="walk",
        )
        mixed_order = self._bound_input(
            "mixed_speed_operation_order",
            target_id=target,
            default=None,
        )
        epoch_movement_mode = movement_mode
        epoch_legal = True
        epoch_movement_authority: dict[str, Any] | None = None
        if target in self._displaced_targets:
            if not base_speeds:
                raise ControlEngineError(
                    "Displacement epoch response requires bound base_speeds_ft"
                )
            epoch_movement_authority = self._engine._movement_state_authority(
                state=self._state,
                target_id=target,
                base_speeds_ft=base_speeds,
                mixed_speed_operation_order=mixed_order,
            )
        area_component_ids = self._active_area_component_ids(target)
        authoritative_area_state = self._area_route_state_or_none(target)
        if area_component_ids:
            if authoritative_area_state is None:
                raise ControlEngineError(
                    "Active area-bound components lack authoritative live area "
                    f"membership for target {target!r}"
                )
        fixed_area_effect_active: bool | None = None
        fixed_area_response_required = bool(
            self._area_response_convention != "shortest_route_v1"
            and area_component_ids
            and authoritative_area_state is not None
            and authoritative_area_state.membership
        )
        if fixed_area_response_required:
            fixed_area_effect_active = self._bound_input(
                "area_effect_active", target_id=target, default=True
            )
            if fixed_area_effect_active is not True:
                raise ControlEngineError(
                    "Movement response cannot retain active area components "
                    "for an effect already marked ended"
                )
        route_state = (
            authoritative_area_state
            if self._area_response_convention == "shortest_route_v1"
            else None
        )
        live_area_membership = bool(
            route_state is not None
            and route_state.membership
            and self._area_effect_is_active(route_state.area_id)
        )
        prone_components_before = tuple(
            component
            for component in self._state.active_components(target)
            if component.magnitude.get("kind") == "condition"
            and component.magnitude.get("condition") == "prone"
        )
        prone = bool(prone_components_before)
        selected_prone_operation: dict[str, Any] | None = None
        prone_proposal_payload: dict[str, Any] | None = None
        drop_condition_instances: tuple[dict[str, Any], ...] = ()
        drop_fall_record: dict[str, Any] | None = None
        if (prone_proposal is None) != (prone_operation is None):
            raise ControlEngineError(
                "prone_proposal and prone_operation must be supplied together"
            )
        if prone_proposal is not None and prone_operation is not None:
            selected_prone_operation, prone_proposal_payload = (
                self._require_pending_prone_operation(
                    target_id=target,
                    proposal=prone_proposal,
                    operation=prone_operation,
                )
            )
        elif prone:
            raise ControlEngineError(
                "A Prone movement response requires an issued explicit operation"
            )
        issued: list[_IssuedControlRecord] = []

        if live_area_membership:
            if route_state is None:  # pragma: no cover - narrowed above
                raise ControlEngineError("Missing live session-owned area route state")
            routes = [route.route_input() for route in route_state.routes]
            pre = _canonical_json(self._state.snapshot())
            pre_route = self._area_route_state_json()
            area = self._engine._resolve_area_response(
                state=self._state,
                schedule=self._schedule,
                effect=self._program,
                target_ids=self._schedule.target_ids,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                target_id=target,
                event_id=event.event_id,
                area_response_convention=self._area_response_convention,
                membership=True,
                effect_active=True,
                routes=routes,
                base_speeds_ft=base_speeds,
                mixed_speed_operation_order=mixed_order,
                prone_operation=selected_prone_operation,
                prone_current_speed_ft=(
                    None
                    if prone_proposal_payload is None
                    else prone_proposal_payload["current_speed_ft"]
                ),
                movement_budget_ft=(
                    None
                    if prone_proposal_payload is None
                    else prone_proposal_payload["movement_budget_ft"]
                ),
            )
            if (
                selected_prone_operation is not None
                and selected_prone_operation["kind"] == "drop_prone"
            ):
                if prone_proposal is None:  # pragma: no cover
                    raise ControlEngineError("Missing issued Prone proposal")
                drop_condition_instances = self._apply_voluntary_drop_prone(
                    target_id=target,
                    event=event,
                    proposal=prone_proposal,
                )
                if prone_proposal_payload is None:  # pragma: no cover
                    raise ControlEngineError("Missing issued Prone proposal payload")
                drop_fall_record = self._record_voluntary_drop_fall(
                    event=event,
                    target_id=target,
                    instances=drop_condition_instances,
                    proposal_payload=prone_proposal_payload,
                )
                area = {
                    **area,
                    "active_components_after": self._state.snapshot(target),
                }
            area_authority = area.get("movement_authority")
            if isinstance(area_authority, Mapping):
                epoch_movement_authority = {
                    key: area_authority[key]
                    for key in (
                        "source",
                        "base_speeds_ft",
                        "effective_speeds_ft",
                        "speed_zero_modes",
                        "denied_modes",
                        "mixed_speed_operation_order",
                        "source_component_ids",
                    )
                }
            selected_route = area.get("selected_route")
            if isinstance(selected_route, Mapping):
                epoch_movement_mode = str(selected_route["mode"])
                route_id = str(selected_route["route_id"])
                source_routes = {
                    route.route_id: route for route in route_state.routes
                }
                if route_id not in source_routes:
                    raise ControlEngineError(
                        "Area response selected a route outside session geometry"
                    )
                remaining = _nonnegative_fraction(
                    selected_route["remaining_distance_exact"],
                    "selected route remaining distance",
                )
                selected_geometry = replace(
                    source_routes[route_id],
                    distance_to_exit_ft=remaining,
                )
                new_route_state = replace(
                    route_state,
                    membership=remaining > 0,
                    routes=(selected_geometry,),
                    selected_route_id=route_id,
                    movement_mode=selected_geometry.mode,
                    environment=selected_geometry.environment,
                    remaining_distance_ft=remaining,
                    movement_cost_basis=_json_safe(area_authority),
                    closed_reason=(
                        "route_exhausted" if remaining == 0 else None
                    ),
                    last_update_event_id=event.event_id,
                    last_update_event_sequence=event.sequence,
                )
                transition_kind = (
                    "route_exit" if remaining == 0 else "movement_progress"
                )
            else:
                new_route_state = replace(
                    route_state,
                    movement_cost_basis=_json_safe(area_authority),
                    last_update_event_id=event.event_id,
                    last_update_event_sequence=event.sequence,
                )
                transition_kind = "movement_blocked"
            self._set_area_route_state(new_route_state)
            if route_state.membership and not new_route_state.membership:
                self._prune_future_area_gate_operations(
                    area_id=route_state.area_id,
                    target_id=target,
                )
            route_transition = self._route_transition(
                transition_kind=transition_kind,
                event=event,
                old_state=route_state,
                new_state=new_route_state,
                pre_route_state_json=pre_route,
            )
            area = {**area, "route_transition": route_transition}
            for audit_index in range(
                len(self._state.audit_ledger) - 1,
                -1,
                -1,
            ):
                audit_row = self._state.audit_ledger[audit_index]
                if (
                    audit_row.get("operation") == "area_response"
                    and audit_row.get("event_id") == event.event_id
                    and audit_row.get("target_id") == target
                    and audit_row.get("effect_id") == self._program.effect_id
                ):
                    self._state.audit_ledger[audit_index] = {
                        "operation": "area_response",
                        **area,
                    }
                    break
            else:  # pragma: no cover - engine response always audits itself
                raise ControlEngineError(
                    "Area response omitted its required state-audit row"
                )
            self._area_records.append(area)
            issued.append(self._issue(
                record_kind="area_response",
                payload=area,
                pre_operation_state_json=pre,
                pre_operation_route_state_json=pre_route,
                target_id=target,
            ))
            if (
                selected_prone_operation is not None
                and not fixed_area_response_required
            ):
                if prone_proposal is None or prone_proposal_payload is None:
                    raise ControlEngineError("Missing issued Prone proposal")
                prone_response_record = (
                    (area.get("selected_route") or {}).get("prone_response")
                    or area.get("prone_response")
                )
                if not isinstance(prone_response_record, Mapping):
                    raise ControlEngineError(
                        "Area response omitted its explicit Prone operation result"
                    )
                prone_record = self._completed_prone_operation_record(
                    event=event,
                    target_id=target,
                    movement_mode=movement_mode,
                    proposal=prone_proposal,
                    proposal_payload=prone_proposal_payload,
                    response=prone_response_record,
                    area_response_operation=True,
                    prone_components_before=prone_components_before,
                    created_condition_instances=drop_condition_instances,
                    fall_transition=drop_fall_record,
                )
                self._prone_records.append(prone_record)
                prone_pre = _canonical_json(self._state.snapshot())
                issued.append(self._issue(
                    record_kind="prone_operation",
                    payload=prone_record,
                    pre_operation_state_json=prone_pre,
                    target_id=target,
                ))
        else:
            if (
                selected_prone_operation is not None
                and not fixed_area_response_required
            ):
                if prone_proposal_payload is None:  # pragma: no cover
                    raise ControlEngineError("Missing issued Prone proposal payload")
                pre = _canonical_json(self._state.snapshot())
                prone_record = prone_movement_response(
                    target_id=target,
                    actor_id=target,
                    kind=selected_prone_operation["kind"],
                    prone=prone,
                    current_speed_ft=prone_proposal_payload["current_speed_ft"],
                    movement_budget_ft=prone_proposal_payload[
                        "movement_budget_ft"
                    ],
                    distance_feet=selected_prone_operation.get("distance_feet"),
                    difficult_terrain=prone_proposal_payload[
                        "difficult_terrain"
                    ],
                    movement_denied=(
                        movement_mode
                        in set(
                            prone_proposal_payload["movement_authority"][
                                "denied_modes"
                            ]
                        )
                    ),
                    actor_owns_opportunity=True,
                    usable_route=prone_proposal_payload["usable_route"],
                )
                if prone_record["stood"]:
                    self._end_prone_for_operation(
                        target_id=target,
                        event=event,
                        reason="explicit_stand_operation",
                    )
                if prone_record["dropped_prone"]:
                    drop_condition_instances = self._apply_voluntary_drop_prone(
                        target_id=target,
                        event=event,
                        proposal=prone_proposal,
                    )
                    drop_fall_record = self._record_voluntary_drop_fall(
                        event=event,
                        target_id=target,
                        instances=drop_condition_instances,
                        proposal_payload=prone_proposal_payload,
                    )
                prone_record = self._completed_prone_operation_record(
                    event=event,
                    target_id=target,
                    movement_mode=movement_mode,
                    proposal=prone_proposal,
                    proposal_payload=prone_proposal_payload,
                    response=prone_record,
                    area_response_operation=False,
                    prone_components_before=prone_components_before,
                    created_condition_instances=drop_condition_instances,
                    fall_transition=drop_fall_record,
                )
                self._prone_records.append(prone_record)
                issued.append(self._issue(
                    record_kind="prone_operation",
                    payload=prone_record,
                    pre_operation_state_json=pre,
                    target_id=target,
                ))
            if fixed_area_response_required:
                if authoritative_area_state is None:  # pragma: no cover - preflight
                    raise ControlEngineError(
                        "Fixed-occupancy area response lost authoritative "
                        "membership state"
                    )
                if fixed_area_effect_active is not True:  # pragma: no cover - preflight
                    raise ControlEngineError(
                        "Fixed-occupancy area response lost active-area authority"
                    )
                pre = _canonical_json(self._state.snapshot())
                area = self._engine._resolve_area_response(
                    state=self._state,
                    schedule=self._schedule,
                    effect=self._program,
                    target_ids=self._schedule.target_ids,
                    selector_membership=self._membership,
                    selector_context=self._selector_context,
                    target_id=target,
                    event_id=event.event_id,
                    area_response_convention=self._area_response_convention,
                    membership=authoritative_area_state.membership,
                    effect_active=fixed_area_effect_active,
                    prone_operation=selected_prone_operation,
                    prone_current_speed_ft=(
                        None
                        if prone_proposal_payload is None
                        else prone_proposal_payload["current_speed_ft"]
                    ),
                    movement_budget_ft=(
                        None
                        if prone_proposal_payload is None
                        else prone_proposal_payload["movement_budget_ft"]
                    ),
                )
                if (
                    selected_prone_operation is not None
                    and selected_prone_operation["kind"] == "drop_prone"
                ):
                    if prone_proposal is None:  # pragma: no cover
                        raise ControlEngineError("Missing issued Prone proposal")
                    drop_condition_instances = self._apply_voluntary_drop_prone(
                        target_id=target,
                        event=event,
                        proposal=prone_proposal,
                    )
                    if prone_proposal_payload is None:  # pragma: no cover
                        raise ControlEngineError(
                            "Missing issued Prone proposal payload"
                        )
                    drop_fall_record = self._record_voluntary_drop_fall(
                        event=event,
                        target_id=target,
                        instances=drop_condition_instances,
                        proposal_payload=prone_proposal_payload,
                    )
                    area = {
                        **area,
                        "active_components_after": self._state.snapshot(target),
                    }
                for audit_index in range(
                    len(self._state.audit_ledger) - 1,
                    -1,
                    -1,
                ):
                    audit_row = self._state.audit_ledger[audit_index]
                    if (
                        audit_row.get("operation") == "area_response"
                        and audit_row.get("event_id") == event.event_id
                        and audit_row.get("target_id") == target
                        and audit_row.get("effect_id") == self._program.effect_id
                    ):
                        self._state.audit_ledger[audit_index] = {
                            "operation": "area_response",
                            **area,
                        }
                        break
                else:  # pragma: no cover - engine response always audits itself
                    raise ControlEngineError(
                        "Fixed-area response omitted its required state-audit row"
                    )
                self._area_records.append(area)
                issued.append(self._issue(
                    record_kind="area_response",
                    payload=area,
                    pre_operation_state_json=pre,
                    target_id=target,
                ))
                if selected_prone_operation is not None:
                    if prone_proposal is None or prone_proposal_payload is None:
                        raise ControlEngineError("Missing issued Prone proposal")
                    prone_response_record = area.get("prone_response")
                    if not isinstance(prone_response_record, Mapping):
                        raise ControlEngineError(
                            "Fixed-area response omitted its explicit Prone result"
                        )
                    prone_record = self._completed_prone_operation_record(
                        event=event,
                        target_id=target,
                        movement_mode=movement_mode,
                        proposal=prone_proposal,
                        proposal_payload=prone_proposal_payload,
                        response=prone_response_record,
                        area_response_operation=True,
                        prone_components_before=prone_components_before,
                        created_condition_instances=drop_condition_instances,
                        fall_transition=drop_fall_record,
                    )
                    self._prone_records.append(prone_record)
                    prone_pre = _canonical_json(self._state.snapshot())
                    issued.append(self._issue(
                        record_kind="prone_operation",
                        payload=prone_record,
                        pre_operation_state_json=prone_pre,
                        target_id=target,
                    ))

        if target in self._displaced_targets:
            if epoch_movement_authority is None:  # pragma: no cover - invariant
                raise ControlEngineError("Missing bound displacement movement authority")
            effective_speeds = epoch_movement_authority["effective_speeds_ft"]
            denied_modes = set(epoch_movement_authority["denied_modes"])
            if not effective_speeds:
                epoch_legal = False
                raise ControlEngineError(
                    "Displacement response has no bound movement mode"
                )
            legal_positive_modes = tuple(
                mode
                for mode, speed in effective_speeds.items()
                if mode not in denied_modes and speed > 0
            )
            legal_zero_modes = tuple(
                mode
                for mode, speed in effective_speeds.items()
                if mode not in denied_modes and speed == 0
            )
            if (
                epoch_movement_mode not in effective_speeds
                or (
                    epoch_movement_mode in denied_modes
                    and legal_positive_modes
                )
                or (
                    effective_speeds[epoch_movement_mode] == 0
                    and legal_positive_modes
                )
            ):
                epoch_movement_mode = (
                    legal_positive_modes[0]
                    if legal_positive_modes
                    else legal_zero_modes[0]
                    if legal_zero_modes
                    else next(iter(effective_speeds))
                )
            epoch_legal = bool(legal_positive_modes or legal_zero_modes)
            movement_denied = epoch_movement_mode in denied_modes
            speed_zero = (
                effective_speeds[epoch_movement_mode] == 0
                and not movement_denied
            )
            pre = _canonical_json(self._state.snapshot())
            epoch_record = self._epochs.self_movement_opportunity(
                target_id=target,
                legal=epoch_legal,
                speed_zero=speed_zero,
                movement_denied=movement_denied,
            )
            epoch = {
                "record": {
                    **epoch_record,
                    "event_id": event.event_id,
                    "source": "typed_self_movement_opportunity",
                    "movement_mode": epoch_movement_mode,
                    "movement_authority": epoch_movement_authority,
                },
            }
            self._displacement_records.append(epoch)
            issued.append(self._issue(
                record_kind="displacement_epoch_boundary",
                payload=epoch,
                pre_operation_state_json=pre,
                target_id=target,
            ))
            if epoch.get("record", {}).get("reset") is True:
                self._displaced_targets.remove(target)

        self._movement_response_consumed = True
        self._movement_response_required = False
        if prone_proposal is not None:
            self._consumed_prone_proposal_sequences.add(
                prone_proposal.operation_sequence
            )
            self._pending_prone_proposals.pop(target, None)
        self._current_required_operations.discard("movement_response")
        return tuple(issued)

    def start_concentration(self) -> _IssuedControlRecord:
        event = self._require_current()
        if (
            not self._concentration_required
            or event.event_id != self._concentration_start_event_id
            or "concentration_start" not in self._current_required_operations
        ):
            raise ControlEngineError(
                "Concentration startup is not required at the current event"
            )
        tracker = self._concentration_tracker
        if tracker is None:
            raise ControlEngineError(
                "The scenario does not bind a concentration save bonus"
            )
        if tracker.active_effect_id is not None:
            raise ControlEngineError(
                "End the prior concentration at its own event before replacement"
            )
        pre = _canonical_json(self._state.snapshot())
        lifecycle = self._engine._start_concentration(
            state=self._state,
            tracker=tracker,
            effect=self._program,
            event_id=event.event_id,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            startup_blood_tax=self._bound_input(
                "startup_blood_tax", default=0
            ),
            choices=self._choices,
        )
        self._area_effect_started = True
        self._area_effect_ended = False
        self._concentration_records.append(lifecycle)
        self._current_required_operations.discard("concentration_start")
        return self._issue(
            record_kind="concentration_start",
            payload=lifecycle,
            pre_operation_state_json=pre,
        )

    def check_concentration(self) -> _IssuedControlRecord:
        event = self._require_current(kinds={"damage_context"})
        tracker = self._concentration_tracker
        if tracker is None:
            raise ControlEngineError(
                "The scenario does not bind a concentration save bonus"
            )
        if self._pending_concentration_failure is not None:
            raise ControlEngineError(
                "A failed concentration check is already pending its typed end"
            )
        if "concentration_check" not in self._current_required_operations:
            raise ControlEngineError(
                "A concentration check is not required at the current event"
            )
        amount = self._bound_input("concentration_amount")
        source = self._bound_input("concentration_source")
        outcome = self._bound_input("concentration_outcome")
        success_probability = self._bound_input(
            "concentration_success_probability", default=None
        )
        roll_kernel = self._bound_input(
            "concentration_roll_kernel", default=None
        )
        pre = _canonical_json(self._state.snapshot())
        if outcome == "success":
            lifecycle = self._engine._check_concentration(
                state=self._state,
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                amount=amount,
                source=source,
                event_id=event.event_id,
                outcome=outcome,
                success_probability=success_probability,
                roll_kernel=roll_kernel,
                choices=self._choices,
            )
            self._concentration_records.append(lifecycle)
            self._current_required_operations.discard("concentration_check")
            return self._issue(
                record_kind="concentration_check",
                payload=lifecycle,
                pre_operation_state_json=pre,
            )
        if outcome != "failure":
            raise ControlEngineError("concentration_outcome must be success or failure")
        end_event_id = _identifier(
            self._bound_input("concentration_end_event_id"),
            "concentration_end_event_id",
        )
        try:
            end_event = self._schedule.event(end_event_id)
        except TimelineError as error:
            raise ControlEngineError(
                "unknown concentration end event; a failed check must bind "
                "the immediate typed end"
            ) from error
        if end_event.sequence != event.sequence + 1 or end_event.kind != "concentration_end":
            raise ControlEngineError(
                "A failed concentration check must bind the immediate typed end event"
            )
        context = self._engine._active_concentration_context(
            tracker=tracker,
            effect=self._program,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            choices=self._choices,
        )
        plans = self._engine._concentration_end_plan(
            state=self._state,
            context=context,
            event_id=end_event_id,
            reason="failed_concentration_save",
        )
        affected_target_ids = self._concentration_end_mutation_target_ids(
            context=context,
            plans=plans,
        )
        self._require_pending_normalization_complete_before_mutation(
            *affected_target_ids
        )
        (
            check_record,
            tracker_end_record,
            tracker_pre_state_json,
            tracker_post_check_state_json,
        ) = self._preview_failed_concentration_tracker_records(
            tracker=tracker,
            amount=amount,
            source=source,
            damage_event_id=event.event_id,
            end_event_id=end_event.event_id,
            success_probability=success_probability,
            roll_kernel=roll_kernel,
        )
        self._require_failed_tracker_end_matches_context(
            tracker_end_record,
            context=context,
            end_event_id=end_event.event_id,
        )
        pending = self._new_pending_concentration_failure(
            event=event,
            end_event=end_event,
            check_record=check_record,
            tracker_pre_state_json=tracker_pre_state_json,
            tracker_post_check_state_json=tracker_post_check_state_json,
            tracker_end_record=tracker_end_record,
            context=context,
            plans=plans,
            affected_target_ids=affected_target_ids,
        )
        tracker.records.append(deepcopy(check_record))
        if (
            self._concentration_tracker_state_json(tracker)
            != tracker_post_check_state_json
        ):
            raise ControlEngineError(
                "Tracker did not commit the previewed failed check"
            )
        issued = self._issue(
            record_kind="concentration_check_pending_end",
            payload={
                "kind": "concentration_check_pending_end",
                "pending_failure": pending.to_dict(),
            },
            pre_operation_state_json=pre,
        )
        self._pending_concentration_failure = pending
        self._pending_concentration_failure_original = pending
        self._pending_concentration_failure_attestation = pending.pending_sha256
        self._current_required_operations.discard("concentration_check")
        return issued

    def end_concentration(self) -> _IssuedControlRecord:
        event = self._require_current()
        tracker = self._concentration_tracker
        if tracker is None:
            raise ControlEngineError(
                "The scenario does not bind a concentration save bonus"
            )
        pre = _canonical_json(self._state.snapshot())
        required_gate_labels = {
            operation
            for operation in self._current_required_operations
            if operation.startswith("concentration_end:")
        }
        pending = self._pending_concentration_failure
        if pending is not None:
            self._require_locally_issued_pending_concentration_failure(
                pending,
                event=event,
                tracker=tracker,
            )
            context = self._engine._active_concentration_context(
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                choices=self._choices,
            )
            if (
                _canonical_json(
                    self._engine._concentration_authority_metadata(context)
                )
                != pending.authority_metadata_json
            ):
                raise ControlEngineError(
                    "Pending concentration failure authority context is stale"
                )
            planned_end_transitions = self._engine._concentration_end_plan(
                state=self._state,
                context=context,
                event_id=event.event_id,
                reason="failed_concentration_save",
            )
            if tuple(planned_end_transitions) != pending.end_plan:
                raise ControlEngineError(
                    "Pending concentration failure end plan is stale or rewritten"
                )
        else:
            context = self._engine._active_concentration_context(
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                choices=self._choices,
            )
            end_reason = self._bound_input("concentration_end_reason")
            if end_reason == "failed_concentration_save":
                raise ControlEngineError(
                    "A failed concentration end requires its matching pending check"
                )
            planned_end_transitions = self._engine._concentration_end_plan(
                state=self._state,
                context=context,
                event_id=event.event_id,
                reason=end_reason,
            )
        affected_target_ids = self._concentration_end_mutation_target_ids(
            context=context,
            plans=planned_end_transitions,
        )
        if (
            pending is not None
            and affected_target_ids != pending.affected_target_ids
        ):
            raise ControlEngineError(
                "Pending concentration failure affected targets are stale"
            )
        self._require_pending_normalization_complete_before_mutation(
            *affected_target_ids
        )
        planned_gate_labels = {
            f"concentration_end:{gate_id}:{target_id}"
            for gate_id, target_id, _outcome in planned_end_transitions
        }
        if required_gate_labels != planned_gate_labels:
            raise ControlEngineError(
                "Concentration lifecycle gate plan does not match the bound "
                f"reliability path: required={sorted(required_gate_labels)}, "
                f"planned={sorted(planned_gate_labels)}"
            )
        if pending is not None:
            simulated = deepcopy(tracker)
            previewed_end_record = simulated.end(
                reason="failed_concentration_save",
                event_id=event.event_id,
            )
            self._require_failed_tracker_end_matches_context(
                previewed_end_record,
                context=context,
                end_event_id=event.event_id,
            )
            if (
                _canonical_json(previewed_end_record)
                != pending.tracker_end_record_json
            ):
                raise ControlEngineError(
                    "Pending concentration failure tracker end is stale"
                )
            previewed_transition = self._engine._apply_concentration_end_record(
                state=deepcopy(self._state),
                record=previewed_end_record,
                context=context,
                plans=planned_end_transitions,
            )
            previewed_plan = tuple(
                (
                    transition.get("gate_id"),
                    transition.get("target_id"),
                    transition.get("filtered_branch", {}).get("outcome"),
                )
                for transition in previewed_transition.get(
                    "concentration_end_gate_transitions",
                    (),
                )
                if isinstance(transition, Mapping)
            )
            if previewed_plan != tuple(planned_end_transitions):
                raise ControlEngineError(
                    "Previewed concentration-end gates differ from the exact "
                    "compiled pending plan"
                )
            end_record = tracker.end(
                reason="failed_concentration_save",
                event_id=event.event_id,
            )
            if end_record != previewed_end_record:  # pragma: no cover - invariant
                raise ControlEngineError(
                    "Tracker end differed from its validated preview"
                )
            transition = self._engine._apply_concentration_end_record(
                state=self._state,
                record=end_record,
                context=context,
                plans=planned_end_transitions,
            )
            if transition != previewed_transition:  # pragma: no cover - invariant
                raise ControlEngineError(
                    "Concentration end differed from its validated state preview"
                )
            self._engine._concentration_contexts.pop(tracker, None)
            check_record = json.loads(pending.check_record_json)
            lifecycle = {
                "kind": "concentration_check_lifecycle",
                "check_record": check_record,
                "tracker_records": [check_record, end_record],
                "applied_end_transitions": [transition],
                "active_effect_id": None,
                "active_components_after": self._state.snapshot(),
            }
            lifecycle = self._engine._audited_lifecycle_result(
                self._state,
                "concentration_check_lifecycle",
                lifecycle,
            )
        else:
            lifecycle = self._engine._end_concentration(
                state=self._state,
                tracker=tracker,
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                reason=end_reason,
                event_id=event.event_id,
                choices=self._choices,
            )
        end_transitions: list[Mapping[str, Any]] = [
            transition
            for transition in lifecycle.get(
                "concentration_end_gate_transitions",
                (),
            )
            if isinstance(transition, Mapping)
        ]
        for wrapper in lifecycle.get("applied_end_transitions", ()):
            if not isinstance(wrapper, Mapping):
                continue
            end_transitions.extend(
                transition
                for transition in wrapper.get(
                    "concentration_end_gate_transitions",
                    (),
                )
                if isinstance(transition, Mapping)
            )
        applied_gate_labels = {
            "concentration_end:"
            f"{transition['gate_id']}:{transition['target_id']}"
            for transition in end_transitions
            if transition.get("operation") == "branch_transition"
        }
        missing_gate_labels = sorted(required_gate_labels - applied_gate_labels)
        if missing_gate_labels:
            raise ControlEngineError(
                "Concentration lifecycle did not execute its required compiled "
                f"end gates: {missing_gate_labels}"
            )
        self._concentration_records.append(lifecycle)
        self._current_required_operations.discard("concentration_end")
        self._current_required_operations.difference_update(required_gate_labels)
        issued = self._issue(
            record_kind="concentration_end",
            payload=lifecycle,
            pre_operation_state_json=pre,
        )
        self._area_effect_ended = True
        self._close_area_routes_for_effect_end(
            event=event,
            reason="effect_ended",
        )
        if pending is not None:
            self._pending_concentration_failure = None
            self._pending_concentration_failure_original = None
            self._pending_concentration_failure_attestation = None
        return issued

    def reconcile_concentration_duration(self) -> _IssuedControlRecord:
        event = self._require_current()
        tracker = self._concentration_tracker
        if tracker is None:
            raise ControlEngineError(
                "The scenario does not bind a concentration save bonus"
            )
        if self._pending_concentration_failure is not None:
            raise ControlEngineError(
                "A pending failed check must end at its bound typed event before "
                "duration reconciliation"
            )
        context = self._engine._active_concentration_context(
            tracker=tracker,
            effect=self._program,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            choices=self._choices,
        )
        expiry_event_id = self._engine._recomputed_concentration_expiry_event_id(
            context
        )
        if expiry_event_id == event.event_id:
            plans = self._engine._concentration_end_plan(
                state=self._state,
                context=context,
                event_id=event.event_id,
                reason="duration_expiry",
            )
            self._require_pending_normalization_complete_before_mutation(
                *self._effect_mutation_target_ids(
                    additional_target_ids=(
                        target_id
                        for _gate_id, target_id, _outcome in plans
                    ),
                )
            )
        pre = _canonical_json(self._state.snapshot())
        lifecycle = self._engine._reconcile_concentration_duration(
            state=self._state,
            tracker=tracker,
            effect=self._program,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            event_id=event.event_id,
            choices=self._choices,
        )
        self._concentration_records.append(lifecycle)
        self._current_required_operations.discard(
            "concentration_duration_reconciliation"
        )
        issued = self._issue(
            record_kind="concentration_duration_reconciliation",
            payload=lifecycle,
            pre_operation_state_json=pre,
        )
        if tracker.active_effect_id is None:
            self._area_effect_ended = True
            self._close_area_routes_for_effect_end(
                event=event,
                reason="effect_ended",
            )
        return issued

    def _validate_normalization_record_basis(
        self,
        record: _IssuedControlRecord,
    ) -> None:
        """Prove a normalization was issued from its target's event basis."""

        target_id = record.target_id
        if target_id is None:
            raise ControlEngineError(
                "Final normalization record must identify one target"
            )
        if (
            self._target_snapshot_slice_json(
                record.pre_operation_state_json,
                target_id,
            )
            != self._target_snapshot_slice_json(
                record.pre_event_state_json,
                target_id,
            )
            or self._target_route_snapshot_slice_json(
                record.pre_operation_route_state_json,
                target_id,
            )
            != self._target_route_snapshot_slice_json(
                record.pre_event_route_state_json,
                target_id,
            )
        ):
            raise ControlEngineError(
                "Final normalization record requires the unchanged pre-event "
                "target and route state"
            )

    def _validated_pending_concentration_failure_payload(
        self,
        record: _IssuedControlRecord,
    ) -> dict[str, Any]:
        """Replay one issued failed-check pending identity without live state."""

        payload = json.loads(record.payload_json)
        if set(payload) != {"kind", "pending_failure"} or payload.get(
            "kind"
        ) != "concentration_check_pending_end":
            raise ControlEngineError(
                "Final pending concentration-check payload is malformed"
            )
        pending = payload.get("pending_failure")
        expected_identity_keys = {
            "scenario_digest",
            "effect_id",
            "invocation_id",
            "source_actor_id",
            "damage_event_id",
            "damage_event_sequence",
            "end_event_id",
            "end_event_sequence",
            "check_operation_sequence",
            "check_record",
            "tracker_pre_state",
            "tracker_post_check_state",
            "tracker_end_record",
            "authority_metadata",
            "compiled_end_plan",
            "affected_target_ids",
        }
        if not isinstance(pending, Mapping) or set(pending) != (
            expected_identity_keys | {"pending_sha256"}
        ):
            raise ControlEngineError(
                "Final pending concentration failure identity is malformed"
            )
        identity = {
            key: pending[key] for key in expected_identity_keys
        }
        if (
            pending["pending_sha256"] != _sha256_record(identity)
            or pending["scenario_digest"] != self._scenario_digest
            or pending["effect_id"] != self._program.effect_id
            or pending["invocation_id"] != self._invocation_id
            or pending["source_actor_id"] != self._source_actor_id
            or pending["damage_event_id"] != record.event_id
            or pending["damage_event_sequence"] != record.event_sequence
            or pending["check_operation_sequence"] != record.operation_sequence
        ):
            raise ControlEngineError(
                "Final pending concentration failure provenance is stale"
            )
        try:
            damage_event = self._schedule.event(
                str(pending["damage_event_id"])
            )
            end_event = self._schedule.event(str(pending["end_event_id"]))
        except TimelineError as error:
            raise ControlEngineError(
                "Final failed check references an unknown bound event"
            ) from error
        if (
            damage_event.kind != "damage_context"
            or end_event.kind != "concentration_end"
            or end_event.sequence != damage_event.sequence + 1
            or pending["end_event_sequence"] != end_event.sequence
        ):
            raise ControlEngineError(
                "Final failed check does not bind the immediate typed end event"
            )
        affected_target_ids = pending["affected_target_ids"]
        if (
            not isinstance(affected_target_ids, list)
            or any(
                not isinstance(target_id, str) or not target_id
                for target_id in affected_target_ids
            )
            or affected_target_ids != sorted(set(affected_target_ids))
            or set(affected_target_ids) - set(self._schedule.target_ids)
        ):
            raise ControlEngineError(
                "Final pending failure affected targets are malformed"
            )
        plan = pending["compiled_end_plan"]
        if not isinstance(plan, list) or any(
            not isinstance(row, Mapping)
            or set(row) != {"gate_id", "target_id", "outcome"}
            or not all(
                isinstance(row.get(key), str) and row.get(key)
                for key in ("gate_id", "target_id", "outcome")
            )
            for row in plan
        ):
            raise ControlEngineError(
                "Final pending concentration failure end plan is malformed"
            )
        plan_identities = [
            (row["gate_id"], row["target_id"], row["outcome"])
            for row in plan
        ]
        if len(plan_identities) != len(set(plan_identities)):
            raise ControlEngineError(
                "Final pending concentration failure end plan is duplicated"
            )
        tracker_pre = pending["tracker_pre_state"]
        tracker_post = pending["tracker_post_check_state"]
        tracker_keys = {
            "active_effect_id",
            "active_metadata",
            "owner_actor_id",
            "save_bonus",
            "records",
        }
        if (
            not isinstance(tracker_pre, Mapping)
            or not isinstance(tracker_post, Mapping)
            or set(tracker_pre) != tracker_keys
            or set(tracker_post) != tracker_keys
            or not isinstance(tracker_pre["active_metadata"], Mapping)
            or not isinstance(tracker_post["active_metadata"], Mapping)
            or not isinstance(tracker_pre["save_bonus"], int)
            or isinstance(tracker_pre["save_bonus"], bool)
            or not isinstance(tracker_pre["records"], list)
            or not isinstance(tracker_post["records"], list)
            or any(
                not isinstance(item, Mapping)
                or item.get("owner_actor_id") != self._source_actor_id
                for item in (
                    *tracker_pre["records"],
                    *tracker_post["records"],
                )
            )
            or tracker_pre["active_effect_id"] != self._program.effect_id
            or tracker_post["active_effect_id"] != self._program.effect_id
            or tracker_pre["owner_actor_id"] != self._source_actor_id
            or tracker_post["owner_actor_id"] != self._source_actor_id
            or tracker_pre["active_metadata"] != tracker_post["active_metadata"]
            or tracker_pre["save_bonus"] != tracker_post["save_bonus"]
            or tracker_post["records"]
            != [*tracker_pre["records"], pending["check_record"]]
        ):
            raise ControlEngineError(
                "Final failed-check tracker pre/post chain is discontinuous"
            )
        check_record = pending["check_record"]
        if not isinstance(check_record, Mapping):
            raise ControlEngineError(
                "Final failed concentration check record is malformed"
            )
        try:
            preview = ConcentrationTracker(
                owner_actor_id=tracker_pre["owner_actor_id"],
                save_bonus=tracker_pre["save_bonus"]
            )
        except TimelineError as error:
            raise ControlEngineError(
                "Final failed-check tracker pre-state is malformed"
            ) from error
        preview.active_effect_id = tracker_pre["active_effect_id"]
        preview._active_metadata = deepcopy(tracker_pre["active_metadata"])
        preview.records = deepcopy(tracker_pre["records"])
        kernel = check_record.get("kernel")
        preview_kwargs: dict[str, Any] = {}
        if isinstance(kernel, Mapping) and kernel.get("kind") == "branch_probability":
            probability = kernel.get("success_probability", {})
            try:
                preview_kwargs["success_probability"] = Fraction(
                    probability["numerator"],
                    probability["denominator"],
                )
            except Exception as error:
                raise ControlEngineError(
                    "Final failed-check branch probability is malformed"
                ) from error
        elif isinstance(kernel, Mapping) and kernel.get("kind") == "exact_roll_kernel":
            try:
                preview_kwargs["roll_kernel"] = [
                    {
                        "roll": row["roll"],
                        "probability": Fraction(
                            row["probability"]["numerator"],
                            row["probability"]["denominator"],
                        ),
                    }
                    for row in kernel["rows"]
                ]
            except Exception as error:
                raise ControlEngineError(
                    "Final failed-check exact kernel is malformed"
                ) from error
        else:
            raise ControlEngineError(
                "Final failed concentration check kernel is malformed"
            )
        first_record_index = len(preview.records)
        try:
            previewed_check = preview.check(
                amount=check_record.get("amount"),
                source=check_record.get("source"),
                event_id=str(pending["damage_event_id"]),
                outcome="failure",
                **preview_kwargs,
            )
        except (TimelineError, TypeError, ValueError) as error:
            raise ControlEngineError(
                f"Final failed concentration check does not replay: {error}"
            ) from error
        generated = preview.records[first_record_index:]
        previewed_end = dict(_json_safe(generated[1]))
        previewed_end["event_id"] = end_event.event_id
        if (
            previewed_check != check_record
            or check_record.get("outcome") != "failure"
            or previewed_end != pending["tracker_end_record"]
        ):
            raise ControlEngineError(
                "Final failed concentration check or end template does not replay"
            )
        context = self._engine._build_concentration_context(
            effect=self._program,
            schedule=self._schedule,
            selector_membership=self._membership,
            selector_context=self._selector_context,
            invocation_id=self._invocation_id,
            source_actor_id=self._source_actor_id,
            start_event_id=str(self._concentration_start_event_id),
            choices=self._choices,
        )
        if pending["authority_metadata"] != (
            self._engine._concentration_authority_metadata(context)
        ):
            raise ControlEngineError(
                "Final pending concentration authority is stale"
            )
        self._require_failed_tracker_end_matches_context(
            pending["tracker_end_record"],
            context=context,
            end_event_id=end_event.event_id,
        )
        return dict(pending)

    def _validate_issued_records(
        self,
        records: Sequence[_IssuedControlRecord],
    ) -> None:
        if (
            len(records) != len(self._issued_records)
            or len(self._issued_record_originals) != len(self._issued_records)
        ):
            raise ControlEngineError(
                "Final result must consume the complete session-issued record stream"
            )
        known_events = {event.event_id: event for event in self._schedule.events}
        closed_snapshots = {
            snapshot.event_id: snapshot for snapshot in self._event_snapshots
        }
        prior_post_by_event: dict[str, str] = {}
        prior_route_post_by_event: dict[str, str] = {}
        prior_operation = 0
        prior_event_sequence = -1

        def validate_prone_descriptor(value: Any, label: str) -> dict[str, Any]:
            if not isinstance(value, Mapping):
                raise ControlEngineError(f"{label} must be an object")
            kind = value.get("kind")
            if kind not in {"remain_prone", "stand", "drop_prone", "crawl"}:
                raise ControlEngineError(f"{label}.kind is unsupported")
            expected = {"kind", "actor_id", "target_id"}
            if kind == "crawl":
                expected.add("distance_feet")
            if set(value) != expected:
                raise ControlEngineError(f"{label} shape is invalid")
            if (
                value.get("actor_id") != value.get("target_id")
                or not isinstance(value.get("target_id"), str)
                or not value["target_id"]
                or (
                    kind == "crawl"
                    and (
                        isinstance(value.get("distance_feet"), bool)
                        or not isinstance(value.get("distance_feet"), int)
                        or value["distance_feet"] < 1
                    )
                )
            ):
                raise ControlEngineError(f"{label} identity is invalid")
            return dict(value)

        prone_response_fields = {
            "operation",
            "target_id",
            "actor_id",
            "kind",
            "was_prone",
            "stood",
            "dropped_prone",
            "crawled",
            "distance_feet",
            "action_cost",
            "standing_cost_ft",
            "crawl_extra_cost_ft",
            "movement_cost_ft",
            "movement_budget_before_ft",
            "remaining_movement_ft",
            "prone_after",
            "reason",
        }
        prone_record_fields = prone_response_fields | {
            "event_id",
            "event_sequence",
            "proposal_operation_sequence",
            "proposal_record_sha256",
            "movement_mode",
            "movement_authority",
            "area_response_operation",
            "ended_component_ids",
            "ended_condition_instance_ids",
            "active_conditions_after",
            "created_condition_instances",
            "fall_transition",
            "active_components_after",
        }

        for index, record in enumerate(records):
            if not isinstance(record, _IssuedControlRecord):
                raise ControlEngineError("Final records must be typed session records")
            if (
                record is not self._issued_records[index]
                or record is not self._issued_record_originals[index]
            ):
                raise ControlEngineError(
                    "Final records contain a foreign, stale, or fabricated record"
                )
            if record._issuer is not self._issuer:
                raise ControlEngineError("Final record belongs to another execution")
            if record.scenario_digest != self._scenario_digest:
                raise ControlEngineError("Final record scenario digest is stale")
            event = known_events.get(record.event_id)
            if event is None or event.sequence != record.event_sequence:
                raise ControlEngineError("Final record references an unknown event")
            if event.sequence < prior_event_sequence:
                raise ControlEngineError(
                    "Final record stream moved backward through the schedule"
                )
            prior_event_sequence = event.sequence
            if (
                record.operation_sequence != index + 1
                or record.operation_sequence <= prior_operation
            ):
                raise ControlEngineError(
                    "Final record order is not the exact executed chronological order"
                )
            prior_operation = record.operation_sequence
            canonical_payload = _canonical_json(json.loads(record.payload_json))
            if canonical_payload != record.payload_json or hashlib.sha256(
                record.payload_json.encode("utf-8")
            ).hexdigest() != record.payload_sha256:
                raise ControlEngineError("Final record payload is stale or malformed")
            if record.record_kind not in _SESSION_RECORD_KINDS:
                raise ControlEngineError("Final record kind is fabricated")
            for snapshot_json in (
                record.pre_event_state_json,
                record.pre_operation_state_json,
                record.post_operation_state_json,
            ):
                if _canonical_json(json.loads(snapshot_json)) != snapshot_json:
                    raise ControlEngineError(
                        "Final record state snapshot is stale or malformed"
                    )
            for route_snapshot_json in (
                record.pre_event_route_state_json,
                record.pre_operation_route_state_json,
                record.post_operation_route_state_json,
            ):
                if _canonical_json(json.loads(route_snapshot_json)) != route_snapshot_json:
                    raise ControlEngineError(
                        "Final record route snapshot is stale or malformed"
                    )
            record_identity = {
                "scenario_digest": record.scenario_digest,
                "event_id": record.event_id,
                "event_sequence": record.event_sequence,
                "operation_sequence": record.operation_sequence,
                "target_id": record.target_id,
                "record_kind": record.record_kind,
                "pre_event_state": json.loads(record.pre_event_state_json),
                "pre_operation_state": json.loads(record.pre_operation_state_json),
                "post_operation_state": json.loads(record.post_operation_state_json),
                "pre_event_route_state": json.loads(
                    record.pre_event_route_state_json
                ),
                "pre_operation_route_state": json.loads(
                    record.pre_operation_route_state_json
                ),
                "post_operation_route_state": json.loads(
                    record.post_operation_route_state_json
                ),
                "payload": json.loads(record.payload_json),
            }
            if _sha256_record(record_identity) != record.record_sha256:
                raise ControlEngineError(
                    "Final record envelope is stale or malformed"
                )
            if record.target_id is not None and record.target_id not in self._known_actor_ids:
                raise ControlEngineError("Final record references an unknown actor")
            snapshot = closed_snapshots.get(record.event_id)
            if (
                snapshot is None
                or record.pre_event_state_json != snapshot.pre_event_state_json
                or record.pre_event_route_state_json
                != snapshot.pre_event_route_state_json
            ):
                raise ControlEngineError(
                    "Final record pre-event state does not match its closed event"
                )
            expected_pre_operation = prior_post_by_event.get(
                record.event_id,
                snapshot.pre_event_state_json,
            )
            if record.pre_operation_state_json != expected_pre_operation:
                raise ControlEngineError(
                    "Same-event operation state chain is stale or out of order"
                )
            prior_post_by_event[record.event_id] = record.post_operation_state_json
            expected_pre_route = prior_route_post_by_event.get(
                record.event_id,
                snapshot.pre_event_route_state_json,
            )
            if record.pre_operation_route_state_json != expected_pre_route:
                raise ControlEngineError(
                    "Same-event route-state chain is stale or out of order"
                )
            prior_route_post_by_event[record.event_id] = (
                record.post_operation_route_state_json
            )

            payload = json.loads(record.payload_json)
            if (
                "target_id" in payload
                and payload["target_id"] != record.target_id
            ):
                raise ControlEngineError(
                    "Final record envelope target does not match its payload"
                )
            if (
                "event_id" in payload
                and payload["event_id"] != record.event_id
            ):
                raise ControlEngineError(
                    "Final record envelope event does not match its payload"
                )
            if record.record_kind == "branch_transition":
                if payload.get("operation") != "branch_transition":
                    raise ControlEngineError(
                        "Final branch record kind does not match its payload"
                    )
                gate_id = payload.get("gate_id")
                branch_id = payload.get("branch_id")
                try:
                    gate = self._program.gate(str(gate_id))
                except Exception as error:
                    raise ControlEngineError(
                        "Final branch record references an unknown gate"
                    ) from error
                if branch_id not in {branch.branch_id for branch in gate.branches}:
                    raise ControlEngineError(
                        "Final branch record has a fabricated branch-to-gate relationship"
                    )
                if gate.requires_active_component_ids:
                    active_ids = {
                        row["component_id"]
                        for row in json.loads(record.pre_event_state_json)
                        if row.get("target_id") == record.target_id
                        and row.get("effect_id") == self._program.effect_id
                    }
                    missing = sorted(
                        set(gate.requires_active_component_ids) - active_ids
                    )
                    if missing:
                        raise ControlEngineError(
                            "Final branch source component was absent from the "
                            f"pre-event state: {missing}"
                        )
            if record.record_kind == "normalization":
                self._validate_normalization_record_basis(record)
                allowed_windows = {
                    value
                    for value in (
                        record.event_id,
                        known_events[record.event_id].window_id,
                        known_events[record.event_id].reaction_interval_id,
                    )
                    if value is not None
                }
                pre_sources = {
                    (
                        f"condition_instance:{row['condition_instance_id']}"
                        if row.get("condition_instance_id") is not None
                        else f"{row['effect_id']}:{row['component_id']}"
                    )
                    for row in json.loads(record.pre_event_state_json)
                    if row.get("target_id") == record.target_id
                }
                for contribution in payload.get("contributions", ()):
                    if contribution.get("event_or_window_id") not in allowed_windows:
                        raise ControlEngineError(
                            "Primitive contribution references a fictional window ID"
                        )
                    for source_id in contribution.get("source_component_ids", ()):
                        if (
                            source_id not in pre_sources
                            and not source_id.startswith(
                                f"target_sense:{record.target_id}:"
                            )
                        ):
                            raise ControlEngineError(
                                "Primitive contribution source was not active in the pre-state"
                            )
            if record.record_kind == "prone_operation_proposal":
                proposal_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "target_id",
                    "actor_id",
                    "prone_before",
                    "movement_mode",
                    "current_speed_ft",
                    "movement_budget_ft",
                    "difficult_terrain",
                    "usable_route",
                    "movement_authority",
                    "operations",
                    "drop_prone_fall_context",
                }
                if set(payload) != proposal_fields:
                    raise ControlEngineError(
                        "Final Prone proposal has an invalid closed shape"
                    )
                authority = payload["movement_authority"]
                authority_fields = {
                    "source",
                    "base_speeds_ft",
                    "effective_speeds_ft",
                    "speed_zero_modes",
                    "denied_modes",
                    "mixed_speed_operation_order",
                    "source_component_ids",
                }
                if (
                    payload["kind"] != "prone_operation_proposal"
                    or event.kind != "target_movement_opportunity"
                    or event.target_id != record.target_id
                    or event.actor_id != record.target_id
                    or event.turn_owner != "target"
                    or payload["event_sequence"] != event.sequence
                    or payload["target_id"] != record.target_id
                    or payload["actor_id"] != record.target_id
                    or not isinstance(payload["prone_before"], bool)
                    or payload["movement_mode"] not in MOVEMENT_MODES
                    or isinstance(payload["current_speed_ft"], bool)
                    or not isinstance(payload["current_speed_ft"], int)
                    or payload["current_speed_ft"] < 0
                    or isinstance(payload["movement_budget_ft"], bool)
                    or not isinstance(payload["movement_budget_ft"], int)
                    or payload["movement_budget_ft"] < 0
                    or not isinstance(payload["difficult_terrain"], bool)
                    or not isinstance(payload["usable_route"], bool)
                    or not isinstance(authority, Mapping)
                    or set(authority) != authority_fields
                    or authority.get("source") != "active_control_state"
                    or payload["movement_mode"]
                    not in authority.get("effective_speeds_ft", {})
                    or "walk" not in authority.get("effective_speeds_ft", {})
                    or authority["effective_speeds_ft"]["walk"]
                    != payload["current_speed_ft"]
                    or record.pre_operation_state_json
                    != record.post_operation_state_json
                    or record.pre_operation_route_state_json
                    != record.post_operation_route_state_json
                ):
                    raise ControlEngineError(
                        "Final Prone proposal identity or authority is invalid"
                    )
                prone_in_pre_state = any(
                    row.get("target_id") == record.target_id
                    and row.get("magnitude", {}).get("kind") == "condition"
                    and row.get("magnitude", {}).get("condition") == "prone"
                    for row in json.loads(record.pre_operation_state_json)
                )
                if prone_in_pre_state != payload["prone_before"]:
                    raise ControlEngineError(
                        "Final Prone proposal does not match its pre-state"
                    )
                operations = payload["operations"]
                if not isinstance(operations, list):
                    raise ControlEngineError(
                        "Final Prone proposal operations must be an array"
                    )
                validated_operations = [
                    validate_prone_descriptor(
                        operation,
                        f"Prone proposal operation {operation_index}",
                    )
                    for operation_index, operation in enumerate(operations)
                ]
                if len(validated_operations) != len({
                    _canonical_json(operation)
                    for operation in validated_operations
                }):
                    raise ControlEngineError(
                        "Final Prone proposal operations are duplicated"
                    )
                try:
                    complete_operations = enumerate_prone_movement_operations(
                        target_id=str(record.target_id),
                        actor_id=str(record.target_id),
                        prone=payload["prone_before"],
                        current_speed_ft=payload["current_speed_ft"],
                        movement_budget_ft=payload["movement_budget_ft"],
                        difficult_terrain=payload["difficult_terrain"],
                        movement_denied=(
                            payload["movement_mode"]
                            in set(authority["denied_modes"])
                        ),
                        actor_owns_opportunity=True,
                        usable_route=payload["usable_route"],
                    )
                except TimelineError as error:
                    raise ControlEngineError(
                        f"Final Prone proposal does not replay: {error}"
                    ) from error
                permitted_operation_sets = [complete_operations]
                permitted_operation_sets.append([
                    operation for operation in complete_operations
                    if operation["kind"] != "crawl"
                ])
                if (
                    record.target_id is not None
                    and "prone" in self._targets_by_id[
                        record.target_id
                    ].condition_immunities
                    and not payload["prone_before"]
                ):
                    permitted_operation_sets.extend([
                        [
                            operation for operation in candidate
                            if operation["kind"] != "drop_prone"
                        ]
                        for candidate in tuple(permitted_operation_sets)
                    ])
                if validated_operations not in permitted_operation_sets:
                    raise ControlEngineError(
                        "Final Prone proposal contains fabricated or reordered operations"
                    )
                offers_drop = any(
                    operation["kind"] == "drop_prone"
                    for operation in validated_operations
                )
                if offers_drop != isinstance(
                    payload["drop_prone_fall_context"],
                    Mapping,
                ):
                    raise ControlEngineError(
                        "Final voluntary-drop proposal lacks exact fall context"
                    )
            if record.record_kind == "prone_operation":
                if set(payload) != prone_record_fields:
                    raise ControlEngineError(
                        "Final Prone operation has an invalid closed shape"
                    )
                operation = validate_prone_descriptor(
                    payload.get("operation"),
                    "Final Prone operation",
                )
                proposal_sequence = payload.get("proposal_operation_sequence")
                if (
                    isinstance(proposal_sequence, bool)
                    or not isinstance(proposal_sequence, int)
                    or proposal_sequence < 1
                    or proposal_sequence >= record.operation_sequence
                    or proposal_sequence > len(records)
                ):
                    raise ControlEngineError(
                        "Final Prone operation proposal sequence is invalid"
                    )
                proposal_record = records[proposal_sequence - 1]
                proposal_payload = json.loads(proposal_record.payload_json)
                if (
                    payload["kind"] != "prone_operation"
                    or payload["event_id"] != record.event_id
                    or payload["event_sequence"] != record.event_sequence
                    or payload["target_id"] != record.target_id
                    or payload["actor_id"] != record.target_id
                    or proposal_record.record_kind
                    != "prone_operation_proposal"
                    or proposal_record.record_sha256
                    != payload["proposal_record_sha256"]
                    or proposal_record.event_id != record.event_id
                    or proposal_record.target_id != record.target_id
                    or operation not in proposal_payload.get("operations", ())
                    or payload["movement_mode"]
                    != proposal_payload.get("movement_mode")
                    or payload["movement_authority"]
                    != proposal_payload.get("movement_authority")
                    or payload["movement_budget_before_ft"]
                    != proposal_payload.get("movement_budget_ft")
                    or not isinstance(payload["area_response_operation"], bool)
                ):
                    raise ControlEngineError(
                        "Final Prone operation is foreign, stale, or rewritten"
                    )
                operation_kind = operation["kind"]
                if (
                    operation_kind == "crawl"
                    and not payload["area_response_operation"]
                    and payload["crawl_extra_cost_ft"]
                    != payload["distance_feet"] * (
                        2
                        if proposal_payload.get("difficult_terrain") is True
                        else 1
                    )
                ):
                    raise ControlEngineError(
                        "Final standalone crawl cost does not replay its terrain"
                    )
                target_pre_rows = [
                    row
                    for row in json.loads(record.pre_operation_state_json)
                    if row.get("target_id") == record.target_id
                ]
                target_post_rows = [
                    row
                    for row in json.loads(record.post_operation_state_json)
                    if row.get("target_id") == record.target_id
                ]
                if payload["active_components_after"] != target_post_rows:
                    raise ControlEngineError(
                        "Final Prone operation active snapshot is stale"
                    )
                pre_prone_ids = {
                    row.get("condition_instance_id")
                    for row in target_pre_rows
                    if row.get("magnitude", {}).get("kind") == "condition"
                    and row.get("magnitude", {}).get("condition") == "prone"
                    and row.get("condition_instance_id") is not None
                }
                post_prone_ids = {
                    row.get("condition_instance_id")
                    for row in target_post_rows
                    if row.get("magnitude", {}).get("kind") == "condition"
                    and row.get("magnitude", {}).get("condition") == "prone"
                    and row.get("condition_instance_id") is not None
                }
                if payload["area_response_operation"]:
                    prior_area_records = [
                        candidate
                        for candidate in records[: record.operation_sequence - 1]
                        if candidate.record_kind == "area_response"
                        and candidate.event_id == record.event_id
                        and candidate.target_id == record.target_id
                    ]
                    if (
                        len(prior_area_records) != 1
                        or record.pre_operation_state_json
                        != record.post_operation_state_json
                        or record.pre_operation_route_state_json
                        != record.post_operation_route_state_json
                    ):
                        raise ControlEngineError(
                            "Final area-bound Prone operation lacks one exact area result"
                        )
                    area_payload = json.loads(
                        prior_area_records[0].payload_json
                    )
                    area_record = prior_area_records[0]
                    target_pre_rows = [
                        row
                        for row in json.loads(
                            area_record.pre_operation_state_json
                        )
                        if row.get("target_id") == record.target_id
                    ]
                    target_post_rows = [
                        row
                        for row in json.loads(
                            area_record.post_operation_state_json
                        )
                        if row.get("target_id") == record.target_id
                    ]
                    pre_prone_ids = {
                        row.get("condition_instance_id")
                        for row in target_pre_rows
                        if row.get("magnitude", {}).get("kind") == "condition"
                        and row.get("magnitude", {}).get("condition") == "prone"
                        and row.get("condition_instance_id") is not None
                    }
                    post_prone_ids = {
                        row.get("condition_instance_id")
                        for row in target_post_rows
                        if row.get("magnitude", {}).get("kind") == "condition"
                        and row.get("magnitude", {}).get("condition") == "prone"
                        and row.get("condition_instance_id") is not None
                    }
                    area_prone_response = (
                        (area_payload.get("selected_route") or {}).get(
                            "prone_response"
                        )
                        or area_payload.get("prone_response")
                    )
                    response_projection = {
                        key: payload[key]
                        for key in prone_response_fields
                    }
                    response_projection["kind"] = operation_kind
                    if area_prone_response != response_projection:
                        raise ControlEngineError(
                            "Final area-bound Prone operation disagrees with its area result"
                        )
                elif operation_kind == "stand":
                    if not pre_prone_ids or post_prone_ids:
                        raise ControlEngineError(
                            "Final stand operation does not end exact Prone state"
                        )
                elif operation_kind in {"remain_prone", "crawl"}:
                    if not pre_prone_ids or post_prone_ids != pre_prone_ids:
                        raise ControlEngineError(
                            "Final Prone-retaining operation rewrites condition state"
                        )
                elif operation_kind == "drop_prone":
                    if pre_prone_ids or not post_prone_ids:
                        raise ControlEngineError(
                            "Final voluntary drop does not create exact Prone state"
                        )
                ended_ids = payload["ended_condition_instance_ids"]
                created_rows = payload["created_condition_instances"]
                created_rows_valid = bool(
                    isinstance(created_rows, list)
                    and all(
                        isinstance(row, Mapping)
                        and isinstance(row.get("instance_id"), str)
                        and bool(row["instance_id"])
                        for row in created_rows
                    )
                )
                created_ids = (
                    [row["instance_id"] for row in created_rows]
                    if created_rows_valid
                    else []
                )
                post_component_instance_ids = {
                    row.get("instance_id") for row in target_post_rows
                }
                expected_ended_component_ids = sorted({
                    str(row["component_id"])
                    for row in target_pre_rows
                    if row.get("magnitude", {}).get("kind") == "condition"
                    and row.get("magnitude", {}).get("condition") == "prone"
                    and row.get("instance_id") not in post_component_instance_ids
                })
                if (
                    ended_ids != sorted(pre_prone_ids - post_prone_ids)
                    or payload["ended_component_ids"]
                    != expected_ended_component_ids
                    or not created_rows_valid
                    or len(created_ids) != len(set(created_ids))
                    or sorted(created_ids)
                    != sorted(post_prone_ids - pre_prone_ids)
                    or (
                        operation_kind == "drop_prone"
                        and not isinstance(payload["fall_transition"], Mapping)
                    )
                    or (
                        operation_kind != "drop_prone"
                        and payload["fall_transition"] is not None
                    )
                ):
                    raise ControlEngineError(
                        "Final Prone operation condition-instance delta is invalid"
                    )
            if record.record_kind == "concentration_check_pending_end":
                self._validated_pending_concentration_failure_payload(record)
                if (
                    record.pre_operation_state_json
                    != record.post_operation_state_json
                    or record.pre_operation_route_state_json
                    != record.post_operation_route_state_json
                ):
                    raise ControlEngineError(
                        "A failed concentration check must not mutate component "
                        "or route state at its damage event"
                    )
            route_transition = payload.get("route_transition")
            if route_transition is not None:
                if not isinstance(route_transition, Mapping):
                    raise ControlEngineError("Route transition payload is malformed")
                if (
                    route_transition.get("event_id") != record.event_id
                    or route_transition.get("event_sequence")
                    != record.event_sequence
                    or route_transition.get("target_id") != record.target_id
                    or route_transition.get("effect_id") != self._program.effect_id
                    or route_transition.get("pre_route_state_sha256")
                    != hashlib.sha256(
                        record.pre_operation_route_state_json.encode("utf-8")
                    ).hexdigest()
                    or route_transition.get("post_route_state_sha256")
                    != hashlib.sha256(
                        record.post_operation_route_state_json.encode("utf-8")
                    ).hexdigest()
                ):
                    raise ControlEngineError(
                        "Route transition is foreign, stale, rewritten, or discontinuous"
                    )
                transition_identity = (
                    route_transition.get("effect_id"),
                    route_transition.get("area_id"),
                    route_transition.get("target_id"),
                )
                pre_route_rows = [
                    row
                    for row in json.loads(record.pre_operation_route_state_json)
                    if (
                        row.get("effect_id"),
                        row.get("area_id"),
                        row.get("target_id"),
                    ) == transition_identity
                ]
                post_route_rows = [
                    row
                    for row in json.loads(record.post_operation_route_state_json)
                    if (
                        row.get("effect_id"),
                        row.get("area_id"),
                        row.get("target_id"),
                    ) == transition_identity
                ]
                if (
                    route_transition.get("transition_kind")
                    not in {
                        "movement_blocked",
                        "movement_progress",
                        "route_exit",
                        "area_entry",
                        "explicit_geometry_update",
                        "effect_end",
                    }
                    or len(pre_route_rows) != 1
                    or len(post_route_rows) != 1
                    or route_transition.get("old_route_state")
                    != pre_route_rows[0]
                    or route_transition.get("new_route_state")
                    != post_route_rows[0]
                ):
                    raise ControlEngineError(
                        "Route transition old/new states do not match its "
                        "chronological route snapshots"
                    )
            if record.record_sha256 != self._issued_record_attestations[index]:
                raise ControlEngineError(
                    "Final record differs from its engine-owned issuance attestation"
                )
        for event_id, post_state_json in prior_post_by_event.items():
            if post_state_json != closed_snapshots[event_id].post_event_state_json:
                raise ControlEngineError(
                    "Final operation post-state does not match its closed event"
                )
        for event_id, post_route_state_json in prior_route_post_by_event.items():
            if (
                post_route_state_json
                != closed_snapshots[event_id].post_event_route_state_json
            ):
                raise ControlEngineError(
                    "Final operation post-route state does not match its closed event"
                )

    def _validate_condition_lifecycle(self) -> None:
        """Replay canonical condition identity, lineage, lifecycle, and issuance."""

        try:
            registry = tuple(self._state.instance_registry())
            lineage = tuple(self._state.lineage_records())
            lifecycle = tuple(self._state.condition_lifecycle_records())
        except ControlStateError as error:
            raise ControlEngineError(
                f"Final condition registry is invalid: {error}"
            ) from error
        registry_by_id = {row["instance_id"]: row for row in registry}
        if len(registry_by_id) != len(registry):
            raise ControlEngineError("Final condition registry duplicates an instance ID")
        for row in registry:
            identity = {
                key: row[key]
                for key in (
                    "condition_id",
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
                    "parent_condition_instance_id",
                    "inclusion_edge_id",
                    "issuance_id",
                    "provenance_id",
                )
            }
            if condition_instance_id_for(**identity) != row["instance_id"]:
                raise ControlEngineError(
                    "Final condition registry contains a rewritten identity"
                )
            if row["status"] == "active":
                if any(
                    row[name] is not None
                    for name in ("end_event_id", "end_sequence", "end_reason")
                ):
                    raise ControlEngineError(
                        "Active condition instance contains end metadata"
                    )
            elif row["status"] == "ended":
                if any(
                    row[name] is None
                    for name in ("end_event_id", "end_sequence", "end_reason")
                ):
                    raise ControlEngineError(
                        "Ended condition instance lacks exact end metadata"
                    )
            else:
                raise ControlEngineError(
                    f"Unsupported condition lifecycle status: {row['status']!r}"
                )

        application_counts: dict[str, int] = {}
        end_counts: dict[str, int] = {}
        for record in lifecycle:
            instance_id = record.get("condition_instance_id")
            if instance_id not in registry_by_id:
                raise ControlEngineError(
                    "Condition lifecycle references a foreign instance"
                )
            instance = registry_by_id[instance_id]
            common_lifecycle = {
                "target_id": instance["target_id"],
                "condition_instance_id": instance_id,
                "condition_id": instance["condition_id"],
                "parent_condition_instance_id": (
                    instance["parent_condition_instance_id"]
                ),
                "inclusion_edge_id": instance["inclusion_edge_id"],
                "source_actor_id": instance["source_actor_id"],
                "source_program_id": instance["source_program_id"],
                "source_effect_id": instance["source_effect_id"],
                "source_component_id": instance["source_component_id"],
                "issuance_id": instance["issuance_id"],
                "provenance_id": instance["provenance_id"],
            }
            if record.get("kind") == "condition_application":
                expected_record = {
                    "kind": "condition_application",
                    "event_id": instance["application_event_id"],
                    "sequence": instance["application_sequence"],
                    **common_lifecycle,
                }
                if record != expected_record:
                    raise ControlEngineError(
                        "condition application lifecycle source or identity "
                        "differs from its canonical instance"
                    )
                application_counts[instance_id] = (
                    application_counts.get(instance_id, 0) + 1
                )
            elif record.get("kind") == "condition_end":
                expected_record = {
                    "kind": "condition_end",
                    "event_id": instance["end_event_id"],
                    "sequence": instance["end_sequence"],
                    **common_lifecycle,
                    "reason": instance["end_reason"],
                }
                if record != expected_record:
                    raise ControlEngineError(
                        "condition end lifecycle source or identity differs "
                        "from its canonical instance"
                    )
                end_counts[instance_id] = end_counts.get(instance_id, 0) + 1
            else:
                raise ControlEngineError("Condition lifecycle kind is fabricated")
        for instance_id, row in registry_by_id.items():
            if application_counts.get(instance_id) != 1:
                raise ControlEngineError(
                    "Condition instance lacks one exact application lifecycle"
                )
            expected_end_count = 1 if row["status"] == "ended" else 0
            if end_counts.get(instance_id, 0) != expected_end_count:
                raise ControlEngineError(
                    "Condition instance end lifecycle is duplicated or missing"
                )

        lineage_ids = {
            (
                row["parent_condition_instance_id"],
                row["child_condition_instance_id"],
                row["inclusion_edge_id"],
            )
            for row in lineage
        }
        if len(lineage_ids) != len(lineage):
            raise ControlEngineError("Final inclusion lineage is duplicated")
        expected_lineage_ids = {
            (
                row["parent_condition_instance_id"],
                row["instance_id"],
                row["inclusion_edge_id"],
            )
            for row in registry
            if row["parent_condition_instance_id"] is not None
        }
        if lineage_ids != expected_lineage_ids:
            raise ControlEngineError("Final inclusion lineage is broken or incomplete")

        initial_ids = {
            row["instance_id"]
            for row in json.loads(self._initial_condition_registry_json)
        }
        issued_application_ids: set[str] = set()
        for record in self._issued_records:
            payload = json.loads(record.payload_json)
            if record.record_kind == "condition_application":
                issued_application_ids.update(
                    row["instance_id"]
                    for row in payload.get("created_condition_instances", ())
                )
            elif record.record_kind == "prone_operation":
                issued_application_ids.update(
                    row["instance_id"]
                    for row in payload.get("created_condition_instances", ())
                )
            elif record.record_kind == "branch_transition":
                issued_application_ids.update(
                    row["instance_id"]
                    for row in payload.get("created_condition_instances", ())
                )
            pre_ids = {
                row.get("condition_instance_id")
                for row in json.loads(record.pre_operation_state_json)
                if row.get("condition_instance_id") is not None
            }
            issued_application_ids.update(
                row["condition_instance_id"]
                for row in json.loads(record.post_operation_state_json)
                if row.get("condition_instance_id") is not None
                and row["condition_instance_id"] not in pre_ids
            )
        root_ids = {
            row["instance_id"]
            for row in registry
            if row["parent_condition_instance_id"] is None
        }
        issued_or_initial_roots = {
            instance_id
            for instance_id in initial_ids | issued_application_ids
            if instance_id in registry_by_id
            and registry_by_id[instance_id]["parent_condition_instance_id"] is None
        }
        if root_ids != issued_or_initial_roots:
            raise ControlEngineError(
                "Final condition roots are not covered by initial or issued provenance"
            )
        if self._pending_condition_proposals:
            raise ControlEngineError(
                "Final execution contains an unfinished condition proposal"
            )
        if self._pending_prone_proposals:
            raise ControlEngineError(
                "Final execution contains an unfinished Prone proposal"
            )

    def _validate_condition_execution_replay(self) -> None:
        """Re-derive live opportunity, legality, fall, and cleanup semantics."""

        registry = {
            row["instance_id"]: row for row in self._state.instance_registry()
        }
        events = {event.event_id: event for event in self._schedule.events}

        def sorted_unique_strings(value: Any, label: str) -> list[str]:
            if (
                not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or value != sorted(set(value))
            ):
                raise ControlEngineError(
                    f"Final {label} must be a sorted unique string array"
                )
            return list(value)

        def snapshot_condition_rows(
            snapshot_json: str,
            *,
            target_id: str,
            event_sequence: int,
        ) -> list[Mapping[str, Any]]:
            root_ids = {
                row["condition_instance_id"]
                for row in json.loads(snapshot_json)
                if row.get("target_id") == target_id
                and row.get("condition_instance_id") is not None
            }
            active: list[Mapping[str, Any]] = []
            for row in registry.values():
                if (
                    row["target_id"] != target_id
                    or row["application_sequence"] > event_sequence
                    or (
                        row["end_sequence"] is not None
                        and row["end_sequence"] <= event_sequence
                    )
                ):
                    continue
                root = row
                seen: set[str] = set()
                while root["parent_condition_instance_id"] is not None:
                    if root["instance_id"] in seen:
                        raise ControlEngineError(
                            "Final condition replay contains an inclusion cycle"
                        )
                    seen.add(root["instance_id"])
                    parent_id = root["parent_condition_instance_id"]
                    if parent_id not in registry:
                        raise ControlEngineError(
                            "Final condition replay contains broken lineage"
                        )
                    root = registry[parent_id]
                if root["instance_id"] in root_ids:
                    active.append(row)
            return sorted(active, key=lambda row: row["instance_id"])

        def expected_legality(
            value: Any,
            *,
            snapshot_json: str,
            event_sequence: int,
        ) -> dict[str, Any]:
            if not isinstance(value, Mapping):
                raise ControlEngineError(
                    "Final source-relative legality decision is malformed"
                )
            actor_id = value.get("actor_id")
            target_id = value.get("proposal_target_id")
            action_economy = value.get("action_economy")
            category = value.get("category")
            if (
                not isinstance(actor_id, str)
                or not actor_id
                or (
                    target_id is not None
                    and (not isinstance(target_id, str) or not target_id)
                )
                or action_economy
                not in {"action", "bonus_action", "reaction", "movement", "other"}
                or category
                not in {
                    "attack",
                    "damaging_ability",
                    "damaging_magical_effect",
                    "non_damaging_effect",
                    "other",
                }
            ):
                raise ControlEngineError(
                    "Final source-relative legality authority is malformed"
                )
            active = snapshot_condition_rows(
                snapshot_json,
                target_id=actor_id,
                event_sequence=event_sequence,
            )
            charmed = [row for row in active if row["condition_id"] == "charmed"]
            incapacitated = [
                row for row in active if row["condition_id"] == "incapacitated"
            ]
            denial_reasons: list[dict[str, Any]] = []
            if incapacitated and action_economy in {
                "action",
                "bonus_action",
                "reaction",
            }:
                denial_reasons.append({
                    "reason": "incapacitated_action_economy_denial",
                    "condition_instance_ids": sorted(
                        row["instance_id"] for row in incapacitated
                    ),
                    "denied_action_economy": action_economy,
                })
            prohibited = {
                "attack",
                "damaging_ability",
                "damaging_magical_effect",
            }
            matching_charmers = [
                row for row in charmed if row["source_actor_id"] == target_id
            ]
            if category in prohibited and charmed and target_id is None:
                denial_reasons.append({
                    "reason": "charmed_target_identity_unresolved",
                    "condition_instance_ids": sorted(
                        row["instance_id"] for row in charmed
                    ),
                    "charmer_actor_ids": sorted({
                        row["source_actor_id"] for row in charmed
                    }),
                    "prohibited_category": category,
                })
            elif category in prohibited and matching_charmers:
                denial_reasons.append({
                    "reason": "charmed_exact_source_target_restriction",
                    "condition_instance_ids": sorted(
                        row["instance_id"] for row in matching_charmers
                    ),
                    "charmer_actor_ids": sorted({
                        row["source_actor_id"] for row in matching_charmers
                    }),
                    "prohibited_category": category,
                })
            return {
                "kind": "source_relative_action_legality",
                "actor_id": actor_id,
                "proposal_target_id": target_id,
                "action_economy": action_economy,
                "category": category,
                "allowed": not denial_reasons,
                "denial_reasons": denial_reasons,
                "active_charmed_instance_ids": sorted(
                    row["instance_id"] for row in charmed
                ),
                "active_incapacitated_instance_ids": sorted(
                    row["instance_id"] for row in incapacitated
                ),
            }

        def validate_normalization(
            value: Any,
            *,
            label: str,
            target_id: str,
            record: _IssuedControlRecord,
        ) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
            if not isinstance(value, Mapping) or set(value) != {
                "contributions",
                "suppressions",
            }:
                raise ControlEngineError(f"Final {label} shape is malformed")
            contributions = value["contributions"]
            suppressions = value["suppressions"]
            if (
                not isinstance(contributions, list)
                or not all(isinstance(row, Mapping) for row in contributions)
                or not isinstance(suppressions, list)
                or not all(isinstance(row, Mapping) for row in suppressions)
            ):
                raise ControlEngineError(f"Final {label} rows are malformed")
            event = events[record.event_id]
            allowed_windows = {
                item
                for item in (
                    event.event_id,
                    event.window_id,
                    event.reaction_interval_id,
                )
                if item is not None
            }
            active_ids = {
                row["instance_id"]
                for row in snapshot_condition_rows(
                    record.pre_operation_state_json,
                    target_id=target_id,
                    event_sequence=record.event_sequence,
                )
            }

            def validate_source(source_id: Any) -> None:
                if not isinstance(source_id, str) or not source_id:
                    raise ControlEngineError(
                        f"Final {label} contains a malformed source ID"
                    )
                prefix = "condition_instance:"
                if source_id.startswith(prefix) and source_id[len(prefix):] not in active_ids:
                    raise ControlEngineError(
                        f"Final {label} references a condition source absent "
                        "from its live replay basis"
                    )

            for contribution in contributions:
                sources = contribution.get("source_component_ids")
                if (
                    contribution.get("target_id") != target_id
                    or contribution.get("event_or_window_id") not in allowed_windows
                    or not isinstance(sources, list)
                ):
                    raise ControlEngineError(
                        f"Final {label} contribution has fabricated identity"
                    )
                for source_id in sources:
                    validate_source(source_id)
            for suppression in suppressions:
                if (
                    suppression.get("target_id") != target_id
                    or suppression.get("event_or_window_id") not in allowed_windows
                ):
                    raise ControlEngineError(
                        f"Final {label} suppression has fabricated identity"
                    )
                for source_key in (
                    "dominant_source_component_ids",
                    "suppressed_source_component_ids",
                ):
                    sources = suppression.get(source_key)
                    if not isinstance(sources, list):
                        raise ControlEngineError(
                            f"Final {label} suppression sources are malformed"
                        )
                    for source_id in sources:
                        validate_source(source_id)
            return list(contributions), list(suppressions)

        def lineage_for_root(root_id: str) -> list[Mapping[str, Any]]:
            if root_id not in registry:
                raise ControlEngineError(
                    "Final condition operation references a foreign root instance"
                )
            children: dict[str, list[Mapping[str, Any]]] = {}
            for row in registry.values():
                parent_id = row["parent_condition_instance_id"]
                if parent_id is not None:
                    children.setdefault(parent_id, []).append(row)
            for rows in children.values():
                rows.sort(key=lambda row: (
                    str(row["inclusion_edge_id"]),
                    row["instance_id"],
                ))
            selected: list[Mapping[str, Any]] = []
            visiting: set[str] = set()

            def visit(instance_id: str) -> None:
                if instance_id in visiting or instance_id not in registry:
                    raise ControlEngineError(
                        "Final condition operation contains broken lineage"
                    )
                visiting.add(instance_id)
                selected.append(registry[instance_id])
                for child in children.get(instance_id, ()):
                    visit(child["instance_id"])
                visiting.remove(instance_id)

            visit(root_id)
            return selected

        def application_projection(row: Mapping[str, Any]) -> dict[str, Any]:
            return {
                **dict(row),
                "status": "active",
                "end_event_id": None,
                "end_sequence": None,
                "end_reason": None,
            }

        records_by_sequence = {
            record.operation_sequence: record for record in self._issued_records
        }

        for record in self._issued_records:
            payload = json.loads(record.payload_json)
            if record.record_kind == "condition_application_proposal":
                if set(payload) != {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "target_id",
                    "condition_instance",
                    "fall_context",
                } or not isinstance(payload.get("condition_instance"), Mapping):
                    raise ControlEngineError(
                        "Final condition application proposal shape is malformed"
                    )
                instance = dict(payload["condition_instance"])
                instance_id = instance.pop("instance_id", None)
                try:
                    computed_id = condition_instance_id_for(**instance)
                except (ControlStateError, TypeError, ValueError) as error:
                    raise ControlEngineError(
                        "Final condition application proposal identity is malformed"
                    ) from error
                expected_issuance = (
                    f"{self._scenario_digest}:{record.event_id}:"
                    f"condition_proposal:{record.operation_sequence}"
                )
                if (
                    payload.get("kind") != "condition_application_proposal"
                    or events[record.event_id].kind != "condition_application"
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("target_id") != record.target_id
                    or instance.get("target_id") != record.target_id
                    or instance.get("application_event_id") != record.event_id
                    or instance.get("application_sequence") != record.event_sequence
                    or instance.get("issuance_id") != expected_issuance
                    or instance_id != computed_id
                    or record.pre_operation_state_json
                    != record.post_operation_state_json
                    or record.pre_operation_route_state_json
                    != record.post_operation_route_state_json
                ):
                    raise ControlEngineError(
                        "Final condition application proposal is foreign, stale, "
                        "or rewritten"
                    )
                try:
                    self._validated_fall_context(
                        payload.get("fall_context"),
                        required=False,
                    )
                except ControlEngineError as error:
                    raise ControlEngineError(
                        "Final condition application proposal fall context is malformed"
                    ) from error

            elif record.record_kind == "condition_application":
                expected_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "target_id",
                    "proposal_operation_sequence",
                    "proposal_record_sha256",
                    "root_condition_instance_id",
                    "created_condition_instances",
                    "condition_concentration_end",
                    "fall_transition",
                    "active_conditions_after",
                }
                proposal_sequence = payload.get("proposal_operation_sequence")
                proposal_record = records_by_sequence.get(proposal_sequence)
                if (
                    set(payload) != expected_fields
                    or proposal_record is None
                    or proposal_record.record_kind
                    != "condition_application_proposal"
                    or proposal_record.operation_sequence
                    >= record.operation_sequence
                    or proposal_record.record_sha256
                    != payload.get("proposal_record_sha256")
                    or proposal_record.event_id != record.event_id
                    or proposal_record.target_id != record.target_id
                ):
                    raise ControlEngineError(
                        "Final condition application lacks its exact issued proposal"
                    )
                proposal_payload = json.loads(proposal_record.payload_json)
                root_id = payload.get("root_condition_instance_id")
                lineage = lineage_for_root(str(root_id))
                expected_created = [
                    application_projection(row) for row in lineage
                ]
                post_condition_ids = sorted({
                    row["condition_id"]
                    for row in snapshot_condition_rows(
                        record.post_operation_state_json,
                        target_id=str(record.target_id),
                        event_sequence=record.event_sequence,
                    )
                })
                if (
                    payload.get("kind") != "condition_application"
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("target_id") != record.target_id
                    or proposal_payload.get("condition_instance", {}).get(
                        "instance_id"
                    )
                    != root_id
                    or payload.get("created_condition_instances")
                    != expected_created
                    or any(
                        row["application_event_id"] != record.event_id
                        or row["application_sequence"] != record.event_sequence
                        for row in lineage
                    )
                    or payload.get("active_conditions_after")
                    != post_condition_ids
                ):
                    raise ControlEngineError(
                        "Final condition application state or lineage does not replay"
                    )

            elif record.record_kind == "condition_end":
                expected_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "target_id",
                    "root_condition_instance_id",
                    "ended_condition_instances",
                    "active_conditions_after",
                }
                root_id = payload.get("root_condition_instance_id")
                lineage = lineage_for_root(str(root_id))
                ended = [
                    row for row in reversed(lineage)
                    if row["end_event_id"] == record.event_id
                    and row["end_sequence"] == record.event_sequence
                ]
                post_condition_ids = sorted({
                    row["condition_id"]
                    for row in snapshot_condition_rows(
                        record.post_operation_state_json,
                        target_id=str(record.target_id),
                        event_sequence=record.event_sequence,
                    )
                })
                if (
                    set(payload) != expected_fields
                    or payload.get("kind") != "condition_end"
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("target_id") != record.target_id
                    or not ended
                    or payload.get("ended_condition_instances") != ended
                    or payload.get("active_conditions_after")
                    != post_condition_ids
                ):
                    raise ControlEngineError(
                        "Final condition end state or lineage does not replay"
                    )

            elif record.record_kind == "branch_transition":
                created_rows = payload.get("created_condition_instances", [])
                if not isinstance(created_rows, list):
                    raise ControlEngineError(
                        "Final branch condition-instance rows are malformed"
                    )
                pre_root_ids = {
                    row["condition_instance_id"]
                    for row in json.loads(record.pre_operation_state_json)
                    if row.get("target_id") == record.target_id
                    and row.get("condition_instance_id") is not None
                }
                post_root_ids = {
                    row["condition_instance_id"]
                    for row in json.loads(record.post_operation_state_json)
                    if row.get("target_id") == record.target_id
                    and row.get("condition_instance_id") is not None
                }
                expected_created: list[dict[str, Any]] = []
                for root_id in sorted(post_root_ids - pre_root_ids):
                    expected_created.extend(
                        application_projection(row)
                        for row in lineage_for_root(root_id)
                    )
                if created_rows != expected_created:
                    raise ControlEngineError(
                        "Final branch condition-instance delta does not replay"
                    )

            if record.record_kind == "action_legality":
                decision = {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {"event_id", "event_sequence", "resolution_created"}
                }
                expected = expected_legality(
                    decision,
                    snapshot_json=record.pre_operation_state_json,
                    event_sequence=record.event_sequence,
                )
                if (
                    events[record.event_id].kind != "action_proposal"
                    or record.target_id != expected["actor_id"]
                    or decision != expected
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("resolution_created")
                    is not expected["allowed"]
                ):
                    raise ControlEngineError(
                        "Final source-relative action legality does not replay"
                    )

            if record.record_kind != "opportunity_roll":
                continue
            opportunity_kind = payload.get("kind")
            advantage = sorted_unique_strings(
                payload.get("advantage_sources"),
                "opportunity advantage sources",
            )
            disadvantage = sorted_unique_strings(
                payload.get("disadvantage_sources"),
                "opportunity disadvantage sources",
            )
            for source_id in (*advantage, *disadvantage):
                if source_id.startswith("condition_instance:"):
                    condition_id = source_id.removeprefix("condition_instance:")
                    active_target = (
                        payload.get("actor_id")
                        if opportunity_kind != "attack_opportunity"
                        else None
                    )
                    candidate_targets = (
                        [active_target]
                        if active_target is not None
                        else [payload.get("attacker_id"), payload.get("defender_id")]
                    )
                    if not any(
                        condition_id
                        in {
                            row["instance_id"]
                            for row in snapshot_condition_rows(
                                record.pre_operation_state_json,
                                target_id=str(target),
                                event_sequence=record.event_sequence,
                            )
                        }
                        for target in candidate_targets
                        if isinstance(target, str)
                    ):
                        raise ControlEngineError(
                            "Final opportunity sources contain a foreign live "
                            "condition identity"
                        )

            if opportunity_kind == "attack_opportunity":
                expected_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "attacker_id",
                    "defender_id",
                    "attack_gate_ids",
                    "legality",
                    "roll_created",
                    "roll_mode",
                    "advantage_sources",
                    "disadvantage_sources",
                    "outgoing_normalization",
                    "incoming_normalization",
                }
                gate_ids = sorted_unique_strings(
                    payload.get("attack_gate_ids"),
                    "attack gate IDs",
                )
                if set(payload) != expected_fields:
                    raise ControlEngineError(
                        "Final attack opportunity shape is malformed"
                    )
                for gate_id in gate_ids:
                    try:
                        gate = self._program.gate(gate_id)
                    except Exception as error:
                        raise ControlEngineError(
                            "Final attack opportunity references a foreign gate"
                        ) from error
                    if gate.resolution_kind != "attack_roll":
                        raise ControlEngineError(
                            "Final attack opportunity gate kind is fabricated"
                        )
                expected_decision = expected_legality(
                    payload.get("legality"),
                    snapshot_json=record.pre_operation_state_json,
                    event_sequence=record.event_sequence,
                )
                if (
                    payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("attacker_id") != record.target_id
                    or payload.get("legality") != expected_decision
                ):
                    raise ControlEngineError(
                        "Final attack opportunity legality does not replay"
                    )
                if not expected_decision["allowed"]:
                    if (
                        payload.get("roll_created") is not False
                        or payload.get("roll_mode") is not None
                        or advantage
                        or disadvantage
                        or payload.get("outgoing_normalization") is not None
                        or payload.get("incoming_normalization") is not None
                    ):
                        raise ControlEngineError(
                            "Final prohibited attack fabricated a roll"
                        )
                    continue
                if payload.get("roll_created") is not True:
                    raise ControlEngineError(
                        "Final legal attack omitted its roll"
                    )
                outgoing, _ = validate_normalization(
                    payload.get("outgoing_normalization"),
                    label="outgoing attack normalization",
                    target_id=str(payload.get("attacker_id")),
                    record=record,
                )
                incoming, _ = validate_normalization(
                    payload.get("incoming_normalization"),
                    label="incoming attack normalization",
                    target_id=str(payload.get("defender_id")),
                    record=record,
                )
                required_advantage = {
                    source_id
                    for row in incoming
                    if row.get("primitive_id") == "defensive_attack_advantage"
                    for source_id in row.get("source_component_ids", ())
                }
                required_disadvantage = {
                    source_id
                    for row in (*outgoing, *incoming)
                    if row.get("primitive_id")
                    in {
                        "offensive_impairment_all_attacks",
                        "offensive_impairment_next_attack",
                        "prone_incoming_attack_context",
                    }
                    for source_id in row.get("source_component_ids", ())
                }
                if (
                    not required_advantage.issubset(advantage)
                    or not required_disadvantage.issubset(disadvantage)
                    or payload.get("roll_mode")
                    != resolve_roll_mode(len(advantage), len(disadvantage))
                ):
                    raise ControlEngineError(
                        "Final attack opportunity roll mode or sources are fabricated"
                    )

            elif opportunity_kind == "save_opportunity":
                expected_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "actor_id",
                    "ability",
                    "save_gate_ids",
                    "roll_created",
                    "automatic_failure",
                    "automatic_failure_sources",
                    "roll_mode",
                    "advantage_sources",
                    "disadvantage_sources",
                    "normalization",
                    "probability_branch_created",
                }
                gate_ids = sorted_unique_strings(
                    payload.get("save_gate_ids"),
                    "save gate IDs",
                )
                auto_sources = sorted_unique_strings(
                    payload.get("automatic_failure_sources"),
                    "automatic-failure sources",
                )
                if (
                    set(payload) != expected_fields
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("actor_id") != record.target_id
                ):
                    raise ControlEngineError(
                        "Final save opportunity identity or shape is malformed"
                    )
                for gate_id in gate_ids:
                    try:
                        gate = self._program.gate(gate_id)
                    except Exception as error:
                        raise ControlEngineError(
                            "Final save opportunity references a foreign gate"
                        ) from error
                    if (
                        gate.resolution_kind != "saving_throw"
                        or gate.ability != payload.get("ability")
                    ):
                        raise ControlEngineError(
                            "Final save opportunity gate authority is fabricated"
                        )
                contributions, suppressions = validate_normalization(
                    payload.get("normalization"),
                    label="save normalization",
                    target_id=str(payload.get("actor_id")),
                    record=record,
                )
                required_auto = {
                    source_id
                    for row in contributions
                    if row.get("primitive_id") == "save_auto_failure"
                    for source_id in row.get("source_component_ids", ())
                }
                required_disadvantage = {
                    source_id
                    for row in contributions
                    if row.get("primitive_id") == "save_disadvantage"
                    for source_id in row.get("source_component_ids", ())
                }
                required_disadvantage.update(
                    source_id
                    for row in suppressions
                    if row.get("primitive_id") == "save_disadvantage"
                    and row.get("reason")
                    == "automatic_failure_dominates_disadvantage"
                    for source_id in row.get(
                        "suppressed_source_component_ids",
                        (),
                    )
                )
                automatic_failure = bool(required_auto)
                if (
                    set(auto_sources) != required_auto
                    or payload.get("automatic_failure") is not automatic_failure
                    or not required_disadvantage.issubset(disadvantage)
                    or payload.get("roll_created") is automatic_failure
                    or payload.get("probability_branch_created")
                    is automatic_failure
                    or payload.get("roll_mode")
                    != (
                        None
                        if automatic_failure
                        else resolve_roll_mode(
                            len(advantage),
                            len(disadvantage),
                        )
                    )
                ):
                    raise ControlEngineError(
                        "Final save opportunity roll mode or automatic failure "
                        "does not replay"
                    )

            elif opportunity_kind == "initiative_opportunity":
                expected_fields = {
                    "kind",
                    "event_id",
                    "event_sequence",
                    "actor_id",
                    "roll_created",
                    "roll_mode",
                    "advantage_sources",
                    "disadvantage_sources",
                    "normalization",
                }
                if (
                    set(payload) != expected_fields
                    or events[record.event_id].kind != "initiative_opportunity"
                    or payload.get("event_id") != record.event_id
                    or payload.get("event_sequence") != record.event_sequence
                    or payload.get("actor_id") != record.target_id
                    or payload.get("roll_created") is not True
                    or payload.get("roll_mode")
                    != resolve_roll_mode(len(advantage), len(disadvantage))
                ):
                    raise ControlEngineError(
                        "Final initiative opportunity does not replay"
                    )
                contributions, _ = validate_normalization(
                    payload.get("normalization"),
                    label="initiative normalization",
                    target_id=str(payload.get("actor_id")),
                    record=record,
                )
                required_disadvantage = {
                    source_id
                    for row in contributions
                    if row.get("primitive_id") == "initiative_disadvantage"
                    for source_id in row.get("source_component_ids", ())
                }
                if not required_disadvantage.issubset(disadvantage):
                    raise ControlEngineError(
                        "Final initiative opportunity omitted live condition sources"
                    )
            else:
                raise ControlEngineError(
                    "Final opportunity roll kind is fabricated"
                )

        executed_falls: set[tuple[str, str]] = set()
        for record in self._issued_records:
            payload = json.loads(record.payload_json)
            fall = (
                payload
                if record.record_kind == "fall_transition"
                else payload.get("fall_transition")
                if record.record_kind
                in {"condition_application", "branch_transition", "prone_operation"}
                else None
            )
            if fall is None:
                continue
            if not isinstance(fall, Mapping):
                raise ControlEngineError("Final fall transition is malformed")
            transition = fall.get("transition")
            identity = (fall.get("event_id"), fall.get("target_id"))
            if (
                fall.get("kind") != "fall_transition"
                or identity != (record.event_id, record.target_id)
                or fall.get("event_sequence") != record.event_sequence
                or not isinstance(transition, Mapping)
                or set(transition)
                != {
                    "target_id",
                    "falls",
                    "reason",
                    "origin",
                    "damage",
                    "altitude_ft",
                    "source_component_id",
                }
                or transition.get("target_id") != record.target_id
                or not isinstance(transition.get("falls"), bool)
                or transition.get("damage") is not None
                or transition.get("altitude_ft") is not None
                or transition.get("origin")
                != ("current_position" if transition.get("falls") else None)
                or fall.get("executed")
                is not (
                    transition.get("falls")
                    and not fall.get("duplicate_trigger_collapsed")
                )
            ):
                raise ControlEngineError(
                    "Final fall transition execution does not replay"
                )
            if not isinstance(fall.get("duplicate_trigger_collapsed"), bool):
                raise ControlEngineError(
                    "Final fall duplicate marker is malformed"
                )
            if fall["duplicate_trigger_collapsed"] and identity not in executed_falls:
                raise ControlEngineError(
                    "Final fall transition claims a nonexistent earlier duplicate"
                )
            if fall["executed"]:
                if identity in executed_falls:
                    raise ControlEngineError(
                        "Final replay contains duplicate fall execution"
                    )
                executed_falls.add(identity)
            trigger_ids = fall.get("trigger_condition_instance_ids")
            if trigger_ids is not None:
                trigger_ids = sorted_unique_strings(
                    trigger_ids,
                    "fall trigger condition instance IDs",
                )
                fly_source_ids = sorted_unique_strings(
                    fall.get("trigger_fly_speed_zero_source_component_ids"),
                    "fall Fly-Speed-0 source component IDs",
                )
                instances = [registry.get(instance_id) for instance_id in trigger_ids]
                fly_source_actors: set[str] = set()
                fly_source_effects: set[str] = set()
                for component_id in fly_source_ids:
                    matching_conditions = [
                        row for row in registry.values()
                        if row["target_id"] == record.target_id
                        and row["application_event_id"] == record.event_id
                        and row["source_component_id"] == component_id
                    ]
                    if matching_conditions:
                        fly_source_actors.update(
                            row["source_actor_id"] for row in matching_conditions
                        )
                        fly_source_effects.update(
                            row["source_effect_id"] for row in matching_conditions
                        )
                        continue
                    try:
                        self._program.component(component_id)
                    except Exception as error:
                        raise ControlEngineError(
                            "Final Fly-Speed-0 fall references a foreign source "
                            "component"
                        ) from error
                    fly_source_actors.add(self._source_actor_id)
                    fly_source_effects.add(self._program.effect_id)
                expected_component_ids = sorted(
                    {
                        instance["source_component_id"]
                        for instance in instances
                        if instance is not None
                    }
                    | set(fly_source_ids)
                )
                expected_reason = (
                    "prone"
                    if any(
                        instance is not None
                        and instance["condition_id"] == "prone"
                        for instance in instances
                    )
                    else "incapacitated"
                    if any(
                        instance is not None
                        and instance["condition_id"] == "incapacitated"
                        for instance in instances
                    )
                    else "fly_speed_zero"
                )
                if (
                    not trigger_ids and not fly_source_ids
                    or any(instance is None for instance in instances)
                    or any(
                        instance["condition_id"] not in {"prone", "incapacitated"}
                        or instance["target_id"] != record.target_id
                        or instance["application_event_id"] != record.event_id
                        for instance in instances
                    )
                    or fall.get("source_actor_ids")
                    != sorted(
                        {
                            instance["source_actor_id"]
                            for instance in instances
                            if instance is not None
                        }
                        | fly_source_actors
                    )
                    or fall.get("source_effect_ids")
                    != sorted(
                        {
                            instance["source_effect_id"]
                            for instance in instances
                            if instance is not None
                        }
                        | fly_source_effects
                    )
                    or fall.get("source_component_ids")
                    != expected_component_ids
                    or transition.get("source_component_id")
                    != (
                        expected_component_ids[0]
                        if len(expected_component_ids) == 1 else None
                    )
                    or transition.get("reason")
                    not in {
                        expected_reason,
                        "not_airborne",
                        "hover_or_explicit_prevention",
                    }
                ):
                    raise ControlEngineError(
                        "Final condition fall provenance does not replay"
                    )

        for record in self._issued_records:
            if record.record_kind not in {"condition_application", "branch_transition"}:
                continue
            payload = json.loads(record.payload_json)
            wrapper = payload.get("condition_concentration_end")
            if wrapper is None:
                continue
            if not isinstance(wrapper, Mapping) or set(wrapper) != {
                "kind",
                "condition_instance_ids",
                "owner_actor_id",
                "tracker_end_record",
                "cleanup_transition",
                "active_effect_id",
            }:
                raise ControlEngineError(
                    "Final condition concentration wrapper is malformed"
                )
            instance_ids = sorted_unique_strings(
                wrapper["condition_instance_ids"],
                "condition concentration instance IDs",
            )
            instances = [registry.get(instance_id) for instance_id in instance_ids]
            tracker_end = wrapper["tracker_end_record"]
            cleanup = wrapper["cleanup_transition"]
            if (
                wrapper.get("kind") != "condition_concentration_end"
                or not instance_ids
                or any(instance is None for instance in instances)
                or any(
                    instance["condition_id"] != "incapacitated"
                    or instance["target_id"] != wrapper.get("owner_actor_id")
                    or instance["application_event_id"] != record.event_id
                    for instance in instances
                )
                or wrapper.get("owner_actor_id") != self._source_actor_id
                or wrapper.get("active_effect_id") is not None
                or not isinstance(tracker_end, Mapping)
                or not isinstance(cleanup, Mapping)
                or tracker_end.get("kind") != "concentration_end"
                or cleanup.get("kind") != "concentration_end"
                or tracker_end.get("event_id") != record.event_id
                or cleanup.get("event_id") != record.event_id
                or tracker_end.get("owner_actor_id") != wrapper.get("owner_actor_id")
                or cleanup.get("owner_actor_id") != wrapper.get("owner_actor_id")
                or tracker_end.get("effect_id") != self._program.effect_id
                or cleanup.get("effect_id") != self._program.effect_id
                or tracker_end.get("reason") != "controller_incapacitated"
                or cleanup.get("reason") != "controller_incapacitated"
                or tracker_end.get("changed") is not True
                or cleanup.get("changed") is not True
                or cleanup.get("active_components_after")
                != json.loads(record.post_operation_state_json)
            ):
                raise ControlEngineError(
                    "Final condition concentration owner, effect, or destructive "
                    "cleanup does not replay"
                )

    def _validate_internal_ledgers(self) -> None:
        payloads_by_kind: dict[str, list[Any]] = {}
        issued_route_transitions: list[Any] = []
        for record in self._issued_records:
            payload = json.loads(record.payload_json)
            payloads_by_kind.setdefault(record.record_kind, []).append(payload)
            if isinstance(payload.get("route_transition"), Mapping):
                issued_route_transitions.append(payload["route_transition"])

        issued_condition_concentration = [
            payload["condition_concentration_end"]
            for record_kind in ("condition_application", "branch_transition")
            for payload in payloads_by_kind.get(record_kind, ())
            if payload.get("condition_concentration_end") is not None
        ]
        issued_concentration = [
            json.loads(record.payload_json)
            for record in self._issued_records
            if record.record_kind in {
                "concentration_start",
                "concentration_check",
                "concentration_end",
                "concentration_duration_reconciliation",
            }
        ]
        issued_concentration.extend(
            payload["cleanup_transition"]
            for payload in issued_condition_concentration
        )
        issued_fall_transitions: list[Mapping[str, Any]] = []
        issued_legality: list[Mapping[str, Any]] = []
        for record in self._issued_records:
            payload = json.loads(record.payload_json)
            if record.record_kind == "fall_transition":
                issued_fall_transitions.append(payload)
            elif (
                record.record_kind
                in {"condition_application", "branch_transition"}
                and payload.get("fall_transition") is not None
            ):
                issued_fall_transitions.append(payload["fall_transition"])
            elif (
                record.record_kind == "prone_operation"
                and payload.get("fall_transition") is not None
            ):
                issued_fall_transitions.append(payload["fall_transition"])
            if record.record_kind == "action_legality":
                issued_legality.append(payload)
            elif (
                record.record_kind == "opportunity_roll"
                and isinstance(payload.get("legality"), Mapping)
            ):
                issued_legality.append({
                    **payload["legality"],
                    "event_id": payload["event_id"],
                    "event_sequence": payload["event_sequence"],
                    "resolution_created": bool(
                        payload["legality"].get("allowed")
                    ),
                })

        comparisons = (
            (
                "branch transitions",
                self._event_state_transitions,
                payloads_by_kind.get("branch_transition", ()),
            ),
            (
                "normalization results",
                self._normalization_results,
                payloads_by_kind.get("normalization", ()),
            ),
            (
                "area responses",
                self._area_records,
                payloads_by_kind.get("area_response", ()),
            ),
            (
                "area route transitions",
                self._area_route_transitions,
                issued_route_transitions,
            ),
            (
                "Prone responses",
                self._prone_records,
                payloads_by_kind.get("prone_operation", ()),
            ),
            (
                "concentration lifecycle",
                self._concentration_records,
                issued_concentration,
            ),
            (
                "condition operations",
                self._condition_operation_records,
                tuple(
                    json.loads(record.payload_json)
                    for record in self._issued_records
                    if record.record_kind
                    in {"condition_application", "condition_end"}
                ),
            ),
            (
                "opportunity rolls",
                self._opportunity_roll_records,
                payloads_by_kind.get("opportunity_roll", ()),
            ),
            (
                "condition concentration ends",
                self._condition_concentration_records,
                issued_condition_concentration,
            ),
            (
                "source-relative legality decisions",
                self._source_relative_legality_records,
                issued_legality,
            ),
            (
                "fall transitions",
                self._fall_transition_records,
                issued_fall_transitions,
            ),
            (
                "displacement lifecycle",
                self._displacement_records,
                tuple(
                    json.loads(record.payload_json)
                    for record in self._issued_records
                    if record.record_kind in {
                        "displacement",
                        "displacement_epoch_boundary",
                    }
                ),
            ),
        )
        for label, internal_rows, issued_rows in comparisons:
            if _canonical_json(internal_rows) != _canonical_json(issued_rows):
                raise ControlEngineError(
                    f"Internal {label} do not match the issued record stream"
                )
        pending_checks = payloads_by_kind.get(
            "concentration_check_pending_end",
            (),
        )
        completed_failed_checks = [
            row for row in self._concentration_records
            if row.get("kind") == "concentration_check_lifecycle"
            and row.get("check_record", {}).get("outcome") == "failure"
        ]
        if len(pending_checks) != len(completed_failed_checks):
            raise ControlEngineError(
                "Internal pending concentration checks do not match completed "
                "failure lifecycles"
            )
        for pending_payload in pending_checks:
            pending = pending_payload.get("pending_failure", {})
            matches = [
                lifecycle for lifecycle in completed_failed_checks
                if lifecycle.get("check_record") == pending.get("check_record")
                and lifecycle.get("tracker_records") == [
                    pending.get("check_record"),
                    pending.get("tracker_end_record"),
                ]
            ]
            if len(matches) != 1:
                raise ControlEngineError(
                    "Internal failed-check pending record has no exact completed "
                    "concentration lifecycle"
                )
        if self._repeat_save_records:
            raise ControlEngineError(
                "Session repeat-save rows must be represented by branch records"
            )

    def _area_effect_active_before_event(self, event: TimelineEvent) -> bool:
        if not self._canonical_persistent_area_ids():
            return False
        if not self._concentration_required:
            return any(
                candidate.kind == "activation"
                and candidate.sequence < event.sequence
                for candidate in self._schedule.events
            )
        active = False
        for record in self._issued_records:
            if record.event_sequence >= event.sequence:
                continue
            if record.record_kind == "concentration_start":
                active = True
            elif record.record_kind == "concentration_end":
                active = False
            elif record.record_kind == "concentration_duration_reconciliation":
                payload = json.loads(record.payload_json)
                if payload.get("active_effect_id") is None:
                    active = False
        return active

    def _area_gate_eligible_in_snapshot(
        self,
        *,
        gate_id: str,
        target_id: str,
        event: TimelineEvent,
        snapshot: _ClosedEventSnapshot,
    ) -> bool:
        area_ids = self._canonical_area_gate_bindings().get(gate_id, ())
        if not area_ids:
            return True
        if not self._area_effect_active_before_event(event):
            return False
        route_rows = json.loads(snapshot.pre_event_route_state_json)
        for area_id in area_ids:
            matches = [
                row for row in route_rows
                if row.get("effect_id") == self._program.effect_id
                and row.get("area_id") == area_id
                and row.get("target_id") == target_id
            ]
            if matches:
                if len(matches) != 1:
                    raise ControlEngineError(
                        "Area-owned gate replay has no unique authoritative "
                        "pre-event membership state"
                    )
                if matches[0].get("membership") is not True:
                    return False
            else:
                raise ControlEngineError(
                    "Area-owned gate replay has no authoritative membership state"
                )
        gate = self._program.gate(gate_id)
        active_component_ids = {
            row["component_id"]
            for row in json.loads(snapshot.pre_event_state_json)
            if row.get("effect_id") == self._program.effect_id
            and row.get("target_id") == target_id
        }
        return not (
            set(gate.requires_active_component_ids) - active_component_ids
        )

    def _validate_area_entry_history(self) -> None:
        """Replay issued entry decisions and authoritative membership changes."""

        replay_history: set[tuple[str, str, str, str]] = set()
        entry_records: dict[tuple[str, str], _IssuedControlRecord] = {}
        geometry_records = {
            (record.event_id, str(record.target_id)): record
            for record in self._issued_records
            if record.record_kind == "area_geometry_update"
            and record.target_id is not None
        }
        for record in self._issued_records:
            if record.record_kind != "area_entry" or record.target_id is None:
                continue
            identity = (record.event_id, record.target_id)
            if identity in entry_records:
                raise ControlEngineError(
                    "Area-entry replay found duplicate transition identities"
                )
            entry_records[identity] = record
            payload = json.loads(record.payload_json)
            bound = self._area_entry_transitions.get(identity)
            if bound is None or payload.get("bound_transition") != bound.to_dict():
                raise ControlEngineError(
                    "Area-entry replay found a foreign or rewritten transition"
                )
            if (
                payload.get("kind") != "area_entry"
                or payload.get("event_id") != bound.event_id
                or payload.get("event_sequence") != bound.event_sequence
                or payload.get("effect_id") != bound.effect_id
                or payload.get("area_id") != bound.area_id
                or payload.get("target_id") != bound.target_id
                or payload.get("entry_cause") != bound.cause
                or payload.get("turn_id") != bound.turn_id
                or payload.get("membership_before") is not False
                or payload.get("membership_after") is not True
            ):
                raise ControlEngineError(
                    "Area-entry replay identity or membership facts are malformed"
                )
            pre_event_rows = json.loads(record.pre_event_route_state_json)
            pre_matches = [
                row for row in pre_event_rows
                if row.get("effect_id") == bound.effect_id
                and row.get("area_id") == bound.area_id
                and row.get("target_id") == bound.target_id
            ]
            if len(pre_matches) != 1 or pre_matches[0].get("membership") is not False:
                raise ControlEngineError(
                    "Area-entry replay requires authoritative pre-event "
                    "membership false"
                )
            if not self._area_effect_active_before_event(
                self._schedule.event(record.event_id)
            ):
                raise ControlEngineError(
                    "Area-entry replay found an inactive compiled area"
                )
            if bound.cause == "area_movement":
                geometry = geometry_records.get(identity)
                if geometry is None:
                    raise ControlEngineError(
                        "Area-movement entry lacks its issued geometry update"
                    )
                geometry_payload = json.loads(geometry.payload_json)
                restoration_pre_state_json = geometry.pre_operation_state_json
                if (
                    geometry.operation_sequence >= record.operation_sequence
                    or payload.get("geometry_operation_sequence")
                    != geometry.operation_sequence
                    or payload.get("geometry_record_sha256")
                    != geometry.record_sha256
                    or geometry_payload.get("membership_before") is not False
                    or geometry_payload.get("membership_after") is not True
                    or geometry_payload.get("old_route_state")
                    != payload.get("old_route_state")
                    or geometry_payload.get("new_route_state")
                    != payload.get("new_route_state")
                    or payload.get("pre_route_state_sha256")
                    != geometry_payload.get("pre_route_state_sha256")
                    or payload.get("post_route_state_sha256")
                    != geometry_payload.get("post_route_state_sha256")
                    or payload.get("ambient_area_component_ids")
                    != geometry_payload.get("ambient_area_component_ids")
                    or payload.get("retained_ambient_component_ids")
                    != geometry_payload.get("retained_ambient_component_ids")
                    or payload.get("restored_ambient_component_ids")
                    != geometry_payload.get("restored_ambient_component_ids")
                ):
                    raise ControlEngineError(
                        "Area-movement entry and geometry operation are discontinuous"
                    )
            else:
                restoration_pre_state_json = record.pre_operation_state_json
                route_transition = payload.get("route_transition")
                if (
                    not isinstance(route_transition, Mapping)
                    or route_transition.get("transition_kind") != "area_entry"
                    or payload.get("pre_route_state_sha256")
                    != route_transition.get("pre_route_state_sha256")
                    or payload.get("post_route_state_sha256")
                    != route_transition.get("post_route_state_sha256")
                ):
                    raise ControlEngineError(
                        "Ordinary/forced entry lacks its membership route transition"
                    )
            ambient_authority_rows = self._live_ambient_area_component_plan(
                area_id=bound.area_id,
                target_id=bound.target_id,
                event_sequence=bound.event_sequence,
            )
            ambient_ids = [
                component.component_id
                for component, _expiry_event_id, _activation_event_id
                in ambient_authority_rows
            ]
            restoration_pre_ids = {
                row["component_id"]
                for row in json.loads(restoration_pre_state_json)
                if row.get("effect_id") == bound.effect_id
                and row.get("target_id") == bound.target_id
            }
            expected_retained_ambient_ids = [
                component_id
                for component_id in ambient_ids
                if component_id in restoration_pre_ids
            ]
            expected_restored_ambient_ids = [
                component_id
                for component_id in ambient_ids
                if component_id not in restoration_pre_ids
            ]
            post_rows = [
                row for row in json.loads(record.post_operation_state_json)
                if row.get("effect_id") == bound.effect_id
                and row.get("target_id") == bound.target_id
            ]
            post_by_component_id = {
                row["component_id"]: row for row in post_rows
            }
            expected_restored_expiry = {
                component.component_id: expiry_event_id
                for component, expiry_event_id, _activation_event_id
                in ambient_authority_rows
                if component.component_id in expected_restored_ambient_ids
            }
            if (
                payload.get("ambient_area_component_ids") != ambient_ids
                or payload.get("retained_ambient_component_ids")
                != expected_retained_ambient_ids
                or payload.get("restored_ambient_component_ids")
                != expected_restored_ambient_ids
                or any(
                    component_id not in post_by_component_id
                    for component_id in ambient_ids
                )
                or any(
                    post_by_component_id[component_id].get("applied_event_id")
                    != record.event_id
                    for component_id in expected_restored_ambient_ids
                )
                or any(
                    post_by_component_id[component_id].get("expiry_event_id")
                    != expected_restored_expiry[component_id]
                    for component_id in expected_restored_ambient_ids
                )
                or any(
                    sum(
                        row.get("component_id") == component_id
                        for row in post_rows
                    ) != 1
                    for component_id in ambient_ids
                )
            ):
                raise ControlEngineError(
                    "Area-entry ambient component restoration does not replay"
                )
            area = next(
                selector.area
                for selector in self._program.selectors
                if selector.area is not None
                and selector.area.area_id == bound.area_id
            )
            policy = None if area.entry_policy is None else area.entry_policy.to_dict()
            if not isinstance(policy, Mapping):
                raise ControlEngineError(
                    "Area-entry replay found missing compiled policy"
                )
            frequency_key = (
                bound.effect_id,
                bound.area_id,
                bound.target_id,
                bound.turn_id,
            )
            previously_triggered = frequency_key in replay_history
            frequency_permitted = bool(
                policy.get("frequency") == "unlimited"
                or not previously_triggered
            )
            movement_counts = bool(
                bound.cause != "area_movement"
                or bound.moved_area_counts_as_entry
            )
            triggered = bool(movement_counts and frequency_permitted)
            if not movement_counts:
                frequency_decision = "area_movement_does_not_count"
            elif not frequency_permitted:
                frequency_decision = "once_per_turn_already_triggered"
            elif policy.get("frequency") == "once_per_turn":
                frequency_decision = "first_qualifying_entry_this_turn"
            else:
                frequency_decision = "unlimited_entry"
            gate_ids = list(self._entry_gate_ids(bound)) if triggered else []
            if (
                payload.get("entry_policy") != policy
                or payload.get("frequency_key") != {
                    "effect_id": frequency_key[0],
                    "area_id": frequency_key[1],
                    "target_id": frequency_key[2],
                    "turn_id": frequency_key[3],
                }
                or payload.get("previously_triggered_this_turn")
                is not previously_triggered
                or payload.get("frequency_permitted") is not frequency_permitted
                or payload.get("frequency_decision") != frequency_decision
                or payload.get("frequency_history_consumed") is not triggered
                or payload.get("triggered") is not triggered
                or payload.get("gate_opportunity_ids") != gate_ids
                or payload.get("gate_requirement_ids") != gate_ids
            ):
                raise ControlEngineError(
                    "Area-entry frequency or gate decision does not replay"
                )
            if triggered:
                replay_history.add(frequency_key)

        for identity, bound in self._area_entry_transitions.items():
            if (
                bound.cause != "area_movement"
                and self._area_effect_active_before_event(
                    self._schedule.event(bound.event_id)
                )
                and identity not in entry_records
            ):
                raise ControlEngineError(
                    "Active scenario-bound AreaEntryTransition lacks its issued "
                    "false-to-true membership attestation"
                )

        false_to_true = {
            (str(row.get("event_id")), str(row.get("target_id")))
            for row in self._area_route_transitions
            if row.get("old_route_state", {}).get("membership") is False
            and row.get("new_route_state", {}).get("membership") is True
        }
        if set(entry_records) != false_to_true:
            raise ControlEngineError(
                "Area-entry records do not exactly cover false-to-true membership "
                "transitions"
            )
        if replay_history != self._area_entry_trigger_history:
            raise ControlEngineError(
                "Engine-owned area-entry frequency history is stale or malformed"
            )

    def _validate_area_gate_execution(self) -> None:
        area_gate_bindings = self._canonical_area_gate_bindings()
        if not area_gate_bindings:
            return
        snapshots = {
            snapshot.event_id: snapshot for snapshot in self._event_snapshots
        }
        entry_records: dict[tuple[str, str], _IssuedControlRecord] = {}
        for record in self._issued_records:
            if record.record_kind != "area_entry" or record.target_id is None:
                continue
            identity = (record.event_id, record.target_id)
            if identity in entry_records:
                raise ControlEngineError(
                    "Area-gate replay found duplicate entry attestations"
                )
            entry_records[identity] = record

        def entry_eligible(
            gate_id: str,
            target_id: str,
            event_id: str,
        ) -> tuple[bool, _IssuedControlRecord | None]:
            entry_record = entry_records.get((event_id, target_id))
            if entry_record is None:
                return False, None
            payload = json.loads(entry_record.payload_json)
            bound = self._area_entry_transitions.get((event_id, target_id))
            eligible = bool(
                bound is not None
                and payload.get("bound_transition") == bound.to_dict()
                and payload.get("triggered") is True
                and payload.get("frequency_permitted") is True
                and gate_id in payload.get("gate_requirement_ids", ())
                and bound.area_id in area_gate_bindings.get(gate_id, ())
            )
            return eligible, entry_record

        observed: dict[tuple[str, str, str], list[_IssuedControlRecord]] = {}
        for record in self._issued_records:
            if record.record_kind != "branch_transition":
                continue
            payload = json.loads(record.payload_json)
            gate_id = payload.get("gate_id")
            if gate_id not in area_gate_bindings or record.target_id is None:
                continue
            event = self._schedule.event(record.event_id)
            snapshot = snapshots[record.event_id]
            gate = self._program.gate(str(gate_id))
            if gate.trigger.kind == "entry":
                eligible, entry_record = entry_eligible(
                    str(gate_id),
                    record.target_id,
                    record.event_id,
                )
                if (
                    not eligible
                    or entry_record is None
                    or entry_record.operation_sequence >= record.operation_sequence
                ):
                    raise ControlEngineError(
                        "Issued entry branch lacks an earlier same-event attested "
                        "false-to-true membership transition"
                    )
            elif not self._area_gate_eligible_in_snapshot(
                gate_id=str(gate_id),
                target_id=record.target_id,
                event=event,
                snapshot=snapshot,
            ):
                raise ControlEngineError(
                    "Issued area-owned branch lacks authoritative pre-event "
                    "membership or active-area eligibility"
                )
            observed.setdefault(
                (record.event_id, str(gate_id), record.target_id),
                [],
            ).append(record)

        required_plan = json.loads(self._required_operation_plan_json)
        for event_id, operations in required_plan.items():
            event = self._schedule.event(event_id)
            snapshot = snapshots[event_id]
            for operation in operations:
                parts = operation.split(":", 2)
                if len(parts) != 3 or parts[0] != "branch":
                    continue
                gate_id, target_id = parts[1], parts[2]
                if (
                    gate_id not in area_gate_bindings
                    or gate_id not in self._program.root_gate_ids
                ):
                    continue
                gate = self._program.gate(gate_id)
                if gate.trigger.kind == "entry":
                    eligible, _entry_record = entry_eligible(
                        gate_id,
                        target_id,
                        event_id,
                    )
                else:
                    eligible = self._area_gate_eligible_in_snapshot(
                        gate_id=gate_id,
                        target_id=target_id,
                        event=event,
                        snapshot=snapshot,
                    )
                count = len(observed.get((event_id, gate_id, target_id), ()))
                if count != (1 if eligible else 0):
                    raise ControlEngineError(
                        "Area-owned root-gate execution does not match canonical "
                        "pre-event membership and effect chronology"
                    )

    def _validate_event_snapshots(self) -> None:
        if len(self._event_snapshots) != len(self._schedule.events):
            raise ControlEngineError(
                "The session must consume and close the complete timeline before result()"
            )
        previous_post = self._initial_state_json
        previous_route_post = self._initial_area_route_state_json
        for event, snapshot in zip(
            self._schedule.events,
            self._event_snapshots,
            strict=True,
        ):
            if (
                snapshot.scenario_digest != self._scenario_digest
                or snapshot.event_id != event.event_id
                or snapshot.event_sequence != event.sequence
                or snapshot.pre_event_state_json != previous_post
                or snapshot.pre_event_route_state_json != previous_route_post
            ):
                raise ControlEngineError(
                    "Event snapshots are foreign, stale, or non-chronological"
                )
            previous_post = snapshot.post_event_state_json
            previous_route_post = snapshot.post_event_route_state_json
        if previous_post != _canonical_json(self._state.snapshot()):
            raise ControlEngineError("Final state does not match the closed event stream")
        if previous_route_post != self._area_route_state_json():
            raise ControlEngineError(
                "Final area-route state does not match the closed event stream"
            )

    def _validate_reliability(self, value: ReliabilityResult) -> None:
        try:
            validate_reliability_result(
                self._program,
                value,
                expected_scenario_digest=self._reliability_digest,
                expected_issuance_token=self._reliability_token,
            )
        except (ControlGraphError, TypeError) as error:
            raise ControlEngineError(
                f"Reliability result is foreign, stale, or malformed: {error}"
            ) from error

    def _validate_concentration_lifecycle(self) -> None:
        tracker = self._concentration_tracker
        start_records = tuple(
            record
            for record in self._issued_records
            if record.record_kind == "concentration_start"
        )
        if not self._concentration_required:
            if tracker is not None or start_records:
                raise ControlEngineError(
                    "Non-concentration scenario contains a concentration lifecycle"
                )
            return
        if tracker is None:
            raise ControlEngineError(
                "Concentration scenario has no bound lifecycle tracker"
            )
        if (
            tracker.owner_actor_id != self._source_actor_id
            or any(
                record.get("owner_actor_id") != tracker.owner_actor_id
                for record in tracker.records
            )
        ):
            raise ControlEngineError(
                "Concentration tracker records do not preserve the exact owner"
            )
        if (
            len(start_records) != 1
            or start_records[0].event_id != self._concentration_start_event_id
        ):
            raise ControlEngineError(
                "Concentration scenario must execute exactly one attested startup"
            )
        active_concentration_components = tuple(
            component
            for target_id in self._schedule.target_ids
            for component in self._state.active_components(target_id)
            if component.effect_id == self._program.effect_id
            and self._program.component(component.component_id).duration.get("kind")
            == "concentration"
        )
        if active_concentration_components and (
            tracker.active_effect_id != self._program.effect_id
        ):
            raise ControlEngineError(
                "Active concentration-duration state has no matching lifecycle"
            )
        if tracker.active_effect_id not in {None, self._program.effect_id}:
            raise ControlEngineError(
                "Concentration tracker contains a foreign active effect"
            )
        if tracker.active_effect_id == self._program.effect_id:
            try:
                self._engine._active_concentration_context(
                    tracker=tracker,
                    effect=self._program,
                    schedule=self._schedule,
                    selector_membership=self._membership,
                    selector_context=self._selector_context,
                    invocation_id=self._invocation_id,
                    source_actor_id=self._source_actor_id,
                    choices=self._choices,
                )
            except ControlEngineError as error:
                raise ControlEngineError(
                    "Active concentration lifecycle has stale authority context"
                ) from error
        if (
            self._pending_concentration_failure is not None
            or self._pending_concentration_failure_original is not None
            or self._pending_concentration_failure_attestation is not None
        ):
            raise ControlEngineError(
                "Final concentration lifecycle retains a pending failed check"
            )

        pending_records = tuple(
            record
            for record in self._issued_records
            if record.record_kind == "concentration_check_pending_end"
        )
        failed_end_records: list[_IssuedControlRecord] = []
        for record in self._issued_records:
            if record.record_kind != "concentration_end":
                continue
            payload = json.loads(record.payload_json)
            if (
                payload.get("kind") == "concentration_end"
                and payload.get("reason") == "failed_concentration_save"
            ):
                raise ControlEngineError(
                    "A failed concentration end has no matching pending check"
                )
            check_record = payload.get("check_record")
            if (
                payload.get("kind") == "concentration_check_lifecycle"
                and isinstance(check_record, Mapping)
                and check_record.get("outcome") == "failure"
            ):
                failed_end_records.append(record)
        if len(pending_records) != len(failed_end_records):
            raise ControlEngineError(
                "Failed concentration checks and typed ends are not one-to-one"
            )

        matched_end_operations: set[int] = set()
        final_tracker_state: Mapping[str, Any] | None = None
        for pending_record in pending_records:
            pending = self._validated_pending_concentration_failure_payload(
                pending_record
            )
            check_record = pending["check_record"]
            tracker_end_record = pending["tracker_end_record"]
            matches = [
                record
                for record in failed_end_records
                if record.event_id == pending["end_event_id"]
                and json.loads(record.payload_json).get("check_record")
                == check_record
            ]
            if len(matches) != 1:
                raise ControlEngineError(
                    "A failed concentration check does not have exactly one "
                    "matching typed end"
                )
            end_record = matches[0]
            if (
                end_record.operation_sequence in matched_end_operations
                or end_record.operation_sequence
                <= pending_record.operation_sequence
                or end_record.event_sequence != pending["end_event_sequence"]
                or end_record.event_sequence
                != pending_record.event_sequence + 1
            ):
                raise ControlEngineError(
                    "Failed concentration check/end chronology is duplicated or stale"
                )
            matched_end_operations.add(end_record.operation_sequence)
            lifecycle = json.loads(end_record.payload_json)
            if (
                set(lifecycle) != {
                    "kind",
                    "check_record",
                    "tracker_records",
                    "applied_end_transitions",
                    "active_effect_id",
                    "active_components_after",
                }
                or lifecycle["tracker_records"]
                != [check_record, tracker_end_record]
                or lifecycle["active_effect_id"] is not None
                or not isinstance(lifecycle["applied_end_transitions"], list)
                or len(lifecycle["applied_end_transitions"]) != 1
            ):
                raise ControlEngineError(
                    "Failed concentration check/end tracker lifecycle is malformed"
                )

            check_state_rows = json.loads(
                pending_record.post_operation_state_json
            )
            check_route_rows = json.loads(
                pending_record.post_operation_route_state_json
            )
            program_check_rows = [
                row for row in check_state_rows
                if row.get("effect_id") == self._program.effect_id
            ]
            program_end_pre_rows = [
                row for row in json.loads(end_record.pre_operation_state_json)
                if row.get("effect_id") == self._program.effect_id
            ]
            program_check_routes = [
                row for row in check_route_rows
                if row.get("effect_id") == self._program.effect_id
            ]
            program_end_pre_routes = [
                row
                for row in json.loads(end_record.pre_operation_route_state_json)
                if row.get("effect_id") == self._program.effect_id
            ]
            if (
                program_check_rows != program_end_pre_rows
                or program_check_routes != program_end_pre_routes
                or end_record.pre_operation_route_state_json
                != end_record.post_operation_route_state_json
            ):
                raise ControlEngineError(
                    "Concentration component or route state ended before the "
                    "typed concentration-end event"
                )

            context = self._engine._build_concentration_context(
                effect=self._program,
                schedule=self._schedule,
                selector_membership=self._membership,
                selector_context=self._selector_context,
                invocation_id=self._invocation_id,
                source_actor_id=self._source_actor_id,
                start_event_id=str(self._concentration_start_event_id),
                choices=self._choices,
            )
            end_event = self._schedule.event(str(pending["end_event_id"]))
            active_ids_by_target = {
                target_id: {
                    row["component_id"]
                    for row in program_check_rows
                    if row.get("target_id") == target_id
                }
                for target_id in self._schedule.target_ids
            }
            expected_plan: list[dict[str, str]] = []
            planned_targets: set[str] = set()
            for gate_id in context.concentration_end_gate_ids:
                gate = context.program.gate(gate_id)
                branch = gate.branches[0]
                for target_id in context.schedule.target_ids:
                    if not any(
                        target_id in context.selector_membership[selector_id]
                        for selector_id in gate.selector_ids
                    ):
                        continue
                    if not set(gate.requires_active_component_ids).issubset(
                        active_ids_by_target[target_id]
                    ):
                        continue
                    if target_id in planned_targets or (
                        end_event.target_id is not None
                        and end_event.target_id != target_id
                    ) or not typed_event_matches(
                        end_event,
                        gate.trigger.data.to_dict(),
                        target_id=target_id,
                        triggering_turn_id=end_event.turn_id,
                    ):
                        raise ControlEngineError(
                            "Final concentration end plan does not match compiled authority"
                        )
                    self._engine._gate_reachability(
                        state=self._state,
                        program=context.program,
                        gate_id=gate.gate_id,
                        target_id=target_id,
                        invocation_id=context.invocation_id,
                        event_id=end_event.event_id,
                        schedule=context.schedule,
                    )
                    planned_targets.add(target_id)
                    expected_plan.append({
                        "gate_id": gate.gate_id,
                        "target_id": target_id,
                        "outcome": branch.outcome,
                    })
            if expected_plan != pending["compiled_end_plan"]:
                raise ControlEngineError(
                    "Final pending end plan differs from compiled authority"
                )
            derived_affected_targets = sorted({
                row["target_id"]
                for row in program_check_rows
                if row.get("component_id") in (
                    set(pending["authority_metadata"][
                        "concentration_component_ids"
                    ])
                    | set(pending["authority_metadata"]["area_component_ids"])
                )
            } | {
                row["target_id"]
                for row in program_check_routes
                if row.get("membership") is True
                and row.get("area_id")
                in pending["authority_metadata"]["area_ids"]
            } | {
                row["target_id"] for row in expected_plan
            })
            if derived_affected_targets != pending["affected_target_ids"]:
                raise ControlEngineError(
                    "Final pending affected targets differ from attested state"
                )

            [applied_end] = lifecycle["applied_end_transitions"]
            if (
                not isinstance(applied_end, Mapping)
                or applied_end.get("event_id") != end_record.event_id
                or applied_end.get("reason") != "failed_concentration_save"
                or applied_end.get("authority_metadata")
                != pending["authority_metadata"]
            ):
                raise ControlEngineError(
                    "Final failed concentration transition is stale"
                )
            actual_plan = [
                {
                    "gate_id": transition.get("gate_id"),
                    "target_id": transition.get("target_id"),
                    "outcome": transition.get("filtered_branch", {}).get(
                        "outcome"
                    ),
                }
                for transition in applied_end.get(
                    "concentration_end_gate_transitions",
                    (),
                )
                if isinstance(transition, Mapping)
            ]
            if actual_plan != expected_plan:
                raise ControlEngineError(
                    "Executed concentration-end gates differ from compiled plan"
                )
            for planned in expected_plan:
                matching_audits = [
                    row for row in self._state.audit_ledger
                    if row.get("operation") == "branch_transition"
                    and row.get("event_id") == end_record.event_id
                    and row.get("gate_id") == planned["gate_id"]
                    and row.get("target_id") == planned["target_id"]
                    and row.get("filtered_branch", {}).get("outcome")
                    == planned["outcome"]
                ]
                if len(matching_audits) != 1:
                    raise ControlEngineError(
                        "Compiled concentration-end gate did not execute exactly once"
                    )

            cleanup_ids = set(
                pending["authority_metadata"]["concentration_component_ids"]
            ) | set(pending["authority_metadata"]["area_component_ids"])
            program_end_post_rows = [
                row for row in json.loads(end_record.post_operation_state_json)
                if row.get("effect_id") == self._program.effect_id
            ]
            if any(
                row.get("component_id") in cleanup_ids
                for row in program_end_post_rows
            ):
                raise ControlEngineError(
                    "Concentration or area-bound component survived its typed end"
                )
            pre_instances = {
                row["instance_id"]: row for row in program_end_pre_rows
            }
            post_instance_ids = {
                row["instance_id"] for row in program_end_post_rows
            }
            expected_ended_instances = [
                {
                    "target_id": row["target_id"],
                    "component_id": row["component_id"],
                    "instance_id": instance_id,
                }
                for instance_id, row in sorted(pre_instances.items())
                if instance_id not in post_instance_ids
            ]
            if applied_end.get("ended_state_instances") != expected_ended_instances:
                raise ControlEngineError(
                    "Typed concentration end instance termination does not replay"
                )

            expected_route_identities = {
                (
                    row["effect_id"],
                    row["area_id"],
                    row["target_id"],
                )
                for row in program_end_pre_routes
                if row.get("membership") is True
            }
            observed_route_identities = set()
            for route_record in self._issued_records:
                if (
                    route_record.record_kind != "area_route_transition"
                    or route_record.event_id != end_record.event_id
                    or route_record.operation_sequence
                    <= end_record.operation_sequence
                ):
                    continue
                route_payload = json.loads(route_record.payload_json)
                transition = route_payload.get("route_transition", {})
                if transition.get("transition_kind") != "effect_end":
                    continue
                identity = (
                    transition.get("effect_id"),
                    transition.get("area_id"),
                    transition.get("target_id"),
                )
                if (
                    identity in observed_route_identities
                    or transition.get("old_route_state", {}).get("membership")
                    is not True
                    or transition.get("new_route_state", {}).get("membership")
                    is not False
                ):
                    raise ControlEngineError(
                        "Typed concentration-end route closure is duplicated or stale"
                    )
                observed_route_identities.add(identity)
            if observed_route_identities != expected_route_identities:
                raise ControlEngineError(
                    "Typed concentration end did not close every live area route"
                )

            tracker_post = deepcopy(pending["tracker_post_check_state"])
            tracker_post["active_effect_id"] = None
            tracker_post["active_metadata"] = {}
            tracker_post["records"] = [
                *tracker_post["records"],
                tracker_end_record,
            ]
            if final_tracker_state is not None:
                raise ControlEngineError(
                    "Final execution contains duplicate failed concentration lifecycles"
                )
            final_tracker_state = tracker_post
        if (
            final_tracker_state is not None
            and json.loads(self._concentration_tracker_state_json(tracker))
            != final_tracker_state
        ):
            raise ControlEngineError(
                "Final concentration tracker does not continue the failed-check chain"
            )

    def _validate_scenario_identity(self) -> None:
        if hashlib.sha256(self._scenario_json.encode("utf-8")).hexdigest() != (
            self._scenario_digest
        ):
            raise ControlEngineError("Session scenario digest is stale or malformed")
        scenario = json.loads(self._scenario_json)
        current_versions = self._engine.version_provenance(
            initiative_convention=self._schedule.convention,
            area_response_convention=self._area_response_convention,
            displacement_function_id=self._displacement_function_id,
        ).to_dict()
        scenario_membership = scenario.get("selector_membership", {})
        compiled_area_ids = {
            selector.area.area_id
            for selector in self._program.selectors
            if selector.area is not None
        }
        expected_area_target_ids_by_area = {
            area_id: sorted({
                target_id
                for selector in self._program.selectors
                if selector.area is not None
                and selector.area.area_id == area_id
                for target_id in scenario_membership[selector.selector_id]
            })
            for area_id in compiled_area_ids
        }
        expected_persistent_area_ids = sorted({
            selector.area.area_id
            for selector in self._program.selectors
            if selector.area is not None and selector.area.persistent
        })
        if (
            scenario.get("session_contract") != "control_execution_session_v2"
            or _canonical_json(scenario.get("target_mechanics"))
            != self._target_mechanics_json
            or _canonical_json(scenario_membership)
            != _canonical_json({
                selector_id: sorted(target_ids)
                for selector_id, target_ids in sorted(self._membership.items())
            })
            or _canonical_json(scenario_membership)
            != _canonical_json(
                self._reliability.scenario.canonical_record().get(
                    "selector_membership"
                )
            )
            or _canonical_json(scenario.get("initial_state"))
            != self._initial_state_json
            or _canonical_json(scenario.get("initial_condition_registry"))
            != self._initial_condition_registry_json
            or _canonical_json(scenario.get("operation_inputs_by_event"))
            != self._operation_inputs_json
            or _canonical_json(scenario.get("initial_area_route_states"))
            != self._initial_area_route_state_json
            or _canonical_json(scenario.get("area_geometry_updates"))
            != self._area_geometry_updates_json
            or _canonical_json([
                update.to_dict() for update in self._area_geometry_updates.values()
            ]) != self._area_geometry_updates_json
            or _canonical_json(scenario.get("area_entry_transitions"))
            != self._area_entry_transitions_json
            or _canonical_json([
                transition.to_dict()
                for transition in self._area_entry_transitions.values()
            ]) != self._area_entry_transitions_json
            or any(
                key != (transition.event_id, transition.target_id)
                for key, transition in self._area_entry_transitions.items()
            )
            or _canonical_json(scenario.get("area_gate_bindings"))
            != self._area_gate_bindings_json
            or _canonical_json({
                gate_id: list(area_ids)
                for gate_id, area_ids in sorted(
                    self._area_gate_bindings.items()
                )
            }) != self._area_gate_bindings_json
            or _canonical_json({
                gate_id: list(area_ids)
                for gate_id, area_ids in sorted(
                    self._compiled_area_gate_bindings(
                        self._program,
                        self._engine._compiled_area_bindings(self._program),
                    ).items()
                )
            }) != self._area_gate_bindings_json
            or _canonical_json(scenario.get("area_target_ids_by_area"))
            != self._area_target_ids_by_area_json
            or _canonical_json({
                area_id: list(target_ids)
                for area_id, target_ids in sorted(
                    self._area_target_ids_by_area.items()
                )
            }) != self._area_target_ids_by_area_json
            or _canonical_json(expected_area_target_ids_by_area)
            != self._area_target_ids_by_area_json
            or _canonical_json(scenario.get("persistent_area_ids"))
            != self._persistent_area_ids_json
            or _canonical_json(sorted(self._persistent_area_ids))
            != self._persistent_area_ids_json
            or _canonical_json(expected_persistent_area_ids)
            != self._persistent_area_ids_json
            or _canonical_json(scenario.get("required_operation_plan"))
            != self._required_operation_plan_json
            or _canonical_json(scenario.get("reliability_timeline_bindings"))
            != self._reliability_timeline_bindings_json
            or scenario.get("reliability_scenario_digest")
            != self._reliability_digest
            or _canonical_json(scenario.get("timeline_schedule"))
            != self._schedule_json
            or _canonical_json(_strict_json_copy(
                self._schedule.to_dict(),
                "timeline_schedule",
            )) != self._schedule_json
            or scenario.get("compiled_program", {}).get("effect_id")
            != self._program.effect_id
            or scenario.get("concentration_lifecycle")
            != {
                "required": self._concentration_required,
                "start_event_id": self._concentration_start_event_id,
                "startup": self._program.concentration.get("startup"),
            }
            or scenario.get("concentration_save_bonus")
            != (
                self._concentration_tracker.save_bonus
                if self._concentration_tracker is not None else None
            )
            or scenario.get("versions") != current_versions
            or self._engine.program(self._program.effect_id) != self._program
        ):
            raise ControlEngineError(
                "Session runtime bindings no longer match its canonical scenario"
            )

    def _validate_ambient_membership_history(self) -> None:
        """Replay typed activation filtering against issued route snapshots."""

        self._validate_ambient_membership_state()
        branch_records = {
            (record.event_id, record.target_id, json.loads(record.payload_json).get(
                "gate_id"
            )): record
            for record in self._issued_records
            if record.record_kind == "branch_transition"
        }
        observed: set[tuple[str, str, str]] = set()
        for transition in self._event_state_transitions:
            event_id = transition.get("event_id")
            target_id = transition.get("target_id")
            gate_id = transition.get("gate_id")
            branch_id = transition.get("branch_id")
            if not all(
                isinstance(value, str)
                for value in (event_id, target_id, gate_id, branch_id)
            ):
                raise ControlEngineError(
                    "Branch transition lacks canonical ambient replay identity"
                )
            event = self._schedule.event(event_id)
            gate = self._program.gate(gate_id)
            branch = next((
                candidate for candidate in gate.branches
                if candidate.branch_id == branch_id
            ), None)
            record = branch_records.get((event_id, target_id, gate_id))
            if branch is None or record is None:
                raise ControlEngineError(
                    "Branch transition lacks its issued compiled branch"
                )
            route_rows = json.loads(record.pre_operation_route_state_json)
            expected_suppressions = list(
                self._outside_membership_ambient_suppressions_from_routes(
                    gate=gate,
                    branch=branch,
                    target_id=target_id,
                    event=event,
                    route_rows=route_rows,
                )
            )
            suppressions = transition.get(
                "outside_compiled_area_membership_suppressions",
                _MISSING,
            )
            if not isinstance(suppressions, Sequence) or isinstance(
                suppressions,
                (str, bytes),
            ) or list(suppressions) != expected_suppressions:
                raise ControlEngineError(
                    "Ambient membership suppression coverage does not replay"
                )
            filtered_applies = set(
                transition.get("filtered_branch", {}).get("applies", ())
            )
            active_after = {
                item.get("component_id")
                for item in transition.get("active_components_after", ())
                if item.get("effect_id") == self._program.effect_id
                and item.get("target_id") == target_id
            }
            for area_id in sorted(self._persistent_area_ids):
                ambient_applications = sorted(
                    set(branch.applies)
                    & set(self._ambient_area_component_ids(
                        area_id=area_id,
                        target_id=target_id,
                    ))
                )
                if not ambient_applications:
                    continue
                route_matches = [
                    row for row in route_rows
                    if row.get("effect_id") == self._program.effect_id
                    and row.get("area_id") == area_id
                    and row.get("target_id") == target_id
                ]
                if len(route_matches) != 1:
                    raise ControlEngineError(
                        "Ambient branch replay lacks authoritative route state"
                    )
                member = route_matches[0].get("membership")
                for component_id in ambient_applications:
                    canonically_suppressed = (
                        self._ambient_component_canonically_suppressed(
                            component_id=component_id,
                            target_id=target_id,
                        )
                    )
                    if (
                        member is False
                        and component_id in filtered_applies
                    ) or (
                        member is True
                        and component_id not in filtered_applies
                    ) or (
                        member is True
                        and not canonically_suppressed
                        and component_id not in active_after
                    ) or (
                        member is True
                        and canonically_suppressed
                        and component_id in active_after
                    ):
                        raise ControlEngineError(
                            "Ambient member/nonmember branch application does not replay"
                        )
            for row in suppressions:
                expected_keys = {
                    "kind",
                    "effect_id",
                    "area_id",
                    "target_id",
                    "source_gate_id",
                    "source_branch_id",
                    "component_id",
                    "authoritative_membership",
                    "event_id",
                    "event_sequence",
                }
                if not isinstance(row, Mapping) or set(row) != expected_keys:
                    raise ControlEngineError(
                        "Ambient membership suppression is malformed"
                    )
                event = self._schedule.event(str(row["event_id"]))
                gate = self._program.gate(str(row["source_gate_id"]))
                branch = next((
                    candidate for candidate in gate.branches
                    if candidate.branch_id == row["source_branch_id"]
                ), None)
                identity = (
                    str(row["event_id"]),
                    str(row["target_id"]),
                    str(row["component_id"]),
                )
                record = branch_records.get((
                    str(row["event_id"]),
                    str(row["target_id"]),
                    str(row["source_gate_id"]),
                ))
                route_rows = (
                    [] if record is None else json.loads(
                        record.pre_operation_route_state_json
                    )
                )
                route_matches = [
                    route for route in route_rows
                    if route.get("effect_id") == row["effect_id"]
                    and route.get("area_id") == row["area_id"]
                    and route.get("target_id") == row["target_id"]
                ]
                active_after = {
                    item.get("component_id")
                    for item in transition.get("active_components_after", ())
                    if item.get("effect_id") == self._program.effect_id
                    and item.get("target_id") == row["target_id"]
                }
                if (
                    identity in observed
                    or row["kind"] != "outside_compiled_area_membership"
                    or row["effect_id"] != self._program.effect_id
                    or event.sequence != row["event_sequence"]
                    or event.event_id != transition.get("event_id")
                    or gate.trigger.kind != "activation"
                    or gate.gate_id != transition.get("gate_id")
                    or branch is None
                    or branch.branch_id != transition.get("branch_id")
                    or row["component_id"] not in branch.applies
                    or row["component_id"] not in self._ambient_area_component_ids(
                        area_id=str(row["area_id"]),
                        target_id=str(row["target_id"]),
                    )
                    or row["authoritative_membership"] is not False
                    or len(route_matches) != 1
                    or route_matches[0].get("membership") is not False
                    or row["component_id"] in transition.get(
                        "filtered_branch",
                        {},
                    ).get("applies", ())
                    or row["component_id"] in active_after
                ):
                    raise ControlEngineError(
                        "Ambient membership suppression does not replay"
                    )
                observed.add(identity)

    def _route_membership_for_reliability_window(
        self,
        *,
        area_id: str,
        target_id: str,
        window_id: str,
    ) -> bool:
        if window_id == "initial":
            route_rows = json.loads(self._initial_area_route_state_json)
        else:
            scenario = self._reliability.scenario
            if scenario is None:  # pragma: no cover - validated session identity
                return False
            reliability_event = next((
                event
                for event in scenario.event_script
                if (event.window_id or event.event_id) == window_id
            ), None)
            binding = json.loads(self._reliability_timeline_bindings_json)
            schedule_event_id = (
                None
                if reliability_event is None
                else binding.get(reliability_event.event_id)
            )
            if schedule_event_id is None and any(
                event.event_id == window_id for event in self._schedule.events
            ):
                schedule_event_id = window_id
            snapshot = next((
                row for row in self._event_snapshots
                if row.event_id == schedule_event_id
            ), None)
            if snapshot is None:
                return False
            route_rows = json.loads(snapshot.post_event_route_state_json)
        matches = [
            row for row in route_rows
            if row.get("effect_id") == self._program.effect_id
            and row.get("area_id") == area_id
            and row.get("target_id") == target_id
        ]
        if len(matches) != 1:
            return False
        return matches[0].get("membership") is True

    def _component_active_for_reliability_window(
        self,
        *,
        component_id: str,
        target_id: str,
        window_id: str,
    ) -> bool:
        if window_id == "initial":
            state_rows = json.loads(self._initial_state_json)
        else:
            scenario = self._reliability.scenario
            if scenario is None:  # pragma: no cover - validated session identity
                return False
            reliability_event = next((
                event
                for event in scenario.event_script
                if (event.window_id or event.event_id) == window_id
            ), None)
            binding = json.loads(self._reliability_timeline_bindings_json)
            schedule_event_id = (
                None
                if reliability_event is None
                else binding.get(reliability_event.event_id)
            )
            if schedule_event_id is None and any(
                event.event_id == window_id for event in self._schedule.events
            ):
                schedule_event_id = window_id
            snapshot = next((
                row for row in self._event_snapshots
                if row.event_id == schedule_event_id
            ), None)
            if snapshot is None:
                return False
            state_rows = json.loads(snapshot.post_event_state_json)
        return any(
            row.get("effect_id") == self._program.effect_id
            and row.get("target_id") == target_id
            and row.get("component_id") == component_id
            for row in state_rows
        )

    def _membership_scoped_component_reliability(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        scoped: list[dict[str, Any]] = []
        bindings = self._engine._compiled_area_bindings(self._program)
        zero = _fraction_record(Fraction())
        initial_window_ids = {
            event.window_id or event.event_id
            for event in self._reliability.scenario.event_script[
                :self._reliability.scenario.initial_event_count
            ]
        }
        for source in rows:
            row = dict(_json_safe(source))
            component_id = str(row["component_id"])
            target_id = str(row["target_id"])
            ambient_area_ids = [
                area_id
                for area_id in bindings.get(component_id, ())
                if component_id in self._ambient_area_component_ids(
                    area_id=area_id,
                    target_id=target_id,
                )
            ]
            if len(ambient_area_ids) != 1:
                scoped.append(row)
                continue
            area_id = ambient_area_ids[0]
            corrected_windows: list[dict[str, Any]] = []
            for window in row.get("active_by_window", ()):
                window_copy = dict(window)
                if not self._route_membership_for_reliability_window(
                    area_id=area_id,
                    target_id=target_id,
                    window_id=str(window_copy["window_id"]),
                ) or not self._component_active_for_reliability_window(
                    component_id=component_id,
                    target_id=target_id,
                    window_id=str(window_copy["window_id"]),
                ):
                    window_copy["probability"] = dict(zero)
                corrected_windows.append(window_copy)
            initially_active = any(
                self._component_active_for_reliability_window(
                    component_id=component_id,
                    target_id=target_id,
                    window_id=window_id,
                )
                for window_id in initial_window_ids
            )
            ever_realized = any(
                any(
                    item.get("effect_id") == self._program.effect_id
                    and item.get("target_id") == target_id
                    and item.get("component_id") == component_id
                    for item in (
                        *json.loads(snapshot.pre_event_state_json),
                        *json.loads(snapshot.post_event_state_json),
                    )
                )
                for snapshot in self._event_snapshots
            )
            if not initially_active:
                row["initially_applied"] = dict(zero)
            if not ever_realized:
                row["ever_applied"] = dict(zero)
            row["active_by_window"] = corrected_windows
            corrected_ever = Fraction(
                int(row["ever_applied"]["numerator"]),
                int(row["ever_applied"]["denominator"]),
            )
            if any(
                Fraction(
                    int(window["probability"]["numerator"]),
                    int(window["probability"]["denominator"]),
                ) > corrected_ever
                for window in corrected_windows
            ):
                raise ControlEngineError(
                    "Membership-scoped active component probability exceeds "
                    "membership-scoped ever-applied probability"
                )
            row["activity_interpretation"] = (
                "membership_scoped_realized_target_activity"
            )
            scoped.append(row)
        return tuple(scoped)

    def _assemble_for_test(
        self,
        *,
        records: Sequence[_IssuedControlRecord] | None = None,
        reliability: ReliabilityResult | None = None,
    ) -> ControlEngineResult:
        """Private integrity seam used by negative tests; never a facade API."""

        if self._current_event is not None:
            raise ControlEngineError("The current event must be closed before result()")
        self._validate_scenario_identity()
        self._validate_event_snapshots()
        selected_records = tuple(
            self._issued_records if records is None else records
        )
        self._validate_issued_records(selected_records)
        self._validate_condition_lifecycle()
        self._validate_condition_execution_replay()
        self._validate_internal_ledgers()
        self._validate_area_entry_history()
        self._validate_area_gate_execution()
        self._validate_ambient_membership_history()
        selected_reliability = self._reliability if reliability is None else reliability
        self._validate_reliability(selected_reliability)
        self._validate_concentration_lifecycle()
        base = self._engine._assemble_result_legacy(
            effect=self._program,
            reliability=selected_reliability,
            schedule=self._schedule,
            area_response_convention=self._area_response_convention,
            displacement_function_id=self._displacement_function_id,
            state=self._state,
            normalization_results=self._normalization_results,
            event_state_transitions=self._event_state_transitions,
            repeat_save_records=self._repeat_save_records,
            area_records=self._area_records,
            prone_records=self._prone_records,
            concentration_records=self._concentration_records,
            displacement_records=self._displacement_records,
        )
        ambient_suppressions = tuple(
            dict(row)
            for transition in self._event_state_transitions
            for row in transition.get(
                "outside_compiled_area_membership_suppressions",
                (),
            )
        )
        return _replace_control_engine_result(
            base,
            component_reliability=(
                self._membership_scoped_component_reliability(
                    base.component_reliability
                )
            ),
            any_candidate_reliability={
                **dict(_json_safe(base.any_candidate_reliability)),
                "activity_interpretation": (
                    "structural_gate_application_potential_unscoped_to_"
                    "runtime_membership"
                ),
            },
            any_component_reliability={
                **dict(_json_safe(base.any_component_reliability)),
                "activity_interpretation": (
                    "structural_gate_application_potential_unscoped_to_"
                    "runtime_membership"
                ),
            },
            suppression_and_dominance_records=(
                *base.suppression_and_dominance_records,
                *ambient_suppressions,
            ),
            scenario_digest=self._scenario_digest,
            scenario_record=json.loads(self._scenario_json),
            execution_records=tuple(record.to_dict() for record in selected_records),
            event_snapshots=tuple(
                snapshot.to_dict() for snapshot in self._event_snapshots
            ),
            area_route_transitions=tuple(self._area_route_transitions),
            final_area_route_states=tuple(
                self._area_route_state_rows(public=True)
            ),
            condition_instance_registry=tuple(
                self._state.instance_registry()
            ),
            condition_lifecycle_records=tuple(
                self._state.condition_lifecycle_records()
            ),
            inclusion_lineage_records=tuple(
                self._state.lineage_records()
            ),
            prone_operation_records=tuple(self._prone_records),
            opportunity_roll_records=tuple(
                self._opportunity_roll_records
            ),
            source_relative_legality_records=tuple(
                self._source_relative_legality_records
            ),
            condition_concentration_records=tuple(
                self._condition_concentration_records
            ),
            fall_transition_records=tuple(
                self._fall_transition_records
            ),
        )

    def result(self) -> ControlEngineResult:
        """Issue the deterministic final result after complete closed execution."""

        self._validate_scenario_identity()
        self._validate_ambient_membership_state()
        if self._cached_result is None:
            self._cached_result = self._assemble_for_test()
        return self._cached_result


def validate_fixture_corpus(
    path: str | Path = DEFAULT_FIXTURE_CORPUS,
) -> dict[str, Any]:
    """Validate the compact 72-case reviewed fixture contract and variants."""

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
    if not isinstance(cases, list) or len(cases) != 72:
        raise ControlEngineError(
            "Fixture corpus must contain exactly 72 reviewed cases"
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
                "Fixture case IDs must be exact sequential integers 1 through 72"
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
    if len(engine.catalog.conditions) != 7 or len(PRIMITIVE_CONTRACT) != 24:
        raise ControlEngineError(
            "Catalog scope must remain seven conditions and 24 primitives"
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
    smoke_program = engine.program("absolute_zero_t0_control")
    smoke_schedule = engine.schedule(
        "fighter_first_v1",
        ["validation_target"],
        controller_events_by_round={
            1: [{"kind": "save_opportunity", "target_id": "validation_target"}],
        },
        target_attack_counts={"validation_target": 0},
    )
    smoke_session = engine.execution_session(
        smoke_program,
        targets=(
            ReliabilityTarget(
                "validation_target",
                15,
                {"constitution": 2},
            ),
        ),
        selector_membership={
            smoke_program.selectors[0].selector_id: ("validation_target",),
        },
        selector_context=SelectorContext(),
        schedule=smoke_schedule,
        target_mechanics={"validation_target": {}},
        area_response_convention="fixed_occupancy_v1",
        displacement_function_id="sqrt_5ft_v1",
        probability_context=ProbabilityContext(save_dc=15),
    )
    smoke_gate_event = next(
        event
        for event in smoke_schedule.events
        if event.kind == "save_opportunity"
    )
    smoke_session.advance_to(smoke_gate_event.event_id)
    smoke_session.resolve_save_opportunity(
        actor_id="validation_target",
        ability="constitution",
    )
    smoke_session.apply_branch(
        gate_id="absolute_zero_t0_save",
        outcome="save_success",
        target_id="validation_target",
    )
    smoke_session.close_event()
    smoke_session.complete()
    smoke_result = smoke_session.result()
    if (
        smoke_result.scenario_digest != smoke_session.scenario_digest
        or len(smoke_result.event_snapshots) != len(smoke_schedule.events)
    ):
        raise ControlEngineError(
            "Execution-session smoke result did not preserve scenario chronology"
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
    "AreaEntryTransition",
    "AreaGeometryUpdate",
    "AreaRouteGeometry",
    "ControlEngine",
    "ControlEngineError",
    "ControlEngineResult",
    "ControlExecutionSession",
    "DisplacementRequest",
    "ENGINE_VERSION",
    "ScenarioConvention",
    "VersionProvenance",
    "main",
    "reliability_result_to_dict",
    "validate_engine",
    "validate_fixture_corpus",
]
