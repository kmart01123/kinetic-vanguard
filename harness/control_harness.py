"""YAML-driven common control selection and comparison matrices."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any,Callable,Sequence

from .authority import AuthorityModel,DEFAULT_AUTHORITY
from .comparison_report import NOTICE_COLUMNS,matrix_row,write_matrix
from .control_value import DEFAULT_PRIMITIVES,DEFAULT_SCORING,load_scoring_config,shadow_rows
from .model import DEFAULT_CATALOG,DEFAULT_COMPARATORS,DEFAULT_CONFIG,DEFAULT_PROFILE,DEFAULT_ROSTERS,PROFILE_COUNTS,Target,ability_check_success_probability,attack_probabilities,file_sha256,level_config,load_comparators,load_config,load_targets,modified_save_success_probability,save_success_probability,target_is_eligible


DELIVERY_RECIPE_IDS=frozenset({
    "mastery_attack_action_hit_retry",
    "no_modeled_control",
    "single_activation_automatic",
    "single_activation_failed_save",
    "single_activation_hit",
    "single_activation_hit_failed_save",
    "kv_attack_action_hit_retry",
    "kv_attack_action_hit_failed_save_retry",
})


def _delivery_recipe(recipe_id:str,gate:str,retry_model:str,save_ability:str="",additional_control_gate:str="")->dict[str,str]:
    """Return fail-closed, diagnostic-only delivery metadata."""
    if recipe_id not in DELIVERY_RECIPE_IDS:raise ValueError(f"Unknown delivery recipe ID: {recipe_id}")
    return {"id":recipe_id,"gate":gate,"retry_model":retry_model,"save_ability":save_ability,"additional_control_gate":additional_control_gate}


def _kv_retry_resources(model:AuthorityModel,config:dict[str,Any],level:int)->dict[str,Any]:
    """Project the maintained inputs carried by KV's retry recursion."""
    progression=level_config(config,level);profile=config["kv_profile"]
    hp=int(profile["hit_point_model"]["first_level_base"])+int(profile["constitution_modifier"])+(level-1)*(int(profile["hit_point_model"]["later_level_average"])+int(profile["constitution_modifier"]))
    mastery=model.projection["core"]["overload"]["mastery"]
    mastery_uses=int(mastery["uses_per_rest"]) if level>=int(mastery["minimum_level"]) else 0
    return {
        "level":level,
        "attacks_per_action":int(progression["attacks_per_action"]),
        "psi_pool":model.progression("psi_points",level),
        "benchmark_hp":hp,
        "blood_tax_budget":int(hp*float(profile["blood_tax_hp_fraction"])),
        "blood_tax_by_tier":tuple(model.blood_tax(level,tier) for tier in (0,1,2)),
        "overload_mastery_uses":mastery_uses,
        "overload_mastery_minimum_level":int(mastery["minimum_level"]),
        "tier_two_limit":int(model.projection["core"]["overload"]["tier_two_limit_per_attack_action"]),
    }


def _kv_rider_delivery_recipe(control:dict[str,Any],rider:bool,target_role:str="primary")->dict[str,str]:
    """Classify one exact KV rider from its target-role-applicable effect gates."""
    applicable=[effect for effect in control["effects"] if effect.get("target_role","all") in {"all",target_role} and (effect.get("conditions") or effect.get("outcomes"))]
    if not applicable:raise ValueError("KV delivery recipe has no applicable modeled control effect")
    gates={str(effect["gate"]) for effect in applicable}
    unknown=gates-{"on_reach","on_failed_save"}
    if unknown:raise ValueError(f"Unsupported KV delivery effect gate: {sorted(unknown)}")
    application=str(control["application"])
    if application not in {"failed_save","no_save"}:raise ValueError(f"Unsupported KV delivery application: {application}")
    if "on_failed_save" in gates and application!="failed_save":raise ValueError("KV delivery application disagrees with applicable effect gates")
    hit_gated=bool(control.get("hit_gated"));has_reach="on_reach" in gates;has_failed_save="on_failed_save" in gates
    save_ability=str(control.get("save","")) if has_failed_save else ""
    if save_ability=="discipline_signature":raise ValueError("KV delivery recipe requires a resolved signature save")
    if has_failed_save and not save_ability:raise ValueError("KV failed-save delivery gate lacks a save ability")
    additional="failed_save" if has_reach and has_failed_save else ""
    if rider:
        if not hit_gated:raise ValueError("Repeatable KV on-hit rider lacks a hit gate")
        if has_reach:return _delivery_recipe("kv_attack_action_hit_retry","hit","kv_attack_action_state_recursion",save_ability,additional)
        return _delivery_recipe("kv_attack_action_hit_failed_save_retry","hit_and_failed_save","kv_attack_action_state_recursion",save_ability)
    if has_reach:
        if hit_gated:return _delivery_recipe("single_activation_hit","hit","single_activation",save_ability,additional)
        return _delivery_recipe("single_activation_automatic","automatic","single_activation",save_ability,additional)
    if hit_gated:return _delivery_recipe("single_activation_hit_failed_save","hit_and_failed_save","single_activation",save_ability)
    return _delivery_recipe("single_activation_failed_save","failed_save","single_activation",save_ability)


def _effect_available(target:Target,effect:dict[str,Any],target_role:str)->bool:
    role=effect.get("target_role","all")
    if role not in {"all",target_role}:return False
    dependency=effect.get("requires_condition")
    if dependency and dependency.lower() in target.condition_immunities:return False
    conditions=list(effect.get("conditions",[]));outcomes=list(effect.get("outcomes",[]))
    return bool(outcomes) or any(condition.lower() not in target.condition_immunities for condition in conditions)


EFFECTIVE="effective"
PARTIALLY_EFFECTIVE="partially_effective"
INEFFECTIVE_STRUCTURAL="ineffective_structural"
INEFFECTIVE_NULLIFIED="ineffective_nullified"
EFFECTIVENESS_NOT_APPLICABLE="not_applicable"


def _catalog_effectiveness(target:Target,effects:Sequence[dict[str,Any]],target_role:str,*,maximum_size:str|None=None,required_creature_type:str|None=None,modeled_control:bool=True)->dict[str,Any]:
    """Derive publication-only exact-source effectiveness from evaluator facts."""
    eligible=target_is_eligible(target,maximum_size,required_creature_type)
    declared:list[str]=[];surviving:list[str]=[];reasons:list[str]=[]
    if not modeled_control:
        return {"status":EFFECTIVENESS_NOT_APPLICABLE,"effective":False,"declared":declared,"surviving":surviving,"reasons":reasons}
    applicable=[]
    for effect in effects:
        if effect.get("target_role","all") in {"all",target_role}:applicable.append(effect)
    for effect in applicable:
        labels=[*(f"condition:{str(condition).lower()}" for condition in effect.get("conditions",[])),*(f"outcome:{str(outcome).lower()}" for outcome in effect.get("outcomes",[]))]
        declared.extend(labels)
    if not declared:raise ValueError("Modeled catalog control source has no applicable consequences")
    if not eligible:
        if maximum_size and not target_is_eligible(target,maximum_size):reasons.append(f"exceeds_maximum_size:{maximum_size.lower()}")
        if required_creature_type and target.creature_type.lower()!=required_creature_type.lower():reasons.append(f"requires_creature_type:{required_creature_type.lower()}")
        if not reasons:raise ValueError("Structurally ineligible catalog source has no maintained reason")
        return {"status":INEFFECTIVE_STRUCTURAL,"effective":False,"declared":declared,"surviving":surviving,"reasons":reasons}
    for effect in applicable:
        conditions=[str(condition) for condition in effect.get("conditions",[])];outcomes=[str(outcome) for outcome in effect.get("outcomes",[])];dependency=effect.get("requires_condition")
        if dependency and str(dependency).lower() in target.condition_immunities:
            token=f"dependency_condition_immune:{str(dependency).lower()}"
            if token not in reasons:reasons.append(token)
            if _effect_available(target,effect,target_role):raise ValueError("Catalog dependency evidence disagrees with evaluator availability")
            continue
        effect_surviving=[*(f"condition:{condition.lower()}" for condition in conditions if condition.lower() not in target.condition_immunities),*(f"outcome:{outcome.lower()}" for outcome in outcomes)]
        for condition in conditions:
            if condition.lower() in target.condition_immunities:
                token=f"immune_condition:{condition.lower()}"
                if token not in reasons:reasons.append(token)
        if bool(effect_surviving)!=_effect_available(target,effect,target_role):raise ValueError("Catalog consequence evidence disagrees with evaluator availability")
        surviving.extend(effect_surviving)
    if surviving and len(surviving)==len(declared):status=EFFECTIVE
    elif surviving:status=PARTIALLY_EFFECTIVE
    else:status=INEFFECTIVE_NULLIFIED
    if status==EFFECTIVE and reasons:raise ValueError("Fully effective catalog source cannot retain nullification reasons")
    if status!=EFFECTIVE and not reasons:raise ValueError("Reduced catalog effectiveness lacks a maintained reason")
    return {"status":status,"effective":bool(surviving),"declared":declared,"surviving":surviving,"reasons":reasons}


