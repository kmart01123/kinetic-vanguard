from __future__ import annotations

import json
import math
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from harness.control_catalog import (
    CATALOG_VERSION,
    DEFAULT_CONTROL_CATALOG,
    DEFAULT_CONTROL_PROVENANCE,
    DEFAULT_ENGINE_CONFIG,
    ENGINE_CONFIG_VERSION,
    NORMALIZATION_RULES_VERSION,
    PRIMITIVE_CONTRACT,
    PRIMITIVE_CONTRACT_VERSION,
    TIMELINE_ENGINE_VERSION,
    CatalogError,
    SenseContext,
    SenseContextError,
    expand_condition,
    load_control_catalog,
    load_engine_config,
    query_sense,
    sha256_file,
    validate_control_catalog,
    validate_engine_config,
)


def _catalog_value() -> dict[str, object]:
    return json.loads(DEFAULT_CONTROL_CATALOG.read_text(encoding="utf-8"))


def _condition(value: dict[str, object], condition_id: str) -> dict[str, object]:
    return next(item for item in value["conditions"] if item["condition_id"] == condition_id)  # type: ignore[index,union-attr]


class SrdConsequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_control_catalog()

    def test_srd_consequence_scope_versions_and_pages_are_exact(self) -> None:
        self.assertEqual(CATALOG_VERSION, "2.0.0")
        self.assertEqual(PRIMITIVE_CONTRACT_VERSION, "2.0.0")
        self.assertEqual(self.catalog.catalog_version, CATALOG_VERSION)
        self.assertEqual(self.catalog.primitive_contract_version, PRIMITIVE_CONTRACT_VERSION)
        self.assertEqual(
            {condition_id: row.source_page for condition_id, row in self.catalog.conditions.items()},
            {
                "blinded": 176,
                "charmed": 177,
                "frightened": 181,
                "incapacitated": 183,
                "prone": 185,
                "restrained": 186,
                "stunned": 188,
            },
        )
        self.assertEqual(
            set(PRIMITIVE_CONTRACT),
            {
                "active_turn_denial",
                "reaction_denial",
                "offensive_impairment_next_attack",
                "offensive_impairment_all_attacks",
                "target_choice_restriction",
                "sight_option_denial",
                "mobility_loss_feet",
                "movement_mode_denial",
                "forced_displacement",
                "geometry_sensitive_approach_restriction",
                "defensive_attack_advantage",
                "defense_numerical_reduction",
                "save_disadvantage",
                "save_auto_failure",
                "sight_dependent_opportunity",
                "ability_check_impairment",
                "speech_denial",
                "social_interaction_advantage",
                "concentration_break",
                "persistent_elevation",
                "fall_transition",
                "nonsight_location_awareness",
                "prone_incoming_attack_context",
                "initiative_disadvantage",
            },
        )

    def test_srd_blinded_preserves_sight_checks_and_both_attack_directions(self) -> None:
        specs = expand_condition(self.catalog, "blinded")
        self.assertEqual(
            [item.primitive_id for item in specs],
            [
                "sight_option_denial",
                "ability_check_impairment",
                "offensive_impairment_all_attacks",
                "defensive_attack_advantage",
            ],
        )
        by_id = {item.primitive_id: item for item in specs}
        sight = by_id["sight_option_denial"]
        ability = by_id["ability_check_impairment"]
        outgoing = by_id["offensive_impairment_all_attacks"]
        incoming = by_id["defensive_attack_advantage"]
        self.assertIs(sight.predicate_values["alternative_sight_available"], False)
        self.assertIs(ability.predicate_values["alternative_sight_available"], False)
        self.assertEqual(ability.status, "retained_unpriced")
        self.assertEqual(ability.qualifier_values["ability_check_effect"], "automatic_failure")
        self.assertTrue(ability.predicate_values["ability_check_depends_on_sight"])
        for attack_fact in (outgoing, incoming):
            self.assertEqual(attack_fact.unit, "attack_opportunity")
            self.assertNotIn("alternative_sight_available", attack_fact.predicate_values)
            self.assertNotIn("alternative_sight_resolution", attack_fact.context_requirements)

    def test_srd_charmed_is_source_specific_and_not_turn_denial(self) -> None:
        specs = expand_condition(self.catalog, "charmed")
        self.assertEqual(
            [item.primitive_id for item in specs],
            ["target_choice_restriction", "social_interaction_advantage"],
        )
        self.assertNotIn("active_turn_denial", {item.primitive_id for item in specs})
        self.assertEqual(specs[0].unit, "action_proposal")
        self.assertEqual(specs[0].qualifier_values["restricted_target_relation"], "charmer")
        self.assertEqual(
            specs[0].qualifier_values["restricted_choice_kinds"],
            ("attack", "damaging_ability", "damaging_magical_effect"),
        )
        self.assertEqual(specs[1].status, "retained_unpriced")
        self.assertTrue(all("source_actor_id" in item.context_requirements for item in specs))

    def test_srd_frightened_separates_line_of_sight_impairment_from_approach(self) -> None:
        specs = expand_condition(self.catalog, "frightened")
        attacks = next(item for item in specs if item.primitive_id == "offensive_impairment_all_attacks")
        checks = next(item for item in specs if item.primitive_id == "ability_check_impairment")
        approach = next(
            item for item in specs if item.primitive_id == "geometry_sensitive_approach_restriction"
        )
        self.assertTrue(attacks.predicate_values["source_in_line_of_sight"])
        self.assertTrue(checks.predicate_values["source_in_line_of_sight"])
        self.assertNotIn("source_in_line_of_sight", approach.predicate_values)
        self.assertTrue(approach.predicate_values["movement_is_willing"])
        self.assertEqual(approach.qualifier_values["movement_relation"], "closer_to_source")
        self.assertTrue(all("source_actor_id" in item.context_requirements for item in specs))

    def test_srd_incapacitated_denies_actions_reactions_speech_and_breaks_real_concentration(self) -> None:
        specs = expand_condition(self.catalog, "incapacitated")
        by_id = {item.primitive_id: item for item in specs}
        self.assertEqual(
            set(by_id),
            {
                "active_turn_denial",
                "reaction_denial",
                "initiative_disadvantage",
                "concentration_break",
                "speech_denial",
                "fall_transition",
            },
        )
        self.assertEqual(by_id["active_turn_denial"].qualifier_values["denied_turn_options"], ("action", "bonus_action"))
        self.assertTrue(by_id["concentration_break"].predicate_values["target_is_concentrating"])
        self.assertEqual(by_id["initiative_disadvantage"].unit, "initiative_opportunity")
        self.assertEqual(by_id["initiative_disadvantage"].status, "retained_unpriced")
        self.assertEqual(by_id["speech_denial"].status, "retained_unpriced")
        self.assertNotIn("mobility_loss_feet", by_id)

    def test_srd_prone_preserves_crawl_stand_distance_and_airborne_rules(self) -> None:
        condition = self.catalog.conditions["prone"]
        self.assertEqual(
            [item.response_id for item in condition.response_mechanics],
            ["remain_prone", "stand_from_prone", "voluntarily_drop_prone", "crawl_while_prone"],
        )
        self.assertTrue(
            all(item.timing == "explicit_operation_proposal" for item in condition.response_mechanics)
        )
        self.assertEqual(
            condition.response_mechanics[1].effects,
            ("spend_half_current_speed_rounded_down", "end_prone", "retain_remaining_movement"),
        )
        self.assertEqual(
            condition.response_mechanics[2].effects,
            ("spend_no_action", "spend_no_speed", "apply_prone"),
        )
        self.assertEqual(
            condition.response_mechanics[3].effects,
            (
                "retain_prone",
                "spend_one_extra_foot_per_foot",
                "spend_two_extra_feet_per_foot_in_difficult_terrain",
            ),
        )
        self.assertEqual(condition.end_mechanics, ("explicit_stand_operation", "source_end"))
        specs = expand_condition(self.catalog, "prone")
        near = next(item for item in specs if item.primitive_id == "defensive_attack_advantage")
        far = next(item for item in specs if item.primitive_id == "prone_incoming_attack_context")
        fall = next(item for item in specs if item.primitive_id == "fall_transition")
        self.assertEqual(near.predicate_values["attacker_distance_band"], "within_5_feet")
        self.assertEqual(far.predicate_values["attacker_distance_band"], "farther_than_5_feet")
        self.assertEqual(far.status, "retained_unpriced")
        self.assertTrue(fall.predicate_values["target_is_airborne"])
        self.assertFalse(fall.predicate_values["hover_or_explicit_fall_prevention"])

    def test_srd_restrained_has_speed_zero_attack_effects_and_dexterity_save_disadvantage(self) -> None:
        specs = expand_condition(self.catalog, "restrained")
        by_id = {item.primitive_id: item for item in specs}
        self.assertEqual(
            set(by_id),
            {
                "mobility_loss_feet",
                "defensive_attack_advantage",
                "offensive_impairment_all_attacks",
                "save_disadvantage",
            },
        )
        self.assertEqual(
            by_id["mobility_loss_feet"].qualifier_values["movement_modes"],
            ("walk", "fly", "swim", "climb", "burrow"),
        )
        self.assertEqual(by_id["mobility_loss_feet"].qualifier_values["mobility_effect"], "speed_zero")
        self.assertEqual(by_id["save_disadvantage"].qualifier_values["save_ability"], "dexterity")

    def test_srd_stunned_includes_incapacitated_exactly_once_without_speed_zero(self) -> None:
        specs = expand_condition(self.catalog, "stunned")
        self.assertEqual(self.catalog.conditions["stunned"].includes, ("incapacitated",))
        self.assertEqual(sum(item.primitive_id == "active_turn_denial" for item in specs), 1)
        self.assertEqual(sum(item.primitive_id == "reaction_denial" for item in specs), 1)
        self.assertEqual(sum(item.primitive_id == "speech_denial" for item in specs), 1)
        self.assertNotIn("mobility_loss_feet", {item.primitive_id for item in specs})
        saves = [item for item in specs if item.primitive_id == "save_auto_failure"]
        self.assertEqual(
            {item.qualifier_values["save_ability"] for item in saves},
            {"strength", "dexterity"},
        )
        self.assertTrue(all(item.dominates == ("save_disadvantage",) for item in saves))
        inherited = next(item for item in specs if item.primitive_id == "active_turn_denial")
        self.assertEqual(inherited.source_condition_ids, ("incapacitated",))


