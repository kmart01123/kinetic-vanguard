from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

from harness.model import ABILITIES,DEFAULT_CATALOG,DEFAULT_PROFILE,DEFAULT_ROSTERS,MOVEMENT_MODES,PROFILE_COUNTS,PROFILE_LEVEL_COUNTS,SENSE_KINDS,file_sha256,load_catalog,load_profiles,load_targets


def _canonical(value:object)->bytes:
    def normalize(item:object)->object:
        if dataclasses.is_dataclass(item):return {field.name:normalize(getattr(item,field.name)) for field in dataclasses.fields(item)}
        if isinstance(item,(set,frozenset)):return sorted(item)
        if isinstance(item,dict):return {key:normalize(child) for key,child in item.items()}
        if isinstance(item,(list,tuple)):return [normalize(child) for child in item]
        return item
    return json.dumps(normalize(value),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()


class CreatureCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.catalog=load_catalog();cls.profiles=load_profiles(catalog=cls.catalog);cls.by_id={row["id"]:row for row in cls.catalog["creatures"]}

    def test_catalog_is_exact_srd_521_population_with_stable_metadata(self)->None:
        creatures=self.catalog["creatures"];self.assertEqual(len(creatures),330);self.assertEqual(len({row["id"] for row in creatures}),330)
        self.assertEqual(self.catalog["source"]["ruleset"],"SRD 5.2.1");self.assertEqual(self.catalog["source"]["pdf_sha256"],"8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87")
        for row in creatures:
            self.assertEqual(set(row["ability_modifiers"]),set(ABILITIES));self.assertLessEqual(set(row["saving_throw_bonuses"]),set(ABILITIES));self.assertEqual(set(row["movement"]["modes"]),set(MOVEMENT_MODES));self.assertEqual(set(row["senses"]),set(SENSE_KINDS));self.assertIsInstance(row["passive_perception"],int);self.assertTrue(row["source"]["anchor"])
            self.assertFalse({"current_hp","position","current_conditions","concentration","visibility","routes","target_selection"}&row.keys())

    def test_sparse_source_explicit_saves_and_skills_remain_distinct(self)->None:
        aboleth=self.by_id["srd521:aboleth"];air_elemental=self.by_id["srd521:air-elemental"]
        self.assertEqual(aboleth["ability_modifiers"]["dexterity"],-1);self.assertEqual(aboleth["saving_throw_bonuses"]["dexterity"],3)
        self.assertEqual(aboleth["skill_bonuses"],[{"skill":"history","bonus":12},{"skill":"perception","bonus":10}]);self.assertEqual(air_elemental["skill_bonuses"],[])

    def test_profile_membership_counts_order_and_historical_identities_are_frozen(self)->None:
        expected_hashes={"legacy_v14_1":"05c8eae6c9aae44f4d5d5eef1c53ac93b6d951c9a6d3eb58e2032bcfb47d8a77","headline":"6bc64ec7f22830c1dc4e9be66bdb1fdffa2ba7b262d52560561a5e3a27aff8bb","eligible_census":"ddd00d1a64e1f0721208af3dd6726393a9929850e60ed7556508b8b6b15240f0"}
        for profile,entries in self.profiles.items():
            self.assertEqual(len(entries),PROFILE_COUNTS[profile]);self.assertEqual(Counter(row["benchmark_level"] for row in entries),Counter(PROFILE_LEVEL_COUNTS[profile]));self.assertEqual(hashlib.sha256(_canonical(entries)).hexdigest(),expected_hashes[profile])
        headline={(row["creature_id"],row["benchmark_level"]) for row in self.profiles["headline"]};census={(row["creature_id"],row["benchmark_level"]) for row in self.profiles["eligible_census"]};self.assertLess(headline,census)

    def test_headline_profile_is_default_and_legacy_remains_exact_migration_oracle(self)->None:
        self.assertEqual(DEFAULT_PROFILE,"headline");targets=load_targets();self.assertEqual(len(targets),47)
        self.assertEqual(hashlib.sha256(_canonical(targets)).hexdigest(),"92f949e612b29ab7dfe3254e936246a4ff1aaa654ff8aa6296ea8e766b15b799")
        legacy_targets=load_targets(profile="legacy_v14_1");self.assertEqual(len(legacy_targets),28)
        self.assertEqual(hashlib.sha256(_canonical(legacy_targets)).hexdigest(),"0e44ca5e57e619dde34a6a1ebf7dc81f7d2a85681542c8c81069db933bbb8659")

    def test_shared_target_projection_covers_damage_and_control_consumers(self)->None:
        targets=load_targets(profile="headline");self.assertEqual(len(targets),47)
        for target in targets:
            self.assertGreater(target.ac,0);self.assertGreater(target.hp,0);self.assertEqual(set(target.saves),set(ABILITIES));self.assertIn(target.size,{"tiny","small","medium","large","huge","gargantuan"});self.assertTrue(target.creature_type)
            self.assertIsInstance(target.damage_resistances,frozenset);self.assertIsInstance(target.damage_immunities,frozenset);self.assertIsInstance(target.damage_vulnerabilities,frozenset);self.assertIsInstance(target.condition_immunities,frozenset)
        archmage=next(row for row in targets if row.name=="Archmage");self.assertIn("charmed",archmage.condition_immunities)

    def test_catalog_and_profiles_fail_closed_on_identity_and_membership_mutation(self)->None:
        catalog=deepcopy(self.catalog);catalog["creatures"][1]["id"]=catalog["creatures"][0]["id"]
        profiles=deepcopy(json.loads(DEFAULT_ROSTERS.read_text(encoding="utf-8")));profiles["profiles"]["headline"].append(deepcopy(profiles["profiles"]["headline"][0]))
        with tempfile.TemporaryDirectory() as directory:
            catalog_path=Path(directory)/"catalog.json";profile_path=Path(directory)/"profiles.json";catalog_path.write_text(json.dumps(catalog),encoding="utf-8");profile_path.write_text(json.dumps(profiles),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"unique stable"):load_catalog(catalog_path)
            with self.assertRaisesRegex(ValueError,"exactly 47"):load_profiles(profile_path,self.catalog)

    def test_catalog_byte_mutation_changes_evidence_identity(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            mutated=Path(directory)/"srd_creatures.json";mutated.write_bytes(DEFAULT_CATALOG.read_bytes()+b"\n")
            self.assertNotEqual(file_sha256(mutated),file_sha256(DEFAULT_CATALOG))


if __name__=="__main__":unittest.main()