def _eldritch_knight_spellcasting_modifier(row:dict[str,Any],level:int)->int:
    """Return the one maintained EK ability modifier used by attacks and save DCs."""
    return int(row["spellcasting_ability_modifier_by_level"][str(level)])


def _automatic_save_success(target:Target,scenario:dict[str,Any])->bool:
    for rule in scenario.get("automatic_success_if",[]):
        kind,value=str(rule).split(":",1)
        if kind=="condition_immunity" and value in target.condition_immunities:return True
        if kind=="source_explicit" and bool(getattr(target,value,False)):return True
    return False


def _resolved_targeting(row:dict[str,Any],scenario:dict[str,Any],level:int)->dict[str,Any]|None:
    targeting=scenario.get("targeting")
    if targeting is None:return None
    resolved=deepcopy(targeting)
    if targeting["mode"]=="capped_selectable":
        highest_slot=int(row["spell_access"]["highest_slot_level_by_fighter_level"][str(level)]);spell_level=int(scenario["spell_level"]);increments=max(0,highest_slot-spell_level)//int(targeting["higher_slot_levels_per_increment"])
        resolved["maximum_target_cap"]=int(targeting["base_target_cap"])+increments*int(targeting["higher_slot_target_increment"])
    return resolved


def _finite_penalty_save_failure_probability(target:Target,ability:str,dc:int,die_sides:int,*,advantage:bool=False,disadvantage:bool=False,magic_resistance:bool=True)->float:
    """Enumerate ``d20 - 1dN`` without replacing the die with an average."""
    if die_sides<2:raise ValueError("Finite save-penalty die must have at least two sides")
    return 1-modified_save_success_probability(target,ability,dc,advantage=advantage,disadvantage=disadvantage,magic_resistance=magic_resistance,penalty_die_sides=die_sides)


def _finite_penalty_with_disadvantage_probability(target:Target,ability:str,dc:int,die_sides:int,disadvantage_probability:float,*,advantage:bool=False,magic_resistance:bool=True)->float:
    """Combine an independent finite penalty and probabilistic Disadvantage exactly."""
    if not 0.0<=disadvantage_probability<=1.0:raise ValueError("Disadvantage probability must be between zero and one")
    ordinary=_finite_penalty_save_failure_probability(target,ability,dc,die_sides,advantage=advantage,magic_resistance=magic_resistance)
    disadvantaged=_finite_penalty_save_failure_probability(target,ability,dc,die_sides,advantage=advantage,disadvantage=True,magic_resistance=magic_resistance)
    return disadvantage_probability*disadvantaged+(1-disadvantage_probability)*ordinary


def _attack_action_retry_probability(attacks:int,attempt_success:float,*,initial_state:tuple[int,...]=(),legal_attempt_states:Callable[[tuple[int,...]],tuple[tuple[int,...],...]]|None=None)->float:
    """Resolve repeatable attack-delivered control within one ordinary Attack action."""
    if attacks<0:raise ValueError("Attack-action retry opportunities cannot be negative")
    if not 0.0<=attempt_success<=1.0:raise ValueError("Attempt probability must be between zero and one")
    @lru_cache(maxsize=None)
    def choose(attacks_remaining:int,state:tuple[int,...])->float:
        if attacks_remaining==0:return 0.0
        next_states=(state,) if legal_attempt_states is None else legal_attempt_states(state)
        return max((attempt_success+(1-attempt_success)*choose(attacks_remaining-1,next_state) for next_state in next_states),default=0.0)
    return choose(attacks,initial_state)


def _attack_action_expected_occurrences(attacks:int,attempt_success:float,*,initial_state:tuple[int,...]=(),legal_attempt_states:Callable[[tuple[int,...]],tuple[tuple[int,...],...]]|None=None)->float:
    """Sum successful accumulating events across every legal declaration."""
    if attacks<0:raise ValueError("Attack-action occurrence opportunities cannot be negative")
    if not 0.0<=attempt_success<=1.0:raise ValueError("Attempt probability must be between zero and one")
    @lru_cache(maxsize=None)
    def choose(attacks_remaining:int,state:tuple[int,...])->float:
        if attacks_remaining==0:return 0.0
        next_states=(state,) if legal_attempt_states is None else legal_attempt_states(state)
        return max((attempt_success+choose(attacks_remaining-1,next_state) for next_state in next_states),default=0.0)
    return choose(attacks,initial_state)


def _repeat_rider_probability(model:AuthorityModel,config:dict[str,Any],level:int,tier:int,psi_cost:int,attempt_success:float)->float:
    """Optimize retry legality for one fixed rider tier without target identity state."""
    if model.projection["core"]["manifested_strike"]["rider_repeatability"]!="per_manifested_strike":raise ValueError("Unsupported canonical rider repeatability")
    resources=_kv_retry_resources(model,config,level);attacks=int(resources["attacks_per_action"]);psi_pool=int(resources["psi_pool"]);blood_budget=int(resources["blood_tax_budget"]);mastery_remaining=int(resources["overload_mastery_uses"]);tier_two_limit=int(resources["tier_two_limit"]);blood_tax=int(resources["blood_tax_by_tier"][tier])
    def legal_attempt_states(state:tuple[int,...])->tuple[tuple[int,...],...]:
        psi_spent,blood_spent,tier_twos,remaining_mastery,mastery_mode=state
        if tier==2 and tier_twos>=tier_two_limit:return ()
        next_psi=psi_spent+psi_cost
        if next_psi>psi_pool:return ()
        states=[]
        for paid_tax,next_mastery,next_mode,_ in model.overload_payment_options(blood_tax,remaining_mastery,mastery_mode):
            next_blood=blood_spent+paid_tax
            if next_blood>blood_budget:continue
            states.append((next_psi,next_blood,tier_twos+int(tier==2),next_mastery,next_mode))
        return tuple(states)
    return _attack_action_retry_probability(attacks,attempt_success,initial_state=(0,0,0,mastery_remaining,0 if mastery_remaining else 2),legal_attempt_states=legal_attempt_states)


