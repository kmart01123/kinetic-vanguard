"""Versioned SRD control consequences, primitive contracts, and sense queries."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_CONTROL_CATALOG = HARNESS_ROOT / "data" / "srd_control_consequences.json"
DEFAULT_CONTROL_PROVENANCE = HARNESS_ROOT / "provenance" / "srd-control-consequences.json"
DEFAULT_ENGINE_CONFIG = HARNESS_ROOT / "config" / "control-engine.json"

CATALOG_VERSION = "1.0.0"
CONSEQUENCE_CATALOG_VERSION = CATALOG_VERSION
PRIMITIVE_CONTRACT_VERSION = "1.0.0"
ENGINE_CONFIG_VERSION = "1.0.0"
NORMALIZATION_RULES_VERSION = "1.0.0"
TIMELINE_ENGINE_VERSION = "1.0.0"

DIAGNOSTIC_FAMILIES = ("denial", "enablement", "retained_unpriced")
PRIMITIVE_STATUSES = ("candidate", "retained_unpriced")
SUPPORTED_NONVISUAL_SENSES = ("blindsight", "tremorsense")

_SNAKE_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CatalogError(ValueError):
    """Raised when catalog or configuration data is not exactly supported."""


class SenseContextError(CatalogError):
    """Raised when a caller requests fail-closed sense resolution without context."""


@dataclass(frozen=True)
class PrimitiveDefinition:
    family: str
    unit: str
    default_status: str
    allowed_statuses: tuple[str, ...]

    def __getitem__(self, key: str) -> Any:
        if key not in {"family", "unit", "default_status", "allowed_statuses"}:
            raise KeyError(key)
        return getattr(self, key)

    def as_dict(self, primitive_id: str | None = None) -> dict[str, Any]:
        value: dict[str, Any] = {
            "family": self.family,
            "unit": self.unit,
            "default_status": self.default_status,
            "allowed_statuses": list(self.allowed_statuses),
        }
        if primitive_id is not None:
            value = {"primitive_id": primitive_id, **value}
        return value


def _primitive(
    family: str,
    unit: str,
    status: str = "candidate",
) -> PrimitiveDefinition:
    return PrimitiveDefinition(family, unit, status, (status,))


PRIMITIVE_CONTRACT: Mapping[str, PrimitiveDefinition] = MappingProxyType(
    {
        "active_turn_denial": _primitive("denial", "target_turn_window"),
        "reaction_denial": _primitive("denial", "reaction_window"),
        "offensive_impairment_next_attack": _primitive("denial", "attack_opportunity_token"),
        "offensive_impairment_all_attacks": _primitive("denial", "affected_target_turn"),
        "target_choice_restriction": _primitive("denial", "affected_target_turn"),
        "sight_option_denial": _primitive("denial", "sight_dependent_opportunity_window"),
        "mobility_loss_feet": _primitive("denial", "feet_unavailable_at_movement_opportunity"),
        "movement_mode_denial": _primitive("denial", "denied_movement_mode_window"),
        "forced_displacement": _primitive("denial", "selected_displacement_function_units"),
        "geometry_sensitive_approach_restriction": _primitive("denial", "contextual_target_turn_window"),
        "defensive_attack_advantage": _primitive("enablement", "relevant_incoming_attack_opportunity"),
        "defense_numerical_reduction": _primitive("enablement", "defense_point_opportunity"),
        "save_disadvantage": _primitive("enablement", "save_opportunity"),
        "save_auto_failure": _primitive("enablement", "save_opportunity"),
        "sight_dependent_opportunity": _primitive(
            "enablement", "relevant_controller_allied_opportunity_window"
        ),
        "ability_check_impairment": _primitive(
            "retained_unpriced", "ability_check_opportunity", "retained_unpriced"
        ),
        "speech_denial": _primitive(
            "retained_unpriced", "communication_opportunity", "retained_unpriced"
        ),
        "social_interaction_advantage": _primitive(
            "retained_unpriced", "social_interaction_check_opportunity", "retained_unpriced"
        ),
        "concentration_break": _primitive(
            "retained_unpriced", "concentration_state_transition", "retained_unpriced"
        ),
        "persistent_elevation": _primitive(
            "retained_unpriced", "elevated_state_window", "retained_unpriced"
        ),
        "fall_transition": _primitive(
            "retained_unpriced", "current_position_transition", "retained_unpriced"
        ),
        "nonsight_location_awareness": _primitive(
            "retained_unpriced", "location_detection_opportunity", "retained_unpriced"
        ),
        "prone_incoming_attack_context": _primitive(
            "retained_unpriced", "incoming_attack_opportunity", "retained_unpriced"
        ),
    }
)

PRIMITIVE_UNITS = tuple(dict.fromkeys(item.unit for item in PRIMITIVE_CONTRACT.values()))

_CONDITION_PAGES = MappingProxyType(
    {
        "blinded": 176,
        "charmed": 177,
        "frightened": 181,
        "incapacitated": 183,
        "prone": 185,
        "restrained": 186,
        "stunned": 188,
    }
)
_CONTEXT_REQUIREMENTS = (
    "alternative_sight_resolution",
    "ability_check_depends_on_sight",
    "source_actor_id",
    "source_in_line_of_sight",
    "movement_is_willing",
    "target_is_concentrating",
    "effective_speed_ft",
    "attacker_distance_ft",
    "target_airborne",
    "hover_or_explicit_fall_prevention",
    "movement_mode_speeds_ft",
)
_CONTEXT_ORDER = {value: index for index, value in enumerate(_CONTEXT_REQUIREMENTS)}

_PREDICATE_RULES: Mapping[str, tuple[str, Any]] = MappingProxyType(
    {
        "ability_check_depends_on_sight": ("bool", None),
        "alternative_sight_available": ("bool", None),
        "source_in_line_of_sight": ("bool", None),
        "movement_is_willing": ("bool", None),
        "target_is_concentrating": ("bool", None),
        "target_is_airborne": ("bool", None),
        "hover_or_explicit_fall_prevention": ("bool", None),
        "attacker_distance_band": ("enum", ("within_5_feet", "farther_than_5_feet")),
    }
)
_PREDICATE_ORDER = {value: index for index, value in enumerate(_PREDICATE_RULES)}

_QUALIFIER_RULES: Mapping[str, tuple[str, Any]] = MappingProxyType(
    {
        "sense_mode": ("enum", ("physical_sight",)),
        "ability_check_effect": ("enum", ("automatic_failure", "disadvantage")),
        "attack_scope": ("enum", ("next_attack", "all_attacks")),
        "restricted_target_relation": ("enum", ("charmer",)),
        "restricted_choice_kinds": ("exact_list", ("attack", "harmful_effect")),
        "social_actor_relation": ("enum", ("charmer",)),
        "movement_relation": ("enum", ("closer_to_source",)),
        "denied_turn_options": ("exact_list", ("action", "bonus_action")),
        "movement_modes": ("exact_list", ("walk", "fly", "swim", "climb", "burrow")),
        "mobility_effect": ("enum", ("speed_zero",)),
        "save_ability": (
            "enum",
            ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"),
        ),
        "incoming_attack_effect": ("enum", ("disadvantage",)),
        "fall_origin": ("enum", ("current_position",)),
    }
)
_ALLOWED_DOMINANCE = frozenset({("save_auto_failure", "save_disadvantage")})

_EXPECTED_RESPONSES: Mapping[str, Mapping[str, tuple[str, ...] | str]] = MappingProxyType(
    {
        "prone_movement_options": MappingProxyType(
            {
                "timing": "each_movement_opportunity",
                "requirements": (),
                "effects": ("crawl_is_remaining_movement_option",),
            }
        ),
        "stand_from_prone": MappingProxyType(
            {
                "timing": "first_legal_movement_opportunity",
                "requirements": ("effective_speed_positive",),
                "effects": (
                    "spend_half_current_speed_rounded_down",
                    "end_prone",
                    "retain_remaining_movement",
                ),
            }
        ),
    }
)
_END_MECHANICS = frozenset({"source_end", "legal_stand"})

_EXPECTED_SOURCE = {
    "ruleset": "D&D SRD 5.2.1",
    "official_pdf_url": "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",
    "official_pdf_sha256": "8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",
    "pages": 364,
}
_EXPECTED_EXTRACTION = {
    "scope": "Blinded, Charmed, Frightened, Incapacitated, Prone, Restrained, and Stunned",
    "representation": "compact_structured_mechanical_facts",
    "copied_paragraphs": False,
    "inference": "none",
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CatalogError(f"{label} must be an array")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing or unknown:
        raise CatalogError(f"{label} keys are invalid; missing={missing}, unknown={unknown}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CatalogError(f"{label} must be a non-empty trimmed string")
    return value


def _snake_id(value: Any, label: str) -> str:
    result = _string(value, label)
    if not _SNAKE_ID.fullmatch(result):
        raise CatalogError(f"{label} must be a stable snake_case ID")
    return result


def _version(value: Any, expected: str, label: str) -> str:
    result = _string(value, label)
    if not _SEMVER.fullmatch(result) or result != expected:
        raise CatalogError(f"{label} must be supported version {expected}")
    return result


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CatalogError(f"{label} must be a positive integer")
    return value


def _unique_strings(value: Any, label: str, allowed: Iterable[str]) -> tuple[str, ...]:
    raw = _array(value, label)
    values = tuple(_snake_id(item, f"{label}[{index}]") for index, item in enumerate(raw))
    if len(values) != len(set(values)):
        raise CatalogError(f"{label} contains a duplicate ID")
    allowed_set = set(allowed)
    unknown = sorted(set(values) - allowed_set)
    if unknown:
        raise CatalogError(f"{label} contains unknown IDs: {unknown}")
    return values


def _canonical_contexts(value: Any, label: str) -> tuple[str, ...]:
    values = _unique_strings(value, label, _CONTEXT_REQUIREMENTS)
    if list(values) != sorted(values, key=_CONTEXT_ORDER.__getitem__):
        raise CatalogError(f"{label} must use canonical context-requirement ordering")
    return values


def _freeze(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple((key, _freeze(item)) for key, item in sorted(value.items()))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _rule_value(value: Any, rule: tuple[str, Any], label: str) -> Any:
    kind, argument = rule
    if kind == "bool":
        if not isinstance(value, bool):
            raise CatalogError(f"{label} must be a boolean")
        return value
    if kind == "enum":
        text = _snake_id(value, label)
        if text not in argument:
            raise CatalogError(f"{label} has unsupported value {text}")
        return text
    if kind == "exact_list":
        values = _unique_strings(value, label, argument)
        if values != argument:
            raise CatalogError(f"{label} must be exactly {list(argument)}")
        return values
    raise AssertionError(f"Unhandled validation rule: {kind}")


@dataclass(frozen=True)
class Predicate:
    predicate_id: str
    value: Any

    def as_dict(self) -> dict[str, Any]:
        return {"predicate_id": self.predicate_id, "value": _thaw(self.value)}


@dataclass(frozen=True)
class Qualifier:
    qualifier_id: str
    value: Any

    def as_dict(self) -> dict[str, Any]:
        return {"qualifier_id": self.qualifier_id, "value": _thaw(self.value)}


@dataclass(frozen=True)
class PrimitiveSpec:
    primitive_id: str
    family: str
    unit: str
    status: str
    predicates: tuple[Predicate, ...]
    qualifiers: tuple[Qualifier, ...]
    context_requirements: tuple[str, ...]
    dominates: tuple[str, ...]
    source_condition_ids: tuple[str, ...]

    @property
    def predicate_values(self) -> Mapping[str, Any]:
        return MappingProxyType({item.predicate_id: item.value for item in self.predicates})

    @property
    def qualifier_values(self) -> Mapping[str, Any]:
        return MappingProxyType({item.qualifier_id: item.value for item in self.qualifiers})

    def signature(self) -> tuple[Any, ...]:
        return (
            self.primitive_id,
            self.family,
            self.unit,
            self.status,
            self.predicates,
            self.qualifiers,
            self.context_requirements,
            self.dominates,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "primitive_id": self.primitive_id,
            "family": self.family,
            "unit": self.unit,
            "status": self.status,
            "predicates": [item.as_dict() for item in self.predicates],
            "qualifiers": [item.as_dict() for item in self.qualifiers],
            "context_requirements": list(self.context_requirements),
            "dominates": list(self.dominates),
            "source_condition_ids": list(self.source_condition_ids),
        }


@dataclass(frozen=True)
class ResponseMechanic:
    response_id: str
    timing: str
    requirements: tuple[str, ...]
    effects: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "response_id": self.response_id,
            "timing": self.timing,
            "requirements": list(self.requirements),
            "effects": list(self.effects),
        }


@dataclass(frozen=True)
class ConditionDefinition:
    condition_id: str
    source_page: int
    includes: tuple[str, ...]
    default_diagnostic_family: str
    response_mechanics: tuple[ResponseMechanic, ...]
    end_mechanics: tuple[str, ...]
    context_requirements: tuple[str, ...]
    primitives: tuple[PrimitiveSpec, ...]


@dataclass(frozen=True)
class ControlCatalog:
    catalog_version: str
    primitive_contract_version: str
    conditions: Mapping[str, ConditionDefinition]
    digest: str

    def expand(self, condition_id: str) -> tuple[PrimitiveSpec, ...]:
        return expand_condition(self, condition_id)


_ResponseSemantics = tuple[str, str, tuple[str, ...], tuple[str, ...]]
_PrimitiveSemantics = tuple[
    str,
    str,
    str,
    str,
    tuple[tuple[str, Any], ...],
    tuple[tuple[str, Any], ...],
    tuple[str, ...],
    tuple[str, ...],
]
_ConditionSemantics = tuple[
    str,
    int,
    tuple[str, ...],
    str,
    tuple[_ResponseSemantics, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[_PrimitiveSemantics, ...],
]


def _condition_semantics(condition: ConditionDefinition) -> _ConditionSemantics:
    return (
        condition.condition_id,
        condition.source_page,
        condition.includes,
        condition.default_diagnostic_family,
        tuple(
            (item.response_id, item.timing, item.requirements, item.effects)
            for item in condition.response_mechanics
        ),
        condition.end_mechanics,
        condition.context_requirements,
        tuple(
            (
                item.primitive_id,
                item.family,
                item.unit,
                item.status,
                tuple((predicate.predicate_id, predicate.value) for predicate in item.predicates),
                tuple((qualifier.qualifier_id, qualifier.value) for qualifier in item.qualifiers),
                item.context_requirements,
                item.dominates,
            )
            for item in condition.primitives
        ),
    )


_EXPECTED_CONDITION_SEMANTICS: Mapping[
    tuple[str, str], tuple[_ConditionSemantics, ...]
] = MappingProxyType(
    {
        ("1.0.0", "1.0.0"): (
            (
                "blinded",
                176,
                (),
                "denial",
                (),
                ("source_end",),
                ("alternative_sight_resolution", "ability_check_depends_on_sight"),
                (
                    (
                        "sight_option_denial",
                        "denial",
                        "sight_dependent_opportunity_window",
                        "candidate",
                        (("alternative_sight_available", False),),
                        (("sense_mode", "physical_sight"),),
                        ("alternative_sight_resolution",),
                        (),
                    ),
                    (
                        "ability_check_impairment",
                        "retained_unpriced",
                        "ability_check_opportunity",
                        "retained_unpriced",
                        (
                            ("ability_check_depends_on_sight", True),
                            ("alternative_sight_available", False),
                        ),
                        (("ability_check_effect", "automatic_failure"),),
                        ("alternative_sight_resolution", "ability_check_depends_on_sight"),
                        (),
                    ),
                    (
                        "offensive_impairment_all_attacks",
                        "denial",
                        "affected_target_turn",
                        "candidate",
                        (("alternative_sight_available", False),),
                        (("attack_scope", "all_attacks"),),
                        ("alternative_sight_resolution",),
                        (),
                    ),
                    (
                        "defensive_attack_advantage",
                        "enablement",
                        "relevant_incoming_attack_opportunity",
                        "candidate",
                        (("alternative_sight_available", False),),
                        (),
                        ("alternative_sight_resolution",),
                        (),
                    ),
                ),
            ),
            (
                "charmed",
                177,
                (),
                "denial",
                (),
                ("source_end",),
                ("source_actor_id",),
                (
                    (
                        "target_choice_restriction",
                        "denial",
                        "affected_target_turn",
                        "candidate",
                        (),
                        (
                            ("restricted_target_relation", "charmer"),
                            ("restricted_choice_kinds", ("attack", "harmful_effect")),
                        ),
                        ("source_actor_id",),
                        (),
                    ),
                    (
                        "social_interaction_advantage",
                        "retained_unpriced",
                        "social_interaction_check_opportunity",
                        "retained_unpriced",
                        (),
                        (("social_actor_relation", "charmer"),),
                        ("source_actor_id",),
                        (),
                    ),
                ),
            ),
            (
                "frightened",
                181,
                (),
                "denial",
                (),
                ("source_end",),
                ("source_actor_id", "source_in_line_of_sight", "movement_is_willing"),
                (
                    (
                        "offensive_impairment_all_attacks",
                        "denial",
                        "affected_target_turn",
                        "candidate",
                        (("source_in_line_of_sight", True),),
                        (("attack_scope", "all_attacks"),),
                        ("source_actor_id", "source_in_line_of_sight"),
                        (),
                    ),
                    (
                        "ability_check_impairment",
                        "retained_unpriced",
                        "ability_check_opportunity",
                        "retained_unpriced",
                        (("source_in_line_of_sight", True),),
                        (("ability_check_effect", "disadvantage"),),
                        ("source_actor_id", "source_in_line_of_sight"),
                        (),
                    ),
                    (
                        "geometry_sensitive_approach_restriction",
                        "denial",
                        "contextual_target_turn_window",
                        "candidate",
                        (("movement_is_willing", True),),
                        (("movement_relation", "closer_to_source"),),
                        ("source_actor_id", "movement_is_willing"),
                        (),
                    ),
                ),
            ),
            (
                "incapacitated",
                183,
                (),
                "denial",
                (),
                ("source_end",),
                (
                    "target_is_concentrating",
                    "target_airborne",
                    "hover_or_explicit_fall_prevention",
                ),
                (
                    (
                        "active_turn_denial",
                        "denial",
                        "target_turn_window",
                        "candidate",
                        (),
                        (("denied_turn_options", ("action", "bonus_action")),),
                        (),
                        (),
                    ),
                    (
                        "reaction_denial",
                        "denial",
                        "reaction_window",
                        "candidate",
                        (),
                        (),
                        (),
                        (),
                    ),
                    (
                        "concentration_break",
                        "retained_unpriced",
                        "concentration_state_transition",
                        "retained_unpriced",
                        (("target_is_concentrating", True),),
                        (),
                        ("target_is_concentrating",),
                        (),
                    ),
                    (
                        "speech_denial",
                        "retained_unpriced",
                        "communication_opportunity",
                        "retained_unpriced",
                        (),
                        (),
                        (),
                        (),
                    ),
                    (
                        "fall_transition",
                        "retained_unpriced",
                        "current_position_transition",
                        "retained_unpriced",
                        (
                            ("target_is_airborne", True),
                            ("hover_or_explicit_fall_prevention", False),
                        ),
                        (("fall_origin", "current_position"),),
                        ("target_airborne", "hover_or_explicit_fall_prevention"),
                        (),
                    ),
                ),
            ),
            (
                "prone",
                185,
                (),
                "denial",
                (
                    (
                        "prone_movement_options",
                        "each_movement_opportunity",
                        (),
                        ("crawl_is_remaining_movement_option",),
                    ),
                    (
                        "stand_from_prone",
                        "first_legal_movement_opportunity",
                        ("effective_speed_positive",),
                        (
                            "spend_half_current_speed_rounded_down",
                            "end_prone",
                            "retain_remaining_movement",
                        ),
                    ),
                ),
                ("legal_stand", "source_end"),
                (
                    "effective_speed_ft",
                    "attacker_distance_ft",
                    "target_airborne",
                    "hover_or_explicit_fall_prevention",
                ),
                (
                    (
                        "offensive_impairment_all_attacks",
                        "denial",
                        "affected_target_turn",
                        "candidate",
                        (),
                        (("attack_scope", "all_attacks"),),
                        (),
                        (),
                    ),
                    (
                        "defensive_attack_advantage",
                        "enablement",
                        "relevant_incoming_attack_opportunity",
                        "candidate",
                        (("attacker_distance_band", "within_5_feet"),),
                        (),
                        ("attacker_distance_ft",),
                        (),
                    ),
                    (
                        "prone_incoming_attack_context",
                        "retained_unpriced",
                        "incoming_attack_opportunity",
                        "retained_unpriced",
                        (("attacker_distance_band", "farther_than_5_feet"),),
                        (("incoming_attack_effect", "disadvantage"),),
                        ("attacker_distance_ft",),
                        (),
                    ),
                    (
                        "fall_transition",
                        "retained_unpriced",
                        "current_position_transition",
                        "retained_unpriced",
                        (
                            ("target_is_airborne", True),
                            ("hover_or_explicit_fall_prevention", False),
                        ),
                        (("fall_origin", "current_position"),),
                        ("target_airborne", "hover_or_explicit_fall_prevention"),
                        (),
                    ),
                ),
            ),
            (
                "restrained",
                186,
                (),
                "denial",
                (),
                ("source_end",),
                ("movement_mode_speeds_ft",),
                (
                    (
                        "mobility_loss_feet",
                        "denial",
                        "feet_unavailable_at_movement_opportunity",
                        "candidate",
                        (),
                        (
                            ("movement_modes", ("walk", "fly", "swim", "climb", "burrow")),
                            ("mobility_effect", "speed_zero"),
                        ),
                        ("movement_mode_speeds_ft",),
                        (),
                    ),
                    (
                        "defensive_attack_advantage",
                        "enablement",
                        "relevant_incoming_attack_opportunity",
                        "candidate",
                        (),
                        (),
                        (),
                        (),
                    ),
                    (
                        "offensive_impairment_all_attacks",
                        "denial",
                        "affected_target_turn",
                        "candidate",
                        (),
                        (("attack_scope", "all_attacks"),),
                        (),
                        (),
                    ),
                    (
                        "save_disadvantage",
                        "enablement",
                        "save_opportunity",
                        "candidate",
                        (),
                        (("save_ability", "dexterity"),),
                        (),
                        (),
                    ),
                ),
            ),
            (
                "stunned",
                188,
                ("incapacitated",),
                "denial",
                (),
                ("source_end",),
                (
                    "target_is_concentrating",
                    "target_airborne",
                    "hover_or_explicit_fall_prevention",
                ),
                (
                    (
                        "save_auto_failure",
                        "enablement",
                        "save_opportunity",
                        "candidate",
                        (),
                        (("save_ability", "strength"),),
                        (),
                        ("save_disadvantage",),
                    ),
                    (
                        "save_auto_failure",
                        "enablement",
                        "save_opportunity",
                        "candidate",
                        (),
                        (("save_ability", "dexterity"),),
                        (),
                        ("save_disadvantage",),
                    ),
                    (
                        "defensive_attack_advantage",
                        "enablement",
                        "relevant_incoming_attack_opportunity",
                        "candidate",
                        (),
                        (),
                        (),
                        (),
                    ),
                ),
            ),
        )
    }
)


def _assert_expected_condition_semantics(
    conditions: Mapping[str, ConditionDefinition],
    catalog_version: str,
    primitive_contract_version: str,
) -> None:
    version = (catalog_version, primitive_contract_version)
    expected = _EXPECTED_CONDITION_SEMANTICS.get(version)
    if expected is None:
        raise CatalogError(
            "No exact condition semantics are registered for catalog/primitive versions "
            f"{catalog_version}/{primitive_contract_version}"
        )
    actual = tuple(_condition_semantics(condition) for condition in conditions.values())
    if actual == expected:
        return
    for actual_condition, expected_condition in zip(actual, expected):
        if actual_condition != expected_condition:
            raise CatalogError(
                f"condition {actual_condition[0]} semantics must match the versioned "
                f"catalog {catalog_version} signature exactly"
            )
    raise CatalogError(
        f"condition semantics must match the versioned catalog {catalog_version} signature exactly"
    )

def _parse_predicates(value: Any, label: str) -> tuple[Predicate, ...]:
    result: list[Predicate] = []
    seen: dict[str, Any] = {}
    for index, item_value in enumerate(_array(value, label)):
        item_label = f"{label}[{index}]"
        item = _object(item_value, item_label)
        _exact_keys(item, {"predicate_id", "value"}, item_label)
        predicate_id = _snake_id(item["predicate_id"], f"{item_label}.predicate_id")
        if predicate_id not in _PREDICATE_RULES:
            raise CatalogError(f"{item_label}.predicate_id is unknown: {predicate_id}")
        rule_value = _freeze(_rule_value(item["value"], _PREDICATE_RULES[predicate_id], f"{item_label}.value"))
        if predicate_id in seen:
            if seen[predicate_id] != rule_value:
                raise CatalogError(f"{label} contains contradictory predicates for {predicate_id}")
            raise CatalogError(f"{label} contains a duplicate predicate: {predicate_id}")
        seen[predicate_id] = rule_value
        result.append(Predicate(predicate_id, rule_value))
    if [item.predicate_id for item in result] != sorted(
        (item.predicate_id for item in result), key=_PREDICATE_ORDER.__getitem__
    ):
        raise CatalogError(f"{label} must use canonical predicate ordering")
    return tuple(result)


def _parse_qualifiers(value: Any, label: str) -> tuple[Qualifier, ...]:
    result: list[Qualifier] = []
    seen: set[str] = set()
    for index, item_value in enumerate(_array(value, label)):
        item_label = f"{label}[{index}]"
        item = _object(item_value, item_label)
        _exact_keys(item, {"qualifier_id", "value"}, item_label)
        qualifier_id = _snake_id(item["qualifier_id"], f"{item_label}.qualifier_id")
        if qualifier_id not in _QUALIFIER_RULES:
            raise CatalogError(f"{item_label}.qualifier_id is unknown: {qualifier_id}")
        if qualifier_id in seen:
            raise CatalogError(f"{label} contains a duplicate qualifier: {qualifier_id}")
        seen.add(qualifier_id)
        rule_value = _freeze(_rule_value(item["value"], _QUALIFIER_RULES[qualifier_id], f"{item_label}.value"))
        result.append(Qualifier(qualifier_id, rule_value))
    return tuple(result)


def _parse_primitive(value: Any, condition_id: str, label: str) -> PrimitiveSpec:
    item = _object(value, label)
    _exact_keys(
        item,
        {
            "primitive_id",
            "family",
            "unit",
            "status",
            "predicates",
            "qualifiers",
            "context_requirements",
            "dominates",
        },
        label,
    )
    primitive_id = _snake_id(item["primitive_id"], f"{label}.primitive_id")
    definition = PRIMITIVE_CONTRACT.get(primitive_id)
    if definition is None:
        raise CatalogError(f"{label}.primitive_id is unknown: {primitive_id}")
    family = _snake_id(item["family"], f"{label}.family")
    unit = _snake_id(item["unit"], f"{label}.unit")
    status = _snake_id(item["status"], f"{label}.status")
    if family != definition.family or unit != definition.unit:
        raise CatalogError(
            f"{label} family/unit disagree with primitive contract for {primitive_id}: "
            f"expected {definition.family}/{definition.unit}"
        )
    if status not in definition.allowed_statuses:
        raise CatalogError(f"{label}.status is unsupported for {primitive_id}: {status}")
    predicates = _parse_predicates(item["predicates"], f"{label}.predicates")
    qualifiers = _parse_qualifiers(item["qualifiers"], f"{label}.qualifiers")
    contexts = _canonical_contexts(item["context_requirements"], f"{label}.context_requirements")
    dominates = _unique_strings(item["dominates"], f"{label}.dominates", PRIMITIVE_CONTRACT)
    if primitive_id in dominates:
        raise CatalogError(f"{label}.dominates cannot contain itself")
    for suppressed in dominates:
        if (primitive_id, suppressed) not in _ALLOWED_DOMINANCE:
            raise CatalogError(f"{label} declares unsupported dominance {primitive_id} over {suppressed}")
    return PrimitiveSpec(
        primitive_id,
        family,
        unit,
        status,
        predicates,
        qualifiers,
        contexts,
        dominates,
        (condition_id,),
    )


def _parse_responses(value: Any, label: str) -> tuple[ResponseMechanic, ...]:
    result: list[ResponseMechanic] = []
    seen: set[str] = set()
    for index, item_value in enumerate(_array(value, label)):
        item_label = f"{label}[{index}]"
        item = _object(item_value, item_label)
        _exact_keys(item, {"response_id", "timing", "requirements", "effects"}, item_label)
        response_id = _snake_id(item["response_id"], f"{item_label}.response_id")
        if response_id in seen:
            raise CatalogError(f"{label} contains a duplicate response ID")
        seen.add(response_id)
        expected = _EXPECTED_RESPONSES.get(response_id)
        if expected is None:
            raise CatalogError(f"{item_label}.response_id is unknown: {response_id}")
        timing = _snake_id(item["timing"], f"{item_label}.timing")
        requirements = tuple(
            _snake_id(raw, f"{item_label}.requirements[{i}]")
            for i, raw in enumerate(_array(item["requirements"], f"{item_label}.requirements"))
        )
        effects = tuple(
            _snake_id(raw, f"{item_label}.effects[{i}]")
            for i, raw in enumerate(_array(item["effects"], f"{item_label}.effects"))
        )
        if timing != expected["timing"] or requirements != expected["requirements"] or effects != expected["effects"]:
            raise CatalogError(f"{item_label} does not match the registered response mechanic")
        result.append(ResponseMechanic(response_id, timing, requirements, effects))
    return tuple(result)


def _assert_acyclic(conditions: Mapping[str, ConditionDefinition]) -> None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(condition_id: str) -> None:
        marker = state.get(condition_id, 0)
        if marker == 2:
            return
        if marker == 1:
            start = stack.index(condition_id)
            cycle = stack[start:] + [condition_id]
            raise CatalogError(f"Condition inclusion cycle: {' -> '.join(cycle)}")
        state[condition_id] = 1
        stack.append(condition_id)
        for included in conditions[condition_id].includes:
            if included not in conditions:
                raise CatalogError(f"Condition {condition_id} includes unknown condition {included}")
            visit(included)
        stack.pop()
        state[condition_id] = 2

    for condition_id in conditions:
        visit(condition_id)


def _expand_from_conditions(
    conditions: Mapping[str, ConditionDefinition], condition_id: str
) -> tuple[PrimitiveSpec, ...]:
    if condition_id not in conditions:
        raise CatalogError(f"Unknown condition ID: {condition_id}")
    visited: set[str] = set()
    ordered: list[PrimitiveSpec] = []
    by_signature: dict[tuple[Any, ...], int] = {}

    def include(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)
        condition = conditions[current_id]
        for nested_id in condition.includes:
            include(nested_id)
        for primitive in condition.primitives:
            signature = primitive.signature()
            existing_index = by_signature.get(signature)
            if existing_index is None:
                by_signature[signature] = len(ordered)
                ordered.append(primitive)
                continue
            existing = ordered[existing_index]
            source_ids = tuple(dict.fromkeys((*existing.source_condition_ids, *primitive.source_condition_ids)))
            ordered[existing_index] = replace(existing, source_condition_ids=source_ids)

    include(condition_id)
    return tuple(ordered)


def _save_ability(spec: PrimitiveSpec) -> str | None:
    value = spec.qualifier_values.get("save_ability")
    return value if isinstance(value, str) else None


def _assert_no_primitive_contradictions(conditions: Mapping[str, ConditionDefinition]) -> None:
    for condition_id in conditions:
        expanded = _expand_from_conditions(conditions, condition_id)
        auto_failures: dict[str, list[PrimitiveSpec]] = {}
        for spec in expanded:
            ability = _save_ability(spec)
            if spec.primitive_id == "save_auto_failure" and ability is not None:
                auto_failures.setdefault(ability, []).append(spec)
        disadvantages = {
            _save_ability(spec)
            for spec in expanded
            if spec.primitive_id == "save_disadvantage" and _save_ability(spec) is not None
        }
        for ability in sorted(set(auto_failures) & disadvantages):
            if any("save_disadvantage" not in spec.dominates for spec in auto_failures[ability]):
                raise CatalogError(
                    f"Condition {condition_id} claims automatic failure and disadvantage for {ability} "
                    "without explicit dominance"
                )

        by_identity: dict[tuple[str, tuple[Qualifier, ...]], list[PrimitiveSpec]] = {}
        for spec in expanded:
            by_identity.setdefault((spec.primitive_id, spec.qualifiers), []).append(spec)
        for identity, specs in by_identity.items():
            for left_index, left in enumerate(specs):
                left_values = left.predicate_values
                for right in specs[left_index + 1 :]:
                    right_values = right.predicate_values
                    for predicate_id in left_values.keys() & right_values.keys():
                        if left_values[predicate_id] != right_values[predicate_id]:
                            raise CatalogError(
                                f"Condition {condition_id} has contradictory predicate sets for "
                                f"{identity[0]}.{predicate_id}"
                            )


def validate_control_catalog(value: Any, *, digest: str | None = None) -> ControlCatalog:
    """Validate a JSON-like catalog value and return its immutable typed form."""

    data = _object(value, "control consequence catalog")
    _exact_keys(
        data,
        {
            "format_version",
            "catalog_version",
            "primitive_contract_version",
            "diagnostic_families",
            "statuses",
            "units",
            "primitive_contract",
            "context_requirement_registry",
            "conditions",
        },
        "control consequence catalog",
    )
    if isinstance(data["format_version"], bool) or data["format_version"] != 1:
        raise CatalogError("Unsupported control consequence catalog format version")
    catalog_version = _version(data["catalog_version"], CATALOG_VERSION, "catalog_version")
    primitive_version = _version(
        data["primitive_contract_version"], PRIMITIVE_CONTRACT_VERSION, "primitive_contract_version"
    )
    if data["diagnostic_families"] != list(DIAGNOSTIC_FAMILIES):
        raise CatalogError("diagnostic_families must match the versioned registry exactly")
    if data["statuses"] != list(PRIMITIVE_STATUSES):
        raise CatalogError("statuses must match the versioned registry exactly")
    if data["units"] != list(PRIMITIVE_UNITS):
        raise CatalogError("units must match the versioned registry exactly")
    if data["context_requirement_registry"] != list(_CONTEXT_REQUIREMENTS):
        raise CatalogError("context_requirement_registry must match the versioned registry exactly")

    raw_contract = _array(data["primitive_contract"], "primitive_contract")
    expected_contract = [
        definition.as_dict(primitive_id) for primitive_id, definition in PRIMITIVE_CONTRACT.items()
    ]
    contract_ids: list[str] = []
    for index, item_value in enumerate(raw_contract):
        item = _object(item_value, f"primitive_contract[{index}]")
        _exact_keys(
            item,
            {"primitive_id", "family", "unit", "default_status", "allowed_statuses"},
            f"primitive_contract[{index}]",
        )
        contract_ids.append(_snake_id(item["primitive_id"], f"primitive_contract[{index}].primitive_id"))
        _snake_id(item["family"], f"primitive_contract[{index}].family")
        _snake_id(item["unit"], f"primitive_contract[{index}].unit")
        _snake_id(item["default_status"], f"primitive_contract[{index}].default_status")
        _unique_strings(
            item["allowed_statuses"],
            f"primitive_contract[{index}].allowed_statuses",
            PRIMITIVE_STATUSES,
        )
    if len(contract_ids) != len(set(contract_ids)):
        raise CatalogError("primitive_contract contains a duplicate primitive ID")
    if raw_contract != expected_contract:
        raise CatalogError("primitive_contract must match the versioned primitive registry exactly")

    raw_conditions = _array(data["conditions"], "conditions")
    parsed: dict[str, ConditionDefinition] = {}
    input_order: list[str] = []
    for index, value_item in enumerate(raw_conditions):
        label = f"conditions[{index}]"
        item = _object(value_item, label)
        _exact_keys(
            item,
            {
                "condition_id",
                "source_page",
                "includes",
                "default_diagnostic_family",
                "response_mechanics",
                "end_mechanics",
                "context_requirements",
                "primitives",
            },
            label,
        )
        condition_id = _snake_id(item["condition_id"], f"{label}.condition_id")
        if condition_id in parsed:
            raise CatalogError(f"conditions contains duplicate condition ID: {condition_id}")
        if condition_id not in _CONDITION_PAGES:
            raise CatalogError(f"conditions contains unsupported condition ID: {condition_id}")
        source_page = _positive_integer(item["source_page"], f"{label}.source_page")
        if source_page != _CONDITION_PAGES[condition_id]:
            raise CatalogError(
                f"{label}.source_page must be pinned SRD page {_CONDITION_PAGES[condition_id]}"
            )
        includes = _unique_strings(item["includes"], f"{label}.includes", _CONDITION_PAGES)
        family = _snake_id(item["default_diagnostic_family"], f"{label}.default_diagnostic_family")
        if family not in DIAGNOSTIC_FAMILIES:
            raise CatalogError(f"{label}.default_diagnostic_family is unknown: {family}")
        responses = _parse_responses(item["response_mechanics"], f"{label}.response_mechanics")
        end_mechanics = _unique_strings(item["end_mechanics"], f"{label}.end_mechanics", _END_MECHANICS)
        contexts = _canonical_contexts(item["context_requirements"], f"{label}.context_requirements")
        primitives = tuple(
            _parse_primitive(raw, condition_id, f"{label}.primitives[{primitive_index}]")
            for primitive_index, raw in enumerate(_array(item["primitives"], f"{label}.primitives"))
        )
        signatures = [primitive.signature() for primitive in primitives]
        if len(signatures) != len(set(signatures)):
            raise CatalogError(f"{label}.primitives contains a duplicate expansion")
        for primitive in primitives:
            missing_contexts = sorted(set(primitive.context_requirements) - set(contexts))
            if missing_contexts:
                raise CatalogError(
                    f"{label} omits primitive context requirements from its condition context: {missing_contexts}"
                )
        parsed[condition_id] = ConditionDefinition(
            condition_id,
            source_page,
            includes,
            family,
            responses,
            end_mechanics,
            contexts,
            primitives,
        )
        input_order.append(condition_id)

    _assert_acyclic(parsed)
    if set(parsed) != set(_CONDITION_PAGES):
        missing = sorted(set(_CONDITION_PAGES) - set(parsed))
        extra = sorted(set(parsed) - set(_CONDITION_PAGES))
        raise CatalogError(f"condition scope is invalid; missing={missing}, extra={extra}")
    if input_order != list(_CONDITION_PAGES):
        raise CatalogError("conditions must use canonical condition ordering")
    _assert_expected_condition_semantics(
        parsed,
        catalog_version,
        primitive_version,
    )
    _assert_no_primitive_contradictions(parsed)
    catalog_digest = digest or _json_digest(data)
    if not _SHA256.fullmatch(catalog_digest):
        raise CatalogError("catalog digest must be a lowercase SHA-256")
    return ControlCatalog(
        catalog_version,
        primitive_version,
        MappingProxyType(parsed),
        catalog_digest,
    )


def _validate_catalog_provenance(value: Any, catalog_path: Path, catalog: ControlCatalog) -> None:
    data = _object(value, "control consequence provenance")
    _exact_keys(
        data,
        {
            "format_version",
            "catalog_version",
            "primitive_contract_version",
            "source",
            "condition_pages",
            "data_file",
            "data_sha256",
            "extraction",
        },
        "control consequence provenance",
    )
    if isinstance(data["format_version"], bool) or data["format_version"] != 1:
        raise CatalogError("Unsupported control consequence provenance format version")
    _version(data["catalog_version"], catalog.catalog_version, "provenance.catalog_version")
    _version(
        data["primitive_contract_version"],
        catalog.primitive_contract_version,
        "provenance.primitive_contract_version",
    )
    source = _object(data["source"], "control consequence provenance.source")
    _exact_keys(source, set(_EXPECTED_SOURCE), "control consequence provenance.source")
    if source != _EXPECTED_SOURCE:
        raise CatalogError("Control consequence provenance does not identify the pinned official SRD 5.2.1 PDF")
    pages = _object(data["condition_pages"], "control consequence provenance.condition_pages")
    _exact_keys(pages, set(_CONDITION_PAGES), "control consequence provenance.condition_pages")
    if pages != dict(_CONDITION_PAGES):
        raise CatalogError("Control consequence provenance condition pages are not exact")
    if data["data_file"] != "harness/data/srd_control_consequences.json":
        raise CatalogError("Control consequence provenance data_file is unsupported")
    data_sha = _string(data["data_sha256"], "control consequence provenance.data_sha256")
    if not _SHA256.fullmatch(data_sha) or data_sha != sha256_file(catalog_path) or data_sha != catalog.digest:
        raise CatalogError("Control consequence catalog SHA-256 does not match provenance")
    extraction = _object(data["extraction"], "control consequence provenance.extraction")
    _exact_keys(extraction, set(_EXPECTED_EXTRACTION), "control consequence provenance.extraction")
    if extraction != _EXPECTED_EXTRACTION:
        raise CatalogError("Control consequence provenance extraction policy is unsupported")


def load_control_catalog(
    path: str | Path = DEFAULT_CONTROL_CATALOG,
    provenance_path: str | Path | None = DEFAULT_CONTROL_PROVENANCE,
) -> ControlCatalog:
    """Load the pinned catalog; a supplied ``None`` provenance path skips only pin validation."""

    catalog_path = Path(path)
    try:
        value = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"Unable to load control consequence catalog: {error}") from error
    catalog = validate_control_catalog(value, digest=sha256_file(catalog_path))
    if provenance_path is not None:
        provenance_file = Path(provenance_path)
        try:
            provenance = json.loads(provenance_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CatalogError(f"Unable to load control consequence provenance: {error}") from error
        _validate_catalog_provenance(provenance, catalog_path, catalog)
    return catalog


def expand_condition(catalog: ControlCatalog, condition_id: str) -> tuple[PrimitiveSpec, ...]:
    """Expand condition inclusions once and merge identical primitive specifications."""

    if not isinstance(catalog, ControlCatalog):
        raise TypeError("catalog must be a validated ControlCatalog")
    normalized_id = _snake_id(condition_id, "condition_id")
    return _expand_from_conditions(catalog.conditions, normalized_id)


@dataclass(frozen=True)
class SenseContext:
    interaction_distance_ft: float | None = None
    total_cover: bool | None = None
    target_airborne: bool | None = None
    same_surface_or_liquid: bool | None = None

    def __post_init__(self) -> None:
        distance = self.interaction_distance_ft
        if distance is not None:
            if isinstance(distance, bool) or not isinstance(distance, (int, float)):
                raise SenseContextError("interaction_distance_ft must be a nonnegative finite number")
            if not math.isfinite(float(distance)) or distance < 0:
                raise SenseContextError("interaction_distance_ft must be a nonnegative finite number")
        for field in ("total_cover", "target_airborne", "same_surface_or_liquid"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, bool):
                raise SenseContextError(f"{field} must be a boolean or null")


@dataclass(frozen=True)
class SenseQueryResult:
    alternative_sight: bool | None
    location_detection: bool | None
    alternative_sight_evidence: tuple[str, ...]
    location_detection_evidence: tuple[str, ...]
    alternative_sight_missing_context: tuple[str, ...]
    location_detection_missing_context: tuple[str, ...]

    @property
    def unresolved(self) -> bool:
        return self.alternative_sight is None or self.location_detection is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "alternative_sight": self.alternative_sight,
            "location_detection": self.location_detection,
            "alternative_sight_evidence": list(self.alternative_sight_evidence),
            "location_detection_evidence": list(self.location_detection_evidence),
            "alternative_sight_missing_context": list(self.alternative_sight_missing_context),
            "location_detection_missing_context": list(self.location_detection_missing_context),
        }


@dataclass(frozen=True)
class _Sense:
    sense: str
    range_ft: int
    limitation: str | None


def _normalize_senses(value: Sequence[Any] | Iterable[Any]) -> tuple[_Sense, ...]:
    if isinstance(value, (str, bytes)):
        raise CatalogError("nonvisual_senses must be an iterable of typed sense records")
    result: list[_Sense] = []
    for index, raw in enumerate(value):
        label = f"nonvisual_senses[{index}]"
        if isinstance(raw, Mapping):
            item = dict(raw)
            _exact_keys(item, {"sense", "range_ft", "limitation"}, label)
            sense_value, range_value, limitation_value = item["sense"], item["range_ft"], item["limitation"]
        elif all(hasattr(raw, field) for field in ("sense", "range_ft", "limitation")):
            sense_value = raw.sense
            range_value = raw.range_ft
            limitation_value = raw.limitation
        else:
            raise CatalogError(f"{label} must expose exactly sense, range_ft, and limitation")
        sense = _snake_id(sense_value, f"{label}.sense")
        if sense not in SUPPORTED_NONVISUAL_SENSES:
            raise CatalogError(f"{label}.sense is not in the nonvisual input boundary: {sense}")
        range_ft = _positive_integer(range_value, f"{label}.range_ft")
        if limitation_value is not None:
            limitation_value = _string(limitation_value, f"{label}.limitation")
        result.append(_Sense(sense, range_ft, limitation_value))
    names = [item.sense for item in result]
    if len(names) != len(set(names)):
        raise CatalogError("nonvisual_senses contains a duplicate sense")
    return tuple(result)


def query_sense(
    nonvisual_senses: Sequence[Any] | Iterable[Any],
    interaction_distance_ft: float | SenseContext | None = None,
    total_cover: bool | None = None,
    target_airborne: bool | None = None,
    same_surface_or_liquid: bool | None = None,
    fail_closed: bool = False,
    *,
    context: SenseContext | None = None,
) -> SenseQueryResult:
    """Resolve Blindsight and Tremorsense independently without treating either as immunity."""

    if isinstance(interaction_distance_ft, SenseContext):
        if context is not None or any(
            value is not None for value in (total_cover, target_airborne, same_surface_or_liquid)
        ):
            raise SenseContextError("SenseContext cannot be combined with individual context arguments")
        context = interaction_distance_ft
    elif context is not None:
        if any(value is not None for value in (interaction_distance_ft, total_cover, target_airborne, same_surface_or_liquid)):
            raise SenseContextError("SenseContext cannot be combined with individual context arguments")
    else:
        context = SenseContext(
            interaction_distance_ft=interaction_distance_ft,
            total_cover=total_cover,
            target_airborne=target_airborne,
            same_surface_or_liquid=same_surface_or_liquid,
        )
    senses = _normalize_senses(nonvisual_senses)
    blindsight = next((item for item in senses if item.sense == "blindsight"), None)
    tremorsense = next((item for item in senses if item.sense == "tremorsense"), None)

    alt_evidence: list[str] = []
    alt_missing: list[str] = []
    if blindsight is None:
        alternative: bool | None = False
        alt_evidence.append("no_blindsight")
    elif blindsight.limitation is not None:
        alternative = None
        alt_evidence.append("blindsight_has_unmodeled_limitation")
        alt_missing.append("blindsight_limitation_context")
    elif context.interaction_distance_ft is None:
        alternative = None
        alt_evidence.append("blindsight_distance_unresolved")
        alt_missing.append("interaction_distance_ft")
    elif context.interaction_distance_ft > blindsight.range_ft:
        alternative = False
        alt_evidence.append("blindsight_outside_range")
    elif context.total_cover is None:
        alternative = None
        alt_evidence.append("blindsight_cover_unresolved")
        alt_missing.append("total_cover")
    elif context.total_cover:
        alternative = False
        alt_evidence.append("blindsight_blocked_by_total_cover")
    else:
        alternative = True
        alt_evidence.append("blindsight_within_range_without_total_cover")

    location_evidence: list[str] = []
    location_missing: list[str] = []
    if tremorsense is None:
        location: bool | None = False
        location_evidence.append("no_tremorsense")
    elif tremorsense.limitation is not None:
        location = None
        location_evidence.append("tremorsense_has_unmodeled_limitation")
        location_missing.append("tremorsense_limitation_context")
    elif context.interaction_distance_ft is None:
        location = None
        location_evidence.append("tremorsense_distance_unresolved")
        location_missing.append("interaction_distance_ft")
    elif context.interaction_distance_ft > tremorsense.range_ft:
        location = False
        location_evidence.append("tremorsense_outside_range")
    elif context.target_airborne is True:
        location = False
        location_evidence.append("tremorsense_excludes_airborne_target")
    else:
        if context.target_airborne is None:
            location_missing.append("target_airborne")
        if context.same_surface_or_liquid is None:
            location_missing.append("same_surface_or_liquid")
        if location_missing:
            location = None
            location_evidence.append("tremorsense_contact_context_unresolved")
        elif not context.same_surface_or_liquid:
            location = False
            location_evidence.append("tremorsense_requires_same_surface_or_liquid")
        else:
            location = True
            location_evidence.append("tremorsense_detects_qualifying_contact")

    result = SenseQueryResult(
        alternative,
        location,
        tuple(alt_evidence),
        tuple(location_evidence),
        tuple(alt_missing),
        tuple(location_missing),
    )
    if fail_closed and result.unresolved:
        missing = tuple(dict.fromkeys((*alt_missing, *location_missing)))
        raise SenseContextError(f"Sense query is unresolved; missing context={list(missing)}")
    return result


@dataclass(frozen=True)
class InitiativeSchedule:
    schedule_id: str
    version: str
    round_events: tuple[str, ...]
    target_turn_events: tuple[str, ...]
    reaction_windows: tuple[str, ...]
    round_boundary: str


@dataclass(frozen=True)
class AreaResponseConvention:
    area_response_id: str
    version: str
    policy: str
    required_route_context: tuple[str, ...]
    route_progress: str
    exit_effect: str
    missing_context: str


@dataclass(frozen=True)
class DisplacementFunction:
    function_id: str
    version: str
    input_unit: str
    grid_unit_feet: int
    formula: str

    def evaluate(self, distance_feet: float) -> float:
        if isinstance(distance_feet, bool) or not isinstance(distance_feet, (int, float)):
            raise CatalogError("distance_feet must be a nonnegative finite number")
        distance = float(distance_feet)
        if not math.isfinite(distance) or distance < 0:
            raise CatalogError("distance_feet must be a nonnegative finite number")
        if self.function_id == "sqrt_5ft_v1":
            return math.sqrt(distance / 5)
        if self.function_id == "log2_5ft_v1":
            return math.log2(1 + distance / 5)
        if self.function_id == "banded_10ft_v1":
            return 0.0 if distance == 0 else float(math.ceil(distance / 10))
        raise CatalogError(f"Unknown displacement function: {self.function_id}")


@dataclass(frozen=True)
class ControlEngineConfig:
    config_version: str
    primitive_contract_version: str
    normalization_rules_version: str
    timeline_engine_version: str
    horizon_rounds: int
    initiative_schedules: Mapping[str, InitiativeSchedule]
    area_response_conventions: Mapping[str, AreaResponseConvention]
    displacement_functions: Mapping[str, DisplacementFunction]
    digest: str


_EXPECTED_SCHEDULES = (
    {
        "schedule_id": "fighter_first_v1",
        "version": "1.0.0",
        "round_events": [
            "controller_turn_start",
            "scripted_controller_events_and_opportunities_in_supplied_legal_order",
            "controller_turn_end",
            "target_turns_in_supplied_stable_order",
        ],
        "target_turn_events": [
            "target_turn_start",
            "repeat_saves_and_start_turn_triggers",
            "target_active_turn_opportunity",
            "target_attack_opportunities_in_supplied_order",
            "target_movement_standing_area_response_opportunity",
            "target_turn_end",
        ],
        "reaction_windows": [
            "only_explicitly_scripted_reaction_opportunities",
            "reaction_availability_resets_at_reactor_turn_start",
        ],
        "round_boundary": "after_last_target_turn_end",
    },
    {
        "schedule_id": "target_before_fighter_v1",
        "version": "1.0.0",
        "round_events": [
            "target_turns_in_supplied_stable_order",
            "controller_turn_start",
            "scripted_controller_events_and_opportunities_in_supplied_legal_order",
            "controller_turn_end",
        ],
        "target_turn_events": [
            "target_turn_start",
            "repeat_saves_and_start_turn_triggers",
            "target_active_turn_opportunity",
            "target_attack_opportunities_in_supplied_order",
            "target_movement_standing_area_response_opportunity",
            "target_turn_end",
        ],
        "reaction_windows": [
            "only_explicitly_scripted_reaction_opportunities",
            "reaction_availability_resets_at_reactor_turn_start",
        ],
        "round_boundary": "after_controller_turn_end",
    },
)
_EXPECTED_AREAS = (
    {
        "area_response_id": "shortest_route_v1",
        "version": "1.0.0",
        "policy": "first_legal_movement_opportunity_minimizes_future_primitive_exposure",
        "required_route_context": [
            "current_membership",
            "distance_to_exit_by_legal_movement_mode",
            "route_compatibility_by_movement_mode",
            "movement_cost_multiplier_by_route",
            "airborne_grounded_or_in_liquid_state",
        ],
        "route_progress": "carry_deterministic_remaining_distance_until_exit",
        "exit_effect": "end_while_in_area_components_only",
        "missing_context": "error",
    },
    {
        "area_response_id": "fixed_occupancy_v1",
        "version": "1.0.0",
        "policy": "retain_membership_until_effect_end",
        "required_route_context": [],
        "route_progress": "none",
        "exit_effect": "effect_end_controls_membership",
        "missing_context": "not_applicable",
    },
)
_EXPECTED_DISPLACEMENT = (
    {
        "function_id": "sqrt_5ft_v1",
        "version": "1.0.0",
        "input_unit": "feet",
        "grid_unit_feet": 5,
        "formula": "sqrt(distance_feet / 5)",
    },
    {
        "function_id": "log2_5ft_v1",
        "version": "1.0.0",
        "input_unit": "feet",
        "grid_unit_feet": 5,
        "formula": "log2(1 + distance_feet / 5)",
    },
    {
        "function_id": "banded_10ft_v1",
        "version": "1.0.0",
        "input_unit": "feet",
        "grid_unit_feet": 5,
        "formula": "0 if distance_feet == 0 else ceil(distance_feet / 10)",
    },
)


def _validate_named_rows(
    value: Any,
    label: str,
    id_key: str,
    exact_keys: set[str],
    expected: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    rows = _array(value, label)
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        item_label = f"{label}[{index}]"
        item = _object(raw, item_label)
        _exact_keys(item, exact_keys, item_label)
        identifier = _snake_id(item[id_key], f"{item_label}.{id_key}")
        if identifier in seen:
            raise CatalogError(f"{label} contains duplicate ID: {identifier}")
        seen.add(identifier)
        _version(item["version"], "1.0.0", f"{item_label}.version")
        normalized.append(item)
    if normalized != list(expected):
        raise CatalogError(f"{label} must match the versioned named registry exactly")
    return normalized


def validate_engine_config(value: Any, *, digest: str | None = None) -> ControlEngineConfig:
    """Validate the non-damage engine methodology configuration."""

    data = _object(value, "control engine config")
    _exact_keys(
        data,
        {
            "format_version",
            "config_version",
            "primitive_contract_version",
            "normalization_rules_version",
            "timeline_engine_version",
            "horizon_rounds",
            "initiative_schedules",
            "area_response_conventions",
            "displacement_functions",
        },
        "control engine config",
    )
    if isinstance(data["format_version"], bool) or data["format_version"] != 1:
        raise CatalogError("Unsupported control engine config format version")
    config_version = _version(data["config_version"], ENGINE_CONFIG_VERSION, "config_version")
    primitive_version = _version(
        data["primitive_contract_version"], PRIMITIVE_CONTRACT_VERSION, "primitive_contract_version"
    )
    normalization_version = _version(
        data["normalization_rules_version"], NORMALIZATION_RULES_VERSION, "normalization_rules_version"
    )
    timeline_version = _version(
        data["timeline_engine_version"], TIMELINE_ENGINE_VERSION, "timeline_engine_version"
    )
    if isinstance(data["horizon_rounds"], bool) or data["horizon_rounds"] != 3:
        raise CatalogError("control engine horizon_rounds must be exactly 3")
    schedules = _validate_named_rows(
        data["initiative_schedules"],
        "initiative_schedules",
        "schedule_id",
        {"schedule_id", "version", "round_events", "target_turn_events", "reaction_windows", "round_boundary"},
        _EXPECTED_SCHEDULES,
    )
    areas = _validate_named_rows(
        data["area_response_conventions"],
        "area_response_conventions",
        "area_response_id",
        {
            "area_response_id",
            "version",
            "policy",
            "required_route_context",
            "route_progress",
            "exit_effect",
            "missing_context",
        },
        _EXPECTED_AREAS,
    )
    displacement = _validate_named_rows(
        data["displacement_functions"],
        "displacement_functions",
        "function_id",
        {"function_id", "version", "input_unit", "grid_unit_feet", "formula"},
        _EXPECTED_DISPLACEMENT,
    )
    schedule_values = {
        item["schedule_id"]: InitiativeSchedule(
            item["schedule_id"],
            item["version"],
            tuple(item["round_events"]),
            tuple(item["target_turn_events"]),
            tuple(item["reaction_windows"]),
            item["round_boundary"],
        )
        for item in schedules
    }
    area_values = {
        item["area_response_id"]: AreaResponseConvention(
            item["area_response_id"],
            item["version"],
            item["policy"],
            tuple(item["required_route_context"]),
            item["route_progress"],
            item["exit_effect"],
            item["missing_context"],
        )
        for item in areas
    }
    displacement_values = {
        item["function_id"]: DisplacementFunction(
            item["function_id"],
            item["version"],
            item["input_unit"],
            item["grid_unit_feet"],
            item["formula"],
        )
        for item in displacement
    }
    config_digest = digest or _json_digest(data)
    if not _SHA256.fullmatch(config_digest):
        raise CatalogError("config digest must be a lowercase SHA-256")
    return ControlEngineConfig(
        config_version,
        primitive_version,
        normalization_version,
        timeline_version,
        3,
        MappingProxyType(schedule_values),
        MappingProxyType(area_values),
        MappingProxyType(displacement_values),
        config_digest,
    )


def load_engine_config(path: str | Path = DEFAULT_ENGINE_CONFIG) -> ControlEngineConfig:
    config_path = Path(path)
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"Unable to load control engine config: {error}") from error
    return validate_engine_config(value, digest=sha256_file(config_path))


if __name__ == "__main__":
    loaded_catalog = load_control_catalog()
    loaded_config = load_engine_config()
    print(
        f"Validated {len(loaded_catalog.conditions)} SRD control consequences, "
        f"{len(PRIMITIVE_CONTRACT)} primitives, and control engine config {loaded_config.config_version}."
    )
