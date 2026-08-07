"""Frozen benchmark inputs and shared probability helpers."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = HARNESS_ROOT / "config" / "benchmark.json"
DEFAULT_COMPARATORS = HARNESS_ROOT / "comparators" / "fighter-subclasses.json"
DEFAULT_ROSTER = HARNESS_ROOT / "data" / "srd_targets.csv"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SIZE_ORDER = {"tiny":0,"small":1,"medium":2,"large":3,"huge":4,"gargantuan":5}


@dataclass(frozen=True)
class Target:
    level:int;name:str;ac:int;saves:dict[str,int];magic_resistance:bool;legendary_resistance:int;size:str;creature_type:str
    condition_immunities:frozenset[str];damage_resistances:frozenset[str];damage_immunities:frozenset[str];damage_vulnerabilities:frozenset[str]
    hp:int;source:str;source_page:str;source_url:str


def _object(value:Any,label:str)->dict[str,Any]:
    if not isinstance(value,dict):raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value:dict[str,Any],expected:set[str],label:str)->None:
    missing=sorted(expected-value.keys());unknown=sorted(value.keys()-expected)
    if missing or unknown:raise ValueError(f"{label} keys are invalid; missing={missing}, unknown={unknown}")


def _integer(value:Any,label:str,minimum:int|None=None)->int:
    if isinstance(value,bool) or not isinstance(value,int):raise ValueError(f"{label} must be an integer")
    if minimum is not None and value<minimum:raise ValueError(f"{label} must be at least {minimum}")
    return value


def _boolean(value:Any,label:str)->bool:
    if not isinstance(value,bool):raise ValueError(f"{label} must be a boolean")
    return value


def _level_map(value:Any,label:str,validator:Any=_integer)->dict[str,Any]:
    row=_object(value,label);_exact_keys(row,{"7","11","15","20"},label)
    for level,item in row.items():validator(item,f"{label}.{level}",0)
    return row


def load_config(path:Path=DEFAULT_CONFIG)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    data=_object(data,"benchmark config");_exact_keys(data,{"format_version","methodology","fighter_progression","fighter_mechanics","kv_profile","damage_matrix","control_matrix"},"benchmark config")
    if data["format_version"]!=1:raise ValueError("Unsupported benchmark config format version")
    methodology=_object(data["methodology"],"methodology");_exact_keys(methodology,{"status","historical_source","levels","rounds","cluster_sizes","target_weighting","target_death","ally_turns","legal_positioning_assumed","legendary_resistance","damage_default_trials","control_default_trials","smoke_trials","damage_seed","control_seed"},"methodology")
    if methodology["status"] not in {"PORTED_UNDER_REVIEW","REVIEWED_WITH_DOCUMENTED_DIFFERENCES"}:raise ValueError("Unsupported numerical review status")
    if methodology["levels"]!=[7,11,15,20] or methodology["cluster_sizes"]!=[1,3,6] or methodology["rounds"]!=3:raise ValueError("Benchmark levels, clusters, and three-round horizon are frozen")
    if methodology["target_weighting"]!="equal_weight_within_level" or methodology["legendary_resistance"]!="metadata_only":raise ValueError("Unsupported benchmark aggregation or Legendary Resistance policy")
    for key in ("target_death","ally_turns","legal_positioning_assumed"):_boolean(methodology[key],f"methodology.{key}")
    for key in ("damage_default_trials","control_default_trials","smoke_trials","damage_seed","control_seed"):_integer(methodology[key],f"methodology.{key}",1)
    progression=_object(data["fighter_progression"],"fighter_progression");_exact_keys(progression,{"7","11","15","20"},"fighter_progression")
    for level,row_value in progression.items():
        row=_object(row_value,f"fighter_progression.{level}");_exact_keys(row,{"attacks_per_action","action_slots_by_round","studied_attacks","combat_prowess"},f"fighter_progression.{level}")
        _integer(row["attacks_per_action"],f"fighter_progression.{level}.attacks_per_action",1)
        if not isinstance(row["action_slots_by_round"],list) or len(row["action_slots_by_round"])!=methodology["rounds"]:raise ValueError(f"fighter_progression.{level}.action_slots_by_round must cover every round")
        for index,count in enumerate(row["action_slots_by_round"]):_integer(count,f"fighter_progression.{level}.action_slots_by_round[{index}]",1)
        _boolean(row["studied_attacks"],f"fighter_progression.{level}.studied_attacks");_boolean(row["combat_prowess"],f"fighter_progression.{level}.combat_prowess")
    expected_progression={
        "7":{"attacks_per_action":2,"action_slots_by_round":[2,1,1],"studied_attacks":False,"combat_prowess":False},
        "11":{"attacks_per_action":3,"action_slots_by_round":[2,1,1],"studied_attacks":False,"combat_prowess":False},
        "15":{"attacks_per_action":3,"action_slots_by_round":[2,1,1],"studied_attacks":True,"combat_prowess":False},
        "20":{"attacks_per_action":4,"action_slots_by_round":[2,2,1],"studied_attacks":True,"combat_prowess":True},
    }
    if progression!=expected_progression:raise ValueError("Unsupported frozen Fighter progression")
    fighter_mechanics=_object(data["fighter_mechanics"],"fighter_mechanics");_exact_keys(fighter_mechanics,{"studied_attacks","combat_prowess"},"fighter_mechanics")
    studied=_object(fighter_mechanics["studied_attacks"],"fighter_mechanics.studied_attacks");_exact_keys(studied,{"trigger","benefit","expiry"},"fighter_mechanics.studied_attacks")
    expected_studied={"trigger":"resolved_miss_after_hit_instead_effects","benefit":"advantage_on_next_attack_against_same_target","expiry":"end_of_next_turn"}
    if studied!=expected_studied:raise ValueError("Unsupported Studied Attacks semantics")
    prowess=_object(fighter_mechanics["combat_prowess"],"fighter_mechanics.combat_prowess");_exact_keys(prowess,{"trigger","effect","uses_per_turn","reset","activation_policy","eligible_after_failed_attack_roll_bonus"},"fighter_mechanics.combat_prowess")
    _integer(prowess["uses_per_turn"],"fighter_mechanics.combat_prowess.uses_per_turn",1);_boolean(prowess["eligible_after_failed_attack_roll_bonus"],"fighter_mechanics.combat_prowess.eligible_after_failed_attack_roll_bonus")
    expected_prowess={"trigger":"attack_roll_miss","effect":"hit_instead","uses_per_turn":1,"reset":"start_of_next_turn","activation_policy":"optimal_after_observed_miss","eligible_after_failed_attack_roll_bonus":True}
    if prowess!=expected_prowess:raise ValueError("Unsupported Combat Prowess semantics")
    profile=_object(data["kv_profile"],"kv_profile");_exact_keys(profile,{"id","psionic_ability_modifier","constitution_modifier","hit_point_model","archery_attack_bonus","blood_tax_hp_fraction","advanced_training_policy","attack_replacement_policy"},"kv_profile")
    for key in ("psionic_ability_modifier","constitution_modifier","archery_attack_bonus"):_integer(profile[key],f"kv_profile.{key}")
    hit_points=_object(profile["hit_point_model"],"kv_profile.hit_point_model");_exact_keys(hit_points,{"first_level_base","later_level_average"},"kv_profile.hit_point_model");_integer(hit_points["first_level_base"],"kv_profile.hit_point_model.first_level_base",1);_integer(hit_points["later_level_average"],"kv_profile.hit_point_model.later_level_average",1)
    if not isinstance(profile["blood_tax_hp_fraction"],(int,float)) or isinstance(profile["blood_tax_hp_fraction"],bool) or not 0<=profile["blood_tax_hp_fraction"]<=1:raise ValueError("kv_profile.blood_tax_hp_fraction must be between zero and one")
    if profile["advanced_training_policy"]!="disabled":raise ValueError("Only the maintained disabled Advanced Training policy is supported")
    if profile["attack_replacement_policy"]!="all_manifested_strikes":raise ValueError("Only the maintained all-Manifested-Strike attack replacement policy is supported")
    damage=_object(data["damage_matrix"],"damage_matrix");_exact_keys(damage,{"control_feedback","optimization","excluded_stateful_features"},"damage_matrix")
    feedback=_object(damage["control_feedback"],"damage_matrix.control_feedback");_exact_keys(feedback,{"rider_conditions_and_save_outcomes","ally_turn_accuracy_and_damage","modeled_self_attack_exception"},"damage_matrix.control_feedback")
    expected_feedback={"rider_conditions_and_save_outcomes":"excluded_from_damage","ally_turn_accuracy_and_damage":"excluded","modeled_self_attack_exception":"thermal_fracture_ac_reduction"}
    if feedback!=expected_feedback:raise ValueError("Unsupported damage control-feedback policy")
    optimization=_object(damage["optimization"],"damage_matrix.optimization");_exact_keys(optimization,{"scope","objective","decision_timing"},"damage_matrix.optimization")
    if optimization["scope"]!="per_target_discipline_cluster":raise ValueError("Unsupported damage optimization scope")
    if optimization["objective"]!=["aggregate_damage","primary_damage"]:raise ValueError("Unsupported damage optimization objective")
    timing=_object(optimization["decision_timing"],"damage_matrix.optimization.decision_timing");_exact_keys(timing,{"pre_roll_declarations","unobserved_outcome_lookahead","post_roll_decisions"},"damage_matrix.optimization.decision_timing")
    _boolean(timing["unobserved_outcome_lookahead"],"damage_matrix.optimization.decision_timing.unobserved_outcome_lookahead")
    expected_timing={"pre_roll_declarations":"optimize_from_legally_observed_state","unobserved_outcome_lookahead":False,"post_roll_decisions":["combat_prowess"]}
    if timing!=expected_timing:raise ValueError("Unsupported damage optimization decision timing")
    exclusions=damage["excluded_stateful_features"]
    if not isinstance(exclusions,list) or not exclusions:raise ValueError("damage_matrix.excluded_stateful_features must be a non-empty list")
    for index,item_value in enumerate(exclusions):
        item=_object(item_value,f"damage exclusion {index}");_exact_keys(item,{"entity_id","reason"},f"damage exclusion {index}")
        if not all(isinstance(item[key],str) and item[key].strip() for key in ("entity_id","reason")):raise ValueError("Damage exclusions require non-empty entity_id and reason")
    control=_object(data["control_matrix"],"control_matrix");_exact_keys(control,{"metric","aggregation","kv_scenarios"},"control_matrix")
    scenarios=_object(control["kv_scenarios"],"control_matrix.kv_scenarios");_exact_keys(scenarios,{"pyrokinesis","cryokinesis","psychokinesis","electrokinesis"},"control_matrix.kv_scenarios")
    for discipline,entries in scenarios.items():
        if not isinstance(entries,list) or not entries:raise ValueError(f"{discipline} control scenarios must be non-empty")
        for index,entry_value in enumerate(entries):
            entry=_object(entry_value,f"{discipline} scenario {index}");allowed={"entity_id","tiers","target_roles"};required={"entity_id","tiers"}
            if not required<=entry.keys() or not entry.keys()<=allowed:raise ValueError(f"{discipline} scenario {index} keys are invalid")
            if not isinstance(entry["entity_id"],str) or not isinstance(entry["tiers"],list) or not entry["tiers"]:raise ValueError(f"{discipline} scenario {index} requires an entity and tiers")
            if any(isinstance(tier,bool) or not isinstance(tier,int) or tier not in {0,1,2} for tier in entry["tiers"]):raise ValueError(f"{discipline} scenario {index} has invalid tiers")
            roles=entry.get("target_roles",["primary"])
            if not isinstance(roles,list) or not roles or any(role not in {"primary","secondary"} for role in roles):raise ValueError(f"{discipline} scenario {index} has invalid target roles")
    return data


def _weapon(value:Any,label:str)->dict[str,Any]:
    row=_object(value,label);_exact_keys(row,{"count","sides","damage_type","great_weapon_fighting"},label);_integer(row["count"],f"{label}.count",1);_integer(row["sides"],f"{label}.sides",2);_boolean(row["great_weapon_fighting"],f"{label}.great_weapon_fighting")
    if not isinstance(row["damage_type"],str) or not row["damage_type"]:raise ValueError(f"{label}.damage_type must be non-empty")
    return row


def load_comparators(path:Path=DEFAULT_COMPARATORS)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    data=_object(data,"comparator config");_exact_keys(data,{"format_version","source_ruleset","primary_comparator_ids","damage","control"},"comparator config")
    expected=["battle_master","eldritch_knight"]
    if data["format_version"]!=1:raise ValueError("Unsupported comparator format version")
    if data["source_ruleset"]!="2024 fifth-edition rules":raise ValueError("Unsupported comparator source ruleset")
    if data["primary_comparator_ids"]!=expected:raise ValueError("Primary comparators must be Battle Master and Eldritch Knight")
    damage=_object(data["damage"],"damage comparators");control=_object(data["control"],"control comparators")
    if set(damage)!=set(expected):raise ValueError("Damage comparator set is incomplete or unsupported")
    if set(control)!=set(expected):raise ValueError("Control comparator set is incomplete or unsupported")
    bm=_object(damage["battle_master"],"damage.battle_master");_exact_keys(bm,{"ability_modifier","weapon","magic_weapon_bonus_by_level","great_weapon_master_attack_action_bonus","graze_damage","hew_critical_bonus_attack_once_per_round","superiority_die_by_level","superiority_pool_by_level","relentless_minimum_level","relentless_die","tactical_policy"},"damage.battle_master")
    for key in ("ability_modifier","graze_damage","relentless_minimum_level","relentless_die"):_integer(bm[key],f"damage.battle_master.{key}",0)
    _weapon(bm["weapon"],"damage.battle_master.weapon");_level_map(bm["magic_weapon_bonus_by_level"],"damage.battle_master.magic_weapon_bonus_by_level");_level_map(bm["superiority_die_by_level"],"damage.battle_master.superiority_die_by_level");_level_map(bm["superiority_pool_by_level"],"damage.battle_master.superiority_pool_by_level")
    if bm["great_weapon_master_attack_action_bonus"]!="proficiency_bonus":raise ValueError("Battle Master GWM bonus must be proficiency_bonus")
    _boolean(bm["hew_critical_bonus_attack_once_per_round"],"damage.battle_master.hew_critical_bonus_attack_once_per_round")
    bm_policy=_object(bm["tactical_policy"],"damage.battle_master.tactical_policy");_exact_keys(bm_policy,{"objective","maneuver_choice_timing","on_hit_die_effect","on_miss_die_effect","maneuver_die_consumption","maximum_maneuver_dice_per_attack","relentless_die_options","relentless_uses_per_turn","relentless_superiority_pool_cost","relentless_refresh","hew_choice_timing"},"damage.battle_master.tactical_policy")
    _integer(bm_policy["maximum_maneuver_dice_per_attack"],"damage.battle_master.tactical_policy.maximum_maneuver_dice_per_attack",1);_integer(bm_policy["relentless_uses_per_turn"],"damage.battle_master.tactical_policy.relentless_uses_per_turn",1);_integer(bm_policy["relentless_superiority_pool_cost"],"damage.battle_master.tactical_policy.relentless_superiority_pool_cost",0)
    expected_bm_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","maneuver_choice_timing":"after_observed_attack_roll_result","on_hit_die_effect":"damage","on_miss_die_effect":"attack_roll_bonus","maneuver_die_consumption":"on_use_before_die_result","maximum_maneuver_dice_per_attack":1,"relentless_die_options":"same_as_superiority_die","relentless_uses_per_turn":1,"relentless_superiority_pool_cost":0,"relentless_refresh":"start_of_next_turn","hew_choice_timing":"after_observed_critical"}
    if bm_policy!=expected_bm_policy:raise ValueError("Unsupported Battle Master tactical policy")
    ek=_object(damage["eldritch_knight"],"damage.eldritch_knight");_exact_keys(ek,{"regular_attack_ability_modifier","true_strike_ability_modifier_by_level","weapon","magic_weapon_bonus_by_level","dueling_damage_bonus","true_strike_damage_by_level","true_strike_uses_per_attack_action","true_strike_damage_type","tactical_policy"},"damage.eldritch_knight")
    _integer(ek["regular_attack_ability_modifier"],"damage.eldritch_knight.regular_attack_ability_modifier",0);_integer(ek["dueling_damage_bonus"],"damage.eldritch_knight.dueling_damage_bonus",0);_integer(ek["true_strike_uses_per_attack_action"],"damage.eldritch_knight.true_strike_uses_per_attack_action",0);_weapon(ek["weapon"],"damage.eldritch_knight.weapon");_level_map(ek["true_strike_ability_modifier_by_level"],"damage.eldritch_knight.true_strike_ability_modifier_by_level");_level_map(ek["magic_weapon_bonus_by_level"],"damage.eldritch_knight.magic_weapon_bonus_by_level")
    true_damage=_object(ek["true_strike_damage_by_level"],"damage.eldritch_knight.true_strike_damage_by_level");_exact_keys(true_damage,{"7","11","15","20"},"damage.eldritch_knight.true_strike_damage_by_level")
    for level,packet_value in true_damage.items():packet=_object(packet_value,f"true strike damage {level}");_exact_keys(packet,{"count","sides"},f"true strike damage {level}");_integer(packet["count"],f"true strike damage {level}.count",0);_integer(packet["sides"],f"true strike damage {level}.sides",2)
    if ek["true_strike_damage_type"]!="radiant":raise ValueError("Unsupported True Strike damage type")
    ek_policy=_object(ek["tactical_policy"],"damage.eldritch_knight.tactical_policy");_exact_keys(ek_policy,{"objective","true_strike_choice_timing","decision_information","true_strike_use_count"},"damage.eldritch_knight.tactical_policy")
    expected_ek_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","true_strike_choice_timing":"before_attack_roll","decision_information":"observed_state_only","true_strike_use_count":"exactly_configured_per_attack_action"}
    if ek_policy!=expected_ek_policy:raise ValueError("Unsupported Eldritch Knight tactical policy")
    for build_id,row_value in control.items():
        row=_object(row_value,f"control.{build_id}");common={"minimum_level","attack_ability_modifier","magic_weapon_bonus_by_level","save_dc_base","magic_resistance_applies","scenarios"};ability={"save_ability_modifier"} if build_id=="battle_master" else {"save_ability_modifier_by_level"};_exact_keys(row,common|ability,f"control.{build_id}")
        for key in ("minimum_level","attack_ability_modifier","save_dc_base"):_integer(row[key],f"control.{build_id}.{key}",0)
        _level_map(row["magic_weapon_bonus_by_level"],f"control.{build_id}.magic_weapon_bonus_by_level");_boolean(row["magic_resistance_applies"],f"control.{build_id}.magic_resistance_applies")
        if build_id=="battle_master":_integer(row["save_ability_modifier"],"control.battle_master.save_ability_modifier",0)
        else:_level_map(row["save_ability_modifier_by_level"],"control.eldritch_knight.save_ability_modifier_by_level")
        if not isinstance(row["scenarios"],list) or not row["scenarios"]:raise ValueError(f"control.{build_id}.scenarios must be non-empty")
        for index,scenario_value in enumerate(row["scenarios"]):
            scenario=_object(scenario_value,f"control.{build_id}.scenarios[{index}]");required={"id","save"};allowed=required|{"minimum_level","hit_gated","conditions","outcomes","maximum_size","primer_hit_disadvantage"}
            if not required<=scenario.keys() or not scenario.keys()<=allowed:raise ValueError(f"control.{build_id}.scenarios[{index}] keys are invalid")
            for key in ("hit_gated","primer_hit_disadvantage"):
                if key in scenario:_boolean(scenario[key],f"control.{build_id}.scenarios[{index}].{key}")
    return data


def _items(value:str)->frozenset[str]:
    return frozenset(item.strip().lower() for item in value.split(";") if item.strip())


def load_targets(path:Path=DEFAULT_ROSTER,levels:set[int]|None=None,limit:int|None=None)->list[Target]:
    rows:list[Target]=[]
    with path.open(newline="",encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            level=int(raw["Level"])
            if levels is not None and level not in levels:continue
            if raw["Source"]!="SRD 5.2.1" or not raw["Source Page"] or not raw["HP"] or not raw["Source URL"]:raise ValueError(f"Pinned roster row {raw.get('Target','?')} lacks required SRD provenance or HP")
            rows.append(Target(level,raw["Target"],int(raw["AC"]),{ability:int(raw[ability[:3].upper()]) for ability in ABILITIES},raw["Magic Resistance"].lower()=="true",int(raw["Legendary Resistance"]),raw["Size"].lower(),raw["Creature Type"].lower(),_items(raw["Condition Immunities"]),_items(raw["Damage Resistances"]),_items(raw["Damage Immunities"]),_items(raw["Damage Vulnerabilities"]),int(raw["HP"]),raw["Source"],raw["Source Page"],raw["Source URL"]))
    if limit is not None:rows=rows[:limit]
    if not rows:raise ValueError("Target selection is empty")
    return rows


def file_sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(65536),b""):digest.update(chunk)
    return digest.hexdigest()


def stable_seed(seed:int,*parts:object)->int:
    payload="|".join([str(seed),*(str(part) for part in parts)]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8],"big")


@lru_cache(maxsize=None)
def attack_probabilities(attack_bonus:int,ac:int,advantage:bool=False)->tuple[float,float,float]:
    outcomes=range(1,21);miss=hit=critical=0
    for first in outcomes:
        seconds=outcomes if advantage else (first,)
        for second in seconds:
            natural=max(first,second) if advantage else first
            if natural==20:critical+=1
            elif natural!=1 and natural+attack_bonus>=ac:hit+=1
            else:miss+=1
    total=400 if advantage else 20
    return miss/total,hit/total,critical/total


def save_success_probability(target:Target,ability:str,dc:int,disadvantage:bool=False,magic_resistance:bool=True)->float:
    advantage=target.magic_resistance and magic_resistance
    successes=total=0
    for first in range(1,21):
        for second in range(1,21):
            total+=1
            if advantage and disadvantage:natural=first
            elif advantage:natural=max(first,second)
            elif disadvantage:natural=min(first,second)
            else:natural=first
            successes+=natural+target.saves[ability]>=dc
    return successes/total


def damage_multiplier(target:Target,damage_type:str,ignore_resistance:bool=False)->float:
    damage_type=damage_type.lower()
    if damage_type in target.damage_immunities:return 0.0
    resistant=damage_type in target.damage_resistances and not ignore_resistance
    vulnerable=damage_type in target.damage_vulnerabilities
    if resistant and vulnerable:return 1.0
    if resistant:return 0.5
    if vulnerable:return 2.0
    return 1.0


def expected_damage(damage:dict[str,Any],strike_die:int,psi_modifier:int)->float:
    kind=damage["kind"]
    if kind=="none":return 0.0
    if kind=="fixed":return float(damage["value"])
    if kind=="dice":return float(damage["count"])*(float(damage["sides"])+1.0)/2.0
    if kind=="manifested_strike_dice":return float(damage["count"])*(strike_die+1.0)/2.0
    if kind=="psionic_ability_modifier":return psi_modifier*float(damage.get("multiplier",1))
    raise ValueError(f"Unsupported damage kind: {kind}")


def level_config(config:dict[str,Any],level:int)->dict[str,Any]:
    try:return config["fighter_progression"][str(level)]
    except KeyError as error:raise ValueError(f"Unsupported benchmark level {level}") from error


def target_is_eligible(target:Target,maximum_size:str|None=None,required_creature_type:str|None=None)->bool:
    if maximum_size is not None and SIZE_ORDER[target.size]>SIZE_ORDER[maximum_size]:return False
    if required_creature_type is not None and target.creature_type!=required_creature_type:return False
    return True
