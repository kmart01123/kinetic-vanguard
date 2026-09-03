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

from harness.authority import AuthorityError,AuthorityModel,AuthorityUnavailableError,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.comparison_report import BANDS,COMPARATOR_NOTICE,LEGAL_NOTICES,NOTICE_COLUMNS,PROJECT_ATTRIBUTION_NOTICE,SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,SRD_SECTION_5_NOTICE,VALUE_COLUMNS,classify_envelope,matrix_row,write_matrix
from harness.control_harness import BATTLE_MASTER_REFERENCE_SCENARIOS,ELDRITCH_KNIGHT_REFERENCE_FAMILIES,EFFECTIVE,INEFFECTIVE_NULLIFIED,INEFFECTIVE_STRUCTURAL,PARTIALLY_EFFECTIVE,_attack_action_retry_probability,_battle_master_retry_probability,_catalog_effectiveness,_catalog_rider_scenario,_comparator_scenario,_comparator_scenario_available_at_level,_composed_eldritch_knight_scenarios,_delivery_recipe,_effect_available,_eldritch_strike_primer_probability,_is_eldritch_knight_reference_scenario,_kv_retry_resources,_kv_rider_delivery_recipe,_kv_scenario,_mastery_scenario,_repeat_rider_probability,_select_control_value,run as run_control
from harness.control_value import DEFAULT_PRIMITIVES,DEFAULT_SCORING,shadow_rows
from harness.damage_harness import Package,Standalone,_KVDamagePlanner,_battle_master_damage,_battle_master_dpr_for_schedule,_battle_master_result,_comparator_dpr,_comparator_score,_eldritch_knight_result,_kv_dpr,_psionic_apex_packet,_rider_values,_strike_packet_options,run as run_damage
from harness.ek_damage_planner import EKDamagePlanner,EKScore,EKState,chromatic_orb_duplicate_probability
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,Target,attack_probabilities,file_sha256,fighter_action_schedules,load_comparators,load_config,load_targets,save_success_probability


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
        self.assertEqual(self.model.projection["projection_version"],"1.3.0")
        self.assertEqual(self.model.rules_version,"14.3.0")
        self.assertEqual(self.model.projection["schema_version"],"2.7.0")
        self.assertEqual(self.model.projection["core"]["action_economy"],{"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False})
        self.assertEqual(self.model.holdout_formula(17)["kind"],"halve_total_rounded_down")
        self.assertEqual(self.model.holdout_formula(18),{"minimum_level":18,"maximum_level":20,"kind":"dice_plus_psionic_ability_modifier","count":1,"sides":6})
        self.assertEqual(self.model.psionic_apex_strike_packet("psychokinesis",18)["reset"],"start_of_each_attack_action")
        self.assertIsNone(self.model.psionic_apex_strike_packet("psychokinesis",17));self.assertIsNone(self.model.psionic_apex_strike_packet("pyrokinesis",20))
        feature_ids=list(self.model.features)
        self.assertEqual(len(feature_ids),len(set(feature_ids)))
        self.assertEqual(set(self.model.disciplines),{"pyrokinesis","cryokinesis","psychokinesis","electrokinesis"})
        self.assertTrue(all(feature["minimum_level"]>=3 and feature["psi_cost"]>=0 for feature in self.model.features.values()))
        self.assertTrue(all("entity_id" in feature and feature["title"] for feature in self.model.features.values()))
        self.assertTrue(self.model.features["advanced_phase_step"]["advanced_training"])

    def test_structural_yaml_mutation_changes_projection_without_python_edit(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        probe="id: pyrokinesis\n          damage_type: fire"
        self.assertIn(probe,source)
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace(probe,"id: pyrokinesis\n          damage_type: cold",1),encoding="utf-8")
            mutated=AuthorityModel.load(authority)
        self.assertEqual(self.model.disciplines["pyrokinesis"]["damage_type"],"fire")
        self.assertEqual(mutated.disciplines["pyrokinesis"]["damage_type"],"cold")

    def test_missing_mechanics_fail_closed(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace("      action_economy:\n","      missing_action_economy:\n",1),encoding="utf-8")
            with self.assertRaises(AuthorityError):AuthorityModel.load(authority)

    def test_authority_unavailability_is_narrow_and_fail_closed(self)->None:
        self.assertTrue(issubclass(AuthorityUnavailableError,AuthorityError))
        with self.assertRaisesRegex(AuthorityUnavailableError,"Feature flare is unavailable at Fighter level 11"):
            self.model.feature("flare",11)
        with self.assertRaisesRegex(AuthorityUnavailableError,"Tier 2 is unavailable at Fighter level 7"):
            self.model.feature("glacial_spike",7,2)
        for entity_id,tier,message in (("unknown_feature",None,"Unknown"),("glacial_spike",9,"Unsupported")):
            with self.subTest(entity_id=entity_id,tier=tier):
                with self.assertRaisesRegex(AuthorityError,message) as raised:
                    self.model.feature(entity_id,7,tier)
                self.assertNotIsInstance(raised.exception,AuthorityUnavailableError)

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
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_progression"]["7"].__setitem__("maximum_action_surges_per_turn",2),"maximum one Action Surge")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["fighter_progression"]["20"].__setitem__("action_surge_uses_over_horizon",4),"one-per-turn benchmark horizon")
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
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].pop("spell_slots_by_level"),"damage.eldritch_knight keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["magic_weapon_bonus_by_level"].pop("20"),"magic_weapon_bonus_by_level keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("great_weapon_master_attack_action_bonus","fixed"),"GWM bonus")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maximum_maneuver_dice_per_attack",2),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maneuver_choice_timing","before_attack_roll"),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["known_maneuvers_by_level"]["7"].__setitem__(0,"riposte"),"audited fixed loadout")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["control"]["battle_master"]["known_maneuvers_by_level"]["11"].append("trip_attack"),"duplicate-free")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["tactical_policy"].__setitem__("spell_choice_timing","after_resolution"),"Eldritch Knight tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["weapon"].__setitem__("great_weapon_fighting",True),"must not use Great Weapon Fighting")

class FighterNumericalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.targets=load_targets(profile="headline")

    def battle_master_dpr(self,config:dict[str,object],comparators:dict[str,object],target:Target,schedule:tuple[int,...])->float:
        return _battle_master_dpr_for_schedule(self.model,config,comparators["damage"]["battle_master"],target,schedule)  # type: ignore[index]

    def test_legal_action_surge_schedules_are_exact_and_complete(self)->None:
        expected={
            7:((2,1,1),(1,2,1),(1,1,2)),
            11:((2,1,1),(1,2,1),(1,1,2)),
            15:((2,1,1),(1,2,1),(1,1,2)),
            20:((2,2,1),(2,1,2),(1,2,2)),
        }
        for level,schedules in expected.items():
            with self.subTest(level=level):
                progression=self.config["fighter_progression"][str(level)];actual=fighter_action_schedules(progression,3)
                self.assertEqual(actual,schedules);self.assertTrue(all(max(schedule)<=2 for schedule in actual))
                self.assertTrue(all(sum(schedule)==(5 if level==20 else 4) for schedule in actual))
        self.assertEqual(max(sum(schedule)*int(self.config["fighter_progression"]["20"]["attacks_per_action"]) for schedule in expected[20]),20)

    def test_all_damage_models_consume_the_shared_schedule_inventory(self)->None:
        target=next(item for item in self.targets if item.level==7);inventory=fighter_action_schedules(self.config["fighter_progression"]["7"],3)
        with patch("harness.damage_harness._fighter_schedules",return_value=inventory) as shared,patch("harness.damage_harness._kv_dpr_for_schedule",return_value=(1.0,1.0,"selection")) as kv_evaluate,patch("harness.damage_harness._battle_master_dpr_for_schedule",return_value=1.0) as bm_evaluate,patch("harness.damage_harness.EKDamagePlanner") as ek_planner:
            ek_planner.return_value.solve.return_value=EKScore(1.0,1.0)
            _kv_dpr(self.model,self.config,target,"pyrokinesis",1)
            _battle_master_result(self.model,self.config,self.comparators["damage"]["battle_master"],target)
            _eldritch_knight_result(self.model,self.config,self.comparators["damage"]["eldritch_knight"],target,1)
        self.assertEqual(shared.call_count,3)
        self.assertEqual(tuple(item.args[-1] for item in kv_evaluate.call_args_list),inventory)
        self.assertEqual(tuple(item.args[-1] for item in bm_evaluate.call_args_list),inventory)
        self.assertEqual(tuple(item.args[-1] for item in ek_planner.call_args_list),inventory)

    def test_exact_fighter_dpr_sentinels_cover_every_supported_level(self)->None:
        expected={
            7:("Air Elemental",18.816666666666663,25.019884651397450),
            11:("Deva",43.2,81.801982129598270),
            15:("Adult Black Dragon",49.960671191473644,91.214066953875730),
            20:("Balor",135.50405069063788,168.983538568658330),
        }
        for level,(name,eldritch_knight,battle_master) in expected.items():
            with self.subTest(level=level,target=name):
                target=next(item for item in self.targets if item.level==level and item.name==name)
                self.assertAlmostEqual(_comparator_dpr(self.model,self.config,self.comparators,target,"eldritch_knight"),eldritch_knight,places=12)
                self.assertAlmostEqual(_comparator_dpr(self.model,self.config,self.comparators,target,"battle_master"),battle_master,places=12)

    def test_declared_comparator_switches_are_numerically_live(self)->None:
        target=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        baseline=_comparator_dpr(self.model,self.config,self.comparators,target,"battle_master")
        mutations=[
            lambda row:row.__setitem__("hew_critical_bonus_attack_once_per_round",False),
            lambda row:row.__setitem__("great_weapon_master_attack_action_bonus","disabled"),
            lambda row:row["weapon"].__setitem__("great_weapon_fighting",False),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed=deepcopy(self.comparators);mutate(changed["damage"]["battle_master"])
                self.assertNotAlmostEqual(_comparator_dpr(self.model,self.config,changed,target,"battle_master"),baseline,places=9)
        row=deepcopy(self.comparators["damage"]["eldritch_knight"]);progression=deepcopy(self.config["fighter_progression"]["7"])
        planner=EKDamagePlanner(row,replace(target,level=7,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset()),progression,self.model.progression("proficiency_bonus",7),1,(1,));state=EKState(0,1,False,False,(0,0,0,0),True);original=planner._weapon_damage(state,False,False);row["dueling_damage_bonus"]+=1
        changed=EKDamagePlanner(row,planner.target,progression,self.model.progression("proficiency_bonus",7),1,(1,))
        self.assertNotEqual(changed._weapon_damage(state,False,False),original)

    def test_true_strike_choice_uses_current_studied_state_before_the_roll(self)->None:
        base=next(item for item in self.targets if item.level==15 and item.name=="Adult Black Dragon")
        target=replace(base,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());progression=deepcopy(self.config["fighter_progression"]["15"])
        planner=EKDamagePlanner(self.comparators["damage"]["eldritch_knight"],target,progression,self.model.progression("proficiency_bonus",15),1,(1,));studied=EKState(0,0,True,False,(0,0,0,0),False);unstudied=replace(studied,studied=False)
        probabilities=lambda _bonus,_ac,advantage=False:(0.0,0.0,1.0) if advantage else (1.0,0.0,0.0)
        def forced(current:EKState,true_strike_first:bool)->EKScore:
            if true_strike_first:return planner._cast_value(current,"true_strike",0,lambda state:planner._weapon_attack(state,False,lambda _:EKScore()))
            return planner._weapon_attack(current,False,lambda state:planner._cast_value(state,"true_strike",0,lambda _:EKScore()))
        with patch("harness.ek_damage_planner.attack_probabilities",side_effect=probabilities):
            studied_first=forced(studied,True);studied_second=forced(studied,False);studied_optimum=planner._sequence(studied,1,"true_strike",0,True)
            unstudied_first=forced(unstudied,True);unstudied_second=forced(unstudied,False);unstudied_optimum=planner._sequence(unstudied,1,"true_strike",0,True)
        self.assertGreater(studied_first.primary,studied_second.primary);self.assertEqual(studied_optimum,studied_first)
        self.assertGreater(unstudied_second.primary,unstudied_first.primary);self.assertEqual(unstudied_optimum,unstudied_second)

    def test_precision_attack_keeps_both_fifty_percent_outcomes_in_the_optimum(self)->None:
        base=next(item for item in self.targets if item.level==7 and item.name=="Air Elemental")
        target=replace(base,ac=24,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression["attacks_per_action"]=1
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            result=self.battle_master_dpr(config,self.comparators,target,(1,1,1))
        self.assertEqual(result,11.0)

    def test_battle_master_fixed_damage_loadout_counts_and_membership(self)->None:
        loadouts=self.comparators["damage"]["battle_master"]["known_maneuvers_by_level"]
        self.assertEqual({level:len(maneuvers) for level,maneuvers in loadouts.items()},{"7":5,"11":7,"15":9,"20":9})
        self.assertEqual(loadouts["7"],["feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack"])
        self.assertEqual(loadouts["11"][-2:],["lunging_attack","riposte"]);self.assertEqual(loadouts["15"][-2:],["goading_attack","menacing_attack"]);self.assertEqual(loadouts["20"],loadouts["15"])

    def test_eldritch_knight_fixed_damage_cantrips_and_prepared_spells(self)->None:
        row=self.comparators["damage"]["eldritch_knight"]
        self.assertEqual(row["cantrips_by_level"],{
            "7":["true_strike","acid_splash"],
            "11":["true_strike","acid_splash","poison_spray"],
            "15":["true_strike","acid_splash","poison_spray"],
            "20":["true_strike","acid_splash","poison_spray"],
        })
        self.assertEqual(row["prepared_spells_by_level"],{
            "7":["chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt"],
            "11":["chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt","scorching_ray","melfs_acid_arrow","enlarge_reduce"],
            "15":["chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt","scorching_ray","enlarge_reduce","fireball","lightning_bolt","bestow_curse"],
            "20":["chromatic_orb","magic_missile","witch_bolt","scorching_ray","shatter","enlarge_reduce","melfs_acid_arrow","fireball","bestow_curse","conjure_minor_elementals","greater_invisibility","phantasmal_killer","vitriolic_sphere"],
        })
        self.assertEqual({level:len(spells) for level,spells in row["prepared_spells_by_level"].items()},{"7":5,"11":8,"15":10,"20":13})
        true_strike=next(spell for spell in row["spells"] if spell["id"]=="true_strike")
        self.assertEqual(true_strike["damage_dice_by_level"],{
            "7":{"count":1,"sides":6},
            "11":{"count":2,"sides":6},
            "15":{"count":2,"sides":6},
            "20":{"count":3,"sides":6},
        })

    def test_eldritch_knight_planner_clears_caches_when_solve_raises(self)->None:
        target=next(item for item in self.targets if item.level==7)
        with patch("harness.damage_harness.EKDamagePlanner") as planner_type:
            planner_type.return_value.solve.side_effect=RuntimeError("planner failed")
            with self.assertRaisesRegex(RuntimeError,"planner failed"):
                _comparator_score(self.model,self.config,self.comparators,target,"eldritch_knight",1)
            planner_type.return_value.clear.assert_called_once_with()

    def test_eldritch_knight_exact_slot_pools_and_dragons_breath_types(self)->None:
        row=self.comparators["damage"]["eldritch_knight"]
        self.assertEqual(row["spell_slots_by_level"],{
            "7":{"1":4,"2":2,"3":0,"4":0},
            "11":{"1":4,"2":3,"3":0,"4":0},
            "15":{"1":4,"2":3,"3":2,"4":0},
            "20":{"1":4,"2":3,"3":3,"4":1},
        })
        spell=next(item for item in row["spells"] if item["id"]=="dragons_breath")
        self.assertEqual(spell["damage_types"],["acid","cold","fire","lightning","poison"])
        self.assertEqual(spell["damage_type_choice"],"once_at_cast_time")

    def test_feint_expected_value_spends_its_resource_before_a_possible_miss(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=False
        probabilities=lambda advantage:{1:0.5,10:0.5} if advantage else {1:1.0}
        pb=self.model.progression("proficiency_bonus",7);hit=_battle_master_damage(row,target,pb,7,False,8,True);expected=(15+0.5*(hit-5))/3
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=self.battle_master_dpr(config,comparators,target,(1,1,1))
        self.assertAlmostEqual(result,expected,places=12)

    def test_feint_hit_and_critical_add_exactly_one_doubled_maneuver_die(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=2;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        for natural,critical in ((10,False),(20,True)):
            probabilities=lambda advantage,natural=natural:{natural:1.0} if advantage else {1:1.0}
            with self.subTest(critical=critical),patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
                result=self.battle_master_dpr(config,comparators,target,(1,0,0))
            self.assertAlmostEqual(result,_battle_master_damage(row,target,pb,7,critical,8,True)/3,places=12)

    def test_feinted_miss_cannot_add_precision_on_the_same_attack(self)->None:
        base=next(item for item in self.targets if item.level==7);attack_bonus=5+self.model.progression("proficiency_bonus",7)+1;target=replace(base,ac=attack_bonus+11,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=2;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        probabilities=lambda advantage:{10:0.5,20:0.5} if advantage else {1:1.0};expected=(5+_battle_master_damage(row,target,pb,7,True,8,True))/6
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=self.battle_master_dpr(config,comparators,target,(1,0,0))
        self.assertAlmostEqual(result,expected,places=12)

    def test_feint_plus_combat_prowess_applies_feint_damage_without_a_second_maneuver(self)->None:
        target=replace(next(item for item in self.targets if item.level==20),ac=40,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["20"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=True)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["20"]=1;row["relentless_minimum_level"]=21;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",20)
        with patch("harness.damage_harness._natural_probabilities",return_value={1:1.0}):result=self.battle_master_dpr(config,comparators,target,(1,0,0))
        self.assertAlmostEqual(result,_battle_master_damage(row,target,pb,20,False,12,True)/3,places=12)

    def test_feint_and_hew_share_one_bonus_action_in_both_directions(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=True;pb=self.model.progression("proficiency_bonus",7);probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):feint_first=self.battle_master_dpr(config,comparators,target,(1,0,0))
        self.assertAlmostEqual(feint_first,_battle_master_damage(row,target,pb,7,True,8,True)/3,places=12)
        target=replace(next(item for item in self.targets if item.level==11),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["11"].update(attacks_per_action=2,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["11"]=["feinting_attack","precision_attack","sweeping_attack","lunging_attack","riposte"];row["superiority_pool_by_level"]["11"]=1;row["hew_critical_bonus_attack_once_per_round"]=True;pb=self.model.progression("proficiency_bonus",11)
        with patch("harness.damage_harness._natural_probabilities",return_value={20:1.0}):hew_first=self.battle_master_dpr(config,comparators,target,(1,0,0))
        expected=(2*_battle_master_damage(row,target,pb,11,True,0,True)+_battle_master_damage(row,target,pb,11,True,0,False))/3;self.assertAlmostEqual(hew_first,expected,places=12)

    def test_bonus_action_and_relentless_feint_resources_reset_per_turn(self)->None:
        target=replace(next(item for item in self.targets if item.level==15),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["15"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["15"]=["feinting_attack"];row["superiority_pool_by_level"]["15"]=1;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",15);probabilities=lambda advantage:{10:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):result=self.battle_master_dpr(config,comparators,target,(1,1,1))
        expected=(_battle_master_damage(row,target,pb,15,False,10,True)+2*_battle_master_damage(row,target,pb,15,False,8,True))/3;self.assertAlmostEqual(result,expected,places=12)

    def test_generic_on_hit_damage_remains_exact_and_contextual_maneuvers_add_nothing_free(self)->None:
        target=replace(next(item for item in self.targets if item.level==7),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);config["fighter_progression"]["7"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        comparators=deepcopy(self.comparators);row=comparators["damage"]["battle_master"];row["known_maneuvers_by_level"]["7"]=["pushing_attack"];row["superiority_pool_by_level"]["7"]=1;row["hew_critical_bonus_attack_once_per_round"]=False;pb=self.model.progression("proficiency_bonus",7)
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):generic=self.battle_master_dpr(config,comparators,target,(1,0,0))
        self.assertAlmostEqual(generic,_battle_master_damage(row,target,pb,7,False,8,True)/3,places=12)
        target=replace(next(item for item in self.targets if item.level==11),damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());config=deepcopy(self.config);contextual=deepcopy(self.comparators);row=contextual["damage"]["battle_master"];row["known_maneuvers_by_level"]["11"]=["sweeping_attack","lunging_attack","riposte"];without=deepcopy(contextual);without["damage"]["battle_master"]["superiority_pool_by_level"]["11"]=0;without["damage"]["battle_master"]["relentless_minimum_level"]=21
        self.assertEqual(_comparator_dpr(self.model,config,contextual,target,"battle_master"),_comparator_dpr(self.model,config,without,target,"battle_master"))

    def test_combat_prowess_can_be_retained_after_an_observed_miss(self)->None:
        base=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        target=replace(base,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["20"];progression["attacks_per_action"]=2
        comparators=deepcopy(self.comparators);battle_master=comparators["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
            self.assertEqual(self.battle_master_dpr(config,comparators,target,(1,1,1)),38.0)

    def test_gwm_applies_to_each_attack_action_hit_but_not_the_single_hew_attack(self)->None:
        base=next(item for item in self.targets if item.level==7 and item.name=="Air Elemental")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression.update(attacks_per_action=2,studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["7"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            main_delta=self.battle_master_dpr(config,enabled,target,(1,1,1))-self.battle_master_dpr(config,disabled,target,(1,1,1))
        self.assertAlmostEqual(main_delta,6.0,places=12)

        progression["attacks_per_action"]=1;battle_master["hew_critical_bonus_attack_once_per_round"]=True
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        without_hew=deepcopy(enabled);without_hew["damage"]["battle_master"]["hew_critical_bonus_attack_once_per_round"]=False
        with patch("harness.damage_harness._natural_probabilities",return_value={20:1.0}):
            hew_gwm_delta=self.battle_master_dpr(config,enabled,target,(1,1,1))-self.battle_master_dpr(config,disabled,target,(1,1,1))
            single_hew_delta=self.battle_master_dpr(config,enabled,target,(1,1,1))-self.battle_master_dpr(config,without_hew,target,(1,1,1))
        self.assertAlmostEqual(hew_gwm_delta,3.0,places=12)
        self.assertAlmostEqual(single_hew_delta,22.0,places=12)

    def test_relentless_supplies_only_one_free_die_per_turn(self)->None:
        base=next(item for item in self.targets if item.level==15 and item.name=="Adult Black Dragon")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["15"].update(attacks_per_action=2,studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["15"]=0;battle_master["relentless_minimum_level"]=15;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=self.battle_master_dpr(config,enabled,target,(1,1,1))-self.battle_master_dpr(config,disabled,target,(1,1,1))
        self.assertAlmostEqual(delta,4.5,places=12)

    def test_one_maneuver_die_per_attack_prevents_superiority_relentless_stacking(self)->None:
        base=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        target=replace(base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        config=deepcopy(self.config);config["fighter_progression"]["20"].update(attacks_per_action=1,studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=3;battle_master["relentless_minimum_level"]=20;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);battle_master=disabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=self.battle_master_dpr(config,enabled,target,(1,1,1))-self.battle_master_dpr(config,disabled,target,(1,1,1))
        self.assertAlmostEqual(delta,6.5,places=12)

    def test_failed_attack_bonus_exposes_a_new_observed_prowess_decision(self)->None:
        target=next(item for item in self.targets if item.level==20 and item.name=="Balor")
        unavailable=deepcopy(self.config);unavailable["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"]=False
        reviewed=_comparator_dpr(self.model,self.config,self.comparators,target,"battle_master")
        without_post_failure_choice=_comparator_dpr(self.model,unavailable,self.comparators,target,"battle_master")
        self.assertAlmostEqual(reviewed-without_post_failure_choice,0.05542795657382271,places=12)


class EldritchKnightPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.base=load_targets()[0]

    def target(self,level:int=7,**changes:object)->Target:
        values={"level":level,"name":"EK hand sentinel","ac":18,"saves":{"strength":0,"dexterity":0,"constitution":0,"intelligence":0,"wisdom":0,"charisma":0},"magic_resistance":False,"damage_resistances":frozenset(),"damage_immunities":frozenset(),"damage_vulnerabilities":frozenset(),"blindsight_range":0,"truesight_range":0};values.update(changes)
        return replace(self.base,**values)

    def planner(self,level:int=7,cluster:int=1,*,attacks:int|None=None,actions:tuple[int,...]=(1,),target:Target|None=None)->EKDamagePlanner:
        progression=deepcopy(self.config["fighter_progression"][str(level)])
        if attacks is not None:progression["attacks_per_action"]=attacks
        return EKDamagePlanner(self.comparators["damage"]["eldritch_knight"],target or self.target(level),progression,self.model.progression("proficiency_bonus",level),cluster,actions)

    def state(self,planner:EKDamagePlanner,*,actions:int=1,slots:tuple[int,int,int,int]=(0,0,0,0),bonus:bool=True,concentration:str="",concentration_type:str="")->EKState:
        return EKState(0,actions,False,False,slots,bonus,concentration,concentration_type)

    def test_war_magic_replaces_one_attack_and_is_not_free(self)->None:
        planner=self.planner(attacks=2);state=self.state(planner);spell=planner.spells["acid_splash"]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):
            ordinary=planner._attack_action(state);war_magic=planner._attack_action(state,"acid_splash",0,1)
        weapon=planner._weapon_damage(state,False,False);acid=planner._packet(spell["damage_dice_by_level"]["7"],"acid")
        self.assertEqual(ordinary.primary,2*weapon);self.assertEqual(war_magic.primary,weapon+acid)

    def test_improved_war_magic_replaces_exactly_two_attacks(self)->None:
        planner=self.planner(20,attacks=4,target=self.target(20));state=self.state(planner,slots=(1,0,0,0));spell=planner.spells["magic_missile"]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            result=planner._attack_action(state,"magic_missile",1,2)
        weapon=planner._weapon_damage(state,False,False);missiles=3*planner._packet(spell["dart_damage"],"force")
        self.assertEqual(result.primary,2*weapon+missiles)

    def test_improved_war_magic_consumes_the_turns_slotted_spell_allowance(self)->None:
        planner=self.planner(20,attacks=4,actions=(2,),target=self.target(20));state=self.state(planner,actions=2,slots=(2,0,0,0));seen=[]
        after_attack=next(next_state for next_state in planner._consume_action_states(state,magic=False) if next_state.ordinary_action_available)
        planner._cast_value(after_attack,"magic_missile",1,lambda next_state:(seen.append(next_state),EKScore())[1]);after_improved=seen[0]
        self.assertTrue(after_improved.slotted_spell_cast_this_turn);self.assertTrue(after_improved.ordinary_action_available)
        self.assertEqual(planner._slot_options(after_improved,planner.spells["magic_missile"]),())
        with self.assertRaisesRegex(ValueError,"already expended a spell slot"):planner._consume_slot(after_improved,1)
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            self.assertGreater(planner._attack_action(after_improved).primary,0.0)

    def test_normal_slotted_spell_prevents_later_improved_war_magic(self)->None:
        planner=self.planner(20,attacks=4,actions=(2,),target=self.target(20));state=self.state(planner,actions=2,slots=(2,0,0,0));seen=[]
        after_magic_action=planner._consume_action_states(state,magic=True)[0]
        planner._cast_value(after_magic_action,"magic_missile",1,lambda next_state:(seen.append(next_state),EKScore())[1]);after_spell=seen[0]
        self.assertTrue(after_spell.slotted_spell_cast_this_turn);self.assertEqual(planner._slot_options(after_spell,planner.spells["magic_missile"]),())
        with self.assertRaisesRegex(ValueError,"already expended a spell slot"):
            planner._attack_action(after_spell,"magic_missile",1,2)

    def test_war_magic_cantrip_remains_legal_after_improved_war_magic(self)->None:
        planner=self.planner(20,attacks=4,actions=(2,),target=self.target(20));state=self.state(planner,actions=2,slots=(1,0,0,0));seen=[]
        after_attack=next(next_state for next_state in planner._consume_action_states(state,magic=False) if next_state.ordinary_action_available)
        planner._cast_value(after_attack,"magic_missile",1,lambda next_state:(seen.append(next_state),EKScore())[1]);after_improved=seen[0]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            ordinary=planner._attack_action(after_improved);war_magic=planner._attack_action(after_improved,"true_strike",0,1)
        self.assertGreater(war_magic.primary,ordinary.primary);self.assertTrue(after_improved.slotted_spell_cast_this_turn)

    def test_slotted_spell_allowance_resets_only_on_the_next_turn(self)->None:
        planner=self.planner(20,actions=(1,1),target=self.target(20));state=replace(self.state(planner,actions=0,slots=(1,0,0,0)),slotted_spell_cast_this_turn=True);seen=[]
        with patch.object(planner,"_turn",side_effect=lambda next_state:(seen.append(next_state),EKScore())[1]):planner._finish_turn(state)
        next_round=seen[0]
        self.assertEqual(next_round.round_index,1);self.assertFalse(next_round.slotted_spell_cast_this_turn)
        after_action=planner._consume_action_states(next_round,magic=True)[0];cast_states=[]
        planner._cast_value(after_action,"magic_missile",1,lambda next_state:(cast_states.append(next_state),EKScore())[1])
        self.assertTrue(cast_states[0].slotted_spell_cast_this_turn)

    def test_action_surge_never_refreshes_slotted_spell_allowance(self)->None:
        planner=self.planner(20,actions=(2,),target=self.target(20));state=replace(self.state(planner,actions=2,slots=(1,0,0,0)),slotted_spell_cast_this_turn=True)
        after_attacks=planner._consume_action_states(state,magic=False)
        self.assertEqual(len(after_attacks),2);self.assertTrue(all(next_state.slotted_spell_cast_this_turn for next_state in after_attacks))
        self.assertEqual(planner._slot_options(state,planner.spells["magic_missile"]),())

    def test_bonus_action_slotted_spell_uses_the_shared_turn_allowance(self)->None:
        planner=self.planner(actions=(1,),target=self.target());state=self.state(planner,slots=(1,1,0,0));after_bonus=planner._cast_dragons_breath(state,2)
        self.assertTrue(after_bonus.slotted_spell_cast_this_turn);self.assertEqual(planner._slot_options(after_bonus,planner.spells["magic_missile"]),())
        after_action=planner._consume_action_states(state,magic=True)[0];seen=[]
        planner._cast_value(after_action,"magic_missile",1,lambda next_state:(seen.append(next_state),EKScore())[1])
        with self.assertRaisesRegex(ValueError,"already expended a spell slot"):planner._cast_dragons_breath(seen[0],2)

    def test_ordinary_action_spell_consumes_one_action_and_action_surge_adds_only_an_action(self)->None:
        immune=frozenset({"acid","cold","fire","lightning","poison","radiant","slashing","thunder"});target=self.target(damage_immunities=immune,saves={ability:20 for ability in ("strength","dexterity","constitution","intelligence","wisdom","charisma")})
        planner=self.planner(actions=(2,),target=target);state=self.state(planner,actions=2,slots=(2,0,0,0))
        consumed=planner._consume_action_states(state,magic=False)
        self.assertEqual({next_state.ordinary_action_available for next_state in consumed},{False,True})
        self.assertEqual(planner._consume_action_states(state,magic=True),(replace(state,actions_left=1,ordinary_action_available=False),))
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=1.0):
            self.assertEqual(planner._turn(state),EKScore(10.5,10.5))
            self.assertEqual(planner._turn(replace(state,actions_left=1,ordinary_action_available=False)),EKScore())
        weapon_planner=self.planner(actions=(2,));surge_only=replace(self.state(weapon_planner,actions=1),ordinary_action_available=False)
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=1.0):self.assertGreater(weapon_planner._turn(surge_only).primary,0.0)

    def test_bonus_action_ledger_allows_only_one_witch_packet(self)->None:
        planner=self.planner(actions=(1,));state=self.state(planner,actions=0,slots=(0,1,0,0),concentration="witch_bolt")
        self.assertEqual(planner._turn(state),EKScore(6.5,6.5))

    def test_concentration_replacement_is_exclusive(self)->None:
        planner=self.planner(15,target=self.target(15));states=[];initial=self.state(planner,slots=(0,1,1,0))
        planner._cast_value(initial,"enlarge_reduce",2,lambda state:(states.append(state),EKScore())[1]);enlarged=replace(next(state for state in states if state.concentration=="enlarge_reduce"),slotted_spell_cast_this_turn=False);states.clear()
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):planner._cast_value(enlarged,"bestow_curse",3,lambda state:(states.append(state),EKScore())[1])
        self.assertNotIn("enlarge_reduce",{state.concentration for state in states});self.assertIn("bestow_curse",{state.concentration for state in states})

    def test_spell_attack_hit_and_critical_double_only_attack_dice(self)->None:
        planner=self.planner(11,target=self.target(11));state=self.state(planner);spell=planner.spells["poison_spray"]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):hit=planner._cast_value(state,"poison_spray",0,lambda _:EKScore())
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,0.0,1.0)):critical=planner._cast_value(state,"poison_spray",0,lambda _:EKScore())
        self.assertAlmostEqual(hit.primary,19.5);self.assertAlmostEqual(critical.primary,39.0);self.assertTrue(spell["critical_dice"])

    def test_combat_prowess_converts_an_observed_spell_attack_miss_and_is_consumed(self)->None:
        planner=self.planner(20,target=self.target(20));state=replace(self.state(planner),prowess=True);seen=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):
            score=planner._cast_value(state,"poison_spray",0,lambda next_state:(seen.append(next_state),EKScore())[1])
        self.assertAlmostEqual(score.primary,26.0);self.assertIn(False,{next_state.prowess for next_state in seen})

    def test_combat_prowess_can_be_retained_for_the_more_valuable_true_strike(self)->None:
        planner=self.planner(20,target=self.target(20));state=replace(self.state(planner,actions=0),prowess=True)
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):
            optimized=planner._weapon_attack(state,False,lambda next_state:planner._weapon_attack(next_state,True,lambda _:EKScore()))
        true_strike=planner._weapon_damage(state,True,False);ordinary=planner._weapon_damage(state,False,False)
        self.assertEqual(optimized.primary,true_strike);self.assertGreater(true_strike,ordinary)

    def test_true_strike_chooses_only_the_base_weapon_packet_damage_type(self)->None:
        neutral=self.planner(target=self.target());slashing_immune=self.planner(target=self.target(damage_immunities=frozenset({"slashing"})));slashing_resistant=self.planner(target=self.target(damage_resistances=frozenset({"slashing"})));radiant_immune=self.planner(target=self.target(damage_immunities=frozenset({"radiant"})))
        neutral_damage=neutral._weapon_damage(self.state(neutral),True,False)
        self.assertEqual(neutral_damage,14.0)
        self.assertEqual(slashing_immune._weapon_damage(self.state(slashing_immune),True,False),14.0)
        self.assertEqual(slashing_resistant._weapon_damage(self.state(slashing_resistant),True,False),14.0)
        self.assertEqual(radiant_immune._weapon_damage(self.state(radiant_immune),True,False),10.5)

    def test_eldritch_strike_is_level_gated_and_repeat_saves_are_not_primed(self)->None:
        level_seven=self.planner(7);level_eleven=self.planner(11,target=self.target(11));seen_seven=[];seen_eleven=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            level_seven._weapon_attack(self.state(level_seven),False,lambda state:(seen_seven.append(state),EKScore())[1])
            level_eleven._weapon_attack(self.state(level_eleven),False,lambda state:(seen_eleven.append(state),EKScore())[1])
        self.assertFalse(level_seven.eldritch_strike_enabled);self.assertFalse(seen_seven[0].eldritch_strike)
        self.assertTrue(level_eleven.eldritch_strike_enabled);self.assertTrue(seen_eleven[0].eldritch_strike)
        gate_calls=[]
        def gate_probability(_target:Target,_ability:str,_dc:int,*,disadvantage:bool=False)->float:
            gate_calls.append(disadvantage);return 1.0
        with patch("harness.ek_damage_planner.modified_save_success_probability",side_effect=gate_probability):
            level_seven._save_success(level_seven.spells["acid_splash"],primer=level_seven._has_primer(seen_seven[0]))
            level_eleven._save_success(level_eleven.spells["acid_splash"],primer=level_eleven._has_primer(seen_eleven[0]))
        self.assertEqual(gate_calls,[False,True])
        primer_calls=[]
        def save_probability(_target:Target,_ability:str,_dc:int,*,disadvantage:bool=False)->float:
            primer_calls.append(disadvantage);return 1.0
        phantasmal=replace(self.state(self.planner(20,target=self.target(20)),actions=0),concentration="phantasmal_killer",eldritch_strike=True)
        repeat_planner=self.planner(20,target=self.target(20))
        with patch("harness.ek_damage_planner.modified_save_success_probability",side_effect=save_probability):repeat_planner._finish_turn(phantasmal)
        self.assertEqual(primer_calls,[False])

    def test_half_damage_uses_integer_halving_before_resistance(self)->None:
        planner=self.planner(target=self.target(damage_resistances=frozenset({"fire"})));packet={"count":1,"sides":4}
        self.assertEqual(planner._packet(packet,"fire",half=True),0.25)

    def test_magic_missile_is_automatic_and_upcasts_by_one_dart(self)->None:
        planner=self.planner();state=self.state(planner,slots=(1,1,0,0));seen=[]
        level_one=planner._cast_value(state,"magic_missile",1,lambda next_state:(seen.append(next_state),EKScore())[1]);level_two=planner._cast_value(state,"magic_missile",2,lambda _:EKScore())
        self.assertEqual(level_one.primary,10.5);self.assertEqual(level_two.primary,14.0);self.assertEqual(seen[0].slots,(0,1,0,0))

    def test_area_primary_and_aggregate_fireball_cluster_damage(self)->None:
        planner=self.planner(15,3,target=self.target(15));state=self.state(planner,slots=(0,0,1,0))
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):score=planner._cast_value(state,"fireball",3,lambda _:EKScore())
        self.assertEqual(score,EKScore(28.0,84.0))
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=1.0):half=planner._cast_value(state,"fireball",3,lambda _:EKScore())
        self.assertAlmostEqual(half.primary,13.75);self.assertAlmostEqual(half.aggregate,41.25)

    def test_chromatic_orb_uses_exact_duplicate_enumeration_and_fresh_leap_attack(self)->None:
        self.assertEqual(chromatic_orb_duplicate_probability(3),0.34375)
        planner=self.planner(cluster=3);state=self.state(planner,slots=(1,0,0,0))
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):score=planner._cast_value(state,"chromatic_orb",1,lambda _:EKScore())
        self.assertEqual(score.primary,13.5);self.assertAlmostEqual(score.aggregate,13.5*(1+0.34375),places=12)

    def test_witch_bolt_initial_miss_persists_for_later_bonus_action_packet(self)->None:
        planner=self.planner();state=self.state(planner,slots=(1,0,0,0));seen=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):score=planner._cast_value(state,"witch_bolt",1,lambda next_state:(seen.append(next_state),EKScore())[1])
        self.assertEqual(score,EKScore());self.assertEqual(seen[0].concentration,"witch_bolt_pending")
        self.assertEqual(planner._witch_repeat(replace(seen[0],actions_left=0,concentration="witch_bolt",bonus_available=True)),EKScore(6.5,6.5))

    def test_dragons_breath_self_cast_uses_stored_type_and_later_magic_action(self)->None:
        immune=frozenset({"acid","fire","lightning","poison","radiant","slashing","thunder"});target=self.target(damage_immunities=immune);planner=self.planner(cluster=3,actions=(2,),target=target);state=self.state(planner,actions=2,slots=(0,2,0,0),concentration="enlarge_reduce")
        active=planner._cast_dragons_breath(state,2)
        self.assertEqual(active.slots,(0,1,0,0));self.assertFalse(active.bonus_available);self.assertEqual((active.concentration,active.concentration_type),("dragons_breath:2","cold"))
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):activation=planner._dragons_breath(active);score=planner._turn(active)
        self.assertAlmostEqual(activation.primary,10.5);self.assertAlmostEqual(activation.aggregate,31.5)
        self.assertEqual(score,activation)

    def test_enlarge_and_bestow_curse_add_exact_weapon_hit_packets(self)->None:
        planner=self.planner(15,target=self.target(15));normal=self.state(planner);enlarge=replace(normal,concentration="enlarge_reduce");curse=replace(normal,concentration="bestow_curse")
        base=planner._weapon_damage(normal,False,False)
        critical_base=planner._weapon_damage(normal,False,True)
        self.assertEqual(planner._weapon_damage(enlarge,False,False)-base,2.5);self.assertEqual(planner._weapon_damage(curse,False,False)-base,4.5)
        self.assertEqual(planner._weapon_damage(curse,False,True)-critical_base,9.0)

    def test_enlarge_die_uses_true_strike_selected_weapon_damage_type(self)->None:
        planner=self.planner(15,target=self.target(15,damage_immunities=frozenset({"slashing"})));normal=self.state(planner);enlarge=replace(normal,concentration="enlarge_reduce")
        self.assertEqual(planner._weapon_damage(enlarge,False,False)-planner._weapon_damage(normal,False,False),0.0)
        self.assertEqual(planner._weapon_damage(enlarge,True,False)-planner._weapon_damage(normal,True,False),2.5)
        self.assertEqual(planner._weapon_damage(enlarge,True,True)-planner._weapon_damage(normal,True,True),5.0)

    def test_bestow_curse_uses_one_magic_missile_event_but_each_scorching_ray_hit(self)->None:
        planner=self.planner(20,target=self.target(20));curse=replace(self.state(planner,slots=(1,1,0,0)),concentration="bestow_curse")
        missiles=planner._cast_value(curse,"magic_missile",1,lambda _:EKScore())
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            rays=planner._cast_value(curse,"scorching_ray",2,lambda _:EKScore())
        self.assertEqual(missiles.primary,15.0);self.assertEqual(rays.primary,34.5)

    def test_melf_delayed_event_is_exact_and_uses_concentration_at_that_event(self)->None:
        planner=self.planner(20,target=self.target(20));state=self.state(planner,slots=(0,1,0,0));seen=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            initial=planner._cast_value(state,"melfs_acid_arrow",2,lambda next_state:(seen.append(next_state),EKScore())[1])
        self.assertEqual(initial.primary,10.0);self.assertEqual(len(seen[0].delayed_packets),1)
        self.assertEqual(planner._finish_turn(replace(seen[0],actions_left=0)).primary,5.0)
        self.assertEqual(planner._finish_turn(replace(seen[0],actions_left=0,concentration="bestow_curse")).primary,9.5)
        missed=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):
            miss=planner._cast_value(state,"melfs_acid_arrow",2,lambda next_state:(missed.append(next_state),EKScore())[1])
        self.assertEqual(miss.primary,4.75);self.assertIn((),{next_state.delayed_packets for next_state in missed})

    def test_melf_miss_applies_curse_only_when_half_acid_damages_target(self)->None:
        planner=self.planner(20,target=self.target(20));state=self.state(planner,slots=(0,1,0,0));curse=replace(state,concentration="bestow_curse");cursed_seen=[];uncursed_seen=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):
            cursed=planner._cast_value(curse,"melfs_acid_arrow",2,lambda next_state:(cursed_seen.append(next_state),EKScore())[1])
            uncursed=planner._cast_value(state,"melfs_acid_arrow",2,lambda next_state:(uncursed_seen.append(next_state),EKScore())[1])
        immune=self.planner(20,target=self.target(20,damage_immunities=frozenset({"acid"})));immune_seen=[]
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(1.0,0.0,0.0)):
            negated=immune._cast_value(replace(self.state(immune,slots=(0,1,0,0)),concentration="bestow_curse"),"melfs_acid_arrow",2,lambda next_state:(immune_seen.append(next_state),EKScore())[1])
        self.assertEqual(cursed.primary,9.25);self.assertEqual(uncursed.primary,4.75);self.assertEqual(negated.primary,0.0)
        for seen in (cursed_seen,uncursed_seen,immune_seen):self.assertIn((),{next_state.delayed_packets for next_state in seen})

    def test_vitriolic_sphere_failure_schedules_exact_delayed_event(self)->None:
        planner=self.planner(20,target=self.target(20));state=replace(self.state(planner,slots=(0,0,0,1)),concentration="bestow_curse");seen=[]
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):
            initial=planner._cast_value(state,"vitriolic_sphere",4,lambda next_state:(seen.append(next_state),EKScore())[1])
        self.assertEqual(initial.primary,29.5);self.assertEqual(len(seen[0].delayed_packets),1)
        self.assertEqual(planner._finish_turn(replace(seen[0],actions_left=0)).primary,17.0)

    def test_conjure_minor_elementals_augments_only_maintained_weapon_hits(self)->None:
        planner=self.planner(20,target=self.target(20));normal=self.state(planner);active=replace(normal,concentration="conjure_minor_elementals",concentration_type="cold")
        self.assertEqual(planner._weapon_damage(active,False,False)-planner._weapon_damage(normal,False,False),9.0)
        self.assertEqual(planner._weapon_damage(active,True,True)-planner._weapon_damage(normal,True,True),18.0)

    def test_greater_invisibility_cast_drives_melee_and_ranged_attack_advantage(self)->None:
        def active(planner:EKDamagePlanner)->EKState:
            seen=[];initial=self.state(planner,slots=(0,0,0,1))
            planner._cast_value(initial,"greater_invisibility",4,lambda state:(seen.append(state),EKScore())[1])
            self.assertEqual(seen[0].slots,(0,0,0,0));self.assertEqual(seen[0].concentration,"greater_invisibility")
            return replace(seen[0],slots=(1,1,0,0),slotted_spell_cast_this_turn=False)
        probabilities=lambda _bonus,_ac,advantage=False:(0.0,1.0,0.0) if advantage else (1.0,0.0,0.0)
        ordinary=self.planner(20,target=self.target(20));blind=self.planner(20,target=self.target(20,blindsight_range=1));true=self.planner(20,target=self.target(20,truesight_range=1))
        ordinary_state=active(ordinary);blind_state=active(blind);true_state=active(true)
        self.assertTrue(ordinary._melee_invisibility_advantage(ordinary_state));self.assertTrue(blind._melee_invisibility_advantage(blind_state));self.assertTrue(true._melee_invisibility_advantage(true_state))
        for spell_id,slot in (("poison_spray",0),("chromatic_orb",1),("witch_bolt",1),("scorching_ray",2),("melfs_acid_arrow",2)):
            with self.subTest(spell=spell_id),patch("harness.ek_damage_planner.attack_probabilities",side_effect=probabilities):
                unobscured=ordinary._cast_value(ordinary_state,spell_id,slot,lambda _:EKScore())
                blindsighted=blind._cast_value(blind_state,spell_id,slot,lambda _:EKScore())
                truesighted=true._cast_value(true_state,spell_id,slot,lambda _:EKScore())
            self.assertGreater(unobscured.primary,blindsighted.primary);self.assertEqual(blindsighted,truesighted)
        self.assertEqual(ordinary._cast_value(ordinary_state,"magic_missile",1,lambda _:EKScore()),EKScore(10.5,10.5))
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):
            self.assertEqual(ordinary._cast_value(ordinary_state,"acid_splash",0,lambda _:EKScore()),ordinary._cast_value(replace(ordinary_state,concentration=""),"acid_splash",0,lambda _:EKScore()))

    def test_conjure_minor_elementals_does_not_augment_ranged_spell_attacks(self)->None:
        planner=self.planner(20,target=self.target(20));normal=self.state(planner);active=replace(normal,concentration="conjure_minor_elementals",concentration_type="cold")
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)):
            normal_score=planner._cast_value(normal,"poison_spray",0,lambda _:EKScore());active_score=planner._cast_value(active,"poison_spray",0,lambda _:EKScore())
        self.assertEqual(active_score,normal_score)

    def test_phantasmal_killer_initial_and_repeat_failed_saves_are_distinct_packets(self)->None:
        planner=self.planner(20,target=self.target(20));state=self.state(planner,slots=(0,0,0,1))
        with patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):initial=planner._cast_value(state,"phantasmal_killer",4,lambda _:EKScore());repeat=planner._finish_turn(replace(state,actions_left=0,concentration="phantasmal_killer"))
        self.assertAlmostEqual(initial.primary,22.0);self.assertAlmostEqual(repeat.primary,22.0)

    def test_damage_defenses_and_empty_slot_pool_fail_closed(self)->None:
        resistant=self.planner(target=self.target(damage_resistances=frozenset({"force"})));immune=self.planner(target=self.target(damage_immunities=frozenset({"force"})));vulnerable=self.planner(target=self.target(damage_vulnerabilities=frozenset({"force"})));packet={"count":1,"sides":4,"flat":1}
        self.assertEqual(resistant._packet(packet,"force"),1.5);self.assertEqual(immune._packet(packet,"force"),0.0);self.assertEqual(vulnerable._packet(packet,"force"),7.0)
        self.assertEqual(resistant._slot_options(self.state(resistant),resistant.spells["magic_missile"]),())

    def test_diagnostic_and_exclude_spells_cannot_enter_the_nominal_planner(self)->None:
        for disposition in ("diagnostic","exclude"):
            with self.subTest(disposition=disposition):
                changed=deepcopy(self.comparators);changed["damage"]["eldritch_knight"]["spells"][0]["disposition"]=disposition
                with tempfile.TemporaryDirectory() as directory:
                    path=Path(directory)/"comparators.json";path.write_text(json.dumps(changed),encoding="utf-8")
                    with self.assertRaisesRegex(ValueError,"source scope or disposition"):load_comparators(path)

    def test_true_strike_is_available_but_not_forced_and_objectives_choose_independently(self)->None:
        target=self.target(damage_immunities=frozenset({"radiant"}),saves={"strength":20,"dexterity":20,"constitution":20,"intelligence":20,"wisdom":20,"charisma":20});single=self.planner(target=target);cluster=self.planner(cluster=3,target=self.target())
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=1.0):single_score=single.solve();ordinary=2*single._weapon_damage(self.state(single),False,False)
        self.assertEqual(single_score.primary,ordinary)
        with patch("harness.ek_damage_planner.attack_probabilities",return_value=(0.0,1.0,0.0)),patch("harness.ek_damage_planner.modified_save_success_probability",return_value=0.0):cluster_score=cluster.solve()
        self.assertEqual(cluster_score.primary,26.5);self.assertEqual(cluster_score.aggregate,40.5)


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

    def ek_damage_signature(self,comparators:dict[str,object],level:int,damage_immunity:str|None=None)->tuple[object,...]:
        target=replace(self.target(level,damage_immunity=damage_immunity),magic_resistance=False,saves={"strength":8,"dexterity":-2,"constitution":5,"intelligence":1,"wisdom":3,"charisma":0},blindsight_range=0,truesight_range=0);progression=deepcopy(self.config["fighter_progression"][str(level)])
        row=comparators["damage"]["eldritch_knight"]  # type: ignore[index]
        planner=EKDamagePlanner(row,target,progression,self.model.progression("proficiency_bonus",level),6,(1,));state=EKState(0,0,False,False,(1,1,1,1),True)
        def continuation(next_state:EKState)->EKScore:
            value=planner._weapon_damage(next_state,False,False)+sum((index+1)*count for index,count in enumerate(next_state.slots))
            if next_state.concentration in {"witch_bolt","witch_bolt_pending"}:value+=planner._packet(planner.spells["witch_bolt"]["repeat_damage"],"lightning")
            value+=float(planner._melee_invisibility_advantage(next_state))
            return EKScore(value,value)+planner._finish_turn(replace(next_state,actions_left=0))
        signature:list[object]=[planner.regular_attack_bonus,planner.true_strike_attack_bonus,planner.spell_attack_bonus,planner.spell_save_dc,planner.eldritch_strike_enabled,planner._weapon_damage(state,False,False),planner._weapon_damage(state,False,True)]
        for spell_id in (*planner.cantrips,*planner.prepared):
            spell=planner.spells[spell_id];types=tuple(planner._profile(damage_type,17) for damage_type in spell.get("damage_types",[]));minimum=int(spell["spell_level"])
            if spell_id=="dragons_breath":
                packets=[]
                for slot in range(2,5):
                    packet=planner._spell_packet(spell,slot);packets.append(planner._save_area_score(state,spell,packet,planner._best_damage_type(spell["damage_types"]))[0])
                signature.append((spell_id,types,tuple(packets)));continue
            slots=(0,) if minimum==0 else tuple(dict.fromkeys((minimum,4)))
            values=[]
            for slot in slots:values.append(planner._cast_value(state,spell_id,slot,continuation))
            signature.append((spell_id,types,tuple(values)))
        planner.clear();return tuple(signature)

    def test_every_damage_comparator_leaf_is_numerically_live(self)->None:
        baselines:dict[tuple[str,int,str|None],float]={};ek_outcomes:Counter[str]=Counter();ek_leaf_count=0
        for path in _leaf_paths(self.comparators["damage"],("damage",)):
            build=str(path[1]);field=str(path[-1]);current=_path_value(self.comparators,path)
            level=next((int(part) for part in path if isinstance(part,str) and part in {"7","11","15","20"}),20)
            damage_immunity=None
            if build=="eldritch_knight":
                ek_leaf_count+=1
                if "damage_types" in path:
                    configured=set(_path_value(self.comparators,path[:path.index("damage_types")+1]));replacement=next(item for item in ("acid","cold","fire","force","lightning","necrotic","poison","psychic","radiant","thunder") if item not in configured);damage_immunity=replacement
                elif field=="weapon_damage_type_choice":replacement=not current;damage_immunity="slashing"
                elif field=="eldritch_strike_minimum_level":replacement=12;level=11
                elif field=="damage_type":replacement="fire" if current!="fire" else "cold";damage_immunity=replacement
                elif isinstance(current,bool):replacement=not current
                elif isinstance(current,int):replacement=current+1
                elif isinstance(current,str):replacement=("wisdom" if current!="wisdom" else "dexterity") if field=="save" else f"{current}_unsupported"
                else:raise AssertionError(f"No EK damage semantic mutation for {_path_label(path)}")
                changed=deepcopy(self.comparators);_set_path(changed,path,replacement)
                with tempfile.TemporaryDirectory() as directory:
                    comparator_path=Path(directory)/"comparators.json";comparator_path.write_text(json.dumps(changed),encoding="utf-8")
                    try:validated=load_comparators(comparator_path)
                    except ValueError:
                        ek_outcomes["validation_rejected"]+=1
                        continue
                target_level=level if level in {7,11,15,20} else 20
                if len(path)>3 and path[2]=="spells":
                    spell_id=self.comparators["damage"]["eldritch_knight"]["spells"][int(path[3])]["id"]
                    if "damage_dice_by_level" in path:target_level=int(path[path.index("damage_dice_by_level")+1])
                    else:target_level=next(candidate for candidate in (7,11,15,20) if spell_id in self.comparators["damage"]["eldritch_knight"]["cantrips_by_level"][str(candidate)] or spell_id in self.comparators["damage"]["eldritch_knight"]["prepared_spells_by_level"][str(candidate)])
                with self.subTest(path=_path_label(path)):
                    self.assertNotEqual(self.ek_damage_signature(validated,target_level,damage_immunity),self.ek_damage_signature(self.comparators,target_level,damage_immunity))
                ek_outcomes["observable"]+=1
                continue
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
        self.assertEqual(ek_leaf_count,387)
        self.assertEqual(ek_outcomes,Counter({"validation_rejected":272,"observable":115}))

    def control_mutation(self,path:tuple[object,...],current:object)->object:
        build=str(path[1]);row_field=str(path[2]);field=str(path[-2]) if isinstance(path[-1],int) else str(path[-1])
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
        return json.dumps({"evaluations":results},sort_keys=True)

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
        self.assertEqual(outcomes,Counter({"observable":947,"validation_rejected":453,"evaluation_rejected":6}))
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
        planner=_KVDamagePlanner(self.model,target,packages,riders,(("normal",(0.0,1.0,2.0)),),((),),0,attacks_per_action,(1,),True,True,0,0,self.mastery,0,1,None);self.addCleanup(planner.clear);return planner

    def test_combat_prowess_hit_instead_does_not_establish_studied(self)->None:
        planner=self.planner(1);package_index=1
        result=planner._resolve_attack_roll(0,0,0,0,False,package_index,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:5],("prowess",False,False,False,0))

    def test_combat_prowess_can_be_retained_for_a_more_valuable_later_attack(self)->None:
        planner=self.planner(2)
        result=planner._resolve_attack_roll(0,0,1,0,False,0,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:5],("miss",True,False,True,0))
        self.assertAlmostEqual(result.score.aggregate,101.0975,places=12)

    def test_studied_expires_after_a_zero_attack_turn(self)->None:
        planner=self.planner(1)
        result=planner._actions(0,0,True,True,0,0,0,0,2,False,0,False)
        self.assertEqual(result.choice,("end_turn",False))

    def test_standalone_consumes_one_slot_and_remains_capped_during_action_surge(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());package=Package(None,0,0,0);standalone=Standalone("forked_lightning",0,0,0,100.0,100.0,False)
        planner=_KVDamagePlanner(self.model,target,(package,),{package:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((standalone,),),0,1,(2,),False,False,0,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,100.0,places=12)
        self.assertEqual(planner.selection().count("forked_lightning:T0"),1)

    def test_pre_roll_rider_cost_is_spent_on_a_miss_without_outcome_lookahead(self)->None:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,1,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,1,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,5.0,places=12)

    def test_mastery_activates_only_on_first_overload_and_then_covers_the_turn(self)->None:
        planner=self.planner(1)
        self.assertEqual(planner._payment_options(0,1,0),((0,1,0,False),))
        self.assertIn((3,0,1,True),planner._payment_options(6,1,0))
        self.assertEqual(planner._payment_options(12,0,1),((6,0,1,False),))
        self.assertEqual(planner._payment_options(12,1,2),((12,1,2,False),))

    def test_tier_two_allowance_resets_for_a_new_attack_action(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,1,(2,),False,False,0,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T2"),2)

    def test_psionic_apex_covers_each_actual_attack_action_during_action_surge(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,12);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,1,(2,),False,False,0,12,self.mastery,1,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        selection=planner.selection();self.assertEqual(selection.count("branching_bolt:T2"),2);self.assertEqual(selection.count(";mastery"),1)

    def test_same_paid_rider_can_be_selected_on_all_three_manifested_strikes(self)->None:
        target=replace(next(item for item in load_targets(profile="headline",levels={11}) if item.name=="Deva"),ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,2,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,3,(1,),False,False,6,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,285.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T0"),3)

    def test_miss_spends_cost_and_same_rider_remains_legal_on_next_strike(self)->None:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",0,1,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,2,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,10.0,places=12)

    def test_repeated_overload_pays_blood_tax_for_each_declaration(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",1,0,4);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,0,8,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T1"),2)

    def test_tier_two_remains_one_declaration_per_attack_action(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,3,(1,),False,False,0,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,95.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T2"),1)

    def test_repeated_thermal_fracture_uses_max_or_refresh_not_addition(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());thermal=Package("thermal_fracture",0,0,0)
        planner=_KVDamagePlanner(self.model,target,(thermal,),{thermal:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((),),0,2,(1,),False,False,0,0,self.mastery,0,1,None);self.addCleanup(planner.clear)
        self.assertEqual(planner._roll_options(0,0,"hit",False,False,1)[0][4],1)

    def test_refined_holdout_uses_1d6_plus_full_modifier_and_full_graze(self)->None:
        target=replace(self.base,damage_resistances=frozenset(),damage_immunities=frozenset({"fire"}),damage_vulnerabilities=frozenset())
        before=_strike_packet_options(self.model,replace(target,level=17),"pyrokinesis",17,5,12)
        refined=_strike_packet_options(self.model,target,"pyrokinesis",20,5,12)
        self.assertEqual(before[0][0],"holdout");self.assertEqual(before[0][1][0],2.0)
        self.assertEqual(refined,(('holdout',(5.0,8.5,12.0)),))

    def test_psychokinesis_apex_packet_is_once_per_attack_action_and_action_surge_refreshes_it(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());package=Package(None,0,0,0);packet=_psionic_apex_packet(self.model,target,"psychokinesis",20)
        planner=_KVDamagePlanner(self.model,target,(package,),{package:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((),),0,4,(2,),False,False,0,0,self.mastery,0,1,packet);self.addCleanup(planner.clear)
        once=packet*(1-0.05**4)
        self.assertAlmostEqual(planner.solve().primary,2*once,places=12)
        hit=planner._roll_options(0,0,"hit",True,False,0)[0];critical=planner._roll_options(0,0,"critical",True,False,0)[0]
        self.assertFalse(hit[2]);self.assertEqual(hit[-2:],critical[-2:]);self.assertEqual(hit[-1],packet)
        immune=replace(target,damage_immunities=frozenset({"force"}));immune_packet=_psionic_apex_packet(self.model,immune,"psychokinesis",20);self.assertEqual(immune_packet,0.0)
        immune_planner=_KVDamagePlanner(self.model,immune,(package,),{package:(0.0,0.0)},(("normal",(0.0,0.0,0.0)),),((),),0,1,(1,),False,False,0,0,self.mastery,0,1,immune_packet);self.addCleanup(immune_planner.clear)
        immune_hit=immune_planner._roll_options(0,0,"hit",True,False,0)[0];self.assertFalse(immune_hit[2]);self.assertEqual(immune_hit[-1],0.0)

    def test_area_damage_tiers_preserve_primary_and_reduce_only_approved_packets(self)->None:
        electron=next(item for item in self.model.features["electron_burst"]["damage_tiers"] if int(item["tier"])==2)
        self.assertEqual((electron["damage"]["count"],electron["secondary_damage"]["count"]),(4,3))
        arctic=[int(item["damage"]["count"]) for item in self.model.features["arctic_tempest"]["damage_tiers"]]
        self.assertEqual(arctic,[8,9,10])

    def test_observed_state_policy_matches_current_l20_sentinel(self)->None:
        target=next(item for item in load_targets(profile="headline",levels={20}) if item.name=="Ancient White Dragon")
        primary,aggregate,selection,_schedule=_kv_dpr(self.model,self.config,target,"electrokinesis",3)
        self.assertAlmostEqual(primary,116.29434009056969,places=10)
        self.assertAlmostEqual(aggregate,171.23091363060868,places=10)
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

    def level_target(self,level:int,*,size:str="medium")->Target:
        target=next(item for item in load_targets(profile="headline",levels={level}) if not item.condition_immunities)
        return replace(target,size=size)

    def expected_mastery_retry(self,level:int,target:Target)->float:
        profile=self.config["kv_profile"];bonus=self.model.kv_attack_bonus(level,int(profile["psionic_ability_modifier"]))+int(profile["archery_attack_bonus"]);hit=sum(attack_probabilities(bonus,target.ac)[1:]);attacks=int(self.config["fighter_progression"][str(level)]["attacks_per_action"])
        return 100*(1-(1-hit)**attacks)

    def test_unconstrained_attack_action_retry_matches_closed_form(self)->None:
        for attacks,probability in ((0,0.42),(1,0.42),(3,0.42),(4,0.0),(4,1.0)):
            with self.subTest(attacks=attacks,probability=probability):
                self.assertAlmostEqual(_attack_action_retry_probability(attacks,probability),1-(1-probability)**attacks,places=12)

    def test_kv_retry_resource_projection_uses_authority_and_benchmark_inputs(self)->None:
        resources=[_kv_retry_resources(self.model,self.config,level) for level in (7,11,15,20)]
        self.assertEqual([row["attacks_per_action"] for row in resources],[2,3,3,4])
        for row in resources:
            level=row["level"];profile=self.config["kv_profile"]
            hp=int(profile["hit_point_model"]["first_level_base"])+int(profile["constitution_modifier"])+(level-1)*(int(profile["hit_point_model"]["later_level_average"])+int(profile["constitution_modifier"]))
            self.assertEqual(row["psi_pool"],self.model.progression("psi_points",level))
            self.assertEqual((row["benchmark_hp"],row["blood_tax_budget"]),(hp,int(hp*float(profile["blood_tax_hp_fraction"]))))
            self.assertEqual(row["blood_tax_by_tier"],tuple(self.model.blood_tax(level,tier) for tier in (0,1,2)))
            self.assertEqual(row["tier_two_limit"],self.model.projection["core"]["overload"]["tier_two_limit_per_attack_action"])
        self.assertEqual([row["overload_mastery_uses"] for row in resources],[0,0,0,1])

    def test_delivery_recipe_metadata_keeps_mastery_and_rider_separate(self)->None:
        target=self.level_target(20)
        mastery=_mastery_scenario(self.model,self.config,target,"electrokinesis")
        rider=_catalog_rider_scenario(self.model,self.config,target,"cryokinesis","snow_chains",0)
        automatic=_delivery_recipe("single_activation_automatic","automatic","single_activation")
        self.assertEqual(mastery["delivery_recipe"]["id"],"mastery_attack_action_hit_retry")
        self.assertEqual(rider["delivery_recipe"],rider["rider_delivery_recipe"])
        self.assertEqual(rider["delivery_recipe"]["id"],"kv_attack_action_hit_retry")
        self.assertEqual(rider["delivery_recipe"]["gate"],"hit")
        self.assertEqual(rider["delivery_recipe"]["save_ability"],"constitution")
        self.assertEqual(rider["delivery_recipe"]["additional_control_gate"],"failed_save")
        self.assertEqual(automatic["id"],"single_activation_automatic")
        with self.assertRaisesRegex(ValueError,"Unknown delivery recipe ID"):
            _delivery_recipe("unknown","automatic","single_activation")

    def test_mixed_gate_recipes_follow_exact_effect_gates(self)->None:
        sentinels=(
            ("cryokinesis","glacial_spike",1,7,"constitution"),
            ("cryokinesis","glacial_spike",2,11,"constitution"),
            ("cryokinesis","snow_chains",0,7,"constitution"),
            ("cryokinesis","snow_chains",1,7,"constitution"),
            ("cryokinesis","snow_chains",2,11,"constitution"),
        )
        for discipline,entity,tier,level,save in sentinels:
            with self.subTest(entity=entity,tier=tier):
                row=_catalog_rider_scenario(self.model,self.config,self.level_target(level),discipline,entity,tier)
                recipe=row["delivery_recipe"]
                self.assertEqual((recipe["id"],recipe["gate"],recipe["save_ability"],recipe["additional_control_gate"]),("kv_attack_action_hit_retry","hit",save,"failed_save"))
                self.assertNotEqual(recipe["gate"],"hit_and_failed_save")
                feature=self.model.features[entity];expected=100*_repeat_rider_probability(self.model,self.config,level,tier,int(feature["psi_cost"]),row["reach"]/100)
                self.assertAlmostEqual(row["whole"],expected,places=12)
        glacial_zero=_catalog_rider_scenario(self.model,self.config,self.level_target(7),"cryokinesis","glacial_spike",0)["delivery_recipe"]
        self.assertEqual((glacial_zero["id"],glacial_zero["gate"],glacial_zero["save_ability"],glacial_zero["additional_control_gate"]),("kv_attack_action_hit_retry","hit","",""))

    def test_standalone_mixed_gate_recipes_are_automatic_initial_delivery(self)->None:
        target=self.level_target(20)
        for discipline,entity,save in (("cryokinesis","absolute_zero","constitution"),("psychokinesis","telekinetic_slam","strength")):
            with self.subTest(entity=entity):
                row=_catalog_rider_scenario(self.model,self.config,target,discipline,entity,2);recipe=row["delivery_recipe"]
                self.assertEqual((recipe["id"],recipe["gate"],recipe["retry_model"],recipe["save_ability"],recipe["additional_control_gate"]),("single_activation_automatic","automatic","single_activation",save,"failed_save"))
                self.assertAlmostEqual(row["whole"],100.0)

    def test_pure_save_recipe_families_remain_unchanged(self)->None:
        target=self.level_target(20)
        frozen=_catalog_rider_scenario(self.model,self.config,target,"cryokinesis","frozen_ground",0)["delivery_recipe"]
        self.assertEqual((frozen["id"],frozen["gate"],frozen["save_ability"],frozen["additional_control_gate"]),("single_activation_failed_save","failed_save","constitution",""))
        for discipline,entity,save in (("pyrokinesis","flare","dexterity"),("electrokinesis","electron_burst","charisma")):
            with self.subTest(entity=entity):
                recipe=_catalog_rider_scenario(self.model,self.config,target,discipline,entity,2)["delivery_recipe"]
                self.assertEqual((recipe["id"],recipe["gate"],recipe["save_ability"],recipe["additional_control_gate"]),("kv_attack_action_hit_failed_save_retry","hit_and_failed_save",save,""))

    def test_delivery_recipe_target_role_filtering_and_malformed_gates_fail_closed(self)->None:
        control={"application":"failed_save","hit_gated":True,"save":"constitution","effects":[
            {"target_role":"primary","gate":"on_reach","outcomes":["speed_zero"]},
            {"target_role":"primary","gate":"on_failed_save","conditions":["restrained"]},
            {"target_role":"secondary","gate":"on_failed_save","conditions":["restrained"]},
        ]}
        primary=_kv_rider_delivery_recipe(control,True,"primary");secondary=_kv_rider_delivery_recipe(control,True,"secondary")
        self.assertEqual((primary["gate"],primary["additional_control_gate"]),("hit","failed_save"))
        self.assertEqual((secondary["gate"],secondary["additional_control_gate"]),("hit_and_failed_save",""))
        malformed=(
            ({**control,"effects":[{"gate":"after_damage","outcomes":["speed_zero"]}]},"Unsupported KV delivery effect gate"),
            ({**control,"effects":[{"target_role":"secondary","gate":"on_reach","outcomes":["speed_zero"]}]},"no applicable modeled control effect"),
            ({**control,"save":"","effects":[{"gate":"on_failed_save","conditions":["restrained"]}]},"lacks a save ability"),
            ({**control,"application":"no_save","effects":[{"gate":"on_failed_save","conditions":["restrained"]}]},"application disagrees"),
        )
        for candidate,message in malformed:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):_kv_rider_delivery_recipe(candidate,True,"primary")

    def test_catalog_initial_delivery_is_not_repeat_save_persistence(self)->None:
        target=next(item for item in load_targets(profile="headline",levels={20}) if item.name=="Lich")
        package=_kv_scenario(self.model,self.config,target,"psychokinesis","mass_levitation",0)
        catalog=_catalog_rider_scenario(self.model,self.config,target,"psychokinesis","mass_levitation",0)
        self.assertAlmostEqual(package["whole"],90.0)
        self.assertAlmostEqual(package["after_repeats"],72.9)
        self.assertAlmostEqual(catalog["whole"],package["whole"])
        self.assertAlmostEqual(catalog["after_repeats"],package["whole"])
        self.assertNotEqual(package["whole"],package["after_repeats"])

    def test_catalog_effectiveness_distinguishes_structural_full_partial_and_nullified(self)->None:
        target=self.target();outcome={"outcomes":["speed_zero"]};condition={"conditions":["restrained"]}
        size=_catalog_effectiveness(replace(target,size="huge"),[outcome],"primary",maximum_size="large")
        creature_type=_catalog_effectiveness(replace(target,creature_type="monstrosity"),[outcome],"primary",required_creature_type="humanoid")
        nullified=_catalog_effectiveness(self.target("restrained"),[condition],"primary")
        partial=_catalog_effectiveness(self.target("restrained"),[condition,outcome],"primary")
        effective=_catalog_effectiveness(target,[condition,outcome],"primary")
        self.assertEqual((size["status"],size["effective"],size["reasons"]),(INEFFECTIVE_STRUCTURAL,False,["exceeds_maximum_size:large"]))
        self.assertEqual((creature_type["status"],creature_type["effective"],creature_type["reasons"]),(INEFFECTIVE_STRUCTURAL,False,["requires_creature_type:humanoid"]))
        self.assertEqual((nullified["status"],nullified["effective"],nullified["surviving"],nullified["reasons"]),(INEFFECTIVE_NULLIFIED,False,[],["immune_condition:restrained"]))
        self.assertEqual((partial["status"],partial["effective"]),(PARTIALLY_EFFECTIVE,True));self.assertEqual(partial["surviving"],["outcome:speed_zero"])
        self.assertEqual((effective["status"],effective["effective"],effective["reasons"]),(EFFECTIVE,True,[]))

    def test_catalog_effectiveness_uses_dependencies_but_not_pricing_or_cu(self)->None:
        unpriced={"outcomes":["forced_movement"],"pricing_status":"unsupported"}
        self.assertEqual(_catalog_effectiveness(self.target(),[unpriced],"primary")["status"],EFFECTIVE)
        dependent={"outcomes":["reaction_denial"],"requires_condition":"restrained"}
        result=_catalog_effectiveness(self.target("restrained"),[dependent],"primary")
        self.assertEqual((result["status"],result["reasons"]),(INEFFECTIVE_NULLIFIED,["dependency_condition_immune:restrained"]))

    def test_air_elemental_snow_chains_is_partial_and_mastery_does_not_rescue_rider(self)->None:
        target=next(item for item in load_targets(profile="headline",levels={7}) if item.name=="Air Elemental")
        self.assertIn("restrained",target.condition_immunities)
        for tier,expected_survivors in ((0,["outcome:speed_zero"]),(1,["outcome:speed_zero","outcome:reaction_denial"])):
            with self.subTest(tier=tier):
                rider=_catalog_rider_scenario(self.model,self.config,target,"cryokinesis","snow_chains",tier)
                evidence=rider["effectiveness"]
                self.assertTrue(rider["eligible"]);self.assertEqual(evidence["status"],PARTIALLY_EFFECTIVE);self.assertTrue(evidence["effective"])
                self.assertEqual(evidence["reasons"],["immune_condition:restrained"]);self.assertEqual(evidence["surviving"],expected_survivors)
                self.assertNotIn("outcome:speed_reduction",evidence["declared"]);self.assertGreater(rider["whole"],0.0)

    def test_purple_worm_flare_uses_unchanged_source_facts(self)->None:
        target=next(item for item in load_targets(profile="headline",levels={15}) if item.name=="Purple Worm")
        self.assertNotIn("blinded",target.condition_immunities)
        rider=_catalog_rider_scenario(self.model,self.config,target,"pyrokinesis","flare",0)
        self.assertEqual((rider["eligible"],rider["effectiveness"]["status"]),(True,EFFECTIVE));self.assertGreater(rider["whole"],0.0)

    def test_bare_sap_mastery_uses_every_ordinary_attack_without_action_surge(self)->None:
        for level,attacks in ((7,2),(11,3),(15,3),(20,4)):
            with self.subTest(level=level):
                target=self.level_target(level);row=_mastery_scenario(self.model,self.config,target,"electrokinesis");profile=self.config["kv_profile"];bonus=self.model.kv_attack_bonus(level,int(profile["psionic_ability_modifier"]))+int(profile["archery_attack_bonus"]);hit=sum(attack_probabilities(bonus,target.ac)[1:])
                self.assertEqual(self.config["fighter_progression"][str(level)]["attacks_per_action"],attacks)
                self.assertAlmostEqual(row["whole"],100*(1-(1-hit)**attacks),places=12)
                self.assertNotAlmostEqual(row["whole"],100*(1-(1-hit)**(2*attacks)),places=12)

    def test_bare_push_mastery_uses_ordinary_retries_and_preserves_size_restriction(self)->None:
        for level in (7,11,15,20):
            with self.subTest(level=level):
                eligible=self.level_target(level);row=_mastery_scenario(self.model,self.config,eligible,"psychokinesis")
                self.assertAlmostEqual(row["whole"],self.expected_mastery_retry(level,eligible),places=12)
                excluded=_mastery_scenario(self.model,self.config,self.level_target(level,size="huge"),"psychokinesis")
                self.assertFalse(excluded["eligible"]);self.assertEqual(excluded["whole"],0.0)

    def test_bare_slow_mastery_uses_ordinary_retries_at_every_maintained_level(self)->None:
        for level in (7,11,15,20):
            with self.subTest(level=level):
                target=self.level_target(level,size="gargantuan");row=_mastery_scenario(self.model,self.config,target,"cryokinesis")
                self.assertTrue(row["eligible"]);self.assertAlmostEqual(row["whole"],self.expected_mastery_retry(level,target),places=12)

    def test_embedded_and_bare_mastery_share_retry_probability_when_gates_match(self)->None:
        for level in (7,11,15,20):
            with self.subTest(level=level):
                target=self.level_target(level);bare=_mastery_scenario(self.model,self.config,target,"cryokinesis");embedded=_kv_scenario(self.model,self.config,target,"cryokinesis","snow_chains",0)
                self.assertAlmostEqual(embedded["mastery"],bare["mastery"],places=12)

    def test_standalone_control_remains_one_use(self)->None:
        target=self.level_target(15);row=_kv_scenario(self.model,self.config,target,"psychokinesis","telekinetic_slam",1);failed=1-save_success_probability(target,"strength",self.model.kv_save_dc(15,5));attacks=int(self.config["fighter_progression"]["15"]["attacks_per_action"])
        self.assertAlmostEqual(row["whole"],100*failed,places=12)
        self.assertNotAlmostEqual(row["whole"],100*(1-(1-failed)**attacks),places=12)

    def test_flare_named_condition_uses_the_same_dexterity_save_at_every_tier(self)->None:
        target=self.level_target(15);feature=self.model.features["flare"];bonus=self.model.kv_attack_bonus(15,5)+int(self.config["kv_profile"]["archery_attack_bonus"]);hit=sum(attack_probabilities(bonus,target.ac)[1:]);failed=1-save_success_probability(target,"dexterity",self.model.kv_save_dc(15,5))
        self.assertEqual([(tier["damage"]["count"],tier["damage"]["sides"],tier["damage"]["resolution"],tier["save"]) for tier in feature["damage_tiers"]],[(3,10,"always","dexterity"),(4,10,"always","dexterity"),(5,10,"always","dexterity")]);self.assertEqual(feature["ignore_resistance_tiers"],[2]);self.assertEqual(feature["psi_cost"],3)
        for tier in range(3):
            with self.subTest(tier=tier):
                control=next(item for item in feature["control_tiers"] if int(item["tier"])==tier);self.assertEqual((control["application"],control["save"]),("failed_save","dexterity"));self.assertTrue(all(effect["gate"]=="on_failed_save" for effect in control["effects"]))
                expected=_repeat_rider_probability(self.model,self.config,15,tier,int(feature["psi_cost"]),hit*failed);row=_kv_scenario(self.model,self.config,target,"pyrokinesis","flare",tier)
                self.assertAlmostEqual(row["named"],100*expected,places=12);self.assertAlmostEqual(row["shadow_components"][0]["application_probability"],expected,places=12)

    def test_mind_lock_uses_one_intelligence_save_for_its_full_condition_package(self)->None:
        target=self.target();feature=self.model.features["advanced_mind_lock"];bonus=self.model.kv_attack_bonus(20,5)+int(self.config["kv_profile"]["archery_attack_bonus"]);hit=sum(attack_probabilities(bonus,target.ac)[1:]);failed=1-save_success_probability(target,"intelligence",self.model.kv_save_dc(20,5));expected_conditions=(("blinded",),("blinded","incapacitated"),("blinded","stunned"))
        self.assertTrue(all(tier["damage"]["kind"]=="none" and tier["damage"]["resolution"]=="always" and tier["save"]=="intelligence" for tier in feature["damage_tiers"]))
        for tier,conditions in enumerate(expected_conditions):
            with self.subTest(tier=tier):
                control=next(item for item in feature["control_tiers"] if int(item["tier"])==tier);self.assertEqual((control["application"],control["save"]),("failed_save","intelligence"));self.assertEqual(len(control["effects"]),1);self.assertEqual(tuple(control["effects"][0]["conditions"]),conditions);self.assertEqual(control["effects"][0]["gate"],"on_failed_save")
                expected=_repeat_rider_probability(self.model,self.config,20,tier,int(feature["psi_cost"]),hit*failed);row=_kv_scenario(self.model,self.config,target,"pyrokinesis","advanced_mind_lock",tier);component=row["shadow_components"][0]
                self.assertAlmostEqual(row["named"],100*expected,places=12);self.assertAlmostEqual(component["application_probability"],expected,places=12);self.assertEqual(tuple(label for kind,label in component["labels"] if kind=="condition"),conditions)

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
                    save=control["save"];self.assertIsInstance(save,str)
                    one=reach*(1-save_success_probability(target,save,self.model.kv_save_dc(target.level,5)))
                self.assertGreater(row["named"],100*one)

    def test_glacial_spike_replaces_slow_reliability_without_weakening_other_cryo_scenarios(self)->None:
        target=self.target()
        for tier in (0,1,2):
            with self.subTest(tier=tier):
                row=_kv_scenario(self.model,self.config,target,"cryokinesis","glacial_spike",tier);self.assertEqual(row["mastery"],0.0);self.assertFalse(any(component["source_effect"]=="mastery:slow" for component in row["shadow_components"]))
        ordinary=_kv_scenario(self.model,self.config,target,"cryokinesis","snow_chains",2);self.assertGreater(ordinary["mastery"],0.0);self.assertTrue(any(component["source_effect"]=="mastery:slow" for component in ordinary["shadow_components"]))

    def test_static_discharge_tier_two_signature_control_cannot_retry(self)->None:
        feature=self.model.features["static_discharge"];target=self.target();row=_kv_scenario(self.model,self.config,target,"electrokinesis","static_discharge",2);bonus=self.model.kv_attack_bonus(20,5)+2;hit=sum(attack_probabilities(bonus,target.ac)[1:])
        self.assertEqual(feature["psi_cost"],0)
        self.assertAlmostEqual(_repeat_rider_probability(self.model,self.config,20,2,int(feature["psi_cost"]),0.25),0.25,places=12)
        self.assertAlmostEqual(row["whole"],100*hit,places=12)
        self.assertGreater(_mastery_scenario(self.model,self.config,target,"electrokinesis")["whole"],row["whole"])


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
        damage_limitation="Damage percentages are computed from the displayed aggregate raw values, never from averaged target-level percentages."
        limitation=("Control Reliability measures how reliably the Control-Value-selected package takes effect and, where applicable, persists. "
                    "It does not measure the relative severity, duration, area, or strategic value of different control effects. "
                    "A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered.")
        old_limitation="Control Reliability measures how often the configured control package takes effect."
        self.assertTrue(control_markdown.startswith("# Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix"))
        self.assertIn("<title>Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix</title>",control_html)
        self.assertIn("<h1>Kinetic Vanguard 14.1.0 Control Reliability Comparison Matrix</h1>",control_html)
        self.assertIn(limitation,control_markdown)
        self.assertIn(limitation,control_html)
        self.assertNotIn(old_limitation,control_markdown)
        self.assertNotIn(old_limitation,control_html)
        self.assertIn(damage_limitation,markdown)
        self.assertIn(damage_limitation,html)
        for rendered in (markdown,html,control_markdown,control_html):
            self.assertNotIn("ORDER CHECK",rendered)
            self.assertNotIn("Hunter Ranger",rendered)
            self.assertNotIn("Open Hand Monk",rendered)


class CommonControlSelectionTests(unittest.TestCase):
    @staticmethod
    def candidate(scenario:str,cu:float,reliability:float,eligible:bool=True)->dict[str,object]:
        return {"Scenario":scenario,"Control Value CU":cu,"Whole-package control stick %":reliability,"Eligible":eligible}

    def test_higher_value_wins_and_reliability_follows_that_package(self)->None:
        winner=_select_control_value([self.candidate("scenario_a",1.00,40.0),self.candidate("scenario_b",0.80,95.0)])
        self.assertEqual((winner["Scenario"],winner["Control Value CU"],winner["Whole-package control stick %"]),("scenario_a",1.00,40.0))

    def test_exact_value_tie_uses_higher_reliability(self)->None:
        winner=_select_control_value([self.candidate("scenario_a",1.00,40.0),self.candidate("scenario_b",1.00,70.0)])
        self.assertEqual(winner["Scenario"],"scenario_b")

    def test_exact_value_and_reliability_tie_uses_ascending_scenario_id(self)->None:
        winner=_select_control_value([self.candidate("scenario_b",1.00,70.0),self.candidate("scenario_a",1.00,70.0)])
        self.assertEqual(winner["Scenario"],"scenario_a")

    def test_ineligible_high_value_scenario_never_wins(self)->None:
        winner=_select_control_value([self.candidate("ineligible",100.0,100.0,False),self.candidate("eligible",1.00,40.0)])
        self.assertEqual(winner["Scenario"],"eligible")


class ComparatorReferenceEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.directory=tempfile.TemporaryDirectory();cls.root=Path(cls.directory.name)
        cls.result=run_control(DEFAULT_AUTHORITY,cls.root,{7,11,15,20},None,write_headline=True,profile="headline",write_shadow=True)
        with cls.result["value_paths"]["comparator_reference"].open(encoding="utf-8") as stream:cls.rows=list(csv.DictReader(stream))
        cls.targets=load_targets(profile="headline",levels={7,11,15,20});cls.target_by_identity={(target.level,target.name):target for target in cls.targets}
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators()

    @classmethod
    def tearDownClass(cls)->None:cls.directory.cleanup()

    def test_fixed_reference_inventories_and_config_sources_are_exact(self)->None:
        self.assertEqual(tuple(item[0] for item in BATTLE_MASTER_REFERENCE_SCENARIOS),("menacing_attack","pushing_attack","trip_attack"))
        self.assertEqual(tuple(item[0] for item in ELDRITCH_KNIGHT_REFERENCE_FAMILIES),("ray_of_frost","thunderwave","blindness_deafness","hold_person","web","hypnotic_pattern","slow"))
        bm_config={scenario["id"] for scenario in self.comparators["control"]["battle_master"]["scenarios"]}
        self.assertTrue(set(dict(BATTLE_MASTER_REFERENCE_SCENARIOS))<=bm_config)
        self.assertFalse({"goading_attack","disarming_attack"}&{row["Family ID"] for row in self.rows if row["Build"]=="battle_master"})
        self.assertEqual({(row["Build"],row["Family ID"]) for row in self.rows},{*(('battle_master',item[0]) for item in BATTLE_MASTER_REFERENCE_SCENARIOS),*(('eldritch_knight',item[0]) for item in ELDRITCH_KNIGHT_REFERENCE_FAMILIES)})

    def test_battle_master_reference_values_are_exact_evaluator_outputs(self)->None:
        target=next(item for item in self.targets if item.level==7 and item.name=="Gladiator")
        for scenario_id,_ in BATTLE_MASTER_REFERENCE_SCENARIOS:
            scenario=next(item for item in self.comparators["control"]["battle_master"]["scenarios"] if item["id"]==scenario_id)
            evaluated=_comparator_scenario(self.model,self.config,self.comparators,target,"battle_master",scenario)
            primitive=shadow_rows({"Build":"battle_master","Discipline":"all","Level":target.level,"Target":target.name,"Scenario":scenario_id},evaluated["shadow_components"],horizon=int(self.config["methodology"]["rounds"]),benchmark_locomotion_speed=target.benchmark_locomotion_speed)
            published=next(row for row in self.rows if row["Build"]=="battle_master" and row["Family ID"]==scenario_id and row["Level"]=="7" and row["Target"]==target.name)
            with self.subTest(scenario=scenario_id):
                self.assertAlmostEqual(float(published["Control Value CU"]),sum(float(row["Control Value CU"]) for row in primitive))
                self.assertAlmostEqual(float(published["Whole-package control stick %"]),float(evaluated["whole"]))
                self.assertEqual(published["Scenario"],scenario_id)

    def test_battle_master_effectiveness_tracks_immunity_size_and_prone(self)->None:
        keyed={(row["Level"],row["Target"],row["Family ID"]):row for row in self.rows if row["Build"]=="battle_master"}
        frightened=[target for target in self.targets if "frightened" in target.condition_immunities]
        oversized=[target for target in self.targets if target.size in {"huge","gargantuan"}]
        prone=[target for target in self.targets if "prone" in target.condition_immunities]
        self.assertTrue(frightened and oversized and prone)
        for target in frightened:self.assertEqual(keyed[(str(target.level),target.name,"menacing_attack")]["Effectiveness Status"],INEFFECTIVE_NULLIFIED)
        for target in oversized:
            self.assertEqual(keyed[(str(target.level),target.name,"pushing_attack")]["Effectiveness Status"],INEFFECTIVE_STRUCTURAL)
            self.assertEqual(keyed[(str(target.level),target.name,"trip_attack")]["Effectiveness Status"],INEFFECTIVE_STRUCTURAL)
        for target in prone:
            if target.size not in {"huge","gargantuan"}:self.assertEqual(keyed[(str(target.level),target.name,"trip_attack")]["Effectiveness Status"],INEFFECTIVE_NULLIFIED)

    def test_eldritch_knight_grouping_modes_access_and_primers_are_semantic(self)->None:
        synthetic={"id":"unrelated_identifier","spell_id":"web","effects":[]}
        impostor={"id":"web","spell_id":"slow","effects":[]}
        self.assertTrue(_is_eldritch_knight_reference_scenario("web",synthetic));self.assertFalse(_is_eldritch_knight_reference_scenario("web",impostor))
        blindness=[row for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]=="blindness_deafness" and row["Family Available At Level"]=="True"]
        self.assertTrue(blindness);self.assertTrue(all("condition:blinded" in row["Declared Consequences"] and "hearing_option_denial" not in row["Declared Consequences"] for row in blindness))
        ray=[row for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]=="ray_of_frost"]
        self.assertTrue(all(row["Family Candidate Scenarios"]=="1" for row in ray))
        thunder=[row for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]=="thunderwave"]
        self.assertTrue(any(int(row["Family Candidate Scenarios"])>1 for row in thunder))
        self.assertTrue(all("eldritch_strike" not in row["Save Primers"] for row in thunder if row["Level"]=="7"))
        self.assertTrue(all(row["Primer Timing"]=="cross_turn" for row in self.rows if "mind_sliver" in row["Save Primers"]))
        slow=next(item for item in self.comparators["control"]["eldritch_knight"]["scenarios"] if item["id"]=="slow");target=replace(self.targets[0],level=11)
        self.assertFalse(_comparator_scenario_available_at_level(self.comparators,target,"eldritch_knight",slow))
        changed=deepcopy(self.comparators);changed["control"]["eldritch_knight"]["spell_access"]["highest_slot_level_by_fighter_level"]["11"]=3
        self.assertTrue(_comparator_scenario_available_at_level(changed,target,"eldritch_knight",slow))

    def test_eldritch_knight_availability_target_zeros_and_per_target_selection(self)->None:
        for family in ("hypnotic_pattern","slow"):
            early=[row for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]==family and row["Level"] in {"7","11"}]
            self.assertTrue(early);self.assertTrue(all(row["Family Available At Level"]=="False" and row["Scenario"]=="" for row in early))
            self.assertTrue(all(row["Family Available At Level"]=="True" for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]==family and row["Level"] in {"15","20"}))
        hold=[row for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]=="hold_person"]
        nonhumanoids=[row for row in hold if self.target_by_identity[(int(row["Level"]),row["Target"])].creature_type!="humanoid"]
        self.assertTrue(nonhumanoids);self.assertTrue(all(row["Family Available At Level"]=="True" and row["Eligible"]=="False" and float(row["Control Value CU"])==0 and float(row["Whole-package control stick %"])==0 for row in nonhumanoids))
        web={row["Scenario"] for row in self.rows if row["Build"]=="eldritch_knight" and row["Family ID"]=="web"}
        self.assertGreater(len(web),1)

    def test_reference_derivative_does_not_change_headline_or_common_selection(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plain=run_control(DEFAULT_AUTHORITY,root/"plain",{7},1,write_headline=True,profile="headline",write_shadow=False);reference=run_control(DEFAULT_AUTHORITY,root/"reference",{7},1,write_headline=True,profile="headline",write_shadow=True)
            self.assertEqual(plain["paths"]["csv"].read_bytes(),reference["paths"]["csv"].read_bytes())
            for name in ("kv-14-3-0-control-detail.csv","kv-14-3-0-control-selection-audit.csv"):
                self.assertEqual((root/"plain"/name).read_bytes(),(root/"reference"/name).read_bytes())


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
            self.assertAlmostEqual(float(damage_row["Eldritch Knight Primary DPR"]),18.816666666666663,places=12)
            self.assertAlmostEqual(float(damage_row["Eldritch Knight Aggregate DPR"]),18.816666666666663,places=12)
            legal={"[2,1,1]","[1,2,1]","[1,1,2]"}
            self.assertIn(damage_row["KV Action Slots"],legal)
            self.assertIn(damage_row["Eldritch Knight Primary Action Slots"],legal)
            self.assertIn(damage_row["Eldritch Knight Aggregate Action Slots"],legal)
            self.assertIn(damage_row["Battle Master Action Slots"],legal)
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
            self.assertTrue(all(row["Selection Basis"]=="Control Value" for row in audit_rows))
            self.assertTrue(all(row["Whole-package control stick %"] for row in audit_rows))
            with (root/"kv-14-3-0-control-detail.csv").open(encoding="utf-8") as stream:
                control_rows=list(csv.DictReader(stream))
            keyed={(row["Build"],row["Scenario"]):row for row in control_rows}
            self.assertEqual(keyed[("battle_master","menacing_attack")]["Whole-package control stick %"],"80.859375")
            self.assertEqual(keyed[("eldritch_knight","blindness_deafness")]["Whole-package control stick %"],"55.000000")
            self.assertIn(("eldritch_knight","web"),keyed)
            with control["paths"]["csv"].open(encoding="utf-8") as stream:
                matrix_rows=list(csv.DictReader(stream))
            self.assertTrue(matrix_rows);self.assertTrue(all(row["Provenance Evaluator"]=="exact_analytical_enumeration" for row in matrix_rows))
            self.assertTrue(all(row["Provenance Control Primitive Catalog Sha256"]==file_sha256(DEFAULT_PRIMITIVES) for row in matrix_rows))
            self.assertTrue(all(row["Provenance Control Value Config Sha256"]==file_sha256(DEFAULT_SCORING) for row in matrix_rows))

    def test_control_value_detail_writes_common_transparent_outputs(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);control=run_control(DEFAULT_AUTHORITY,root,{20},1,write_headline=False,profile="headline",write_shadow=True)
            self.assertEqual(control["shadow_rows"],569);self.assertEqual(control["value_scenario_rows"],186);self.assertEqual(control["catalog_scenario_rows"],4);self.assertEqual(control["comparator_reference_rows"],10);self.assertEqual(control["value_audit_rows"],6);self.assertEqual(control["value_matrix_rows"],4)
            self.assertEqual(set(control["value_paths"]),{"scenario_detail","catalog_scenario_detail","comparator_reference","selection_audit","matrix"});self.assertTrue(all(path.is_file() for path in control["value_paths"].values()))
            with control["shadow_path"].open(encoding="utf-8") as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"] in {"candidate","context_required","unsupported"} for row in rows))
            for column in ("Application Probability","Active Probabilities","Expected Exposure","Nominal Weight","Scoring Transform","Control Value CU","Normalization","Suppressed By","Control Value Config SHA-256"):
                self.assertIn(column,rows[0])
            with control["value_paths"]["selection_audit"].open(encoding="utf-8") as stream:
                value_audit=list(csv.DictReader(stream))
            self.assertEqual(len(value_audit),6);self.assertTrue(all(row["Selected Scenario"] and row["Eligible"]=="True" for row in value_audit));self.assertTrue(all(row["Selection Basis"]=="Control Value" for row in value_audit));self.assertTrue(all(row["Value Disposition"] in {"priced_nonzero","legitimately_priced_zero","entirely_context_required_or_unsupported"} for row in value_audit))
            with (root/"kv-14-3-0-control-selection-audit.csv").open(encoding="utf-8") as stream:
                reliability_audit=list(csv.DictReader(stream))
            identity=lambda row:(row["Level"],row["Target"],row["Discipline"],row["Build"],row["Selected Scenario"])
            self.assertEqual({identity(row) for row in reliability_audit},{identity(row) for row in value_audit})
            self.assertNotIn("reliability_scenario_ids",load_comparators()["control"]["eldritch_knight"])

    def test_rider_only_catalog_evidence_is_isolated_from_headline_selection(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);baseline_root=root/"baseline";catalog_root=root/"catalog"
            baseline=run_control(DEFAULT_AUTHORITY,baseline_root,{7},1,write_headline=True,profile="headline",write_shadow=True)
            control=run_control(
                DEFAULT_AUTHORITY,catalog_root,{7},1,
                write_headline=True,profile="headline",write_shadow=True,
                publication_scenarios=(
                    {"discipline_id":"cryokinesis","entity_id":"snow_chains","tier":0,"target_role":"primary"},
                    {"discipline_id":"cryokinesis","entity_id":"snow_chains","tier":2,"target_role":"primary"},
                ),
            )
            self.assertEqual(baseline["paths"]["csv"].read_bytes(),control["paths"]["csv"].read_bytes())
            self.assertEqual(baseline["value_paths"]["matrix"].read_bytes(),control["value_paths"]["matrix"].read_bytes())
            self.assertEqual(baseline["value_paths"]["selection_audit"].read_bytes(),control["value_paths"]["selection_audit"].read_bytes())
            with control["value_paths"]["catalog_scenario_detail"].open(encoding="utf-8") as stream:
                scenarios=list(csv.DictReader(stream))
            extra=[row for row in scenarios if row["Build"]=="kinetic_vanguard" and row["Discipline"]=="cryokinesis" and row["Scenario"]=="snow_chains:T0"]
            self.assertEqual(len(extra),1)
            self.assertFalse(any(row["Scenario"]=="snow_chains:T2" for row in scenarios))
            self.assertIn("Retained Candidate Rows",extra[0]);self.assertIn("Retained Context/Unsupported Rows",extra[0])
            with control["value_paths"]["selection_audit"].open(encoding="utf-8") as stream:
                winners=list(csv.DictReader(stream))
            with baseline["value_paths"]["selection_audit"].open(encoding="utf-8") as stream:
                baseline_winners=list(csv.DictReader(stream))
            self.assertEqual(winners,baseline_winners)
            model=AuthorityModel.load();config=load_config();target=load_targets(profile="headline",levels={7},limit=1)[0]
            full=_kv_scenario(model,config,target,"cryokinesis","snow_chains",0);rider=_catalog_rider_scenario(model,config,target,"cryokinesis","snow_chains",0);mastery=_mastery_scenario(model,config,target,"cryokinesis")
            self.assertGreater(full["mastery"],0.0);self.assertEqual(rider["mastery"],0.0);self.assertEqual(rider["whole"],full["named"]);self.assertTrue(all(not component["source_effect"].startswith("mastery:") for component in rider["shadow_components"]));self.assertTrue(all(component["source_effect"].startswith("mastery:") for component in mastery["shadow_components"]))
            projection=deepcopy(model.projection);next(item for item in projection["disciplines"] if item["id"]=="cryokinesis")["mastery"]["control_outcomes"]=[]
            without_mastery=_catalog_rider_scenario(AuthorityModel(projection),config,target,"cryokinesis","snow_chains",0)
            self.assertEqual((rider["named"],rider["whole"],rider["shadow_components"]),(without_mastery["named"],without_mastery["whole"],without_mastery["shadow_components"]))
            with self.assertRaisesRegex(ValueError,"lacks canonical control mechanics"):_kv_scenario(model,config,target,"electrokinesis","branching_bolt",0)

    def test_publication_catalog_scenario_errors_fail_closed(self)->None:
        publication=({"discipline_id":"cryokinesis","entity_id":"snow_chains","tier":0,"target_role":"primary"},)
        for error in (RuntimeError("synthetic unavailable evaluator failure"),AuthorityError("synthetic unavailable authority failure")):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as directory:
                with patch("harness.control_harness._catalog_rider_scenario",side_effect=error):
                    with self.assertRaisesRegex(type(error),"synthetic unavailable"):
                        run_control(DEFAULT_AUTHORITY,Path(directory),{7},1,write_headline=False,profile="headline",write_shadow=True,publication_scenarios=publication)


if __name__=="__main__":unittest.main()
