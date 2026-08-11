from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import harness.authority as authority_module
from harness.authority import AuthorityError,DamageAuthorityModel,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.creature_catalog import DAMAGE_PROJECTION_ID,DAMAGE_PROJECTION_VERSION,HEADLINE_PROFILE_ID,DamageTarget,RosterEntry,load_catalog,load_consumer_requirements,load_profile,project_damage_target,project_profile_damage_targets
from harness.damage_report import BANDS,COMPARATOR_NOTICE,LEGAL_NOTICES,NOTICE_COLUMNS,PROJECT_ATTRIBUTION_NOTICE,SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,SRD_SECTION_5_NOTICE,VALUE_COLUMNS,classify_envelope,damage_matrix_row,write_damage_matrix
from harness.damage_harness import DAMAGE_EVALUATOR_ID,DAMAGE_EVALUATOR_IMPLEMENTATION_PATHS,DAMAGE_RESULT_CONTRACT_VERSION,RUN_MANIFEST_FILENAME,Package,Standalone,_KVDamagePlanner,_comparator_dpr,_kv_dpr,_strike_packet_options,evaluator_implementation_sha256,run as run_damage
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,load_comparators,load_config


_HEADLINE_BINDINGS:tuple[tuple[RosterEntry,DamageTarget],...]|None=None


def _headline_bindings(levels:set[int]|None=None)->tuple[tuple[RosterEntry,DamageTarget],...]:
    global _HEADLINE_BINDINGS
    if _HEADLINE_BINDINGS is None:
        catalog=load_catalog();requirements=load_consumer_requirements(catalog=catalog);entries=load_profile(HEADLINE_PROFILE_ID,catalog=catalog)
        _HEADLINE_BINDINGS=tuple(project_profile_damage_targets(entries,catalog=catalog,requirements=requirements))
    if levels is None:return _HEADLINE_BINDINGS
    return tuple(binding for binding in _HEADLINE_BINDINGS if binding[0].benchmark_level in levels)


def _headline_target(level:int,name:str|None=None)->DamageTarget:
    matches=[target for entry,target in _headline_bindings({level}) if name is None or target.name==name]
    if len(matches)!=1 and name is not None:raise AssertionError(f"Expected one level-{level} headline target named {name!r}")
    if not matches:raise AssertionError(f"No level-{level} headline DamageTarget")
    return matches[0]


