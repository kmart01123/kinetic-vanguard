from __future__ import annotations

import json
import unittest
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from harness.authority import AuthorityModel
from harness.control_harness import _comparator_scenario,_composed_eldritch_knight_scenarios,_eldritch_strike_primer_probability,_finite_penalty_save_failure_probability,_finite_penalty_with_disadvantage_probability,_kv_scenario
from harness.control_value import PrimitiveExposure,decompose_label,expose_label,fixed_exposure,instantaneous_exposure,load_primitive_catalog,normalize_exposures,repeat_save_exposure,shadow_rows
from harness.model import Target,ability_check_success_probability,attack_probabilities,load_comparators,load_config,modified_save_success_probability,save_success_probability


def target(*immunities:str)->Target:
    return Target(20,"Sentinel",18,{"strength":5,"dexterity":3,"constitution":5,"intelligence":1,"wisdom":2,"charisma":1},False,0,"large","monstrosity",frozenset(immunities),frozenset(),frozenset(),frozenset(),200,"SRD 5.2.1","1","https://example.invalid")


class PrimitiveDecompositionTests(unittest.TestCase):
    def ids(self,label:str)->list[str]:
        return [item.primitive_id for item in decompose_label(label)]

    def test_blinded_keeps_distinct_mechanical_consequences(self)->None:
        self.assertEqual(self.ids("Blinded"),["sight_option_denial","ability_check_impairment","offensive_impairment_all_attacks","defensive_attack_advantage"])

    def test_source_scopes_keep_srd_conditions_separate_from_generic_and_comparator_semantics(self)->None:
        source=load_primitive_catalog()["source"]
        self.assertEqual(source["condition_definitions"]["ruleset"],"SRD 5.2.1")
        self.assertEqual(source["analytical_primitives"],"project-authored generic benchmark semantics")
        self.assertEqual(source["comparator_packages"],"independently expressed mechanical abstractions from sanitized GitHub rulings")

    def test_incapacitated_and_stunned_expand_without_inventing_speed_zero(self)->None:
        incapacitated=self.ids("Incapacitated");stunned=decompose_label("Stunned")
        self.assertIn("active_turn_denial",incapacitated);self.assertIn("reaction_denial",incapacitated);self.assertNotIn("mobility_loss_feet",incapacitated)
        self.assertEqual([item.primitive_id for item in stunned].count("active_turn_denial"),1);self.assertEqual([item.primitive_id for item in stunned].count("reaction_denial"),1)
        self.assertEqual([dict(item.qualifiers)["save_ability"] for item in stunned if item.primitive_id=="save_auto_failure"],["strength","dexterity"])
        self.assertNotIn("mobility_loss_feet",[item.primitive_id for item in stunned])

    def test_restrained_frightened_and_prone_remain_mechanically_honest(self)->None:
        restrained=decompose_label("Restrained");self.assertEqual({item.primitive_id for item in restrained},{"mobility_loss_feet","defensive_attack_advantage","offensive_impairment_all_attacks","save_disadvantage"})
        frightened=decompose_label("Frightened");geometry=next(item for item in frightened if item.primitive_id=="geometry_sensitive_approach_restriction");self.assertEqual(geometry.pricing_status,"context_required")
        prone=decompose_label("Prone");offense=next(item for item in prone if item.primitive_id=="offensive_impairment_all_attacks");self.assertEqual(offense.pricing_status,"context_required")

    def test_bare_outcomes_retain_scope_and_magnitude(self)->None:
        self.assertEqual(decompose_label("attack_disadvantage",attack_scope="next_attack")[0].primitive_id,"offensive_impairment_next_attack")
        speed_zero=decompose_label("Speed 0")[0];self.assertEqual(speed_zero.primitive_id,"mobility_loss_feet");self.assertEqual(dict(speed_zero.qualifiers)["mobility_effect"],"speed_zero")
        reduction=decompose_label("speed_reduction",magnitude_feet=10)[0];self.assertEqual(reduction.magnitude,10);self.assertEqual(dict(reduction.qualifiers)["mobility_effect"],"flat_reduction")
        displacement=decompose_label("forced_movement",magnitude_feet=20)[0];self.assertEqual(displacement.primitive_id,"forced_displacement");self.assertEqual(displacement.magnitude,20)
        self.assertEqual(decompose_label("forced_movement")[0].pricing_status,"unsupported")

    def test_poisoned_and_paralyzed_are_faithful_and_distinct_from_stunned(self)->None:
        poisoned=decompose_label("Poisoned");self.assertEqual([item.primitive_id for item in poisoned],["offensive_impairment_all_attacks","ability_check_impairment"]);self.assertEqual(poisoned[0].pricing_status,"candidate");self.assertEqual(poisoned[1].pricing_status,"context_required")
        paralyzed=decompose_label("Paralyzed");ids=[item.primitive_id for item in paralyzed]
        self.assertEqual(ids.count("active_turn_denial"),1);self.assertEqual(ids.count("reaction_denial"),1);self.assertEqual(ids.count("mobility_loss_feet"),1);self.assertEqual(ids.count("defensive_attack_advantage"),1);self.assertEqual(ids.count("melee_hit_auto_critical_context"),1)
        self.assertEqual([dict(item.qualifiers)["save_ability"] for item in paralyzed if item.primitive_id=="save_auto_failure"],["strength","dexterity"])
        critical=next(item for item in paralyzed if item.primitive_id=="melee_hit_auto_critical_context");self.assertEqual(critical.pricing_status,"context_required");self.assertEqual(dict(critical.qualifiers)["attacker_distance"],"within_5_feet")
        self.assertNotIn("mobility_loss_feet",self.ids("Stunned"))

    def test_unconscious_includes_each_mechanical_consequence_without_duplication(self)->None:
        rows=decompose_label("Unconscious");ids=[item.primitive_id for item in rows]
        for primitive in ("active_turn_denial","reaction_denial","mobility_loss_feet","defensive_attack_advantage","melee_hit_auto_critical_context","awareness_denial"):
            self.assertEqual(ids.count(primitive),1,primitive)
        self.assertEqual([dict(item.qualifiers)["save_ability"] for item in rows if item.primitive_id=="save_auto_failure"],["strength","dexterity"])
        self.assertEqual(ids.count("fall_transition"),1);self.assertEqual(ids.count("prone_incoming_attack_context"),1)
        critical=next(item for item in rows if item.primitive_id=="melee_hit_auto_critical_context");awareness=next(item for item in rows if item.primitive_id=="awareness_denial")
        self.assertEqual(critical.pricing_status,"context_required");self.assertEqual(awareness.pricing_status,"context_required")


