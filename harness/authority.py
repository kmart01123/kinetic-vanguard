"""Fail-closed adapter from the canonical TypeScript YAML loader to Python."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = PROJECT_ROOT / "KineticVanguard.yaml"
LEGACY_PROJECTION_VERSION = "1.0.0"
CONTROL_PROJECTION_VERSION = "2.0.0"
CONTROL_LEDGER_SIZE = 49

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENTS = {
    "declaration", "hit", "entry", "start_turn", "save", "repeat_save", "exit", "instantaneous_resolution"
}
_CONCENTRATION_TERMINATION = {
    "failed_concentration_save", "controller_incapacitated", "controller_death", "duration_expires", "voluntary_end"
}
_MOVEMENT_MODES = {"walk", "fly", "swim", "climb", "burrow"}
_SAVE_ABILITIES = {
    "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "discipline_signature"
}
_CONDITIONS = {"blinded", "charmed", "incapacitated", "prone", "restrained", "stunned"}
_FORCED_DIRECTIONS = {"straight_away_from_controller", "toward_controller", "controller_choice", "vertical_up"}
_FORCED_DESTINATIONS = {"legal_unoccupied_space", "legal_destination"}
_SIZE_COST_KEYS = {"tiny", "small", "medium", "large"}
_CONTROL_LEDGER_KEYS = (
    ("absolute_zero", 0), ("absolute_zero", 1), ("absolute_zero", 2),
    ("advanced_beguile", 0), ("advanced_beguile", 1), ("advanced_beguile", 2),
    ("advanced_deflection_screen", 2),
    ("advanced_gravitic_press", 0), ("advanced_gravitic_press", 1), ("advanced_gravitic_press", 2),
    ("advanced_improved_phase_step", 2),
    ("advanced_mind_lock", 0), ("advanced_mind_lock", 1), ("advanced_mind_lock", 2),
    ("advanced_phase_step", 2),
    ("arctic_tempest", 0), ("arctic_tempest", 1), ("arctic_tempest", 2),
    ("ball_lightning", 2),
    ("electron_burst", 2),
    ("explosion_implosion", 0), ("explosion_implosion", 1), ("explosion_implosion", 2),
    ("flare", 0), ("flare", 1), ("flare", 2),
    ("forked_lightning", 2),
    ("frozen_ground", 0), ("frozen_ground", 1), ("frozen_ground", 2),
    ("glacial_spike", 0), ("glacial_spike", 1), ("glacial_spike", 2),
    ("mass_levitation", 0), ("mass_levitation", 1), ("mass_levitation", 2),
    ("snow_chains", 0), ("snow_chains", 1), ("snow_chains", 2),
    ("static_discharge", 2),
    ("telekinetic_shove", 0), ("telekinetic_shove", 1), ("telekinetic_shove", 2),
    ("telekinetic_slam", 0), ("telekinetic_slam", 1), ("telekinetic_slam", 2),
    ("thermal_fracture", 0), ("thermal_fracture", 1), ("thermal_fracture", 2),
)
_CONTROL_MODELED_KEYS = frozenset({
    ("ball_lightning", 2), ("forked_lightning", 2),
    ("glacial_spike", 0), ("glacial_spike", 1), ("glacial_spike", 2),
    ("mass_levitation", 0),
    ("telekinetic_shove", 0), ("telekinetic_shove", 1), ("telekinetic_shove", 2),
})
_CONTROL_EXCLUDED_REASONS = {
    ("advanced_beguile", 0): "selectable_advanced_training_disabled",
    ("advanced_beguile", 1): "selectable_advanced_training_disabled",
    ("advanced_beguile", 2): "selectable_advanced_training_disabled",
    ("advanced_deflection_screen", 2): "incoming_enemy_attacks_unmodeled",
    ("advanced_gravitic_press", 0): "selectable_advanced_training_disabled",
    ("advanced_gravitic_press", 1): "selectable_advanced_training_disabled",
    ("advanced_gravitic_press", 2): "selectable_advanced_training_disabled",
    ("advanced_improved_phase_step", 2): "selectable_advanced_training_disabled",
    ("advanced_mind_lock", 0): "selectable_advanced_training_disabled",
    ("advanced_mind_lock", 1): "selectable_advanced_training_disabled",
    ("advanced_mind_lock", 2): "selectable_advanced_training_disabled",
    ("thermal_fracture", 0): "outside_headline_control_value",
    ("thermal_fracture", 1): "outside_headline_control_value",
    ("thermal_fracture", 2): "outside_headline_control_value",
}
_CONTROL_COVERAGE = {"modeled": 9, "excluded_by_profile": 14, "unsupported_error": 26, "total": 49}
_EXPECTED_MASTERIES = [
    {
        "mastery_id": "mastery_slow",
        "minimum_level": 3,
        "trigger": ["hit"],
        "component": {
            "component_id": "mastery_slow_speed_reduction",
            "target_selector_ids": ["manifested_strike_target"],
            "magnitude": {
                "kind": "speed_reduction",
                "reduction": {"kind": "flat_feet", "value": 10},
                "movement_modes": ["walk", "fly", "swim", "climb", "burrow"],
            },
            "duration": {"kind": "relative", "owner": "controller", "anchor": "start_turn", "offset_turns": 1},
            "cadence": {"apply": ["hit"], "repeat": [], "end": ["start_turn"]},
            "stacking": {
                "key": "mastery_slow_speed_reduction",
                "mode": "nonstacking",
                "refresh": "duration",
                "dominates_component_ids": [],
            },
        },
    },
    {
        "mastery_id": "mastery_push",
        "minimum_level": 3,
        "trigger": ["hit"],
        "component": {
            "component_id": "mastery_push_forced_movement",
            "target_selector_ids": ["manifested_strike_large_or_smaller_target"],
            "magnitude": {
                "kind": "forced_movement",
                "distance_feet": 10,
                "distance_mode": "up_to",
                "movement_mode": "push",
                "direction": "straight_away_from_controller",
                "destination": "legal_destination",
            },
            "duration": {"kind": "instantaneous"},
            "cadence": {"apply": ["hit"], "repeat": [], "end": ["instantaneous_resolution"]},
            "stacking": {
                "key": "mastery_push_forced_movement",
                "mode": "independent",
                "refresh": "none",
                "dominates_component_ids": [],
            },
        },
    },
    {
        "mastery_id": "mastery_sap",
        "minimum_level": 3,
        "trigger": ["hit"],
        "component": {
            "component_id": "mastery_sap_attack_disadvantage",
            "target_selector_ids": ["manifested_strike_target"],
            "magnitude": {"kind": "attack_disadvantage", "scope": "next_attack", "count": 1},
            "duration": {"kind": "relative", "owner": "controller", "anchor": "start_turn", "offset_turns": 1},
            "cadence": {"apply": ["hit"], "repeat": [], "end": ["start_turn"]},
            "stacking": {
                "key": "mastery_sap_attack_disadvantage",
                "mode": "nonstacking",
                "refresh": "duration",
                "dominates_component_ids": [],
            },
        },
    },
]


class AuthorityError(RuntimeError):
    """Raised when canonical mechanics cannot be projected safely."""



def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityError(f"{label} must be an object")
    return value


def _array(value: Any, label: str, minimum: int = 0) -> list[Any]:
    if not isinstance(value, list) or len(value) < minimum:
        raise AuthorityError(f"{label} must be an array with at least {minimum} item(s)")
    return value


def _exact_keys(value: dict[str, Any], required: set[str], label: str, optional: set[str] | None = None) -> None:
    optional = optional or set()
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    if missing or unknown:
        raise AuthorityError(f"{label} keys are invalid; missing={missing}, unknown={unknown}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityError(f"{label} must be a non-empty string")
    return value


def _identifier_value(value: Any, label: str) -> str:
    text = _string(value, label)
    if not _IDENTIFIER.fullmatch(text):
        raise AuthorityError(f"{label} must be a stable snake_case ID")
    return text


def _integer(value: Any, label: str, minimum: int | None = None) -> int:
    if isinstance(value, bool):
        raise AuthorityError(f"{label} must be an integer")
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        normalized = int(value)
    else:
        raise AuthorityError(f"{label} must be an integer")
    if minimum is not None and normalized < minimum:
        raise AuthorityError(f"{label} must be at least {minimum}")
    return normalized

def _number(value: Any, label: str, minimum_exclusive: float | None = None) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthorityError(f"{label} must be a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise AuthorityError(f"{label} must be finite")
    if minimum_exclusive is not None and value <= minimum_exclusive:
        raise AuthorityError(f"{label} must be greater than {minimum_exclusive}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise AuthorityError(f"{label} must be a boolean")
    return value


def _choice(value: Any, choices: set[str], label: str) -> str:
    text = _string(value, label)
    if text not in choices:
        raise AuthorityError(f"{label} has unsupported value {text!r}")
    return text


def _id_array(value: Any, label: str, minimum: int = 0) -> list[str]:
    rows = _array(value, label, minimum)
    result = [_identifier_value(item, f"{label}[{index}]") for index, item in enumerate(rows)]
    if len(result) != len(set(result)):
        raise AuthorityError(f"{label} contains duplicate IDs")
    return result


def _event_array(value: Any, label: str, minimum: int = 0) -> list[str]:
    rows = _array(value, label, minimum)
    result = [_choice(item, _EVENTS, f"{label}[{index}]") for index, item in enumerate(rows)]
    if len(result) != len(set(result)):
        raise AuthorityError(f"{label} contains duplicate events")
    return result


def _movement_modes(value: Any, label: str, minimum: int = 1) -> list[str]:
    rows = _array(value, label, minimum)
    result = [_choice(item, _MOVEMENT_MODES, f"{label}[{index}]") for index, item in enumerate(rows)]
    if len(result) != len(set(result)):
        raise AuthorityError(f"{label} contains duplicate movement modes")
    return result


def _projector_command(authority_path: Path, projection_version: str | None = None) -> list[str]:
    executable = PROJECT_ROOT / "node_modules" / ".bin" / "tsx"
    if not executable.is_file():
        raise AuthorityError("TypeScript projector unavailable; run `npm ci` first")
    command = [str(executable), str(PROJECT_ROOT / "src" / "harness-authority.ts"), "--authority", str(authority_path)]
    if projection_version is not None:
        command.extend(["--projection-version", projection_version])
    return command


def _run_projector(authority_path: str | Path, projection_version: str | None = None) -> dict[str, Any]:
    path = Path(authority_path).resolve()
    if not path.is_file():
        raise AuthorityError(f"Authority file does not exist: {path}")
    completed = subprocess.run(
        _projector_command(path, projection_version), cwd=PROJECT_ROOT, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown projection failure"
        raise AuthorityError(message)
    try:
        projection = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AuthorityError(f"Projector returned invalid JSON: {error}") from error
    if not isinstance(projection, dict):
        raise AuthorityError("Projector returned a non-object JSON projection")
    return projection


def load_projection(authority_path: str | Path = DEFAULT_AUTHORITY) -> dict[str, Any]:
    projection = _run_projector(authority_path)
    required = {"projection_version", "authority_path", "authority_sha256", "rules_version", "progressions", "disciplines", "features"}
    missing = sorted(required - projection.keys())
    if missing:
        raise AuthorityError(f"Projection is missing required fields: {', '.join(missing)}")
    if projection["projection_version"] != LEGACY_PROJECTION_VERSION:
        raise AuthorityError(
            f"Unsupported legacy projection version: {projection['projection_version']!r}; "
            f"expected {LEGACY_PROJECTION_VERSION}"
        )
    return projection


def _validate_magnitude(value: Any, label: str) -> None:
    magnitude = _object(value, label)
    kind = _choice(
        magnitude.get("kind"),
        {
            "condition", "forced_movement", "speed_reduction", "speed_zero", "attack_disadvantage",
            "reaction_denial", "movement_option_denial", "numerical_modifier",
        },
        f"{label}.kind",
    )
    if kind == "condition":
        _exact_keys(magnitude, {"kind", "condition"}, label)
        _choice(magnitude["condition"], _CONDITIONS, f"{label}.condition")
    elif kind == "forced_movement":
        _exact_keys(
            magnitude,
            {"kind", "distance_feet", "distance_mode", "movement_mode", "direction", "destination"},
            label,
        )
        _integer(magnitude["distance_feet"], f"{label}.distance_feet", 1)
        _choice(magnitude["distance_mode"], {"exact", "up_to"}, f"{label}.distance_mode")
        _choice(magnitude["movement_mode"], {"push", "pull", "reposition", "lift"}, f"{label}.movement_mode")
        _choice(magnitude["direction"], _FORCED_DIRECTIONS, f"{label}.direction")
        _choice(magnitude["destination"], _FORCED_DESTINATIONS, f"{label}.destination")
    elif kind == "speed_reduction":
        _exact_keys(magnitude, {"kind", "reduction", "movement_modes"}, label)
        reduction = _object(magnitude["reduction"], f"{label}.reduction")
        reduction_kind = _choice(
            reduction.get("kind"), {"flat_feet", "fraction", "terrain_multiplier"}, f"{label}.reduction.kind"
        )
        if reduction_kind == "flat_feet":
            _exact_keys(reduction, {"kind", "value"}, f"{label}.reduction")
            _integer(reduction["value"], f"{label}.reduction.value", 1)
        elif reduction_kind == "fraction":
            _exact_keys(reduction, {"kind", "numerator", "denominator"}, f"{label}.reduction")
            numerator = _integer(reduction["numerator"], f"{label}.reduction.numerator", 1)
            denominator = _integer(reduction["denominator"], f"{label}.reduction.denominator", 1)
            if numerator >= denominator:
                raise AuthorityError(f"{label}.reduction fraction must reduce speed")
        else:
            _exact_keys(reduction, {"kind", "value"}, f"{label}.reduction")
            _number(reduction["value"], f"{label}.reduction.value", 1)
        _movement_modes(magnitude["movement_modes"], f"{label}.movement_modes")
    elif kind == "speed_zero":
        _exact_keys(magnitude, {"kind", "movement_modes"}, label)
        _movement_modes(magnitude["movement_modes"], f"{label}.movement_modes")
    elif kind == "attack_disadvantage":
        _exact_keys(magnitude, {"kind", "scope"}, label, {"count"})
        scope = _choice(magnitude["scope"], {"next_attack", "all_attacks"}, f"{label}.scope")
        if scope == "next_attack":
            _exact_keys(magnitude, {"kind", "scope", "count"}, label)
            _integer(magnitude["count"], f"{label}.count", 1)
        else:
            _exact_keys(magnitude, {"kind", "scope"}, label)
    elif kind == "reaction_denial":
        _exact_keys(magnitude, {"kind", "scope"}, label)
        _choice(magnitude["scope"], {"all_reactions"}, f"{label}.scope")
    elif kind == "movement_option_denial":
        _exact_keys(magnitude, {"kind", "movement_modes"}, label)
        _movement_modes(magnitude["movement_modes"], f"{label}.movement_modes")
    else:
        _exact_keys(magnitude, {"kind", "target", "value"}, label)
        _choice(magnitude["target"], {"armor_class"}, f"{label}.target")
        modifier = _number(magnitude["value"], f"{label}.value")
        if modifier == 0:
            raise AuthorityError(f"{label}.value must be non-zero")


def _validate_duration(value: Any, label: str) -> None:
    duration = _object(value, label)
    kind = _choice(
        duration.get("kind"), {"instantaneous", "relative", "while_in_area", "concentration"}, f"{label}.kind"
    )
    if kind == "instantaneous":
        _exact_keys(duration, {"kind"}, label)
    elif kind == "relative":
        _exact_keys(duration, {"kind", "owner", "anchor", "offset_turns"}, label)
        _choice(duration["owner"], {"controller", "target"}, f"{label}.owner")
        _choice(duration["anchor"], {"start_turn", "end_turn"}, f"{label}.anchor")
        _integer(duration["offset_turns"], f"{label}.offset_turns", 0)
    elif kind == "while_in_area":
        _exact_keys(duration, {"kind", "area_id"}, label)
        _identifier_value(duration["area_id"], f"{label}.area_id")
    else:
        _exact_keys(duration, {"kind", "maximum_value", "unit"}, label)
        _integer(duration["maximum_value"], f"{label}.maximum_value", 1)
        _choice(duration["unit"], {"round", "minute", "hour"}, f"{label}.unit")


def _validate_component(value: Any, label: str) -> dict[str, Any]:
    component = _object(value, label)
    _exact_keys(
        component,
        {"component_id", "target_selector_ids", "magnitude", "duration", "cadence", "stacking"},
        label,
    )
    _identifier_value(component["component_id"], f"{label}.component_id")
    _id_array(component["target_selector_ids"], f"{label}.target_selector_ids", 1)
    _validate_magnitude(component["magnitude"], f"{label}.magnitude")
    _validate_duration(component["duration"], f"{label}.duration")
    cadence = _object(component["cadence"], f"{label}.cadence")
    _exact_keys(cadence, {"apply", "repeat", "end"}, f"{label}.cadence")
    _event_array(cadence["apply"], f"{label}.cadence.apply", 1)
    _event_array(cadence["repeat"], f"{label}.cadence.repeat")
    _event_array(cadence["end"], f"{label}.cadence.end")
    stacking = _object(component["stacking"], f"{label}.stacking")
    _exact_keys(
        stacking,
        {"key", "mode", "refresh", "dominates_component_ids"},
        f"{label}.stacking",
        {"replacement_group"},
    )
    _identifier_value(stacking["key"], f"{label}.stacking.key")
    mode = _choice(
        stacking["mode"], {"stacks", "nonstacking", "replace", "dominates", "independent"}, f"{label}.stacking.mode"
    )
    _choice(stacking["refresh"], {"duration", "none"}, f"{label}.stacking.refresh")
    dominated = _id_array(stacking["dominates_component_ids"], f"{label}.stacking.dominates_component_ids")
    if "replacement_group" in stacking:
        _identifier_value(stacking["replacement_group"], f"{label}.stacking.replacement_group")
    if mode == "replace" and "replacement_group" not in stacking:
        raise AuthorityError(f"{label}.stacking replacement mode requires replacement_group")
    if mode == "dominates" and not dominated:
        raise AuthorityError(f"{label}.stacking dominance mode requires explicit edges")
    if dominated and mode not in {"replace", "dominates"}:
        raise AuthorityError(f"{label}.stacking dominance edges require replace or dominates mode")
    return component


def _validate_selector_count(value: Any, label: str) -> None:
    count = _object(value, label)
    kind = _choice(
        count.get("kind"), {"fixed", "up_to", "proficiency_bonus", "cluster_remainder", "weighted_slots"}, f"{label}.kind"
    )
    if kind in {"fixed", "up_to"}:
        _exact_keys(count, {"kind", "value"}, label)
        _integer(count["value"], f"{label}.value", 1)
    elif kind == "proficiency_bonus":
        _exact_keys(count, {"kind"}, label)
    elif kind == "cluster_remainder":
        _exact_keys(count, {"kind"}, label)
    else:
        _exact_keys(count, {"kind", "slots", "size_costs"}, label)
        _integer(count["slots"], f"{label}.slots", 1)
        costs = _object(count["size_costs"], f"{label}.size_costs")
        if not costs:
            raise AuthorityError(f"{label}.size_costs must not be empty")
        for size, cost in costs.items():
            _choice(size, _SIZE_COST_KEYS, f"{label}.size_costs key")
            _integer(cost, f"{label}.size_costs.{size}", 1)


def _validate_restriction(value: Any, label: str) -> str:
    restriction = _object(value, label)
    kind = _choice(
        restriction.get("kind"),
        {"visibility", "maximum_size", "unique_targets", "excludes_primary_target"},
        f"{label}.kind",
    )
    if kind == "visibility":
        _exact_keys(restriction, {"kind", "requirement"}, label)
        _choice(restriction["requirement"], {"controller_can_see"}, f"{label}.requirement")
    elif kind == "maximum_size":
        _exact_keys(restriction, {"kind", "size"}, label)
        _choice(restriction["size"], {"large_or_smaller"}, f"{label}.size")
    else:
        _exact_keys(restriction, {"kind", "required"}, label)
        if not _boolean(restriction["required"], f"{label}.required"):
            raise AuthorityError(f"{label}.required must be true")
    return kind


def _validate_area(value: Any, label: str) -> dict[str, Any]:
    area = _object(value, label)
    required = {"area_id", "shape", "origin", "persistent", "triggers", "exit_behavior"}
    dimensions = {"radius_feet", "height_feet", "length_feet", "width_feet"}
    persistence_fields = {"entry_policy", "movement"}
    _exact_keys(area, required, label, dimensions | persistence_fields)
    _identifier_value(area["area_id"], f"{label}.area_id")
    shape = _choice(area["shape"], {"sphere", "cylinder", "cone", "line"}, f"{label}.shape")
    _choice(
        area["origin"],
        {"controller", "primary_target", "selected_point", "departure_or_arrival"},
        f"{label}.origin",
    )
    expected = {
        "sphere": {"radius_feet"},
        "cylinder": {"radius_feet", "height_feet"},
        "cone": {"length_feet"},
        "line": {"length_feet", "width_feet"},
    }[shape]
    present = dimensions & area.keys()
    if present != expected:
        raise AuthorityError(
            f"{label} has incomplete {shape} dimensions; "
            f"expected={sorted(expected)}, present={sorted(present)}"
        )
    for field in expected:
        _integer(area[field], f"{label}.{field}", 1)
    persistent = _boolean(area["persistent"], f"{label}.persistent")
    triggers = _event_array(area["triggers"], f"{label}.triggers", 1)
    exit_behavior = _choice(area["exit_behavior"], {"ends_area_effects", "none"}, f"{label}.exit_behavior")
    if persistent:
        if not persistence_fields <= area.keys():
            raise AuthorityError(f"{label} persistent area requires entry_policy and movement")
        if not {"entry", "start_turn"} <= set(triggers) or exit_behavior != "ends_area_effects":
            raise AuthorityError(f"{label} persistent area requires entry/start_turn triggers and exit termination")
        entry_policy = _object(area["entry_policy"], f"{label}.entry_policy")
        _exact_keys(entry_policy, {"frequency", "moved_area_counts_as_entry"}, f"{label}.entry_policy")
        _choice(entry_policy["frequency"], {"once_per_turn"}, f"{label}.entry_policy.frequency")
        _boolean(entry_policy["moved_area_counts_as_entry"], f"{label}.entry_policy.moved_area_counts_as_entry")
        movement = _object(area["movement"], f"{label}.movement")
        movement_kind = _choice(
            movement.get("kind"), {"stationary", "controller_reposition"}, f"{label}.movement.kind"
        )
        if movement_kind == "stationary":
            _exact_keys(movement, {"kind"}, f"{label}.movement")
        else:
            _exact_keys(
                movement,
                {"kind", "controller_action", "distance_feet"},
                f"{label}.movement",
            )
            _choice(movement["controller_action"], {"bonus_action"}, f"{label}.movement.controller_action")
            _integer(movement["distance_feet"], f"{label}.movement.distance_feet", 1)
    elif persistence_fields & area.keys():
        raise AuthorityError(f"{label} nonpersistent area must not define entry_policy or movement")
    return area


def _validate_selector(value: Any, label: str) -> tuple[str, dict[str, dict[str, Any]]]:
    selector = _object(value, label)
    _exact_keys(
        selector,
        {"selector_id", "role", "count", "range", "restrictions", "gate_scope"},
        label,
        {"area"},
    )
    selector_id = _identifier_value(selector["selector_id"], f"{label}.selector_id")
    _choice(selector["role"], {"primary", "secondary", "all"}, f"{label}.role")
    _validate_selector_count(selector["count"], f"{label}.count")
    reach = _object(selector["range"], f"{label}.range")
    _exact_keys(reach, {"feet", "origin"}, f"{label}.range")
    _integer(reach["feet"], f"{label}.range.feet", 0)
    _choice(
        reach["origin"],
        {"controller", "primary_target", "selected_point", "departure_or_arrival"},
        f"{label}.range.origin",
    )
    restrictions = _array(selector["restrictions"], f"{label}.restrictions")
    restriction_kinds = [
        _validate_restriction(item, f"{label}.restrictions[{index}]")
        for index, item in enumerate(restrictions)
    ]
    if len(restriction_kinds) != len(set(restriction_kinds)):
        raise AuthorityError(f"{label}.restrictions contains duplicate restriction kinds")
    _choice(selector["gate_scope"], {"independent_per_target", "shared"}, f"{label}.gate_scope")
    areas: dict[str, dict[str, Any]] = {}
    if "area" in selector:
        area = _validate_area(selector["area"], f"{label}.area")
        areas[area["area_id"]] = area
    return selector_id, areas


def _validate_policy(value: Any, entity_id: str, tier: int, label: str) -> None:
    policy = _object(value, label)
    _exact_keys(
        policy,
        {
            "activation", "declaration", "delivery", "psi_cost", "overload_tier", "blood_tax",
            "repeatability", "mastery",
        },
        label,
    )
    activation = _choice(
        policy["activation"], {"action", "bonus_action", "reaction", "on_hit", "passive"}, f"{label}.activation"
    )
    _choice(policy["declaration"], {"declaration"}, f"{label}.declaration")
    delivery = _choice(policy["delivery"], {"attack_rider", "standalone"}, f"{label}.delivery")
    psi_cost = _integer(policy["psi_cost"], f"{label}.psi_cost", 0)
    overload_tier = _integer(policy["overload_tier"], f"{label}.overload_tier", 0)
    if overload_tier not in {0, 1, 2} or overload_tier != tier:
        raise AuthorityError(f"{label}.overload_tier must equal ledger tier {tier}")
    blood_tax = _choice(policy["blood_tax"], {"none", "tier_formula"}, f"{label}.blood_tax")
    if tier == 0 and blood_tax != "none":
        raise AuthorityError(f"{label}.blood_tax must be none at Tier 0")
    if tier > 0 and blood_tax != "tier_formula":
        raise AuthorityError(f"{label}.blood_tax must use the canonical tier formula above Tier 0")
    repeatability = _choice(
        policy["repeatability"],
        {"unlimited", "once_per_attack_action", "once_per_turn", "limited_use"},
        f"{label}.repeatability",
    )
    mastery = _choice(
        policy["mastery"], {"stacks", "replaces_on_declaration", "not_applicable"}, f"{label}.mastery"
    )
    expected = {
        "ball_lightning": ("action", "standalone", 5, "once_per_turn", "not_applicable"),
        "forked_lightning": ("action", "standalone", 3, "once_per_turn", "not_applicable"),
        "mass_levitation": ("action", "standalone", 5, "once_per_turn", "not_applicable"),
        "glacial_spike": ("on_hit", "attack_rider", 0, "unlimited", "stacks"),
        "telekinetic_shove": ("on_hit", "attack_rider", 0, "unlimited", "replaces_on_declaration"),
    }[entity_id]
    if (activation, delivery, psi_cost, repeatability, mastery) != expected:
        raise AuthorityError(f"{label} must match the canonical entity policy")


def _validate_concentration(value: Any, label: str) -> None:
    concentration = _object(value, label)
    kind = _choice(concentration.get("kind"), {"none", "required"}, f"{label}.kind")
    if kind == "none":
        _exact_keys(concentration, {"kind"}, label)
        return
    _exact_keys(
        concentration,
        {"kind", "startup", "occupancy", "replacement", "maximum_duration", "termination"},
        label,
    )
    _choice(concentration["startup"], {"on_resolution"}, f"{label}.startup")
    _choice(concentration["occupancy"], {"one_controller_slot"}, f"{label}.occupancy")
    _choice(concentration["replacement"], {"new_effect_ends_existing"}, f"{label}.replacement")
    maximum = _object(concentration["maximum_duration"], f"{label}.maximum_duration")
    _exact_keys(maximum, {"value", "unit"}, f"{label}.maximum_duration")
    _integer(maximum["value"], f"{label}.maximum_duration.value", 1)
    _choice(maximum["unit"], {"round", "minute", "hour"}, f"{label}.maximum_duration.unit")
    termination = _array(concentration["termination"], f"{label}.termination", 1)
    values = [_choice(item, _CONCENTRATION_TERMINATION, f"{label}.termination[{index}]") for index, item in enumerate(termination)]
    if len(values) != len(set(values)):
        raise AuthorityError(f"{label}.termination contains duplicate events")
    if set(values) != _CONCENTRATION_TERMINATION:
        raise AuthorityError(f"{label}.termination must enumerate every canonical termination event")


def _validate_branch(value: Any, label: str, component_ids: set[str]) -> dict[str, Any]:
    branch = _object(value, label)
    _exact_keys(
        branch,
        {"branch_id", "outcome", "applies", "replaces", "terminates", "refreshes", "next_gate_ids"},
        label,
    )
    branch_id = _identifier_value(branch["branch_id"], f"{label}.branch_id")
    outcome = _choice(
        branch["outcome"],
        {"attack_hit", "attack_miss", "save_success", "save_failure", "no_save", "other"},
        f"{label}.outcome",
    )
    transitions: dict[str, set[str]] = {}
    referenced: set[str] = set()
    for field in ("applies", "replaces", "terminates", "refreshes"):
        ids = set(_id_array(branch[field], f"{label}.{field}"))
        unknown = sorted(ids - component_ids)
        if unknown:
            raise AuthorityError(f"{label}.{field} references unknown components: {', '.join(unknown)}")
        transitions[field] = ids
        referenced.update(ids)
    transition_fields = ("applies", "replaces", "terminates", "refreshes")
    conflicting = {
        component_id
        for component_id in referenced
        if sum(component_id in transitions[field] for field in transition_fields) > 1
    }
    if conflicting:
        raise AuthorityError(
            f"{label} cannot reference the same component in multiple transition arrays: "
            f"{', '.join(sorted(conflicting))}"
        )
    next_gate_ids = _id_array(branch["next_gate_ids"], f"{label}.next_gate_ids")
    return {
        "branch_id": branch_id,
        "outcome": outcome,
        "referenced_components": referenced,
        "next_gate_ids": next_gate_ids,
        "transitions": transitions,
    }


def _validate_resolution(
    value: Any,
    label: str,
    selector_ids: set[str],
    component_ids: set[str],
    components_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = _object(value, label)
    _exact_keys(gate, {"gate_id", "selector_ids", "trigger", "gate_scope", "resolution"}, label)
    gate_id = _identifier_value(gate["gate_id"], f"{label}.gate_id")
    selected = _id_array(gate["selector_ids"], f"{label}.selector_ids", 1)
    unknown_selectors = sorted(set(selected) - selector_ids)
    if unknown_selectors:
        raise AuthorityError(f"{label}.selector_ids references unknown selectors: {', '.join(unknown_selectors)}")
    trigger = _choice(gate["trigger"], _EVENTS, f"{label}.trigger")
    gate_scope = _choice(gate["gate_scope"], {"independent_per_target", "shared"}, f"{label}.gate_scope")
    resolution = _object(gate["resolution"], f"{label}.resolution")
    kind = _choice(
        resolution.get("kind"), {"attack_roll", "saving_throw", "no_save", "other"}, f"{label}.resolution.kind"
    )
    if kind == "saving_throw":
        _exact_keys(resolution, {"kind", "ability", "branches"}, f"{label}.resolution")
        _choice(resolution["ability"], _SAVE_ABILITIES, f"{label}.resolution.ability")
    else:
        _exact_keys(resolution, {"kind", "branches"}, f"{label}.resolution")
    branches = _array(resolution["branches"], f"{label}.resolution.branches", 1)
    branch_ids: list[str] = []
    outcomes: list[str] = []
    referenced: set[str] = set()
    branch_summaries: list[dict[str, Any]] = []
    for index, branch_value in enumerate(branches):
        branch_label = f"{label}.resolution.branches[{index}]"
        branch_summary = _validate_branch(branch_value, branch_label, component_ids)
        branch_ids.append(branch_summary["branch_id"])
        outcomes.append(branch_summary["outcome"])
        referenced.update(branch_summary["referenced_components"])
        branch_summaries.append(branch_summary)
        branch = _object(branch_value, branch_label)
        for transition, cadence_field in {
            "applies": "apply",
            "refreshes": "repeat",
            "replaces": "end",
            "terminates": "end",
        }.items():
            for component_id in branch[transition]:
                cadence = components_by_id[component_id]["cadence"][cadence_field]
                if trigger not in cadence:
                    raise AuthorityError(
                        f"{branch_label}.{transition} requires {component_id}.cadence.{cadence_field} to include {trigger}"
                    )
    if len(branch_ids) != len(set(branch_ids)):
        raise AuthorityError(f"{label}.resolution contains duplicate branch IDs")
    if len(outcomes) != len(set(outcomes)):
        raise AuthorityError(f"{label}.resolution contains duplicate branch outcomes")
    expected = {
        "attack_roll": {"attack_hit", "attack_miss"},
        "saving_throw": {"save_success", "save_failure"},
        "no_save": {"no_save"},
        "other": {"other"},
    }[kind]
    if set(outcomes) != expected:
        raise AuthorityError(
            f"{label}.resolution has incomplete {kind} branches; expected={sorted(expected)}, actual={sorted(outcomes)}"
        )
    return {
        "gate_id": gate_id,
        "selector_ids": set(selected),
        "trigger": trigger,
        "gate_scope": gate_scope,
        "kind": kind,
        "branches": branch_summaries,
        "referenced_components": referenced,
    }


def _validate_relationships(value: Any, label: str, component_ids: set[str]) -> tuple[dict[str, set[str]], set[tuple[str, str]]]:
    relationships = _object(value, label)
    _exact_keys(relationships, {"replacement_groups", "dominance"}, label)
    replacement_groups: dict[str, set[str]] = {}
    for index, group_value in enumerate(_array(relationships["replacement_groups"], f"{label}.replacement_groups")):
        group = _object(group_value, f"{label}.replacement_groups[{index}]")
        _exact_keys(group, {"group_id", "component_ids"}, f"{label}.replacement_groups[{index}]")
        group_id = _identifier_value(group["group_id"], f"{label}.replacement_groups[{index}].group_id")
        if group_id in replacement_groups:
            raise AuthorityError(f"{label}.replacement_groups contains duplicate group IDs")
        members = set(_id_array(group["component_ids"], f"{label}.replacement_groups[{index}].component_ids", 2))
        unknown = sorted(members - component_ids)
        if unknown:
            raise AuthorityError(f"{label}.replacement_groups[{index}] references unknown components: {', '.join(unknown)}")
        replacement_groups[group_id] = members
    dominance_pairs: set[tuple[str, str]] = set()
    dominant_rows: set[str] = set()
    for index, dominance_value in enumerate(_array(relationships["dominance"], f"{label}.dominance")):
        dominance = _object(dominance_value, f"{label}.dominance[{index}]")
        _exact_keys(
            dominance,
            {"dominant_component_id", "suppressed_component_ids"},
            f"{label}.dominance[{index}]",
        )
        dominant = _identifier_value(
            dominance["dominant_component_id"], f"{label}.dominance[{index}].dominant_component_id"
        )
        if dominant in dominant_rows:
            raise AuthorityError(f"{label}.dominance contains duplicate dominant_component_id rows")
        dominant_rows.add(dominant)
        suppressed = _id_array(
            dominance["suppressed_component_ids"], f"{label}.dominance[{index}].suppressed_component_ids", 1
        )
        unknown = sorted(({dominant, *suppressed}) - component_ids)
        if unknown:
            raise AuthorityError(f"{label}.dominance[{index}] references unknown components: {', '.join(unknown)}")
        if dominant in suppressed:
            raise AuthorityError(f"{label}.dominance[{index}] cannot suppress its dominant component")
        for subordinate in suppressed:
            pair = (dominant, subordinate)
            if pair in dominance_pairs:
                raise AuthorityError(f"{label}.dominance contains duplicate relationships")
            dominance_pairs.add(pair)
    graph = {component_id: set() for component_id in component_ids}
    for dominant, subordinate in dominance_pairs:
        graph[dominant].add(subordinate)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visiting:
            raise AuthorityError(f"{label}.dominance must not contain a cycle")
        if component_id in visited:
            return
        visiting.add(component_id)
        for subordinate in graph[component_id]:
            visit(subordinate)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in sorted(component_ids):
        visit(component_id)
    return replacement_groups, dominance_pairs

def _validate_gate_graph(
    root_gate_ids: list[str],
    gates_by_id: dict[str, dict[str, Any]],
    delivery: str,
    label: str,
) -> None:
    gate_ids = set(gates_by_id)
    unknown_roots = sorted(set(root_gate_ids) - gate_ids)
    if unknown_roots:
        raise AuthorityError(f"{label}.root_gate_ids references unknown gates: {', '.join(unknown_roots)}")

    graph = {gate_id: set() for gate_id in gate_ids}
    incoming: set[str] = set()
    attack_hit_targets: set[str] = set()
    attack_miss_targets: set[str] = set()
    for gate_id, gate in gates_by_id.items():
        for branch in gate["branches"]:
            targets = set(branch["next_gate_ids"])
            unknown_targets = sorted(targets - gate_ids)
            if unknown_targets:
                raise AuthorityError(
                    f"{label} branch {branch['branch_id']!r} references unknown next gates: "
                    f"{', '.join(unknown_targets)}"
                )
            graph[gate_id].update(targets)
            incoming.update(targets)
            if branch["outcome"] == "attack_hit":
                attack_hit_targets.update(targets)
            elif branch["outcome"] == "attack_miss":
                attack_miss_targets.update(targets)

    roots_with_incoming = sorted(set(root_gate_ids) & incoming)
    if roots_with_incoming:
        raise AuthorityError(
            f"{label}.root_gate_ids must be exogenous and have no incoming transitions: "
            f"{', '.join(roots_with_incoming)}"
        )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(gate_id: str) -> None:
        if gate_id in visiting:
            raise AuthorityError(f"{label} gate graph must not contain a cycle")
        if gate_id in visited:
            return
        visiting.add(gate_id)
        for target in graph[gate_id]:
            visit(target)
        visiting.remove(gate_id)
        visited.add(gate_id)

    for root_gate_id in root_gate_ids:
        visit(root_gate_id)
    unreachable = sorted(gate_ids - visited)
    if unreachable:
        raise AuthorityError(f"{label} gate graph contains unreachable gates: {', '.join(unreachable)}")

    def descendants(starts: set[str]) -> set[str]:
        reached: set[str] = set()
        pending = list(starts)
        while pending:
            gate_id = pending.pop()
            if gate_id in reached:
                continue
            reached.add(gate_id)
            pending.extend(graph[gate_id] - reached)
        return reached

    attack_hit_reachable = descendants(attack_hit_targets)
    attack_miss_reachable = descendants(attack_miss_targets)
    if delivery == "attack_rider":
        non_attack_roots = sorted(
            gate_id for gate_id in root_gate_ids if gates_by_id[gate_id]["kind"] != "attack_roll"
        )
        if non_attack_roots:
            raise AuthorityError(f"{label} attack-rider root gates must use attack_roll resolution")
        saving_gate_ids = {
            gate_id for gate_id, gate in gates_by_id.items() if gate["kind"] == "saving_throw"
        }
        invalid_save_gates = sorted(
            gate_id
            for gate_id, gate in gates_by_id.items()
            if gate_id not in root_gate_ids
            and gate["kind"] == "saving_throw"
            and gate["trigger"] == "save"
            and gate_id not in attack_hit_reachable
        )
        if invalid_save_gates:
            raise AuthorityError(
                f"{label} nonroot save gates must be reached by attack_hit: {', '.join(invalid_save_gates)}"
            )
        miss_to_save = sorted(attack_miss_reachable & saving_gate_ids)
        if miss_to_save:
            raise AuthorityError(f"{label} attack_miss branches must not reach saving gates: {', '.join(miss_to_save)}")


def _validate_model(value: Any, entity_id: str, tier: int, label: str) -> dict[str, Any]:
    model = _object(value, label)
    _exact_keys(
        model,
        {
            "effect_id", "inheritance", "policy", "target_selectors", "components", "resolutions",
            "root_gate_ids", "concentration", "relationships",
        },
        label,
    )
    effect_id = _identifier_value(model["effect_id"], f"{label}.effect_id")
    inheritance = _object(model["inheritance"], f"{label}.inheritance")
    inheritance_kind = _choice(inheritance.get("kind"), {"none", "resolved"}, f"{label}.inheritance.kind")
    source_tier: int | None = None
    if inheritance_kind == "none":
        _exact_keys(inheritance, {"kind"}, f"{label}.inheritance")
        if tier != 0:
            raise AuthorityError(f"{label}.inheritance must resolve every modeled tier above Tier 0")
    else:
        _exact_keys(inheritance, {"kind", "source_tier"}, f"{label}.inheritance")
        source_tier = _integer(inheritance["source_tier"], f"{label}.inheritance.source_tier", 0)
        if source_tier not in {0, 1, 2} or source_tier >= tier:
            raise AuthorityError(f"{label}.inheritance.source_tier must be a lower canonical tier")
    _validate_policy(model["policy"], entity_id, tier, f"{label}.policy")
    policy = _object(model["policy"], f"{label}.policy")
    selector_rows = _array(model["target_selectors"], f"{label}.target_selectors", 1)
    selector_ids: list[str] = []
    selectors_by_id: dict[str, dict[str, Any]] = {}
    areas_by_id: dict[str, tuple[dict[str, Any], str]] = {}
    for index, selector_value in enumerate(selector_rows):
        selector_label = f"{label}.target_selectors[{index}]"
        selector_id, selector_areas = _validate_selector(selector_value, selector_label)
        selector_ids.append(selector_id)
        selectors_by_id[selector_id] = _object(selector_value, selector_label)
        for area_id, area in selector_areas.items():
            if area_id in areas_by_id:
                raise AuthorityError(f"{label}.target_selectors contains duplicate area IDs")
            areas_by_id[area_id] = (area, selector_id)
    if len(selector_ids) != len(set(selector_ids)):
        raise AuthorityError(f"{label}.target_selectors contains duplicate selector IDs")
    component_rows = _array(model["components"], f"{label}.components", 1)
    components = [
        _validate_component(item, f"{label}.components[{index}]")
        for index, item in enumerate(component_rows)
    ]
    component_ids = [
        _identifier_value(item["component_id"], f"{label}.components[{index}].component_id")
        for index, item in enumerate(components)
    ]
    if len(component_ids) != len(set(component_ids)):
        raise AuthorityError(f"{label}.components contains duplicate component IDs")
    selector_set = set(selector_ids)
    component_set = set(component_ids)
    components_by_id = {component["component_id"]: component for component in components}

    _validate_concentration(model["concentration"], f"{label}.concentration")
    concentration = _object(model["concentration"], f"{label}.concentration")
    concentration_required = concentration["kind"] == "required"
    canonical_concentration_required = entity_id in {"ball_lightning", "mass_levitation"}
    if concentration_required != canonical_concentration_required:
        raise AuthorityError(f"{label}.concentration does not match the canonical entity concentration flag")
    for index, component in enumerate(components):
        unknown_selectors = sorted(set(component["target_selector_ids"]) - selector_set)
        if unknown_selectors:
            raise AuthorityError(f"{label}.components[{index}] references unknown selectors: {', '.join(unknown_selectors)}")
        duration = _object(component["duration"], f"{label}.components[{index}].duration")
        if duration["kind"] == "while_in_area" and duration["area_id"] not in areas_by_id:
            raise AuthorityError(f"{label}.components[{index}].duration references an unknown area")
        if duration["kind"] == "concentration":
            if not concentration_required:
                raise AuthorityError(f"{label}.components[{index}].duration requires model concentration")
            maximum = concentration["maximum_duration"]
            if (
                duration["maximum_value"] != maximum["value"]
                or duration["unit"] != maximum["unit"]
            ):
                raise AuthorityError(
                    f"{label}.components[{index}].duration must match model concentration maximum_duration"
                )
    root_gate_ids = _id_array(model["root_gate_ids"], f"{label}.root_gate_ids", 1)
    gate_summaries: list[dict[str, Any]] = []
    branch_references: set[str] = set()
    for index, resolution_value in enumerate(_array(model["resolutions"], f"{label}.resolutions", 1)):
        gate_summary = _validate_resolution(
            resolution_value,
            f"{label}.resolutions[{index}]",
            selector_set,
            component_set,
            components_by_id,
        )
        gate_summaries.append(gate_summary)
        branch_references.update(gate_summary["referenced_components"])
        for selector_id in gate_summary["selector_ids"]:
            if selectors_by_id[selector_id]["gate_scope"] != gate_summary["gate_scope"]:
                raise AuthorityError(
                    f"{label}.resolutions[{index}].gate_scope must match every referenced selector"
                )
    gate_ids = [gate["gate_id"] for gate in gate_summaries]
    if len(gate_ids) != len(set(gate_ids)):
        raise AuthorityError(f"{label}.resolutions contains duplicate gate IDs")
    branch_ids = [
        branch["branch_id"]
        for gate in gate_summaries
        for branch in gate["branches"]
    ]
    if len(branch_ids) != len(set(branch_ids)):
        raise AuthorityError(f"{label}.resolutions contains duplicate branch IDs")
    missing_references = sorted(component_set - branch_references)
    if missing_references:
        raise AuthorityError(f"{label} components have no explicit branch reference: {', '.join(missing_references)}")
    gates_by_id = {gate["gate_id"]: gate for gate in gate_summaries}
    _validate_gate_graph(root_gate_ids, gates_by_id, policy["delivery"], label)

    for area_id, (area, selector_id) in areas_by_id.items():
        if not area["persistent"]:
            continue
        for event in ("entry", "start_turn"):
            if not any(
                gate["trigger"] == event and selector_id in gate["selector_ids"]
                for gate in gate_summaries
            ):
                raise AuthorityError(
                    f"{label} persistent area {area_id!r} requires a matching {event} resolution gate"
                )
        area_components = [
            component
            for component in components
            if component["duration"].get("kind") == "while_in_area"
            and component["duration"].get("area_id") == area_id
        ]
        if not area_components:
            raise AuthorityError(f"{label} persistent area {area_id!r} requires an area-duration component")
        for component in area_components:
            if selector_id not in component["target_selector_ids"] or "exit" not in component["cadence"]["end"]:
                raise AuthorityError(
                    f"{label} persistent area {area_id!r} components require the owning selector and exit cadence"
                )
    replacement_groups, dominance_pairs = _validate_relationships(
        model["relationships"], f"{label}.relationships", component_set
    )
    component_group_members: dict[str, set[str]] = {}
    inline_dominance: set[tuple[str, str]] = set()
    for index, component in enumerate(components):
        stacking = _object(component["stacking"], f"{label}.components[{index}].stacking")
        replacement_group = stacking.get("replacement_group")
        if replacement_group is not None and replacement_group not in replacement_groups:
            raise AuthorityError(f"{label}.components[{index}].stacking references an unknown replacement group")
        component_id = component["component_id"]
        if replacement_group is not None:
            component_group_members.setdefault(replacement_group, set()).add(component_id)
        for subordinate in stacking["dominates_component_ids"]:
            if subordinate not in component_set or subordinate == component_id:
                raise AuthorityError(f"{label}.components[{index}].stacking has invalid dominance references")
            inline_dominance.add((component_id, subordinate))
    for group_id, canonical_members in replacement_groups.items():
        if component_group_members.get(group_id, set()) != canonical_members:
            raise AuthorityError(
                f"{label}.relationships replacement group {group_id!r} must match component declarations"
            )
    if inline_dominance != dominance_pairs:
        raise AuthorityError(f"{label}.relationships dominance must match component declarations")
    return {
        "effect_id": effect_id,
        "inheritance_kind": inheritance_kind,
        "source_tier": source_tier,
        "selector_ids": selector_set,
        "component_ids": component_set,
    }


def _validate_contract(value: Any, label: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    contract = _object(value, label)
    _exact_keys(
        contract,
        {
            "contract_version", "active_profile", "target_data_requirements", "policy_inputs",
            "masteries", "tactical_master", "ledger",
        },
        label,
    )
    if contract["contract_version"] != CONTROL_PROJECTION_VERSION:
        raise AuthorityError(
            f"{label}.contract_version must be {CONTROL_PROJECTION_VERSION}, "
            f"got {contract['contract_version']!r}"
        )

    profile = _object(contract["active_profile"], f"{label}.active_profile")
    _exact_keys(
        profile,
        {
            "id", "selectable_advanced_training", "tactical_master", "legendary_resistance",
            "unsupported_disposition",
        },
        f"{label}.active_profile",
    )
    profile_id = _identifier_value(profile["id"], f"{label}.active_profile.id")
    if profile_id != "official_default_25_percent_hp":
        raise AuthorityError(f"{label}.active_profile.id must be official_default_25_percent_hp")
    _choice(
        profile["selectable_advanced_training"],
        {"excluded"},
        f"{label}.active_profile.selectable_advanced_training",
    )
    _choice(profile["tactical_master"], {"included"}, f"{label}.active_profile.tactical_master")
    _choice(
        profile["legendary_resistance"],
        {"metadata_only"},
        f"{label}.active_profile.legendary_resistance",
    )
    _choice(
        profile["unsupported_disposition"],
        {"error"},
        f"{label}.active_profile.unsupported_disposition",
    )

    requirements = _array(contract["target_data_requirements"], f"{label}.target_data_requirements", 4)
    expected_requirements = ["walking_speed", "movement_modes", "hover", "nonvisual_senses"]
    if requirements != expected_requirements:
        raise AuthorityError(
            f"{label}.target_data_requirements must be exactly {expected_requirements!r}"
        )

    inputs = _object(contract["policy_inputs"], f"{label}.policy_inputs")
    _exact_keys(inputs, {"horizon_rounds", "action_economy", "resources", "concentration"}, f"{label}.policy_inputs")
    if _integer(inputs["horizon_rounds"], f"{label}.policy_inputs.horizon_rounds", 1) != 3:
        raise AuthorityError(f"{label}.policy_inputs.horizon_rounds must be 3")
    economy = _object(inputs["action_economy"], f"{label}.policy_inputs.action_economy")
    _exact_keys(
        economy,
        {
            "attack_rider_declaration", "standalone_action_limit_per_turn",
            "action_surge_additional_standalone",
        },
        f"{label}.policy_inputs.action_economy",
    )
    _choice(
        economy["attack_rider_declaration"],
        {"before_attack_roll"},
        f"{label}.policy_inputs.action_economy.attack_rider_declaration",
    )
    if _integer(
        economy["standalone_action_limit_per_turn"],
        f"{label}.policy_inputs.action_economy.standalone_action_limit_per_turn",
    ) != 1:
        raise AuthorityError(f"{label}.policy_inputs.action_economy.standalone_action_limit_per_turn must be 1")
    if _boolean(
        economy["action_surge_additional_standalone"],
        f"{label}.policy_inputs.action_economy.action_surge_additional_standalone",
    ):
        raise AuthorityError(f"{label}.policy_inputs.action_economy.action_surge_additional_standalone must be false")

    resources = _object(inputs["resources"], f"{label}.policy_inputs.resources")
    _exact_keys(
        resources,
        {"psi_source", "blood_tax_source", "tier_two_limit_per_attack_action"},
        f"{label}.policy_inputs.resources",
    )
    _choice(resources["psi_source"], {"psi_point_bands"}, f"{label}.policy_inputs.resources.psi_source")
    _choice(resources["blood_tax_source"], {"harness_overload"}, f"{label}.policy_inputs.resources.blood_tax_source")
    if _integer(
        resources["tier_two_limit_per_attack_action"],
        f"{label}.policy_inputs.resources.tier_two_limit_per_attack_action",
    ) != 1:
        raise AuthorityError(f"{label}.policy_inputs.resources.tier_two_limit_per_attack_action must be 1")

    concentration = _object(inputs["concentration"], f"{label}.policy_inputs.concentration")
    _exact_keys(
        concentration,
        {"pressure", "startup_blood_tax_check", "occupancy", "replacement", "termination"},
        f"{label}.policy_inputs.concentration",
    )
    _choice(concentration["pressure"], {"endogenous_only"}, f"{label}.policy_inputs.concentration.pressure")
    _choice(
        concentration["startup_blood_tax_check"],
        {"exempt"},
        f"{label}.policy_inputs.concentration.startup_blood_tax_check",
    )
    _choice(
        concentration["occupancy"],
        {"one_controller_slot"},
        f"{label}.policy_inputs.concentration.occupancy",
    )
    _choice(
        concentration["replacement"],
        {"new_effect_ends_existing"},
        f"{label}.policy_inputs.concentration.replacement",
    )
    termination = _array(concentration["termination"], f"{label}.policy_inputs.concentration.termination", 1)
    termination_values = [
        _choice(item, _CONCENTRATION_TERMINATION, f"{label}.policy_inputs.concentration.termination[{index}]")
        for index, item in enumerate(termination)
    ]
    if len(termination_values) != len(set(termination_values)) or set(termination_values) != _CONCENTRATION_TERMINATION:
        raise AuthorityError(f"{label}.policy_inputs.concentration.termination must enumerate every canonical event once")

    mastery_rows = _array(contract["masteries"], f"{label}.masteries", 1)
    mastery_ids: list[str] = []
    for index, mastery_value in enumerate(mastery_rows):
        mastery_label = f"{label}.masteries[{index}]"
        mastery = _object(mastery_value, mastery_label)
        _exact_keys(mastery, {"mastery_id", "minimum_level", "trigger", "component"}, mastery_label)
        mastery_ids.append(_identifier_value(mastery["mastery_id"], f"{mastery_label}.mastery_id"))
        minimum_level = _integer(mastery["minimum_level"], f"{mastery_label}.minimum_level", 3)
        if minimum_level > 20:
            raise AuthorityError(f"{mastery_label}.minimum_level must not exceed 20")
        _event_array(mastery["trigger"], f"{mastery_label}.trigger", 1)
        _validate_component(mastery["component"], f"{mastery_label}.component")
    if len(mastery_ids) != len(set(mastery_ids)):
        raise AuthorityError(f"{label}.masteries contains duplicate mastery IDs")
    expected_mastery_ids = {"mastery_push", "mastery_sap", "mastery_slow"}
    if set(mastery_ids) != expected_mastery_ids:
        raise AuthorityError(f"{label}.masteries must define Push, Sap, and Slow exactly once")

    if mastery_rows != _EXPECTED_MASTERIES:
        raise AuthorityError(f"{label}.masteries must match the exact canonical mastery fixtures")
    tactical = _object(contract["tactical_master"], f"{label}.tactical_master")
    _exact_keys(
        tactical,
        {"minimum_level", "choice_mastery_ids", "choice_timing", "behavior"},
        f"{label}.tactical_master",
    )
    if _integer(tactical["minimum_level"], f"{label}.tactical_master.minimum_level") != 9:
        raise AuthorityError(f"{label}.tactical_master.minimum_level must be 9")
    choices = _id_array(tactical["choice_mastery_ids"], f"{label}.tactical_master.choice_mastery_ids", 3)
    if choices != ["mastery_push", "mastery_sap", "mastery_slow"] or set(choices) != set(mastery_ids):
        raise AuthorityError(f"{label}.tactical_master.choice_mastery_ids must reference the canonical choices")
    _choice(tactical["choice_timing"], {"declaration"}, f"{label}.tactical_master.choice_timing")
    _choice(tactical["behavior"], {"replaces_kinetic_mastery"}, f"{label}.tactical_master.behavior")

    ledger = _array(contract["ledger"], f"{label}.ledger", CONTROL_LEDGER_SIZE)
    if len(ledger) != CONTROL_LEDGER_SIZE:
        raise AuthorityError(f"{label}.ledger must contain exactly {CONTROL_LEDGER_SIZE} rows")
    counts = {"modeled": 0, "excluded_by_profile": 0, "unsupported_error": 0, "total": len(ledger)}
    keys: list[tuple[str, int]] = []
    effect_ids: list[str] = []
    modeled_summaries: dict[tuple[str, int], dict[str, Any]] = {}
    for index, row_value in enumerate(ledger):
        row_label = f"{label}.ledger[{index}]"
        row = _object(row_value, row_label)
        entity_id = _identifier_value(row.get("entity_id"), f"{row_label}.entity_id")
        tier = _integer(row.get("tier"), f"{row_label}.tier", 0)
        if tier not in {0, 1, 2}:
            raise AuthorityError(f"{row_label}.tier must be 0, 1, or 2")
        disposition = _choice(
            row.get("disposition"),
            {"modeled", "excluded_by_profile", "unsupported_error"},
            f"{row_label}.disposition",
        )
        key = (entity_id, tier)
        expected_disposition = (
            "modeled" if key in _CONTROL_MODELED_KEYS
            else "excluded_by_profile" if key in _CONTROL_EXCLUDED_REASONS
            else "unsupported_error"
        )
        if disposition != expected_disposition:
            raise AuthorityError(f"{row_label}.disposition does not match the canonical foundation")
        keys.append(key)
        counts[disposition] += 1
        if disposition == "modeled":
            _exact_keys(row, {"entity_id", "tier", "disposition", "model"}, row_label)
            summary = _validate_model(row["model"], entity_id, tier, f"{row_label}.model")
            effect_ids.append(summary["effect_id"])
            modeled_summaries[key] = summary
        elif disposition == "excluded_by_profile":
            _exact_keys(row, {"entity_id", "tier", "disposition", "profile_id", "reason"}, row_label)
            if _identifier_value(row["profile_id"], f"{row_label}.profile_id") != profile_id:
                raise AuthorityError(f"{row_label}.profile_id must match the active profile")
            reason = _choice(
                row["reason"],
                {
                    "selectable_advanced_training_disabled", "outside_headline_control_value",
                    "incoming_enemy_attacks_unmodeled",
                },
                f"{row_label}.reason",
            )
            if reason != _CONTROL_EXCLUDED_REASONS[key]:
                raise AuthorityError(f"{row_label}.reason does not match the canonical foundation")
        else:
            _exact_keys(row, {"entity_id", "tier", "disposition", "reason"}, row_label)
            _choice(row["reason"], {"pending_authority_population"}, f"{row_label}.reason")
    if len(keys) != len(set(keys)):
        raise AuthorityError(f"{label}.ledger contains duplicate entity/tier rows")
    if keys != sorted(keys):
        raise AuthorityError(f"{label}.ledger must be sorted by entity_id and then tier")
    if keys != list(_CONTROL_LEDGER_KEYS):
        raise AuthorityError(f"{label}.ledger does not cover the canonical 49 entity/tier rows")
    if len(effect_ids) != len(set(effect_ids)):
        raise AuthorityError(f"{label}.ledger contains duplicate modeled effect IDs")

    for (entity_id, tier), summary in modeled_summaries.items():
        source_tier = summary["source_tier"]
        if summary["inheritance_kind"] != "resolved" or source_tier is None:
            continue
        source = modeled_summaries.get((entity_id, source_tier))
        if source is None:
            continue
        missing_selectors = sorted(source["selector_ids"] - summary["selector_ids"])
        missing_components = sorted(source["component_ids"] - summary["component_ids"])
        if missing_selectors or missing_components:
            raise AuthorityError(
                f"{label}.ledger {entity_id}:T{tier} must retain inherited selector/component IDs; "
                f"selectors={missing_selectors}, components={missing_components}"
            )
    if counts != _CONTROL_COVERAGE:
        raise AuthorityError(f"{label}.ledger must preserve the canonical 9/14/26 coverage foundation")
    return counts, ledger

def validate_control_projection_v2(projection: Any) -> dict[str, Any]:
    """Validate a v2 control projection recursively without coercing any value."""

    root = _object(projection, "projection")
    _exact_keys(
        root,
        {
            "projection_version", "authority_path", "authority_sha256", "rules_version", "schema_version",
            "supported_level_range", "control_authority", "coverage",
        },
        "projection",
    )
    if root["projection_version"] != CONTROL_PROJECTION_VERSION:
        raise AuthorityError(
            f"Unsupported control projection version: {root['projection_version']!r}; "
            f"expected {CONTROL_PROJECTION_VERSION}"
        )
    authority_path = _string(root["authority_path"], "projection.authority_path")
    if not Path(authority_path).is_absolute():
        raise AuthorityError("projection.authority_path must be absolute")
    digest = _string(root["authority_sha256"], "projection.authority_sha256")
    if not _SHA256.fullmatch(digest):
        raise AuthorityError("projection.authority_sha256 must be a lowercase SHA-256 digest")
    for field in ("rules_version", "schema_version"):
        version = _string(root[field], f"projection.{field}")
        if not _SEMVER.fullmatch(version):
            raise AuthorityError(f"projection.{field} must be semantic version x.y.z")
    level_range = _object(root["supported_level_range"], "projection.supported_level_range")
    _exact_keys(level_range, {"minimum", "maximum"}, "projection.supported_level_range")
    minimum_level = _integer(level_range["minimum"], "projection.supported_level_range.minimum", 1)
    maximum_level = _integer(level_range["maximum"], "projection.supported_level_range.maximum", minimum_level)
    if (minimum_level, maximum_level) != (3, 20):
        raise AuthorityError("projection.supported_level_range must be Fighter levels 3 through 20")
    counts, _ = _validate_contract(root["control_authority"], "projection.control_authority")
    declared = _object(root["coverage"], "projection.coverage")
    _exact_keys(
        declared,
        {"modeled", "excluded_by_profile", "unsupported_error", "total", "benchmark_ready"},
        "projection.coverage",
    )
    for field in ("modeled", "excluded_by_profile", "unsupported_error", "total"):
        _integer(declared[field], f"projection.coverage.{field}", 0)
        if declared[field] != counts[field]:
            raise AuthorityError(
                f"projection.coverage.{field}={declared[field]} does not match ledger count {counts[field]}"
            )
    ready = _boolean(declared["benchmark_ready"], "projection.coverage.benchmark_ready")
    expected_ready = counts["unsupported_error"] == 0
    if ready != expected_ready:
        raise AuthorityError(
            "projection.coverage.benchmark_ready must equal whether unsupported_error coverage is zero"
        )
    return root


def load_control_projection_v2(authority_path: str | Path = DEFAULT_AUTHORITY) -> dict[str, Any]:
    """Request projection v2 explicitly and reject any malformed or legacy result."""

    return validate_control_projection_v2(_run_projector(authority_path, CONTROL_PROJECTION_VERSION))


@dataclass(frozen=True, init=False)
class ControlAuthorityV2Model:
    """Validated structured control authority, kept separate from the legacy model."""

    __projection: dict[str, Any]

    def __init__(self, projection: dict[str, Any]) -> None:
        snapshot = deepcopy(projection)
        validate_control_projection_v2(snapshot)
        object.__setattr__(self, "_ControlAuthorityV2Model__projection", snapshot)

    @property
    def projection(self) -> dict[str, Any]:
        return deepcopy(self.__projection)

    @classmethod
    def load(
        cls,
        authority_path: str | Path = DEFAULT_AUTHORITY,
        *,
        require_benchmark_ready: bool = False,
    ) -> "ControlAuthorityV2Model":
        model = cls(load_control_projection_v2(authority_path))
        if require_benchmark_ready:
            model.require_benchmark_ready()
        return model

    @property
    def control_authority(self) -> dict[str, Any]:
        return deepcopy(self.__projection["control_authority"])

    @property
    def contract(self) -> dict[str, Any]:
        return self.control_authority

    @property
    def ledger(self) -> list[dict[str, Any]]:
        return deepcopy(self.__projection["control_authority"]["ledger"])

    @property
    def modeled(self) -> list[dict[str, Any]]:
        return [row for row in self.ledger if row["disposition"] == "modeled"]

    @property
    def excluded_by_profile(self) -> list[dict[str, Any]]:
        return [row for row in self.ledger if row["disposition"] == "excluded_by_profile"]

    @property
    def unsupported(self) -> list[dict[str, Any]]:
        return [row for row in self.ledger if row["disposition"] == "unsupported_error"]

    @property
    def benchmark_ready(self) -> bool:
        return self.__projection["coverage"]["benchmark_ready"]

    def require_benchmark_ready(self) -> "ControlAuthorityV2Model":
        unsupported_count = sum(
            row["disposition"] == "unsupported_error"
            for row in self.__projection["control_authority"]["ledger"]
        )
        if not self.benchmark_ready or unsupported_count:
            raise AuthorityError(
                "Control benchmark is not ready: "
                f"{unsupported_count} ledger row(s) remain unsupported_error"
            )
        return self


def band_value(bands: list[dict[str, int]], level: int, label: str) -> int:
    matches = [band for band in bands if band["minimum_level"] <= level <= band["maximum_level"]]
    if len(matches) != 1:
        raise AuthorityError(f"{label} has {len(matches)} bands at Fighter level {level}; expected exactly one")
    return int(matches[0]["value"])


@dataclass(frozen=True)
class AuthorityModel:
    projection: dict[str, Any]

    @classmethod
    def load(cls, authority_path: str | Path = DEFAULT_AUTHORITY) -> "AuthorityModel":
        return cls(load_projection(authority_path))

    @property
    def rules_version(self) -> str:
        return str(self.projection["rules_version"])

    @property
    def authority_sha256(self) -> str:
        return str(self.projection["authority_sha256"])

    @property
    def disciplines(self) -> dict[str, dict[str, Any]]:
        rows = self.projection["disciplines"]
        return {str(row["id"]): row for row in rows}

    @property
    def features(self) -> dict[str, dict[str, Any]]:
        rows = self.projection["features"]
        result = {str(row["entity_id"]): row for row in rows}
        if len(result) != len(rows):
            raise AuthorityError("Projection contains duplicate feature entity IDs")
        return result

    def _derived_value(self, definition: dict[str, Any], level: int, psi_modifier: int) -> int:
        components = {
            "psionic_ability_modifier": psi_modifier,
            "proficiency_bonus": self.progression("proficiency_bonus", level),
            "psionic_focus": self.progression("psionic_focus", level),
        }
        try:
            return int(definition["base"]) + sum(components[name] for name in definition["components"])
        except KeyError as error:
            raise AuthorityError(f"Unsupported canonical derived-value component: {error.args[0]}") from error

    def kv_attack_bonus(self, level: int, psi_modifier: int) -> int:
        return self._derived_value(self.projection["core"]["manifested_strike"]["attack_bonus"], level, psi_modifier)

    def kv_save_dc(self, level: int, psi_modifier: int) -> int:
        return self._derived_value(self.projection["core"]["manifested_strike"]["save_dc"], level, psi_modifier)

    def blood_tax(self, level: int, tier: int) -> int:
        if tier not in {0, 1, 2}:
            raise AuthorityError(f"Unsupported Overload tier {tier}")
        rule = self.projection["core"]["overload"]["blood_tax_per_tier"]
        return int(rule["base"]) + tier * self.progression("proficiency_bonus", level) * int(rule["proficiency_bonus_multiplier"])

    def feature(self, entity_id: str, level: int, tier: int | None = None) -> dict[str, Any]:
        feature = self.features.get(entity_id)
        if feature is None:
            raise AuthorityError(f"Unknown harness feature entity ID: {entity_id}")
        if level < int(feature["minimum_level"]):
            raise AuthorityError(f"Feature {entity_id} is unavailable at Fighter level {level}")
        if tier is not None:
            minimums = {int(row["tier"]): int(row["minimum_level"]) for row in self.projection["progressions"]["tier_minimum_levels"]}
            if tier not in minimums:
                raise AuthorityError(f"Unsupported Overload tier {tier}")
            if level < minimums[tier]:
                raise AuthorityError(f"Tier {tier} is unavailable at Fighter level {level}")
        return feature

    def progression(self, name: str, level: int) -> int:
        bands = self.projection["progressions"].get(name)
        if not isinstance(bands, list):
            raise AuthorityError(f"Unknown progression: {name}")
        return band_value(bands, level, name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Kinetic Vanguard harness authority projection")
    parser.add_argument("--authority", default=str(DEFAULT_AUTHORITY), help="path to canonical authority YAML")
    parser.add_argument(
        "--projection-version",
        choices=(LEGACY_PROJECTION_VERSION, CONTROL_PROJECTION_VERSION),
        default=LEGACY_PROJECTION_VERSION,
        help="projection contract to request and validate",
    )
    parser.add_argument(
        "--require-benchmark-ready",
        action="store_true",
        help="fail when v2 still contains unsupported_error ledger rows",
    )
    args = parser.parse_args(argv)
    try:
        if args.projection_version == LEGACY_PROJECTION_VERSION:
            if args.require_benchmark_ready:
                raise AuthorityError("--require-benchmark-ready is only valid for projection version 2.0.0")
            projection = load_projection(args.authority)
            summary = {
                "projection_version": projection["projection_version"],
                "authority_sha256": projection["authority_sha256"],
                "valid": True,
            }
        else:
            model = ControlAuthorityV2Model.load(
                args.authority,
                require_benchmark_ready=args.require_benchmark_ready,
            )
            summary = {
                "projection_version": model.projection["projection_version"],
                "authority_sha256": model.projection["authority_sha256"],
                "coverage": model.projection["coverage"],
                "benchmark_ready": model.benchmark_ready,
                "valid": True,
            }
    except AuthorityError as error:
        parser.exit(1, f"authority validation failed: {error}\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
