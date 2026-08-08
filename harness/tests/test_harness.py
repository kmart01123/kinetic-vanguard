from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import harness.authority as authority_module
import harness.model as model_module
from harness.authority import AuthorityError,DamageAuthorityModel,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.damage_report import BANDS,COMPARATOR_NOTICE,LEGAL_NOTICES,NOTICE_COLUMNS,PROJECT_ATTRIBUTION_NOTICE,SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,SRD_SECTION_5_NOTICE,VALUE_COLUMNS,classify_envelope,damage_matrix_row,write_damage_matrix
from harness.damage_harness import Package,Standalone,_KVDamagePlanner,_comparator_dpr,_kv_dpr,_strike_packet_options,run as run_damage
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,Target,load_comparators,load_config,load_targets


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


class AuthorityProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load()

    def test_real_root_damage_authority_and_complete_stable_id_inventory(self)->None:
        self.assertEqual(Path(self.model.projection["authority_path"]),DEFAULT_AUTHORITY)
        self.assertEqual(self.model.rules_version,"14.2.0")
        self.assertEqual(self.model.projection["schema_version"],"3.0.0")
        self.assertEqual(self.model.projection["projection_version"],authority_module.DAMAGE_PROJECTION_VERSION)
        self.assertEqual(self.model.projection["core"]["action_economy"],{"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False})
        feature_ids=list(self.model.features)
        self.assertEqual(len(feature_ids),len(set(feature_ids)))
        self.assertEqual(set(self.model.disciplines),{"pyrokinesis","cryokinesis","psychokinesis","electrokinesis"})
        self.assertTrue(all(feature["minimum_level"]>=3 and feature["psi_cost"]>=0 for feature in self.model.features.values()))
        self.assertTrue(all("entity_id" in feature and "control_tiers" not in feature for feature in self.model.features.values()))
        self.assertTrue(all("mastery" not in discipline for discipline in self.model.disciplines.values()))
        self.assertEqual(self.model.disciplines["pyrokinesis"]["graze_damage"],"psionic_ability_modifier")
        self.assertTrue(all("graze_damage" not in discipline for key,discipline in self.model.disciplines.items() if key!="pyrokinesis"))

    def test_damage_authority_names_have_no_generic_compatibility_aliases(self)->None:
        self.assertIs(authority_module.DamageAuthorityModel,DamageAuthorityModel)
        self.assertTrue(callable(authority_module.load_damage_projection))
        for obsolete in ("LEGACY_PROJECTION_VERSION","load_projection","AuthorityModel"):
            self.assertFalse(hasattr(authority_module,obsolete),obsolete)

    def test_structural_yaml_mutation_changes_projection_without_python_edit(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        probe="id: pyrokinesis\n        damage_type: fire"
        self.assertIn(probe,source)
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace(probe,"id: pyrokinesis\n        damage_type: cold",1),encoding="utf-8")
            mutated=DamageAuthorityModel.load(authority)
        self.assertEqual(self.model.disciplines["pyrokinesis"]["damage_type"],"fire")
        self.assertEqual(mutated.disciplines["pyrokinesis"]["damage_type"],"cold")

    def test_missing_mechanics_and_unavailable_tier_fail_closed(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace("  harness_mechanics:\n","  missing_harness_mechanics:\n",1),encoding="utf-8")
            with self.assertRaises(AuthorityError):DamageAuthorityModel.load(authority)
        with self.assertRaisesRegex(AuthorityError,"unavailable"):self.model.feature("flare",7,2)
        with self.assertRaisesRegex(AuthorityError,"Unsupported"):self.model.feature("glacial_spike",7,9)

    def test_action_economy_mutation_fails_closed(self)->None:
        source=DEFAULT_AUTHORITY.read_text(encoding="utf-8")
        probe="      action_surge_allows_additional_standalone_psionic_action: false"
        self.assertIn(probe,source)
        with tempfile.TemporaryDirectory() as directory:
            authority=Path(directory)/"KineticVanguard.yaml"
            authority.write_text(source.replace(probe,"      action_surge_allows_additional_standalone_psionic_action: true",1),encoding="utf-8")
            with self.assertRaisesRegex(AuthorityError,"action_economy|action_surge_allows_additional"):DamageAuthorityModel.load(authority)

    def test_progression_bands_cover_every_supported_level_once(self)->None:
        for name in ("proficiency_bonus","psi_points","psionic_focus","manifested_strike_die"):
            for level in range(3,21):self.assertIsInstance(self.model.progression(name,level),int)

    def test_optional_graze_damage_is_the_only_discipline_damage_mastery_input(self)->None:
        target=replace(load_targets()[0],damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
        pyro=_strike_packet_options(self.model,target,"pyrokinesis",7,5,8)
        cryo=_strike_packet_options(self.model,target,"cryokinesis",7,5,8)
        self.assertTrue(all(packet[1][0]==5.0 for packet in pyro))
        self.assertTrue(all(packet[1][0]==0.0 for packet in cryo))

    def test_comparator_inputs_are_isolated_minimal_and_fail_closed(self)->None:
        config=load_config();comparators=load_comparators()
        self.assertNotIn("damage_comparators",config);self.assertNotIn("control_comparators",config)
        self.assertNotIn("control_matrix",config);self.assertNotIn("control",comparators)
        self.assertEqual(comparators["source_ruleset"],"2024 fifth-edition rules")
        self.assertEqual(set(comparators["primary_comparator_ids"]),{"battle_master","eldritch_knight"})
        self.assertEqual(set(comparators["damage"]),{"battle_master","eldritch_knight"})
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

    def test_benchmark_config_rejects_unknown_status_shape_and_progression(self)->None:
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("status","CERTIFIED_BY_ASSERTION"),"review status")
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
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["non_damage_effect_boundary"].__setitem__("modeled_self_attack_exception","none"),"non-damage effect boundary")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"].__setitem__("objective",["primary_damage","aggregate_damage"]),"optimization objective")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"]["decision_timing"].__setitem__("unobserved_outcome_lookahead",True),"decision timing")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["damage_matrix"]["optimization"]["decision_timing"].__setitem__("unobserved_outcome_lookahead",0),"lookahead must be a boolean")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value.__setitem__("control_matrix",{}),"benchmark config keys")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("control_seed",1),"methodology keys")

    def test_comparator_config_rejects_unknown_missing_and_incomplete_parameters(self)->None:
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("unused_bonus",1),"damage.battle_master keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].pop("true_strike_uses_per_attack_action"),"damage.eldritch_knight keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["magic_weapon_bonus_by_level"].pop("20"),"magic_weapon_bonus_by_level keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("great_weapon_master_attack_action_bonus","fixed"),"GWM bonus")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maximum_maneuver_dice_per_attack",2),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maneuver_choice_timing","before_attack_roll"),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["tactical_policy"].__setitem__("true_strike_choice_timing","after_attack_roll"),"Eldritch Knight tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value.__setitem__("control",{}),"comparator config keys")

    def test_full_pinned_target_shape_remains_generic_roster_data(self)->None:
        self.assertEqual(set(Target.__dataclass_fields__),{
            "level","name","ac","saves","magic_resistance","legendary_resistance","size","creature_type",
            "condition_immunities","damage_resistances","damage_immunities","damage_vulnerabilities",
            "hp","source","source_page","source_url",
        })
        target=load_targets()[0]
        self.assertTrue(target.size and target.creature_type and target.condition_immunities is not None)

    def test_current_review_status_matches_damage_only_provenance(self)->None:
        path=PROJECT_ROOT/"harness/provenance/damage-review.json"
        provenance=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(provenance),{
            "pinned_srd","historical_damage_source","historical_damage_certification",
            "current_damage_review","current_comparator_review",
        })
        self.assertEqual(provenance["historical_damage_certification"]["status"],"PRESERVED_PROVENANCE_ONLY")
        self.assertEqual(load_config()["methodology"]["status"],provenance["current_damage_review"]["status"])
        self.assertEqual(provenance["historical_damage_source"]["filename"],"kv_v12_0_0_damage_harness.py")
        self.assertNotIn("control",json.dumps(provenance).lower())
        self.assertFalse((PROJECT_ROOT/"harness/provenance/legacy-import.json").exists())


class FighterNumericalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.targets=load_targets()

    def test_exact_fighter_dpr_sentinels_cover_every_supported_level(self)->None:
        expected={
            7:("Air Elemental",13.900000000000006,24.575569569001160),
            11:("Aboleth",44.400000000000000,81.127998399293940),
            15:("Adult Black Dragon",49.960671191473686,90.409620247713760),
            20:("Balor",108.956136040152290,168.515058184716450),
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
        self.assertAlmostEqual(reviewed-without_post_failure_choice,0.06767946573216932,places=12)


class ComparatorLeafContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.base=load_targets()[0]

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


class DamagePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.base=next(item for item in load_targets(levels={20}) if item.name=="Balor");cls.mastery=cls.model.projection["core"]["overload"]["mastery"]

    def planner(self,attacks_per_action:int)->_KVDamagePlanner:
        target=replace(self.base,ac=30,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());packages=(Package(None,0,0,0),Package("branching_bolt",0,0,0));riders={packages[0]:(0.0,0.0),packages[1]:(100.0,100.0)}
        planner=_KVDamagePlanner(self.model,target,packages,riders,(("normal",(0.0,1.0,2.0)),),((),),0,attacks_per_action,(1,),True,True,0,0,self.mastery,0,1);self.addCleanup(planner.clear);return planner

    def test_combat_prowess_hit_instead_does_not_establish_studied(self)->None:
        planner=self.planner(1);package_index=1
        result=planner._resolve_attack_roll(0,0,0,planner.package_bits[package_index],0,package_index,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:4],("prowess",False,False,0))

    def test_combat_prowess_can_be_retained_for_a_more_valuable_later_attack(self)->None:
        planner=self.planner(2)
        result=planner._resolve_attack_roll(0,0,1,0,0,0,0,"miss",True,0,0,0,0,2,False,0)
        self.assertEqual(result.choice[:4],("miss",True,True,0))
        self.assertAlmostEqual(result.score.aggregate,101.0975,places=12)

    def test_studied_expires_after_a_zero_attack_turn(self)->None:
        planner=self.planner(1)
        result=planner._actions(0,0,True,True,0,0,0,0,2,False,0,False)
        self.assertEqual(result.choice,("end_turn",False))

    def test_tier_zero_does_not_spend_the_first_overload_mastery_trigger(self)->None:
        planner=self.planner(1)
        self.assertEqual(planner._payment_options(0,1,0),((0,1,0,False),))
        self.assertIn((3,0,1,True),planner._payment_options(6,1,0))

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

    def test_repeatability_and_tier_two_allowance_reset_for_a_new_attack_action(self)->None:
        target=replace(self.base,ac=1,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset());plain=Package(None,0,0,0);rider=Package("branching_bolt",2,0,0);packages=(plain,rider)
        planner=_KVDamagePlanner(self.model,target,packages,{plain:(0.0,0.0),rider:(100.0,100.0)},(("normal",(0.0,0.0,0.0)),),((),),0,1,(2,),False,False,0,0,self.mastery,0,1);self.addCleanup(planner.clear)
        self.assertAlmostEqual(planner.solve().aggregate,190.0,places=12)
        self.assertEqual(planner.selection().count("branching_bolt:T2"),2)

    def test_observed_state_policy_matches_reviewed_l20_sentinel(self)->None:
        target=next(item for item in load_targets(levels={20}) if item.name=="Ancient Black Dragon")
        primary,aggregate,selection=_kv_dpr(self.model,self.config,target,"electrokinesis",3)
        self.assertAlmostEqual(primary,105.43451437911521,places=10)
        self.assertAlmostEqual(aggregate,164.8852829551137,places=10)
        self.assertIn("electron_burst:T2",selection)
        self.assertTrue(selection.endswith("|representative=locally-modal-path|policy=observed-state-adaptive"))


