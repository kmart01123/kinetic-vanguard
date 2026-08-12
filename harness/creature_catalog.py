"""Authoritative SRD 5.2.1 creature catalog and deterministic rosters.

Python owns this shared semantic validation layer. Consumer-specific target
projections live in sibling modules, so damage and control depend on the same
source without depending on one another.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG = HARNESS_ROOT / "data" / "srd_creatures.json"
DEFAULT_ROSTERS = HARNESS_ROOT / "data" / "srd_creature_rosters.json"
DEFAULT_PROVENANCE = HARNESS_ROOT / "provenance" / "srd-creatures.json"
DEFAULT_CONSUMER_REQUIREMENTS = HARNESS_ROOT / "config" / "creature-consumers.json"

CATALOG_CONTRACT_ID = "srd521_creature_catalog"
CATALOG_CONTRACT_VERSION = "1.0.0"
ROSTER_CONTRACT_ID = "srd521_creature_rosters"
ROSTER_CONTRACT_VERSION = "1.0.0"
PASSIVE_TRAIT_REGISTRY_ID = "srd521_passive_trait_registry"
PASSIVE_TRAIT_REGISTRY_VERSION = "1.0.0"
CONSUMER_REQUIREMENTS_ID = "srd521_creature_consumer_requirements"
CONSUMER_REQUIREMENTS_VERSION = "1.0.0"
ELIGIBILITY_POLICY_ID = "srd521_level_cr_closed_ranges_v1"
SELECTION_ALGORITHM_ID = "srd521_source_diversity_greedy_v1"
HEADLINE_PROFILE_ID = "srd521_headline_source_diversity_v1"
CENSUS_PROFILE_ID = "srd521_eligible_census_v1"
PROFILE_VERSION = "1.0.0"
PLANNER_PROJECTION_ID = "srd521_planner_static_target"
PLANNER_PROJECTION_VERSION = "1.0.0"

OFFICIAL_SOURCE_RULESET = "D&D SRD 5.2.1"
OFFICIAL_SOURCE_URL = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf"
OFFICIAL_SOURCE_SHA256 = "8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87"
OFFICIAL_SOURCE_BYTES = 6_031_375
OFFICIAL_SOURCE_PAGE_COUNT = 364
PROVENANCE_ID = "official_srd_5_2_1_creatures"

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SKILL_IDS = (
    "acrobatics", "animal_handling", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleight_of_hand", "stealth", "survival",
)
MOVEMENT_MODES = ("walk", "fly", "swim", "climb", "burrow")
SENSE_KINDS = ("darkvision", "blindsight", "tremorsense", "truesight")
BENCHMARK_LEVELS = (7, 11, 15, 20)
BANDS = {
    7: (Fraction(5), Fraction(8)),
    11: (Fraction(10), Fraction(13)),
    15: (Fraction(14), Fraction(16)),
    20: (Fraction(19), Fraction(30)),
}
EXPECTED_MODIFICATION_NOTICE = (
    "Selected source facts transcribed, structured, and normalized; no rules text reproduced."
)

_DISPOSITIONS = {"modeled_typed", "irrelevant", "retained_not_consumed"}
_IMPACT_AXES = {
    "attack_check_reaction_or_aura",
    "condition_targeting_or_visibility",
    "damage_hp_or_transition",
    "delayed_lifecycle_or_restoration",
    "form_equipment_or_source_choice",
    "movement_position_or_environment",
    "outgoing_utility_or_social",
    "save_or_result_conversion",
    "sense_communication_or_detection",
}
_SAVE_BASES = {"explicit_stat_block_save_column", "ordinary_ability_modifier_default"}
_GEAR_CATEGORIES = {"armor", "melee_weapon", "ranged_weapon", "shield", "spellcasting_focus", "tool"}
_LANGUAGE_MODES = {"speaks_and_understands", "understands_only"}
_CREATURE_SIZES = {"tiny", "small", "medium", "large", "huge", "gargantuan"}
_DAMAGE_TYPES = {
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
}
_CONDITIONS = {
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned", "prone",
    "restrained", "stunned", "unconscious",
}
_SCENARIO_FIELD_NAMES = {
    "airborne", "altitude", "available_route", "check_advantage_sources",
    "check_circumstances", "check_disadvantage_sources", "check_roll_mode",
    "concentration", "current_condition",
    "current_conditions", "current_hit_points", "current_position", "dropped", "held",
    "intent", "legal_disarming_attack_target", "line_of_sight", "occupying_hand",
    "reaction_available", "retrievable", "visibility_relation", "wielded", "worn",
}
_NULLABLE_REQUIRED_PATHS = {
    "communication.telepathy",
    "legendary_resistance.lair_uses_per_day",
}

_EXCLUDED_CREATURES = {
    "srd521:assassin": "unsupported_evasion_result_conversion",
    "srd521:flesh-golem": "unsupported_damage_absorption",
    "srd521:half-dragon": "unresolved_draconic_origin_choice",
    "srd521:invisible-stalker": "unsupported_static_invisibility",
    "srd521:iron-golem": "unsupported_damage_absorption",
    "srd521:rakshasa": "unsupported_greater_magic_resistance",
    "srd521:shambling-mound": "unsupported_damage_absorption",
    "srd521:tarrasque": "unsupported_reflective_carapace",
}
_TARGETING_TRAITS = {
    "greater_magic_resistance": {
        "spell_attack_automatic_miss",
        "remote_observation_requires_permission",
        "thought_detection_requires_permission",
    },
    "inscrutable": {
        "remote_observation_requires_permission",
        "thought_detection_requires_permission",
    },
    "invisibility": {"static_invisible"},
    "reflective_carapace": {"magic_missile_or_ranged_spell_attack_deflection"},
    "transparent": {"visually_indistinguishable_while_still"},
}
_DEDICATED_TRAIT_IDS = {"magic_resistance", "legendary_resistance", *_TARGETING_TRAITS}

_XP_BY_CR = {
    Fraction(0): 10,
    Fraction(1, 8): 25,
    Fraction(1, 4): 50,
    Fraction(1, 2): 100,
    Fraction(1): 200,
    Fraction(2): 450,
    Fraction(3): 700,
    Fraction(4): 1_100,
    Fraction(5): 1_800,
    Fraction(6): 2_300,
    Fraction(7): 2_900,
    Fraction(8): 3_900,
    Fraction(9): 5_000,
    Fraction(10): 5_900,
    Fraction(11): 7_200,
    Fraction(12): 8_400,
    Fraction(13): 10_000,
    Fraction(14): 11_500,
    Fraction(15): 13_000,
    Fraction(16): 15_000,
    Fraction(17): 18_000,
    Fraction(18): 20_000,
    Fraction(19): 22_000,
    Fraction(20): 25_000,
    Fraction(21): 33_000,
    Fraction(22): 41_000,
    Fraction(23): 50_000,
    Fraction(24): 62_000,
    Fraction(25): 75_000,
    Fraction(26): 90_000,
    Fraction(27): 105_000,
    Fraction(28): 120_000,
    Fraction(29): 135_000,
    Fraction(30): 155_000,
}


class CreatureCatalogError(ValueError):
    """Raised when a catalog, roster, provenance, or projection fails closed."""


@dataclass(frozen=True, init=False)
class CreatureCatalog:
    records: tuple[Mapping[str, Any], ...]
    by_id: Mapping[str, Mapping[str, Any]]
    contract_id: str
    contract_version: str
    sha256: str
    source_url: str
    source_sha256: str
    provenance: Mapping[str, Any]

    def __init__(self) -> None:
        raise CreatureCatalogError(
            "CreatureCatalog must be created by the validated catalog loader"
        )

    def __post_init__(self) -> None:
        if type(self.by_id) is not MappingProxyType or any(
            not isinstance(record, Mapping) for record in self.records
        ):
            raise CreatureCatalogError(
                "CreatureCatalog must be created by the validated catalog loader"
            )
        if tuple(self.by_id.values()) != self.records:
            raise CreatureCatalogError(
                "Creature catalog ID index disagrees with its immutable records"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise CreatureCatalogError("Creature catalog SHA-256 must be lower-case hexadecimal")

    def creature(self, creature_id: str) -> Mapping[str, Any]:
        try:
            return self.by_id[creature_id]
        except KeyError as error:
            raise CreatureCatalogError(f"Unknown creature_id {creature_id!r}") from error


@dataclass(frozen=True)
class ConsumerRequirements:
    data: Mapping[str, Any]
    registry_sha256: str
    consumer_sha256_by_id: Mapping[str, str]

    def __post_init__(self) -> None:
        frozen_data = _deep_freeze(self.data)
        recomputed = consumer_requirements_sha256_by_id(frozen_data)
        if dict(self.consumer_sha256_by_id) != dict(recomputed):
            raise CreatureCatalogError(
                "Consumer requirement digests disagree with their canonical payloads"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.registry_sha256):
            raise CreatureCatalogError(
                "Consumer requirement registry SHA-256 must be lower-case hexadecimal"
            )
        object.__setattr__(self, "data", frozen_data)
        object.__setattr__(self, "consumer_sha256_by_id", recomputed)

    def consumer(self, consumer_id: str) -> Mapping[str, Any]:
        try:
            return self.data["consumers"][consumer_id]
        except KeyError as error:
            raise CreatureCatalogError(f"Unknown creature consumer {consumer_id!r}") from error

    def sha256_for(self, consumer_id: str) -> str:
        try:
            stored = self.consumer_sha256_by_id[consumer_id]
        except KeyError as error:
            raise CreatureCatalogError(f"Unknown creature consumer {consumer_id!r}") from error
        recomputed = consumer_requirements_sha256_by_id(self.data)[consumer_id]
        if stored != recomputed:
            raise CreatureCatalogError(
                f"Creature consumer {consumer_id!r} changed after identity derivation"
            )
        return stored


@dataclass(frozen=True)
class RosterEntry:
    creature_id: str
    benchmark_level: int
    eligibility_policy_id: str
    profile_id: str
    profile_version: str
    weight: Fraction
    purpose: str
    profile_order: int
    catalog_sha256: str
    roster_sha256: str
    profile_sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        _json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _deep_freeze(value: Any) -> Any:
    """Recursively make validated source and contract values immutable."""

    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def consumer_requirements_sha256_by_id(
    data: Mapping[str, Any],
) -> Mapping[str, str]:
    """Derive isolated canonical identities from a requirement-registry payload."""

    consumers = data["consumers"]
    return MappingProxyType({
        consumer_id: canonical_sha256({
            "consumer_requirements_contract": data["contract"],
            "catalog_contract": data["catalog_contract"],
            "passive_trait_registry": data["passive_trait_registry"],
            "scenario_state_boundary": data["scenario_state_boundary"],
            "consumer_id": consumer_id,
            "consumer": consumers[consumer_id],
        })
        for consumer_id in sorted(consumers)
    })


def _json_safe(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_safe(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_json_safe(item) for item in value)
    return value


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CreatureCatalogError(f"JSON object contains duplicate key {key!r}")
        output[key] = value
    return output


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_duplicate_rejecting_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CreatureCatalogError(f"Unable to load {label} from {path}: {error}") from error
    return _object(value, label)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CreatureCatalogError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CreatureCatalogError(f"{label} must be an array")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing or unknown:
        raise CreatureCatalogError(
            f"{label} keys are invalid; missing={missing}, unknown={unknown}"
        )


def _string(value: Any, label: str, *, lower: bool = False) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CreatureCatalogError(f"{label} must be a non-empty trimmed string")
    if "\n" in value or "\r" in value:
        raise CreatureCatalogError(f"{label} must be compact single-line text")
    if lower and value != value.lower():
        raise CreatureCatalogError(f"{label} must be lower-case normalized text")
    return value


def _optional_string(value: Any, label: str, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    return _string(value, label, lower=lower)


def _integer(value: Any, label: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CreatureCatalogError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise CreatureCatalogError(f"{label} must be at least {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise CreatureCatalogError(f"{label} must be a boolean")
    return value


def _string_array(
    value: Any,
    label: str,
    *,
    lower: bool = False,
    nonempty: bool = False,
    canonical: bool = False,
) -> list[str]:
    rows = _array(value, label)
    if nonempty and not rows:
        raise CreatureCatalogError(f"{label} must not be empty")
    output = [_string(item, f"{label}[{index}]", lower=lower) for index, item in enumerate(rows)]
    if len(output) != len(set(output)):
        raise CreatureCatalogError(f"{label} contains duplicates")
    if canonical and output != sorted(output):
        raise CreatureCatalogError(f"{label} must use canonical ordering")
    return output


def _ratio(value: Any, label: str, *, allow_zero: bool = False) -> Fraction:
    row = _object(value, label)
    _exact_keys(row, {"numerator", "denominator"}, label)
    numerator = _integer(row["numerator"], f"{label}.numerator", 0 if allow_zero else 1)
    denominator = _integer(row["denominator"], f"{label}.denominator", 1)
    fraction = Fraction(numerator, denominator)
    if (fraction.numerator, fraction.denominator) != (numerator, denominator):
        raise CreatureCatalogError(f"{label} must be a reduced exact rational")
    return fraction


def _ratio_dict(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _slug(display_name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_name.lower())).strip("-")


def _expected_pb(challenge: Fraction) -> int:
    if challenge <= 4:
        return 2
    return min(9, 2 + math.ceil((int(challenge) - 4) / 4))


def _validate_contract(value: Any, label: str, contract_id: str, version: str) -> None:
    row = _object(value, label)
    _exact_keys(row, {"id", "version"}, label)
    if row != {"id": contract_id, "version": version}:
        raise CreatureCatalogError(f"Unsupported {label}: {row!r}")


def _validate_passive_registry(value: Any) -> dict[str, Mapping[str, Any]]:
    label = "catalog.passive_trait_registry"
    row = _object(value, label)
    _exact_keys(
        row,
        {
            "id", "version", "source_heading_count", "source_occurrence_count",
            "definitions", "irrelevant_reason_ids", "retained_reason_ids",
        },
        label,
    )
    if row["id"] != PASSIVE_TRAIT_REGISTRY_ID or row["version"] != PASSIVE_TRAIT_REGISTRY_VERSION:
        raise CreatureCatalogError("Unsupported passive-trait registry contract")
    heading_count = _integer(row["source_heading_count"], f"{label}.source_heading_count", 1)
    _integer(row["source_occurrence_count"], f"{label}.source_occurrence_count", 0)
    irrelevant = _string_array(row["irrelevant_reason_ids"], f"{label}.irrelevant_reason_ids", lower=True, canonical=True)
    retained = _string_array(row["retained_reason_ids"], f"{label}.retained_reason_ids", lower=True, canonical=True)
    if not irrelevant or not retained:
        raise CreatureCatalogError("Passive-trait reason registries must be closed and non-empty")
    definitions = _array(row["definitions"], f"{label}.definitions")
    by_id: dict[str, Mapping[str, Any]] = {}
    headings: set[str] = set()
    for index, item in enumerate(definitions):
        item_label = f"{label}.definitions[{index}]"
        definition = _object(item, item_label)
        _exact_keys(
            definition,
            {"trait_id", "source_headings", "impact_axes", "disposition", "reason_id"},
            item_label,
        )
        trait_id = _string(definition["trait_id"], f"{item_label}.trait_id", lower=True)
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", trait_id):
            raise CreatureCatalogError(f"{item_label}.trait_id is not a canonical ID")
        if trait_id in by_id:
            raise CreatureCatalogError(f"Duplicate passive trait_id {trait_id!r}")
        source_headings = _string_array(
            definition["source_headings"], f"{item_label}.source_headings", nonempty=True, canonical=True
        )
        overlap = headings.intersection(source_headings)
        if overlap:
            raise CreatureCatalogError(f"Passive source headings are ambiguous: {sorted(overlap)}")
        headings.update(source_headings)
        impact_axes = _string_array(
            definition["impact_axes"], f"{item_label}.impact_axes", lower=True, nonempty=True, canonical=True
        )
        unknown_axes = sorted(set(impact_axes) - _IMPACT_AXES)
        if unknown_axes:
            raise CreatureCatalogError(f"{item_label} has unknown impact axes {unknown_axes}")
        disposition = _string(definition["disposition"], f"{item_label}.disposition", lower=True)
        if disposition not in _DISPOSITIONS:
            raise CreatureCatalogError(f"{item_label} has unknown disposition {disposition!r}")
        reason = _optional_string(definition["reason_id"], f"{item_label}.reason_id", lower=True)
        expected_reasons = irrelevant if disposition == "irrelevant" else retained if disposition == "retained_not_consumed" else []
        if (disposition == "modeled_typed" and reason is not None) or (
            disposition != "modeled_typed" and reason not in expected_reasons
        ):
            raise CreatureCatalogError(f"{item_label} has an invalid closed reason disposition")
        by_id[trait_id] = definition
    if list(by_id) != sorted(by_id):
        raise CreatureCatalogError("Passive-trait definitions must use canonical trait_id order")
    if len(headings) != heading_count:
        raise CreatureCatalogError("Passive-trait source_heading_count is inconsistent")
    return by_id


def _validate_defense_atom(value: Any, label: str, field: str) -> None:
    row = _object(value, label)
    base = {field, "qualifier_id", "qualifier"}
    if field == "damage_type" and field in row and row[field] is None:
        base.add("choices")
    _exact_keys(row, base, label)
    item = row[field]
    choices: list[str] = []
    if item is None:
        if field != "damage_type":
            raise CreatureCatalogError(f"{label}.{field} must not be null")
        choices = _string_array(row["choices"], f"{label}.choices", lower=True, nonempty=True, canonical=True)
    else:
        _string(item, f"{label}.{field}", lower=True)
        allowed = _DAMAGE_TYPES if field == "damage_type" else _CONDITIONS
        if item not in allowed:
            raise CreatureCatalogError(f"{label}.{field} is unknown: {item!r}")
    if choices and not set(choices).issubset(_DAMAGE_TYPES):
        raise CreatureCatalogError(f"{label}.choices contains an unknown damage type")
    qualifier_id = _optional_string(row["qualifier_id"], f"{label}.qualifier_id", lower=True)
    qualifier = _optional_string(row["qualifier"], f"{label}.qualifier")
    if (qualifier_id is None) != (qualifier is None):
        raise CreatureCatalogError(f"{label} qualifier_id and qualifier must appear together")
    if item is None and qualifier_id is None:
        raise CreatureCatalogError(f"{label} unresolved choice requires a qualifier")


def _validate_creature(
    value: Any,
    index: int,
    trait_definitions: Mapping[str, Mapping[str, Any]],
) -> tuple[str, int, int, int]:
    label = f"catalog.creatures[{index}]"
    row = _object(value, label)
    _exact_keys(
        row,
        {
            "creature_id", "display_name", "source_variant_tags", "source", "challenge",
            "classification", "armor_class", "hit_points", "abilities", "skills",
            "passive_perception", "initiative", "movement", "senses", "communication",
            "defenses", "magic_resistance", "legendary_resistance", "gear", "passive_traits",
        },
        label,
    )
    creature_id = _string(row["creature_id"], f"{label}.creature_id", lower=True)
    display_name = _string(row["display_name"], f"{label}.display_name")
    if creature_id != f"srd521:{_slug(display_name)}":
        raise CreatureCatalogError(f"{label}.creature_id is not deterministic from display_name")
    _string_array(row["source_variant_tags"], f"{label}.source_variant_tags", lower=True, canonical=True)

    source = _object(row["source"], f"{label}.source")
    _exact_keys(source, {"ruleset", "page", "stat_block_order", "stat_block_anchor", "modification_notice"}, f"{label}.source")
    if source["ruleset"] != OFFICIAL_SOURCE_RULESET:
        raise CreatureCatalogError(f"{label}.source.ruleset is unsupported")
    page = _integer(source["page"], f"{label}.source.page", 258)
    if page > 364:
        raise CreatureCatalogError(f"{label}.source.page is outside the source stat-block section")
    source_order = _integer(source["stat_block_order"], f"{label}.source.stat_block_order", 1)
    anchor = _string(source["stat_block_anchor"], f"{label}.source.stat_block_anchor", lower=True)
    if anchor != f"p{page}-o{source_order:03d}":
        raise CreatureCatalogError(f"{label}.source.stat_block_anchor disagrees with page/order")
    if source["modification_notice"] != EXPECTED_MODIFICATION_NOTICE:
        raise CreatureCatalogError(f"{label}.source.modification_notice is unsupported")

    challenge = _object(row["challenge"], f"{label}.challenge")
    _exact_keys(challenge, {"rating", "canonical", "xp", "xp_alternatives", "proficiency_bonus", "source_anomaly_id"}, f"{label}.challenge")
    rating = _ratio(challenge["rating"], f"{label}.challenge.rating", allow_zero=True)
    if rating not in _XP_BY_CR:
        raise CreatureCatalogError(f"{label}.challenge.rating is outside the supported CR table")
    canonical_cr = str(rating.numerator) if rating.denominator == 1 else f"{rating.numerator}/{rating.denominator}"
    if challenge["canonical"] != canonical_cr:
        raise CreatureCatalogError(f"{label}.challenge.canonical disagrees with its rational")
    xp = _integer(challenge["xp"], f"{label}.challenge.xp", 0)
    anomaly = _optional_string(challenge["source_anomaly_id"], f"{label}.challenge.source_anomaly_id", lower=True)
    expected_xp = _XP_BY_CR[rating]
    xp_is_standard = xp == expected_xp or (rating == 0 and xp == 0)
    if not xp_is_standard:
        if not (
            creature_id == "srd521:archmage"
            and rating == 12
            and xp == 8_000
            and anomaly == "source_printed_xp_8000_for_cr12"
        ):
            raise CreatureCatalogError(f"{label}.challenge.xp is inconsistent with CR")
    elif anomaly is not None:
        raise CreatureCatalogError(f"{label}.challenge.source_anomaly_id is unexplained")
    if _integer(challenge["proficiency_bonus"], f"{label}.challenge.proficiency_bonus", 2) != _expected_pb(rating):
        raise CreatureCatalogError(f"{label}.challenge.proficiency_bonus is inconsistent with CR")
    xp_alternatives = _array(challenge["xp_alternatives"], f"{label}.challenge.xp_alternatives")
    seen_xp_qualifiers: set[str] = set()
    for alt_index, item in enumerate(xp_alternatives):
        alt_label = f"{label}.challenge.xp_alternatives[{alt_index}]"
        alt = _object(item, alt_label)
        _exact_keys(alt, {"xp", "qualifier_id"}, alt_label)
        _integer(alt["xp"], f"{alt_label}.xp", 1)
        qualifier_id = _string(alt["qualifier_id"], f"{alt_label}.qualifier_id", lower=True)
        if qualifier_id in seen_xp_qualifiers:
            raise CreatureCatalogError(f"{label}.challenge.xp_alternatives has duplicate qualifiers")
        seen_xp_qualifiers.add(qualifier_id)

    classification = _object(row["classification"], f"{label}.classification")
    _exact_keys(classification, {"sizes", "swarm_of_size", "creature_type", "tags", "alignment"}, f"{label}.classification")
    sizes = _string_array(classification["sizes"], f"{label}.classification.sizes", lower=True, nonempty=True)
    if not set(sizes).issubset(_CREATURE_SIZES):
        raise CreatureCatalogError(f"{label}.classification.sizes contains an unknown size")
    swarm = _optional_string(classification["swarm_of_size"], f"{label}.classification.swarm_of_size", lower=True)
    if swarm is not None and swarm not in _CREATURE_SIZES:
        raise CreatureCatalogError(f"{label}.classification.swarm_of_size is unknown")
    _string(classification["creature_type"], f"{label}.classification.creature_type", lower=True)
    _string_array(classification["tags"], f"{label}.classification.tags", lower=True, canonical=True)
    _string(classification["alignment"], f"{label}.classification.alignment")

    armor = _object(row["armor_class"], f"{label}.armor_class")
    _exact_keys(armor, {"default", "alternatives", "qualifiers", "resolution"}, f"{label}.armor_class")
    _integer(armor["default"], f"{label}.armor_class.default", 1)
    alternatives = _array(armor["alternatives"], f"{label}.armor_class.alternatives")
    qualifiers = _array(armor["qualifiers"], f"{label}.armor_class.qualifiers")
    if alternatives or qualifiers:
        raise CreatureCatalogError("Catalog AC alternative schema requires a contract extension before use")
    if armor["resolution"] != "resolved":
        raise CreatureCatalogError(f"{label}.armor_class.resolution is unresolved")

    hp = _object(row["hit_points"], f"{label}.hit_points")
    _exact_keys(hp, {"average", "hit_dice", "qualifier"}, f"{label}.hit_points")
    _integer(hp["average"], f"{label}.hit_points.average", 1)
    _string(hp["hit_dice"], f"{label}.hit_points.hit_dice")
    _optional_string(hp["qualifier"], f"{label}.hit_points.qualifier")

    abilities = _object(row["abilities"], f"{label}.abilities")
    _exact_keys(abilities, set(ABILITIES), f"{label}.abilities")
    for ability in ABILITIES:
        ability_label = f"{label}.abilities.{ability}"
        fact = _object(abilities[ability], ability_label)
        _exact_keys(fact, {"score", "modifier", "save_bonus", "save_basis", "source_anomaly_id"}, ability_label)
        score = _integer(fact["score"], f"{ability_label}.score", 1)
        modifier = _integer(fact["modifier"], f"{ability_label}.modifier")
        if modifier != math.floor((score - 10) / 2):
            raise CreatureCatalogError(f"{ability_label}.modifier is inconsistent with score")
        save_bonus = _integer(fact["save_bonus"], f"{ability_label}.save_bonus")
        save_basis = _string(fact["save_basis"], f"{ability_label}.save_basis", lower=True)
        if save_basis not in _SAVE_BASES:
            raise CreatureCatalogError(f"{ability_label}.save_basis is unknown")
        if save_basis == "ordinary_ability_modifier_default" and save_bonus != modifier:
            raise CreatureCatalogError(f"{ability_label}.default save must equal its ability modifier")
        save_anomaly = _optional_string(fact["source_anomaly_id"], f"{ability_label}.source_anomaly_id", lower=True)
        if save_anomaly is not None and not (
            creature_id == "srd521:young-white-dragon"
            and ability == "intelligence"
            and save_anomaly == "source_unsigned_final_save_token"
        ):
            raise CreatureCatalogError(f"{ability_label}.source_anomaly_id is unsupported")

    skills = _array(row["skills"], f"{label}.skills")
    seen_skills: set[str] = set()
    skill_ids: list[str] = []
    for skill_index, item in enumerate(skills):
        skill_label = f"{label}.skills[{skill_index}]"
        skill = _object(item, skill_label)
        _exact_keys(skill, {"skill", "bonus"}, skill_label)
        skill_id = _string(skill["skill"], f"{skill_label}.skill", lower=True)
        if skill_id not in SKILL_IDS:
            raise CreatureCatalogError(f"{skill_label}.skill is unknown: {skill_id!r}")
        _integer(skill["bonus"], f"{skill_label}.bonus")
        if skill_id in seen_skills:
            raise CreatureCatalogError(f"{label}.skills contains duplicate skill {skill_id!r}")
        seen_skills.add(skill_id)
        skill_ids.append(skill_id)
    if skill_ids != sorted(skill_ids):
        raise CreatureCatalogError(f"{label}.skills must use canonical skill ordering")
    _integer(row["passive_perception"], f"{label}.passive_perception", 0)

    initiative = _object(row["initiative"], f"{label}.initiative")
    _exact_keys(initiative, {"modifier", "score", "advantage", "qualifier"}, f"{label}.initiative")
    modifier = _integer(initiative["modifier"], f"{label}.initiative.modifier")
    score = _integer(initiative["score"], f"{label}.initiative.score")
    advantage = _boolean(initiative["advantage"], f"{label}.initiative.advantage")
    _optional_string(initiative["qualifier"], f"{label}.initiative.qualifier")
    expected_initiative_score = modifier + (15 if advantage else 10)
    if score != expected_initiative_score:
        raise CreatureCatalogError(
            f"{label}.initiative.score is inconsistent with its modifier/Advantage fact"
        )
    if advantage and creature_id not in {"srd521:gray-ooze", "srd521:invisible-stalker"}:
        raise CreatureCatalogError(
            f"{label}.initiative.advantage is not in the source-backed closed set"
        )

    movement = _object(row["movement"], f"{label}.movement")
    _exact_keys(movement, {"modes", "hover", "choice_groups"}, f"{label}.movement")
    modes = _object(movement["modes"], f"{label}.movement.modes")
    _exact_keys(modes, set(MOVEMENT_MODES), f"{label}.movement.modes")
    choice_groups = _array(movement["choice_groups"], f"{label}.movement.choice_groups")
    groups: dict[str, set[str]] = {}
    for group_index, item in enumerate(choice_groups):
        group_label = f"{label}.movement.choice_groups[{group_index}]"
        group = _object(item, group_label)
        _exact_keys(group, {"choice_group_id", "modes", "qualifier"}, group_label)
        group_id = _string(group["choice_group_id"], f"{group_label}.choice_group_id", lower=True)
        group_modes = _string_array(group["modes"], f"{group_label}.modes", lower=True, nonempty=True, canonical=True)
        if not set(group_modes).issubset(MOVEMENT_MODES):
            raise CreatureCatalogError(f"{group_label}.modes contains an unknown mode")
        _string(group["qualifier"], f"{group_label}.qualifier")
        if group_id in groups:
            raise CreatureCatalogError(f"{label}.movement has duplicate choice_group_id")
        groups[group_id] = set(group_modes)
    for mode in MOVEMENT_MODES:
        facts = _array(modes[mode], f"{label}.movement.modes.{mode}")
        for fact_index, item in enumerate(facts):
            fact_label = f"{label}.movement.modes.{mode}[{fact_index}]"
            fact = _object(item, fact_label)
            _exact_keys(fact, {"feet", "qualifier", "choice_group_id"}, fact_label)
            _integer(fact["feet"], f"{fact_label}.feet", 1)
            qualifier = _optional_string(fact["qualifier"], f"{fact_label}.qualifier")
            group_id = _optional_string(fact["choice_group_id"], f"{fact_label}.choice_group_id", lower=True)
            if group_id is not None and (group_id not in groups or mode not in groups[group_id]):
                raise CreatureCatalogError(f"{fact_label}.choice_group_id is inconsistent")
            if group_id is not None and qualifier is None:
                raise CreatureCatalogError(f"{fact_label} choice group requires a qualifier")
    hover = _boolean(movement["hover"], f"{label}.movement.hover")
    if hover and not modes["fly"]:
        raise CreatureCatalogError(f"{label}.movement.hover requires a fly speed")

    senses = _object(row["senses"], f"{label}.senses")
    _exact_keys(senses, set(SENSE_KINDS), f"{label}.senses")
    for kind in SENSE_KINDS:
        facts = _array(senses[kind], f"{label}.senses.{kind}")
        seen_sense_facts: set[tuple[int, str | None]] = set()
        for fact_index, item in enumerate(facts):
            fact_label = f"{label}.senses.{kind}[{fact_index}]"
            fact = _object(item, fact_label)
            _exact_keys(fact, {"range_feet", "limitation"}, fact_label)
            sense_key = (
                _integer(fact["range_feet"], f"{fact_label}.range_feet", 1),
                _optional_string(fact["limitation"], f"{fact_label}.limitation"),
            )
            if sense_key in seen_sense_facts:
                raise CreatureCatalogError(f"{label}.senses.{kind} contains a duplicate fact")
            seen_sense_facts.add(sense_key)

    communication = _object(row["communication"], f"{label}.communication")
    _exact_keys(communication, {"source_expression", "languages", "all_languages", "additional_language_count", "telepathy", "limitations"}, f"{label}.communication")
    _string(communication["source_expression"], f"{label}.communication.source_expression")
    languages = _array(communication["languages"], f"{label}.communication.languages")
    seen_languages: set[tuple[str, str, str | None]] = set()
    for language_index, item in enumerate(languages):
        language_label = f"{label}.communication.languages[{language_index}]"
        language = _object(item, language_label)
        _exact_keys(language, {"identity", "mode", "limitation_id"}, language_label)
        language_key = (
            _string(language["identity"], f"{language_label}.identity"),
            _string(language["mode"], f"{language_label}.mode", lower=True),
            _optional_string(language["limitation_id"], f"{language_label}.limitation_id", lower=True),
        )
        if language_key[1] not in _LANGUAGE_MODES:
            raise CreatureCatalogError(f"{language_label}.mode is unknown")
        if language_key in seen_languages:
            raise CreatureCatalogError(f"{label}.communication.languages contains a duplicate")
        seen_languages.add(language_key)
    _boolean(communication["all_languages"], f"{label}.communication.all_languages")
    _integer(communication["additional_language_count"], f"{label}.communication.additional_language_count", 0)
    limitations = _string_array(communication["limitations"], f"{label}.communication.limitations", lower=True, canonical=True)
    telepathy = communication["telepathy"]
    if telepathy is not None:
        telepathy_label = f"{label}.communication.telepathy"
        telepathy_row = _object(telepathy, telepathy_label)
        _exact_keys(telepathy_row, {"range_feet", "limitation_id", "limitation"}, telepathy_label)
        _integer(telepathy_row["range_feet"], f"{telepathy_label}.range_feet", 1)
        limitation_id = _optional_string(telepathy_row["limitation_id"], f"{telepathy_label}.limitation_id", lower=True)
        limitation = _optional_string(telepathy_row["limitation"], f"{telepathy_label}.limitation")
        if (limitation_id is None) != (limitation is None):
            raise CreatureCatalogError(f"{telepathy_label} limitation fields must appear together")

    defenses = _object(row["defenses"], f"{label}.defenses")
    _exact_keys(defenses, {"damage_resistances", "damage_immunities", "damage_vulnerabilities", "condition_immunities"}, f"{label}.defenses")
    for family in ("damage_resistances", "damage_immunities", "damage_vulnerabilities"):
        facts = _array(defenses[family], f"{label}.defenses.{family}")
        for fact_index, item in enumerate(facts):
            _validate_defense_atom(item, f"{label}.defenses.{family}[{fact_index}]", "damage_type")
    conditions = _array(defenses["condition_immunities"], f"{label}.defenses.condition_immunities")
    for fact_index, item in enumerate(conditions):
        _validate_defense_atom(item, f"{label}.defenses.condition_immunities[{fact_index}]", "condition")

    magic_resistance = _object(row["magic_resistance"], f"{label}.magic_resistance")
    _exact_keys(magic_resistance, {"present", "trait_id"}, f"{label}.magic_resistance")
    present = _boolean(magic_resistance["present"], f"{label}.magic_resistance.present")
    trait_id = _optional_string(magic_resistance["trait_id"], f"{label}.magic_resistance.trait_id", lower=True)
    if trait_id != ("magic_resistance" if present else None):
        raise CreatureCatalogError(f"{label}.magic_resistance trait identity is inconsistent")

    legendary = _object(row["legendary_resistance"], f"{label}.legendary_resistance")
    _exact_keys(legendary, {"uses_per_day", "lair_uses_per_day", "policy"}, f"{label}.legendary_resistance")
    uses = _integer(legendary["uses_per_day"], f"{label}.legendary_resistance.uses_per_day", 0)
    lair = legendary["lair_uses_per_day"]
    if lair is not None:
        lair = _integer(lair, f"{label}.legendary_resistance.lair_uses_per_day", 1)
        if lair <= uses:
            raise CreatureCatalogError(f"{label}.legendary_resistance lair count must exceed base count")
    if legendary["policy"] != "metadata_only":
        raise CreatureCatalogError(f"{label}.legendary_resistance.policy is unsupported")

    gear = _array(row["gear"], f"{label}.gear")
    for gear_index, item in enumerate(gear):
        gear_label = f"{label}.gear[{gear_index}]"
        fact = _object(item, gear_label)
        _exact_keys(fact, {"name", "quantity", "category"}, gear_label)
        _string(fact["name"], f"{gear_label}.name")
        _integer(fact["quantity"], f"{gear_label}.quantity", 1)
        category = _string(fact["category"], f"{gear_label}.category", lower=True)
        if category not in _GEAR_CATEGORIES:
            raise CreatureCatalogError(f"{gear_label}.category is unknown")

    passive_traits = _array(row["passive_traits"], f"{label}.passive_traits")
    seen_headings: set[str] = set()
    for trait_index, item in enumerate(passive_traits):
        trait_label = f"{label}.passive_traits[{trait_index}]"
        trait = _object(item, trait_label)
        _exact_keys(trait, {"source_heading", "parent_source_heading", "trait_id", "disposition", "reason_id", "parameters"}, trait_label)
        heading = _string(trait["source_heading"], f"{trait_label}.source_heading")
        if heading in seen_headings:
            raise CreatureCatalogError(f"{label}.passive_traits contains duplicate source heading")
        seen_headings.add(heading)
        _optional_string(trait["parent_source_heading"], f"{trait_label}.parent_source_heading")
        occurrence_id = _string(trait["trait_id"], f"{trait_label}.trait_id", lower=True)
        try:
            definition = trait_definitions[occurrence_id]
        except KeyError as error:
            raise CreatureCatalogError(f"{trait_label} uses unknown potentially material trait {occurrence_id!r}") from error
        if heading not in definition["source_headings"]:
            raise CreatureCatalogError(f"{trait_label}.source_heading is not registered for {occurrence_id!r}")
        if trait["disposition"] != definition["disposition"] or trait["reason_id"] != definition["reason_id"]:
            raise CreatureCatalogError(f"{trait_label} disposition disagrees with the closed registry")
        parameters = _object(trait["parameters"], f"{trait_label}.parameters")
        unknown_parameters = sorted(set(parameters) - {"uses_per_day", "lair_uses_per_day", "policy"})
        if unknown_parameters:
            raise CreatureCatalogError(f"{trait_label}.parameters has unknown keys {unknown_parameters}")
        for key, parameter in parameters.items():
            if key == "policy":
                if parameter != "metadata_only":
                    raise CreatureCatalogError(f"{trait_label}.parameters.policy is unsupported")
            elif parameter is not None:
                _integer(parameter, f"{trait_label}.parameters.{key}", 1)
    typed_ids = {item["trait_id"] for item in passive_traits if item["disposition"] == "modeled_typed"}
    if present != ("magic_resistance" in typed_ids):
        raise CreatureCatalogError(f"{label}.magic_resistance disagrees with passive traits")
    if uses != (next((item["parameters"].get("uses_per_day", 0) for item in passive_traits if item["trait_id"] == "legendary_resistance"), 0)):
        raise CreatureCatalogError(f"{label}.legendary_resistance disagrees with passive traits")
    return creature_id, page, source_order, len(passive_traits)


def _validate_catalog_data(data: dict[str, Any]) -> None:
    _exact_keys(data, {"contract", "provenance_id", "source_ruleset", "source_stat_block_count", "passive_trait_registry", "creatures"}, "catalog")
    _validate_contract(data["contract"], "catalog.contract", CATALOG_CONTRACT_ID, CATALOG_CONTRACT_VERSION)
    if data["provenance_id"] != PROVENANCE_ID or data["source_ruleset"] != OFFICIAL_SOURCE_RULESET:
        raise CreatureCatalogError("Catalog source/provenance identity is unsupported")
    declared_count = _integer(data["source_stat_block_count"], "catalog.source_stat_block_count", 1)
    trait_definitions = _validate_passive_registry(data["passive_trait_registry"])
    creatures = _array(data["creatures"], "catalog.creatures")
    if len(creatures) != declared_count:
        raise CreatureCatalogError("Catalog source_stat_block_count does not equal creature rows")
    identities = [
        _validate_creature(creature, index, trait_definitions)
        for index, creature in enumerate(creatures)
    ]
    creature_ids = [item[0] for item in identities]
    if len(creature_ids) != len(set(creature_ids)):
        raise CreatureCatalogError("Catalog contains duplicate creature IDs")
    if creature_ids != sorted(creature_ids):
        raise CreatureCatalogError("Catalog creatures must use canonical creature_id ordering")
    source_identities = [(item[1], item[2]) for item in identities]
    if len(source_identities) != len(set(source_identities)):
        raise CreatureCatalogError("Catalog contains duplicate source identities")
    source_ordered = sorted(identities, key=lambda item: (item[1], item[2], item[0]))
    if [item[2] for item in source_ordered] != list(range(1, declared_count + 1)):
        raise CreatureCatalogError("Catalog source-order accounting is incomplete")
    occurrence_count = sum(item[3] for item in identities)
    if occurrence_count != data["passive_trait_registry"]["source_occurrence_count"]:
        raise CreatureCatalogError("Passive-trait source_occurrence_count is inconsistent")
    _reject_scenario_state(data["creatures"], "catalog.creatures")


def _reject_scenario_state(value: Any, label: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(set(value).intersection(_SCENARIO_FIELD_NAMES))
        if forbidden:
            raise CreatureCatalogError(f"{label} contains forbidden live scenario state {forbidden}")
        for key, item in value.items():
            _reject_scenario_state(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_scenario_state(item, f"{label}[{index}]")


def _validate_provenance(
    data: dict[str, Any],
    catalog_path: Path,
    roster_path: Path,
    catalog_data: Mapping[str, Any],
) -> None:
    _exact_keys(data, {"format_version", "provenance_id", "source", "catalog", "rosters", "extraction", "accounting", "source_exceptions", "modifications", "license"}, "creature provenance")
    if data["format_version"] != 1 or data["provenance_id"] != PROVENANCE_ID:
        raise CreatureCatalogError("Unsupported creature provenance version/identity")
    source = _object(data["source"], "creature provenance.source")
    expected_source = {
        "ruleset": OFFICIAL_SOURCE_RULESET,
        "official_pdf_url": OFFICIAL_SOURCE_URL,
        "official_pdf_sha256": OFFICIAL_SOURCE_SHA256,
        "official_pdf_bytes": OFFICIAL_SOURCE_BYTES,
        "page_count": OFFICIAL_SOURCE_PAGE_COUNT,
        "monster_rules_pages": [254, 257],
        "stat_block_pages": [258, 364],
    }
    _exact_keys(source, set(expected_source), "creature provenance.source")
    if source != expected_source:
        raise CreatureCatalogError("Creature provenance source digest or identity mismatch")
    catalog = _object(data["catalog"], "creature provenance.catalog")
    _exact_keys(catalog, {"file", "contract_id", "contract_version", "sha256", "stat_block_count", "first_source_identity", "last_source_identity"}, "creature provenance.catalog")
    if catalog != {
        "file": "harness/data/srd_creatures.json",
        "contract_id": CATALOG_CONTRACT_ID,
        "contract_version": CATALOG_CONTRACT_VERSION,
        "sha256": file_sha256(catalog_path),
        "stat_block_count": catalog_data["source_stat_block_count"],
        "first_source_identity": "p258-o001",
        "last_source_identity": "p364-o330",
    }:
        raise CreatureCatalogError("Creature catalog provenance digest/contract mismatch")
    rosters = _object(data["rosters"], "creature provenance.rosters")
    _exact_keys(rosters, {"file", "contract_id", "contract_version", "sha256"}, "creature provenance.rosters")
    if rosters["file"] != "harness/data/srd_creature_rosters.json" or rosters["contract_id"] != ROSTER_CONTRACT_ID or rosters["contract_version"] != ROSTER_CONTRACT_VERSION:
        raise CreatureCatalogError("Creature roster provenance contract is unsupported")
    if not roster_path.is_file() or rosters["sha256"] != file_sha256(roster_path):
        raise CreatureCatalogError("Creature roster provenance digest mismatch")
    extraction = _object(data["extraction"], "creature provenance.extraction")
    _exact_keys(extraction, {"primary_text_layer", "coordinate_metadata", "font_metadata", "parser_policy", "trait_heading_policy", "trait_audit_sha256", "visual_source_checks", "inference", "ocr"}, "creature provenance.extraction")
    for key in ("primary_text_layer", "coordinate_metadata", "font_metadata"):
        item = _object(extraction[key], f"creature provenance.extraction.{key}")
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise CreatureCatalogError(f"creature provenance.extraction.{key}.sha256 is invalid")
    if extraction["inference"] != "none" or extraction["ocr"] != "not_used":
        raise CreatureCatalogError("Creature extraction provenance must remain source-only without OCR")
    if not re.fullmatch(r"[0-9a-f]{64}", extraction["trait_audit_sha256"]):
        raise CreatureCatalogError("Creature trait-audit digest is invalid")
    accounting = _object(data["accounting"], "creature provenance.accounting")
    _exact_keys(accounting, {"monsters_a_z_stat_blocks", "animal_stat_blocks", "total_stat_blocks", "multi_size_stat_blocks", "swarm_stat_blocks", "explicit_skill_stat_blocks", "static_gear_stat_blocks", "hover_stat_blocks", "alternate_lair_xp_stat_blocks", "telepathy_stat_blocks", "special_sense_occurrences", "passive_trait_source_headings", "passive_trait_occurrences", "qualified_defense_facts"}, "creature provenance.accounting")
    if accounting["total_stat_blocks"] != catalog_data["source_stat_block_count"] or accounting["passive_trait_occurrences"] != catalog_data["passive_trait_registry"]["source_occurrence_count"]:
        raise CreatureCatalogError("Creature provenance accounting disagrees with catalog")
    senses = _object(accounting["special_sense_occurrences"], "creature provenance.accounting.special_sense_occurrences")
    _exact_keys(senses, set(SENSE_KINDS), "creature provenance.accounting.special_sense_occurrences")
    computed_senses = {
        kind: sum(len(creature["senses"][kind]) for creature in catalog_data["creatures"])
        for kind in SENSE_KINDS
    }
    if senses != computed_senses:
        raise CreatureCatalogError("Creature provenance sense accounting disagrees with catalog")
    exceptions = _array(data["source_exceptions"], "creature provenance.source_exceptions")
    for index, item in enumerate(exceptions):
        label = f"creature provenance.source_exceptions[{index}]"
        row = _object(item, label)
        _exact_keys(row, {"creature_id", "field", "source_page", "source_value", "exception_id"}, label)
        if row["creature_id"] not in {creature["creature_id"] for creature in catalog_data["creatures"]}:
            raise CreatureCatalogError(f"{label}.creature_id is unknown")
        _string(row["field"], f"{label}.field")
        _integer(row["source_page"], f"{label}.source_page", 258)
        _string(row["exception_id"], f"{label}.exception_id", lower=True)
    _string(data["modifications"], "creature provenance.modifications")
    if data["license"] != "Creative Commons Attribution 4.0 International (CC BY 4.0)":
        raise CreatureCatalogError("Creature provenance license is unsupported")


def load_catalog(
    catalog_path: Path = DEFAULT_CATALOG,
    provenance_path: Path = DEFAULT_PROVENANCE,
    roster_path: Path = DEFAULT_ROSTERS,
) -> CreatureCatalog:
    """Load and fully validate the one authoritative creature catalog."""

    data = _load_json(catalog_path, "creature catalog")
    _validate_catalog_data(data)
    provenance = _load_json(provenance_path, "creature provenance")
    _validate_provenance(provenance, catalog_path, roster_path, data)
    digest = file_sha256(catalog_path)
    records = tuple(_deep_freeze(record) for record in data["creatures"])
    by_id = MappingProxyType({record["creature_id"]: record for record in records})
    return _creature_catalog_from_validated(
        records=records,
        by_id=by_id,
        contract_id=CATALOG_CONTRACT_ID,
        contract_version=CATALOG_CONTRACT_VERSION,
        sha256=digest,
        source_url=OFFICIAL_SOURCE_URL,
        source_sha256=OFFICIAL_SOURCE_SHA256,
        provenance=_deep_freeze(provenance),
    )


def _creature_catalog_from_validated(
    *,
    records: tuple[Mapping[str, Any], ...],
    by_id: Mapping[str, Mapping[str, Any]],
    contract_id: str,
    contract_version: str,
    sha256: str,
    source_url: str,
    source_sha256: str,
    provenance: Mapping[str, Any],
) -> CreatureCatalog:
    """Construct an immutable catalog only after byte/provenance validation."""

    frozen_records = tuple(_deep_freeze(record) for record in records)
    expected_by_id = MappingProxyType(
        {record["creature_id"]: record for record in frozen_records}
    )
    if dict(by_id) != dict(expected_by_id):
        raise CreatureCatalogError(
            "Creature catalog ID index disagrees with its immutable records"
        )
    catalog = object.__new__(CreatureCatalog)
    for name, value in (
        ("records", frozen_records),
        ("by_id", expected_by_id),
        ("contract_id", contract_id),
        ("contract_version", contract_version),
        ("sha256", sha256),
        ("source_url", source_url),
        ("source_sha256", source_sha256),
        ("provenance", _deep_freeze(provenance)),
    ):
        object.__setattr__(catalog, name, value)
    catalog.__post_init__()
    return catalog


def _validate_requirement_path(creature: Mapping[str, Any], path: str, label: str) -> None:
    current: Any = creature
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise CreatureCatalogError(f"{label} required field {path!r} is absent")
        current = current[part]
    if current is None and path not in _NULLABLE_REQUIRED_PATHS:
        raise CreatureCatalogError(f"{label} required field {path!r} is unresolved")


def load_consumer_requirements(
    path: Path = DEFAULT_CONSUMER_REQUIREMENTS,
    *,
    catalog: CreatureCatalog | None = None,
) -> ConsumerRequirements:
    """Load the versioned, fail-closed declarations for maintained consumers."""

    data = _load_json(path, "creature consumer requirements")
    _exact_keys(data, {"contract", "catalog_contract", "passive_trait_registry", "scenario_state_boundary", "consumers"}, "creature consumer requirements")
    _validate_contract(data["contract"], "consumer requirements.contract", CONSUMER_REQUIREMENTS_ID, CONSUMER_REQUIREMENTS_VERSION)
    _validate_contract(data["catalog_contract"], "consumer requirements.catalog_contract", CATALOG_CONTRACT_ID, CATALOG_CONTRACT_VERSION)
    _validate_contract(data["passive_trait_registry"], "consumer requirements.passive_trait_registry", PASSIVE_TRAIT_REGISTRY_ID, PASSIVE_TRAIT_REGISTRY_VERSION)
    boundary = _object(data["scenario_state_boundary"], "consumer requirements.scenario_state_boundary")
    _exact_keys(boundary, {"policy", "forbidden_static_fields"}, "consumer requirements.scenario_state_boundary")
    if boundary["policy"] != "separately_supplied_live_state_only":
        raise CreatureCatalogError("Unsupported scenario-state boundary policy")
    forbidden = _string_array(boundary["forbidden_static_fields"], "consumer requirements.scenario_state_boundary.forbidden_static_fields", lower=True, nonempty=True, canonical=True)
    if set(forbidden) != _SCENARIO_FIELD_NAMES:
        raise CreatureCatalogError("Consumer requirements must declare the complete scenario-state exclusion boundary")
    consumers = _object(data["consumers"], "consumer requirements.consumers")
    _exact_keys(consumers, {"damage_target", "control_target", "planner_static_target"}, "consumer requirements.consumers")
    for consumer_id in ("damage_target", "control_target", "planner_static_target"):
        label = f"consumer requirements.consumers.{consumer_id}"
        consumer = _object(consumers[consumer_id], label)
        _exact_keys(consumer, {"implemented", "projection_contract", "required_catalog_paths", "typed_trait_policy", "required_typed_trait_ids", "unsupported_material_trait_ids", "qualifier_policy", "output_fields"}, label)
        implemented = _boolean(consumer["implemented"], f"{label}.implemented")
        projection = _object(consumer["projection_contract"], f"{label}.projection_contract")
        _exact_keys(projection, {"id", "version"}, f"{label}.projection_contract")
        _string(projection["id"], f"{label}.projection_contract.id", lower=True)
        _string(projection["version"], f"{label}.projection_contract.version")
        paths = _string_array(consumer["required_catalog_paths"], f"{label}.required_catalog_paths", nonempty=True)
        if len(paths) != len(set(paths)):
            raise CreatureCatalogError(f"{label}.required_catalog_paths contains duplicates")
        _string(consumer["typed_trait_policy"], f"{label}.typed_trait_policy", lower=True)
        required_traits = _string_array(consumer["required_typed_trait_ids"], f"{label}.required_typed_trait_ids", lower=True, canonical=True)
        unsupported_traits = _string_array(consumer["unsupported_material_trait_ids"], f"{label}.unsupported_material_trait_ids", lower=True, canonical=True)
        if set(required_traits).intersection(unsupported_traits):
            raise CreatureCatalogError(f"{label} cannot both require and reject a trait")
        qualifier_policy = _object(consumer["qualifier_policy"], f"{label}.qualifier_policy")
        for key, value in qualifier_policy.items():
            _string(key, f"{label}.qualifier_policy key", lower=True)
            _string(value, f"{label}.qualifier_policy.{key}", lower=True)
        output_fields = _string_array(consumer["output_fields"], f"{label}.output_fields")
        if implemented != (consumer_id != "planner_static_target"):
            raise CreatureCatalogError(
                f"{label}.implemented disagrees with the maintained runtime boundary"
            )
        if not implemented:
            if projection != {
                "id": PLANNER_PROJECTION_ID,
                "version": PLANNER_PROJECTION_VERSION,
            }:
                raise CreatureCatalogError(
                    f"{label}.projection_contract must retain the draft 1.0.0 identity"
                )
            if output_fields:
                raise CreatureCatalogError(
                    "Unimplemented projection must not declare runtime output fields"
                )
            if consumer["typed_trait_policy"] != "fail_closed_until_implemented":
                raise CreatureCatalogError(
                    "Unimplemented projection must fail closed on typed traits"
                )
            if required_traits or unsupported_traits:
                raise CreatureCatalogError(
                    "Unimplemented projection must not claim typed-trait support"
                )
            if qualifier_policy != {"all": "fail_closed_until_implemented"}:
                raise CreatureCatalogError(
                    "Unimplemented projection must fail closed on all qualifiers"
                )
    if catalog is not None:
        definition_ids = {
            trait["trait_id"]
            for creature in catalog.records
            for trait in creature["passive_traits"]
        }
        for consumer_id, consumer in consumers.items():
            declared = set(consumer["required_typed_trait_ids"]) | set(consumer["unsupported_material_trait_ids"])
            unknown = sorted(declared - definition_ids)
            if unknown:
                raise CreatureCatalogError(f"{consumer_id} declares unknown typed traits {unknown}")
            for creature in catalog.records:
                for path_value in consumer["required_catalog_paths"]:
                    _validate_requirement_path(creature, path_value, consumer_id)
    return ConsumerRequirements(
        data=data,
        registry_sha256=file_sha256(path),
        consumer_sha256_by_id=consumer_requirements_sha256_by_id(data),
    )


def validate_consumer_projection_contract(
    requirements: ConsumerRequirements,
    consumer_id: str,
    *,
    projection_id: str,
    projection_version: str,
    typed_trait_policy: str,
    output_fields: Iterable[str],
) -> Mapping[str, Any]:
    """Bind one projection module to its exact consumer declaration."""

    consumer = requirements.consumer(consumer_id)
    label = f"consumer requirements.consumers.{consumer_id}"
    if consumer["implemented"] is not True:
        raise CreatureCatalogError(f"{label}.implemented must be true")
    if consumer["projection_contract"] != {
        "id": projection_id,
        "version": projection_version,
    }:
        raise CreatureCatalogError(f"{label}.projection_contract disagrees with the maintained projection")
    if consumer["typed_trait_policy"] != typed_trait_policy:
        raise CreatureCatalogError(f"{label}.typed_trait_policy disagrees with the maintained projection")
    if tuple(consumer["output_fields"]) != tuple(output_fields):
        raise CreatureCatalogError(f"{label}.output_fields disagrees with the maintained projection")
    return consumer


def _challenge(creature: Mapping[str, Any]) -> Fraction:
    row = creature["challenge"]["rating"]
    return Fraction(row["numerator"], row["denominator"])


def _level_for(creature: Mapping[str, Any]) -> int | None:
    challenge = _challenge(creature)
    matches = [level for level, (minimum, maximum) in BANDS.items() if minimum <= challenge <= maximum]
    if len(matches) > 1:
        raise CreatureCatalogError(f"Eligibility ranges overlap for {creature['creature_id']}")
    return matches[0] if matches else None


def _source_key(creature: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        creature["source"]["page"],
        creature["source"]["stat_block_order"],
        creature["creature_id"],
    )


def _present_or_none(values: Iterable[str]) -> set[str]:
    result = set(values)
    return result or {"none"}


def _qualifier_token(row: Mapping[str, Any], key: str) -> str:
    value = row[key] if row.get(key) is not None else "unresolved_choice:" + "/".join(row["choices"])
    qualifier = row.get("qualifier_id") or "none"
    return f"{value}|qualifier:{qualifier}"


def _categorical_tokens(creature: Mapping[str, Any]) -> dict[str, set[str]]:
    tokens: dict[str, set[str]] = defaultdict(set)

    def add(dimension: str, values: str | Iterable[str]) -> None:
        if isinstance(values, str):
            tokens[dimension].add(values)
        else:
            tokens[dimension].update(values)

    challenge = creature["challenge"]["rating"]
    add("exact_cr", str(challenge["numerator"]) if challenge["denominator"] == 1 else f"{challenge['numerator']}/{challenge['denominator']}")
    armor = creature["armor_class"]
    signature = {"alternatives": armor["alternatives"], "qualifiers": armor["qualifiers"], "resolution": armor["resolution"]}
    add("ac_alternative_qualifier_signature", "none" if not armor["alternatives"] and not armor["qualifiers"] else json.dumps(signature, sort_keys=True, separators=(",", ":")))
    add("size", creature["classification"]["sizes"])
    add("creature_type", creature["classification"]["creature_type"])
    add("creature_tag", _present_or_none(creature["classification"]["tags"]))
    add("magic_resistance", "present" if creature["magic_resistance"]["present"] else "none")
    legendary = creature["legendary_resistance"]
    add("legendary_resistance_count", str(legendary["uses_per_day"]) if legendary["uses_per_day"] else "none")
    add("legendary_resistance_policy", "lair_plus_one" if legendary["lair_uses_per_day"] is not None else "fixed" if legendary["uses_per_day"] else "none")
    defenses = creature["defenses"]
    for key, dimension in (("damage_resistances", "damage_resistance"), ("damage_immunities", "damage_immunity"), ("damage_vulnerabilities", "damage_vulnerability")):
        add(dimension, _present_or_none(_qualifier_token(row, "damage_type") for row in defenses[key]))
    add("condition_immunity", _present_or_none(_qualifier_token(row, "condition") for row in defenses["condition_immunities"]))
    movement = creature["movement"]
    add("movement_mode", (mode for mode, rows in movement["modes"].items() if rows))
    add("hover", "present" if movement["hover"] else "none")
    limitations = {
        f"{mode}:{row['qualifier']}"
        for mode, rows in movement["modes"].items()
        for row in rows
        if row["qualifier"]
    }
    limitations.update(f"choice:{row['qualifier']}" for row in movement["choice_groups"])
    add("movement_limitation", _present_or_none(limitations))
    for kind, rows in creature["senses"].items():
        facts: set[str] = set()
        for row in rows:
            facts.update(("present", f"range:{row['range_feet']}", f"limitation:{row['limitation'] or 'none'}"))
        add(f"sense_{kind}", _present_or_none(facts))
    initiative = creature["initiative"]
    initiative_token = "advantage" if initiative["advantage"] else "standard"
    if initiative["qualifier"]:
        initiative_token += f"|qualifier:{initiative['qualifier']}"
    add("initiative_categorical", initiative_token)
    communication = creature["communication"]
    restrictions = set(communication["limitations"])
    restrictions.update(row["limitation_id"] for row in communication["languages"] if row["limitation_id"])
    add("communication_restriction", _present_or_none(restrictions))
    telepathy = communication["telepathy"]
    if telepathy is None:
        add("telepathy", "none")
    else:
        add("telepathy", {"present", f"range:{telepathy['range_feet']}", f"limitation:{telepathy['limitation_id'] or 'none'}"})
    add("static_gear_category", _present_or_none(row["category"] for row in creature["gear"]))
    all_traits = {row["trait_id"] for row in creature["passive_traits"] if row["disposition"] == "modeled_typed"}
    add("typed_passive_trait", _present_or_none(all_traits - _DEDICATED_TRAIT_IDS))
    targeting = set()
    for trait_id in all_traits:
        targeting.update(_TARGETING_TRAITS.get(trait_id, set()))
    add("targeting_restriction", _present_or_none(targeting))
    add("skill_identity", _present_or_none(row["skill"] for row in creature["skills"]))
    return dict(tokens)


def _numeric_values(creature: Mapping[str, Any]) -> dict[str, int]:
    values = {
        "default_ac": creature["armor_class"]["default"],
        "average_hp": creature["hit_points"]["average"],
        "initiative_numeric": creature["initiative"]["score"],
        "passive_perception": creature["passive_perception"],
    }
    for ability in ABILITIES:
        values[f"ability_modifier:{ability}"] = creature["abilities"][ability]["modifier"]
        values[f"final_save:{ability}"] = creature["abilities"][ability]["save_bonus"]
    for skill in creature["skills"]:
        values[f"skill_bonus:{skill['skill']}"] = skill["bonus"]
    return values


def _bucket_map(values: set[int]) -> dict[int, str]:
    ordered = sorted(values)
    if len(ordered) == 1:
        return {ordered[0]: "only"}
    return {
        value: f"q{1 + min(3, math.floor(4 * index / (len(ordered) - 1)))}"
        for index, value in enumerate(ordered)
    }


def _tokens_for_level(candidates: list[Mapping[str, Any]]) -> tuple[dict[str, dict[str, set[str]]], dict[str, dict[int, str]]]:
    raw_numeric = {row["creature_id"]: _numeric_values(row) for row in candidates}
    dimensions = sorted({dimension for values in raw_numeric.values() for dimension in values})
    maps = {
        dimension: _bucket_map({values[dimension] for values in raw_numeric.values() if dimension in values})
        for dimension in dimensions
    }
    output: dict[str, dict[str, set[str]]] = {}
    for creature in candidates:
        dimensions_tokens: dict[str, set[str]] = defaultdict(set, _categorical_tokens(creature))
        for dimension, value in raw_numeric[creature["creature_id"]].items():
            dimensions_tokens[dimension].add(maps[dimension][value])
        output[creature["creature_id"]] = dict(dimensions_tokens)
    return output, maps


def _greedy(candidates: list[Mapping[str, Any]], token_map: Mapping[str, Mapping[str, set[str]]], k: int) -> tuple[list[Mapping[str, Any]], list[dict[str, Any]], dict[str, set[str]], dict[str, set[str]]]:
    universe: dict[str, set[str]] = defaultdict(set)
    for dimensions in token_map.values():
        for dimension, values in dimensions.items():
            universe[dimension].update(values)
    weights = {dimension: Fraction(1, len(values)) for dimension, values in universe.items()}
    covered: dict[str, set[str]] = defaultdict(set)
    remaining = list(candidates)
    selected: list[Mapping[str, Any]] = []
    trace: list[dict[str, Any]] = []
    while len(selected) < k:
        scored = [
            (
                sum(
                    weights[dimension] * len(values - covered[dimension])
                    for dimension, values in token_map[creature["creature_id"]].items()
                ),
                creature,
            )
            for creature in remaining
        ]
        score, chosen = sorted(scored, key=lambda item: (-item[0], *_source_key(item[1])))[0]
        newly: dict[str, list[str]] = {}
        for dimension, values in token_map[chosen["creature_id"]].items():
            uncovered = values - covered[dimension]
            if uncovered:
                newly[dimension] = sorted(uncovered)
            covered[dimension].update(values)
        trace.append({"pick": len(selected) + 1, "creature_id": chosen["creature_id"], "score": _ratio_dict(score), "newly_covered": dict(sorted(newly.items()))})
        selected.append(chosen)
        remaining.remove(chosen)
    return sorted(selected, key=_source_key), trace, dict(universe), dict(covered)


def _family_facts(creature: Mapping[str, Any]) -> dict[str, bool]:
    defenses = creature["defenses"]
    all_traits = {row["trait_id"] for row in creature["passive_traits"] if row["disposition"] == "modeled_typed"}
    traits = all_traits - _DEDICATED_TRAIT_IDS
    qualified = any(
        row.get("qualifier_id")
        for key in ("damage_resistances", "damage_immunities", "damage_vulnerabilities")
        for row in defenses[key]
    )
    restrictions: set[str] = set()
    for trait_id in all_traits:
        restrictions.update(_TARGETING_TRAITS.get(trait_id, set()))
    return {
        "magic_resistance": creature["magic_resistance"]["present"],
        "legendary_resistance": creature["legendary_resistance"]["uses_per_day"] > 0,
        "qualified_damage_defense": qualified,
        "condition_immunity": bool(defenses["condition_immunities"]),
        "special_movement": any(creature["movement"]["modes"][mode] for mode in ("fly", "swim", "climb", "burrow")) or bool(creature["movement"]["choice_groups"]),
        "hover": creature["movement"]["hover"],
        "darkvision": bool(creature["senses"]["darkvision"]),
        "blindsight": bool(creature["senses"]["blindsight"]),
        "tremorsense": bool(creature["senses"]["tremorsense"]),
        "truesight": bool(creature["senses"]["truesight"]),
        "material_typed_passive_traits": bool(traits),
        "static_gear": bool(creature["gear"]),
        "targeting_restrictions": bool(restrictions),
    }


def _family_audit(candidates: list[Mapping[str, Any]], selected: list[Mapping[str, Any]]) -> dict[str, Any]:
    keys = _family_facts(candidates[0]).keys()
    output: dict[str, Any] = {}
    for key in keys:
        present = [row["creature_id"] for row in candidates if _family_facts(row)[key]]
        represented = [row["creature_id"] for row in selected if _family_facts(row)[key]]
        output[key] = {
            "candidate_count": len(present),
            "candidate_creature_ids": present,
            "selected_count": len(represented),
            "selected_creature_ids": represented,
            "represented_when_present": not present or bool(represented),
        }
    return output


def _profile(profile_id: str, purpose: str, levels: Mapping[int, list[Mapping[str, Any]]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for level in BENCHMARK_LEVELS:
        rows = levels[level]
        weight = Fraction(1, len(rows))
        for creature in sorted(rows, key=_source_key):
            entries.append({
                "creature_id": creature["creature_id"],
                "benchmark_level": level,
                "eligibility_policy_id": ELIGIBILITY_POLICY_ID,
                "profile_id": profile_id,
                "profile_version": PROFILE_VERSION,
                "weight": _ratio_dict(weight),
                "purpose": purpose,
                "profile_order": len(entries) + 1,
            })
    identity = {"profile_id": profile_id, "profile_version": PROFILE_VERSION, "purpose": purpose, "entries": entries}
    return {**identity, "profile_sha256": canonical_sha256(identity)}


def _expected_roster(catalog: CreatureCatalog) -> dict[str, Any]:
    source_sorted = sorted(catalog.records, key=_source_key)
    accounting: list[dict[str, Any]] = []
    eligible: dict[int, list[Mapping[str, Any]]] = {level: [] for level in BENCHMARK_LEVELS}
    feasible: dict[int, list[Mapping[str, Any]]] = {level: [] for level in BENCHMARK_LEVELS}
    for creature in source_sorted:
        level = _level_for(creature)
        exclusion = _EXCLUDED_CREATURES.get(creature["creature_id"])
        if level is None:
            disposition = "ineligible_under_level_cr_policy"
            exclusion = None
        else:
            eligible[level].append(creature)
            if exclusion:
                disposition = "excluded_unsupported_material_mechanic"
            else:
                disposition = "eligible_pending_profile_disposition"
                feasible[level].append(creature)
        accounting.append({
            "creature_id": creature["creature_id"],
            "challenge_rating": creature["challenge"]["rating"],
            "benchmark_level": level,
            "eligibility_policy_id": ELIGIBILITY_POLICY_ID,
            "projection_feasible": level is not None and not exclusion,
            "disposition": disposition,
            "reason_id": exclusion,
        })
    selected: dict[int, list[Mapping[str, Any]]] = {}
    audits: dict[str, Any] = {}
    selected_ids: set[str] = set()
    for level in BENCHMARK_LEVELS:
        tokens, maps = _tokens_for_level(feasible[level])
        if not feasible[level]:
            raise CreatureCatalogError(f"Level {level} has zero projection-feasible candidates")
        k = min(12, len(feasible[level]))
        chosen, trace, universe, covered = _greedy(feasible[level], tokens, k)
        selected[level] = chosen
        selected_ids.update(row["creature_id"] for row in chosen)
        coverage = {dimension: Fraction(len(covered.get(dimension, set())), len(values)) for dimension, values in universe.items()}
        covered_weight = sum(coverage.values(), Fraction())
        uncovered = {dimension: sorted(values - covered.get(dimension, set())) for dimension, values in universe.items() if values - covered.get(dimension, set())}
        audits[str(level)] = {
            "eligible_count": len(eligible[level]),
            "projection_feasible_count": len(feasible[level]),
            "excluded_count": len(eligible[level]) - len(feasible[level]),
            "headline_count": k,
            "census_count": len(feasible[level]),
            "numeric_bucket_maps": {
                dimension: [{"value": value, "bucket": bucket} for value, bucket in sorted(mapping.items())]
                for dimension, mapping in sorted(maps.items())
            },
            "token_universes": {dimension: sorted(values) for dimension, values in sorted(universe.items())},
            "greedy_pick_trace": trace,
            "coverage": {
                "covered_weight": _ratio_dict(covered_weight),
                "available_weight": _ratio_dict(Fraction(len(universe))),
                "fraction": _ratio_dict(covered_weight / len(universe)),
                "by_dimension": {dimension: _ratio_dict(value) for dimension, value in sorted(coverage.items())},
                "uncovered_tokens": dict(sorted(uncovered.items())),
            },
            "major_family_audit": _family_audit(feasible[level], chosen),
        }
    for row in accounting:
        if row["disposition"] == "eligible_pending_profile_disposition":
            row["disposition"] = "headline_selected" if row["creature_id"] in selected_ids else "eligible_census_only"
    return {
        "contract": {"id": ROSTER_CONTRACT_ID, "version": ROSTER_CONTRACT_VERSION},
        "catalog": {"contract_version": catalog.contract_version, "sha256": catalog.sha256},
        "eligibility_policy": {
            "id": ELIGIBILITY_POLICY_ID,
            "closed_ranges": {str(level): {"minimum": _ratio_dict(low), "maximum": _ratio_dict(high)} for level, (low, high) in BANDS.items()},
            "intentional_gaps": [_ratio_dict(Fraction(9)), _ratio_dict(Fraction(17)), _ratio_dict(Fraction(18))],
        },
        "selection_algorithm": {
            "id": SELECTION_ALGORITHM_ID,
            "headline_cap_per_level": 12,
            "dimension_weight": _ratio_dict(Fraction(1)),
            "token_weight": "uniform_exact_rational_within_dimension",
            "tie_break": ["source_page_ascending", "source_order_ascending", "creature_id_ascending"],
            "serialized_order": ["benchmark_level_ascending", "source_page_ascending", "source_order_ascending", "creature_id_ascending"],
            "result_blind": True,
        },
        "exclusion_reason_ids": sorted(set(_EXCLUDED_CREATURES.values())),
        "accounting": accounting,
        "profiles": [
            _profile(HEADLINE_PROFILE_ID, "bounded_source_mechanical_diversity", selected),
            _profile(CENSUS_PROFILE_ID, "complete_projection_feasible_eligible_census", feasible),
        ],
        "selection_audit": {"levels": audits},
    }


def _load_validated_roster(
    roster_path: Path,
    catalog: CreatureCatalog,
) -> tuple[dict[str, Any], str]:
    data = _load_json(roster_path, "creature rosters")
    expected = _expected_roster(catalog)
    if data != expected:
        raise CreatureCatalogError(
            "Creature roster differs from deterministic source-only recomputation"
        )
    digest = file_sha256(roster_path)
    if catalog.provenance["rosters"]["sha256"] != digest:
        raise CreatureCatalogError("Creature roster digest disagrees with provenance")
    return data, digest


def load_profile(
    profile_id: str = HEADLINE_PROFILE_ID,
    levels: set[int] | None = None,
    *,
    catalog: CreatureCatalog | None = None,
    catalog_path: Path = DEFAULT_CATALOG,
    roster_path: Path = DEFAULT_ROSTERS,
    provenance_path: Path = DEFAULT_PROVENANCE,
) -> list[RosterEntry]:
    """Load one deterministic profile while retaining roster identity separately."""

    if levels is not None:
        unknown_levels = sorted(levels - set(BENCHMARK_LEVELS))
        if unknown_levels:
            raise CreatureCatalogError(f"Unsupported benchmark levels {unknown_levels}")
    if catalog is None:
        catalog = load_catalog(catalog_path, provenance_path, roster_path)
    data, roster_sha = _load_validated_roster(roster_path, catalog)
    try:
        profile = next(item for item in data["profiles"] if item["profile_id"] == profile_id)
    except StopIteration as error:
        raise CreatureCatalogError(f"Requested profile {profile_id!r} does not exist") from error
    entries = [
        RosterEntry(
            creature_id=item["creature_id"],
            benchmark_level=item["benchmark_level"],
            eligibility_policy_id=item["eligibility_policy_id"],
            profile_id=item["profile_id"],
            profile_version=item["profile_version"],
            weight=_ratio(item["weight"], f"profile {profile_id} weight"),
            purpose=item["purpose"],
            profile_order=item["profile_order"],
            catalog_sha256=catalog.sha256,
            roster_sha256=roster_sha,
            profile_sha256=profile["profile_sha256"],
        )
        for item in profile["entries"]
        if levels is None or item["benchmark_level"] in levels
    ]
    if not entries:
        raise CreatureCatalogError(f"Requested profile {profile_id!r} selection is empty")
    return entries


def _ensure_requirements(
    requirements: ConsumerRequirements | None,
    requirements_path: Path,
    catalog: CreatureCatalog,
) -> ConsumerRequirements:
    return requirements or load_consumer_requirements(requirements_path, catalog=catalog)


def _ensure_catalog(
    catalog: CreatureCatalog | None,
    catalog_path: Path,
    provenance_path: Path,
    roster_path: Path,
) -> CreatureCatalog:
    return catalog or load_catalog(catalog_path, provenance_path, roster_path)


def _projection_identity(record: Mapping[str, Any]) -> str:
    return canonical_sha256(record)


if __name__ == "__main__":
    loaded_catalog = load_catalog()
    load_consumer_requirements(catalog=loaded_catalog)
    headline = load_profile(catalog=loaded_catalog)
    print(
        f"Validated {len(loaded_catalog.records)} SRD creatures and "
        f"{len(headline)} deterministic headline roster bindings."
    )
