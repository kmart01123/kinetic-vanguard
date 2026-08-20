from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from harness.authority import AuthorityError,AuthorityModel,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.comparison_report import BANDS,COMPARATOR_NOTICE,LEGAL_NOTICES,NOTICE_COLUMNS,PROJECT_ATTRIBUTION_NOTICE,SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,SRD_SECTION_5_NOTICE,VALUE_COLUMNS,classify_envelope,matrix_row,write_matrix
from harness.control_harness import _battle_master_retry_probability,_comparator_scenario,_composed_eldritch_knight_scenarios,_effect_available,_eldritch_strike_primer_probability,_kv_scenario,_repeat_rider_probability,run as run_control
from harness.damage_harness import Package,Standalone,_KVDamagePlanner,_battle_master_damage,_comparator_dpr,_kv_dpr,_rider_values,run as run_damage
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,Target,attack_probabilities,load_comparators,load_config,load_targets,save_success_probability


def _leaf_paths(value:object,prefix:tuple[object,...]=())->list[tuple[object,...]]:
    if isinstance(value,dict):
        return [path for key,item in value.items() for path in _leaf_paths(item,(*prefix,key))]
    if isinstance(value,list):
        return [path for index,item in enumerate(value) for path in _leaf_paths(item,(*prefix,index))]
    return [prefix]


def _path_value(value:object,path:tuple[object,...])->object:
    current=value
    for part in path:current=current[part]  # type: ignore[index]
    return current


def _set_path(value:object,path:tuple[object,...],replacement:object)->None:
    parent=_path_value(value,path[:-1]);parent[path[-1]]=replacement  # type: ignore[index]


def _path_label(path:tuple[object,...])->str:
    return '.'.join(f'[{part}]' if isinstance(part,int) else str(part) for part in path)


def _classify_control_leaf_mutation(validate:Callable[[],object],evaluate:Callable[[object],tuple[str,str]],*,expected_evaluation_rejection:str|None=None)->tuple[str,str|None]:
    try:validated=validate()
    except ValueError as error:return "validation_rejected",str(error)
    try:baseline,changed=evaluate(validated)
    except ValueError as error:
        if expected_evaluation_rejection is None or str(error)!=expected_evaluation_rejection:raise
        return "evaluation_rejected",str(error)
    return ("observable",None) if changed!=baseline else ("unobservable",None)


class AuthorityProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load()

    def test_real_root_authority_and_complete_stable_id_inventory(self)->None:
        self.assertEqual(Path(self.model.projection["authority_path"]),DEFAULT_AUTHORITY)
        self.assertEqual(self.model.rules_version,"14.3.0")
        self.assertEqual(self.model.projection["schema_version"],"2.2.0")
        self.assertEqual(self.model.projection["core"]["action_economy"],{"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False})
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

    def test_action_economy_mutation_fails_closed(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        probe="      action_surge_allows_additional_standalone_psionic_action: false"
        self.assertIn(probe,source)
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace(probe,"      action_surge_allows_additional_standalone_psionic_action: true",1),encoding="utf-8")
            with self.assertRaisesRegex(AuthorityError,"action_economy|action_surge_allows_additional"):AuthorityModel.load(authority)

    def test_progression_bands_cover_every_supported_level_once(self)->None:
        for name in ("proficiency_bonus","psi_points","psionic_focus","manifested_strike_die"):
            for level in range(3,21):self.assertIsInstance(self.model.progression(name,level),int)

    def test_comparator_inputs_are_isolated_minimal_and_fail_closed(self)->None:
        config=load_config();comparators=load_comparators()
        self.assertNotIn("damage_comparators",config);self.assertNotIn("control_comparators",config)
        self.assertEqual(comparators["source_ruleset"],"2024 fifth-edition rules")
        self.assertEqual(set(comparators["primary_comparator_ids"]),{"battle_master","eldritch_knight"})
        self.assertEqual(set(comparators["damage"]),{"battle_master","eldritch_knight"});self.assertEqual(set(comparators["control"]),{"battle_master","eldritch_knight"})
        source=DEFAULT_COMPARATORS.read_text(encoding="utf-8")
        for forbidden in ('"label"','"status"','"description"','"rules_text"','"feature_text"','"spell_text"','"maneuver_text"','"flavor"'):self.assertNotIn(forbidden,source)
        self.assertNotRegex(DEFAULT_AUTHORITY.read_text(encoding="utf-8"),r"(?i)battle.?master|eldritch.?knight")
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"comparators.json"
            reordered=deepcopy(comparators);reordered["primary_comparator_ids"]=["eldritch_knight","battle_master"]
            path.write_text(json.dumps(reordered),encoding="utf-8")
            self.assertEqual(load_comparators(path)["primary_comparator_ids"],reordered["primary_comparator_ids"])
            invalid=deepcopy(comparators);invalid["primary_comparator_ids"]=["battle_master","battle_master"]
            path.write_text(json.dumps(invalid),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Primary comparators"):load_comparators(path)
            malformed=deepcopy(comparators);malformed["primary_comparator_ids"]=[{},"battle_master"]
            path.write_text(json.dumps(malformed),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Primary comparators"):load_comparators(path)
        self.assertTrue(DEFAULT_CONFIG.is_file());self.assertTrue(DEFAULT_COMPARATORS.is_file())


class FrozenInputValidationTests(unittest.TestCase):
    def assert_json_rejected(self,source:Path,loader:object,mutate:object,pattern:str)->None:
        value=json.loads(source.read_text(encoding="utf-8"));mutate(value)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/source.name;path.write_text(json.dumps(value),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,pattern):loader(path)

    def test_benchmark_config_rejects_invalid_mechanics_and_progression(self)->None:
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["kv_profile"].__setitem__("weapon_damage",{}),"kv_profile keys")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["kv_profile"].__setitem__("attack_replacement_policy","mixed_weapon_and_manifested_strike"),"all-Manifested-Strike")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_progression"]["7"]["action_slots_by_round"].pop(),"cover every round")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_progression"]["7"].__setitem__("studied_attacks",True),"frozen Fighter progression")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["studied_attacks"].__setitem__("expiry","indefinite"),"Studied Attacks semantics")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["studied_attacks"].__setitem__("trigger","attack_roll_miss"),"Studied Attacks semantics")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["combat_prowess"].__setitem__("reset","end_of_turn"),"Combat Prowess semantics")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["combat_prowess"].__setitem__("uses_per_turn",True),"uses_per_turn must be an integer")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["combat_prowess"].__setitem__("activation_policy","first_eligible_miss"),"Combat Prowess semantics")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_mechanics"]["combat_prowess"].__setitem__("eligible_after_failed_attack_roll_bonus",False),"Combat Prowess semantics")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["control_feedback"].__setitem__("modeled_self_attack_exception","none"),"control-feedback policy")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"].__setitem__("objective",["primary_damage","aggregate_damage"]),"optimization objective")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"]["decision_timing"].__setitem__("unobserved_outcome_lookahead",True),"decision timing")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"]["decision_timing"].__setitem__("unobserved_outcome_lookahead",0),"lookahead must be a boolean")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["control_matrix"]["kv_scenarios"]["psychokinesis"][1].__setitem__("target_roles",["tertiary"]),"target roles")

    def test_comparator_config_rejects_unknown_missing_and_incomplete_parameters(self)->None:
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("unused_bonus",1),"damage.battle_master keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].pop("true_strike_uses_per_attack_action"),"damage.eldritch_knight keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["magic_weapon_bonus_by_level"].pop("20"),"magic_weapon_bonus_by_level keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("great_weapon_master_attack_action_bonus","fixed"),"GWM bonus")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maximum_maneuver_dice_per_attack",2),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maneuver_choice_timing","before_attack_roll"),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["known_maneuvers_by_level"]["7"].__setitem__(0,"riposte"),"audited fixed loadout")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["control"]["battle_master"]["known_maneuvers_by_level"]["11"].append("trip_attack"),"duplicate-free")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["tactical_policy"].__setitem__("true_strike_choice_timing","after_attack_roll"),"Eldritch Knight tactical policy")

class FighterNumericalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.targets=load_targets(profile="headline")

    def test_exact_fighter_dpr_sentinels_cover_every_supported_level(self)->None:
        expected={
            7:("Air Elemental",13.900000000000006,25.019884651397450),
            11:("Deva",40.916666666666686,81.801982129598270),
            15:("Adult Black Dragon",49.960671191473686,91.212464318445840),
            20:("Balor",108.956136040152290,168.983538568658330),
        }
        for level,(name,eldritch_knight,battle_master) in expected.items():
            with self.subTest(level=level,target=name):
                target=next(item for item in self.targets if item.level==level and item.name==name)
                self.assertAlmostEqual(_comparator_dpr(self.model,self.config,self.comparators,target,"eldritch_knight"),eldritch_knight,places=12)
                self.assertAlmostEqual(_comparator_dpr(self.model,self.config,self.comparators,target,"battle_master"),battle_master,places=12)

    def test_declared_comparator_switches_are_numerically_live(self)->None:
        target=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        baseline={build:_comparator_dpr(self.model,self.config,self.comparators,target,build) for build in ("battle_master","eldritch_knight")}
        mutations=[
            ("battle_master",lambda row:row.__setitem__("hew_critical_bonus_attack_once_per_round",False)),
            ("battle_master",lambda row:row.__setitem__("great_weapon_master_attack_action_bonus","disabled")),
            ("battle_master",lambda row:row["weapon"].__setitem__("great_weapon_fighting",False)),
            ("eldritch_knight",lambda row:row.__setitem__("true_strike_uses_per_attack_action",0)),
            ("eldritch_knight",lambda row:row["weapon"].__setitem__("great_weapon_fighting",True)),
        ]
        for build,mutate in mutations:
            with self.subTest(build=build,mutation=mutate):
                changed=deepcopy(self.comparators);mutate(changed["damage"][build])
                self.assertNotAlmostEqual(_comparator_dpr(self.model,self.config,changed,target,build),baseline[build],places=9)

    def test_true_strike_choice_uses_current_studied_state_before_the_roll(self)->None:
        base=next(item for item in self.targets if item.level==15 and item.name=="Adult Black Dragon")
        target=replace(base,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["15"];progression["attacks_per_action"]=2;progression["action_slots_by_round"]=[1,1,1]
        probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
            result=_comparator_dpr(self.model,config,self.comparators,target,"eldritch_knight")
        self.assertEqual(result,32.0)

    def test_precision_attack_keeps_both_fifty_percent_outcomes_in_the_optimum(self)->None:
        base=next(item for item in self.targets if item.level==7 and item.name=="Air Elemental")
        target=replace(base,ac=24,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression["attacks_per_action"]=1;progression["action_slots_by_round"]=[1,1,1]
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            result=_comparator_dpr(self.model,config,self.comparators,target,"battle_master")
        self.assertEqual(result,11.0)

    def test_battle_master_fixed_damage_loadout_counts_and_membership(self)->None:
        loadouts=self.comparators["damage"]["battle_master"]["known_maneuvers_by_level"]
        self.assertEqual({level:len(maneuvers) for level,maneuvers in loadouts.items()},{"7":5,"11":7,"15":9,"20":9})
        self.assertEqual(loadouts["7"],["feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack"])
        self.assertEqual(loadouts["11"][-2:],["lunging_attack","riposte"]);self.assertEqual(loadouts["15"][-2:],["goading_attack","menacing_attack"]);self.assertEqual(loadouts["20"],loadouts["15"])

    def test_feint_expected_value_spends_its_resource_before_a_possible_miss(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=False
        probabilities=lambda advantage:{1:0.5,10:0.5} if advantage else {1:1.0}
        pb=self.model.progression("proficiency_bonus",7);hit=_battle_master_damage(row,target,pb,7,False,8,True);expected=(15+0.5*(hit-5))/3
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        self.assertAlmostEqual(result,expected,places=12)

    def test_feint_hit_and_critical_add_exactly_one_doubled_maneuver_die(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=2;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        for natural,critical in ((10,False),(20,True)):
            probabilities=lambda advantage,natural=natural:{natural:1.0} if advantage else {1:1.0}
            with self.subTest(critical=critical),patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
                result=_comparator_dpr(self.model,config,comparators,target,"battle_master")
            self.assertAlmostEqual(result,_battle_master_damage(row,target,pb,7,critical,8,True)/3,places=12)

    def test_feinted_miss_cannot_add_precision_on_the_same_attack(self)->None:
        base=next(item for item in self.targets if item.level==7);attack_bonus=5+self.model.progression("proficiency_bonus",7)+1;target=replace(base,ac=attack_bonus+11,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=2;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        probabilities=lambda advantage:{10:0.5,20:0.5} if advantage else {1:1.0};expected=(5+_battle_master_damage(row,target,pb,7,True,8,True))/6
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        self.assertAlmostEqual(result,expected,places=12)

    def test_feint_plus_combat_prowess_applies_feint_damage_without_a_second_maneuver(self)->None:
        target=replace(next(item for item in self.targets if item.level==20),ac=40,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["20"].update(attacks_per_action=1,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=True)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["20"]=1;row["relentless_minimum_level"]=21;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",20)
        with patch("harness.damage_harness._natural_probabilities",return_value={1:1.0}):result=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        self.assertAlmostEqual(result,_battle_master_damage(row,target,pb,20,False,12,True)/3,places=12)

    def test_feint_and_hew_share_one_bonus_action_in_both_directions(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=True;pb=self.model.progression("proficiency_bonus",7);probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):feint_first=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        self.assertAlmostEqual(feint_first,_battle_master_damage(row,target,pb,7,True,8,True)/3,places=12)
        target=replace(next(item for item in self.targets if item.level==11),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["11"].update(attacks_per_action=2,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["11"]=["feinting_attack","precision_attack","sweeping_attack","lunging_attack","riposte"];row["superiority_pool_by_level"]["11"]=1;row["hew_critical_bonus_attack_once_per_round"]=True;pb=self.model.progression("proficiency_bonus",11)
        with patch("harness.damage_harness._natural_probabilities",return_value={20:1.0}):hew_first=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        expected=(2*_battle_master_damage(row,target,pb,11,True,0,True)+_battle_master_damage(row,target,pb,11,True,0,False))/3;self.assertAlmostEqual(hew_first,expected,places=12)

    def test_bonus_action_and_relentless_feint_resources_reset_per_turn(self)->None:
        target=replace(next(item for item in self.targets if item.level==15),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["15"].update(attacks_per_action=1,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["15"]=["feinting_attack"];row["superiority_pool_by_level"]["15"]=1;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",15);probabilities=lambda advantage:{10:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        expected=(_battle_master_damage(row,target,pb,15,False,10,True)+2*_battle_master_damage(row,target,pb,15,False,8,True))/3;self.assertAlmostEqual(result,expected,places=12)

    def test_generic_on_hit_damage_remains_exact_and_contextual_maneuvers_add_nothing_free(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,action_slots_by_round=[1,0,0],studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["7"]=["pushing_attack"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):generic=_comparator_dpr(self.model,config,comparators,target,"battle_master")
        self.assertAlmostEqual(generic,_battle_master_damage(row,target,pb,7,False,8,True)/3,places=12)
        target=replace(next(item for item in self.targets if item.level==11),damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);contextual=deepcopy(self.comparators);row=contextual["damage"]["battle_master"];row["known_maneuvers_by_level"]["11"]=["sweeping_attack","lunging_attack","riposte"];without=deepcopy(contextual);without["damage"]["battle_master"]["superiority_pool_by_level"]["11"]=0;without["damage"]["battle_master"]["relentless_minimum_level"]=21
        self.assertEqual(_comparator_dpr(self.model,config,contextual,target,"battle_master"),_comparator_dpr(self.model,config,without,target,"battle_master"))

    def test_combat_prowess_can_be_retained_after_an_observed_miss(self)->None:
        base=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        target=replace(base,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["20"];progression["attacks_per_action"]=2;progression["action_slots_by_round"]=[1,1,1]
        comparators=deepcopy(self.comparators);battle_master=comparators["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
            self.assertEqual(_comparator_dpr(self.model,config,comparators,target,"eldritch_knight"),40.0)
            self.assertEqual(_comparator_dpr(self.model,config,comparators,target,"battle_master"),38.0)

    def test_gwm_applies_to_each_attack_action_hit_but_not_the_single_hew_attack(self)->None:
        base=next(item for item in self.targets if item.level==7 and item.name=="Air Elemental")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression.update(attacks_per_action=2,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["7"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            main_delta=_comparator_dpr(self.model,config,enabled,target,"battle_master")-_comparator_dpr(self.model,config,disabled,target,"battle_master")
        self.assertAlmostEqual(main_delta,6.0,places=12)

        progression["attacks_per_action"]=1;battle_master["hew_critical_bonus_attack_once_per_round"]=True
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        without_hew=deepcopy(enabled);without_hew["damage"]["battle_master"]["hew_critical_bonus_attack_once_per_round"]=False
        with patch("harness.damage_harness._natural_probabilities",return_value={20:1.0}):
            hew_gwm_delta=_comparator_dpr(self.model,config,enabled,target,"battle_master")-_comparator_dpr(self.model,config,disabled,target,"battle_master")
            single_hew_delta=_comparator_dpr(self.model,config,enabled,target,"battle_master")-_comparator_dpr(self.model,config,without_hew,target,"battle_master")
        self.assertAlmostEqual(hew_gwm_delta,3.0,places=12)
        self.assertAlmostEqual(single_hew_delta,22.0,places=12)

    def test_relentless_supplies_only_one_free_die_per_turn(self)->None:
        base=next(item for item in self.targets if item.level==15 and item.name=="Adult Black Dragon")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["15"].update(attacks_per_action=2,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["15"]=0;battle_master["relentless_minimum_level"]=15;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=_comparator_dpr(self.model,config,enabled,target,"battle_master")-_comparator_dpr(self.model,config,disabled,target,"battle_master")
        self.assertAlmostEqual(delta,4.5,places=12)

    def test_one_maneuver_die_per_attack_prevents_superiority_relentless_stacking(self)->None:
        base=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["20"].update(attacks_per_action=1,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=3;battle_master["relentless_minimum_level"]=20;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);battle_master=disabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=_comparator_dpr(self.model,config,enabled,target,"battle_master")-_comparator_dpr(self.model,config,disabled,target,"battle_master")
        self.assertAlmostEqual(delta,6.5,places=12)

    def test_failed_attack_bonus_exposes_a_new_observed_prowess_decision(self)->None:
        target=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        unavailable=deepcopy(self.config);unavailable["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"]=False
        reviewed=_comparator_dpr(self.model,self.config,self.comparators,target,"battle_master")
        without_post_failure_choice=_comparator_dpr(self.model,unavailable,self.comparators,target,"battle_master")
        self.assertAlmostEqual(reviewed-without_post_failure_choice,0.05542795657382271,places=12)


class ComparatorLeafContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.base=load_targets()[0]

    def target(self,level:int,*,damage_immunity:str|None=None,condition_immunities:tuple[str,...]=())->Target:
        return replace(
            self.base,
            level=level,
            name=f"Comparator contract level {level}",
            ac=18,
            saves={"strength":12,"dexterity":-2,"constitution":1,"intelligence":2,"wisdom":-1,"charisma":0},
            magic_resistance=True,
            size="medium",
            condition_immunities=frozenset(condition_immunities),
            damage_resistances=frozenset(),
            damage_immunities=frozenset({damage_immunity} if damage_immunity else ()),
            damage_vulnerabilities=frozenset(),
        )

    def test_every_damage_comparator_leaf_is_numerically_live(self)->None:
        baselines:dict[tuple[str,int,str|None],float]={}
        for path in _leaf_paths(self.comparators["damage"],("damage",)):
            build=str(path[1]);field=str(path[-1]);current=_path_value(self.comparators,path)
            level=next((int(part) for part in path if isinstance(part,str) and part in {"7","11","15","20"}),20)
            damage_immunity=None
            if "known_maneuvers_by_level" in path:
                changed=deepcopy(self.comparators);_set_path(changed,path,f"{current}_unsupported")
                with tempfile.TemporaryDirectory() as directory:
                    comparator_path=Path(directory)/"comparators.json";comparator_path.write_text(json.dumps(changed),encoding="utf-8")
                    with self.subTest(path=_path_label(path)):
                        with self.assertRaisesRegex(ValueError,"audited fixed loadout"):load_comparators(comparator_path)
                continue
            if "tactical_policy" in path:
                replacement=current+1 if isinstance(current,int) else f"{current}_unsupported"
                changed=deepcopy(self.comparators);_set_path(changed,path,replacement)
                with self.subTest(path=_path_label(path)):
                    with self.assertRaisesRegex(ValueError,"tactical policy"):_comparator_dpr(self.model,self.config,changed,self.target(level),build)
                continue
            if field in {"damage_type","true_strike_damage_type"}:
                replacement="fire" if current!="fire" else "cold";damage_immunity=replacement
            elif field=="great_weapon_master_attack_action_bonus":replacement="disabled" if current!="disabled" else "proficiency_bonus"
            elif field=="relentless_minimum_level":replacement=level+1
            elif field=="true_strike_uses_per_attack_action":replacement=0 if current else 1
            elif isinstance(current,bool):replacement=not current
            elif isinstance(current,int):replacement=current+(2 if field in {"sides","relentless_die"} else 1)
            else:raise AssertionError(f"No numerical liveness mutation for {_path_label(path)}")
            target=self.target(level,damage_immunity=damage_immunity);key=(build,level,damage_immunity)
            if key not in baselines:baselines[key]=_comparator_dpr(self.model,self.config,self.comparators,target,build)
            changed=deepcopy(self.comparators);_set_path(changed,path,replacement)
            with self.subTest(path=_path_label(path)):
                self.assertNotEqual(_comparator_dpr(self.model,self.config,changed,target,build),baselines[key])

    def control_mutation(self,path:tuple[object,...],current:object)->object:
        build=str(path[1]);row_field=str(path[2]);field=str(path[-2]) if isinstance(path[-1],int) else str(path[-1])
        if row_field=="reliability_scenario_ids":
            selected=set(self.comparators["control"][build]["reliability_scenario_ids"])
            return next(scenario["id"] for scenario in self.comparators["control"][build]["scenarios"] if scenario["id"] not in selected)
        if row_field=="spell_access":return int(current)-1
        if field=="save" or field=="ability" or field=="save_ability":return "wisdom" if current=="strength" else "strength"
        if field=="delivery":return "action_spell" if current=="war_magic_cantrip" else "war_magic_cantrip"
        if field=="duration":return "until_start_next_turn" if current!="until_start_next_turn" else "until_end_next_turn"
        if field=="repeat_save_trigger":return "start_of_affected_turn"
        if field=="required_creature_type":return "construct"
        if field=="conditions":return "stunned" if current!="stunned" else "blinded"
        if field=="outcomes":return "speed_zero" if current!="speed_zero" else "forced_movement"
        if field=="maximum_size":return "tiny"
        if field=="gate":return "on_failed_save" if current=="after_failed_second_save" else "after_failed_second_save"
        if field=="requires_condition_effective":return "missing_condition"
        if field=="active_pattern":return "remaining_after_first_target_turn" if current=="first_target_turn_only" else "first_target_turn_only"
        if isinstance(current,str):return f"{current}_contract_probe"
        if isinstance(current,bool):return not current
        if isinstance(current,int):return current+1
        if isinstance(current,float):return current+0.25
        raise AssertionError(f"No control semantic mutation for {_path_label(path)}")

    def control_result_signature(self,result:dict[str,object])->str:
        keys=("scenario","spell_id","audit_comment_id","source_scope","disposition","eligible","reach","named","whole","after_repeats","shadow_components","targeting","breaks","escapes","escape_resolution","context_predicates","area_exit_policy","turn_branches","save_composition","automatic_save_success","automatic_success_rules")
        return json.dumps({key:result.get(key) for key in keys},sort_keys=True)

    def composed_eldritch_knight_signature(self,comparators:dict[str,object],target:Target)->list[tuple[str,tuple[str,...]]]:
        return [
            (str(scenario["id"]),tuple(str(primer) for primer in scenario.get("_composed_save_primers",[])))
            for scenario in _composed_eldritch_knight_scenarios(comparators,target)  # type: ignore[arg-type]
            if "_composed_save_primers" in scenario
        ]

    def scenario_level(self,row:dict[str,object],scenario:dict[str,object])->int:
        levels=sorted(int(level) for level in row["magic_weapon_bonus_by_level"])  # type: ignore[union-attr]
        if "spell_level" not in scenario:return next(level for level in levels if level>=int(row["minimum_level"]))
        access=row["spell_access"]["highest_slot_level_by_fighter_level"]  # type: ignore[index]
        return next(level for level in levels if level>=int(row["minimum_level"]) and int(access[str(level)])>=int(scenario["spell_level"]) and (not scenario.get("primer_hit_disadvantage") or level>=int(row["eldritch_strike_minimum_level"])))

    def scenario_signature(self,comparators:dict[str,object],build:str,scenario:dict[str,object],level:int,field:str,current:object)->str:
        target=replace(self.target(level),magic_resistance=False)
        if field=="required_creature_type":target=replace(target,creature_type=str(current))
        elif scenario.get("required_creature_type"):target=replace(target,creature_type=str(scenario["required_creature_type"]))
        if field=="maximum_size":target=replace(target,size=str(current))
        elif scenario.get("maximum_size"):target=replace(target,size=str(scenario["maximum_size"]))
        if field=="conditions":target=replace(target,condition_immunities=frozenset({str(current).lower()}))
        signature={"evaluation":json.loads(self.control_result_signature(_comparator_scenario(self.model,self.config,comparators,target,build,scenario)))}
        if build=="eldritch_knight":signature["composed_scenarios"]=self.composed_eldritch_knight_signature(comparators,target)
        return json.dumps(signature,sort_keys=True)

    def expected_control_evaluation_rejection(self,path:tuple[object,...],current:object)->str|None:
        field=str(path[-2]) if isinstance(path[-1],int) else str(path[-1])
        if field=="check":return f"Unknown ability check skill: {str(current).split('_',1)[1]}_contract_probe"
        if field=="area_exit_policy":return "Modeled action escape lacks the standing legal-exit policy"
        if field=="area_trigger":return "Unsupported modeled area trigger"
        return None

    def row_signature(self,comparators:dict[str,object],build:str)->str:
        row=comparators["control"][build]  # type: ignore[index]
        levels=sorted(int(level) for level in row["magic_weapon_bonus_by_level"])
        results=[]
        for level in levels:
            for scenario in row["scenarios"]:
                target=self.target(level)
                if scenario.get("required_creature_type"):target=replace(target,creature_type=str(scenario["required_creature_type"]))
                if scenario.get("maximum_size"):target=replace(target,size=str(scenario["maximum_size"]))
                results.append(self.control_result_signature(_comparator_scenario(self.model,self.config,comparators,target,build,scenario)))
        reliability=[]
        for scenario_id in row.get("reliability_scenario_ids",[]):
            scenario=next(item for item in row["scenarios"] if item["id"]==scenario_id);level=self.scenario_level(row,scenario);reliability.append((scenario_id,self.scenario_signature(comparators,build,scenario,level,"",None)))
        return json.dumps({"evaluations":results,"reliability":reliability},sort_keys=True)

    def test_every_control_comparator_leaf_has_observable_semantics(self)->None:
        outcomes:Counter[str]=Counter();evaluation_rejections:Counter[str]=Counter()
        with tempfile.TemporaryDirectory() as directory:
            comparator_path=Path(directory)/"comparators.json"
            for path in _leaf_paths(self.comparators["control"],("control",)):
                build=str(path[1]);row_field=str(path[2]);scenario_index=int(path[3]) if row_field=="scenarios" else None;field=str(path[-2]) if isinstance(path[-1],int) else str(path[-1]);current=_path_value(self.comparators,path)
                before=deepcopy(self.comparators);after=deepcopy(self.comparators);_set_path(after,path,self.control_mutation(path,current));comparator_path.write_text(json.dumps(after),encoding="utf-8")
                def evaluate(validated:object)->tuple[str,str]:
                    if scenario_index is not None:
                        before_scenario=before["control"][build]["scenarios"][scenario_index];after_scenario=validated["control"][build]["scenarios"][scenario_index];level=self.scenario_level(before["control"][build],before_scenario)
                        baseline=self.scenario_signature(before,build,before_scenario,level,field,current);changed=self.scenario_signature(validated,build,after_scenario,level,field,current)
                    else:
                        if build=="eldritch_knight" and row_field=="magic_weapon_bonus_by_level" and int(path[-1])<int(before["control"][build]["eldritch_strike_minimum_level"]):
                            before["control"][build]["eldritch_strike_minimum_level"]=int(path[-1]);validated["control"][build]["eldritch_strike_minimum_level"]=int(path[-1])
                        baseline=self.row_signature(before,build);changed=self.row_signature(validated,build)
                    return baseline,changed
                with self.subTest(path=_path_label(path)):
                    outcome,reason=_classify_control_leaf_mutation(lambda:load_comparators(comparator_path),evaluate,expected_evaluation_rejection=self.expected_control_evaluation_rejection(path,current))
                    self.assertNotEqual(outcome,"unobservable")
                outcomes[outcome]+=1
                if outcome=="evaluation_rejected":evaluation_rejections[str(reason)]+=1
        self.assertEqual(outcomes,Counter({"observable":947,"validation_rejected":455,"evaluation_rejected":6}))
        self.assertEqual(evaluation_rejections,Counter({"Unknown ability check skill: athletics_contract_probe":2,"Modeled action escape lacks the standing legal-exit policy":2,"Unsupported modeled area trigger":2}))

    def test_control_leaf_contract_propagates_accidental_evaluator_key_error(self)->None:
        def broken_evaluator(_:object)->tuple[str,str]:raise KeyError("missing evaluator leaf")
        with self.assertRaises(KeyError) as raised:_classify_control_leaf_mutation(lambda:self.comparators,broken_evaluator)
        self.assertEqual(raised.exception.args,("missing evaluator leaf",))

    def test_control_leaf_contract_classifies_intentional_validation_rejection(self)->None:
        changed=deepcopy(self.comparators);changed["control"]["battle_master"]["scenarios"][0]["id"]="unsupported_maneuver"
        with tempfile.TemporaryDirectory() as directory:
            comparator_path=Path(directory)/"comparators.json";comparator_path.write_text(json.dumps(changed),encoding="utf-8")
            outcome,reason=_classify_control_leaf_mutation(lambda:load_comparators(comparator_path),lambda _:self.fail("validation rejection must not reach evaluation"))
        self.assertEqual((outcome,reason),("validation_rejected","control.battle_master scenarios do not match the audited package set"))

    def test_ek_delivery_leaf_changes_production_composed_inventory(self)->None:
        before=deepcopy(self.comparators);after=deepcopy(self.comparators);before_scenario=next(item for item in before["control"]["eldritch_knight"]["scenarios"] if item["id"]=="slow");after_scenario=next(item for item in after["control"]["eldritch_knight"]["scenarios"] if item["id"]=="slow");after_scenario["delivery"]="war_magic_cantrip";target=self.target(20)
        baseline=self.composed_eldritch_knight_signature(before,target);changed=self.composed_eldritch_knight_signature(after,target)
        self.assertIn(("slow_after_mind_sliver",("mind_sliver",)),baseline);self.assertNotIn(("slow_after_mind_sliver",("mind_sliver",)),changed);self.assertNotEqual(changed,baseline)
        self.assertNotEqual(self.scenario_signature(before,"eldritch_knight",before_scenario,20,"delivery","action_spell"),self.scenario_signature(after,"eldritch_knight",after_scenario,20,"delivery","action_spell"))

    def test_ordinary_control_leaf_does_not_change_composed_inventory(self)->None:
        before=deepcopy(self.comparators);after=deepcopy(self.comparators);after["control"]["eldritch_knight"]["save_dc_base"]+=1;scenario=next(item for item in before["control"]["eldritch_knight"]["scenarios"] if item["id"]=="slow");target=self.target(20)
        self.assertEqual(self.composed_eldritch_knight_signature(before,target),self.composed_eldritch_knight_signature(after,target))
        self.assertNotEqual(self.scenario_signature(before,"eldritch_knight",scenario,20,"save_dc_base",8),self.scenario_signature(after,"eldritch_knight",scenario,20,"save_dc_base",8))


class DamagePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.base=next(item for item in load_targets(levels={20}) if item.name=="Balor");cls.mastery=cls.model.projection["core"]["overload"]["mastery"]

    def planner(self,attacks_per_action:int)->_KVDamagePlanner:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());packages=(Package(None,0,0,0),Package("branching_bolt",0,0,0));riders={packages[0]:(0.0,0.0),packages[1]:(100.0,100.0)}
        planner=_KVDamagePlanner(self.model,target,packages,riders,(("normal",(0.0,1.0,2.0)),),((),),0,attacks_per_action,(1,),True,True,0,0,self.mastery,0,1);self.addCleanup(planner.clear);return planner

    def test_combat_prowess_hit_instead_does_not_establish_studied(self)->None:
        planner=self.planner(1);package_index=1
        result=planner._resolve_attack_roll(0,0,0,0,package_index,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:4],("prowess",False,False,0))

    def test_combat_prowess_can_be_retained_for_a_more_valuable_later_attack(self)->None:
        planner=self.planner(2)
        result=planner._resolve_attack_roll(0,0,1,0,0,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:4],("miss",True,True,0))
        self.assertAlmostEqual(result.score.aggregate,101.0975,places=12)

    def test_studied_expires_after_a_zero_attack_turn(self)->None:
        planner=self.planner(1)
        result=planner._actions(0,0,True,True,0,0,0,0,2,False,0,False)
        self.assertEqual(result.choice,("end_turn",False))

    def test_standalone_consumes_one_slot_and_remains_capped_during_action_surge(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());package=Package(None,0,0,0);standalone=Standalone("forked_lightning",0,0,0,100.0,100.0,False)
        planner=_KVDamagePlanner(self.model,target,(package,),{package:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((standalone,),),0,1,(2,),False,False,0,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,100.0,places=12)
        self.assertEqual(planner.selection().count("forked_lightning:T0"),1)

    def test_pre_roll_rider_cost_is_spent_on_a_miss_without_outcome_lookahead(self)->None:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,1,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,1,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,5.0,places=12)

    def test_mastery_activates_only_on_first_overload_and_then_covers_the_turn(self)->None:
        planner=self.planner(1)
        self.assertEqual(planner._payment_options(0,1,0),((0,1,0,False),))
        self.assertIn((3,0,1,True),planner._payment_options(6,1,0))
        self.assertEqual(planner._payment_options(12,0,1),((6,0,1,False),))
        self.assertEqual(planner._payment_options(12,1,2),((12,1,2,False),))

    def test_tier_two_allowance_resets_for_a_new_attack_action(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,1,(2,),False,False,0,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T2"),2)

    def test_same_paid_rider_can_be_selected_on_all_three_manifested_strikes(self)->None:
        target=replace(next(item for item in load_targets(profile="headline",levels={11}) if item.name=="Deva"),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,2,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,3,(1,),False,False,6,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,285.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T0"),3)

    def test_miss_spends_cost_and_same_rider_remains_legal_on_next_strike(self)->None:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,1,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,2,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,10.0,places=12)

    def test_repeated_overload_pays_blood_tax_for_each_declaration(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",1,0,4);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,0,8,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T1"),2)

    def test_tier_two_remains_one_declaration_per_attack_action(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,3,(1,),False,False,0,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,95.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T2"),1)

    def test_repeated_thermal_fracture_uses_max_or_refresh_not_addition(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());thermal=Package("thermal_fracture",0,0,0)
        planner=_KVDamagePlanner(self.model,target,(thermal,),{thermal:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,0,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertEqual(planner._roll_options(0,0,"hit",False,1)[0][3],1)

    def test_observed_state_policy_matches_current_l20_sentinel(self)->None:
        target=next(item for item in load_targets(profile="headline",levels={20}) if item.name=="Ancient White Dragon")
        primary,aggregate,selection=_kv_dpr(self.model,self.config,target,"electrokinesis",3)
        self.assertAlmostEqual(primary,116.29434009056969,places=10)
        self.assertAlmostEqual(aggregate,191.24370620676075,places=10)
        self.assertIn("electron_burst:T2",selection)
        self.assertTrue(selection.endswith("|representative=locally-modal-path|policy=observed-state-adaptive"))

    def test_glacial_spike_damage_ignores_the_control_replacement_flag(self)->None:
        target=replace(self.base,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());package=Package("glacial_spike",0,0,0);pb=self.model.progression("proficiency_bonus",target.level);strike_die=self.model.progression("manifested_strike_die",target.level)
        with_replacement=_rider_values(self.model,target,"cryokinesis",1,target.level,pb,5,strike_die,package)
        projection=deepcopy(self.model.projection);next(item for item in projection["features"] if item["entity_id"]=="glacial_spike").pop("replaces_mastery");without_replacement=_rider_values(AuthorityModel(projection),target,"cryokinesis",1,target.level,pb,5,strike_die,package)
        self.assertEqual(with_replacement,(2.0,2.0));self.assertEqual(without_replacement,with_replacement)


class CanonicalControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.base=next(item for item in load_targets() if item.level==20 and item.name=="Balor")

    def target(self,*immunities:str)->Target:
        return replace(self.base,size="medium",condition_immunities=frozenset(immunities))

    def test_condition_immunity_removes_only_the_matching_canonical_effect(self)->None:
        target=self.target("stunned")
        row=_kv_scenario(self.model,self.config,target,"cryokinesis","snow_chains",2)
        self.assertGreater(row["reach"],0.0)
        self.assertEqual(row["named"],row["reach"])
        self.assertEqual(row["whole"],row["reach"])

    def test_target_roles_follow_canonical_primary_and_secondary_effects(self)->None:
        target=self.target();control=next(item for item in self.model.features["forked_lightning"]["control_tiers"] if int(item["tier"])==2)
        common,primary_only=control["effects"]
        self.assertTrue(_effect_available(target,common,"primary"));self.assertTrue(_effect_available(target,common,"secondary"))
        self.assertTrue(_effect_available(target,primary_only,"primary"));self.assertFalse(_effect_available(target,primary_only,"secondary"))
        primary=_kv_scenario(self.model,self.config,target,"electrokinesis","forked_lightning",2,"primary")
        secondary=_kv_scenario(self.model,self.config,target,"electrokinesis","forked_lightning",2,"secondary")
        self.assertEqual(primary["scenario"],"forked_lightning:T2");self.assertEqual(secondary["scenario"],"forked_lightning:T2:secondary")

    def test_dependent_effect_is_unavailable_when_its_required_condition_is_immune(self)->None:
        control=next(item for item in self.model.features["mass_levitation"]["control_tiers"] if int(item["tier"])==1);dependent=control["effects"][1]
        self.assertEqual(dependent["requires_condition"],"restrained")
        self.assertTrue(_effect_available(self.target(),dependent,"primary"));self.assertFalse(_effect_available(self.target("restrained"),dependent,"primary"))
        available=_kv_scenario(self.model,self.config,self.target(),"psychokinesis","mass_levitation",1)
        immune=_kv_scenario(self.model,self.config,self.target("restrained"),"psychokinesis","mass_levitation",1)
        self.assertGreater(available["named"],0.0);self.assertEqual(immune["named"],0.0);self.assertEqual(immune["whole"],0.0)

    def test_reviewed_kraken_corrections_keep_valid_components_only(self)->None:
        kraken=next(item for item in load_targets(levels={20}) if item.name=="Kraken")
        absolute=_kv_scenario(self.model,self.config,kraken,"cryokinesis","absolute_zero",1)
        self.assertAlmostEqual(absolute["whole"],15.0,places=12)
        for tier in (0,1):
            primary=_kv_scenario(self.model,self.config,kraken,"psychokinesis","explosion_implosion",tier,"primary")
            secondary=_kv_scenario(self.model,self.config,kraken,"psychokinesis","explosion_implosion",tier,"secondary")
            self.assertEqual(primary["whole"],0.0)
            self.assertAlmostEqual(secondary["whole"],17.688609683593764,places=12)

    def test_snow_chains_can_retry_after_an_observed_miss_or_save(self)->None:
        target=self.target();single=attack_probabilities(self.model.kv_attack_bonus(20,5)+2,target.ac);reach=single[1]+single[2];failed=1-save_success_probability(target,"constitution",self.model.kv_save_dc(20,5));one=reach*failed
        repeated=_repeat_rider_probability(self.model,self.config,20,0,int(self.model.features["snow_chains"]["psi_cost"]),one)
        self.assertGreater(repeated,one);self.assertLessEqual(repeated,1.0)

    def test_control_retry_contract_contains_no_target_identity(self)->None:
        from inspect import signature
        self.assertNotIn("target",signature(_repeat_rider_probability).parameters)
        same_target=_repeat_rider_probability(self.model,self.config,11,0,2,0.25)
        different_target=_repeat_rider_probability(self.model,self.config,11,0,2,0.25)
        retry_then_redirect=_repeat_rider_probability(self.model,self.config,11,0,2,0.25)
        self.assertEqual(same_target,different_target);self.assertEqual(different_target,retry_then_redirect)

    def test_all_signature_riders_are_zero_psi_repeatable_and_overload_still_costs_blood(self)->None:
        signature_ids={"ember_bolt","glacial_spike","telekinetic_shove","static_discharge"}
        self.assertEqual(self.model.projection["core"]["manifested_strike"]["rider_repeatability"],"per_manifested_strike")
        no_blood=deepcopy(self.config);no_blood["kv_profile"]["blood_tax_hp_fraction"]=0.0
        for entity_id in signature_ids:
            with self.subTest(entity_id=entity_id):
                feature=self.model.features[entity_id]
                self.assertEqual(feature["psi_cost"],0);self.assertEqual(feature["activation"],"on_hit");self.assertEqual(feature["damage_delivery"],"on_hit_rider")
                self.assertGreater(self.model.blood_tax(11,1),0)
                self.assertEqual(_repeat_rider_probability(self.model,no_blood,11,1,int(feature["psi_cost"]),0.25),0.0)

    def test_glacial_spike_and_telekinetic_shove_retry_signature_control(self)->None:
        target=self.target()
        for discipline,entity_id,tier in (("cryokinesis","glacial_spike",0),("cryokinesis","glacial_spike",1),("psychokinesis","telekinetic_shove",0),("psychokinesis","telekinetic_shove",1)):
            with self.subTest(entity_id=entity_id,tier=tier):
                row=_kv_scenario(self.model,self.config,target,discipline,entity_id,tier)
                bonus=self.model.kv_attack_bonus(target.level,5)+2;reach=sum(attack_probabilities(bonus,target.ac)[1:])
                control=next(item for item in self.model.features[entity_id]["control_tiers"] if int(item["tier"])==tier)
                one=reach
                if control["application"]=="failed_save":
                    save=control["save"];save=self.model.disciplines[discipline]["signature_save"] if save=="discipline_signature" else save
                    one=reach*(1-save_success_probability(target,save,self.model.kv_save_dc(target.level,5)))
                self.assertGreater(row["named"],100*one)

    def test_glacial_spike_replaces_slow_reliability_without_weakening_other_cryo_scenarios(self)->None:
        target=self.target()
        for tier in (0,1,2):
            with self.subTest(tier=tier):
                row=_kv_scenario(self.model,self.config,target,"cryokinesis","glacial_spike",tier);self.assertEqual(row["mastery"],0.0);self.assertFalse(any(component["source_effect"]=="mastery:slow" for component in row["shadow_components"]))
        ordinary=_kv_scenario(self.model,self.config,target,"cryokinesis","snow_chains",2);self.assertGreater(ordinary["mastery"],0.0);self.assertTrue(any(component["source_effect"]=="mastery:slow" for component in ordinary["shadow_components"]))

    def test_static_discharge_tier_two_signature_control_cannot_retry(self)->None:
        feature=self.model.features["static_discharge"]
        self.assertEqual(feature["psi_cost"],0)
        self.assertAlmostEqual(_repeat_rider_probability(self.model,self.config,20,2,int(feature["psi_cost"]),0.25),0.25,places=12)


class ControlComparatorRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.targets=load_targets(profile="headline")

    def target(self,level:int)->Target:
        return next(item for item in self.targets if item.level==level and not item.condition_immunities and not item.magic_resistance)

    def scenario(self,build:str,scenario_id:str)->dict[str,object]:
        return next(item for item in self.comparators["control"][build]["scenarios"] if item["id"]==scenario_id)

    def test_battle_master_one_attack_matches_the_old_single_attempt(self)->None:
        self.assertAlmostEqual(_battle_master_retry_probability(1,5,0.6,0.25),0.15,places=12)

    def test_battle_master_two_attack_sentinel_tracks_misses_saves_and_dice(self)->None:
        self.assertAlmostEqual(_battle_master_retry_probability(2,2,0.5,0.5),0.4375,places=12)
        self.assertAlmostEqual(_battle_master_retry_probability(2,1,0.5,0.5),0.375,places=12)
        self.assertGreater(_battle_master_retry_probability(2,1,0.5,0.5),_battle_master_retry_probability(1,1,0.5,0.5))

    def test_battle_master_attempts_are_bounded_by_attacks_pool_and_one_die_per_attack(self)->None:
        self.assertAlmostEqual(_battle_master_retry_probability(2,99,0.5,0.5),0.4375,places=12)
        self.assertAlmostEqual(_battle_master_retry_probability(1,99,0.5,0.5),0.25,places=12)
        self.assertEqual(_battle_master_retry_probability(4,0,0.5,0.5),0.0)

    def test_battle_master_comparator_uses_frozen_inputs_and_observed_retry_chronology(self)->None:
        damage=self.comparators["damage"]["battle_master"];control=self.comparators["control"]["battle_master"]
        self.assertEqual(damage["superiority_pool_by_level"],{"7":5,"11":5,"15":6,"20":6})
        self.assertEqual(damage["tactical_policy"]["maneuver_choice_timing"],"pre_roll_feint_or_post_roll_observed_result")
        self.assertEqual(damage["tactical_policy"]["decision_information"],"observed_state_only")
        self.assertEqual(damage["tactical_policy"]["maneuver_die_consumption"],"on_use_before_die_result")
        self.assertEqual(damage["tactical_policy"]["maximum_maneuver_dice_per_attack"],1)
        self.assertNotIn("relentless",control)
        target=self.target(11);scenario=self.scenario("battle_master","menacing_attack");row=_comparator_scenario(self.model,self.config,self.comparators,target,"battle_master",scenario)
        bonus=self.model.progression("proficiency_bonus",11)+int(control["attack_ability_modifier"])+int(control["magic_weapon_bonus_by_level"]["11"]);hit=sum(attack_probabilities(bonus,target.ac)[1:]);dc=int(control["save_dc_base"])+self.model.progression("proficiency_bonus",11)+int(control["save_ability_modifier"]);failed=1-save_success_probability(target,"wisdom",dc)
        self.assertAlmostEqual(row["whole"],100*_battle_master_retry_probability(3,5,hit,failed),places=12)
        self.assertEqual(row["source_scope"],"independently_expressed_phb_comparator_abstraction");self.assertEqual(row["audit_comment_id"],5322552001);self.assertEqual(row["shadow_components"][0]["duration"],"until_end_next_turn")

    def test_battle_master_control_loadouts_gate_scenarios_at_every_level(self)->None:
        row=self.comparators["control"]["battle_master"];self.assertEqual({level:len(maneuvers) for level,maneuvers in row["known_maneuvers_by_level"].items()},{"7":5,"11":7,"15":9,"20":9})
        for level in (7,11,15,20):
            for scenario in row["scenarios"]:
                with self.subTest(level=level,scenario=scenario["id"]):self.assertTrue(_comparator_scenario(self.model,self.config,self.comparators,replace(self.target(level),size="medium"),"battle_master",scenario)["eligible"])
        changed=deepcopy(self.comparators);changed["control"]["battle_master"]["known_maneuvers_by_level"]["7"].remove("menacing_attack");scenario=self.scenario("battle_master","menacing_attack");result=_comparator_scenario(self.model,self.config,changed,self.target(7),"battle_master",scenario);self.assertFalse(result["eligible"]);self.assertEqual(result["whole"],0)

    def test_battle_master_control_size_recovery_diagnostics_and_immunity(self)->None:
        medium=replace(self.target(11),size="medium");huge=replace(medium,size="huge");row=self.comparators["control"]["battle_master"]
        push=self.scenario("battle_master","pushing_attack");pushed=_comparator_scenario(self.model,self.config,self.comparators,medium,"battle_master",push);self.assertGreater(pushed["whole"],0);self.assertEqual(pushed["shadow_components"][0]["magnitude_feet"],15);self.assertEqual(pushed["shadow_components"][0]["qualifiers"]["direction"],"directly_away_from_source");self.assertFalse(_comparator_scenario(self.model,self.config,self.comparators,huge,"battle_master",push)["eligible"])
        trip=self.scenario("battle_master","trip_attack");self.assertNotIn("outcomes",trip["effects"][0]);tripped=_comparator_scenario(self.model,self.config,self.comparators,medium,"battle_master",trip);self.assertEqual(tripped["shadow_components"][0]["duration"],"until_target_stands");self.assertEqual(tripped["shadow_components"][0]["qualifiers"]["recovery_timing"],"target_turn");self.assertEqual(tripped["shadow_components"][0]["qualifiers"]["recovery_movement_cost"],"half_speed")
        immune=replace(medium,condition_immunities=frozenset({"frightened"}));menacing=_comparator_scenario(self.model,self.config,self.comparators,immune,"battle_master",self.scenario("battle_master","menacing_attack"));self.assertEqual(menacing["whole"],0);self.assertFalse(menacing["shadow_components"])
        for scenario_id,predicate in (("goading_attack","alternate_valid_attack_target"),("disarming_attack","benchmark_relevant_held_object_exists")):
            result=_comparator_scenario(self.model,self.config,self.comparators,medium,"battle_master",self.scenario("battle_master",scenario_id));self.assertEqual(result["whole"],0);self.assertIn(predicate,result["context_predicates"]);self.assertTrue(result["shadow_components"]);self.assertEqual(result["shadow_components"][0]["pricing_status"],"context_required")

    def test_eldritch_strike_primer_hand_sentinel_uses_at_least_one_hit(self)->None:
        self.assertAlmostEqual(_eldritch_strike_primer_probability(2,0.5),0.75,places=12)
        self.assertAlmostEqual(_eldritch_strike_primer_probability(4,0.5),0.9375,places=12)

    def test_plain_blindness_remains_one_cast_and_level_seven_is_unchanged(self)->None:
        target=self.target(7);row=self.comparators["control"]["eldritch_knight"];scenario=self.scenario("eldritch_knight","blindness_deafness");result=_comparator_scenario(self.model,self.config,self.comparators,target,"eldritch_knight",scenario)
        dc=int(row["save_dc_base"])+self.model.progression("proficiency_bonus",7)+int(row["spellcasting_ability_modifier_by_level"]["7"]);expected=1-save_success_probability(target,"constitution",dc,False,True)
        self.assertEqual(result["reach"],100.0);self.assertAlmostEqual(result["whole"],100*expected,places=12)
        eldritch=self.scenario("eldritch_knight","blindness_after_eldritch_strike");self.assertFalse(_comparator_scenario(self.model,self.config,self.comparators,target,"eldritch_knight",eldritch)["eligible"])

    def test_eldritch_strike_uses_every_ordinary_primer_attack_without_stacking_or_action_surge(self)->None:
        row=self.comparators["control"]["eldritch_knight"];scenario=self.scenario("eldritch_knight","blindness_after_eldritch_strike")
        for level,attacks in ((11,3),(15,3),(20,4)):
            with self.subTest(level=level):
                target=self.target(level);pb=self.model.progression("proficiency_bonus",level);bonus=pb+int(row["attack_ability_modifier"])+int(row["magic_weapon_bonus_by_level"][str(level)]);hit=sum(attack_probabilities(bonus,target.ac)[1:]);mark=1-(1-hit)**attacks
                self.assertAlmostEqual(_eldritch_strike_primer_probability(attacks,hit),mark,places=12)
                dc=int(row["save_dc_base"])+pb+int(row["spellcasting_ability_modifier_by_level"][str(level)]);normal=1-save_success_probability(target,"constitution",dc,False,True);disadvantaged=1-save_success_probability(target,"constitution",dc,True,True);expected=mark*disadvantaged+(1-mark)*normal
                result=_comparator_scenario(self.model,self.config,self.comparators,target,"eldritch_knight",scenario)
                self.assertAlmostEqual(result["whole"],100*expected,places=12)
                action_surge_mark=_eldritch_strike_primer_probability(2*attacks,hit)
                self.assertNotAlmostEqual(result["whole"],100*(action_surge_mark*disadvantaged+(1-action_surge_mark)*normal),places=12)


class ClassificationTests(unittest.TestCase):
    def test_shared_envelope_classifier_is_swap_invariant_and_inclusive(self)->None:
        expected=((9,"COLD"),(10,"IDEAL"),(15,"IDEAL"),(20,"IDEAL"),(21,"HOT"))
        for eldritch_knight,battle_master in ((10,20),(20,10)):
            for kv,band in expected:
                with self.subTest(kv=kv,ek=eldritch_knight,bm=battle_master):
                    self.assertEqual(classify_envelope(kv,eldritch_knight,battle_master),band)
                    for kind in ("damage","control"):
                        self.assertEqual(matrix_row({},kv,eldritch_knight,battle_master,kind)["Band"],band)

    def test_swap_preserves_band_delta_and_dynamic_boundary_values(self)->None:
        for kind in ("damage","control"):
            for kv,band,delta in ((8,"COLD","-20.00"),(10,"IDEAL","0.00"),(15,"IDEAL","0.00"),(20,"IDEAL","0.00"),(24,"HOT","+20.00")):
                forward=matrix_row({},kv,10,20,kind)
                reversed_order=matrix_row({},kv,20,10,kind)
                for field in ("Band","Boundary Delta %","Lower Boundary","Upper Boundary"):
                    self.assertEqual(forward[field],reversed_order[field])
                self.assertEqual((forward["Band"],forward["Boundary Delta %"]),(band,delta))

    def test_unavailable_equal_and_invalid_inputs_fail_or_classify_explicitly(self)->None:
        for values in ((15,0,20),(15,20,0),(float("nan"),10,20),(15,float("inf"),20)):
            with self.subTest(values=values):
                self.assertEqual(classify_envelope(*values),"N/A")
        for values in ((float("nan"),10,20),(15,float("inf"),20)):
            with self.subTest(matrix_values=values):
                with self.assertRaisesRegex(ValueError,"must be finite"):
                    matrix_row({},*values,"damage")
        self.assertEqual(classify_envelope(9,10,10),"COLD")
        self.assertEqual(classify_envelope(10,10,10),"IDEAL")
        self.assertEqual(classify_envelope(11,10,10),"HOT")
        with self.assertRaisesRegex(ValueError,"Unsupported benchmark type"):
            matrix_row({},15,10,20,"unsupported")

    def test_percentage_uses_displayed_aggregate_raw_values(self)->None:
        row=matrix_row({"Level":7},10.0,8.0,20.0,"damage")
        self.assertEqual(row["Benchmark Type"],"Damage")
        self.assertEqual(row["KV as % of EK"],"125.00")
        self.assertEqual(row["KV as % of BM"],"50.00")
        self.assertEqual(row["Band"],"IDEAL")
        self.assertEqual(row["Boundary Delta %"],"0.00")

    def test_matrix_row_identifies_dynamic_boundaries_and_ties(self)->None:
        expected=(
            (10,20,"Eldritch Knight","Battle Master"),
            (20,10,"Battle Master","Eldritch Knight"),
        )
        for eldritch_knight,battle_master,lower_name,upper_name in expected:
            row=matrix_row({},15,eldritch_knight,battle_master,"control")
            self.assertEqual(row["Benchmark Type"],"Control Reliability")
            self.assertEqual(row["Lower Comparator"],lower_name)
            self.assertEqual(row["Upper Comparator"],upper_name)
            self.assertEqual(row["Lower Boundary"],"10.000000")
            self.assertEqual(row["Upper Boundary"],"20.000000")
        tied=matrix_row({},10,10,10,"damage")
        self.assertEqual(tied["Lower Comparator"],"Eldritch Knight + Battle Master")
        self.assertEqual(tied["Upper Comparator"],"Eldritch Knight + Battle Master")
        self.assertEqual(tied["Lower Boundary"],"10.000000")
        self.assertEqual(tied["Upper Boundary"],"10.000000")

    def test_supported_bands_have_no_comparator_order_state(self)->None:
        self.assertEqual(BANDS,{"COLD","IDEAL","HOT","N/A"})
        self.assertNotIn("ORDER CHECK",BANDS)

    def test_report_notices_are_structured_and_source_grounded(self)->None:
        repository_notice=(PROJECT_ROOT/"NOTICE.md").read_text(encoding="utf-8")
        content_notice=(PROJECT_ROOT/"LICENSE-CONTENT").read_text(encoding="utf-8")
        labels=[label for label,_ in LEGAL_NOTICES]
        self.assertEqual(len(labels),len(set(labels)))
        self.assertEqual(NOTICE_COLUMNS,{f"Notice {label}":value for label,value in LEGAL_NOTICES})
        for retained in (SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,COMPARATOR_NOTICE):
            self.assertIn(retained,repository_notice)
        self.assertEqual(SRD_SECTION_5_NOTICE,"Section 5 of CC-BY-4.0 includes a Disclaimer of Warranties and Limitation of Liability that limits our liability to you.")
        project=NOTICE_COLUMNS["Notice Project Attribution"]
        for retained in ("Copyright © 2026 NixNinja","Created by NixNinja","https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode","Section 5 disclaimer"):
            self.assertIn(retained,project)
        self.assertEqual(project,PROJECT_ATTRIBUTION_NOTICE)
        for retained in ("Copyright © 2026 NixNinja","Created by NixNinja"):
            self.assertIn(retained,repository_notice)
        for retained in ("https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode","Section 5"):
            self.assertIn(retained,content_notice)
        component=NOTICE_COLUMNS["Notice Component Boundary"]
        for retained in ("Copyright (c) 2026, NixNinja","BSD-3-Clause","CC BY 4.0","LICENSE-CODE","LICENSE.md","NOTICE.md"):
            self.assertIn(retained,component)

    def test_csv_markdown_html_share_full_envelope_evidence(self)->None:
        row=matrix_row({"Level":7,"Discipline":"cryokinesis"},10,8,20,"damage")
        control_row=matrix_row({"Level":7,"Discipline":"cryokinesis"},25,20,10,"control")
        provenance={"rules_version":"14.1.0","authority_sha256":"probe","roster_sha256":"probe"}
        self.assertEqual([key for key in row if key in VALUE_COLUMNS],VALUE_COLUMNS)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=write_matrix(root/"damage","14.1.0","damage",[row],provenance)
            control_paths=write_matrix(root/"control","14.1.0","control",[control_row],provenance)
            bad=dict(row);bad["Band"]="ORDER CHECK"
            with self.assertRaisesRegex(ValueError,"unsupported band"):
                write_matrix(root/"bad","14.1.0","damage",[bad],provenance)
            incomplete=dict(row);del incomplete["Lower Boundary"]
            with self.assertRaisesRegex(ValueError,"missing evidence"):
                write_matrix(root/"incomplete","14.1.0","damage",[incomplete],provenance)
            stale_band=dict(row);stale_band["Band"]="HOT"
            with self.assertRaisesRegex(ValueError,"stale Band"):
                write_matrix(root/"stale-band","14.1.0","damage",[stale_band],provenance)
            stale_delta=dict(row);stale_delta["Boundary Delta %"]="+1.00"
            with self.assertRaisesRegex(ValueError,"stale Boundary Delta"):
                write_matrix(root/"stale-delta","14.1.0","damage",[stale_delta],provenance)
            with self.assertRaisesRegex(ValueError,"stale Benchmark Type"):
                write_matrix(root/"wrong-kind","14.1.0","damage",[control_row],provenance)
            with self.assertRaisesRegex(ValueError,"Unsupported comparison matrix kind"):
                write_matrix(root/"unknown-kind","14.1.0","unknown",[row],provenance)
            with paths["csv"].open(encoding="utf-8") as stream:
                csv_row=next(csv.DictReader(stream))
            markdown=paths["markdown"].read_text(encoding="utf-8");html=paths["html"].read_text(encoding="utf-8")
            control_markdown=control_paths["markdown"].read_text(encoding="utf-8")
            control_html=control_paths["html"].read_text(encoding="utf-8")
        self.assertTrue(all(csv_row[key]==value for key,value in row.items()))
        self.assertEqual(csv_row["Provenance Rules Version"],"14.1.0")
        self.assertEqual(csv_row["Provenance Authority Sha256"],"probe")
        self.assertEqual(csv_row["Provenance Roster Sha256"],"probe")
        self.assertEqual({key:csv_row[key] for key in NOTICE_COLUMNS},NOTICE_COLUMNS)
        self.assertEqual(csv_row["Lower Comparator"],"Eldritch Knight")
        self.assertEqual(csv_row["Upper Comparator"],"Battle Master")
        self.assertEqual(csv_row["Lower Boundary"],"8.000000")
        self.assertEqual(csv_row["Upper Boundary"],"20.000000")
        for value in row.values():
            self.assertIn(value,markdown);self.assertIn(value,html)
        self.assertIn("## Licensing and notices",markdown)
        self.assertIn("<h2>Licensing and notices</h2>",html)
        for label,value in LEGAL_NOTICES:
            self.assertEqual(markdown.count(value),1,label)
            self.assertEqual(html.count(value),1,label)
        limitation=("Control Reliability measures how often the configured control package takes effect. "
                    "It does not measure the relative severity, duration, area, or strategic value of different control effects. "
                    "A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered.")
        self.assertTrue(control_markdown.startswith("# Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix"))
        self.assertIn("<title>Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix</title>",control_html)
        self.assertIn("<h1>Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix</h1>",control_html)
        self.assertIn(limitation,control_markdown)
        self.assertIn(limitation,control_html)
        for rendered in (markdown,html,control_markdown,control_html):
            self.assertNotIn("ORDER CHECK",rendered)
            self.assertNotIn("Hunter Ranger",rendered)
            self.assertNotIn("Open Hand Monk",rendered)


class SmokeAndBoundaryTests(unittest.TestCase):
    def test_damage_smoke_writes_current_detail_and_matrix_outputs(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);damage=run_damage(DEFAULT_AUTHORITY,root,{7},1,profile="headline")
            self.assertEqual(damage["detail_rows"],12);self.assertEqual(damage["matrix_rows"],24)
            self.assertEqual(set(damage["paths"]),{"csv","markdown","html"})
            self.assertTrue(all("14-3-0" in path.name and path.is_file() for path in damage["paths"].values()))
            with (root/"kv-14-3-0-damage-detail.csv").open(encoding="utf-8") as stream:
                damage_row=next(csv.DictReader(stream))
            self.assertEqual(damage_row["Target Profile"],"headline")
            self.assertAlmostEqual(float(damage_row["Eldritch Knight DPR"]),13.9,places=12)
            with damage["paths"]["csv"].open(encoding="utf-8") as stream:
                matrix_rows=list(csv.DictReader(stream))
            self.assertTrue(matrix_rows);self.assertTrue(all(row["Provenance Evaluator"]=="exact_analytical_enumeration" for row in matrix_rows))
            workers_root=root/"workers-2"
            workers_damage=run_damage(DEFAULT_AUTHORITY,workers_root,{7},1,write_headline=False,workers=2,profile="headline")
            self.assertEqual(workers_damage["paths"],{})
            self.assertEqual(
                (root/"kv-14-3-0-damage-detail.csv").read_bytes(),
                (workers_root/"kv-14-3-0-damage-detail.csv").read_bytes(),
            )

    def test_control_smoke_writes_current_detail_selection_and_matrix_outputs(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);control=run_control(DEFAULT_AUTHORITY,root,{7},1,profile="headline")
            self.assertEqual(control["matrix_rows"],4);self.assertEqual(set(control["paths"]),{"csv","markdown","html"})
            self.assertEqual(control["shadow_rows"],0);self.assertIsNone(control["shadow_path"])
            self.assertEqual(list(root.glob("*shadow*")),[])
            with (root/"kv-14-3-0-control-selection-audit.csv").open(encoding="utf-8") as stream:
                audit_rows=list(csv.DictReader(stream))
            self.assertTrue(audit_rows);self.assertTrue(all(row["Selected Scenario"] for row in audit_rows))
            self.assertTrue(all(row["Target Profile"]=="headline" for row in audit_rows))
            with (root/"kv-14-3-0-control-detail.csv").open(encoding="utf-8") as stream:
                control_rows=list(csv.DictReader(stream))
            keyed={(row["Build"],row["Scenario"]):row for row in control_rows}
            self.assertEqual(keyed[("battle_master","menacing_attack")]["Whole-package control stick %"],"80.859375")
            self.assertEqual(keyed[("eldritch_knight","blindness_deafness")]["Whole-package control stick %"],"55.000000")
            with control["paths"]["csv"].open(encoding="utf-8") as stream:
                matrix_rows=list(csv.DictReader(stream))
            self.assertTrue(matrix_rows);self.assertTrue(all(row["Provenance Evaluator"]=="exact_analytical_enumeration" for row in matrix_rows))


if __name__=="__main__":unittest.main()
