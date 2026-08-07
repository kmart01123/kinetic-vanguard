from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.authority import AuthorityError,AuthorityModel,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.comparison_report import classify_control,classify_damage,matrix_row,write_matrix
from harness.control_harness import run as run_control
from harness.damage_harness import run as run_damage
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,load_comparators,load_config


class AuthorityProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load()

    def test_real_root_authority_and_complete_stable_id_inventory(self)->None:
        self.assertEqual(Path(self.model.projection["authority_path"]),DEFAULT_AUTHORITY)
        self.assertEqual(self.model.rules_version,"14.1.0")
        self.assertEqual(self.model.projection["schema_version"],"2.1.0")
        feature_ids=list(self.model.features)
        self.assertEqual(len(feature_ids),len(set(feature_ids)))
        self.assertEqual(set(self.model.disciplines),{"pyrokinesis","cryokinesis","psychokinesis","electrokinesis"})
        self.assertTrue(all(feature["minimum_level"]>=3 and feature["psi_cost"]>=0 for feature in self.model.features.values()))
        self.assertTrue(all("entity_id" in feature for feature in self.model.features.values()))

    def test_structural_yaml_mutation_changes_projection_without_python_edit(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        probe="id: pyrokinesis\n        damage_type: fire"
        self.assertIn(probe,source)
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace(probe,"id: pyrokinesis\n        damage_type: cold",1),encoding="utf-8")
            mutated=AuthorityModel.load(authority)
        self.assertEqual(self.model.disciplines["pyrokinesis"]["damage_type"],"fire")
        self.assertEqual(mutated.disciplines["pyrokinesis"]["damage_type"],"cold")

    def test_missing_mechanics_and_unavailable_tier_fail_closed(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace("  harness_mechanics:\n","  missing_harness_mechanics:\n",1),encoding="utf-8")
            with self.assertRaises(AuthorityError):AuthorityModel.load(authority)
        with self.assertRaisesRegex(AuthorityError,"unavailable"):self.model.feature("flare",7,2)
        with self.assertRaisesRegex(AuthorityError,"Unsupported"):self.model.feature("glacial_spike",7,9)

    def test_progression_bands_cover_every_supported_level_once(self)->None:
        for name in ("proficiency_bonus","psi_points","psionic_focus","manifested_strike_die"):
            for level in range(3,21):self.assertIsInstance(self.model.progression(name,level),int)

    def test_comparator_inputs_are_isolated_minimal_and_fail_closed(self)->None:
        config=load_config();comparators=load_comparators()
        self.assertNotIn("damage_comparators",config);self.assertNotIn("control_comparators",config)
        self.assertEqual(comparators["source_ruleset"],"2024 fifth-edition rules")
        self.assertEqual(comparators["primary_comparator_ids"],["battle_master","eldritch_knight"])
        self.assertEqual(set(comparators["damage"]),{"battle_master","eldritch_knight"});self.assertEqual(set(comparators["control"]),{"battle_master","eldritch_knight"})
        source=DEFAULT_COMPARATORS.read_text(encoding="utf-8")
        for forbidden in ('"label"','"status"','"description"','"rules_text"','"feature_text"','"spell_text"','"maneuver_text"','"flavor"'):self.assertNotIn(forbidden,source)
        self.assertNotRegex(DEFAULT_AUTHORITY.read_text(encoding="utf-8"),r"(?i)battle.?master|eldritch.?knight")
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"comparators.json";mutated=dict(comparators);mutated["primary_comparator_ids"]=["eldritch_knight","battle_master"]
            path.write_text(json.dumps(mutated),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Primary comparators"):load_comparators(path)
        self.assertTrue(DEFAULT_CONFIG.is_file());self.assertTrue(DEFAULT_COMPARATORS.is_file())


class ClassificationTests(unittest.TestCase):
    def test_damage_boundaries_order_and_zero(self)->None:
        self.assertEqual(classify_damage(9,10,20),"COLD")
        self.assertEqual(classify_damage(10,10,20),"IDEAL")
        self.assertEqual(classify_damage(15,10,20),"IDEAL")
        self.assertEqual(classify_damage(20,10,20),"IDEAL")
        self.assertEqual(classify_damage(21,10,20),"HOT")
        self.assertEqual(classify_damage(15,20,10),"ORDER CHECK")
        self.assertEqual(classify_damage(15,0,20),"N/A")

    def test_control_boundaries_order_and_zero(self)->None:
        self.assertEqual(classify_control(9,20,10),"COLD")
        self.assertEqual(classify_control(10,20,10),"IDEAL")
        self.assertEqual(classify_control(15,20,10),"IDEAL")
        self.assertEqual(classify_control(20,20,10),"IDEAL")
        self.assertEqual(classify_control(21,20,10),"HOT")
        self.assertEqual(classify_control(15,10,20),"ORDER CHECK")
        self.assertEqual(classify_control(15,20,0),"N/A")

    def test_percentage_uses_displayed_aggregate_raw_values(self)->None:
        row=matrix_row({"Level":7},10.0,8.0,20.0,"damage")
        self.assertEqual(row["KV as % of EK"],"125.00")
        self.assertEqual(row["KV as % of BM"],"50.00")
        self.assertEqual(row["Band"],"IDEAL")
        self.assertEqual(row["Boundary Delta %"],"0.00")

    def test_boundary_delta_quantifies_hot_and_cold_tuning_distance(self)->None:
        cases=[
            ("damage",8,10,20,"COLD","-20.00"),
            ("damage",24,10,20,"HOT","+20.00"),
            ("damage",15,10,20,"IDEAL","0.00"),
            ("control",8,20,10,"COLD","-20.00"),
            ("control",24,20,10,"HOT","+20.00"),
            ("control",15,20,10,"IDEAL","0.00"),
            ("damage",15,20,10,"ORDER CHECK","N/A"),
            ("control",15,20,0,"N/A","N/A"),
        ]
        for kind,kv,ek,bm,band,delta in cases:
            with self.subTest(kind=kind,band=band):
                row=matrix_row({},kv,ek,bm,kind);self.assertEqual(row["Band"],band);self.assertEqual(row["Boundary Delta %"],delta)

    def test_csv_markdown_html_are_one_row_model_and_visible_band(self)->None:
        row=matrix_row({"Level":7,"Discipline":"cryokinesis"},10,8,20,"damage")
        provenance={"rules_version":"14.1.0","authority_sha256":"probe","roster_sha256":"probe"}
        with tempfile.TemporaryDirectory() as directory:
            paths=write_matrix(Path(directory),"14.1.0","damage",[row],provenance)
            with paths["csv"].open(encoding="utf-8") as stream:
                csv_row=next(csv.DictReader(stream))
            markdown=paths["markdown"].read_text(encoding="utf-8");html=paths["html"].read_text(encoding="utf-8")
        self.assertTrue(all(csv_row[key]==value for key,value in row.items()))
        self.assertEqual(csv_row["Provenance Rules Version"],"14.1.0")
        self.assertEqual(csv_row["Provenance Authority Sha256"],"probe")
        self.assertEqual(csv_row["Provenance Roster Sha256"],"probe")
        for value in row.values():
            self.assertIn(value,markdown);self.assertIn(value,html)
        self.assertIn("IDEAL",html)
        self.assertNotIn("Hunter Ranger",html);self.assertNotIn("Open Hand Monk",html)


class SmokeAndBoundaryTests(unittest.TestCase):
    def test_fixed_seed_smokes_write_versioned_outputs_and_selection_audit(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);damage=run_damage(DEFAULT_AUTHORITY,root/"damage",{7},1,16,19);control=run_control(DEFAULT_AUTHORITY,root/"control",{7},1,16,19)
            self.assertEqual(damage["matrix_rows"],24);self.assertEqual(control["matrix_rows"],4)
            for result in (damage,control):
                self.assertEqual(set(result["paths"]),{"csv","markdown","html"})
                self.assertTrue(all("14-1-0" in path.name and path.is_file() for path in result["paths"].values()))
            audit=root/"control"/"kv-14-1-0-control-selection-audit.csv"
            with audit.open(encoding="utf-8") as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue(rows);self.assertTrue(all(row["Selected Scenario"] for row in rows))
            self.assertTrue(all(row["Rules Version"]=="14.1.0" and row["Authority SHA-256"] and row["Roster SHA-256"] for row in rows))
            self.assertTrue(all(row["Comparator Config SHA-256"] for row in rows))
            with (root/"damage"/"kv-14-1-0-damage-detail.csv").open(encoding="utf-8") as stream:
                damage_row=next(csv.DictReader(stream))
            self.assertAlmostEqual(float(damage_row["Eldritch Knight DPR"]),11.616666666666667)
            self.assertAlmostEqual(float(damage_row["Battle Master DPR"]),19.025000000000002);self.assertTrue(damage_row["Comparator Config SHA-256"])
            with (root/"control"/"kv-14-1-0-control-detail.csv").open(encoding="utf-8") as stream:
                control_rows=list(csv.DictReader(stream))
            keyed={(row["Build"],row["Scenario"]):row for row in control_rows}
            self.assertEqual(keyed[("battle_master","menacing_attack")]["Whole-package control stick %"],"52.500000")
            self.assertEqual(keyed[("eldritch_knight","blindness_deafness")]["Whole-package control stick %"],"65.000000")
            self.assertTrue(all(row["Comparator Config SHA-256"] for row in control_rows))

    def test_imports_outputs_and_archive_are_not_positive_inputs_or_tracked(self)->None:
        inputs=json.loads((PROJECT_ROOT/"build"/"inputs.json").read_text(encoding="utf-8"))["inputs"]
        paths=[item["path"] for item in inputs]
        self.assertTrue(all(not path.startswith(".codex-import/") and "results" not in path and not path.endswith(".zip") for path in paths))
        tracked=subprocess.run(["git","ls-files"],cwd=PROJECT_ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
        self.assertTrue(all(not path.startswith(".codex-import/") and not path.endswith("harness-import.zip") for path in tracked))


if __name__=="__main__":unittest.main()
