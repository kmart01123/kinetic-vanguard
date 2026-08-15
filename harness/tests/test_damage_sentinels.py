"""Validation for the independent Issue #65 frozen damage sentinel corpus."""

from __future__ import annotations

import ast
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import json
from pathlib import Path
import unittest

from harness.tests.damage_sentinel_oracles import (
    CORPUS_PATH,
    EXPECTED_CASE_IDS,
    ORACLES,
    canonical_corpus_sha256,
    cases_by_id,
    evaluate_case,
    fraction,
    load_corpus,
)


EXPECTED_CORPUS_SHA256 = "9b355c99574e346fa0a7ee64146b78a0b1d912c524e0aea272759a0d707f7fd0"
MODEL_CONTRACT_PATH = CORPUS_PATH.parents[1] / "provenance" / "damage-model-contract.json"
BENCHMARK_CONFIG_PATH = CORPUS_PATH.parents[1] / "config" / "benchmark.json"
DAMAGE_CONTRACT_PATH = CORPUS_PATH.parents[1] / "damage_contract.py"
PR2_ONLY_CASE_IDS = frozenset({"S27", "S28", "S29", "S38", "S39", "S40", "S44", "S50"})
MIXED_CASE_IDS = frozenset({"S30", "S42", "S46"})
REQUIRED_CASE_FIELDS = frozenset(
    {
        "id",
        "title",
        "oracle",
        "production_behavior_ids",
        "integration_facets",
        "inputs",
        "starting_state",
        "legal_choices",
        "hidden_fields",
        "event_order",
        "formula",
        "numeric_oracles",
        "contract_expectations",
        "selected_policy",
        "post_state",
        "prohibited_alternatives",
    }
)
ALLOWED_ORACLE_IMPORTS = frozenset(
    {"__future__", "dataclasses", "fractions", "hashlib", "json", "pathlib", "typing"}
)


def _assert_decimal_matches(test: unittest.TestCase, exact: Fraction, rendered: str) -> None:
    decimal_places = len(rendered.partition(".")[2]) if "." in rendered else 0
    quantum = Decimal(1).scaleb(-decimal_places)
    with localcontext() as context:
        context.prec = 60
        calculated = (Decimal(exact.numerator) / Decimal(exact.denominator)).quantize(
            quantum,
            rounding=ROUND_HALF_EVEN,
        )
    test.assertEqual(calculated, Decimal(rendered))


class DamageSentinelCorpusIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_corpus()
        cls.cases = cases_by_id(cls.corpus)

    def test_corpus_identity_provenance_and_case_count_are_frozen(self) -> None:
        self.assertEqual(self.corpus["schema_version"], 1)
        self.assertEqual(
            self.corpus["contract_id"],
            "issue65_phase1_frozen_damage_sentinels_v1",
        )
        self.assertEqual(self.corpus["case_count"], 50)
        self.assertEqual(tuple(self.cases), EXPECTED_CASE_IDS)
        self.assertEqual(
            self.corpus["source_records"],
            {
                "original_assessment_comment_id": "5299910436",
                "independent_review_comment_id": "5299998789",
                "addendum_comment_id": "5300138781",
                "addendum_review_comment_id": "5300161056",
                "addendum_url": "https://github.com/kmart01123/kinetic-vanguard/issues/65#issuecomment-5300138781",
                "addendum_review_url": "https://github.com/kmart01123/kinetic-vanguard/issues/65#issuecomment-5300161056",
                "addendum_title": "Phase 1 addendum — corrected and frozen damage-model contract",
            },
        )
        model_contract = json.loads(MODEL_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            model_contract["sentinel_corpus"],
            {
                "contract_version": 1,
                "case_count": 50,
                "first_case_id": "S01",
                "last_case_id": "S50",
                "identity_path": "harness/data/damage-sentinels-v1.json",
                "canonical_sha256": EXPECTED_CORPUS_SHA256,
                "canonicalization": "UTF-8 JSON with object keys sorted, ensure_ascii=false, compact separators, and array order preserved.",
                "independent_oracle_path": "harness/tests/damage_sentinel_oracles.py",
                "test_path": "harness/tests/test_damage_sentinels.py",
                "finite_cases_are_contract_only_in_pr1": True,
            },
        )
    def test_every_case_has_the_complete_phase_one_schema(self) -> None:
        for sentinel_id, case in self.cases.items():
            with self.subTest(sentinel_id=sentinel_id):
                self.assertEqual(set(case), REQUIRED_CASE_FIELDS)
                self.assertEqual(case["id"], sentinel_id)
                self.assertTrue(case["title"])
                self.assertTrue(case["production_behavior_ids"])
                self.assertTrue(case["integration_facets"])
                self.assertIsInstance(case["inputs"], dict)
                self.assertTrue(case["inputs"])
                self.assertIsInstance(case["starting_state"], dict)
                self.assertTrue(case["starting_state"])
                self.assertTrue(case["legal_choices"])
                self.assertTrue(case["hidden_fields"])
                self.assertTrue(case["event_order"])
                self.assertTrue(case["formula"])
                self.assertIsInstance(case["numeric_oracles"], list)
                self.assertIsInstance(case["contract_expectations"], dict)
                self.assertTrue(case["contract_expectations"])
                self.assertTrue(case["selected_policy"])
                self.assertIsInstance(case["post_state"], dict)
                self.assertTrue(case["post_state"])
                self.assertTrue(case["prohibited_alternatives"])
                self.assertEqual(case["oracle"], sentinel_id.lower())

    def test_pr1_static_knowledge_actions_objective_and_result_identity_are_closed(self) -> None:
        contract = json.loads(MODEL_CONTRACT_PATH.read_text(encoding="utf-8"))
        knowledge = contract["nominal_target_knowledge"]
        self.assertEqual(knowledge["contract_id"], "declared_static_target_knowledge_v1")
        self.assertEqual(knowledge["provider_surface"], "identical_for_all_providers")
        self.assertEqual(
            knowledge["visible_static_fields"],
            [
                "armor_class",
                "saving_throw_bonuses",
                "magic_resistance",
                "legendary_resistance_metadata_policy",
                "damage_resistances",
                "damage_immunities",
                "damage_vulnerabilities",
                "size_when_legally_relevant",
                "creature_type_when_legally_relevant",
            ],
        )
        self.assertEqual(
            knowledge["deferred_finite_visible_fields"],
            ["current_hit_points", "alive_or_dead_state"],
        )
        self.assertEqual(
            knowledge["hidden_future_fields"],
            [
                "future_attack_rolls",
                "future_save_rolls",
                "future_damage_rolls",
                "future_deaths",
                "unselected_future_policy_branches",
            ],
        )
        self.assertEqual(
            knowledge["active_observation_stages"],
            [
                "before_choosing_action",
                "before_declaring_attack",
                "before_declaring_rider",
                "after_natural_attack_roll_observed",
                "after_provisional_miss",
                "after_miss_correction_resolved",
                "after_final_hit_or_critical_identity",
                "before_legal_follow_up_decision",
            ],
        )
        self.assertEqual(
            knowledge["deferred_finite_observation_stages"],
            [
                "after_damage_roll_observed",
                "after_target_death_known",
                "before_retargeting_decision",
            ],
        )

        vocabulary = contract["closed_action_vocabulary"]
        self.assertFalse(vocabulary["additional_action_kinds_allowed"])
        self.assertEqual(
            vocabulary["active_pr1_actions"],
            [
                "attack_action",
                "ordinary_attack",
                "manifested_strike",
                "rider_declaration",
                "standalone_feature",
                "battle_master_on_hit_die",
                "battle_master_miss_correction",
                "relentless",
                "combat_prowess",
                "true_strike_replacement",
                "kinetic_mastery",
                "hew_bonus_attack",
                "attack_resolution",
                "end_action",
                "end_turn",
                "end_round",
                "end_horizon",
                "canonical_tie_probe",
            ],
        )
        self.assertEqual(vocabulary["deferred_finite_only_actions"], ["retargeting"])
        self.assertEqual(
            vocabulary["deferred_finite_only_transitions"],
            ["target_death", "hew_bonus_attack_from_reduce_to_zero_trigger"],
        )
        damage_contract_tree = ast.parse(
            DAMAGE_CONTRACT_PATH.read_text(encoding="utf-8"),
            filename=str(DAMAGE_CONTRACT_PATH),
        )
        action_kind_class = next(
            node
            for node in damage_contract_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ActionKind"
        )
        executable_action_kinds = [
            node.value.value
            for node in action_kind_class.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ]
        self.assertEqual(vocabulary["active_pr1_actions"], executable_action_kinds)

        objective = contract["nominal_objective_and_resources"]
        self.assertEqual(objective["objective_policy_id"], "nominal_sustained_dpr_v1")
        self.assertEqual(
            objective["lexicographic_order"],
            [
                "aggregate_damage",
                "primary_damage",
                "least_self_damage",
                "least_horizon_limited_use",
                "least_persistent_pool_use",
                "least_refreshable_use",
                "smallest_canonical_action_id",
            ],
        )
        self.assertEqual(
            objective["objective_semantics"],
            {
                "aggregate_damage": "maximum_exact_aggregate_three_round_damage",
                "primary_damage": "maximum_exact_fixed_primary_three_round_damage",
            },
        )
        self.assertTrue(objective["resource_efficiency_never_outranks_damage"])
        self.assertEqual(
            objective["resource_class_order"],
            ["self_damage", "horizon_limited", "persistent_pool", "refreshable"],
        )
        self.assertEqual(
            objective["resource_class_mapping"],
            {
                "kinetic_vanguard": {
                    "self_damage": ["blood_tax"],
                    "horizon_limited": ["overload_mastery"],
                    "persistent_pool": ["psi"],
                    "refreshable": ["combat_prowess"],
                },
                "battle_master": {
                    "self_damage": [],
                    "horizon_limited": [],
                    "persistent_pool": ["superiority_die"],
                    "refreshable": ["relentless", "combat_prowess", "hew", "bonus_action"],
                },
                "eldritch_knight": {
                    "self_damage": [],
                    "horizon_limited": [],
                    "persistent_pool": [],
                    "refreshable": ["true_strike_replacement", "combat_prowess"],
                },
            },
        )
        optimization = json.loads(BENCHMARK_CONFIG_PATH.read_text(encoding="utf-8"))[
            "damage_matrix"
        ]["optimization"]
        self.assertEqual(objective["lexicographic_order"], optimization["objective"])
        self.assertEqual(
            {
                "order": objective["resource_class_order"],
                **objective["resource_class_mapping"],
            },
            optimization["resource_cost_classes"],
        )

        result = contract["result_and_provenance"]
        self.assertEqual(result["run_manifest_format_version"], 2)
        self.assertEqual(result["damage_result_contract_version"], "3.0.0")
        self.assertEqual(
            result["required_input_identity_fields"],
            [
                "damage_result_contract_version",
                "damage_model_mode_id",
                "target_knowledge_contract_id",
                "numeric_representation_id",
                "provider_ids",
                "rules_version",
                "authority_sha256",
                "authority_projection_sha256",
                "catalog_contract_version",
                "catalog_sha256",
                "roster_contract_version",
                "roster_sha256",
                "target_profile_id",
                "target_profile_version",
                "target_profile_sha256",
                "damage_target_projection_id",
                "damage_target_projection_version",
                "damage_target_projection_sha256",
                "consumer_requirements_version",
                "damage_consumer_requirements_sha256",
                "config_sha256",
                "comparator_config_sha256",
                "damage_model_contract_sha256",
                "sentinel_corpus_sha256",
                "sentinel_corpus_file_sha256",
                "observation_policy_sha256",
                "resource_policy_sha256",
                "optimization_policy_sha256",
                "evaluator",
                "evaluator_implementation_sha256",
                "semantic_implementation_sha256",
                "orchestration_implementation_sha256",
                "reporter_implementation_sha256",
                "trials",
                "seed",
                "trial_seed_role",
                "aggregation",
                "status",
            ],
        )
        self.assertEqual(
            result["required_output_identity_fields"],
            ["detail_csv", "matrix_csv", "matrix_markdown", "matrix_html"],
        )
        self.assertEqual(result["required_row_count_fields"], ["detail", "matrix"])
        self.assertFalse(result["fresh_pr1_matrix_evidence_claimed"])

    def test_numeric_oracles_have_unique_names_exact_fractions_and_decimals(self) -> None:
        for sentinel_id, case in self.cases.items():
            names: list[str] = []
            for oracle in case["numeric_oracles"]:
                with self.subTest(sentinel_id=sentinel_id, oracle=oracle):
                    self.assertEqual(set(oracle), {"name", "fraction", "decimal"})
                    names.append(oracle["name"])
                    exact = fraction(oracle["fraction"])
                    _assert_decimal_matches(self, exact, oracle["decimal"])
            self.assertEqual(len(names), len(set(names)), sentinel_id)

    def test_pr1_and_deferred_finite_facets_are_explicit_and_have_no_skips(self) -> None:
        expected = set(EXPECTED_CASE_IDS)
        pr1_only = expected - set(PR2_ONLY_CASE_IDS) - set(MIXED_CASE_IDS)
        seen_pr1_only: set[str] = set()
        seen_pr2_only: set[str] = set()
        seen_mixed: set[str] = set()
        for sentinel_id, case in self.cases.items():
            facets = case["integration_facets"]
            phases = {facet["phase"] for facet in facets}
            expectations = {facet["expectation"] for facet in facets}
            self.assertTrue(
                expectations <= {"match_exact", "fail_closed_until_pr2"},
                sentinel_id,
            )
            self.assertNotIn("skip", expectations, sentinel_id)
            for facet in facets:
                self.assertEqual(
                    set(facet),
                    {"mode", "phase", "expectation"},
                    sentinel_id,
                )
                if facet["phase"] == "pr1":
                    self.assertEqual(facet["expectation"], "match_exact")
                elif facet["phase"] == "pr2":
                    self.assertEqual(facet["expectation"], "fail_closed_until_pr2")
                else:
                    self.fail(f"{sentinel_id} has unsupported phase {facet['phase']!r}")
            if sentinel_id in PR2_ONLY_CASE_IDS:
                self.assertEqual(phases, {"pr2"})
                seen_pr2_only.add(sentinel_id)
            elif sentinel_id in MIXED_CASE_IDS:
                self.assertEqual(phases, {"pr1", "pr2"})
                seen_mixed.add(sentinel_id)
            else:
                self.assertEqual(phases, {"pr1"})
                seen_pr1_only.add(sentinel_id)
        self.assertEqual(seen_pr1_only, pr1_only)
        self.assertEqual(seen_pr2_only, set(PR2_ONLY_CASE_IDS))
        self.assertEqual(seen_mixed, set(MIXED_CASE_IDS))

    def test_all_fifty_oracles_are_registered_and_no_test_is_skipped(self) -> None:
        self.assertEqual(set(ORACLES), {sentinel_id.lower() for sentinel_id in EXPECTED_CASE_IDS})
        generated = {
            name
            for name in vars(DamageSentinelExactOracleTests)
            if name.startswith("test_s")
        }
        self.assertEqual(generated, {f"test_{sentinel_id.lower()}" for sentinel_id in EXPECTED_CASE_IDS})
        for name in generated:
            method = getattr(DamageSentinelExactOracleTests, name)
            self.assertFalse(getattr(method, "__unittest_skip__", False), name)

    def test_oracle_module_has_only_standard_library_imports_and_no_matrix_reachability(self) -> None:
        oracle_path = Path(__file__).with_name("damage_sentinel_oracles.py")
        tree = ast.parse(oracle_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertIsNotNone(node.module)
                imports.add(str(node.module).split(".", 1)[0])
        self.assertEqual(imports, ALLOWED_ORACLE_IMPORTS)
        forbidden_modules = {
            "harness.damage_contract",
            "harness.damage_harness",
            "harness.damage_report",
            "harness.model",
            "harness.authority",
            "harness.creature_catalog",
            "harness.creature_damage_projection",
            "concurrent.futures",
            "multiprocessing",
        }
        imported_full_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_full_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_full_names.add(node.module)
        self.assertTrue(forbidden_modules.isdisjoint(imported_full_names))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(
            {"run", "run_damage", "write_damage_matrix", "load_profile"}.isdisjoint(called_names)
        )

    def test_corpus_canonical_sha256_is_frozen(self) -> None:
        self.assertEqual(canonical_corpus_sha256(self.corpus), EXPECTED_CORPUS_SHA256)


class DamageSentinelExactOracleTests(unittest.TestCase):
    cases = cases_by_id()

    def assert_sentinel(self, sentinel_id: str) -> None:
        case = self.cases[sentinel_id]
        result = evaluate_case(case)
        expected_numbers = {
            oracle["name"]: fraction(oracle["fraction"])
            for oracle in case["numeric_oracles"]
        }
        self.assertEqual(result.number_map(), expected_numbers)
        self.assertEqual(result.facts, case["contract_expectations"])


def _make_sentinel_test(sentinel_id: str):
    def test(self: DamageSentinelExactOracleTests) -> None:
        self.assert_sentinel(sentinel_id)

    test.__name__ = f"test_{sentinel_id.lower()}"
    test.__qualname__ = f"DamageSentinelExactOracleTests.test_{sentinel_id.lower()}"
    test.__doc__ = f"Independently derive and validate frozen sentinel {sentinel_id}."
    return test


for _sentinel_id in EXPECTED_CASE_IDS:
    setattr(
        DamageSentinelExactOracleTests,
        f"test_{_sentinel_id.lower()}",
        _make_sentinel_test(_sentinel_id),
    )

del _sentinel_id


if __name__ == "__main__":
    unittest.main()