class SenseQueryTests(unittest.TestCase):
    def test_sense_blindsight_is_range_and_total_cover_specific(self) -> None:
        senses = [{"sense": "blindsight", "range_ft": 30, "limitation": None}]
        inside = query_sense(senses, 20, False, None, None)
        outside = query_sense(senses, 35, False, None, None)
        covered = query_sense(senses, 20, True, None, None)
        self.assertIs(inside.alternative_sight, True)
        self.assertIs(outside.alternative_sight, False)
        self.assertIs(covered.alternative_sight, False)
        self.assertIs(inside.location_detection, False)
        self.assertIn("blindsight_within_range_without_total_cover", inside.alternative_sight_evidence)

    def test_sense_tremorsense_locates_but_never_supplies_sight(self) -> None:
        senses = [{"sense": "tremorsense", "range_ft": 60, "limitation": None}]
        contact = query_sense(senses, context=SenseContext(40, False, False, True))
        airborne = query_sense(senses, 40, False, True, True)
        airborne_without_surface_context = query_sense(senses, 40, False, True, None)
        separate_surface = query_sense(senses, 40, False, False, False)
        self.assertIs(contact.alternative_sight, False)
        self.assertIs(contact.location_detection, True)
        self.assertIs(airborne.location_detection, False)
        self.assertIs(airborne_without_surface_context.location_detection, False)
        self.assertEqual(airborne_without_surface_context.location_detection_missing_context, ())
        self.assertIs(separate_surface.location_detection, False)
        self.assertIn("tremorsense_excludes_airborne_target", airborne.location_detection_evidence)

    def test_sense_missing_required_context_is_unresolved_or_fail_closed(self) -> None:
        blindsight = [{"sense": "blindsight", "range_ft": 30, "limitation": None}]
        unresolved_blind = query_sense(blindsight, None, False, None, None)
        self.assertIsNone(unresolved_blind.alternative_sight)
        self.assertEqual(unresolved_blind.alternative_sight_missing_context, ("interaction_distance_ft",))
        with self.assertRaisesRegex(SenseContextError, "missing context"):
            query_sense(blindsight, None, False, None, None, fail_closed=True)

        tremor = [{"sense": "tremorsense", "range_ft": 60, "limitation": None}]
        unresolved_tremor = query_sense(tremor, 30, False, None, None)
        self.assertIsNone(unresolved_tremor.location_detection)
        self.assertEqual(
            unresolved_tremor.location_detection_missing_context,
            ("target_airborne", "same_surface_or_liquid"),
        )
        with self.assertRaises(SenseContextError):
            query_sense(tremor, 30, False, None, None, fail_closed=True)

    def test_sense_truesight_is_not_in_the_nonvisual_boundary(self) -> None:
        with self.assertRaisesRegex(CatalogError, "not in the nonvisual input boundary: truesight"):
            query_sense([{"sense": "truesight", "range_ft": 120, "limitation": None}], 10, False, False, True)