class ExposureMathTests(unittest.TestCase):
    def test_closed_form_exposure_helpers(self)->None:
        self.assertEqual(fixed_exposure(0.0,3),(0.0,0.0,0.0));self.assertEqual(fixed_exposure(0.4,1),(0.4,))
        self.assertEqual(fixed_exposure(0.4,3),(0.4,0.4,0.4));self.assertEqual(repeat_save_exposure(0.5,0.5,3,checkpoint_side="after_scored_window"),(0.5,0.25,0.125));self.assertEqual(repeat_save_exposure(0.5,0.5,3,checkpoint_side="before_scored_window"),(0.25,0.125,0.0625));self.assertEqual(instantaneous_exposure(0.5,20),10)

    def test_repeat_save_and_instantaneous_expected_exposure_are_hand_computable(self)->None:
        repeated=expose_label("probe","restrained",0.5,"one_minute_concentration",repeat_survival_probability=0.5,repeat_checkpoint="start_of_affected_turn")
        offense=next(item for item in repeated if item.primitive_id=="offensive_impairment_all_attacks");self.assertEqual(offense.active_probabilities,(0.25,0.125,0.0625));self.assertEqual(offense.expected_exposure,0.4375)
        advantage=next(item for item in repeated if item.primitive_id=="defensive_attack_advantage");self.assertEqual(advantage.pricing_status,"context_required");self.assertFalse(advantage.active_probabilities);self.assertIsNone(advantage.expected_exposure)
        movement=expose_label("probe","forced_movement",0.5,"instantaneous",magnitude_feet=20)[0];self.assertEqual(movement.expected_exposure,10)

    def test_repeat_save_without_a_supported_checkpoint_fails_closed(self)->None:
        rows=expose_label("probe","restrained",0.5,"one_minute_concentration",repeat_survival_probability=0.5)
        self.assertTrue(rows);self.assertTrue(all(item.pricing_status in {"context_required","unsupported"} and item.expected_exposure is None and not item.active_probabilities for item in rows))

    def test_end_of_turn_repeat_save_scores_only_target_turns_before_the_checkpoint(self)->None:
        rows=expose_label("hold","paralyzed",0.5,"one_minute_concentration",repeat_survival_probability=0.5,repeat_checkpoint="end_of_affected_turn")
        turn=next(item for item in rows if item.primitive_id=="active_turn_denial");self.assertEqual(turn.active_probabilities,(0.5,0.25,0.125));self.assertEqual(turn.expected_exposure,0.875)
        incoming=next(item for item in rows if item.primitive_id=="defensive_attack_advantage");self.assertEqual(incoming.pricing_status,"context_required");self.assertFalse(incoming.active_probabilities);self.assertIsNone(incoming.expected_exposure)

    def test_unknown_timing_fails_closed(self)->None:
        rows=expose_label("probe","blinded",0.5,None);self.assertTrue(rows);self.assertTrue(all(item.pricing_status=="unsupported" and item.expected_exposure is None and not item.active_probabilities for item in rows))


class NormalizationTests(unittest.TestCase):
    def normalized(self,*groups:tuple[PrimitiveExposure,...])->tuple[PrimitiveExposure,...]:
        return normalize_exposures(item for group in groups for item in group)

    def test_duplicate_boolean_primitives_collapse_with_diagnostics(self)->None:
        rows=self.normalized(expose_label("one","reaction_denial",0.6,"until_start_next_turn"),expose_label("two","reaction_denial",0.6,"until_start_next_turn"))
        self.assertEqual(sum(item.normalization_disposition=="retained" for item in rows),1);self.assertEqual(sum(item.normalization_disposition=="suppressed" for item in rows),1);self.assertTrue(next(item for item in rows if item.normalization_disposition=="suppressed").suppressed_by)

    def test_turn_denial_suppresses_lesser_offense(self)->None:
        rows=self.normalized(expose_label("stun","stunned",0.5,"until_end_next_turn"),expose_label("sap","attack_disadvantage",0.5,"until_end_next_turn",attack_scope="all_attacks"))
        offense=next(item for item in rows if item.source_effect=="sap");self.assertEqual(offense.normalization_disposition,"suppressed");self.assertEqual(offense.expected_exposure,0)

    def test_specified_action_suppresses_only_overlapping_all_attacks_impairment(self)->None:
        action=expose_label("escape","escape_action",0.5,"one_minute_concentration",active_probabilities_by_basis={"target_turn_window":(0.5,0.25,0.125)})
        restrained=expose_label("restrained","restrained",0.7,"one_minute_concentration",active_probabilities_by_basis={"target_turn_window":(0.7,0.4,0.2),"attack_opportunity":(0.7,0.4,0.2),"incoming_attack_opportunity":(0.7,0.4,0.2),"save_opportunity":(0.7,0.4,0.2)})
        rows=self.normalized(action,restrained);requirement=next(item for item in rows if item.primitive_id=="specified_action_requirement");offense=next(item for item in rows if item.primitive_id=="offensive_impairment_all_attacks");incoming=next(item for item in rows if item.primitive_id=="defensive_attack_advantage");save=next(item for item in rows if item.primitive_id=="save_disadvantage")
        self.assertEqual(requirement.normalization_disposition,"retained");self.assertEqual(requirement.active_probabilities,(0.5,0.25,0.125))
        self.assertEqual(offense.normalization_disposition,"partially_suppressed")
        for observed,expected in zip(offense.active_probabilities,(0.2,0.15,0.075)):self.assertAlmostEqual(observed,expected,places=12)
        self.assertEqual(incoming.normalization_disposition,"retained");self.assertEqual(incoming.active_probabilities,(0.7,0.4,0.2));self.assertEqual(save.normalization_disposition,"retained");self.assertEqual(save.active_probabilities,(0.7,0.4,0.2))

    def test_all_attacks_only_suppresses_an_explicitly_nested_next_attack_source(self)->None:
        nested=self.normalized(expose_label("burst","attack_disadvantage",0.4,"until_start_next_turn",attack_scope="all_attacks",overlapping_attack_impairment_sources=("sap",)),expose_label("sap","attack_disadvantage",0.7,"until_start_next_turn",attack_scope="next_attack"));sap=next(item for item in nested if item.source_effect=="sap")
        self.assertEqual(sap.normalization_disposition,"partially_suppressed");self.assertAlmostEqual(sap.active_probabilities[0],0.3);self.assertAlmostEqual(sap.expected_exposure or 0,0.3);self.assertIn("burst:offensive_impairment_all_attacks",sap.suppressed_by)
        independent=self.normalized(expose_label("unrelated","attack_disadvantage",0.4,"until_start_next_turn",attack_scope="all_attacks"),expose_label("standalone","attack_disadvantage",0.7,"until_start_next_turn",attack_scope="next_attack"));standalone=next(item for item in independent if item.source_effect=="standalone")
        self.assertEqual(standalone.normalization_disposition,"retained");self.assertEqual(standalone.active_probabilities,(0.7,));self.assertEqual(standalone.expected_exposure,0.7)

    def test_auto_failure_speed_zero_and_condition_inclusion_normalize(self)->None:
        save_rows=self.normalized(expose_label("stun","stunned",0.5,"until_end_next_turn"),expose_label("restrain","restrained",0.5,"until_end_next_turn"))
        dex_disadvantage=next(item for item in save_rows if item.primitive_id=="save_disadvantage");self.assertEqual(dex_disadvantage.normalization_disposition,"suppressed")
        mobility=self.normalized(expose_label("slow","speed_reduction",0.8,"until_end_next_turn",magnitude_feet=10),expose_label("stop","speed_zero",0.4,"until_end_next_turn"))
        slow=next(item for item in mobility if item.source_effect=="slow");self.assertEqual(slow.normalization_disposition,"partially_suppressed");self.assertEqual(slow.active_probabilities,(0.4,));self.assertEqual(slow.expected_exposure,4)
        included=self.normalized(expose_label("stun","stunned",0.5,"until_end_next_turn"),expose_label("incap","incapacitated",0.5,"until_end_next_turn"))
        self.assertEqual(sum(item.primitive_id=="active_turn_denial" and item.normalization_disposition!="suppressed" for item in included),1)

    def test_measured_reductions_stack_across_sources_but_not_with_themselves(self)->None:
        slow=expose_label("mastery:slow","speed_reduction",0.8,"until_start_next_turn",magnitude_feet=10)
        glacial=expose_label("glacial_spike:T0:effect0","speed_reduction",0.8,"until_end_next_turn",magnitude_feet=10)
        distinct=self.normalized(slow,glacial);self.assertEqual(sum(item.normalization_disposition=="retained" for item in distinct),2)
        duplicate=self.normalized(glacial,glacial);self.assertEqual(sum(item.normalization_disposition=="retained" for item in duplicate),1);self.assertEqual(sum(item.normalization_disposition=="suppressed" for item in duplicate),1)
        dominated=self.normalized(slow,glacial,expose_label("stop","speed_zero",0.4,"until_end_next_turn"));reductions=[item for item in dominated if dict(item.qualifiers).get("mobility_effect")=="flat_reduction"]
        self.assertEqual(len(reductions),2);self.assertTrue(all(item.normalization_disposition=="partially_suppressed" and item.active_probabilities==(0.4,) and item.expected_exposure==4 for item in reductions))

    def test_duplicate_advantage_and_disadvantage_do_not_stack(self)->None:
        advantage=self.normalized(expose_label("blind","blinded",0.5,"until_end_next_turn"),expose_label("stun","stunned",0.5,"until_end_next_turn"))
        self.assertEqual(sum(item.primitive_id=="defensive_attack_advantage" and item.normalization_disposition!="suppressed" for item in advantage),1)
        disadvantage=self.normalized(expose_label("one","attack_disadvantage",0.5,"until_end_next_turn",attack_scope="all_attacks"),expose_label("two","attack_disadvantage",0.5,"until_end_next_turn",attack_scope="all_attacks"))
        self.assertEqual(sum(item.primitive_id=="offensive_impairment_all_attacks" and item.normalization_disposition!="suppressed" for item in disadvantage),1)
        next_attack=self.normalized(expose_label("one","attack_disadvantage",0.5,"until_end_next_turn",attack_scope="next_attack"),expose_label("two","attack_disadvantage",0.5,"until_end_next_turn",attack_scope="next_attack"))
        self.assertEqual(sum(item.primitive_id=="offensive_impairment_next_attack" and item.normalization_disposition!="suppressed" for item in next_attack),1)


class CurrentScenarioShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls)->None:
        cls.model=AuthorityModel.load();cls.config=load_config();cls.comparators=load_comparators();cls.target=target()

    def rows(self,value:dict[str,object],discipline:str)->list[dict[str,object]]:
        return shadow_rows({"Build":value["build"],"Discipline":discipline,"Level":20,"Target":"Sentinel","Scenario":value["scenario"]},value["shadow_components"],horizon=3)  # type: ignore[arg-type]

    def test_one_current_kv_scenario_per_discipline_is_inspectable(self)->None:
        cases=[("pyrokinesis","flare",2,"primary"),("cryokinesis","snow_chains",2,"primary"),("psychokinesis","telekinetic_shove",2,"primary"),("electrokinesis","forked_lightning",2,"primary")]
        for discipline,entity,tier,role in cases:
            with self.subTest(discipline=discipline):
                value=_kv_scenario(self.model,self.config,self.target,discipline,entity,tier,role);rows=self.rows(value,discipline);self.assertTrue(rows);self.assertTrue(all(row["Mechanical Primitive"] for row in rows))
        shove=self.rows(_kv_scenario(self.model,self.config,self.target,"psychokinesis","telekinetic_shove",2),"psychokinesis");movement=next(row for row in shove if row["Mechanical Primitive"]=="forced_displacement");self.assertEqual(movement["Magnitude"],"20");self.assertNotIn("cliff",str(movement).lower())

    def test_same_strike_mastery_vectors_respect_normal_and_replacement_rules(self)->None:
        cryo=self.rows(_kv_scenario(self.model,self.config,self.target,"cryokinesis","glacial_spike",0),"cryokinesis");reductions=[row for row in cryo if row["Mechanical Primitive"]=="mobility_loss_feet"]
        self.assertEqual([row["Source Effect"] for row in reductions],["glacial_spike:T0:effect0"]);self.assertEqual(reductions[0]["Normalization"],"retained");self.assertEqual(reductions[0]["Magnitude"],"10");self.assertFalse(any(str(row["Source Effect"]).startswith("mastery:") for row in cryo))
        ordinary=self.rows(_kv_scenario(self.model,self.config,self.target,"cryokinesis","snow_chains",2),"cryokinesis");slow=next(row for row in ordinary if row["Source Effect"]=="mastery:slow");self.assertEqual(slow["Mechanical Primitive"],"mobility_loss_feet");self.assertEqual(slow["Magnitude"],"10")
        electro=self.rows(_kv_scenario(self.model,self.config,self.target,"electrokinesis","static_discharge",2),"electrokinesis");sap=next(row for row in electro if row["Source Effect"]=="mastery:sap");self.assertEqual(sap["Mechanical Primitive"],"offensive_impairment_next_attack")
        shove=self.rows(_kv_scenario(self.model,self.config,self.target,"psychokinesis","telekinetic_shove",2),"psychokinesis");self.assertFalse(any(str(row["Source Effect"]).startswith("mastery:") for row in shove));self.assertEqual([row["Magnitude"] for row in shove if row["Mechanical Primitive"]=="forced_displacement"],["20"])

    def test_glacial_tier_one_failed_save_is_speed_zero_and_success_keeps_only_its_reduction(self)->None:
        rows=self.rows(_kv_scenario(self.model,self.config,self.target,"cryokinesis","glacial_spike",1),"cryokinesis");reductions=[row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="10"];speed_zero=next(row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="")
        self.assertEqual([row["Source Effect"] for row in reductions],["glacial_spike:T1:effect0"]);self.assertEqual(reductions[0]["Normalization"],"partially_suppressed");self.assertEqual(speed_zero["Source Effect"],"glacial_spike:T1:effect1");self.assertFalse(any(row["Source Effect"]=="mastery:slow" for row in rows))
        successful_branch=float(reductions[0]["Application Probability"])-float(speed_zero["Application Probability"]);active=[float(str(row["Active Probabilities"]).split("=")[1]) for row in reductions];self.assertGreater(successful_branch,0)
        self.assertTrue(all(abs(value-successful_branch)<1e-10 for value in active));self.assertTrue(all(abs(float(row["Expected Exposure"])-10*value)<1e-10 for row,value in zip(reductions,active)))

    def test_glacial_tier_two_failed_save_is_restrained_and_success_keeps_only_its_reduction(self)->None:
        rows=self.rows(_kv_scenario(self.model,self.config,self.target,"cryokinesis","glacial_spike",2),"cryokinesis");reductions=[row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="10"];restrained=[row for row in rows if row["Source Effect"]=="glacial_spike:T2:effect1"]
        self.assertEqual([row["Source Effect"] for row in reductions],["glacial_spike:T2:effect0"]);self.assertTrue(restrained);self.assertTrue(any(row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="" for row in restrained));self.assertFalse(any(row["Source Effect"]=="mastery:slow" for row in rows))
        speed_zero=next(row for row in restrained if row["Mechanical Primitive"]=="mobility_loss_feet");successful_branch=float(reductions[0]["Application Probability"])-float(speed_zero["Application Probability"]);active=float(str(reductions[0]["Active Probabilities"]).split("=")[1]);self.assertGreater(successful_branch,0);self.assertAlmostEqual(active,successful_branch,places=10);self.assertAlmostEqual(float(reductions[0]["Expected Exposure"]),10*active,places=10)

    def test_electron_burst_all_attacks_only_suppresses_the_failed_save_sap_overlap(self)->None:
        rows=self.rows(_kv_scenario(self.model,self.config,self.target,"electrokinesis","electron_burst",2),"electrokinesis");all_attacks=next(row for row in rows if row["Mechanical Primitive"]=="offensive_impairment_all_attacks");sap=next(row for row in rows if row["Mechanical Primitive"]=="offensive_impairment_next_attack")
        self.assertEqual(all_attacks["Normalization"],"retained");self.assertEqual(sap["Source Effect"],"mastery:sap");self.assertEqual(sap["Normalization"],"partially_suppressed")
        successful_save_branch=float(sap["Application Probability"])-float(all_attacks["Application Probability"]);residual=float(str(sap["Active Probabilities"]).split("=")[1]);self.assertGreater(successful_save_branch,0);self.assertAlmostEqual(residual,successful_save_branch,places=10);self.assertAlmostEqual(float(sap["Expected Exposure"]),residual,places=10)
        self.assertIn("electron_burst:T2:effect0:offensive_impairment_all_attacks",str(sap["Suppressed By"]))

    def test_battle_master_gaps_remain_explicit_while_eldritch_knight_packages_are_structured(self)->None:
        for scenario in self.comparators["control"]["battle_master"]["scenarios"]:
            value=_comparator_scenario(self.model,self.config,self.comparators,self.target,"battle_master",scenario);rows=self.rows(value,"all");self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"]=="unsupported" for row in rows))
        target=replace(self.target,creature_type="humanoid",size="medium")
        for scenario in self.comparators["control"]["eldritch_knight"]["scenarios"]:
            value=_comparator_scenario(self.model,self.config,self.comparators,target,"eldritch_knight",scenario);rows=self.rows(value,"all")
            self.assertTrue(rows);self.assertFalse(any(row["Pricing Status"]=="unsupported" for row in rows))
        push=next(item for item in self.comparators["control"]["battle_master"]["scenarios"] if item["id"]=="pushing_attack");rows=self.rows(_comparator_scenario(self.model,self.config,self.comparators,self.target,"battle_master",push),"all");self.assertEqual(rows[0]["Mechanical Primitive"],"forced_displacement");self.assertEqual(rows[0]["Magnitude"],"")

    def scenario(self,scenario_id:str)->dict[str,object]:
        return next(item for item in self.comparators["control"]["eldritch_knight"]["scenarios"] if item["id"]==scenario_id)

    def active(self,row:dict[str,object])->tuple[float,...]:
        return tuple(float(item.split("=")[1]) for item in str(row["Active Probabilities"]).split(";") if item)

    def test_stage_a_spell_attack_and_direct_consequence_sentinels(self)->None:
        row=self.comparators["control"]["eldritch_knight"];pb=self.model.progression("proficiency_bonus",20);spell_modifier=int(row["spellcasting_ability_modifier_by_level"]["20"])
        ray=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("ray_of_frost"));spell_hit=sum(attack_probabilities(pb+spell_modifier,self.target.ac)[1:]);weapon_hit=sum(attack_probabilities(pb+spell_modifier+int(row["magic_weapon_bonus_by_level"]["20"]),self.target.ac)[1:])
        self.assertAlmostEqual(ray["whole"],100*spell_hit);self.assertNotAlmostEqual(ray["whole"],100*weapon_hit);movement=next(item for item in self.rows(ray,"all") if item["Mechanical Primitive"]=="mobility_loss_feet");self.assertEqual(movement["Magnitude"],"10");self.assertAlmostEqual(float(movement["Expected Exposure"]),10*spell_hit)
        sickness=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("ray_of_sickness"));sickness_rows=self.rows(sickness,"all");self.assertEqual(next(item for item in sickness_rows if item["Mechanical Primitive"]=="offensive_impairment_all_attacks")["Pricing Status"],"candidate");self.assertEqual(next(item for item in sickness_rows if item["Mechanical Primitive"]=="ability_check_impairment")["Pricing Status"],"context_required")
        immune=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,condition_immunities=frozenset({"poisoned"})),"eldritch_knight",self.scenario("ray_of_sickness"));self.assertEqual(immune["whole"],0);self.assertFalse(immune["shadow_components"])
        thunder=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("thunderwave"));displacement=next(item for item in self.rows(thunder,"all") if item["Mechanical Primitive"]=="forced_displacement");self.assertEqual(displacement["Magnitude"],"10");self.assertAlmostEqual(float(displacement["Expected Exposure"]),10*float(displacement["Application Probability"]));self.assertNotIn("environment",str(displacement).lower())

    def test_color_hold_and_blindness_sentinels(self)->None:
        row=self.comparators["control"]["eldritch_knight"];pb=self.model.progression("proficiency_bonus",20);dc=int(row["save_dc_base"])+pb+int(row["spellcasting_ability_modifier_by_level"]["20"])
        color=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("color_spray"));color_rows=self.rows(color,"all");self.assertTrue(color_rows);self.assertTrue(all(str(item["Active Probabilities"]).count("window_")==1 for item in color_rows))
        primer=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("color_spray_after_eldritch_strike"));weapon_bonus=pb+int(row["attack_ability_modifier"])+int(row["magic_weapon_bonus_by_level"]["20"]);hit=sum(attack_probabilities(weapon_bonus,self.target.ac)[1:]);mark=_eldritch_strike_primer_probability(4,hit);normal=1-save_success_probability(self.target,"constitution",dc,False,True);disadvantaged=1-save_success_probability(self.target,"constitution",dc,True,True);self.assertAlmostEqual(primer["whole"],100*(mark*disadvantaged+(1-mark)*normal))
        humanoid=replace(self.target,creature_type="humanoid");hold=_comparator_scenario(self.model,self.config,self.comparators,humanoid,"eldritch_knight",self.scenario("hold_person"));self.assertTrue(hold["eligible"]);turn=next(item for item in self.rows(hold,"all") if item["Mechanical Primitive"]=="active_turn_denial");p=float(turn["Application Probability"]);q=1-save_success_probability(humanoid,"wisdom",dc,False,True);active=tuple(float(item.split("=")[1]) for item in str(turn["Active Probabilities"]).split(";"));self.assertEqual(len(active),3);self.assertAlmostEqual(active[0],p);self.assertAlmostEqual(active[1],p*q);self.assertAlmostEqual(active[2],p*q*q)
        nonhumanoid=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hold_person"));self.assertFalse(nonhumanoid["eligible"]);self.assertEqual(nonhumanoid["whole"],0)
        immune=_comparator_scenario(self.model,self.config,self.comparators,replace(humanoid,condition_immunities=frozenset({"paralyzed"})),"eldritch_knight",self.scenario("hold_person"));self.assertEqual(immune["whole"],0);self.assertFalse(immune["shadow_components"])
        blindness=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("blindness_deafness"));offense=next(item for item in self.rows(blindness,"all") if item["Mechanical Primitive"]=="offensive_impairment_all_attacks");active=tuple(float(item.split("=")[1]) for item in str(offense["Active Probabilities"]).split(";"));self.assertEqual(len(active),3);self.assertAlmostEqual(active[0],float(offense["Application Probability"]))

    def test_hideous_laughter_break_policy_and_eldritch_strike_repeat_math(self)->None:
        normal=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hideous_laughter"));rows=self.rows(normal,"all");turn=next(row for row in rows if row["Mechanical Primitive"]=="active_turn_denial");p=float(turn["Application Probability"]);dc=8+self.model.progression("proficiency_bonus",20)+int(self.comparators["control"]["eldritch_knight"]["spellcasting_ability_modifier_by_level"]["20"]);q=1-save_success_probability(self.target,"wisdom",dc,False,True)
        self.assertEqual({row["Condition/Outcome"] for row in rows},{"prone","incapacitated"});self.assertEqual(len(self.active(turn)),3);self.assertAlmostEqual(self.active(turn)[0],p);self.assertAlmostEqual(self.active(turn)[1],p*q);self.assertAlmostEqual(self.active(turn)[2],p*q*q)
        self.assertEqual(normal["breaks"],[{"id":"damage_repeat_save","trigger":"damage","resolution":"repeat_save","save":"wisdom","save_advantage":True,"success":"ends_effect","baseline_disposition":"inactive_controller_preserves_control"}]);self.assertIn("end_own_prone",str(normal["shadow_components"]))
        primer=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hideous_laughter_after_eldritch_strike"));primer_turn=next(row for row in self.rows(primer,"all") if row["Mechanical Primitive"]=="active_turn_denial");primer_p=float(primer_turn["Application Probability"]);self.assertGreater(primer_p,p);self.assertAlmostEqual(self.active(primer_turn)[1],primer_p*q);self.assertAlmostEqual(self.active(primer_turn)[2],primer_p*q*q)

    def test_sleep_two_stage_vectors_eligibility_and_initial_only_primer(self)->None:
        normal=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("sleep"));rows=self.rows(normal,"all");stage1=next(row for row in rows if row["Source Effect"]=="sleep:incapacitated_stage" and row["Mechanical Primitive"]=="active_turn_denial");stage2_mobility=next(row for row in rows if row["Source Effect"]=="sleep:unconscious_stage" and row["Mechanical Primitive"]=="mobility_loss_feet");p=float(stage1["Application Probability"]);dc=8+self.model.progression("proficiency_bonus",20)+int(self.comparators["control"]["eldritch_knight"]["spellcasting_ability_modifier_by_level"]["20"]);q=1-save_success_probability(self.target,"wisdom",dc,False,True)
        self.assertEqual(stage1["Normalization"],"combined_disjoint_stages");self.assertEqual(len(self.active(stage1)),3);self.assertAlmostEqual(self.active(stage1)[0],p);self.assertAlmostEqual(self.active(stage1)[1],p*q);self.assertAlmostEqual(self.active(stage1)[2],p*q);self.assertEqual(len(self.active(stage2_mobility)),3);self.assertEqual(self.active(stage2_mobility)[0],0.0);self.assertAlmostEqual(self.active(stage2_mobility)[1],p*q);self.assertAlmostEqual(self.active(stage2_mobility)[2],p*q);self.assertAlmostEqual(float(stage2_mobility["Application Probability"]),p*q)
        primer=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("sleep_after_eldritch_strike"));primer_rows=self.rows(primer,"all");primer_stage1=next(row for row in primer_rows if row["Source Effect"]=="sleep_after_eldritch_strike:incapacitated_stage" and row["Mechanical Primitive"]=="active_turn_denial");primer_stage2=next(row for row in primer_rows if row["Source Effect"]=="sleep_after_eldritch_strike:unconscious_stage" and row["Mechanical Primitive"]=="mobility_loss_feet");primer_p=float(primer_stage1["Application Probability"]);self.assertGreater(primer_p,p);self.assertAlmostEqual(float(primer_stage2["Application Probability"]),primer_p*q)
        exhaustion=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,condition_immunities=frozenset({"exhaustion"})),"eldritch_knight",self.scenario("sleep"));self.assertTrue(exhaustion["automatic_save_success"]);self.assertEqual(exhaustion["whole"],0);self.assertFalse(exhaustion["shadow_components"])
        no_sleep=SimpleNamespace(**self.target.__dict__,does_not_sleep=True);source_explicit=_comparator_scenario(self.model,self.config,self.comparators,no_sleep,"eldritch_knight",self.scenario("sleep"));self.assertTrue(source_explicit["automatic_save_success"]);self.assertFalse(source_explicit["shadow_components"])
        inferred=replace(self.target,name="Sleepless Construct",creature_type="construct");not_inferred=_comparator_scenario(self.model,self.config,self.comparators,inferred,"eldritch_knight",self.scenario("sleep"));self.assertFalse(not_inferred["automatic_save_success"]);self.assertGreater(not_inferred["whole"],0)
        incap_immune=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,condition_immunities=frozenset({"incapacitated"})),"eldritch_knight",self.scenario("sleep"));self.assertTrue(any(component["source_effect"].endswith("unconscious_stage") for component in incap_immune["shadow_components"]));self.assertFalse(any(component["source_effect"].endswith("incapacitated_stage") for component in incap_immune["shadow_components"]))
        unconscious_immune=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,condition_immunities=frozenset({"unconscious"})),"eldritch_knight",self.scenario("sleep"));self.assertTrue(any(component["source_effect"].endswith("incapacitated_stage") for component in unconscious_immune["shadow_components"]));self.assertFalse(any(component["source_effect"].endswith("unconscious_stage") for component in unconscious_immune["shadow_components"]))

    def test_hypnotic_pattern_dependency_persistence_breaks_and_access(self)->None:
        normal=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hypnotic_pattern"));rows=self.rows(normal,"all");turn=next(row for row in rows if row["Mechanical Primitive"]=="active_turn_denial");mobility=next(row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet");p=float(turn["Application Probability"]);self.assertEqual(self.active(turn),(p,p,p));self.assertEqual(self.active(mobility),(p,p,p));self.assertTrue(all(component["repeat_survival_probability"] is None for component in normal["shadow_components"]))
        self.assertEqual({item["trigger"] for item in normal["breaks"]},{"damage","external_action"});self.assertTrue(all(str(item["baseline_disposition"]).startswith("inactive_") for item in normal["breaks"]))
        immune=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,condition_immunities=frozenset({"charmed"})),"eldritch_knight",self.scenario("hypnotic_pattern"));self.assertEqual(immune["whole"],0);self.assertFalse(immune["shadow_components"])
        unavailable=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,level=11),"eldritch_knight",self.scenario("hypnotic_pattern"));self.assertFalse(unavailable["eligible"]);self.assertEqual(unavailable["whole"],0)

    def test_targeting_upcast_metadata_has_no_breadth_scalar(self)->None:
        row=self.comparators["control"]["eldritch_knight"]
        laughter=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hideous_laughter"));self.assertEqual(laughter["targeting"]["maximum_target_cap"],4)
        hold=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,creature_type="humanoid"),"eldritch_knight",self.scenario("hold_person"));self.assertEqual(hold["targeting"]["maximum_target_cap"],3)
        sleep=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("sleep"));self.assertEqual(sleep["targeting"]["area"],{"shape":"sphere","radius_feet":5});self.assertEqual(sleep["targeting"]["creature_selection"],"creatures_of_caster_choice")
        pattern=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("hypnotic_pattern"));self.assertEqual(pattern["targeting"]["area"],{"shape":"cube","size_feet":30});self.assertEqual(pattern["targeting"]["eligibility_predicate"],"can_see_pattern");self.assertFalse(self.scenario("hypnotic_pattern")["improved_war_magic_eligible"])
        blindness=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("blindness_deafness"));self.assertEqual(blindness["targeting"]["maximum_target_cap"],3)
        deafness=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("blindness_deafness_deafened_mode"));self.assertEqual(deafness["targeting"]["maximum_target_cap"],3);self.assertEqual(self.scenario("blindness_deafness_deafened_mode")["effects"][0]["outcomes"],["hearing_option_denial"])
        color=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("color_spray"));self.assertEqual(color["targeting"]["area"],{"shape":"cone","size_feet":15,"origin":"caster"})
        thunder=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",self.scenario("thunderwave"));self.assertEqual(thunder["targeting"]["area"],{"shape":"cube","size_feet":15,"origin":"caster"})
        self.assertEqual(row["spell_access"]["highest_slot_level_by_fighter_level"],{"7":2,"11":2,"15":3,"20":4});self.assertNotIn("breadth_scalar",json.dumps(self.comparators))

    def test_reliability_boundary_battle_master_inventory_and_no_scalar(self)->None:
        self.assertEqual(self.comparators["control"]["eldritch_knight"]["reliability_scenario_ids"],["blindness_deafness","blindness_after_eldritch_strike"])
        self.assertEqual(self.comparators["control"]["battle_master"]["scenarios"],[{"id":"menacing_attack","save":"wisdom","hit_gated":True,"conditions":["frightened"]},{"id":"pushing_attack","save":"strength","hit_gated":True,"outcomes":["forced_movement"],"maximum_size":"large"},{"id":"trip_attack","save":"strength","hit_gated":True,"conditions":["prone"],"maximum_size":"large"},{"id":"goading_attack","save":"wisdom","hit_gated":True,"outcomes":["attack_disadvantage"]}])
        def keys(value:object)->set[str]:
            if isinstance(value,dict):return set(value)|set().union(*(keys(item) for item in value.values()))
            if isinstance(value,list):return set().union(*(keys(item) for item in value))
            return set()
        catalog=json.loads((Path(__file__).parents[1]/"data/control_primitives.json").read_text(encoding="utf-8"));self.assertTrue({"weight","weights","scalar"}.isdisjoint(keys(catalog)|keys(self.comparators)))
        shocking=self.scenario("shocking_grasp");self.assertEqual(shocking["effects"][0]["outcomes"],["opportunity_attack_denial"]);self.assertNotIn("reaction_denial",json.dumps(shocking))

    def test_mind_sliver_uses_exact_finite_penalty_and_combines_with_eldritch_strike(self)->None:
        probe=replace(self.target,saves={**self.target.saves,"wisdom":1},magic_resistance=False);dc=15
        expected=sum(roll-penalty+1<dc for roll in range(1,21) for penalty in range(1,5))/80
        self.assertAlmostEqual(_finite_penalty_save_failure_probability(probe,"wisdom",dc,4),expected,places=12)
        disadvantaged=sum(min(first,second)-penalty+1<dc for first in range(1,21) for second in range(1,21) for penalty in range(1,5))/1600
        mark=0.75;combined=mark*disadvantaged+(1-mark)*expected
        self.assertAlmostEqual(_finite_penalty_with_disadvantage_probability(probe,"wisdom",dc,4,mark),combined,places=12)
        primer=self.scenario("mind_sliver");self.assertEqual(primer["effects"][0]["magnitude"],4);self.assertNotIn("save_disadvantage",json.dumps(primer));self.assertIn("same_attack_action_sequence_not_established",primer["context_predicates"])

        expanded=_composed_eldritch_knight_scenarios(self.comparators,probe);slow=self.scenario("slow")
        ordinary=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",slow)
        composed=next(item for item in expanded if item["id"]=="slow_after_mind_sliver")
        composed_value=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",composed)
        ek_row=self.comparators["control"]["eldritch_knight"];spell_dc=int(ek_row["save_dc_base"])+self.model.progression("proficiency_bonus",20)+int(ek_row["spellcasting_ability_modifier_by_level"]["20"])
        primer_probability=1-modified_save_success_probability(probe,"intelligence",spell_dc,magic_resistance=True)
        ordinary_failure=1-modified_save_success_probability(probe,"wisdom",spell_dc,magic_resistance=True)
        exact_penalized=sum(roll-penalty+probe.saves["wisdom"]<spell_dc for roll in range(1,21) for penalty in range(1,5))/80
        self.assertAlmostEqual(composed_value["whole"]/100,primer_probability*exact_penalized+(1-primer_probability)*ordinary_failure,places=12)
        self.assertNotAlmostEqual(composed_value["whole"],ordinary["whole"])

        combined=next(item for item in expanded if item["id"]=="slow_after_mind_sliver_and_eldritch_strike")
        combined_value=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",combined)
        weapon_bonus=self.model.progression("proficiency_bonus",20)+int(ek_row["attack_ability_modifier"])+int(ek_row["magic_weapon_bonus_by_level"]["20"])
        hit=sum(attack_probabilities(weapon_bonus,probe.ac)[1:]);mark=_eldritch_strike_primer_probability(3,hit)
        penalized_disadvantage=sum(min(first,second)-penalty+probe.saves["wisdom"]<spell_dc for first in range(1,21) for second in range(1,21) for penalty in range(1,5))/1600
        ordinary_disadvantage=1-modified_save_success_probability(probe,"wisdom",spell_dc,disadvantage=True,magic_resistance=True)
        expected_combined=primer_probability*(mark*penalized_disadvantage+(1-mark)*exact_penalized)+(1-primer_probability)*(mark*ordinary_disadvantage+(1-mark)*ordinary_failure)
        self.assertAlmostEqual(combined_value["whole"]/100,expected_combined,places=12)
        resistant=replace(probe,magic_resistance=True);resistant_expanded=_composed_eldritch_knight_scenarios(self.comparators,resistant);resistant_combined=next(item for item in resistant_expanded if item["id"]=="slow_after_mind_sliver_and_eldritch_strike");resistant_value=_comparator_scenario(self.model,self.config,self.comparators,resistant,"eldritch_knight",resistant_combined)
        resistant_mark=float(resistant_value["save_composition"]["eldritch_strike_establishment_probability"]);resistant_primer=float(resistant_value["save_composition"]["mind_sliver_establishment_probability"])
        resistant_normal=1-modified_save_success_probability(resistant,"wisdom",spell_dc,magic_resistance=True);resistant_disadvantage=1-modified_save_success_probability(resistant,"wisdom",spell_dc,disadvantage=True,magic_resistance=True)
        resistant_penalty=_finite_penalty_save_failure_probability(resistant,"wisdom",spell_dc,4,magic_resistance=True);resistant_penalty_cancelled=_finite_penalty_save_failure_probability(resistant,"wisdom",spell_dc,4,disadvantage=True,magic_resistance=True)
        self.assertAlmostEqual(resistant_value["whole"]/100,resistant_primer*(resistant_mark*resistant_penalty_cancelled+(1-resistant_mark)*resistant_penalty)+(1-resistant_primer)*(resistant_mark*resistant_disadvantage+(1-resistant_mark)*resistant_normal),places=12)
        invalid=_composed_eldritch_knight_scenarios(self.comparators,probe,mind_sliver_timing="same_attack_action")
        self.assertFalse(any("after_mind_sliver" in item["id"] for item in invalid))

    def test_war_magic_combined_primer_replaces_one_attack_at_levels_11_and_20(self)->None:
        configured={item["id"]:item for item in self.comparators["control"]["eldritch_knight"]["scenarios"]}
        for level,combined_attacks,eldritch_only_attacks in ((11,2,3),(20,3,4)):
            probe=replace(self.target,level=level);expanded={item["id"]:item for item in _composed_eldritch_knight_scenarios(self.comparators,probe)}
            combined=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",expanded["blindness_deafness_after_mind_sliver_and_eldritch_strike"])
            eldritch_only=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",configured["blindness_after_eldritch_strike"])
            pb=self.model.progression("proficiency_bonus",level);row=self.comparators["control"]["eldritch_knight"];weapon_bonus=pb+int(row["attack_ability_modifier"])+int(row["magic_weapon_bonus_by_level"][str(level)]);hit=sum(attack_probabilities(weapon_bonus,probe.ac)[1:])
            self.assertEqual(combined["save_composition"]["eldritch_strike_weapon_attacks"],combined_attacks);self.assertAlmostEqual(combined["save_composition"]["eldritch_strike_establishment_probability"],_eldritch_strike_primer_probability(combined_attacks,hit),places=12)
            self.assertEqual(eldritch_only["save_composition"]["eldritch_strike_weapon_attacks"],eldritch_only_attacks);self.assertAlmostEqual(eldritch_only["save_composition"]["eldritch_strike_establishment_probability"],_eldritch_strike_primer_probability(eldritch_only_attacks,hit),places=12)

    def test_area_movement_tax_and_action_escape_are_generic(self)->None:
        terrain=decompose_label("difficult_terrain")[0];self.assertEqual(terrain.primitive_id,"terrain_movement_tax");self.assertNotEqual(terrain.primitive_id,"mobility_loss_feet");self.assertEqual(dict(terrain.qualifiers)["stacking"],"nonstacking")
        web=self.scenario("web");tentacles=self.scenario("evards_black_tentacles")
        self.assertEqual(web["escapes"],tentacles["escapes"]);self.assertEqual(web["area_exit_policy"],tentacles["area_exit_policy"])
        probe=replace(self.target,ability_modifiers={"strength":1},skill_bonuses={"athletics":7})
        dc=8+self.model.progression("proficiency_bonus",20)+int(self.comparators["control"]["eldritch_knight"]["spellcasting_ability_modifier_by_level"]["20"])
        self.assertAlmostEqual(ability_check_success_probability(probe,"strength",dc,"athletics"),sum(roll+7>=dc for roll in range(1,21))/20)
        fallback=replace(probe,skill_bonuses={});self.assertAlmostEqual(ability_check_success_probability(fallback,"strength",dc,"athletics"),sum(roll+1>=dc for roll in range(1,21))/20)
        for scenario in (web,tentacles):
            self.assertTrue(any("difficult_terrain" in effect.get("outcomes",[]) for effect in scenario["effects"]))
            value=_comparator_scenario(self.model,self.config,self.comparators,probe,"eldritch_knight",scenario);resolution=value["escape_resolution"];self.assertIsNotNone(resolution)
            success=float(resolution["success_probability"]);application=1-save_success_probability(probe,scenario["save"],dc,False,True);attempts=tuple(float(item) for item in resolution["attempt_probabilities"])
            self.assertEqual(resolution["area_trigger"],next(effect["area_trigger"] for effect in scenario["effects"] if "restrained" in effect.get("conditions",[])))
            self.assertAlmostEqual(attempts[0],application);self.assertAlmostEqual(attempts[1],application*(1-success));self.assertAlmostEqual(attempts[2],application*(1-success)**2)
            self.assertEqual(tuple(float(item) for item in resolution["legal_exit_probabilities"]),tuple(attempt*success for attempt in attempts))
            rows=self.rows(value,"all");escape_action=next(row for row in rows if row["Source Effect"]==f"{scenario['id']}:escape_action")
            restrained=next(row for row in rows if row["Condition/Outcome"]=="restrained" and row["Mechanical Primitive"]=="mobility_loss_feet");offense=next(row for row in rows if row["Condition/Outcome"]=="restrained" and row["Mechanical Primitive"]=="offensive_impairment_all_attacks");incoming=next(row for row in rows if row["Condition/Outcome"]=="restrained" and row["Mechanical Primitive"]=="defensive_attack_advantage");dexterity_save=next(row for row in rows if row["Condition/Outcome"]=="restrained" and row["Mechanical Primitive"]=="save_disadvantage")
            for observed,expected in zip(self.active(escape_action),attempts):self.assertAlmostEqual(observed,expected,places=12)
            for observed,expected in zip(self.active(restrained),attempts):self.assertAlmostEqual(observed,expected,places=12)
            self.assertEqual(escape_action["Pricing Status"],"candidate");self.assertEqual(offense["Normalization"],"suppressed");self.assertTrue(all(value==0 for value in self.active(offense)));self.assertEqual(float(offense["Expected Exposure"]),0)
            for independent in (incoming,dexterity_save):
                self.assertEqual(independent["Normalization"],"retained")
                for observed,expected in zip(self.active(independent),attempts):self.assertAlmostEqual(observed,expected,places=12)

    def test_generic_eldritch_strike_variants_cover_new_spells_and_only_the_initial_save(self)->None:
        expanded=_composed_eldritch_knight_scenarios(self.comparators,self.target);by_id={item["id"]:item for item in expanded}
        for scenario_id in ("slow","confusion","phantasmal_killer"):
            base=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",by_id[scenario_id]);primed=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",by_id[f"{scenario_id}_after_eldritch_strike"])
            self.assertGreater(primed["whole"],base["whole"]);self.assertEqual(primed["save_composition"]["primers"],["eldritch_strike"])
        slow=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",by_id["slow_after_eldritch_strike"]);speed=next(row for row in self.rows(slow,"all") if row["Mechanical Primitive"]=="speed_multiplier")
        active=self.active(speed);repeat=float(slow["save_composition"]["repeat_failure_probability"]);self.assertAlmostEqual(active[1],active[0]*repeat);self.assertAlmostEqual(active[2],active[1]*repeat)
        level7=replace(self.target,level=7);level7_ids={item["id"] for item in _composed_eldritch_knight_scenarios(self.comparators,level7)};self.assertNotIn("slow_after_eldritch_strike",level7_ids)
        self.assertEqual(self.comparators["control"]["eldritch_knight"]["reliability_scenario_ids"],["blindness_deafness","blindness_after_eldritch_strike"])

    def test_bestow_curse_modes_are_separate_and_forced_dodge_is_not_turn_denial(self)->None:
        modes={scenario["id"]:scenario for scenario in self.comparators["control"]["eldritch_knight"]["scenarios"] if scenario["spell_id"]=="bestow_curse"}
        self.assertEqual(set(modes),{"bestow_curse_ability","bestow_curse_attacks","bestow_curse_forced_dodge","bestow_curse_damage"})
        dodge=modes["bestow_curse_forced_dodge"]["effects"][0];self.assertEqual(dodge["outcomes"],["forced_dodge_action"]);self.assertNotIn("active_turn_denial",json.dumps(dodge));self.assertEqual(dodge["secondary_save"]["trigger"],"start_of_affected_turn")

    def test_slow_keeps_distinct_primitives_and_repeat_save_exposure(self)->None:
        slow=self.scenario("slow");effects={effect["id"]:effect for effect in slow["effects"]}
        self.assertEqual({key:effects[key]["outcomes"][0] for key in effects},{"speed":"speed_multiplier","armor_class":"armor_class_penalty","dexterity_save":"save_roll_penalty","reactions":"reaction_denial","action_bonus":"action_bonus_exclusivity","attacks":"one_attack_cap","somatic":"somatic_spell_failure"})
        self.assertTrue(all(effect["repeat_save_trigger"]=="end_of_affected_turn" for effect in effects.values()))
        value=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",slow);rows=self.rows(value,"all");speed=next(row for row in rows if row["Mechanical Primitive"]=="speed_multiplier");self.assertEqual(len(self.active(speed)),3);self.assertGreater(self.active(speed)[0],self.active(speed)[1]);self.assertGreater(self.active(speed)[1],self.active(speed)[2])

    def test_confusion_branches_are_exact_and_deterministic(self)->None:
        scenario=self.scenario("confusion");branches={row["id"]:Fraction(row["numerator"],row["denominator"]) for row in scenario["turn_branches"]};self.assertEqual(sum(branches.values(),Fraction(0,1)),1)
        value=_comparator_scenario(self.model,self.config,self.comparators,self.target,"eldritch_knight",scenario);rows=self.rows(value,"all");p=float(next(row for row in rows if row["Mechanical Primitive"]=="reaction_denial")["Application Probability"])
        reaction=next(row for row in rows if row["Mechanical Primitive"]=="reaction_denial");action=next(row for row in rows if row["Mechanical Primitive"]=="active_turn_denial");movement=next(row for row in rows if row["Mechanical Primitive"]=="turn_movement_denial");bonus=next(row for row in rows if row["Mechanical Primitive"]=="bonus_action_denial")
        self.assertAlmostEqual(float(action["Application Probability"]),p*0.6,places=12);self.assertAlmostEqual(float(movement["Application Probability"]),p*0.7,places=12)
        self.assertEqual(bonus["Normalization"],"partially_suppressed");self.assertEqual(len(self.active(bonus)),3)
        for residual,affected in zip(self.active(bonus),self.active(reaction)):self.assertAlmostEqual(residual,affected*0.4,places=12)

    def test_condition_dependencies_block_charmed_and_other_conditional_outcomes(self)->None:
        immune=replace(self.target,creature_type="humanoid",condition_immunities=frozenset({"charmed"}))
        for scenario_id in ("crown_of_madness","charm_person","charm_monster","suggestion"):
            value=_comparator_scenario(self.model,self.config,self.comparators,immune,"eldritch_knight",self.scenario(scenario_id));labels={label for component in value["shadow_components"] for _,label in component["labels"]}
            self.assertTrue({"restricted_melee_attack","attitude_change","open_ended_behavior"}.isdisjoint(labels),scenario_id)
            self.assertEqual(value["whole"],0,scenario_id)
        frightened_immune=replace(self.target,condition_immunities=frozenset({"frightened"}));fear=_comparator_scenario(self.model,self.config,self.comparators,frightened_immune,"eldritch_knight",self.scenario("fear"));fear_labels={label for component in fear["shadow_components"] for _,label in component["labels"]};self.assertNotIn("forced_dash_action",fear_labels);self.assertIn("held_item_drop",fear_labels)
        poisoned_immune=replace(self.target,condition_immunities=frozenset({"poisoned"}));cloud=_comparator_scenario(self.model,self.config,self.comparators,poisoned_immune,"eldritch_knight",self.scenario("stinking_cloud"));cloud_labels={label for component in cloud["shadow_components"] for _,label in component["labels"]};self.assertNotIn("active_turn_denial",cloud_labels);self.assertIn("sight_barrier",cloud_labels)

    def test_two_sided_isolation_and_phantasmal_killer_supersession(self)->None:
        banishment=self.scenario("banishment");sphere=self.scenario("otilukes_resilient_sphere")
        banishment_outcomes={outcome for effect in banishment["effects"] for outcome in effect.get("outcomes",[])};sphere_outcomes={outcome for effect in sphere["effects"] for outcome in effect.get("outcomes",[])}
        self.assertEqual(banishment_outcomes,{"interaction_isolation","target_protection"});self.assertEqual(sphere_outcomes,{"interaction_isolation","target_protection","retained_action"});self.assertTrue(any("incapacitated" in effect.get("conditions",[]) for effect in banishment["effects"]));self.assertFalse(any(effect.get("conditions") for effect in sphere["effects"]))
        killer=self.scenario("phantasmal_killer");self.assertNotIn("frightened",json.dumps(killer).lower());self.assertEqual({outcome for effect in killer["effects"] for outcome in effect.get("outcomes",[])},{"attack_disadvantage","ability_check_disadvantage"})

    def test_contextual_scenarios_fail_closed_and_inventory_matches_audit(self)->None:
        expected={"mind_sliver","ray_of_frost","shocking_grasp","charm_person","color_spray","fog_cloud","grease","ray_of_sickness","sleep","hideous_laughter","thunderwave","blindness_deafness","crown_of_madness","darkness","enlarge_reduce","gust_of_wind","hold_person","levitate","phantasmal_force","ray_of_enfeeblement","suggestion","web","bestow_curse","counterspell","dispel_magic","fear","hypnotic_pattern","sleet_storm","slow","stinking_cloud","banishment","charm_monster","confusion","conjure_minor_elementals","control_water","evards_black_tentacles","ice_storm","otilukes_resilient_sphere","phantasmal_killer","polymorph","wall_of_fire"}
        scenarios=self.comparators["control"]["eldritch_knight"]["scenarios"];self.assertEqual({scenario["spell_id"] for scenario in scenarios},expected)
        for scenario in scenarios:
            self.assertEqual(scenario["source_scope"],"independently_expressed_phb_comparator_abstraction")
            if scenario["disposition"]!="diagnostic_unpriced":continue
            result=_comparator_scenario(self.model,self.config,self.comparators,replace(self.target,creature_type="humanoid",size="medium"),"eldritch_knight",scenario);rows=self.rows(result,"all")
            self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"]=="context_required" and row["Expected Exposure"]=="" for row in rows))

    def test_configured_inventory_maps_or_fails_closed_explicitly(self)->None:
        catalog=load_primitive_catalog();known=set(catalog["conditions"])|set(catalog["outcomes"])
        labels=set()
        for discipline in self.model.disciplines.values():labels.update(discipline["mastery"]["control_outcomes"])
        configured={entry["entity_id"] for entries in self.config["control_matrix"]["kv_scenarios"].values() for entry in entries}
        for entity_id in configured:
            for tier in self.model.features[entity_id].get("control_tiers",[]):
                for effect in tier["effects"]:labels.update(effect.get("conditions",[]));labels.update(effect.get("outcomes",[]))
        for build_id,build in self.comparators["control"].items():
            for scenario in build["scenarios"]:
                if build_id=="eldritch_knight":
                    for effect in scenario["effects"]:labels.update(effect.get("conditions",[]));labels.update(effect.get("outcomes",[]))
                else:labels.update(scenario.get("conditions",[]));labels.update(scenario.get("outcomes",[]))
        self.assertLessEqual(labels,known)
        for discipline,entries in self.config["control_matrix"]["kv_scenarios"].items():
            for entry in entries:
                for tier in entry["tiers"]:
                    for role in entry.get("target_roles",["primary"]):
                        with self.subTest(discipline=discipline,entity=entry["entity_id"],tier=tier,role=role):
                            value=_kv_scenario(self.model,self.config,self.target,discipline,entry["entity_id"],tier,role);rows=self.rows(value,discipline);self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"] in {"candidate","context_required","unsupported"} and row["Source/Reason"] for row in rows))

if __name__=="__main__":unittest.main()
