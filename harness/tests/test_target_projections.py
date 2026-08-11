from __future__ import annotations

import ast
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from harness.creature_catalog import (
    CONTROL_PROJECTION_ID,
    CONTROL_PROJECTION_VERSION,
    DAMAGE_PROJECTION_ID,
    DAMAGE_PROJECTION_VERSION,
    DEFAULT_CONSUMER_REQUIREMENTS,
    HEADLINE_PROFILE_ID,
    ControlTarget,
    CreatureCatalogError,
    DamageTarget,
    canonical_sha256,
    load_catalog,
    load_consumer_requirements,
    load_profile,
    project_control_target,
    project_damage_target,
    project_profile_damage_targets,
)


class TargetProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()
        cls.requirements = load_consumer_requirements(catalog=cls.catalog)

    def assert_requirements_mutation_rejected(self, mutate: object, pattern: str) -> None:
        data = json.loads(DEFAULT_CONSUMER_REQUIREMENTS.read_text(encoding="utf-8"))
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "creature-consumers.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(CreatureCatalogError, pattern):
                load_consumer_requirements(path, catalog=self.catalog)

    def test_consumer_registry_matches_projection_contracts_and_exact_field_sets(self) -> None:
        damage = self.requirements.consumer("damage_target")
        control = self.requirements.consumer("control_target")
        planner = self.requirements.consumer("planner_static_target")
        self.assertEqual(
            damage["projection_contract"],
            {"id": DAMAGE_PROJECTION_ID, "version": DAMAGE_PROJECTION_VERSION},
        )
        self.assertEqual(
            control["projection_contract"],
            {"id": CONTROL_PROJECTION_ID, "version": CONTROL_PROJECTION_VERSION},
        )
        self.assertEqual(damage["output_fields"], list(DamageTarget.__dataclass_fields__))
        self.assertEqual(control["output_fields"], list(ControlTarget.__dataclass_fields__))
        self.assertIs(planner["implemented"], False)
        self.assertEqual(planner["typed_trait_policy"], "fail_closed_until_implemented")
        self.assertEqual(planner["output_fields"], [])

    def test_damage_projection_is_thin_and_preserves_current_damage_facts(self) -> None:
        target = project_damage_target(
            "srd521:aboleth", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(target.name, "Aboleth")
        self.assertEqual(target.ac, 17)
        self.assertEqual(target.saves["intelligence"], 8)
        self.assertTrue(target.magic_resistance is False)
        self.assertEqual(target.legendary_resistance, 3)
        self.assertEqual(target.legendary_resistance_lair, 4)
        self.assertEqual(target.legendary_resistance_policy, "metadata_only")
        self.assertEqual(target.size, "large")
        self.assertEqual(target.creature_type, "aberration")
        self.assertEqual(target.hp, 150)
        self.assertNotIn("movement", DamageTarget.__dataclass_fields__)
        self.assertNotIn("senses", DamageTarget.__dataclass_fields__)
        self.assertNotIn("condition_immunities", DamageTarget.__dataclass_fields__)
        self.assertNotIn("gear", DamageTarget.__dataclass_fields__)

    def test_control_projection_is_a_sibling_with_checks_saves_and_no_damage_packet(self) -> None:
        target = project_control_target(
            "srd521:aboleth", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(target.ability_modifiers["intelligence"], 4)
        self.assertEqual(target.saves["intelligence"], 8)
        self.assertEqual(target.ac, 17)
        self.assertEqual(target.legendary_resistance, 3)
        self.assertNotIn("hp", ControlTarget.__dataclass_fields__)
        self.assertNotIn("damage_resistances", ControlTarget.__dataclass_fields__)
        self.assertNotIn("damage_immunities", ControlTarget.__dataclass_fields__)
        self.assertNotIn("damage_vulnerabilities", ControlTarget.__dataclass_fields__)
        self.assertFalse(issubclass(ControlTarget, DamageTarget))
        self.assertFalse(issubclass(DamageTarget, ControlTarget))

    def test_control_projection_preserves_all_distinct_senses_ranges_and_limitations(self) -> None:
        storm_giant = project_control_target(
            "srd521:storm-giant", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(storm_giant.senses["darkvision"][0].range_feet, 120)
        self.assertEqual(storm_giant.senses["truesight"][0].range_feet, 30)
        self.assertEqual(storm_giant.senses["blindsight"], ())
        self.assertEqual(storm_giant.senses["tremorsense"], ())
        earth = project_control_target(
            "srd521:earth-elemental", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(earth.senses["tremorsense"][0].range_feet, 60)
        barbed = project_control_target(
            "srd521:barbed-devil", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(
            barbed.senses["darkvision"][0].limitation,
            "unimpeded by magical Darkness",
        )

    def test_control_projection_preserves_movement_hover_choices_and_form_qualifiers(self) -> None:
        storm_giant = project_control_target(
            "srd521:storm-giant", catalog=self.catalog, requirements=self.requirements
        )
        self.assertTrue(storm_giant.movement.hover)
        self.assertEqual(storm_giant.movement.sole_speed("fly"), 25)
        swarm = project_control_target(
            "srd521:swarm-of-insects", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(
            swarm.movement.choice_groups,
            (("movement_mode_choice_1", ("climb", "fly"), "GM’s choice"),),
        )
        with self.assertRaisesRegex(CreatureCatalogError, "one unconditional speed"):
            swarm.movement.sole_speed("fly")
        werebear = project_control_target(
            "srd521:werebear", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(werebear.movement.climb[0].qualifier, "bear form only")

    def test_communication_telepathy_and_static_gear_are_not_scenario_state(self) -> None:
        otyugh = project_control_target(
            "srd521:otyugh", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(otyugh.communication.telepathy.range_feet, 120)
        self.assertEqual(
            otyugh.communication.telepathy.limitation_id, "recipient_cannot_reply"
        )
        self.assertNotIn("telepathy", otyugh.senses)
        archmage = project_control_target(
            "srd521:archmage", catalog=self.catalog, requirements=self.requirements
        )
        self.assertTrue(any(item.category == "spellcasting_focus" for item in archmage.gear))
        forbidden = set(
            self.requirements.data["scenario_state_boundary"]["forbidden_static_fields"]
        )
        self.assertFalse(forbidden.intersection(ControlTarget.__dataclass_fields__))
        self.assertFalse(forbidden.intersection(DamageTarget.__dataclass_fields__))

    def test_qualified_condition_immunities_are_preserved_without_unconditional_flattening(self) -> None:
        archmage = project_control_target(
            "srd521:archmage", catalog=self.catalog, requirements=self.requirements
        )
        self.assertIn("charmed", archmage.condition_immunities)
        self.assertEqual(
            archmage.condition_immunity_facts[0].qualifier_id,
            "source_default_mind_blank",
        )
        familiar = project_control_target(
            "srd521:vampire-familiar", catalog=self.catalog, requirements=self.requirements
        )
        self.assertNotIn("charmed", familiar.condition_immunities)
        self.assertEqual(
            familiar.condition_immunity_facts[0].qualifier_id,
            "except_vampire_master",
        )

    def test_typed_passive_traits_are_preserved_and_unsupported_damage_traits_fail_closed(self) -> None:
        vampire = project_control_target(
            "srd521:vampire", catalog=self.catalog, requirements=self.requirements
        )
        trait_ids = {item.trait_id for item in vampire.passive_traits}
        self.assertIn("forbiddance", trait_ids)
        self.assertIn("legendary_resistance", trait_ids)
        with self.assertRaisesRegex(CreatureCatalogError, "unsupported material passive traits"):
            project_damage_target(
                "srd521:assassin", catalog=self.catalog, requirements=self.requirements
            )
        with self.assertRaisesRegex(CreatureCatalogError, "unsupported material passive traits"):
            project_damage_target(
                "srd521:half-dragon", catalog=self.catalog, requirements=self.requirements
            )
        with self.assertRaisesRegex(CreatureCatalogError, "unsupported material passive traits"):
            project_damage_target(
                "srd521:clay-golem", catalog=self.catalog, requirements=self.requirements
            )

    def test_projection_and_profile_digests_bind_exact_inputs_without_merging_roster_state(self) -> None:
        entries = load_profile(catalog=self.catalog, levels={7})
        projected = project_profile_damage_targets(
            entries, catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(len(projected), 12)
        for entry, target in projected:
            self.assertEqual(entry.profile_id, HEADLINE_PROFILE_ID)
            self.assertEqual(entry.creature_id, target.creature_id)
            self.assertEqual(entry.catalog_sha256, target.catalog_sha256)
            self.assertNotIn("benchmark_level", DamageTarget.__dataclass_fields__)
            self.assertNotIn("weight", DamageTarget.__dataclass_fields__)
        damage = projected[0][1]
        damage_record = asdict(damage)
        target_digest = damage_record.pop("target_sha256")
        self.assertEqual(target_digest, canonical_sha256(damage_record))
        control = project_control_target(
            damage.creature_id, catalog=self.catalog, requirements=self.requirements
        )
        control_record = asdict(control)
        control_digest = control_record.pop("target_sha256")
        self.assertEqual(control_digest, canonical_sha256(control_record))
        self.assertNotEqual(damage.target_sha256, control.target_sha256)

    def test_missing_fields_unknown_creatures_and_requirement_drift_fail_closed(self) -> None:
        with self.assertRaisesRegex(CreatureCatalogError, "Unknown creature_id"):
            project_damage_target(
                "srd521:not-a-creature", catalog=self.catalog, requirements=self.requirements
            )
        self.assert_requirements_mutation_rejected(
            lambda value: value["consumers"]["damage_target"]["required_catalog_paths"].append("current_position"),
            "required field 'current_position' is absent",
        )
        self.assert_requirements_mutation_rejected(
            lambda value: value["scenario_state_boundary"]["forbidden_static_fields"].pop(),
            "complete scenario-state exclusion boundary",
        )
        self.assert_requirements_mutation_rejected(
            lambda value: value["consumers"]["control_target"]["output_fields"].append("current_position"),
            "output_fields disagrees",
        )

    def test_shared_module_has_no_damage_or_control_evaluator_import_cycle(self) -> None:
        source_path = Path(__file__).parents[1] / "creature_catalog.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        forbidden = {
            "harness.damage_harness",
            "harness.control_engine",
            "harness.model",
            "harness.control_targets",
        }
        self.assertFalse(imports.intersection(forbidden))


if __name__ == "__main__":
    unittest.main()