def _repeat_rider_expected_occurrences(model:AuthorityModel,config:dict[str,Any],level:int,tier:int,psi_cost:int,attempt_success:float)->float:
    """Optimize legal declarations and sum successes for accumulating events."""
    if model.projection["core"]["manifested_strike"]["rider_repeatability"]!="per_manifested_strike":raise ValueError("Unsupported canonical rider repeatability")
    resources=_kv_retry_resources(model,config,level);attacks=int(resources["attacks_per_action"]);psi_pool=int(resources["psi_pool"]);blood_budget=int(resources["blood_tax_budget"]);mastery_remaining=int(resources["overload_mastery_uses"]);tier_two_limit=int(resources["tier_two_limit"]);blood_tax=int(resources["blood_tax_by_tier"][tier])
    def legal_attempt_states(state:tuple[int,...])->tuple[tuple[int,...],...]:
        psi_spent,blood_spent,tier_twos,remaining_mastery,mastery_mode=state
        if tier==2 and tier_twos>=tier_two_limit:return ()
        next_psi=psi_spent+psi_cost
        if next_psi>psi_pool:return ()
        states=[]
        for paid_tax,next_mastery,next_mode,_ in model.overload_payment_options(blood_tax,remaining_mastery,mastery_mode):
            next_blood=blood_spent+paid_tax
            if next_blood<=blood_budget:states.append((next_psi,next_blood,tier_twos+int(tier==2),next_mastery,next_mode))
        return tuple(states)
    return _attack_action_expected_occurrences(attacks,attempt_success,initial_state=(0,0,0,mastery_remaining,0 if mastery_remaining else 2),legal_attempt_states=legal_attempt_states)


def _battle_master_retry_probability(attacks:int,superiority_dice:int,hit_probability:float,save_fail_probability:float)->float:
    """Resolve one fixed on-hit maneuver across one ordinary Attack action."""
    if attacks<0 or superiority_dice<0:raise ValueError("Battle Master retry resources cannot be negative")
    if not 0.0<=hit_probability<=1.0 or not 0.0<=save_fail_probability<=1.0:raise ValueError("Battle Master retry probabilities must be between zero and one")
    @lru_cache(maxsize=None)
    def resolve(attacks_remaining:int,dice_remaining:int)->float:
        if attacks_remaining==0 or dice_remaining==0:return 0.0
        later_after_miss=resolve(attacks_remaining-1,dice_remaining)
        later_after_saved_hit=resolve(attacks_remaining-1,dice_remaining-1)
        return (1-hit_probability)*later_after_miss+hit_probability*(save_fail_probability+(1-save_fail_probability)*later_after_saved_hit)
    return resolve(attacks,superiority_dice)


def _battle_master_expected_occurrences(attacks:int,superiority_dice:int,hit_probability:float,save_fail_probability:float)->float:
    """Sum successful accumulating maneuver events while dice remain."""
    if attacks<0 or superiority_dice<0:raise ValueError("Battle Master occurrence resources cannot be negative")
    if not 0.0<=hit_probability<=1.0 or not 0.0<=save_fail_probability<=1.0:raise ValueError("Battle Master occurrence probabilities must be between zero and one")
    @lru_cache(maxsize=None)
    def resolve(attacks_remaining:int,dice_remaining:int)->float:
        if attacks_remaining==0 or dice_remaining==0:return 0.0
        later_after_miss=resolve(attacks_remaining-1,dice_remaining)
        later_after_hit=resolve(attacks_remaining-1,dice_remaining-1)
        return (1-hit_probability)*later_after_miss+hit_probability*(save_fail_probability+later_after_hit)
    return resolve(attacks,superiority_dice)


def _eldritch_strike_primer_probability(attacks:int,hit_probability:float)->float:
    """Return the chance that one ordinary primer Attack action establishes a mark."""
    if attacks<0:raise ValueError("Eldritch Strike primer attacks cannot be negative")
    if not 0.0<=hit_probability<=1.0:raise ValueError("Eldritch Strike primer probability must be between zero and one")
    return 1-(1-hit_probability)**attacks


def _composed_eldritch_knight_scenarios(comparators:dict[str,Any],target:Target,*,mind_sliver_timing:str="cross_turn")->list[dict[str,Any]]:
    """Expand configured EK spells through reusable, non-published save primers.

    Generated variants join the maintained legal evaluation inventory. Mind Sliver is
    admitted only for the approved cross-turn window; the unestablished
    same-Attack-action sequence deliberately produces no Mind Sliver variant.
    """
    if mind_sliver_timing not in {"cross_turn","same_attack_action"}:raise ValueError("Unsupported Mind Sliver timing convention")
    row=comparators["control"]["eldritch_knight"];configured=list(row["scenarios"]);expanded=list(configured);used_ids={str(item["id"]) for item in configured}
    explicit_eldritch_spells={str(item["spell_id"]) for item in configured if item.get("primer_hit_disadvantage")}
    minimum_level=int(row["eldritch_strike_minimum_level"]);highest_slot=int(row["spell_access"]["highest_slot_level_by_fighter_level"][str(target.level)])

    def add(source:dict[str,Any],scenario_id:str,primers:list[str])->None:
        if scenario_id in used_ids:return
        variant=deepcopy(source);variant["id"]=scenario_id;variant["_composed_save_primers"]=primers;expanded.append(variant);used_ids.add(scenario_id)

    for scenario in configured:
        if "save" not in scenario or scenario.get("primer_hit_disadvantage") or scenario["spell_id"]=="mind_sliver":continue
        access_legal=int(scenario["spell_level"])==0 or int(scenario["spell_level"])<=highest_slot
        if target.level>=minimum_level and access_legal and scenario["spell_id"] not in explicit_eldritch_spells:
            add(scenario,f"{scenario['id']}_after_eldritch_strike",["eldritch_strike"])
        if mind_sliver_timing!="cross_turn" or scenario.get("delivery")!="action_spell" or not access_legal:continue
        add(scenario,f"{scenario['id']}_after_mind_sliver",["mind_sliver"])
        if target.level>=minimum_level:add(scenario,f"{scenario['id']}_after_mind_sliver_and_eldritch_strike",["mind_sliver","eldritch_strike"])
    return expanded


def _save_failure_with_primers(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target,scenario:dict[str,Any],dc:int,weapon_bonus_total:int)->tuple[float,float,float,dict[str,Any]]:
    """Resolve the initial save with exact, independently established primers."""
    primers=set(str(item) for item in scenario.get("_composed_save_primers",[]))
    if scenario.get("primer_hit_disadvantage"):primers.add("eldritch_strike")
    if not primers<={"mind_sliver","eldritch_strike"}:raise ValueError("Unsupported composed save primer")
    advantage=bool(scenario.get("initial_save_advantage"));magic_resistance=bool(row["magic_resistance_applies"]);ability=str(scenario["save"])
    normal_fail=1-modified_save_success_probability(target,ability,dc,advantage=advantage,magic_resistance=magic_resistance)
    eldritch_probability=0.0;eldritch_weapon_attacks=0
    if "eldritch_strike" in primers:
        eldritch_weapon_attacks=int(level_config(config,target.level)["attacks_per_action"])-int("mind_sliver" in primers)
        if eldritch_weapon_attacks<0:raise ValueError("War Magic primer composition cannot use negative weapon attacks")
        primer=attack_probabilities(weapon_bonus_total,target.ac);eldritch_probability=_eldritch_strike_primer_probability(eldritch_weapon_attacks,primer[1]+primer[2])
    disadvantaged_fail=1-modified_save_success_probability(target,ability,dc,advantage=advantage,disadvantage=True,magic_resistance=magic_resistance)
    ordinary_composed=eldritch_probability*disadvantaged_fail+(1-eldritch_probability)*normal_fail
    mind_sliver_probability=0.0;initial_fail=ordinary_composed
    if "mind_sliver" in primers:
        mind_sliver_probability=1-modified_save_success_probability(target,"intelligence",dc,magic_resistance=magic_resistance)
        penalized=_finite_penalty_with_disadvantage_probability(target,ability,dc,4,eldritch_probability,advantage=advantage,magic_resistance=magic_resistance)
        initial_fail=mind_sliver_probability*penalized+(1-mind_sliver_probability)*ordinary_composed
    timing="cross_turn" if "mind_sliver" in primers else ("prior_attack_action" if "eldritch_strike" in primers else "none")
    metadata={"primers":sorted(primers),"timing":timing,"mind_sliver_establishment_probability":mind_sliver_probability,"eldritch_strike_weapon_attacks":eldritch_weapon_attacks,"eldritch_strike_establishment_probability":eldritch_probability,"initial_failure_probability":initial_fail,"repeat_failure_probability":normal_fail}
    return initial_fail,1-initial_fail,normal_fail,metadata


