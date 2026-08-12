from __future__ import annotations

import ast
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path

from harness.creature_catalog import (
    CENSUS_PROFILE_ID,
    DEFAULT_CONSUMER_REQUIREMENTS,
    HEADLINE_PROFILE_ID,
    SKILL_IDS,
    CreatureCatalogError,
    canonical_sha256,
    consumer_requirements_sha256_by_id,
    load_catalog,
    load_consumer_requirements,
    load_profile,
)
from harness.creature_control_projection import (
    CONTROL_PROJECTION_ID,
    CONTROL_PROJECTION_VERSION,
    ControlTarget,
    SKILL_ABILITY_BY_ID,
    SkillBonusFact,
    project_control_target,
)
from harness.creature_damage_projection import (
    DAMAGE_PROJECTION_ID,
    DAMAGE_PROJECTION_VERSION,
    DamageTarget,
    project_damage_target,
    project_profile_damage_targets,
)
from harness.control_engine import _control_target_projection_digest
from harness.damage_harness import _projection_digest as _damage_target_projection_digest


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

    def load_requirements_mutation(self, mutate: object):
        data = json.loads(DEFAULT_CONSUMER_REQUIREMENTS.read_text(encoding="utf-8"))
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "creature-consumers.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return load_consumer_requirements(path, catalog=self.catalog)

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
        self.assertEqual(tuple(damage["output_fields"]), tuple(DamageTarget.__dataclass_fields__))
        self.assertEqual(tuple(control["output_fields"]), tuple(ControlTarget.__dataclass_fields__))
        self.assertIn("damage_consumer_requirements_sha256", DamageTarget.__dataclass_fields__)
        self.assertIn("control_consumer_requirements_sha256", ControlTarget.__dataclass_fields__)
        self.assertNotIn("requirements_sha256", DamageTarget.__dataclass_fields__)
        self.assertNotIn("requirements_sha256", ControlTarget.__dataclass_fields__)
        self.assertIs(planner["implemented"], False)
        self.assertEqual(planner["typed_trait_policy"], "fail_closed_until_implemented")
        self.assertEqual(planner["output_fields"], ())
        self.assertEqual(tuple(SKILL_ABILITY_BY_ID), SKILL_IDS)
        self.assertEqual(
            dict(SKILL_ABILITY_BY_ID),
            {
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
            },
        )

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

    def test_control_projection_preserves_explicit_skills_passive_perception_and_fallback(self) -> None:
        def check_bonus(target: ControlTarget, skill_id: str) -> tuple[bool, int]:
            explicit = next(
                (fact.bonus for fact in target.skills if fact.skill_id == skill_id),
                None,
            )
            if explicit is not None:
                return True, explicit
            return False, target.ability_modifiers[SKILL_ABILITY_BY_ID[skill_id]]

        giant_ape = project_control_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=self.requirements
        )
        athletics = next(
            fact for fact in giant_ape.skills if fact.skill_id == "athletics"
        )
        self.assertEqual(
            athletics,
            SkillBonusFact("athletics", "strength", 9, source_explicit=True),
        )
        self.assertEqual(giant_ape.passive_perception, 14)
        self.assertEqual(check_bonus(giant_ape, "athletics"), (True, 9))

        archmage = project_control_target(
            "srd521:archmage", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(archmage.ability_modifiers["strength"], 0)
        self.assertEqual(check_bonus(archmage, "athletics"), (False, 0))

        aboleth = project_control_target(
            "srd521:aboleth", catalog=self.catalog, requirements=self.requirements
        )
        self.assertEqual(check_bonus(aboleth, "athletics"), (False, 5))
        payload = {
            field.name: getattr(aboleth, field.name)
            for field in fields(aboleth)
            if field.name != "target_sha256"
        }
        payload["skills"] = (
            SkillBonusFact("athletics", "strength", 0, True),
            *aboleth.skills,
        )
        explicit_zero = ControlTarget(
            **payload,
            target_sha256=canonical_sha256(payload),
        )
        self.assertEqual(check_bonus(explicit_zero, "athletics"), (True, 0))

    def test_skill_fact_rejects_unknown_ability_mismatch_and_rewritten_source_status(self) -> None:
        with self.assertRaisesRegex(CreatureCatalogError, "Unknown canonical skill ID"):
            SkillBonusFact("unknown_skill", "strength", 0, True)
        with self.assertRaisesRegex(CreatureCatalogError, "must use ability 'strength'"):
            SkillBonusFact("athletics", "dexterity", 9, True)
        with self.assertRaisesRegex(CreatureCatalogError, "source_explicit=true"):
            SkillBonusFact("athletics", "strength", 9, False)

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
        damage_record = {
            field.name: getattr(damage, field.name)
            for field in fields(damage)
            if field.name != "target_sha256"
        }
        target_digest = damage.target_sha256
        self.assertEqual(target_digest, canonical_sha256(damage_record))
        control = project_control_target(
            damage.creature_id, catalog=self.catalog, requirements=self.requirements
        )
        control_record = {
            field.name: getattr(control, field.name)
            for field in fields(control)
            if field.name != "target_sha256"
        }
        control_digest = control.target_sha256
        self.assertEqual(control_digest, canonical_sha256(control_record))
        self.assertNotEqual(damage.target_sha256, control.target_sha256)
        self.assertEqual(
            damage.damage_consumer_requirements_sha256,
            self.requirements.sha256_for("damage_target"),
        )
        self.assertEqual(
            control.control_consumer_requirements_sha256,
            self.requirements.sha256_for("control_target"),
        )
        self.assertEqual(
            damage,
            project_damage_target(
                damage.creature_id,
                catalog=self.catalog,
                requirements=self.requirements,
            ),
        )
        self.assertEqual(
            control,
            project_control_target(
                control.creature_id,
                catalog=self.catalog,
                requirements=self.requirements,
            ),
        )

    def test_all_headline_and_census_control_targets_project_canonically(self) -> None:
        expected_counts = {HEADLINE_PROFILE_ID: 47, CENSUS_PROFILE_ID: 93}
        for profile_id, expected_count in expected_counts.items():
            with self.subTest(profile_id=profile_id):
                entries = load_profile(profile_id, catalog=self.catalog)
                targets = [
                    project_control_target(
                        entry.creature_id,
                        catalog=self.catalog,
                        requirements=self.requirements,
                    )
                    for entry in entries
                ]
                self.assertEqual(len(targets), expected_count)
                self.assertEqual(
                    [target.creature_id for target in targets],
                    [entry.creature_id for entry in entries],
                )
                for target in targets:
                    skill_ids = [fact.skill_id for fact in target.skills]
                    self.assertEqual(skill_ids, sorted(skill_ids))
                    self.assertEqual(len(skill_ids), len(set(skill_ids)))
                    self.assertTrue(all(fact.source_explicit for fact in target.skills))
                    self.assertTrue(
                        all(
                            fact.ability_id == SKILL_ABILITY_BY_ID[fact.skill_id]
                            for fact in target.skills
                        )
                    )
                    self.assertIsInstance(target.passive_perception, int)

    def test_consumer_digests_are_isolated_and_shared_inputs_bind_every_consumer(self) -> None:
        baseline = self.requirements
        control_mutation = self.load_requirements_mutation(
            lambda value: value["consumers"]["control_target"]["qualifier_policy"].__setitem__(
                "skills", "listed_final_bonus_else_associated_raw_ability_modifier_test"
            )
        )
        self.assertNotEqual(
            control_mutation.sha256_for("control_target"),
            baseline.sha256_for("control_target"),
        )
        self.assertEqual(
            control_mutation.sha256_for("damage_target"),
            baseline.sha256_for("damage_target"),
        )
        self.assertEqual(
            control_mutation.sha256_for("planner_static_target"),
            baseline.sha256_for("planner_static_target"),
        )

        damage_mutation = self.load_requirements_mutation(
            lambda value: value["consumers"]["damage_target"]["qualifier_policy"].__setitem__(
                "size", "first_source_authored_option_test"
            )
        )
        self.assertNotEqual(
            damage_mutation.sha256_for("damage_target"),
            baseline.sha256_for("damage_target"),
        )
        self.assertEqual(
            damage_mutation.sha256_for("control_target"),
            baseline.sha256_for("control_target"),
        )
        self.assertEqual(
            damage_mutation.sha256_for("planner_static_target"),
            baseline.sha256_for("planner_static_target"),
        )

        raw = json.loads(DEFAULT_CONSUMER_REQUIREMENTS.read_text(encoding="utf-8"))
        baseline_digests = consumer_requirements_sha256_by_id(raw)
        changed_raw = deepcopy(raw)
        changed_raw["scenario_state_boundary"]["policy"] += "_test"
        changed_digests = consumer_requirements_sha256_by_id(changed_raw)
        self.assertEqual(set(baseline_digests), set(changed_digests))
        self.assertTrue(
            all(
                changed_digests[consumer_id] != baseline_digests[consumer_id]
                for consumer_id in baseline_digests
            )
        )
        self.assert_requirements_mutation_rejected(
            lambda value: value["scenario_state_boundary"].__setitem__(
                "policy", "unsupported_live_state_policy"
            ),
            "Unsupported scenario-state boundary policy",
        )

    def test_sibling_requirement_mutations_leave_target_values_and_hashes_unchanged(self) -> None:
        baseline_damage = project_damage_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=self.requirements
        )
        control_mutation = self.load_requirements_mutation(
            lambda value: value["consumers"]["control_target"]["qualifier_policy"].__setitem__(
                "skills", "listed_final_bonus_else_associated_raw_ability_modifier_test"
            )
        )
        changed_damage = project_damage_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=control_mutation
        )
        self.assertEqual(changed_damage, baseline_damage)

        baseline_control = project_control_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=self.requirements
        )
        damage_mutation = self.load_requirements_mutation(
            lambda value: value["consumers"]["damage_target"]["qualifier_policy"].__setitem__(
                "size", "first_source_authored_option_test"
            )
        )
        changed_control = project_control_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=damage_mutation
        )
        self.assertEqual(changed_control, baseline_control)

    def test_loaded_requirements_are_immutable_and_cannot_reuse_a_stale_digest(self) -> None:
        with self.assertRaises(TypeError):
            self.requirements.data["consumers"]["damage_target"][
                "unsupported_material_trait_ids"
            ] = ()
        with self.assertRaises(TypeError):
            self.requirements.consumer("control_target")["qualifier_policy"][
                "skills"
            ] = "rewritten_after_load"

    def test_target_identity_rejects_post_projection_skill_or_perception_changes(self) -> None:
        target = project_control_target(
            "srd521:giant-ape", catalog=self.catalog, requirements=self.requirements
        )
        entry = next(
            item
            for item in load_profile(catalog=self.catalog)
            if item.creature_id == target.creature_id
        )
        for replacement in (
            {"passive_perception": target.passive_perception + 1},
            {"skills": ()},
        ):
            with self.assertRaisesRegex(CreatureCatalogError, "changed after identity"):
                replace(target, **replacement)

    def test_control_only_projection_facts_change_control_but_not_damage_projection(self) -> None:
        creature_id = "srd521:giant-ape"
        entry = next(
            item
            for item in load_profile(catalog=self.catalog)
            if item.creature_id == creature_id
        )
        baseline_control = project_control_target(
            creature_id, catalog=self.catalog, requirements=self.requirements
        )
        baseline_damage = project_damage_target(
            creature_id, catalog=self.catalog, requirements=self.requirements
        )
        baseline_aggregate = _control_target_projection_digest(
            (entry,), (baseline_control,)
        )
        baseline_damage_aggregate = _damage_target_projection_digest(
            [entry], [baseline_damage]
        )
        for field_name in ("passive_perception", "skills"):
            with self.subTest(field_name=field_name):
                payload = {
                    field.name: getattr(baseline_control, field.name)
                    for field in fields(baseline_control)
                    if field.name != "target_sha256"
                }
                if field_name == "passive_perception":
                    payload[field_name] = baseline_control.passive_perception + 1
                else:
                    payload[field_name] = tuple(
                        replace(fact, bonus=fact.bonus + 1)
                        if fact.skill_id == "athletics"
                        else fact
                        for fact in baseline_control.skills
                    )
                changed_control = ControlTarget(
                    **payload,
                    target_sha256=canonical_sha256(payload),
                )
                self.assertNotEqual(changed_control.target_sha256, baseline_control.target_sha256)
                self.assertNotEqual(
                    _control_target_projection_digest((entry,), (changed_control,)),
                    baseline_aggregate,
                )
                self.assertEqual(
                    project_damage_target(
                        creature_id,
                        catalog=self.catalog,
                        requirements=self.requirements,
                    ),
                    baseline_damage,
                )
                self.assertEqual(
                    _damage_target_projection_digest([entry], [baseline_damage]),
                    baseline_damage_aggregate,
                )

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
        changed_output = self.load_requirements_mutation(
            lambda value: value["consumers"]["control_target"]["output_fields"].append(
                "current_position"
            )
        )
        with self.assertRaisesRegex(CreatureCatalogError, "output_fields disagrees"):
            project_control_target(
                "srd521:aboleth",
                catalog=self.catalog,
                requirements=changed_output,
            )
        for field, replacement, pattern in (
            ("implemented", True, "maintained runtime boundary"),
            ("projection_contract", {"id": "wrong_planner", "version": "999.0.0"}, "draft 1.0.0 identity"),
            ("typed_trait_policy", "silently_accept_everything", "fail closed on typed traits"),
            ("qualifier_policy", {"all": "accept_everything"}, "fail closed on all qualifiers"),
        ):
            with self.subTest(planner_field=field):
                self.assert_requirements_mutation_rejected(
                    lambda value, field=field, replacement=replacement: value[
                        "consumers"
                    ]["planner_static_target"].__setitem__(field, replacement),
                    pattern,
                )

    def test_projection_modules_and_consumers_follow_one_way_import_boundaries(self) -> None:
        harness_root = Path(__file__).parents[1]

        def imports(filename: str) -> set[str]:
            tree = ast.parse((harness_root / filename).read_text(encoding="utf-8"))
            found: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module.rsplit(".", 1)[-1])
            return found

        common = imports("creature_catalog.py")
        damage = imports("creature_damage_projection.py")
        control = imports("creature_control_projection.py")
        damage_harness = imports("damage_harness.py")
        control_engine = imports("control_engine.py")

        self.assertFalse(
            common.intersection(
                {
                    "creature_damage_projection",
                    "creature_control_projection",
                    "damage_harness",
                    "control_engine",
                    "model",
                }
            )
        )
        self.assertIn("creature_catalog", damage)
        self.assertIn("creature_catalog", control)
        self.assertFalse(
            damage.intersection(
                {"creature_control_projection", "damage_harness", "control_engine", "model"}
            )
        )
        self.assertFalse(
            control.intersection(
                {"creature_damage_projection", "damage_harness", "control_engine", "model"}
            )
        )
        self.assertTrue(
            {"creature_catalog", "creature_damage_projection"}.issubset(damage_harness)
        )
        self.assertNotIn("creature_control_projection", damage_harness)
        self.assertTrue(
            {"creature_catalog", "creature_control_projection"}.issubset(control_engine)
        )
        self.assertNotIn("creature_damage_projection", control_engine)


if __name__ == "__main__":
    unittest.main()