class ClassificationTests(unittest.TestCase):
    def test_damage_envelope_classifier_is_swap_invariant_and_inclusive(self)->None:
        expected=((9,"COLD"),(10,"IDEAL"),(15,"IDEAL"),(20,"IDEAL"),(21,"HOT"))
        for eldritch_knight,battle_master in ((10,20),(20,10)):
            for kv,band in expected:
                with self.subTest(kv=kv,ek=eldritch_knight,bm=battle_master):
                    self.assertEqual(classify_envelope(kv,eldritch_knight,battle_master),band)
                    self.assertEqual(damage_matrix_row({},kv,eldritch_knight,battle_master)["Band"],band)

    def test_swap_preserves_band_delta_and_dynamic_boundary_values(self)->None:
        for kv,band,delta in ((8,"COLD","-20.00"),(10,"IDEAL","0.00"),(15,"IDEAL","0.00"),(20,"IDEAL","0.00"),(24,"HOT","+20.00")):
            forward=damage_matrix_row({},kv,10,20)
            reversed_order=damage_matrix_row({},kv,20,10)
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
                    damage_matrix_row({},*values)
        self.assertEqual(classify_envelope(9,10,10),"COLD")
        self.assertEqual(classify_envelope(10,10,10),"IDEAL")
        self.assertEqual(classify_envelope(11,10,10),"HOT")

    def test_percentage_uses_displayed_aggregate_raw_values(self)->None:
        row=damage_matrix_row({"Level":7},10.0,8.0,20.0)
        self.assertEqual(row["Benchmark Type"],"Damage")
        self.assertEqual(row["KV as % of EK"],"125.00")
        self.assertEqual(row["KV as % of BM"],"50.00")
        self.assertEqual(row["Band"],"IDEAL")
        self.assertEqual(row["Boundary Delta %"],"0.00")

    def test_damage_matrix_row_identifies_dynamic_boundaries_and_ties(self)->None:
        expected=((10,20,"Eldritch Knight","Battle Master"),(20,10,"Battle Master","Eldritch Knight"))
        for eldritch_knight,battle_master,lower_name,upper_name in expected:
            row=damage_matrix_row({},15,eldritch_knight,battle_master)
            self.assertEqual(row["Benchmark Type"],"Damage")
            self.assertEqual(row["Lower Comparator"],lower_name)
            self.assertEqual(row["Upper Comparator"],upper_name)
            self.assertEqual(row["Lower Boundary"],"10.000000")
            self.assertEqual(row["Upper Boundary"],"20.000000")
        tied=damage_matrix_row({},10,10,10)
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

    def test_csv_markdown_html_share_full_damage_envelope_evidence(self)->None:
        row=damage_matrix_row({"Level":7,"Discipline":"cryokinesis"},10,8,20)
        provenance={"rules_version":"14.1.0","authority_sha256":"probe","roster_sha256":"probe"}
        self.assertEqual([key for key in row if key in VALUE_COLUMNS],VALUE_COLUMNS)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=write_damage_matrix(root/"damage","14.1.0",[row],provenance)
            bad=dict(row);bad["Band"]="ORDER CHECK"
            with self.assertRaisesRegex(ValueError,"unsupported band"):
                write_damage_matrix(root/"bad","14.1.0",[bad],provenance)
            incomplete=dict(row);del incomplete["Lower Boundary"]
            with self.assertRaisesRegex(ValueError,"missing evidence"):
                write_damage_matrix(root/"incomplete","14.1.0",[incomplete],provenance)
            stale_band=dict(row);stale_band["Band"]="HOT"
            with self.assertRaisesRegex(ValueError,"stale Band"):
                write_damage_matrix(root/"stale-band","14.1.0",[stale_band],provenance)
            stale_delta=dict(row);stale_delta["Boundary Delta %"]="+1.00"
            with self.assertRaisesRegex(ValueError,"stale Boundary Delta"):
                write_damage_matrix(root/"stale-delta","14.1.0",[stale_delta],provenance)
            stale_type=dict(row);stale_type["Benchmark Type"]="Not Damage"
            with self.assertRaisesRegex(ValueError,"stale Benchmark Type"):
                write_damage_matrix(root/"stale-type","14.1.0",[stale_type],provenance)
            with paths["csv"].open(encoding="utf-8") as stream:
                csv_row=next(csv.DictReader(stream))
            markdown=paths["markdown"].read_text(encoding="utf-8")
            html=paths["html"].read_text(encoding="utf-8")
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
        self.assertTrue(markdown.startswith("# Kinetic Vanguard 14.1.0 Damage Comparison Matrix"))
        self.assertIn("<title>Kinetic Vanguard 14.1.0 Damage Comparison Matrix</title>",html)
        self.assertIn("## Licensing and notices",markdown)
        self.assertIn("<h2>Licensing and notices</h2>",html)
        for label,value in LEGAL_NOTICES:
            self.assertEqual(markdown.count(value),1,label)
            self.assertEqual(html.count(value),1,label)
        for rendered in (markdown,html):
            self.assertNotIn("ORDER CHECK",rendered)
            self.assertNotIn("Hunter Ranger",rendered)
            self.assertNotIn("Open Hand Monk",rendered)