def _mechanics_target(level:int,*,ac:int=18,damage_immunity:str|None=None)->DamageTarget:
    return replace(
        _headline_target(level),
        name=f"Synthetic damage-mechanics target level {level}",
        ac=ac,
        saves={"strength":0,"dexterity":0,"constitution":0,"intelligence":0,"wisdom":0,"charisma":0},
        magic_resistance=False,
        legendary_resistance=0,
        legendary_resistance_lair=None,
        legendary_resistance_policy="none",
        damage_resistances=frozenset(),
        damage_immunities=frozenset({damage_immunity} if damage_immunity else ()),
        damage_vulnerabilities=frozenset(),
        target_sha256="synthetic-test-only",
    )


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
        self.assertEqual(self.model.projection["schema_version"],"3.1.0")
        self.assertEqual(self.model.projection["projection_version"],authority_module.DAMAGE_PROJECTION_VERSION)
        self.assertEqual(self.model.projection["core"]["action_economy"],{"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False})
        feature_ids=list(self.model.features)
        self.assertEqual(len(feature_ids),len(set(feature_ids)))
        self.assertEqual(set(self.model.disciplines),{"pyrokinesis","cryokinesis","psychokinesis","electrokinesis"})
        self.assertTrue(all(feature["minimum_level"]>=3 and feature["psi_cost"]>=0 for feature in self.model.features.values()))
        self.assertTrue(all("entity_id" in feature for feature in self.model.features.values()))
        self.assertEqual(self.model.disciplines["pyrokinesis"]["graze_damage"],"psionic_ability_modifier")
        self.assertTrue(all("graze_damage" not in discipline for key,discipline in self.model.disciplines.items() if key!="pyrokinesis"))

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
        target=_mechanics_target(7)
        pyro=_strike_packet_options(self.model,target,"pyrokinesis",7,5,8)
        cryo=_strike_packet_options(self.model,target,"cryokinesis",7,5,8)
        self.assertTrue(all(packet[1][0]==5.0 for packet in pyro))
        self.assertTrue(all(packet[1][0]==0.0 for packet in cryo))

    def test_comparator_inputs_are_isolated_minimal_and_fail_closed(self)->None:
        comparators=load_comparators()
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
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value.__setitem__("format_version",1),"format version")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("status","CERTIFIED_BY_ASSERTION"),"review status")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("target_profile_id","legacy_target_rows"),"target profile")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("target_weighting","equal_weight_within_level"),"aggregation")
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

    def test_comparator_config_rejects_unknown_missing_and_incomplete_parameters(self)->None:
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("unused_bonus",1),"damage.battle_master keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].pop("true_strike_uses_per_attack_action"),"damage.eldritch_knight keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["magic_weapon_bonus_by_level"].pop("20"),"magic_weapon_bonus_by_level keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("great_weapon_master_attack_action_bonus","fixed"),"GWM bonus")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maximum_maneuver_dice_per_attack",2),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maneuver_choice_timing","before_attack_roll"),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["tactical_policy"].__setitem__("true_strike_choice_timing","after_attack_roll"),"Eldritch Knight tactical policy")

    def test_damage_target_shape_is_an_isolated_static_projection(self)->None:
        self.assertEqual(set(DamageTarget.__dataclass_fields__),{
            "creature_id","name","ac","saves","magic_resistance","legendary_resistance",
            "legendary_resistance_lair","legendary_resistance_policy","size","creature_type",
            "damage_resistances","damage_immunities","damage_vulnerabilities","hp",
            "source_ruleset","source_page","source_anchor","source_url",
            "catalog_contract_version","catalog_sha256","projection_id","projection_version",
            "requirements_sha256","target_sha256",
        })
        self.assertFalse({"benchmark_level","level","weight"}&set(DamageTarget.__dataclass_fields__))
        entry,target=_headline_bindings()[0]
        self.assertIsInstance(entry,RosterEntry)
        self.assertTrue(target.size and target.creature_type and target.source_anchor)
        self.assertEqual((target.projection_id,target.projection_version),(DAMAGE_PROJECTION_ID,DAMAGE_PROJECTION_VERSION))

    def test_headline_profile_owns_level_order_and_exact_rational_weight(self)->None:
        bindings=_headline_bindings();entries=[entry for entry,_ in bindings]
        self.assertEqual(len(entries),47)
        self.assertEqual(Counter(entry.benchmark_level for entry in entries),Counter({7:12,11:12,15:11,20:12}))
        self.assertEqual([entry.profile_order for entry in entries],list(range(1,48)))
        for level in (7,11,15,20):
            level_entries=[entry for entry in entries if entry.benchmark_level==level]
            self.assertEqual(sum((entry.weight for entry in level_entries),Fraction()),Fraction(1))
            self.assertTrue(all(entry.weight==Fraction(1,len(level_entries)) for entry in level_entries))
        for entry,target in bindings:
            self.assertEqual(entry.creature_id,target.creature_id)
            self.assertEqual(entry.profile_id,HEADLINE_PROFILE_ID)
            self.assertNotIn("benchmark_level",target.__dataclass_fields__)
            self.assertNotIn("weight",target.__dataclass_fields__)

    def test_damage_projection_identity_is_deterministic_and_catalog_bound(self)->None:
        catalog=load_catalog();requirements=load_consumer_requirements(catalog=catalog);entry=_headline_bindings()[0][0]
        first=project_damage_target(entry.creature_id,catalog=catalog,requirements=requirements)
        second=project_damage_target(entry.creature_id,catalog=catalog,requirements=requirements)
        self.assertEqual(first,second)
        self.assertEqual(first.target_sha256,second.target_sha256)
        self.assertEqual(first.catalog_sha256,entry.catalog_sha256)
        self.assertEqual(first.requirements_sha256,requirements.sha256)


class FighterNumericalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators()

    def test_declared_comparator_switches_are_numerically_live(self)->None:
        level=20;target=_mechanics_target(level)
        baseline={build:_comparator_dpr(self.model,self.config,self.comparators,target,level,build) for build in ("battle_master","eldritch_knight")}
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
                self.assertNotAlmostEqual(_comparator_dpr(self.model,self.config,changed,target,level,build),baseline[build],places=9)

    def test_true_strike_choice_uses_current_studied_state_before_the_roll(self)->None:
        target=_mechanics_target(15)
        config=deepcopy(self.config);progression=config["fighter_progression"]["15"];progression["attacks_per_action"]=2;progression["action_slots_by_round"]=[1,1,1]
        probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
            result=_comparator_dpr(self.model,config,self.comparators,target,15,"eldritch_knight")
        self.assertEqual(result,32.0)

    def test_precision_attack_keeps_both_fifty_percent_outcomes_in_the_optimum(self)->None:
        target=_mechanics_target(7,ac=24)
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression["attacks_per_action"]=1;progression["action_slots_by_round"]=[1,1,1]
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            result=_comparator_dpr(self.model,config,self.comparators,target,7,"battle_master")
        self.assertEqual(result,11.0)

    def test_combat_prowess_can_be_retained_after_an_observed_miss(self)->None:
        target=_mechanics_target(20)
        config=deepcopy(self.config);progression=config["fighter_progression"]["20"];progression["attacks_per_action"]=2;progression["action_slots_by_round"]=[1,1,1]
        comparators=deepcopy(self.comparators);battle_master=comparators["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        probabilities=lambda advantage:{20:1.0} if advantage else {1:1.0}
        with patch("harness.damage_harness._natural_probabilities",side_effect=probabilities):
            self.assertEqual(_comparator_dpr(self.model,config,comparators,target,20,"eldritch_knight"),40.0)
            self.assertEqual(_comparator_dpr(self.model,config,comparators,target,20,"battle_master"),38.0)

    def test_gwm_applies_to_each_attack_action_hit_but_not_the_single_hew_attack(self)->None:
        target=_mechanics_target(7,ac=1)
        config=deepcopy(self.config);progression=config["fighter_progression"]["7"];progression.update(attacks_per_action=2,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["7"]=0;battle_master["relentless_minimum_level"]=21;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            main_delta=_comparator_dpr(self.model,config,enabled,target,7,"battle_master")-_comparator_dpr(self.model,config,disabled,target,7,"battle_master")
        self.assertAlmostEqual(main_delta,6.0,places=12)

        progression["attacks_per_action"]=1;battle_master["hew_critical_bonus_attack_once_per_round"]=True
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["great_weapon_master_attack_action_bonus"]="disabled"
        without_hew=deepcopy(enabled);without_hew["damage"]["battle_master"]["hew_critical_bonus_attack_once_per_round"]=False
        with patch("harness.damage_harness._natural_probabilities",return_value={20:1.0}):
            hew_gwm_delta=_comparator_dpr(self.model,config,enabled,target,7,"battle_master")-_comparator_dpr(self.model,config,disabled,target,7,"battle_master")
            single_hew_delta=_comparator_dpr(self.model,config,enabled,target,7,"battle_master")-_comparator_dpr(self.model,config,without_hew,target,7,"battle_master")
        self.assertAlmostEqual(hew_gwm_delta,3.0,places=12)
        self.assertAlmostEqual(single_hew_delta,22.0,places=12)

    def test_relentless_supplies_only_one_free_die_per_turn(self)->None:
        target=_mechanics_target(15,ac=1)
        config=deepcopy(self.config);config["fighter_progression"]["15"].update(attacks_per_action=2,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["15"]=0;battle_master["relentless_minimum_level"]=15;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);disabled["damage"]["battle_master"]["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=_comparator_dpr(self.model,config,enabled,target,15,"battle_master")-_comparator_dpr(self.model,config,disabled,target,15,"battle_master")
        self.assertAlmostEqual(delta,4.5,places=12)

    def test_one_maneuver_die_per_attack_prevents_superiority_relentless_stacking(self)->None:
        target=_mechanics_target(20,ac=1)
        config=deepcopy(self.config);config["fighter_progression"]["20"].update(attacks_per_action=1,action_slots_by_round=[1,1,1],studied_attacks=False,combat_prowess=False)
        enabled=deepcopy(self.comparators);battle_master=enabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=3;battle_master["relentless_minimum_level"]=20;battle_master["hew_critical_bonus_attack_once_per_round"]=False
        disabled=deepcopy(enabled);battle_master=disabled["damage"]["battle_master"];battle_master["superiority_pool_by_level"]["20"]=0;battle_master["relentless_minimum_level"]=21
        with patch("harness.damage_harness._natural_probabilities",return_value={10:1.0}):
            delta=_comparator_dpr(self.model,config,enabled,target,20,"battle_master")-_comparator_dpr(self.model,config,disabled,target,20,"battle_master")
        self.assertAlmostEqual(delta,6.5,places=12)

    def test_failed_attack_bonus_exposes_a_new_observed_prowess_decision(self)->None:
        target=_mechanics_target(20)
        unavailable=deepcopy(self.config);unavailable["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"]=False
        reviewed=_comparator_dpr(self.model,self.config,self.comparators,target,20,"battle_master")
        without_post_failure_choice=_comparator_dpr(self.model,unavailable,self.comparators,target,20,"battle_master")
        self.assertGreater(reviewed,without_post_failure_choice)


class ComparatorLeafContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators()

    def target(self,level:int,*,damage_immunity:str|None=None)->DamageTarget:
        return replace(_mechanics_target(level,damage_immunity=damage_immunity),saves={"strength":12,"dexterity":-2,"constitution":1,"intelligence":2,"wisdom":-1,"charisma":0},magic_resistance=True,size="medium")

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
                    with self.assertRaisesRegex(ValueError,"tactical policy"):_comparator_dpr(self.model,self.config,changed,self.target(level),level,build)
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
            if key not in baselines:baselines[key]=_comparator_dpr(self.model,self.config,self.comparators,target,level,build)
            changed=deepcopy(self.comparators);_set_path(changed,path,replacement)
            with self.subTest(path=_path_label(path)):
                self.assertNotEqual(_comparator_dpr(self.model,self.config,changed,target,level,build),baselines[key])


class DamagePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.base=_mechanics_target(20);cls.mastery=cls.model.projection["core"]["overload"]["mastery"]

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

    def test_observed_state_policy_exposes_aggregate_damage_and_selection_trace(self)->None:
        target=_mechanics_target(20)
        primary,aggregate,selection=_kv_dpr(self.model,self.config,target,20,"electrokinesis",3)
        self.assertGreater(primary,0)
        self.assertGreater(aggregate,primary)
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
    def test_one_level_diagnostic_uses_profile_weights_and_writes_bound_manifest(self)->None:
        def comparator(_model:object,_config:object,_comparators:object,_target:DamageTarget,_level:int,comparator_id:str)->float:
            return 20.0 if comparator_id=="eldritch_knight" else 30.0

        def diagnostic_rows(arguments:tuple[object,...])->list[dict[str,object]]:
            _model,_config,entry,target,discipline,clusters,ek,bm=arguments
            assert isinstance(entry,RosterEntry) and isinstance(target,DamageTarget)
            value=float(entry.profile_order)
            return [{
                "Level":entry.benchmark_level,"Creature ID":target.creature_id,"Target":target.name,
                "Target Profile ID":entry.profile_id,"Target Profile SHA-256":entry.profile_sha256,
                "Target Weight Numerator":entry.weight.numerator,"Target Weight Denominator":entry.weight.denominator,
                "Discipline":discipline,"Cluster Size":cluster,"KV Primary DPR":value,
                "KV Aggregate DPR":value+100.0,"Eldritch Knight DPR":ek,"Battle Master DPR":bm,
                "Selection":"diagnostic-no-evaluator",
            } for cluster in clusters]

        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"damage"
            with patch("harness.damage_harness._comparator_dpr",side_effect=comparator),patch("harness.damage_harness._discipline_damage_rows",side_effect=diagnostic_rows):
                damage=run_damage(DEFAULT_AUTHORITY,output,{15},trials=2,seed=16,workers=1)
            self.assertEqual(set(damage),{"rules_version","detail_rows","matrix_rows","paths","inputs"})
            self.assertEqual(damage["detail_rows"],132)
            self.assertEqual(damage["matrix_rows"],24)
            self.assertEqual(set(damage["paths"]),{"detail_csv","matrix_csv","matrix_markdown","matrix_html","manifest"})
            self.assertTrue(all(path.is_file() for path in damage["paths"].values()))
            self.assertEqual(damage["paths"]["manifest"].name,RUN_MANIFEST_FILENAME)
            detail=damage["paths"]["detail_csv"]
            with detail.open(encoding="utf-8") as stream:
                detail_rows=list(csv.DictReader(stream))
            self.assertEqual(len(detail_rows),132)
            damage_row=detail_rows[0]
            self.assertEqual((damage_row["Target Weight Numerator"],damage_row["Target Weight Denominator"]),("1","11"))
            self.assertEqual(damage_row["Target Profile ID"],HEADLINE_PROFILE_ID)
            self.assertTrue(damage_row["Provenance Comparator Config Sha256"])
            for prefix in ("Primary Target","Aggregate Cluster"):
                self.assertEqual(damage_row[f"{prefix} Lower Comparator"],"Eldritch Knight")
                self.assertEqual(damage_row[f"{prefix} Upper Comparator"],"Battle Master")
                self.assertEqual(damage_row[f"{prefix} Lower Boundary"],"20.000000")
                self.assertEqual(damage_row[f"{prefix} Upper Boundary"],"30.000000")
                self.assertIn(damage_row[f"{prefix} Band"],BANDS)
            self.assertEqual({key:damage_row[key] for key in NOTICE_COLUMNS},NOTICE_COLUMNS)
            status=load_config()["methodology"]["status"]
            with damage["paths"]["matrix_csv"].open(encoding="utf-8") as stream:
                matrix_rows=list(csv.DictReader(stream))
            self.assertEqual(len(matrix_rows),24)
            entries=[entry for entry,_ in _headline_bindings({15})]
            weighted_order=sum((entry.weight*entry.profile_order for entry in entries),Fraction())
            self.assertEqual(weighted_order,Fraction(30))
            self.assertTrue(all(row["Provenance Status"]==status for row in matrix_rows))
            self.assertTrue(all({key:row[key] for key in NOTICE_COLUMNS}==NOTICE_COLUMNS for row in matrix_rows))
            self.assertTrue(all(row["Provenance Evaluator"]==DAMAGE_EVALUATOR_ID for row in matrix_rows))
            self.assertTrue(all(row["Provenance Trial Seed Role"]=="historical_compatibility_metadata" for row in matrix_rows))
            self.assertTrue(all(row["Benchmark Type"]=="Damage" for row in matrix_rows))
            for row in matrix_rows:
                expected=weighted_order+(100 if row["Damage Scope"]=="aggregate cluster DPR" else 0)
                self.assertEqual(row["KV"],f"{float(expected):.6f}")
                self.assertEqual(row["Eldritch Knight"],"20.000000")
                self.assertEqual(row["Battle Master"],"30.000000")
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
            self.assertIn(status,damage["paths"]["matrix_markdown"].read_text(encoding="utf-8"))
            self.assertIn(status,damage["paths"]["matrix_html"].read_text(encoding="utf-8"))

            inputs=damage["inputs"]
            self.assertEqual(set(inputs),{
                "damage_result_contract_version","rules_version","authority_sha256",
                "catalog_contract_version","catalog_sha256","roster_contract_version","roster_sha256",
                "target_profile_id","target_profile_version","target_profile_sha256",
                "damage_target_projection_id","damage_target_projection_version","damage_target_projection_sha256",
                "consumer_requirements_version","consumer_requirements_sha256","config_sha256",
                "comparator_config_sha256","evaluator","evaluator_implementation_sha256","trials","seed",
                "trial_seed_role","aggregation","status",
            })
            self.assertEqual(inputs["damage_result_contract_version"],DAMAGE_RESULT_CONTRACT_VERSION)
            self.assertEqual(inputs["target_profile_id"],HEADLINE_PROFILE_ID)
            self.assertEqual(inputs["damage_target_projection_id"],DAMAGE_PROJECTION_ID)
            self.assertEqual(inputs["damage_target_projection_version"],DAMAGE_PROJECTION_VERSION)
            self.assertEqual(inputs["evaluator"],DAMAGE_EVALUATOR_ID)
            self.assertEqual((inputs["trials"],inputs["seed"]),(2,16))
            self.assertEqual(inputs["aggregation"],"exact rational target-profile weights; percentages from displayed aggregates")
            self.assertTrue(all(inputs[key] for key in ("catalog_sha256","roster_sha256","target_profile_sha256","damage_target_projection_sha256","consumer_requirements_sha256")))
            self.assertEqual(
                {key:damage_row[key] for key in (
                    f"Provenance {str(name).replace('_',' ').title()}" for name in inputs
                )},
                {f"Provenance {str(name).replace('_',' ').title()}":str(value) for name,value in inputs.items()},
            )

            manifest=json.loads(damage["paths"]["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(set(manifest),{"format_version","damage_result_contract_version","inputs","outputs","row_counts"})
            self.assertEqual(manifest["damage_result_contract_version"],DAMAGE_RESULT_CONTRACT_VERSION)
            self.assertEqual(manifest["inputs"],inputs)
            self.assertEqual(manifest["row_counts"],{"detail":132,"matrix":24})
            self.assertEqual(set(manifest["outputs"]),{"detail_csv","matrix_csv","matrix_markdown","matrix_html"})
            for output_identity in manifest["outputs"].values():
                self.assertEqual(set(output_identity),{"file","sha256"})
                self.assertRegex(output_identity["sha256"],r"^[0-9a-f]{64}$")

    def test_evaluator_implementation_digest_binds_every_result_module(self)->None:
        self.assertEqual(
            [label for label,_ in DAMAGE_EVALUATOR_IMPLEMENTATION_PATHS],
            [
                "harness/authority.py",
                "harness/creature_catalog.py",
                "harness/damage_harness.py",
                "harness/damage_report.py",
                "harness/model.py",
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=root/"model.py";report=root/"damage_report.py"
            model.write_text("model-v1\n",encoding="utf-8");report.write_text("report-v1\n",encoding="utf-8")
            paths=(("harness/damage_report.py",report),("harness/model.py",model))
            original=evaluator_implementation_sha256(paths)
            model.write_text("model-v2\n",encoding="utf-8")
            self.assertNotEqual(evaluator_implementation_sha256(paths),original)
            changed=evaluator_implementation_sha256(paths)
            report.write_text("report-v2\n",encoding="utf-8")
            self.assertNotEqual(evaluator_implementation_sha256(paths),changed)

    def test_imports_outputs_and_archive_are_not_positive_inputs_or_tracked(self)->None:
        inputs=json.loads((PROJECT_ROOT/"build"/"inputs.json").read_text(encoding="utf-8"))["inputs"]
        paths=[item["path"] for item in inputs]
        self.assertTrue(all(not path.startswith(".codex-import/") and "results" not in path and not path.endswith(".zip") for path in paths))
        tracked=subprocess.run(["git","ls-files"],cwd=PROJECT_ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
        self.assertTrue(all(not path.startswith(".codex-import/") and not path.endswith("harness-import.zip") for path in tracked))


if __name__=="__main__":unittest.main()
