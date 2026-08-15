from __future__ import annotations

import csv
import json
import multiprocessing
import pickle
import subprocess
import tempfile
import unittest
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import harness.authority as authority_module
from harness.authority import AuthorityError,DamageAuthorityModel,DEFAULT_AUTHORITY,PROJECT_ROOT
from harness.creature_catalog import HEADLINE_PROFILE_ID,RosterEntry,load_catalog,load_consumer_requirements,load_profile
from harness.creature_damage_projection import DAMAGE_PROJECTION_ID,DAMAGE_PROJECTION_VERSION,DamageTarget,project_damage_target,project_profile_damage_targets
from harness.damage_contract import ACTION_KINDS,PROVIDER_IDS,ActionKind,DamageSolution,DamageValue,ExactTransition,NOMINAL_MODE_ID,NominalKernel,Proposal,ProviderId,ResourceCost,TargetKnowledge,UnsupportedDamageMode,apply_defense,attack_outcome_distribution,die_distribution,manifested_strike_packet_options,reject_unsupported_mode,save_success_probability,solve_comparator,solve_kinetic_vanguard
from harness.damage_report import BANDS,COMPARATOR_NOTICE,LEGAL_NOTICES,NOTICE_COLUMNS,PROJECT_ATTRIBUTION_NOTICE,SRD_ATTRIBUTION_NOTICE,SRD_MODIFICATION_NOTICE,SRD_SECTION_5_NOTICE,VALUE_COLUMNS,classify_envelope,damage_matrix_row,write_damage_matrix
from harness.damage_harness import DAMAGE_EVALUATOR_ID,DAMAGE_ORCHESTRATION_IMPLEMENTATION_PATHS,DAMAGE_REPORTER_IMPLEMENTATION_PATHS,DAMAGE_RESULT_CONTRACT_VERSION,DAMAGE_SEMANTIC_IMPLEMENTATION_PATHS,RUN_MANIFEST_FILENAME,implementation_sha256,run as run_damage
from harness.model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,load_comparators,load_config


_HEADLINE_BINDINGS:tuple[tuple[RosterEntry,DamageTarget],...]|None=None


def _headline_bindings(levels:set[int]|None=None)->tuple[tuple[RosterEntry,DamageTarget],...]:
    global _HEADLINE_BINDINGS
    if _HEADLINE_BINDINGS is None:
        catalog=load_catalog();requirements=load_consumer_requirements(catalog=catalog);entries=load_profile(HEADLINE_PROFILE_ID,catalog=catalog)
        _HEADLINE_BINDINGS=tuple(project_profile_damage_targets(entries,catalog=catalog,requirements=requirements))
    if levels is None:return _HEADLINE_BINDINGS
    return tuple(binding for binding in _HEADLINE_BINDINGS if binding[0].benchmark_level in levels)


def _inspect_damage_worker_argument(arguments:tuple[object,...])->tuple[object,...]:
    model,config,entry,target,discipline,clusters,eldritch_knight,battle_master=arguments
    assert isinstance(model,DamageAuthorityModel)
    assert isinstance(config,dict)
    assert isinstance(entry,RosterEntry)
    assert isinstance(target,DamageTarget)
    assert isinstance(discipline,str)
    assert isinstance(clusters,list)
    target.validate_identity()
    return (
        model.rules_version,
        config["methodology"]["status"],
        entry.creature_id,
        target.creature_id,
        target.target_sha256,
        discipline,
        tuple(clusters),
        eldritch_knight,
        battle_master,
        tuple(target.saves.items()),
    )


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