class CatalogInvariantTests(unittest.TestCase):
    def test_catalog_invariant_rejects_unknown_fields_primitives_and_contract_drift(self) -> None:
        cases: list[tuple[object, str]] = []

        unknown_field = _catalog_value()
        unknown_field["weight"] = 1
        cases.append((unknown_field, "unknown=.*weight"))

        unknown_primitive = _catalog_value()
        _condition(unknown_primitive, "blinded")["primitives"][0]["primitive_id"] = "unknown_primitive"  # type: ignore[index]
        cases.append((unknown_primitive, "primitive_id is unknown"))

        wrong_unit = _catalog_value()
        _condition(wrong_unit, "blinded")["primitives"][0]["unit"] = "reaction_window"  # type: ignore[index]
        cases.append((wrong_unit, "family/unit disagree"))

        for value, pattern in cases:
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(CatalogError, pattern):
                    validate_control_catalog(value)

    def test_catalog_invariant_rejects_removal_of_each_required_primitive(self) -> None:
        canonical = _catalog_value()
        for condition in canonical["conditions"]:  # type: ignore[union-attr]
            condition_id = condition["condition_id"]
            for primitive_index, primitive in enumerate(condition["primitives"]):
                primitive_id = primitive["primitive_id"]
                value = deepcopy(canonical)
                del _condition(value, condition_id)["primitives"][primitive_index]  # type: ignore[index]
                with self.subTest(condition_id=condition_id, primitive_id=primitive_id):
                    with self.assertRaisesRegex(
                        CatalogError,
                        rf"condition {condition_id} semantics .* signature exactly",
                    ):
                        validate_control_catalog(value)

    def test_catalog_invariant_rejects_change_to_each_required_primitive(self) -> None:
        canonical = _catalog_value()
        for condition in canonical["conditions"]:  # type: ignore[union-attr]
            condition_id = condition["condition_id"]
            for primitive_index, primitive in enumerate(condition["primitives"]):
                primitive_id = primitive["primitive_id"]
                qualifier_ids = {
                    qualifier["qualifier_id"] for qualifier in primitive["qualifiers"]
                }
                added_qualifier = (
                    {"qualifier_id": "sense_mode", "value": "physical_sight"}
                    if "social_actor_relation" in qualifier_ids
                    else {"qualifier_id": "social_actor_relation", "value": "charmer"}
                )
                value = deepcopy(canonical)
                mutated = _condition(value, condition_id)["primitives"][primitive_index]  # type: ignore[index]
                mutated["qualifiers"].append(added_qualifier)
                with self.subTest(condition_id=condition_id, primitive_id=primitive_id):
                    with self.assertRaisesRegex(
                        CatalogError,
                        rf"condition {condition_id} semantics .* signature exactly",
                    ):
                        validate_control_catalog(value)

    def test_catalog_invariant_pins_all_condition_and_primitive_semantics(self) -> None:
        cases: list[tuple[str, str, dict[str, object]]] = []

        includes = _catalog_value()
        _condition(includes, "stunned")["includes"] = []
        cases.append(("includes", "stunned", includes))

        family = _catalog_value()
        _condition(family, "blinded")["default_diagnostic_family"] = "enablement"
        cases.append(("default family", "blinded", family))

        response = _catalog_value()
        del _condition(response, "prone")["response_mechanics"][0]  # type: ignore[index]
        cases.append(("response", "prone", response))

        ending = _catalog_value()
        _condition(ending, "charmed")["end_mechanics"] = []
        cases.append(("end", "charmed", ending))

        condition_context = _catalog_value()
        _condition(condition_context, "restrained")["context_requirements"] = [
            "source_actor_id",
            "movement_mode_speeds_ft",
        ]
        cases.append(("condition context", "restrained", condition_context))

        primitive_header = _catalog_value()
        _condition(primitive_header, "charmed")["primitives"][0].update(  # type: ignore[index]
            {
                "primitive_id": "offensive_impairment_all_attacks",
                "family": "denial",
                "unit": "attack_opportunity",
                "status": "candidate",
            }
        )
        cases.append(("primitive header", "charmed", primitive_header))

        predicate = _catalog_value()
        _condition(predicate, "blinded")["primitives"][0]["predicates"][0]["value"] = True  # type: ignore[index]
        cases.append(("predicate", "blinded", predicate))

        qualifier = _catalog_value()
        _condition(qualifier, "blinded")["primitives"][1]["qualifiers"][0][  # type: ignore[index]
            "value"
        ] = "disadvantage"
        cases.append(("qualifier", "blinded", qualifier))

        primitive_context = _catalog_value()
        _condition(primitive_context, "frightened")["primitives"][0][
            "context_requirements"
        ] = ["source_actor_id"]  # type: ignore[index]
        cases.append(("primitive context", "frightened", primitive_context))

        dominance = _catalog_value()
        _condition(dominance, "stunned")["primitives"][0]["dominates"] = []  # type: ignore[index]
        cases.append(("dominance", "stunned", dominance))

        for semantic_field, condition_id, value in cases:
            with self.subTest(semantic_field=semantic_field):
                with self.assertRaisesRegex(
                    CatalogError,
                    rf"condition {condition_id} semantics .* signature exactly",
                ):
                    validate_control_catalog(value)

    def test_catalog_invariant_rejects_unversioned_duplicate_unstable_and_bad_page_data(self) -> None:
        unversioned = _catalog_value()
        del unversioned["catalog_version"]
        with self.assertRaisesRegex(CatalogError, "missing=.*catalog_version"):
            validate_control_catalog(unversioned)

        duplicate = _catalog_value()
        duplicate["conditions"].append(deepcopy(duplicate["conditions"][0]))  # type: ignore[union-attr,index]
        with self.assertRaisesRegex(CatalogError, "duplicate condition ID"):
            validate_control_catalog(duplicate)

        unstable = _catalog_value()
        _condition(unstable, "blinded")["condition_id"] = "Blinded"
        with self.assertRaisesRegex(CatalogError, "stable snake_case ID"):
            validate_control_catalog(unstable)

        bad_page = _catalog_value()
        _condition(bad_page, "prone")["source_page"] = 999
        with self.assertRaisesRegex(CatalogError, "pinned SRD page 185"):
            validate_control_catalog(bad_page)

    def test_catalog_invariant_rejects_condition_inclusion_cycles(self) -> None:
        value = _catalog_value()
        _condition(value, "blinded")["includes"] = ["charmed"]
        _condition(value, "charmed")["includes"] = ["blinded"]
        with self.assertRaisesRegex(CatalogError, "Condition inclusion cycle: blinded -> charmed -> blinded"):
            validate_control_catalog(value)

    def test_catalog_invariant_rejects_contradictory_predicates(self) -> None:
        value = _catalog_value()
        primitive = _condition(value, "blinded")["primitives"][0]  # type: ignore[index]
        primitive["predicates"].append(  # type: ignore[union-attr]
            {"predicate_id": "alternative_sight_available", "value": True}
        )
        with self.assertRaisesRegex(CatalogError, "contradictory predicates"):
            validate_control_catalog(value)

    def test_catalog_invariant_rejects_unregistered_condition_primitive_addition(self) -> None:
        value = _catalog_value()
        restrained_disadvantage = deepcopy(_condition(value, "restrained")["primitives"][3])  # type: ignore[index]
        stunned = _condition(value, "stunned")
        stunned["primitives"].append(restrained_disadvantage)  # type: ignore[union-attr]
        with self.assertRaisesRegex(CatalogError, "condition stunned semantics .* signature exactly"):
            validate_control_catalog(value)

    def test_catalog_invariant_provenance_pins_public_records_and_exact_file_digest(self) -> None:
        provenance = json.loads(DEFAULT_CONTROL_PROVENANCE.read_text(encoding="utf-8"))
        self.assertEqual(provenance["format_version"], 2)
        self.assertEqual(
            provenance["source"],
            {
                "repository": "kmart01123/kinetic-vanguard",
                "issue_53_record_ids": [
                    5247061714,
                    5247097441,
                    5247104955,
                    5247113901,
                    5247133887,
                    5247179060,
                    5247181650,
                    5247254885,
                    5247439835,
                ],
                "issue_54_record_ids": [5247493229],
            },
        )
        self.assertNotIn("condition_pages", provenance)
        self.assertNotIn("extraction", provenance)
        self.assertEqual(provenance["data_sha256"], sha256_file(DEFAULT_CONTROL_CATALOG))

        with tempfile.TemporaryDirectory() as directory:
            reformatted = Path(directory) / "srd_control_consequences.json"
            reformatted.write_text(json.dumps(_catalog_value()), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "SHA-256 does not match provenance"):
                load_control_catalog(reformatted)

    def test_catalog_invariant_provenance_rejects_legacy_private_source_shape(self) -> None:
        provenance = json.loads(DEFAULT_CONTROL_PROVENANCE.read_text(encoding="utf-8"))
        provenance["source"] = {
            "ruleset": "private-source-placeholder",
            "official_pdf_url": "private-source-placeholder",
            "official_pdf_sha256": "0" * 64,
            "pages": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            provenance_path = Path(directory) / "provenance.json"
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            with self.assertRaisesRegex(CatalogError, "unknown=.*official_pdf"):
                load_control_catalog(provenance_path=provenance_path)

    def test_catalog_invariant_engine_config_has_named_unweighted_variants_and_no_default_function(self) -> None:
        config = load_engine_config()
        self.assertEqual(config.config_version, ENGINE_CONFIG_VERSION)
        self.assertEqual(config.primitive_contract_version, PRIMITIVE_CONTRACT_VERSION)
        self.assertEqual(config.normalization_rules_version, NORMALIZATION_RULES_VERSION)
        self.assertEqual(config.timeline_engine_version, TIMELINE_ENGINE_VERSION)
        self.assertEqual(ENGINE_CONFIG_VERSION, "2.0.0")
        self.assertEqual(NORMALIZATION_RULES_VERSION, "2.0.0")
        self.assertEqual(TIMELINE_ENGINE_VERSION, "2.0.0")
        self.assertEqual(config.horizon_rounds, 3)
        self.assertEqual(
            list(config.initiative_schedules),
            ["fighter_first_v1", "target_before_fighter_v1"],
        )
        self.assertEqual(
            list(config.area_response_conventions),
            ["shortest_route_v1", "fixed_occupancy_v1"],
        )
        self.assertEqual(config.area_response_conventions["shortest_route_v1"].version, "2.0.0")
        self.assertEqual(
            config.area_response_conventions["shortest_route_v1"].policy,
            "post_explicit_prone_operation_minimizes_future_primitive_exposure",
        )
        self.assertEqual(config.area_response_conventions["fixed_occupancy_v1"].version, "1.0.0")
        self.assertTrue(all(item.version == "1.0.0" for item in config.initiative_schedules.values()))
        self.assertTrue(all(item.version == "1.0.0" for item in config.displacement_functions.values()))
        self.assertEqual(
            list(config.displacement_functions),
            ["sqrt_5ft_v1", "log2_5ft_v1", "banded_10ft_v1"],
        )
        self.assertAlmostEqual(config.displacement_functions["sqrt_5ft_v1"].evaluate(10), math.sqrt(2))
        self.assertAlmostEqual(config.displacement_functions["log2_5ft_v1"].evaluate(10), math.log2(3))
        self.assertEqual(config.displacement_functions["banded_10ft_v1"].evaluate(10), 1)
        serialized = DEFAULT_ENGINE_CONFIG.read_text(encoding="utf-8").lower()
        self.assertNotIn("weight", serialized)
        self.assertNotIn("default_displacement", serialized)

    def test_catalog_invariant_engine_config_rejects_unknown_defaults_and_formula_drift(self) -> None:
        value = json.loads(DEFAULT_ENGINE_CONFIG.read_text(encoding="utf-8"))
        value["default_displacement_function"] = "sqrt_5ft_v1"
        with self.assertRaisesRegex(CatalogError, "unknown=.*default_displacement_function"):
            validate_engine_config(value)

        value = json.loads(DEFAULT_ENGINE_CONFIG.read_text(encoding="utf-8"))
        value["displacement_functions"][0]["formula"] = "distance_feet"
        with self.assertRaisesRegex(CatalogError, "versioned named registry"):
            validate_engine_config(value)


if __name__ == "__main__":
    unittest.main()