def _closed_form_escape(target:Target,scenario:dict[str,Any],dc:int,application_probability:float,horizon:int)->dict[str,Any]|None:
    """Resolve the reviewed adversarial escape-and-exit convention analytically."""
    restrained=next((effect for effect in scenario["effects"] if "restrained" in effect.get("conditions",[]) and effect.get("area_trigger")),None)
    escape=next((item for item in scenario.get("escapes",[]) if item.get("action")=="action" and item.get("dc")=="spell_save_dc" and item.get("success")=="ends_restrained"),None)
    if restrained is None or escape is None:return None
    if scenario.get("area_exit_policy")!="exit_as_soon_as_legally_possible_after_first_movement":raise ValueError("Modeled action escape lacks the standing legal-exit policy")
    if restrained["area_trigger"] not in {"first_entry_or_start_turn","initial_entry_or_end_turn"}:raise ValueError("Unsupported modeled area trigger")
    ability,skill=str(escape["check"]).split("_",1);success=ability_check_success_probability(target,ability,dc,skill);failure=1-success
    attempts=tuple(application_probability*failure**index for index in range(horizon));exits=tuple(attempt*success for attempt in attempts)
    active_by_basis={basis:attempts for basis in ("target_turn_window","attack_opportunity","incoming_attack_opportunity","save_opportunity")}
    return {"effect_id":restrained["id"],"check":escape["check"],"success_probability":success,"attempt_probabilities":attempts,"legal_exit_probabilities":exits,"condition_active_probabilities_by_basis":active_by_basis,"terminal_probability":attempts[-1]*failure if attempts else application_probability,"area_trigger":restrained["area_trigger"],"area_exit_policy":scenario["area_exit_policy"]}


def _mastery_shadow_component(mastery:dict[str,Any],discipline_id:str,application_probability:float,expected_occurrences:float|None=None)->dict[str,Any]:
    component={"source_effect":f"mastery:{mastery['kind']}","labels":[('outcome',outcome) for outcome in mastery["control_outcomes"]],"duration":mastery.get("control_duration"),"application_probability":application_probability,"repeat_survival_probability":None,"repeat_checkpoint":None,"magnitude_feet":mastery.get("control_magnitude_feet"),"attack_scope":mastery.get("attack_scope"),"reason":f"KineticVanguard.yaml calculator.harness_mechanics.disciplines[{discipline_id}].mastery"}
    if "forced_movement" in mastery["control_outcomes"]:component["expected_occurrences"]=expected_occurrences
    return component


def _catalog_rider_scenario(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str,entity_id:str,tier:int,target_role:str="primary")->dict[str,Any]:
    """Project rider-only catalog evidence without changing headline packages."""
    package=_kv_scenario(model,config,target,discipline_id,entity_id,tier,target_role)
    rider_components=[component for component in package["shadow_components"] if not str(component["source_effect"]).startswith("mastery:")]
    feature=model.feature(entity_id,target.level,tier);control=next(item for item in feature["control_tiers"] if int(item["tier"])==tier)
    effectiveness=_catalog_effectiveness(target,control["effects"],target_role,maximum_size=control.get("maximum_size"),required_creature_type=control.get("required_creature_type"))
    return {**package,"mastery":0.0,"whole":package["named"],"after_repeats":package["named"],"shadow_components":rider_components,"effectiveness":effectiveness,"delivery_recipe":package["rider_delivery_recipe"]}


def _kv_scenario(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str,entity_id:str,tier:int,target_role:str="primary")->dict[str,Any]:
    feature=model.feature(entity_id,target.level,tier);control=next((item for item in feature.get("control_tiers",[]) if int(item["tier"])==tier),None)
    if control is None:raise ValueError(f"Configured control scenario {entity_id} Tier {tier} lacks canonical control mechanics")
    eligible=target_is_eligible(target,control.get("maximum_size"),control.get("required_creature_type"))
    profile=config["kv_profile"];psi_modifier=int(profile["psionic_ability_modifier"]);bonus=model.kv_attack_bonus(target.level,psi_modifier)+int(profile["archery_attack_bonus"])
    probabilities=attack_probabilities(bonus,target.ac);reach=probabilities[1]+probabilities[2] if control.get("hit_gated") else 1.0;failed=0.0;repeat_failed=0.0
    if control["application"]=="failed_save":
        save=control["save"];save=model.disciplines[discipline_id]["signature_save"] if save=="discipline_signature" else save
        failed=1-save_success_probability(target,save,model.kv_save_dc(target.level,psi_modifier));repeat_failed=1-save_success_probability(target,save,model.kv_save_dc(target.level,psi_modifier),bool(control.get("repeat_save_disadvantage")))
    effects=[effect for effect in control["effects"] if eligible and _effect_available(target,effect,target_role)]
    def effect_probability(effect:dict[str,Any])->float:return reach*failed if effect["gate"]=="on_failed_save" else reach
    named_single=max((effect_probability(effect) for effect in effects),default=0.0)
    mastery=model.disciplines[discipline_id]["mastery"];mastery_available=target_role=="primary" and bool(mastery["control_outcomes"]) and control.get("hit_gated") and not feature.get("replaces_mastery")
    if mastery.get("maximum_size") and not target_is_eligible(target,mastery["maximum_size"]):mastery_available=False
    mastery_single=reach if mastery_available else 0.0;rider=feature.get("damage_delivery")=="on_hit_rider" and feature.get("activation")=="on_hit"
    repeat=lambda value:_repeat_rider_probability(model,config,target.level,tier,int(feature["psi_cost"]),value) if rider else value
    expected=lambda value:_repeat_rider_expected_occurrences(model,config,target.level,tier,int(feature["psi_cost"]),value) if rider else value
    named=repeat(named_single);mastery_value=repeat(mastery_single);whole=max(named,mastery_value);repeat_count=int(config["methodology"]["rounds"])-1 if control.get("repeat_save_trigger")=="start_of_affected_turn" else 0
    mastery_attack_source=f"mastery:{mastery['kind']}" if mastery_available and "attack_disadvantage" in mastery["control_outcomes"] and mastery.get("attack_scope")=="next_attack" else None
    after=[];shadow_components=[]
    for effect_index,effect in enumerate(effects):
        value=repeat(effect_probability(effect))
        if repeat_count and effect["gate"]=="on_failed_save":value*=repeat_failed**repeat_count
        after.append(value)
        labels=[*(('condition',condition) for condition in effect.get("conditions",[]) if condition.lower() not in target.condition_immunities),*(('outcome',outcome) for outcome in effect.get("outcomes",[]))]
        component={"source_effect":f"{entity_id}:T{tier}:effect{effect_index}","labels":labels,"duration":effect["duration"],"application_probability":repeat(effect_probability(effect)),"repeat_survival_probability":repeat_failed if repeat_count and effect["gate"]=="on_failed_save" else None,"repeat_checkpoint":control.get("repeat_save_trigger") if repeat_count and effect["gate"]=="on_failed_save" else None,"magnitude_feet":effect.get("magnitude_feet"),"magnitude":effect.get("magnitude"),"attack_scope":effect.get("attack_scope"),"pricing_status":effect.get("pricing_status"),"overlapping_attack_impairment_sources":[mastery_attack_source] if mastery_attack_source and ('outcome','attack_disadvantage') in labels and effect.get("attack_scope")=="all_attacks" else [],"reason":f"KineticVanguard.yaml calculator.harness_mechanics.feature_rules[{entity_id}].control_tiers[T{tier}]"}
        if "failed_save_magnitude_feet" in effect or "successful_save_magnitude_feet" in effect:
            failed_probability=repeat(reach*failed);reached_probability=repeat(reach);success_probability=max(0.0,reached_probability-failed_probability)
            branch_labels=[item for item in labels if item[1]=="forced_movement"]
            other_labels=[item for item in labels if item[1]!="forced_movement"]
            if branch_labels:
                shadow_components.append({**component,"source_effect":f"{component['source_effect']}:failed_save","labels":branch_labels,"application_probability":failed_probability,"magnitude_feet":effect.get("failed_save_magnitude_feet"),"expected_occurrences":expected(reach*failed)})
                shadow_components.append({**component,"source_effect":f"{component['source_effect']}:successful_save","labels":branch_labels,"application_probability":success_probability,"magnitude_feet":effect.get("successful_save_magnitude_feet"),"expected_occurrences":max(0.0,expected(reach)-expected(reach*failed))})
            if other_labels:shadow_components.append({**component,"labels":other_labels})
        else:
            if any(label=="forced_movement" for _,label in labels):component["expected_occurrences"]=expected(effect_probability(effect))
            shadow_components.append(component)
    if mastery_available and mastery["control_outcomes"]:
        shadow_components.append(_mastery_shadow_component(mastery,discipline_id,mastery_value,expected(mastery_single)))
    repeat=max([mastery_value,*after]);suffix=f":{target_role}" if target_role!="primary" else ""
    recipe_control={**control,"save":save} if control["application"]=="failed_save" else control
    return {"build":discipline_id,"scenario":f"{entity_id}:T{tier}{suffix}","eligible":eligible,"reach":100*reach,"named":100*named,"mastery":100*mastery_value,"whole":100*whole,"after_repeats":100*repeat,"shadow_components":shadow_components,"rider_delivery_recipe":_kv_rider_delivery_recipe(recipe_control,rider,target_role)}