class SmokeAndBoundaryTests(unittest.TestCase):
    def test_fixed_seed_damage_smoke_writes_versioned_outputs_deterministically(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            damage=run_damage(DEFAULT_AUTHORITY,root/"damage",{7},2,16,19)
            parallel=run_damage(DEFAULT_AUTHORITY,root/"damage-parallel",{7},2,16,19,workers=2)
            self.assertEqual(damage["matrix_rows"],24)
            self.assertEqual(parallel["matrix_rows"],24)
            for result in (damage,parallel):
                self.assertEqual(set(result["paths"]),{"csv","markdown","html"})
                self.assertTrue(all("14-2-0" in path.name and path.is_file() for path in result["paths"].values()))
            detail=root/"damage"/"kv-14-2-0-damage-detail.csv"
            with detail.open(encoding="utf-8") as stream:
                damage_row=next(csv.DictReader(stream))
            self.assertAlmostEqual(float(damage_row["Eldritch Knight DPR"]),13.900000000000018,places=12)
            self.assertAlmostEqual(float(damage_row["Battle Master DPR"]),24.57556956900116,places=12)
            self.assertTrue(damage_row["Comparator Config SHA-256"])
            self.assertEqual({key:damage_row[key] for key in NOTICE_COLUMNS},NOTICE_COLUMNS)
            self.assertEqual(detail.read_bytes(),(root/"damage-parallel"/detail.name).read_bytes())
            for format_name in damage["paths"]:
                self.assertEqual(damage["paths"][format_name].read_bytes(),parallel["paths"][format_name].read_bytes())
            status=load_config()["methodology"]["status"]
            with damage["paths"]["csv"].open(encoding="utf-8") as stream:
                matrix_rows=list(csv.DictReader(stream))
            self.assertTrue(matrix_rows)
            self.assertTrue(all(row["Provenance Status"]==status for row in matrix_rows))
            self.assertTrue(all({key:row[key] for key in NOTICE_COLUMNS}==NOTICE_COLUMNS for row in matrix_rows))
            self.assertTrue(all(row["Provenance Evaluator"]=="exact_analytical_enumeration" for row in matrix_rows))
            self.assertTrue(all(row["Provenance Trial Seed Role"]=="historical_compatibility_metadata" for row in matrix_rows))
            self.assertTrue(all(row["Benchmark Type"]=="Damage" for row in matrix_rows))
            for row in matrix_rows:
                comparators={"Eldritch Knight":float(row["Eldritch Knight"]),"Battle Master":float(row["Battle Master"])}
                lower=min(comparators.values());upper=max(comparators.values())
                self.assertEqual(row["Lower Boundary"],f"{lower:.6f}")
                self.assertEqual(row["Upper Boundary"],f"{upper:.6f}")
                if lower==upper:
                    self.assertEqual(row["Lower Comparator"],"Eldritch Knight + Battle Master")
                    self.assertEqual(row["Upper Comparator"],"Eldritch Knight + Battle Master")
                else:
                    self.assertEqual(comparators[row["Lower Comparator"]],lower)
                    self.assertEqual(comparators[row["Upper Comparator"]],upper)
                self.assertNotEqual(row["Band"],"ORDER CHECK")
            self.assertIn(status,damage["paths"]["markdown"].read_text(encoding="utf-8"))
            self.assertIn(status,damage["paths"]["html"].read_text(encoding="utf-8"))

    def test_retired_python_runtime_configuration_and_aliases_are_absent(self)->None:
        for path in (
            PROJECT_ROOT/"harness/control_harness.py",
            PROJECT_ROOT/"harness/comparison_report.py",
            PROJECT_ROOT/"harness/provenance/legacy-import.json",
        ):
            self.assertFalse(path.exists(),path)
        self.assertTrue((PROJECT_ROOT/"harness/damage_report.py").is_file())
        self.assertTrue((PROJECT_ROOT/"harness/provenance/damage-review.json").is_file())
        config=load_config();comparators=load_comparators();projection=DamageAuthorityModel.load().projection
        self.assertNotIn("control_matrix",config)
        self.assertNotIn("control_default_trials",config["methodology"])
        self.assertNotIn("control_seed",config["methodology"])
        self.assertNotIn("smoke_trials",config["methodology"])
        self.assertNotIn("control",comparators)
        self.assertTrue(all("control_tiers" not in feature for feature in projection["features"]))
        for obsolete in ("stable_seed","attack_probabilities","damage_multiplier","expected_damage","target_is_eligible","SIZE_ORDER"):
            self.assertFalse(hasattr(model_module,obsolete),obsolete)

    def test_imports_outputs_and_archive_are_not_positive_inputs_or_tracked(self)->None:
        inputs=json.loads((PROJECT_ROOT/"build"/"inputs.json").read_text(encoding="utf-8"))["inputs"]
        paths=[item["path"] for item in inputs]
        self.assertTrue(all(not path.startswith(".codex-import/") and "results" not in path and not path.endswith(".zip") for path in paths))
        tracked=subprocess.run(["git","ls-files"],cwd=PROJECT_ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
        self.assertTrue(all(not path.startswith(".codex-import/") and not path.endswith("harness-import.zip") for path in tracked))


if __name__=="__main__":unittest.main()
