from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from harness.authority import AuthorityModel,DEFAULT_AUTHORITY
from harness.control_harness import _battle_master_retry_probability,_comparator_scenario,_eldritch_strike_primer_probability,_kv_scenario,run
from harness.control_value import PrimitiveExposure,decompose_label,expose_label,fixed_exposure,instantaneous_exposure,load_primitive_catalog,normalize_exposures,primitive_inventory,repeat_save_exposure,shadow_rows
from harness.model import Target,load_comparators,load_config


def target(*immunities:str)->Target:
    return Target(20,"Sentinel",18,{"strength":5,"dexterity":3,"constitution":5,"intelligence":1,"wisdom":2,"charisma":1},False,0,"large","monstrosity",frozenset(immunities),frozenset(),frozenset(),frozenset(),200,"SRD 5.2.1","1","https://example.invalid")


class PrimitiveDecompositionTests(unittest.TestCase):
    def ids(self,label:str)->list[str]:
        return [item.primitive_id for item in decompose_label(label)]

    def test_blinded_keeps_distinct_mechanical_consequences(self)->None:
        self.assertEqual(self.ids("Blinded"),["sight_option_denial","ability_check_impairment","offensive_impairment_all_attacks","defensive_attack_advantage"])

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

    def test_historical_inventory_has_an_explicit_disposition(self)->None:
        historical={"active_turn_denial","reaction_denial","offensive_impairment_next_attack","offensive_impairment_all_attacks","target_choice_restriction","sight_option_denial","mobility_loss_feet","movement_mode_denial","forced_displacement","geometry_sensitive_approach_restriction","defensive_attack_advantage","defense_numerical_reduction","save_disadvantage","save_auto_failure","sight_dependent_opportunity","ability_check_impairment","speech_denial","social_interaction_advantage","concentration_break","persistent_elevation","fall_transition","nonsight_location_awareness","prone_incoming_attack_context"}
        inventory=primitive_inventory();self.assertEqual({row["id"] for row in inventory},historical);self.assertTrue(all(row["historical_disposition"] in {"retain_as_is","retain_but_context_required","merge","omit_current_unproduced"} for row in inventory))


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
        self.assertEqual({row["Source Effect"] for row in reductions},{"glacial_spike:T0:effect0","mastery:slow"});self.assertTrue(all(row["Normalization"]=="retained" and row["Magnitude"]=="10" for row in reductions))
        electro=self.rows(_kv_scenario(self.model,self.config,self.target,"electrokinesis","static_discharge",2),"electrokinesis");sap=next(row for row in electro if row["Source Effect"]=="mastery:sap");self.assertEqual(sap["Mechanical Primitive"],"offensive_impairment_next_attack")
        shove=self.rows(_kv_scenario(self.model,self.config,self.target,"psychokinesis","telekinetic_shove",2),"psychokinesis");self.assertFalse(any(str(row["Source Effect"]).startswith("mastery:") for row in shove));self.assertEqual([row["Magnitude"] for row in shove if row["Mechanical Primitive"]=="forced_displacement"],["20"])

    def test_glacial_speed_zero_suppresses_failed_branch_but_success_keeps_both_reductions(self)->None:
        rows=self.rows(_kv_scenario(self.model,self.config,self.target,"cryokinesis","glacial_spike",1),"cryokinesis");reductions=[row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="10"];speed_zero=next(row for row in rows if row["Mechanical Primitive"]=="mobility_loss_feet" and row["Magnitude"]=="")
        self.assertEqual({row["Source Effect"] for row in reductions},{"glacial_spike:T1:effect0","mastery:slow"});self.assertTrue(all(row["Normalization"]=="partially_suppressed" for row in reductions))
        successful_branch=float(reductions[0]["Application Probability"])-float(speed_zero["Application Probability"]);active=[float(str(row["Active Probabilities"]).split("=")[1]) for row in reductions];self.assertGreater(successful_branch,0)
        self.assertTrue(all(abs(value-successful_branch)<1e-10 for value in active));self.assertTrue(all(abs(float(row["Expected Exposure"])-10*value)<1e-10 for row,value in zip(reductions,active)))

    def test_battle_master_and_eldritch_knight_gaps_are_explicit(self)->None:
        for build in ("battle_master","eldritch_knight"):
            for scenario in self.comparators["control"][build]["scenarios"]:
                value=_comparator_scenario(self.model,self.config,self.comparators,self.target,build,scenario);rows=self.rows(value,"all");self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"]=="unsupported" for row in rows))
        push=next(item for item in self.comparators["control"]["battle_master"]["scenarios"] if item["id"]=="pushing_attack");rows=self.rows(_comparator_scenario(self.model,self.config,self.comparators,self.target,"battle_master",push),"all");self.assertEqual(rows[0]["Mechanical Primitive"],"forced_displacement");self.assertEqual(rows[0]["Magnitude"],"")

    def test_configured_inventory_maps_or_fails_closed_explicitly(self)->None:
        catalog=load_primitive_catalog();known=set(catalog["conditions"])|set(catalog["outcomes"])
        labels=set()
        for discipline in self.model.disciplines.values():labels.update(discipline["mastery"]["control_outcomes"])
        configured={entry["entity_id"] for entries in self.config["control_matrix"]["kv_scenarios"].values() for entry in entries}
        for entity_id in configured:
            for tier in self.model.features[entity_id].get("control_tiers",[]):
                for effect in tier["effects"]:labels.update(effect.get("conditions",[]));labels.update(effect.get("outcomes",[]))
        for build in self.comparators["control"].values():
            for scenario in build["scenarios"]:labels.update(scenario.get("conditions",[]));labels.update(scenario.get("outcomes",[]))
        self.assertLessEqual(labels,known)
        for discipline,entries in self.config["control_matrix"]["kv_scenarios"].items():
            for entry in entries:
                for tier in entry["tiers"]:
                    for role in entry.get("target_roles",["primary"]):
                        with self.subTest(discipline=discipline,entity=entry["entity_id"],tier=tier,role=role):
                            value=_kv_scenario(self.model,self.config,self.target,discipline,entry["entity_id"],tier,role);rows=self.rows(value,discipline);self.assertTrue(rows);self.assertTrue(all(row["Pricing Status"] in {"candidate","context_required","unsupported"} and row["Source/Reason"] for row in rows))

    def test_reliability_helpers_and_default_output_are_unchanged(self)->None:
        self.assertAlmostEqual(_battle_master_retry_probability(2,5,0.75,0.5),0.609375);self.assertAlmostEqual(_eldritch_strike_primer_probability(2,0.75),0.9375)
        with tempfile.TemporaryDirectory() as directory:
            result=run(DEFAULT_AUTHORITY,Path(directory),{7},1,16,19,write_headline=False)
            self.assertEqual(result["shadow_rows"],0);self.assertIsNone(result["shadow_path"]);self.assertFalse(list(Path(directory).glob("*shadow*")))
            with next(Path(directory).glob("*control-detail.csv")).open(encoding="utf-8") as stream:header=next(csv.reader(stream))
            self.assertNotIn("Mechanical Primitive",header);self.assertIn("Whole-package control stick %",header)

    def test_shadow_rows_are_deterministic_and_architecture_stays_lean(self)->None:
        value=_kv_scenario(self.model,self.config,self.target,"cryokinesis","snow_chains",2);first=self.rows(value,"cryokinesis");second=self.rows(value,"cryokinesis");self.assertEqual(first,second)
        source=(Path(__file__).parents[1]/"control_value.py").read_text(encoding="utf-8")
        for forbidden in ("from .control_engine import","from .control_state import","from .control_timeline import","from .control_graph import","ControlExecutionSession"):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":unittest.main()