def _mastery_scenario(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str)->dict[str,Any]:
    mastery=model.disciplines[discipline_id]["mastery"];profile=config["kv_profile"]
    bonus=model.kv_attack_bonus(target.level,int(profile["psionic_ability_modifier"]))+int(profile["archery_attack_bonus"]);probabilities=attack_probabilities(bonus,target.ac);reach=probabilities[1]+probabilities[2]
    eligible=not mastery.get("maximum_size") or target_is_eligible(target,mastery["maximum_size"])
    attacks=int(level_config(config,target.level)["attacks_per_action"]);whole=_attack_action_retry_probability(attacks,reach) if eligible and mastery["control_outcomes"] else 0.0
    component=_mastery_shadow_component(mastery,discipline_id,whole,attacks*reach if eligible else 0.0)
    recipe=_delivery_recipe("mastery_attack_action_hit_retry","hit","ordinary_attack_action_independent_hits") if mastery["control_outcomes"] else _delivery_recipe("no_modeled_control","none","none")
    return {"build":discipline_id,"scenario":f"mastery:{mastery['kind']}","eligible":eligible,"reach":100*reach,"named":0.0,"mastery":100*whole,"whole":100*whole,"after_repeats":100*whole,"shadow_components":[component] if component["labels"] else [],"delivery_recipe":recipe}


def _catalog_mastery_scenario(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str)->dict[str,Any]:
    """Attach publication-only effectiveness to Mastery-only evidence."""
    scenario=_mastery_scenario(model,config,target,discipline_id);mastery=model.disciplines[discipline_id]["mastery"];outcomes=list(mastery["control_outcomes"])
    effectiveness=_catalog_effectiveness(target,[{"outcomes":outcomes}],"primary",maximum_size=mastery.get("maximum_size"),modeled_control=bool(outcomes))
    return {**scenario,"effectiveness":effectiveness}


