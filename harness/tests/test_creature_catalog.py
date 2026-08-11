from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from harness.creature_catalog import (
    CATALOG_CONTRACT_ID,
    CATALOG_CONTRACT_VERSION,
    DEFAULT_CATALOG,
    DEFAULT_PROVENANCE,
    DEFAULT_ROSTERS,
    OFFICIAL_SOURCE_SHA256,
    PASSIVE_TRAIT_REGISTRY_ID,
    PASSIVE_TRAIT_REGISTRY_VERSION,
    CreatureCatalogError,
    canonical_sha256,
    file_sha256,
    load_catalog,
)


class CreatureCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()
        cls.raw = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))

    def assert_catalog_mutation_rejected(self, mutate: object, pattern: str) -> None:
        catalog_data = deepcopy(self.raw)
        mutate(catalog_data)
        provenance = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "srd_creatures.json"
            provenance_path = Path(directory) / "srd-creatures.json"
            catalog_path.write_text(
                json.dumps(catalog_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            provenance["catalog"]["sha256"] = file_sha256(catalog_path)
            provenance_path.write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CreatureCatalogError, pattern):
                load_catalog(catalog_path, provenance_path, DEFAULT_ROSTERS)

    def test_contract_source_count_and_canonical_id_inventory(self) -> None:
        self.assertEqual(self.catalog.contract_id, CATALOG_CONTRACT_ID)
        self.assertEqual(self.catalog.contract_version, CATALOG_CONTRACT_VERSION)
        self.assertEqual(len(self.catalog.records), 330)
        ids = [row["creature_id"] for row in self.catalog.records]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        source_ids = {
            (row["source"]["page"], row["source"]["stat_block_order"])
            for row in self.catalog.records
        }
        self.assertEqual(len(source_ids), 330)

    def test_raw_serialization_and_canonical_digest_are_deterministic(self) -> None:
        expected = json.dumps(self.raw, ensure_ascii=False, indent=2) + "\n"
        self.assertEqual(DEFAULT_CATALOG.read_text(encoding="utf-8"), expected)
        reordered = {key: self.raw[key] for key in reversed(self.raw)}
        self.assertEqual(canonical_sha256(self.raw), canonical_sha256(reordered))
        self.assertEqual(self.catalog.sha256, file_sha256(DEFAULT_CATALOG))

    def test_provenance_pins_official_source_and_generated_digests(self) -> None:
        provenance = self.catalog.provenance
        self.assertEqual(provenance["source"]["official_pdf_sha256"], OFFICIAL_SOURCE_SHA256)
        self.assertEqual(provenance["source"]["page_count"], 364)
        self.assertEqual(provenance["catalog"]["sha256"], file_sha256(DEFAULT_CATALOG))
        self.assertEqual(provenance["rosters"]["sha256"], file_sha256(DEFAULT_ROSTERS))
        self.assertEqual(provenance["accounting"]["total_stat_blocks"], 330)

    def test_exact_cr_xp_pb_and_source_exceptions_remain_distinct(self) -> None:
        pseudodragon = self.catalog.creature("srd521:pseudodragon")
        self.assertEqual(
            Fraction(**{
                "numerator": pseudodragon["challenge"]["rating"]["numerator"],
                "denominator": pseudodragon["challenge"]["rating"]["denominator"],
            }),
            Fraction(1, 4),
        )
        self.assertEqual(pseudodragon["challenge"]["canonical"], "1/4")
        self.assertEqual(pseudodragon["challenge"]["xp"], 50)
        self.assertEqual(pseudodragon["challenge"]["proficiency_bonus"], 2)
        archmage = self.catalog.creature("srd521:archmage")
        self.assertEqual(archmage["challenge"]["xp"], 8000)
        self.assertEqual(
            archmage["challenge"]["source_anomaly_id"],
            "source_printed_xp_8000_for_cr12",
        )
        self.assertEqual(self.catalog.creature("srd521:seahorse")["challenge"]["xp"], 0)

    def test_ability_modifiers_final_saves_and_initiative_are_separate_facts(self) -> None:
        aboleth = self.catalog.creature("srd521:aboleth")
        self.assertEqual(aboleth["abilities"]["intelligence"]["modifier"], 4)
        self.assertEqual(aboleth["abilities"]["intelligence"]["save_bonus"], 8)
        self.assertEqual(
            aboleth["abilities"]["intelligence"]["save_basis"],
            "explicit_stat_block_save_column",
        )
        gray_ooze = self.catalog.creature("srd521:gray-ooze")
        self.assertEqual(
            gray_ooze["initiative"],
            {"modifier": -2, "score": 13, "advantage": True, "qualifier": None},
        )

    def test_ac_hp_movement_senses_communication_defenses_and_gear_sentinels(self) -> None:
        werebear = self.catalog.creature("srd521:werebear")
        self.assertEqual(werebear["armor_class"]["resolution"], "resolved")
        self.assertIsInstance(werebear["hit_points"]["average"], int)
        self.assertIsInstance(werebear["hit_points"]["hit_dice"], str)
        self.assertEqual(werebear["movement"]["modes"]["climb"][0]["qualifier"], "bear form only")
        swarm = self.catalog.creature("srd521:swarm-of-insects")
        self.assertEqual(swarm["movement"]["choice_groups"][0]["modes"], ["climb", "fly"])
        storm_giant = self.catalog.creature("srd521:storm-giant")
        self.assertTrue(storm_giant["movement"]["hover"])
        self.assertTrue(storm_giant["senses"]["darkvision"])
        self.assertTrue(storm_giant["senses"]["truesight"])
        self.assertFalse(storm_giant["senses"]["blindsight"])
        self.assertFalse(storm_giant["senses"]["tremorsense"])
        barbed = self.catalog.creature("srd521:barbed-devil")
        self.assertEqual(
            barbed["senses"]["darkvision"][0]["limitation"],
            "unimpeded by magical Darkness",
        )
        otyugh = self.catalog.creature("srd521:otyugh")
        self.assertEqual(otyugh["communication"]["telepathy"]["range_feet"], 120)
        self.assertEqual(
            otyugh["communication"]["telepathy"]["limitation_id"],
            "recipient_cannot_reply",
        )
        rakshasa = self.catalog.creature("srd521:rakshasa")
        self.assertEqual(
            rakshasa["defenses"]["damage_vulnerabilities"][0]["qualifier_id"],
            "blessed_weapon_wielder",
        )
        self.assertTrue(self.catalog.creature("srd521:archmage")["gear"])

    def test_passive_trait_registry_is_closed_and_every_occurrence_dispositioned(self) -> None:
        registry = self.raw["passive_trait_registry"]
        self.assertEqual(registry["id"], PASSIVE_TRAIT_REGISTRY_ID)
        self.assertEqual(registry["version"], PASSIVE_TRAIT_REGISTRY_VERSION)
        definitions = {item["trait_id"]: item for item in registry["definitions"]}
        occurrences = 0
        for creature in self.catalog.records:
            for trait in creature["passive_traits"]:
                occurrences += 1
                definition = definitions[trait["trait_id"]]
                self.assertEqual(trait["disposition"], definition["disposition"])
                self.assertEqual(trait["reason_id"], definition["reason_id"])
        self.assertEqual(occurrences, registry["source_occurrence_count"])

    def test_duplicate_id_source_identity_missing_page_and_ability_rewrite_fail_closed(self) -> None:
        def duplicate_id(value: dict) -> None:
            value["creatures"][1]["creature_id"] = value["creatures"][0]["creature_id"]
            value["creatures"][1]["display_name"] = value["creatures"][0]["display_name"]

        self.assert_catalog_mutation_rejected(duplicate_id, "duplicate creature IDs")

        def duplicate_source(value: dict) -> None:
            value["creatures"][1]["source"] = deepcopy(value["creatures"][0]["source"])

        self.assert_catalog_mutation_rejected(duplicate_source, "duplicate source identities")
        self.assert_catalog_mutation_rejected(
            lambda value: value["creatures"][0]["source"].__setitem__("page", None),
            "source.page must be an integer",
        )
        self.assert_catalog_mutation_rejected(
            lambda value: value["creatures"][0]["abilities"]["strength"].__setitem__("modifier", 99),
            "modifier is inconsistent",
        )

    def test_unknown_trait_live_gear_state_and_rewritten_source_digest_fail_closed(self) -> None:
        self.assert_catalog_mutation_rejected(
            lambda value: value["creatures"][0]["passive_traits"][0].__setitem__("trait_id", "unknown_material_trait"),
            "unknown potentially material trait",
        )
        gear_index = next(
            index for index, creature in enumerate(self.raw["creatures"]) if creature["gear"]
        )
        self.assert_catalog_mutation_rejected(
            lambda value: value["creatures"][gear_index]["gear"][0].__setitem__("held", True),
            "keys are invalid",
        )
        provenance = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
        provenance["source"]["official_pdf_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "srd-creatures.json"
            path.write_text(json.dumps(provenance), encoding="utf-8")
            with self.assertRaisesRegex(CreatureCatalogError, "source digest or identity mismatch"):
                load_catalog(DEFAULT_CATALOG, path, DEFAULT_ROSTERS)


if __name__ == "__main__":
    unittest.main()
