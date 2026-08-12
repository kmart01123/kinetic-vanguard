"""Thin damage-consumer projection over the canonical SRD creature catalog."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterable, Mapping

from .creature_catalog import (
    ABILITIES,
    DEFAULT_CATALOG,
    DEFAULT_CONSUMER_REQUIREMENTS,
    DEFAULT_PROVENANCE,
    DEFAULT_ROSTERS,
    ConsumerRequirements,
    CreatureCatalog,
    CreatureCatalogError,
    RosterEntry,
    _ensure_catalog,
    _ensure_requirements,
    _deep_freeze,
    _projection_identity,
    _validate_requirement_path,
    validate_consumer_projection_contract,
)


DAMAGE_PROJECTION_ID = "srd521_damage_target"
DAMAGE_PROJECTION_VERSION = "1.0.0"


_DAMAGE_REQUIRED_CATALOG_PATHS = (
    "creature_id",
    "display_name",
    "source.ruleset",
    "source.page",
    "source.stat_block_anchor",
    "armor_class.default",
    "armor_class.resolution",
    "hit_points.average",
    "abilities.strength.save_bonus",
    "abilities.dexterity.save_bonus",
    "abilities.constitution.save_bonus",
    "abilities.intelligence.save_bonus",
    "abilities.wisdom.save_bonus",
    "abilities.charisma.save_bonus",
    "classification.sizes",
    "classification.creature_type",
    "magic_resistance.present",
    "legendary_resistance.uses_per_day",
    "legendary_resistance.lair_uses_per_day",
    "legendary_resistance.policy",
    "defenses.damage_resistances",
    "defenses.damage_immunities",
    "defenses.damage_vulnerabilities",
)
_DAMAGE_QUALIFIER_POLICY = {
    "armor_class": "reject_unresolved",
    "damage_defenses": "reject_qualified_or_unresolved",
    "size": "first_source_authored_option",
}


@dataclass(frozen=True)
class DamageTarget:
    creature_id: str
    name: str
    ac: int
    saves: Mapping[str, int]
    magic_resistance: bool
    legendary_resistance: int
    legendary_resistance_lair: int | None
    legendary_resistance_policy: str
    size: str
    creature_type: str
    damage_resistances: frozenset[str]
    damage_immunities: frozenset[str]
    damage_vulnerabilities: frozenset[str]
    hp: int
    source_ruleset: str
    source_page: int
    source_anchor: str
    source_url: str
    catalog_contract_version: str
    catalog_sha256: str
    projection_id: str
    projection_version: str
    damage_consumer_requirements_sha256: str
    target_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "saves", _deep_freeze(self.saves))

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """Serialize the immutable target for process-worker transport."""
        return (
            DamageTarget,
            tuple(
                dict(self.saves) if field.name == "saves" else getattr(self, field.name)
                for field in fields(self)
            ),
        )

    def validate_identity(self) -> None:
        payload = {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "target_sha256"
        }
        if _projection_identity(payload) != self.target_sha256:
            raise CreatureCatalogError(
                f"DamageTarget {self.creature_id!r} changed after identity derivation"
            )


def _damage_consumer(requirements: ConsumerRequirements) -> Mapping[str, object]:
    consumer = validate_consumer_projection_contract(
        requirements,
        "damage_target",
        projection_id=DAMAGE_PROJECTION_ID,
        projection_version=DAMAGE_PROJECTION_VERSION,
        typed_trait_policy="consume_declared_and_reject_declared_unsupported",
        output_fields=DamageTarget.__dataclass_fields__,
    )
    if tuple(consumer["required_catalog_paths"]) != _DAMAGE_REQUIRED_CATALOG_PATHS:
        raise CreatureCatalogError(
            "consumer requirements.consumers.damage_target.required_catalog_paths "
            "disagrees with the maintained projection"
        )
    if consumer["qualifier_policy"] != _DAMAGE_QUALIFIER_POLICY:
        raise CreatureCatalogError(
            "consumer requirements.consumers.damage_target.qualifier_policy "
            "disagrees with the maintained projection"
        )
    return consumer


def _unqualified_damage_types(
    creature: Mapping[str, object], family: str
) -> frozenset[str]:
    output: set[str] = set()
    for item in creature["defenses"][family]:  # type: ignore[index]
        if item.get("damage_type") is None or item.get("qualifier_id") is not None:
            raise CreatureCatalogError(
                f"{creature['creature_id']} has an unresolved or qualified {family} fact"
            )
        output.add(item["damage_type"])
    return frozenset(output)


def project_damage_target(
    creature_id: str,
    *,
    catalog: CreatureCatalog | None = None,
    catalog_path: Path = DEFAULT_CATALOG,
    provenance_path: Path = DEFAULT_PROVENANCE,
    roster_path: Path = DEFAULT_ROSTERS,
    requirements: ConsumerRequirements | None = None,
    requirements_path: Path = DEFAULT_CONSUMER_REQUIREMENTS,
) -> DamageTarget:
    """Project only static damage-consumer facts for one canonical creature."""

    catalog = _ensure_catalog(catalog, catalog_path, provenance_path, roster_path)
    requirements = _ensure_requirements(requirements, requirements_path, catalog)
    consumer = _damage_consumer(requirements)
    creature = catalog.creature(creature_id)
    for path in consumer["required_catalog_paths"]:
        _validate_requirement_path(creature, path, "damage_target")
    if creature["armor_class"]["resolution"] != "resolved":
        raise CreatureCatalogError(f"{creature_id} has unresolved Armor Class")
    typed_traits = {
        trait["trait_id"]
        for trait in creature["passive_traits"]
        if trait["disposition"] == "modeled_typed"
    }
    unsupported = sorted(
        typed_traits.intersection(consumer["unsupported_material_trait_ids"])
    )
    if unsupported:
        raise CreatureCatalogError(
            f"{creature_id} has unsupported material passive traits {unsupported}"
        )
    base = {
        "creature_id": creature_id,
        "name": creature["display_name"],
        "ac": creature["armor_class"]["default"],
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
        "damage_resistances": _unqualified_damage_types(creature, "damage_resistances"),
        "damage_immunities": _unqualified_damage_types(creature, "damage_immunities"),
        "damage_vulnerabilities": _unqualified_damage_types(creature, "damage_vulnerabilities"),
        "hp": creature["hit_points"]["average"],
        "source_ruleset": creature["source"]["ruleset"],
        "source_page": creature["source"]["page"],
        "source_anchor": creature["source"]["stat_block_anchor"],
        "source_url": catalog.source_url,
        "catalog_contract_version": catalog.contract_version,
        "catalog_sha256": catalog.sha256,
        "projection_id": DAMAGE_PROJECTION_ID,
        "projection_version": DAMAGE_PROJECTION_VERSION,
        "damage_consumer_requirements_sha256": requirements.sha256_for("damage_target"),
    }
    return DamageTarget(**base, target_sha256=_projection_identity(base))


def project_profile_damage_targets(
    entries: Iterable[RosterEntry],
    *,
    catalog: CreatureCatalog,
    requirements: ConsumerRequirements,
) -> list[tuple[RosterEntry, DamageTarget]]:
    """Project roster bindings without merging level or weight into target facts."""

    output: list[tuple[RosterEntry, DamageTarget]] = []
    for entry in entries:
        if entry.catalog_sha256 != catalog.sha256:
            raise CreatureCatalogError(
                "Roster entry catalog digest does not match loaded catalog"
            )
        output.append(
            (
                entry,
                project_damage_target(
                    entry.creature_id,
                    catalog=catalog,
                    requirements=requirements,
                ),
            )
        )
    return output