def _comparator_scenario(model:AuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:Target,build_id:str,scenario:dict[str,Any])->dict[str,Any]:
    row=comparators["control"][build_id];pb=model.progression("proficiency_bonus",target.level);weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(target.level)]);weapon_bonus_total=pb+int(row["attack_ability_modifier"])+weapon_bonus;reach=1.0
    if build_id=="battle_master":
        known=set(row["known_maneuvers_by_level"][str(target.level)]);legal=scenario["id"] in known;eligible=target.level>=int(row["minimum_level"]) and legal and target_is_eligible(target,scenario.get("maximum_size"))
        if scenario.get("hit_gated"):probabilities=attack_probabilities(weapon_bonus_total,target.ac);reach=probabilities[1]+probabilities[2]
        dc=int(row["save_dc_base"])+pb+int(row["save_ability_modifier"]);normal_fail=1-save_success_probability(target,scenario["save"],dc,False,bool(row["magic_resistance_applies"]))
        attacks=int(level_config(config,target.level)["attacks_per_action"]);superiority_dice=int(comparators["damage"]["battle_master"]["superiority_pool_by_level"][str(target.level)]);application=_battle_master_retry_probability(attacks,superiority_dice,reach,normal_fail) if eligible else 0.0
        components=[];applications=[];horizon=int(config["methodology"]["rounds"])
        for effect in scenario["effects"]:
            declared_conditions=[str(condition) for condition in effect.get("conditions",[])];effective_conditions=[condition for condition in declared_conditions if condition.lower() not in target.condition_immunities]
            if declared_conditions and not effective_conditions:continue
            labels=[*(('condition',condition) for condition in effective_conditions),*(('outcome',outcome) for outcome in effect.get("outcomes",[]))]
            if not labels:continue
            recovery=effect.get("recovery");qualifiers=dict(effect.get("qualifiers",{}));active_by_basis=None
            if recovery:
                qualifiers.update({f"recovery_{key}":value for key,value in recovery.items()});active_by_basis={"target_turn_window":(application,*((0.0,)*(horizon-1)))}
            if scenario["disposition"]=="diagnostic_unpriced":active_by_basis={}
            else:applications.append(application)
            metadata=", ".join(f"{key}={scenario[key]}" for key in ("audit_comment_id","source_scope","disposition"))
            component={"source_effect":f"{scenario['id']}:{effect['id']}","labels":labels,"duration":effect["duration"],"application_probability":application,"repeat_survival_probability":None,"repeat_checkpoint":None,"magnitude_feet":effect.get("magnitude_feet"),"magnitude":effect.get("magnitude"),"attack_scope":effect.get("attack_scope"),"pricing_status":effect.get("pricing_status") or ("context_required" if scenario["disposition"]=="diagnostic_unpriced" else None),"qualifiers":qualifiers or None,"active_probabilities_by_basis":active_by_basis,"suppressed_recovery_options":effect.get("suppressed_recovery_options",[]),"disjoint_stage_group":"","breaks":[],"escapes":[],"reason":f"harness/comparators/fighter-subclasses.json control.{build_id}; {metadata}; effect={effect['id']}, gate={effect['gate']}"}
            if any(label=="forced_movement" for _,label in labels):component["expected_occurrences"]=_battle_master_expected_occurrences(attacks,superiority_dice,reach,normal_fail) if eligible else 0.0
            components.append(component)
        value=max(applications,default=0.0)
        return {"build":build_id,"scenario":scenario["id"],"spell_id":None,"audit_comment_id":scenario["audit_comment_id"],"source_scope":scenario["source_scope"],"disposition":scenario["disposition"],"eligible":eligible,"reach":100*reach,"named":100*value,"mastery":0.0,"whole":100*value,"after_repeats":100*value,"shadow_components":components,"targeting":None,"breaks":[],"escapes":[],"escape_resolution":None,"context_predicates":list(scenario.get("context_predicates",[])),"area_exit_policy":None,"turn_branches":[],"save_composition":{"primers":[],"initial_failure_probability":application,"repeat_failure_probability":None},"automatic_save_success":False,"automatic_success_rules":[]}

    if not scenario.get("spell_attack") and "save" not in scenario and not scenario.get("automatic_effect"):raise ValueError("Eldritch Knight scenario requires a spell attack, saving throw, or automatic effect")
    composed_primers=set(str(item) for item in scenario.get("_composed_save_primers",[]));uses_eldritch_strike=bool(scenario.get("primer_hit_disadvantage")) or "eldritch_strike" in composed_primers
    highest_slot=int(row["spell_access"]["highest_slot_level_by_fighter_level"][str(target.level)]);access_legal=int(scenario["spell_level"])==0 or int(scenario["spell_level"])<=highest_slot;primer_legal=not uses_eldritch_strike or target.level>=int(row["eldritch_strike_minimum_level"])
    eligible=target.level>=int(row["minimum_level"]) and access_legal and primer_legal and target_is_eligible(target,scenario.get("maximum_size"),scenario.get("required_creature_type"));automatic_success=_automatic_save_success(target,scenario)
    if scenario.get("hit_gated"):
        attack_bonus=pb+_eldritch_knight_spellcasting_modifier(row,target.level) if scenario.get("spell_attack") else weapon_bonus_total;probabilities=attack_probabilities(attack_bonus,target.ac);reach=probabilities[1]+probabilities[2]
    normal_fail=None;normal_success=None;initial_success=None;save_composition={"primers":[],"initial_failure_probability":None,"repeat_failure_probability":None};initial_probability=reach if scenario.get("spell_attack") else (1.0 if scenario.get("automatic_effect") else 0.0)
    if "save" in scenario:
        dc=int(row["save_dc_base"])+pb+_eldritch_knight_spellcasting_modifier(row,target.level);initial_probability,initial_success,normal_fail,save_composition=_save_failure_with_primers(model,config,row,target,scenario,dc,weapon_bonus_total);normal_success=1-normal_fail
    effective_conditions={condition.lower() for effect in scenario["effects"] for condition in effect.get("conditions",[]) if condition.lower() not in target.condition_immunities}
    components=[];applications=[];terminals=[];horizon=int(config["methodology"]["rounds"]);multi_effect=len(scenario["effects"])>1;escape_resolution=_closed_form_escape(target,scenario,dc,initial_probability,horizon) if "save" in scenario and "restrained" in effective_conditions and scenario["disposition"]!="diagnostic_unpriced" else None
    if eligible and not automatic_success:
        for effect in scenario["effects"]:
            dependency=effect.get("requires_condition_effective")
            if dependency and dependency.lower() not in effective_conditions:continue
            labels=[*(('condition',condition) for condition in effect.get("conditions",[]) if condition.lower() not in target.condition_immunities),*(('outcome',outcome) for outcome in effect.get("outcomes",[]))]
            if not labels:continue
            gate=effect["gate"]
            if gate in {"on_hit","on_failed_save"}:application=initial_probability
            elif gate=="automatic":application=1.0
            elif gate=="on_successful_save":application=float(initial_success or 0.0)
            elif gate=="after_failed_second_save":application=initial_probability*float(normal_fail or 0.0)
            else:raise ValueError(f"Unsupported comparator effect gate: {gate}")
            if "secondary_save" in effect:
                secondary=effect["secondary_save"];secondary_fail=1-modified_save_success_probability(target,str(secondary["ability"]),dc,magic_resistance=bool(row["magic_resistance_applies"]));application*=secondary_fail
            if "branch_fraction" in effect:
                fraction=effect["branch_fraction"];application*=float(Fraction(int(fraction["numerator"]),int(fraction["denominator"])))
            if "branch_ids" in effect:
                branches={str(item["id"]):Fraction(int(item["numerator"]),int(item["denominator"])) for item in scenario.get("turn_branches",[])};application*=float(sum((branches[str(branch_id)] for branch_id in effect["branch_ids"]),Fraction(0,1)))
            active_by_basis=None;pattern=effect.get("active_pattern")
            if escape_resolution is not None and effect["id"]==escape_resolution["effect_id"]:active_by_basis=escape_resolution["condition_active_probabilities_by_basis"];terminal=float(escape_resolution["terminal_probability"])
            elif pattern=="first_target_turn_only":active_by_basis={"target_turn_window":(application,*((0.0,)*(horizon-1)))};terminal=0.0
            elif pattern=="remaining_after_first_target_turn":active_by_basis={"target_turn_window":((0.0,)+((application,)*(horizon-1)))};terminal=application
            elif effect.get("repeat_save_trigger") and normal_fail is not None:terminal=application*normal_fail**(horizon-1)
            else:terminal=application
            if scenario["disposition"]=="diagnostic_unpriced" or effect.get("unpriced"):active_by_basis={}
            if active_by_basis!={}:
                applications.append(application);terminals.append(terminal)
            source_effect=f"{scenario['id']}:{effect['id']}" if multi_effect else scenario["id"]
            metadata=", ".join(f"{key}={scenario[key]}" for key in ("spell_id","audit_comment_id","source_scope","disposition","spell_level","delivery","improved_war_magic_eligible") if key in scenario);effect_metadata=", ".join(f"{key}={effect[key]}" for key in ("id","gate","requires_condition_effective","active_pattern","transition_checkpoint","disjoint_stage_group","suppressed_recovery_options","area_trigger","context_predicates","secondary_save","branch_fraction","branch_ids") if key in effect)
            status=effect.get("pricing_status") or ("context_required" if scenario["disposition"]=="diagnostic_unpriced" else None)
            components.append({"source_effect":source_effect,"labels":labels,"duration":effect["duration"],"application_probability":application,"repeat_survival_probability":normal_fail if effect.get("repeat_save_trigger") else None,"repeat_checkpoint":effect.get("repeat_save_trigger"),"magnitude_feet":effect.get("magnitude_feet"),"magnitude":effect.get("magnitude"),"attack_scope":effect.get("attack_scope"),"pricing_status":status,"qualifiers":effect.get("qualifiers"),"active_probabilities_by_basis":active_by_basis,"suppressed_recovery_options":effect.get("suppressed_recovery_options",[]),"disjoint_stage_group":effect.get("disjoint_stage_group",""),"breaks":scenario.get("breaks",[]),"escapes":scenario.get("escapes",[]),"reason":f"harness/comparators/fighter-subclasses.json control.{build_id}; {metadata}"+(f"; {effect_metadata}" if effect_metadata else "")})
        if escape_resolution is not None:
            attempts=escape_resolution["attempt_probabilities"];components.append({"source_effect":f"{scenario['id']}:escape_action","labels":[("outcome","escape_action")],"duration":"one_minute_concentration","application_probability":float(attempts[0]),"repeat_survival_probability":None,"repeat_checkpoint":None,"magnitude_feet":None,"magnitude":None,"attack_scope":None,"pricing_status":None,"qualifiers":{"check":escape_resolution["check"],"dc":"spell_save_dc","timing":"earliest_useful_legal_turn"},"active_probabilities_by_basis":{"target_turn_window":attempts},"disjoint_stage_group":"","breaks":[],"escapes":scenario.get("escapes",[]),"reason":"Closed-form adversarial escape attempts use explicit target skill facts with ability fallback; a successful attempt ends Restrained and invokes the standing legal-exit policy."})
    value=max(applications,default=0.0);after_repeats=max(terminals,default=0.0)
    return {"build":build_id,"scenario":scenario["id"],"spell_id":scenario["spell_id"],"audit_comment_id":scenario["audit_comment_id"],"source_scope":scenario["source_scope"],"disposition":scenario["disposition"],"eligible":eligible,"reach":100*reach,"named":100*value,"mastery":0.0,"whole":100*value,"after_repeats":100*after_repeats,"shadow_components":components,"targeting":_resolved_targeting(row,scenario,target.level),"breaks":list(scenario.get("breaks",[])),"escapes":list(scenario.get("escapes",[])),"escape_resolution":escape_resolution,"context_predicates":list(scenario.get("context_predicates",[])),"area_exit_policy":scenario.get("area_exit_policy"),"turn_branches":deepcopy(scenario.get("turn_branches",[])),"save_composition":save_composition,"automatic_save_success":automatic_success,"automatic_success_rules":list(scenario.get("automatic_success_if",[]))}