def _mechanics_knowledge(level:int,*,ac:int=18)->TargetKnowledge:
    return replace(
        TargetKnowledge.from_damage_target(_headline_target(level)),
        ac=ac,
        saves=(("charisma",0),("constitution",0),("dexterity",0),("intelligence",0),("strength",0),("wisdom",0)),
        magic_resistance=False,
        legendary_resistance=0,
        legendary_resistance_lair=None,
        legendary_resistance_policy="metadata_only",
        damage_resistances=frozenset(),
        damage_immunities=frozenset(),
        damage_vulnerabilities=frozenset(),
    )


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
        knowledge=_mechanics_knowledge(7)
        pyro=manifested_strike_packet_options(self.model,knowledge,"pyrokinesis",5,8)
        cryo=manifested_strike_packet_options(self.model,knowledge,"cryokinesis",5,8)
        self.assertTrue(all(packet[1][0]==5 for packet in pyro))
        self.assertTrue(all(packet[1][0]==0 for packet in cryo))

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
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("target_death",True),"target-death")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("ally_turns",True),"ally-turn")
        self.assert_json_rejected(DEFAULT_CONFIG,load_config,lambda value:value["methodology"].__setitem__("legal_positioning_assumed",False),"positioning")
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
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].pop("true_strike_maximum_uses_per_attack_action"),"damage.eldritch_knight keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["magic_weapon_bonus_by_level"].pop("20"),"magic_weapon_bonus_by_level keys")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"].__setitem__("great_weapon_master_attack_action_bonus","fixed"),"GWM bonus")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maximum_maneuver_dice_per_attack",2),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["battle_master"]["tactical_policy"].__setitem__("maneuver_choice_timing","before_attack_roll"),"Battle Master tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"]["tactical_policy"].__setitem__("true_strike_choice_timing","after_attack_roll"),"Eldritch Knight tactical policy")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].__setitem__("true_strike_maximum_uses_per_attack_action",0),"maximum must be exactly one")
        self.assert_json_rejected(DEFAULT_COMPARATORS,load_comparators,lambda value:value["damage"]["eldritch_knight"].__setitem__("true_strike_maximum_uses_per_attack_action",2),"maximum must be exactly one")

    def test_damage_target_shape_is_an_isolated_static_projection(self)->None:
        self.assertEqual(set(DamageTarget.__dataclass_fields__),{
            "creature_id","name","ac","saves","magic_resistance","legendary_resistance",
            "legendary_resistance_lair","legendary_resistance_policy","size","creature_type",
            "damage_resistances","damage_immunities","damage_vulnerabilities","hp",
            "source_ruleset","source_page","source_anchor","source_url",
            "catalog_contract_version","catalog_sha256","projection_id","projection_version",
            "damage_consumer_requirements_sha256","target_sha256",
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
        self.assertEqual(
            first.damage_consumer_requirements_sha256,
            requirements.sha256_for("damage_target"),
        )


class ExactNominalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=DamageAuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators()

    def test_target_knowledge_is_identical_static_surface_without_hp(self)->None:
        target=_headline_target(7)
        views=[TargetKnowledge.from_damage_target(target) for _ in range(3)]
        self.assertEqual(views[0],views[1]);self.assertEqual(views[1],views[2])
        self.assertNotIn("hp",TargetKnowledge.__dataclass_fields__)
        self.assertEqual(views[0].contract_id,"declared_static_target_knowledge_v1")
        self.assertRegex(views[0].digest,r"^[0-9a-f]{64}$")

    def test_exact_attack_save_and_defense_primitives_match_frozen_arithmetic(self)->None:
        target=_mechanics_knowledge(7,ac=15)
        self.assertEqual(dict(attack_outcome_distribution(target,5)),{"miss":Fraction(9,20),"hit":Fraction(1,2),"critical":Fraction(1,20)})
        self.assertEqual(sum(probability for _,probability in die_distribution(2,6)),1)
        mr=replace(target,magic_resistance=True,saves=tuple((key,4 if key=="charisma" else value) for key,value in target.saves))
        self.assertEqual(save_success_probability(mr,"charisma",15),Fraction(3,4))
        knowledge=replace(target,damage_resistances=frozenset({"fire"}))
        self.assertEqual([apply_defense(knowledge,"fire",value) for value in range(2,8)],[1,1,2,2,3,3])

    def test_nominal_kernel_uses_full_cost_order_then_canonical_id(self)->None:
        damage=DamageValue(Fraction(5),Fraction(10))
        self.assertEqual(NominalKernel.choose((Proposal("tie_probe.b",damage),Proposal("tie_probe.a",damage))).action_id,"tie_probe.a")
        expensive=DamageValue(Fraction(5),Fraction(10),ResourceCost(refreshable=Fraction(1)))
        self.assertEqual(NominalKernel.choose((Proposal("tie_probe.a",expensive),Proposal("tie_probe.z",damage))).action_id,"tie_probe.z")
        with self.assertRaisesRegex(ValueError,"duplicate canonical action IDs"):
            NominalKernel.choose((Proposal("tie_probe.same",damage),Proposal("tie_probe.same",damage)))
        with self.assertRaisesRegex(ValueError,"outside the closed damage vocabulary"):
            Proposal("unsupported.action",damage)

    def test_closed_provider_action_and_immutable_value_contracts(self)->None:
        self.assertEqual(PROVIDER_IDS,tuple(item.value for item in ProviderId))
        self.assertEqual(ACTION_KINDS,tuple(item.value for item in ActionKind))
        target=_mechanics_knowledge(7)
        values=(target,ResourceCost(),DamageValue(),ExactTransition(Fraction(1),DamageValue()),Proposal("tie_probe.probe",DamageValue()))
        self.assertTrue(all(not hasattr(value,"__dict__") for value in values))
        with self.assertRaisesRegex(TypeError,"exact Fraction"):
            DamageValue(1.0,Fraction(1))  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError,"canonical immutable exact values"):
            NominalKernel(ProviderId.BATTLE_MASTER).memoized_value("probe",(["mutable"],),lambda:DamageValue())  # type: ignore[list-item]

        kernel=NominalKernel(ProviderId.ELDRITCH_KNIGHT)
        calls=0
        expected=DamageValue(Fraction(1),Fraction(2))
        def compute()->DamageValue:
            nonlocal calls;calls+=1;return expected
        self.assertEqual(kernel.memoized_value("probe",("state",),compute),expected)
        self.assertEqual(kernel.memoized_value("probe",("state",),compute),expected)
        self.assertEqual(calls,1)
        self.assertEqual(kernel.cache_info.hits,1);self.assertEqual(kernel.cache_info.misses,1)

    def test_exact_transition_kernel_coalesces_immutable_successors(self)->None:
        transitions=(
            ExactTransition(Fraction(1,4),DamageValue(Fraction(2),Fraction(3)),("next",)),
            ExactTransition(Fraction(1,4),DamageValue(Fraction(2),Fraction(3)),("next",)),
            ExactTransition(Fraction(1,2),DamageValue(Fraction(4),Fraction(5)),None),
        )
        continuations={None:DamageValue(),("next",):DamageValue(Fraction(1),Fraction(2))}
        self.assertEqual(
            NominalKernel.transition_value(transitions,continuations.__getitem__),
            DamageValue(Fraction(7,2),Fraction(5)),
        )
        with self.assertRaisesRegex(TypeError,"immutable tuple"):
            NominalKernel.transition_value(
                (ExactTransition(Fraction(1),DamageValue(),["mutable"]),),  # type: ignore[arg-type]
                continuations.__getitem__,
            )

    def test_finite_modes_fail_closed_before_provider_evaluation(self)->None:
        for mode in ("finite_hp_removed_v1","finite_hp_kill_cleave_v1","finite_hp"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(UnsupportedDamageMode,"separately authorized PR2"):reject_unsupported_mode(mode)
        reject_unsupported_mode(NOMINAL_MODE_ID)

    def test_three_public_providers_return_exact_bound_solutions_on_one_target(self)->None:
        target=_headline_target(7)
        solutions=[
            solve_kinetic_vanguard(self.model,self.config,target,7,"pyrokinesis",1),
            solve_comparator(self.model,self.config,self.comparators,target,7,"battle_master"),
            solve_comparator(self.model,self.config,self.comparators,target,7,"eldritch_knight"),
        ]
        self.assertEqual([solution.provider_id for solution in solutions],["kinetic_vanguard","battle_master","eldritch_knight"])
        for solution in solutions:
            self.assertIsInstance(solution.primary_dpr,Fraction);self.assertIsInstance(solution.aggregate_dpr,Fraction)
            self.assertEqual(solution.mode_id,NOMINAL_MODE_ID);self.assertRegex(solution.policy_digest,r"^[0-9a-f]{64}$")
            self.assertTrue(solution.trace);self.assertTrue(solution.stats)
        self.assertIn("representative=locally-modal-path",solutions[0].trace)
        self.assertFalse(any(item.startswith("cluster=") for item in solutions[0].trace))


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
    def test_damage_target_pickle_round_trip_preserves_identity_and_immutability(self)->None:
        target=_headline_bindings({7})[0][1]
        restored=pickle.loads(pickle.dumps(target,protocol=pickle.HIGHEST_PROTOCOL))
        self.assertEqual(restored,target)
        self.assertEqual(restored.target_sha256,target.target_sha256)
        self.assertEqual(dict(restored.saves),dict(target.saves))
        restored.validate_identity()
        with self.assertRaises(TypeError):
            restored.saves["strength"]=99  # type: ignore[index]

    def test_damage_worker_argument_crosses_spawned_executor_without_evaluation(self)->None:
        model=DamageAuthorityModel.load();config=load_config();entry,target=_headline_bindings({7})[0]
        arguments=(model,config,entry,target,"pyrokinesis",[1],20.0,30.0)
        expected=(
            model.rules_version,
            config["methodology"]["status"],
            entry.creature_id,
            target.creature_id,
            target.target_sha256,
            "pyrokinesis",
            (1,),
            20.0,
            30.0,
            tuple(target.saves.items()),
        )
        with ProcessPoolExecutor(
            max_workers=1,
            max_tasks_per_child=1,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            self.assertEqual(executor.submit(_inspect_damage_worker_argument,arguments).result(timeout=60),expected)

    def test_one_level_diagnostic_uses_profile_weights_and_writes_bound_manifest(self)->None:
        def comparator(_model:object,_config:object,_comparators:object,target:DamageTarget,_level:int,comparator_id:str)->DamageSolution:
            value=Fraction(20 if comparator_id=="eldritch_knight" else 30)
            return DamageSolution(NOMINAL_MODE_ID,comparator_id,TargetKnowledge.from_damage_target(target).digest,value,value,"0"*64,("diagnostic",),(("states",0),))

        def diagnostic_rows(arguments:tuple[object,...])->list[dict[str,object]]:
            _model,_config,entry,target,discipline,clusters,ek,bm=arguments
            assert isinstance(entry,RosterEntry) and isinstance(target,DamageTarget)
            value=Fraction(entry.profile_order)
            return [{
                "Level":entry.benchmark_level,"Creature ID":target.creature_id,"Target":target.name,
                "Target Profile ID":entry.profile_id,"Target Profile SHA-256":entry.profile_sha256,
                "Target Weight Numerator":entry.weight.numerator,"Target Weight Denominator":entry.weight.denominator,
                "Discipline":discipline,"Cluster Size":cluster,"KV Primary DPR":f"{float(value):.6f}","KV Primary DPR Exact":str(value),
                "KV Aggregate DPR":f"{float(value+100):.6f}","KV Aggregate DPR Exact":str(value+100),
                "Eldritch Knight DPR":f"{float(ek.primary_dpr):.6f}","Eldritch Knight DPR Exact":str(ek.primary_dpr),
                "Battle Master DPR":f"{float(bm.primary_dpr):.6f}","Battle Master DPR Exact":str(bm.primary_dpr),
                "KV Policy Digest":"1"*64,"Eldritch Knight Policy Digest":ek.policy_digest,"Battle Master Policy Digest":bm.policy_digest,
                "Selection":"diagnostic-no-evaluator","Eldritch Knight Trace":ek.selection,"Battle Master Trace":bm.selection,
            } for cluster in clusters]

        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"damage"
            with patch("harness.damage_harness.solve_comparator",side_effect=comparator),patch("harness.damage_harness._discipline_damage_rows",side_effect=diagnostic_rows):
                damage=run_damage(DEFAULT_AUTHORITY,output,{15},trials=2,seed=16,workers=1)
            self.assertEqual(set(damage),{"rules_version","mode_id","detail_rows","matrix_rows","paths","inputs"})
            self.assertEqual(damage["mode_id"],NOMINAL_MODE_ID)
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
                self.assertEqual(row["KV Exact"],str(expected))
                self.assertEqual(row["Eldritch Knight"],"20.000000")
                self.assertEqual(row["Eldritch Knight Exact"],"20")
                self.assertEqual(row["Battle Master"],"30.000000")
                self.assertEqual(row["Battle Master Exact"],"30")
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
                "damage_result_contract_version","damage_model_mode_id","target_knowledge_contract_id","numeric_representation_id","provider_ids","rules_version","authority_sha256","authority_projection_sha256",
                "catalog_contract_version","catalog_sha256","roster_contract_version","roster_sha256",
                "target_profile_id","target_profile_version","target_profile_sha256",
                "damage_target_projection_id","damage_target_projection_version","damage_target_projection_sha256",
                "consumer_requirements_version","damage_consumer_requirements_sha256","config_sha256",
                "comparator_config_sha256","damage_model_contract_sha256","sentinel_corpus_sha256","sentinel_corpus_file_sha256","observation_policy_sha256","resource_policy_sha256","optimization_policy_sha256",
                "evaluator","evaluator_implementation_sha256","semantic_implementation_sha256","orchestration_implementation_sha256","reporter_implementation_sha256","trials","seed",
                "trial_seed_role","aggregation","status",
            })
            self.assertEqual(inputs["damage_result_contract_version"],DAMAGE_RESULT_CONTRACT_VERSION)
            self.assertEqual(inputs["target_profile_id"],HEADLINE_PROFILE_ID)
            self.assertEqual(inputs["damage_target_projection_id"],DAMAGE_PROJECTION_ID)
            self.assertEqual(inputs["damage_target_projection_version"],DAMAGE_PROJECTION_VERSION)
            self.assertEqual(inputs["evaluator"],DAMAGE_EVALUATOR_ID)
            self.assertEqual(inputs["damage_model_mode_id"],NOMINAL_MODE_ID)
            self.assertEqual((inputs["trials"],inputs["seed"]),(2,16))
            self.assertEqual(inputs["aggregation"],"exact rational target-profile weights; deterministic half-even display boundary")
            self.assertTrue(all(inputs[key] for key in ("catalog_sha256","roster_sha256","target_profile_sha256","damage_target_projection_sha256","damage_consumer_requirements_sha256")))
            self.assertEqual(
                {key:damage_row[key] for key in (
                    f"Provenance {str(name).replace('_',' ').title()}" for name in inputs
                )},
                {f"Provenance {str(name).replace('_',' ').title()}":str(value) for name,value in inputs.items()},
            )

            manifest=json.loads(damage["paths"]["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(set(manifest),{"format_version","damage_result_contract_version","inputs","outputs","row_counts"})
            self.assertEqual(manifest["format_version"],2)
            self.assertEqual(manifest["damage_result_contract_version"],DAMAGE_RESULT_CONTRACT_VERSION)
            self.assertEqual(manifest["inputs"],inputs)
            self.assertEqual(manifest["row_counts"],{"detail":132,"matrix":24})
            self.assertEqual(set(manifest["outputs"]),{"detail_csv","matrix_csv","matrix_markdown","matrix_html"})
            for output_identity in manifest["outputs"].values():
                self.assertEqual(set(output_identity),{"file","sha256"})
                self.assertRegex(output_identity["sha256"],r"^[0-9a-f]{64}$")

    def test_split_implementation_digests_bind_semantics_orchestration_and_reporter(self)->None:
        self.assertEqual([label for label,_ in DAMAGE_SEMANTIC_IMPLEMENTATION_PATHS],["harness/authority.py","harness/damage_contract.py"])
        self.assertEqual([label for label,_ in DAMAGE_ORCHESTRATION_IMPLEMENTATION_PATHS],["harness/damage_harness.py","harness/model.py"])
        self.assertEqual([label for label,_ in DAMAGE_REPORTER_IMPLEMENTATION_PATHS],["harness/damage_report.py"])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=root/"model.py";report=root/"damage_report.py"
            model.write_text("model-v1\n",encoding="utf-8");report.write_text("report-v1\n",encoding="utf-8")
            paths=(("harness/damage_report.py",report),("harness/model.py",model))
            original=implementation_sha256(paths)
            model.write_text("model-v2\n",encoding="utf-8")
            self.assertNotEqual(implementation_sha256(paths),original)
            changed=implementation_sha256(paths)
            report.write_text("report-v2\n",encoding="utf-8")
            self.assertNotEqual(implementation_sha256(paths),changed)

    def test_imports_outputs_and_archive_are_not_positive_inputs_or_tracked(self)->None:
        inputs=json.loads((PROJECT_ROOT/"build"/"inputs.json").read_text(encoding="utf-8"))["inputs"]
        paths=[item["path"] for item in inputs]
        self.assertTrue(all(not path.startswith(".codex-import/") and "results" not in path and not path.endswith(".zip") for path in paths))
        tracked=subprocess.run(["git","ls-files"],cwd=PROJECT_ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
        self.assertTrue(all(not path.startswith(".codex-import/") and not path.endswith("harness-import.zip") for path in tracked))


if __name__=="__main__":unittest.main()
