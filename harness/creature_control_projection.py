"""Thin control-consumer projection over the canonical SRD creature catalog."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .creature_catalog import (
    ABILITIES,
    DEFAULT_CATALOG,
    DEFAULT_CONSUMER_REQUIREMENTS,
    DEFAULT_PROVENANCE,
    DEFAULT_ROSTERS,
    MOVEMENT_MODES,
    SENSE_KINDS,
    SKILL_IDS,
    ConsumerRequirements,
    CreatureCatalog,
    CreatureCatalogError,
    _ensure_catalog,
    _ensure_requirements,
    _deep_freeze,
    _projection_identity,
    _validate_requirement_path,
    validate_consumer_projection_contract,
)


CONTROL_PROJECTION_ID = "srd521_control_target"
CONTROL_PROJECTION_VERSION = "1.0.0"

SKILL_ABILITY_BY_ID = MappingProxyType({
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
})
if tuple(SKILL_ABILITY_BY_ID) != SKILL_IDS:
    raise RuntimeError("Control skill associations must cover the common skill vocabulary")


_SOURCE_DEFAULT_CONDITION_QUALIFIERS = {"source_default_mind_blank"}
_CONTROL_REQUIRED_CATALOG_PATHS = (
    "creature_id",
    "display_name",
    "source.ruleset",
    "source.page",
    "source.stat_block_anchor",
    "armor_class.default",
    "armor_class.resolution",
    "abilities.strength.modifier",
    "abilities.strength.save_bonus",
    "abilities.dexterity.modifier",
    "abilities.dexterity.save_bonus",
    "abilities.constitution.modifier",
    "abilities.constitution.save_bonus",
    "abilities.intelligence.modifier",
    "abilities.intelligence.save_bonus",
    "abilities.wisdom.modifier",
    "abilities.wisdom.save_bonus",
    "abilities.charisma.modifier",
    "abilities.charisma.save_bonus",
    "skills",
    "passive_perception",
    "classification.sizes",
    "classification.creature_type",
    "magic_resistance.present",
    "legendary_resistance.uses_per_day",
    "legendary_resistance.lair_uses_per_day",
    "legendary_resistance.policy",
    "defenses.condition_immunities",
    "movement.modes",
    "movement.hover",
    "movement.choice_groups",
    "senses.darkvision",
    "senses.blindsight",
    "senses.tremorsense",
    "senses.truesight",
    "initiative.modifier",
    "initiative.score",
    "initiative.advantage",
    "communication.languages",
    "communication.telepathy",
    "gear",
    "passive_traits",
)
_CONTROL_QUALIFIER_POLICY = {
    "armor_class": "reject_unresolved",
    "condition_immunities": "preserve_structured_and_apply_source_default_only",
    "movement": "preserve_structured",
    "size": "first_source_authored_option",
    "skills": "listed_final_bonus_else_associated_raw_ability_modifier",
}


@dataclass(frozen=True)
class DefenseFact:
    value: str | None
    choices: tuple[str, ...]
    qualifier_id: str | None
    qualifier: str | None


@dataclass(frozen=True)
class MovementFact:
    feet: int
    qualifier: str | None
    choice_group_id: str | None


@dataclass(frozen=True)
class MovementProfile:
    walk: tuple[MovementFact, ...]
    fly: tuple[MovementFact, ...]
    swim: tuple[MovementFact, ...]
    climb: tuple[MovementFact, ...]
    burrow: tuple[MovementFact, ...]
    hover: bool
    choice_groups: tuple[tuple[str, tuple[str, ...], str], ...]

    def sole_speed(self, mode: str) -> int | None:
        facts = getattr(self, mode)
        if not facts:
            return None
        if len(facts) != 1 or facts[0].choice_group_id is not None:
            raise CreatureCatalogError(
                f"movement.{mode} does not have one unconditional speed"
            )
        return facts[0].feet


@dataclass(frozen=True)
class SenseFact:
    range_feet: int
    limitation: str | None


@dataclass(frozen=True)
class InitiativeFact:
    modifier: int
    score: int
    advantage: bool
    qualifier: str | None


@dataclass(frozen=True)
class LanguageFact:
    identity: str
    mode: str
    limitation_id: str | None


@dataclass(frozen=True)
class TelepathyFact:
    range_feet: int
    limitation_id: str | None
    limitation: str | None


@dataclass(frozen=True)
class CommunicationProfile:
    languages: tuple[LanguageFact, ...]
    all_languages: bool
    additional_language_count: int
    telepathy: TelepathyFact | None
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class StaticGearFact:
    name: str
    quantity: int
    category: str


@dataclass(frozen=True)
class PassiveTraitFact:
    trait_id: str
    source_heading: str
    parent_source_heading: str | None
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class SkillBonusFact:
    skill_id: str
    ability_id: str
    bonus: int
    source_explicit: bool

    def __post_init__(self) -> None:
        try:
            expected_ability = SKILL_ABILITY_BY_ID[self.skill_id]
        except KeyError as error:
            raise CreatureCatalogError(
                f"Unknown canonical skill ID {self.skill_id!r}"
            ) from error
        if self.ability_id != expected_ability:
            raise CreatureCatalogError(
                f"Skill {self.skill_id!r} must use ability {expected_ability!r}"
            )
        if isinstance(self.bonus, bool) or not isinstance(self.bonus, int):
            raise CreatureCatalogError("Skill bonus must be an integer")
        if self.source_explicit is not True:
            raise CreatureCatalogError(
                "Projected SkillBonusFact must retain source_explicit=true"
            )


@dataclass(frozen=True)
class ControlTarget:
    creature_id: str
    name: str
    ac: int
    ability_modifiers: Mapping[str, int]
    skills: tuple[SkillBonusFact, ...]
    passive_perception: int
    saves: Mapping[str, int]
    magic_resistance: bool
    legendary_resistance: int
    legendary_resistance_lair: int | None
    legendary_resistance_policy: str
    size: str
    creature_type: str
    condition_immunities: frozenset[str]
    condition_immunity_facts: tuple[DefenseFact, ...]
    movement: MovementProfile
    senses: Mapping[str, tuple[SenseFact, ...]]
    initiative: InitiativeFact
    communication: CommunicationProfile
    gear: tuple[StaticGearFact, ...]
    passive_traits: tuple[PassiveTraitFact, ...]
    source_ruleset: str
    source_page: int
    source_anchor: str
    source_url: str
    catalog_contract_version: str
    catalog_sha256: str
    projection_id: str
    projection_version: str
    control_consumer_requirements_sha256: str
    target_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ability_modifiers", _deep_freeze(self.ability_modifiers))
        object.__setattr__(self, "saves", _deep_freeze(self.saves))
        object.__setattr__(self, "senses", _deep_freeze(self.senses))
        object.__setattr__(
            self,
            "passive_traits",
            tuple(
                replace(fact, parameters=_deep_freeze(fact.parameters))
                for fact in self.passive_traits
            ),
        )
        if isinstance(self.passive_perception, bool) or not isinstance(
            self.passive_perception, int
        ):
            raise CreatureCatalogError("ControlTarget.passive_perception must be an integer")
        if set(self.ability_modifiers) != set(ABILITIES) or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in self.ability_modifiers.values()
        ):
            raise CreatureCatalogError(
                "ControlTarget.ability_modifiers must contain six integer facts"
            )
        if not isinstance(self.skills, tuple) or any(
            not isinstance(fact, SkillBonusFact) for fact in self.skills
        ):
            raise CreatureCatalogError(
                "ControlTarget.skills must be an immutable tuple of SkillBonusFact records"
            )
        skill_ids = [fact.skill_id for fact in self.skills]
        if skill_ids != sorted(skill_ids) or len(skill_ids) != len(set(skill_ids)):
            raise CreatureCatalogError(
                "ControlTarget.skills must be unique and canonically ordered"
            )
        if not isinstance(self.target_sha256, str) or not self.target_sha256:
            raise CreatureCatalogError("ControlTarget.target_sha256 must be non-empty")
        self.validate_identity()

    def validate_identity(self) -> None:
        payload = {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "target_sha256"
        }
        if _projection_identity(payload) != self.target_sha256:
            raise CreatureCatalogError(
                f"ControlTarget {self.creature_id!r} changed after identity derivation"
            )

def _control_consumer(requirements: ConsumerRequirements) -> Mapping[str, object]:
    consumer = validate_consumer_projection_contract(
        requirements,
        "control_target",
        projection_id=CONTROL_PROJECTION_ID,
        projection_version=CONTROL_PROJECTION_VERSION,
        typed_trait_policy="preserve_all_registry_modeled_typed",
        output_fields=ControlTarget.__dataclass_fields__,
    )
    if tuple(consumer["required_catalog_paths"]) != _CONTROL_REQUIRED_CATALOG_PATHS:
        raise CreatureCatalogError(
            "consumer requirements.consumers.control_target.required_catalog_paths "
            "disagrees with the maintained projection"
        )
    if consumer["qualifier_policy"] != _CONTROL_QUALIFIER_POLICY:
        raise CreatureCatalogError(
            "consumer requirements.consumers.control_target.qualifier_policy "
            "disagrees with the maintained projection"
        )
    return consumer


def _defense_fact(item: Mapping[str, Any], field: str) -> DefenseFact:
    return DefenseFact(
        value=item[field],
        choices=tuple(item.get("choices", ())),
        qualifier_id=item.get("qualifier_id"),
        qualifier=item.get("qualifier"),
    )


def _movement_profile(creature: Mapping[str, Any]) -> MovementProfile:
    movement = creature["movement"]
    facts = {
        mode: tuple(
            MovementFact(item["feet"], item["qualifier"], item["choice_group_id"])
            for item in movement["modes"][mode]
        )
        for mode in MOVEMENT_MODES
    }
    groups = tuple(
        (item["choice_group_id"], tuple(item["modes"]), item["qualifier"])
        for item in movement["choice_groups"]
    )
    return MovementProfile(**facts, hover=movement["hover"], choice_groups=groups)


def project_control_target(
    creature_id: str,
    *,
    catalog: CreatureCatalog | None = None,
    catalog_path: Path = DEFAULT_CATALOG,
    provenance_path: Path = DEFAULT_PROVENANCE,
    roster_path: Path = DEFAULT_ROSTERS,
    requirements: ConsumerRequirements | None = None,
    requirements_path: Path = DEFAULT_CONSUMER_REQUIREMENTS,
) -> ControlTarget:
    """Project static control facts without damage packets or live scenario state."""

    catalog = _ensure_catalog(catalog, catalog_path, provenance_path, roster_path)
    requirements = _ensure_requirements(requirements, requirements_path, catalog)
    consumer = _control_consumer(requirements)
    creature = catalog.creature(creature_id)
    for path in consumer["required_catalog_paths"]:
        _validate_requirement_path(creature, path, "control_target")
    if creature["armor_class"]["resolution"] != "resolved":
        raise CreatureCatalogError(f"{creature_id} has unresolved Armor Class")
    condition_facts = tuple(
        _defense_fact(item, "condition")
        for item in creature["defenses"]["condition_immunities"]
    )
    effective_conditions = frozenset(
        item.value
        for item in condition_facts
        if item.value is not None
        and (
            item.qualifier_id is None
            or item.qualifier_id in _SOURCE_DEFAULT_CONDITION_QUALIFIERS
        )
    )
    communication = creature["communication"]
    telepathy = communication["telepathy"]
    base = {
        "creature_id": creature_id,
        "name": creature["display_name"],
        "ac": creature["armor_class"]["default"],
        "ability_modifiers": {
            ability: creature["abilities"][ability]["modifier"]
            for ability in ABILITIES
        },
        "skills": tuple(
            SkillBonusFact(
                skill_id=item["skill"],
                ability_id=SKILL_ABILITY_BY_ID[item["skill"]],
                bonus=item["bonus"],
                source_explicit=True,
            )
            for item in creature["skills"]
        ),
        "passive_perception": creature["passive_perception"],
        "saves": {
            ability: creature["abilities"][ability]["save_bonus"]
            for ability in ABILITIES
        },
        "magic_resistance": creature["magic_resistance"]["present"],
        "legendary_resistance": creature["legendary_resistance"]["uses_per_day"],
        "legendary_resistance_lair": creature["legendary_resistance"]["lair_uses_per_day"],
        "legendary_resistance_policy": creature["legendary_resistance"]["policy"],
        "size": creature["classification"]["sizes"][0],
        "creature_type": creature["classification"]["creature_type"],
        "condition_immunities": effective_conditions,
        "condition_immunity_facts": condition_facts,
        "movement": _movement_profile(creature),
        "senses": {
            kind: tuple(
                SenseFact(item["range_feet"], item["limitation"])
                for item in creature["senses"][kind]
            )
            for kind in SENSE_KINDS
        },
        "initiative": InitiativeFact(**creature["initiative"]),
        "communication": CommunicationProfile(
            languages=tuple(
                LanguageFact(**item) for item in communication["languages"]
            ),
            all_languages=communication["all_languages"],
            additional_language_count=communication["additional_language_count"],
            telepathy=TelepathyFact(**telepathy) if telepathy is not None else None,
            limitations=tuple(communication["limitations"]),
        ),
        "gear": tuple(StaticGearFact(**item) for item in creature["gear"]),
        "passive_traits": tuple(
            PassiveTraitFact(
                trait_id=item["trait_id"],
                source_heading=item["source_heading"],
                parent_source_heading=item["parent_source_heading"],
                parameters=item["parameters"],
            )
            for item in creature["passive_traits"]
            if item["disposition"] == "modeled_typed"
        ),
        "source_ruleset": creature["source"]["ruleset"],
        "source_page": creature["source"]["page"],
        "source_anchor": creature["source"]["stat_block_anchor"],
        "source_url": catalog.source_url,
        "catalog_contract_version": catalog.contract_version,
        "catalog_sha256": catalog.sha256,
        "projection_id": CONTROL_PROJECTION_ID,
        "projection_version": CONTROL_PROJECTION_VERSION,
        "control_consumer_requirements_sha256": requirements.sha256_for(
            "control_target"
        ),
    }
    return ControlTarget(**base, target_sha256=_projection_identity(base))