def _select_control_value(rows:list[dict[str,Any]])->dict[str,Any]:
    if not rows:raise ValueError("Configured Control Value scenario set is empty at this level")
    eligible=[row for row in rows if row.get("Eligible") is True]
    if not eligible:raise ValueError("Configured Control Value scenario set has no eligible scenario at this level and target")
    return min(eligible,key=lambda row:(-float(row["Control Value CU"]),-float(row["Whole-package control stick %"]),str(row["Scenario"])))


def run(authority:Path,output_dir:Path,levels:set[int],target_limit:int|None,write_detail:bool=True,write_headline:bool=True,profile:str=DEFAULT_PROFILE,write_shadow:bool=False,publication_scenarios:Sequence[dict[str,Any]]=())->dict[str,Any]:
    model=AuthorityModel.load(authority);config=load_config();comparators=load_comparators();targets=load_targets(profile=profile,levels=levels,limit=target_limit);detail=[];audit=[];envelopes=[];shadow_detail=[];value_scenarios=[];catalog_scenarios=[];value_audit=[];value_envelopes=[]
    scenario_sets=config["control_matrix"]["kv_scenarios"]
    if publication_scenarios and not write_shadow:raise ValueError("Publication-only scenarios require Control Value scenario detail")
    publication_by_discipline:dict[str,list[dict[str,Any]]]=defaultdict(list);publication_identities:set[tuple[str,str,int,str]]=set()
    for index,entry in enumerate(publication_scenarios):
        if set(entry)!={"discipline_id","entity_id","tier","target_role"}:raise ValueError(f"Publication-only scenario {index} has invalid keys")
        identity=(str(entry["discipline_id"]),str(entry["entity_id"]),int(entry["tier"]),str(entry["target_role"]))
        if identity in publication_identities:raise ValueError(f"Duplicate publication-only scenario identity: {identity}")
        publication_identities.add(identity);publication_by_discipline[identity[0]].append({"entity_id":identity[1],"tier":identity[2],"target_role":identity[3]})

    def value_row(target:Target,build:str,discipline:str,value:dict[str,Any],*,collect_detail:bool,include_effectiveness:bool=False)->dict[str,Any]:
        metadata={"Build":build,"Discipline":discipline,"Level":target.level,"Target":target.name,"Scenario":value["scenario"]}
        rows=shadow_rows(metadata,value["shadow_components"],horizon=int(config["methodology"]["rounds"]),benchmark_locomotion_speed=target.benchmark_locomotion_speed)
        if collect_detail:shadow_detail.extend(rows)
        total=sum(float(row["Control Value CU"]) for row in rows)
        candidate=sum(row["Pricing Status"]=="candidate" for row in rows)
        unpriced=len(rows)-candidate
        retained_candidate=sum(row["Pricing Status"]=="candidate" and row["Normalization"] not in {"suppressed","combined_into_disjoint_stages"} for row in rows)
        retained_unpriced=sum(row["Pricing Status"]!="candidate" and row["Normalization"] not in {"suppressed","combined_into_disjoint_stages"} for row in rows)
        zero_context=bool(rows and total==0.0 and retained_candidate==0 and unpriced>0)
        disposition="ineligible" if not value["eligible"] else ("priced_nonzero" if total!=0.0 else ("entirely_context_required_or_unsupported" if zero_context else "legitimately_priced_zero"))
        row={**metadata,"Eligible":value["eligible"],"Control Value CU":total,"Whole-package control stick %":value["whole"],"Value Disposition":disposition,"Primitive Rows":len(rows),"Candidate Rows":candidate,"Context/Unsupported Rows":unpriced,"Retained Candidate Rows":retained_candidate,"Retained Context/Unsupported Rows":retained_unpriced,"Zero Entirely Fail-Closed Context":zero_context}
        if include_effectiveness:
            evidence=value.get("effectiveness")
            if not isinstance(evidence,dict):raise ValueError("Catalog scenario lacks effectiveness evidence")
            recipe=value.get("delivery_recipe")
            if not isinstance(recipe,dict) or set(recipe)!={"id","gate","retry_model","save_ability","additional_control_gate"}:raise ValueError("Catalog scenario lacks exact delivery recipe evidence")
            row.update({"Effectiveness Status":evidence["status"],"Effective":evidence["effective"],"Declared Consequences":";".join(evidence["declared"]),"Surviving Consequences":";".join(evidence["surviving"]),"Effectiveness Reasons":";".join(evidence["reasons"]),"Delivery Recipe ID":recipe["id"],"Delivery Gate":recipe["gate"],"Retry Model":recipe["retry_model"],"Resolved Save Ability":recipe["save_ability"],"Additional Control Gate":recipe["additional_control_gate"]})
        return row

    def selected_audit_row(winner:dict[str,Any])->dict[str,Any]:
        return {"Level":winner["Level"],"Target":winner["Target"],"Discipline":winner["Discipline"],"Build":winner["Build"],"Selected Scenario":winner["Scenario"],"Eligible":winner["Eligible"],"Selection Basis":"Control Value","Control Value CU":winner["Control Value CU"],"Whole-package control stick %":winner["Whole-package control stick %"],"Value Disposition":winner["Value Disposition"]}

    for target in targets:
        comparator_winners={}
        for build in ("battle_master","eldritch_knight"):
            scenarios=_composed_eldritch_knight_scenarios(comparators,target) if build=="eldritch_knight" else comparators["control"][build]["scenarios"]
            all_values=[_comparator_scenario(model,config,comparators,target,build,scenario) for scenario in scenarios]
            detail.extend({"Level":target.level,"Target":target.name,**value} for value in all_values)
            scored=[value_row(target,build,"all",value,collect_detail=write_shadow) for value in all_values]
            if write_shadow:value_scenarios.extend(scored)
            comparator_winners[build]=_select_control_value(scored)
            selected=selected_audit_row(comparator_winners[build]);audit.append(selected)
            if write_shadow:value_audit.append(selected)
        for discipline,configured in scenario_sets.items():
            values=[_mastery_scenario(model,config,target,discipline)]
            for entry in configured:
                feature=model.features[entry["entity_id"]]
                if target.level<int(feature["minimum_level"]):continue
                for tier in entry["tiers"]:
                    for target_role in entry.get("target_roles",["primary"]):
                        try:values.append(_kv_scenario(model,config,target,discipline,entry["entity_id"],int(tier),str(target_role)))
                        except Exception as error:
                            if "unavailable" not in str(error):raise
            detail.extend({"Level":target.level,"Target":target.name,**value} for value in values)
            scored=[value_row(target,"kinetic_vanguard",discipline,value,collect_detail=write_shadow) for value in values]
            if write_shadow:value_scenarios.extend(scored)
            winner=_select_control_value(scored);selected=selected_audit_row(winner);audit.append(selected)
            if write_shadow:
                catalog_scenarios.append(value_row(target,"kinetic_vanguard",discipline,_catalog_mastery_scenario(model,config,target,discipline),collect_detail=False,include_effectiveness=True))
                value_audit.append(selected);value_envelopes.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"KV":winner["Control Value CU"],"Eldritch Knight":comparator_winners["eldritch_knight"]["Control Value CU"],"Battle Master":comparator_winners["battle_master"]["Control Value CU"]})
                for entry in publication_by_discipline.get(discipline,[]):
                    try:publication_value=_catalog_rider_scenario(model,config,target,discipline,entry["entity_id"],entry["tier"],entry["target_role"])
                    except Exception as error:
                        if "unavailable" in str(error):continue
                        raise
                    catalog_scenarios.append(value_row(target,"kinetic_vanguard",discipline,publication_value,collect_detail=False,include_effectiveness=True))
            envelopes.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"KV":winner["Whole-package control stick %"],"Eldritch Knight":comparator_winners["eldritch_knight"]["Whole-package control stick %"],"Battle Master":comparator_winners["battle_master"]["Whole-package control stick %"]})
    slug=model.rules_version.replace(".","-");output_dir.mkdir(parents=True,exist_ok=True)
    source_columns={"Rules Version":model.rules_version,"Authority SHA-256":model.authority_sha256,"Catalog SHA-256":file_sha256(DEFAULT_CATALOG),"Roster SHA-256":file_sha256(DEFAULT_ROSTERS),"Target Profile":profile,"Config SHA-256":file_sha256(DEFAULT_CONFIG),"Comparator Config SHA-256":file_sha256(DEFAULT_COMPARATORS),**NOTICE_COLUMNS}
    selection_source={**source_columns,"Control Primitive Catalog SHA-256":file_sha256(DEFAULT_PRIMITIVES),"Control Value Config SHA-256":file_sha256(DEFAULT_SCORING)}
    if write_detail:
        detail_rows=[]
        for item in detail:detail_rows.append({"Level":item["Level"],"Target":item["Target"],"Build":item["build"],"Scenario":item["scenario"],"Eligible":item["eligible"],"Reach/Hit %":f"{item['reach']:.6f}","Named control stick %":f"{item['named']:.6f}","Mastery control floor %":f"{item['mastery']:.6f}","Whole-package control stick %":f"{item['whole']:.6f}","Still controlled after configured repeats %":f"{item['after_repeats']:.6f}",**source_columns})
        audit_rows=[{**row,**selection_source} for row in audit]
        with (output_dir/f"kv-{slug}-control-detail.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(detail_rows[0]));writer.writeheader();writer.writerows(detail_rows)
        with (output_dir/f"kv-{slug}-control-selection-audit.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(audit_rows[0]));writer.writeheader();writer.writerows(audit_rows)
    shadow_path=None;value_paths={}
    if write_shadow:
        shadow_path=output_dir/f"kv-{slug}-control-value-shadow-detail.csv";shadow_source=selection_source;shadow_output=[{**row,**shadow_source} for row in shadow_detail]
        with shadow_path.open("w",newline="",encoding="utf-8") as stream:
            if shadow_output:
                writer=csv.DictWriter(stream,fieldnames=list(shadow_output[0]));writer.writeheader();writer.writerows(shadow_output)
        value_scenario_path=output_dir/f"kv-{slug}-control-value-scenario-detail.csv";catalog_scenario_path=output_dir/f"kv-{slug}-control-catalog-scenario-detail.csv";value_audit_path=output_dir/f"kv-{slug}-control-value-selection-audit.csv";value_matrix_path=output_dir/f"kv-{slug}-control-value-matrix.csv"
        scenario_output=[{**row,**shadow_source} for row in value_scenarios];catalog_output=[{**row,**shadow_source} for row in catalog_scenarios];audit_output=[{**row,**shadow_source} for row in value_audit]
        value_groups:dict[tuple[int,str],list[dict[str,Any]]]=defaultdict(list)
        for row in value_envelopes:value_groups[(int(row["Level"]),str(row["Discipline"]))].append(row)
        value_matrix=[]
        for (level,discipline),values in sorted(value_groups.items()):
            mean=lambda key:sum(float(item[key]) for item in values)/len(values)
            value_matrix.append({"Level":level,"Discipline":discipline,"Kinetic Vanguard Control Value CU":f"{mean('KV'):.12f}","Eldritch Knight Control Value CU":f"{mean('Eldritch Knight'):.12f}","Battle Master Control Value CU":f"{mean('Battle Master'):.12f}","Targets":len(values),**shadow_source})
        for path,output in ((value_scenario_path,scenario_output),(catalog_scenario_path,catalog_output),(value_audit_path,audit_output),(value_matrix_path,value_matrix)):
            with path.open("w",newline="",encoding="utf-8") as stream:
                if output:
                    writer=csv.DictWriter(stream,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
        value_paths={"scenario_detail":value_scenario_path,"catalog_scenario_detail":catalog_scenario_path,"selection_audit":value_audit_path,"matrix":value_matrix_path}
    groups:dict[tuple[int,str],list[dict[str,Any]]]=defaultdict(list)
    for row in envelopes:groups[(int(row["Level"]),str(row["Discipline"]))].append(row)
    rows=[]
    for (level,discipline),values in sorted(groups.items()):
        mean=lambda key:sum(float(item[key]) for item in values)/len(values)
        rows.append(matrix_row({"Level":level,"Discipline":discipline,"Metric":config["control_matrix"]["metric"],"Profile":config["kv_profile"]["id"]},mean("KV"),mean("Eldritch Knight"),mean("Battle Master"),"control"))
    provenance={"rules_version":model.rules_version,"authority_sha256":model.authority_sha256,"catalog_sha256":file_sha256(DEFAULT_CATALOG),"roster_sha256":file_sha256(DEFAULT_ROSTERS),"target_profile":profile,"config_sha256":file_sha256(DEFAULT_CONFIG),"comparator_config_sha256":file_sha256(DEFAULT_COMPARATORS),"control_primitive_catalog_sha256":file_sha256(DEFAULT_PRIMITIVES),"control_value_config_sha256":file_sha256(DEFAULT_SCORING),"evaluator":"exact_analytical_enumeration","aggregation":config["control_matrix"]["aggregation"]}
    paths=write_matrix(output_dir,model.rules_version,"control",rows,provenance) if write_headline else {}
    return {"rules_version":model.rules_version,"detail_rows":len(detail),"audit_rows":len(audit),"matrix_rows":len(rows),"paths":paths,"shadow_rows":len(shadow_detail),"shadow_path":shadow_path,"value_scenario_rows":len(value_scenarios),"catalog_scenario_rows":len(catalog_scenarios),"value_audit_rows":len(value_audit),"value_matrix_rows":len(value_matrix) if write_shadow else 0,"value_paths":value_paths}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--authority",type=Path,default=DEFAULT_AUTHORITY);parser.add_argument("--output-dir",type=Path,required=True);parser.add_argument("--profile",choices=tuple(PROFILE_COUNTS),default=DEFAULT_PROFILE);parser.add_argument("--levels",default="7,11,15,20");parser.add_argument("--target-limit",type=int);parser.add_argument("--validate-only",action="store_true");parser.add_argument("--matrix-only",action="store_true");parser.add_argument("--no-matrix",action="store_true");parser.add_argument("--shadow-detail",action="store_true",help="write non-default primitive exposure detail without changing selection");args=parser.parse_args()
    model=AuthorityModel.load(args.authority)
    if args.validate_only:load_config();load_scoring_config();load_comparators();load_targets(profile=args.profile);print(f"Validated Kinetic Vanguard {model.rules_version} authority {model.authority_sha256}, target profile {args.profile}, isolated comparator config, and frozen Control Value config");return
    levels={int(value) for value in args.levels.split(",")}
    if args.target_limit is not None and args.target_limit<=0:parser.error("--target-limit must be positive")
    result=run(args.authority,args.output_dir,levels,args.target_limit,not args.matrix_only,not args.no_matrix,args.profile,args.shadow_detail)
    if args.shadow_detail:print(f"Control harness wrote {result['detail_rows']} Reliability detail rows, {result['audit_rows']} Reliability audit rows, {result['shadow_rows']} Control Value primitive rows, {result['value_scenario_rows']} Control Value scenario rows, {result['value_audit_rows']} Control Value audit rows, and {result['value_matrix_rows']} Control Value matrix rows for rules {result['rules_version']}")
    else:print(f"Control harness wrote {result['detail_rows']} detail rows, {result['audit_rows']} audit rows, and {result['matrix_rows']} matrix rows for rules {result['rules_version']}")


if __name__=="__main__":main()
