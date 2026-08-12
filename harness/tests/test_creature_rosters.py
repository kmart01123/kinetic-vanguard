from __future__ import annotations

import json
import math
import tempfile
import unittest
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from harness.creature_catalog import (
    BENCHMARK_LEVELS,
    CENSUS_PROFILE_ID,
    DEFAULT_CATALOG,
    DEFAULT_PROVENANCE,
    DEFAULT_ROSTERS,
    ELIGIBILITY_POLICY_ID,
    HEADLINE_PROFILE_ID,
    PROFILE_VERSION,
    SELECTION_ALGORITHM_ID,
    CreatureCatalogError,
    canonical_sha256,
    file_sha256,
    load_catalog,
    load_profile,
)


class CreatureRosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()
        cls.raw = json.loads(DEFAULT_ROSTERS.read_text(encoding="utf-8"))
        cls.headline = load_profile(catalog=cls.catalog)
        cls.census = load_profile(CENSUS_PROFILE_ID, catalog=cls.catalog)

    def assert_roster_mutation_rejected(self, mutate: object, pattern: str) -> None:
        roster = deepcopy(self.raw)
        mutate(roster)
        provenance = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            roster_path = Path(directory) / "srd_creature_rosters.json"
            provenance_path = Path(directory) / "srd-creatures.json"
            roster_path.write_text(
                json.dumps(roster, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            provenance["rosters"]["sha256"] = file_sha256(roster_path)
            provenance_path.write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            catalog = load_catalog(DEFAULT_CATALOG, provenance_path, roster_path)
            with self.assertRaisesRegex(CreatureCatalogError, pattern):
                load_profile(
                    catalog=catalog,
                    roster_path=roster_path,
                    provenance_path=provenance_path,
                )

    def test_approved_policy_algorithm_and_profile_contracts_are_exact(self) -> None:
        self.assertEqual(self.raw["eligibility_policy"]["id"], ELIGIBILITY_POLICY_ID)
        self.assertEqual(self.raw["selection_algorithm"]["id"], SELECTION_ALGORITHM_ID)
        self.assertIs(self.raw["selection_algorithm"]["result_blind"], True)
        self.assertEqual(
            self.raw["selection_algorithm"]["tie_break"],
            ["source_page_ascending", "source_order_ascending", "creature_id_ascending"],
        )
        self.assertEqual(self.raw["eligibility_policy"]["intentional_gaps"], [
            {"numerator": 9, "denominator": 1},
            {"numerator": 17, "denominator": 1},
            {"numerator": 18, "denominator": 1},
        ])
        self.assertTrue(all(entry.profile_version == PROFILE_VERSION for entry in self.headline))

    def test_complete_source_accounting_has_one_closed_disposition_per_creature(self) -> None:
        accounting = self.raw["accounting"]
        self.assertEqual(len(accounting), len(self.catalog.records))
        self.assertEqual(
            {item["creature_id"] for item in accounting},
            {item["creature_id"] for item in self.catalog.records},
        )
        self.assertEqual(
            Counter(item["disposition"] for item in accounting),
            {
                "ineligible_under_level_cr_policy": 229,
                "headline_selected": 47,
                "eligible_census_only": 46,
                "excluded_unsupported_material_mechanic": 8,
            },
        )
        self.assertTrue(
            all(
                (item["reason_id"] is not None)
                == (item["disposition"] == "excluded_unsupported_material_mechanic")
                for item in accounting
            )
        )

    def test_headline_and_census_counts_weights_and_memberships_are_exact(self) -> None:
        headline_counts = Counter(entry.benchmark_level for entry in self.headline)
        census_counts = Counter(entry.benchmark_level for entry in self.census)
        self.assertEqual(headline_counts, {7: 12, 11: 12, 15: 11, 20: 12})
        self.assertEqual(census_counts, {7: 47, 11: 20, 15: 11, 20: 15})
        for entries in (self.headline, self.census):
            by_level: dict[int, list] = defaultdict(list)
            for entry in entries:
                by_level[entry.benchmark_level].append(entry)
            for level in BENCHMARK_LEVELS:
                self.assertEqual(sum((entry.weight for entry in by_level[level]), Fraction()), 1)
                self.assertEqual(
                    {entry.weight for entry in by_level[level]},
                    {Fraction(1, len(by_level[level]))},
                )
        feasible = {
            item["creature_id"]
            for item in self.raw["accounting"]
            if item["projection_feasible"]
        }
        self.assertEqual({entry.creature_id for entry in self.census}, feasible)
        self.assertTrue({entry.creature_id for entry in self.headline}.issubset(feasible))

    def test_profile_identity_digests_bind_exact_entries(self) -> None:
        profiles = {profile["profile_id"]: profile for profile in self.raw["profiles"]}
        for profile_id in (HEADLINE_PROFILE_ID, CENSUS_PROFILE_ID):
            profile = profiles[profile_id]
            identity = {
                "profile_id": profile["profile_id"],
                "profile_version": profile["profile_version"],
                "purpose": profile["purpose"],
                "entries": profile["entries"],
            }
            self.assertEqual(profile["profile_sha256"], canonical_sha256(identity))
        self.assertTrue(all(entry.catalog_sha256 == self.catalog.sha256 for entry in self.headline))
        self.assertTrue(all(entry.roster_sha256 == file_sha256(DEFAULT_ROSTERS) for entry in self.headline))

    def test_numeric_rank_bucket_maps_follow_approved_distinct_value_formula(self) -> None:
        for level, audit in self.raw["selection_audit"]["levels"].items():
            for dimension, rows in audit["numeric_bucket_maps"].items():
                values = [row["value"] for row in rows]
                self.assertEqual(values, sorted(set(values)), (level, dimension))
                if len(values) == 1:
                    self.assertEqual(rows[0]["bucket"], "only")
                    continue
                expected = [
                    f"q{1 + min(3, math.floor(4 * index / (len(values) - 1)))}"
                    for index in range(len(values))
                ]
                self.assertEqual([row["bucket"] for row in rows], expected, (level, dimension))

    def test_token_universes_preserve_approved_atomic_facts_and_exclusions(self) -> None:
        levels = self.raw["selection_audit"]["levels"]
        self.assertEqual(
            levels["7"]["token_universes"]["sense_tremorsense"],
            ["limitation:none", "none", "present", "range:120", "range:60"],
        )
        for audit in levels.values():
            restrictions = audit["token_universes"]["communication_restriction"]
            self.assertFalse(any(token == "all_languages" for token in restrictions))
            self.assertFalse(any(token.startswith("additional_languages:") for token in restrictions))
            for kind in ("darkvision", "blindsight", "tremorsense", "truesight"):
                tokens = audit["token_universes"][f"sense_{kind}"]
                self.assertTrue(tokens == ["none"] or "present" in tokens)
        self.assertNotIn(
            "residential_entry_requires_invitation",
            levels["11"]["token_universes"]["targeting_restriction"],
        )

    def test_greedy_trace_serialization_coverage_and_major_families_are_auditable(self) -> None:
        source_keys = {
            row["creature_id"]: (
                row["source"]["page"],
                row["source"]["stat_block_order"],
                row["creature_id"],
            )
            for row in self.catalog.records
        }
        headline_by_level: dict[int, list] = defaultdict(list)
        for entry in self.headline:
            headline_by_level[entry.benchmark_level].append(entry)
        for level, audit in self.raw["selection_audit"]["levels"].items():
            level_number = int(level)
            trace_ids = [item["creature_id"] for item in audit["greedy_pick_trace"]]
            serialized_ids = [entry.creature_id for entry in headline_by_level[level_number]]
            self.assertEqual(set(trace_ids), set(serialized_ids))
            self.assertEqual(serialized_ids, sorted(serialized_ids, key=source_keys.__getitem__))
            dimensions = audit["token_universes"]
            self.assertEqual(
                Fraction(**audit["coverage"]["available_weight"]),
                len(dimensions),
            )
            self.assertTrue(
                all(item["represented_when_present"] for item in audit["major_family_audit"].values())
            )

    def test_level_filter_and_missing_profile_fail_closed(self) -> None:
        selected = load_profile(levels={15}, catalog=self.catalog)
        self.assertEqual(len(selected), 11)
        self.assertEqual({entry.benchmark_level for entry in selected}, {15})
        with self.assertRaisesRegex(CreatureCatalogError, "does not exist"):
            load_profile("missing_profile", catalog=self.catalog)
        with self.assertRaisesRegex(CreatureCatalogError, "Unsupported benchmark levels"):
            load_profile(levels={9}, catalog=self.catalog)

    def test_membership_weight_accounting_and_result_blind_mutations_fail_closed(self) -> None:
        self.assert_roster_mutation_rejected(
            lambda value: value["profiles"][0]["entries"][0]["weight"].__setitem__("denominator", 11),
            "deterministic source-only recomputation",
        )
        self.assert_roster_mutation_rejected(
            lambda value: value["accounting"].pop(),
            "deterministic source-only recomputation",
        )
        self.assert_roster_mutation_rejected(
            lambda value: value["selection_algorithm"].__setitem__("result_blind", False),
            "deterministic source-only recomputation",
        )


if __name__ == "__main__":
    unittest.main()
