"""Frozen benchmark inputs and shared probability helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = HARNESS_ROOT / "config" / "benchmark.json"
DEFAULT_COMPARATORS = HARNESS_ROOT / "comparators" / "fighter-subclasses.json"
DEFAULT_CATALOG = HARNESS_ROOT / "data" / "srd_creatures.json"
DEFAULT_ROSTERS = HARNESS_ROOT / "data" / "srd_creature_rosters.json"
DEFAULT_PROFILE = "headline"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SIZE_ORDER = {"tiny":0,"small":1,"medium":2,"large":3,"huge":4,"gargantuan":5}
MOVEMENT_MODES = ("walk","fly","swim","climb","burrow")
SENSE_KINDS = ("darkvision","blindsight","tremorsense","truesight")
SKILLS = frozenset({"acrobatics","animal_handling","arcana","athletics","deception","history","insight","intimidation","investigation","medicine","nature","perception","performance","persuasion","religion","sleight_of_hand","stealth","survival"})
PROFILE_COUNTS = {"headline":47,"eligible_census":93}
PROFILE_LEVEL_COUNTS = {"headline":{7:12,11:12,15:11,20:12},"eligible_census":{7:47,11:20,15:11,20:15}}


@dataclass(frozen=True)
class Target:
    level:int;name:str;ac:int;saves:dict[str,int];magic_resistance:bool;legendary_resistance:int;size:str;creature_type:str
    condition_immunities:frozenset[str];damage_resistances:frozenset[str];damage_immunities:frozenset[str];damage_vulnerabilities:frozenset[str]
    hp:int;source:str;source_page:str;source_url:str
    ability_modifiers:dict[str,int]=field(default_factory=dict);skill_bonuses:dict[str,int]=field(default_factory=dict)
    blindsight_range:int=0;truesight_range:int=0
    benchmark_locomotion_speed:int|None=None


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


def fighter_action_schedules(progression:dict[str,Any],rounds:int)->tuple[tuple[int,...],...]:
    """Enumerate schedules that spend every available Action Surge at most once per turn."""
    if rounds<=0:raise ValueError("Fighter action schedule horizon must be positive")
    uses=_integer(progression.get("action_surge_uses_over_horizon"),"fighter action_surge_uses_over_horizon",0)
    maximum=_integer(progression.get("maximum_action_surges_per_turn"),"fighter maximum_action_surges_per_turn",1)
    if maximum!=1:raise ValueError("Maintained Fighter schedules require maximum one Action Surge per turn")
    if uses>rounds:raise ValueError("Fighter Action Surge uses exceed the one-per-turn benchmark horizon")
    return tuple(tuple(2 if round_index in surge_rounds else 1 for round_index in range(rounds)) for surge_rounds in combinations(range(rounds),uses))


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
    methodology=_object(data["methodology"],"methodology");_exact_keys(methodology,{"levels","rounds","cluster_sizes","target_weighting","target_death","ally_turns","legal_positioning_assumed","legendary_resistance"},"methodology")
    if methodology["levels"]!=[7,11,15,20] or methodology["cluster_sizes"]!=[1,3,6] or methodology["rounds"]!=3:raise ValueError("Benchmark levels, clusters, and three-round horizon are frozen")
    if methodology["target_weighting"]!="equal_weight_within_level" or methodology["legendary_resistance"]!="metadata_only":raise ValueError("Unsupported benchmark aggregation or Legendary Resistance policy")
    for key in ("target_death","ally_turns","legal_positioning_assumed"):_boolean(methodology[key],f"methodology.{key}")
    progression=_object(data["fighter_progression"],"fighter_progression");_exact_keys(progression,{"7","11","15","20"},"fighter_progression")
    for level,row_value in progression.items():
        row=_object(row_value,f"fighter_progression.{level}");_exact_keys(row,{"attacks_per_action","action_surge_uses_over_horizon","maximum_action_surges_per_turn","studied_attacks","combat_prowess"},f"fighter_progression.{level}")
        _integer(row["attacks_per_action"],f"fighter_progression.{level}.attacks_per_action",1)
        _integer(row["action_surge_uses_over_horizon"],f"fighter_progression.{level}.action_surge_uses_over_horizon",0)
        _integer(row["maximum_action_surges_per_turn"],f"fighter_progression.{level}.maximum_action_surges_per_turn",1)
        _boolean(row["studied_attacks"],f"fighter_progression.{level}.studied_attacks");_boolean(row["combat_prowess"],f"fighter_progression.{level}.combat_prowess")
        fighter_action_schedules(row,int(methodology["rounds"]))
    expected_progression={
        "7":{"attacks_per_action":2,"action_surge_uses_over_horizon":1,"maximum_action_surges_per_turn":1,"studied_attacks":False,"combat_prowess":False},
        "11":{"attacks_per_action":3,"action_surge_uses_over_horizon":1,"maximum_action_surges_per_turn":1,"studied_attacks":False,"combat_prowess":False},
        "15":{"attacks_per_action":3,"action_surge_uses_over_horizon":1,"maximum_action_surges_per_turn":1,"studied_attacks":True,"combat_prowess":False},
        "20":{"attacks_per_action":4,"action_surge_uses_over_horizon":2,"maximum_action_surges_per_turn":1,"studied_attacks":True,"combat_prowess":True},
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
    timing=_object(optimization["decision_timing"],"damage_matrix.optimization.decision_timing");_exact_keys(timing,{"action_surge_schedule","pre_roll_declarations","unobserved_outcome_lookahead","post_roll_decisions"},"damage_matrix.optimization.decision_timing")
    _boolean(timing["unobserved_outcome_lookahead"],"damage_matrix.optimization.decision_timing.unobserved_outcome_lookahead")
    expected_timing={"action_surge_schedule":"optimize_before_outcome_resolution","pre_roll_declarations":"optimize_from_legally_observed_state","unobserved_outcome_lookahead":False,"post_roll_decisions":["combat_prowess"]}
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


_BATTLE_MASTER_DAMAGE_LOADOUTS={
    "7":("feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack"),
    "11":("feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack","lunging_attack","riposte"),
    "15":("feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack","lunging_attack","riposte","goading_attack","menacing_attack"),
    "20":("feinting_attack","precision_attack","pushing_attack","sweeping_attack","trip_attack","lunging_attack","riposte","goading_attack","menacing_attack"),
}
_BATTLE_MASTER_CONTROL_LOADOUTS={
    "7":("disarming_attack","goading_attack","menacing_attack","pushing_attack","trip_attack"),
    "11":("disarming_attack","goading_attack","menacing_attack","pushing_attack","trip_attack","distracting_strike","precision_attack"),
    "15":("disarming_attack","goading_attack","menacing_attack","pushing_attack","trip_attack","distracting_strike","precision_attack","ambush","maneuvering_attack"),
    "20":("disarming_attack","goading_attack","menacing_attack","pushing_attack","trip_attack","distracting_strike","precision_attack","ambush","maneuvering_attack"),
}
_ELDRITCH_KNIGHT_DAMAGE_CANTRIPS={
    "7":("true_strike","acid_splash"),
    "11":("true_strike","acid_splash","poison_spray"),
    "15":("true_strike","acid_splash","poison_spray"),
    "20":("true_strike","acid_splash","poison_spray"),
}
_ELDRITCH_KNIGHT_DAMAGE_PREPARED={
    "7":("chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt"),
    "11":("chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt","scorching_ray","melfs_acid_arrow","enlarge_reduce"),
    "15":("chromatic_orb","dragons_breath","magic_missile","shatter","witch_bolt","scorching_ray","enlarge_reduce","fireball","lightning_bolt","bestow_curse"),
    "20":("chromatic_orb","magic_missile","witch_bolt","scorching_ray","shatter","enlarge_reduce","melfs_acid_arrow","fireball","bestow_curse","conjure_minor_elementals","greater_invisibility","phantasmal_killer","vitriolic_sphere"),
}
_ELDRITCH_KNIGHT_DAMAGE_SLOTS={
    "7":{"1":4,"2":2,"3":0,"4":0},
    "11":{"1":4,"2":3,"3":0,"4":0},
    "15":{"1":4,"2":3,"3":2,"4":0},
    "20":{"1":4,"2":3,"3":3,"4":1},
}


def _dice(value:Any,label:str,*,flat:bool=False)->dict[str,Any]:
    row=_object(value,label);keys={"count","sides","flat"} if flat else {"count","sides"};_exact_keys(row,keys,label)
    _integer(row["count"],f"{label}.count",1);_integer(row["sides"],f"{label}.sides",2)
    if flat:_integer(row["flat"],f"{label}.flat")
    return row


def _string_list(value:Any,label:str,*,allowed:set[str]|None=None)->list[str]:
    if not isinstance(value,list) or not value or any(not isinstance(item,str) or not item for item in value) or len(value)!=len(set(value)):raise ValueError(f"{label} must be a unique non-empty string list")
    if allowed is not None and not set(value)<=allowed:raise ValueError(f"{label} contains unsupported values")
    return value


def _validate_eldritch_knight_damage(ek:dict[str,Any])->None:
    expected_keys={"regular_attack_ability_modifier","spellcasting_ability_modifier_by_level","save_dc_base","weapon","magic_weapon_bonus_by_level","dueling_damage_bonus","eldritch_strike_minimum_level","cantrips_by_level","prepared_spells_by_level","spell_slots_by_level","war_magic","improved_war_magic","spells","tactical_policy"}
    _exact_keys(ek,expected_keys,"damage.eldritch_knight")
    for key in ("regular_attack_ability_modifier","save_dc_base","dueling_damage_bonus"):_integer(ek[key],f"damage.eldritch_knight.{key}",0)
    _integer(ek["eldritch_strike_minimum_level"],"damage.eldritch_knight.eldritch_strike_minimum_level",1)
    _weapon(ek["weapon"],"damage.eldritch_knight.weapon");_level_map(ek["spellcasting_ability_modifier_by_level"],"damage.eldritch_knight.spellcasting_ability_modifier_by_level");_level_map(ek["magic_weapon_bonus_by_level"],"damage.eldritch_knight.magic_weapon_bonus_by_level")
    for field,expected in (("cantrips_by_level",_ELDRITCH_KNIGHT_DAMAGE_CANTRIPS),("prepared_spells_by_level",_ELDRITCH_KNIGHT_DAMAGE_PREPARED)):
        rows=_object(ek[field],f"damage.eldritch_knight.{field}");_exact_keys(rows,set(expected),f"damage.eldritch_knight.{field}")
        for level,members in rows.items():
            _string_list(members,f"damage.eldritch_knight.{field}.{level}")
            if tuple(members)!=expected[level]:raise ValueError(f"damage.eldritch_knight.{field}.{level} does not match the audited fixed loadout")
    slots=_object(ek["spell_slots_by_level"],"damage.eldritch_knight.spell_slots_by_level");_exact_keys(slots,set(_ELDRITCH_KNIGHT_DAMAGE_SLOTS),"damage.eldritch_knight.spell_slots_by_level")
    for level,expected in _ELDRITCH_KNIGHT_DAMAGE_SLOTS.items():
        pool=_object(slots[level],f"damage.eldritch_knight.spell_slots_by_level.{level}");_exact_keys(pool,set(expected),f"damage.eldritch_knight.spell_slots_by_level.{level}")
        for slot,count in pool.items():_integer(count,f"damage.eldritch_knight.spell_slots_by_level.{level}.{slot}",0)
        if pool!=expected:raise ValueError(f"damage.eldritch_knight.spell_slots_by_level.{level} does not match the audited slot pool")
    war=_object(ek["war_magic"],"damage.eldritch_knight.war_magic");_exact_keys(war,{"minimum_level","attack_replacement_cost"},"damage.eldritch_knight.war_magic")
    improved=_object(ek["improved_war_magic"],"damage.eldritch_knight.improved_war_magic");_exact_keys(improved,{"minimum_level","eligible_spell_levels","attack_replacement_cost"},"damage.eldritch_knight.improved_war_magic")
    if war!={"minimum_level":7,"attack_replacement_cost":1} or improved!={"minimum_level":18,"eligible_spell_levels":[1,2],"attack_replacement_cost":2}:raise ValueError("Unsupported Eldritch Knight War Magic action economy")
    common={"id","spell_level","audit_comment_id","source_scope","disposition","action_type","concentration","mechanic"}
    mechanic_fields={
        "true_strike":{"damage_types","weapon_damage_type_choice","damage_dice_by_level"},
        "save_area":{"save","save_result","targeting","damage_types"},
        "spell_attack":{"targeting","critical_dice","damage_types","damage_dice_by_level"},
        "chromatic_orb":{"targeting","critical_dice","damage_types","base_damage","slot_damage_dice","maximum_leaps"},
        "dragons_breath":{"targeting","save","save_result","damage_types","damage_type_choice","base_damage","slot_damage_dice","activation_action"},
        "magic_missile":{"targeting","damage_types","base_darts","slot_darts","dart_damage","automatic_hit"},
        "witch_bolt":{"targeting","critical_dice","damage_types","base_damage","slot_damage_dice","repeat_damage","repeat_action","repeat_timing","persists_on_initial_miss"},
        "multiple_spell_attacks":{"targeting","critical_dice","damage_types","base_attacks","slot_attacks","attack_damage"},
        "melfs_acid_arrow":{"targeting","critical_dice","damage_types","initial_damage","delayed_damage","slot_damage_dice_each_event","miss_result"},
        "self_enlarge":{"targeting","weapon_hit_bonus"},
        "bestow_curse_damage":{"targeting","save","save_result","damage_types","damage_event_bonus","mode"},
        "conjure_minor_elementals":{"targeting","damage_types","damage_type_choice","weapon_hit_bonus"},
        "greater_invisibility":{"targeting","melee_distance_feet","suppressed_by_senses"},
        "phantasmal_killer":{"targeting","save","initial_success","repeat_success","damage_types","damage","repeat_timing"},
        "vitriolic_sphere":{"targeting","save","initial_success","damage_types","initial_damage","delayed_damage","delayed_timing"},
    }
    expected_mechanics={
        "true_strike":"true_strike","acid_splash":"save_area","poison_spray":"spell_attack","chromatic_orb":"chromatic_orb","dragons_breath":"dragons_breath","magic_missile":"magic_missile","shatter":"save_area","witch_bolt":"witch_bolt","scorching_ray":"multiple_spell_attacks","melfs_acid_arrow":"melfs_acid_arrow","enlarge_reduce":"self_enlarge","fireball":"save_area","lightning_bolt":"save_area","bestow_curse":"bestow_curse_damage","conjure_minor_elementals":"conjure_minor_elementals","greater_invisibility":"greater_invisibility","phantasmal_killer":"phantasmal_killer","vitriolic_sphere":"vitriolic_sphere",
    }
    expected_levels={"true_strike":0,"acid_splash":0,"poison_spray":0,"chromatic_orb":1,"dragons_breath":2,"magic_missile":1,"shatter":2,"witch_bolt":1,"scorching_ray":2,"melfs_acid_arrow":2,"enlarge_reduce":2,"fireball":3,"lightning_bolt":3,"bestow_curse":3,"conjure_minor_elementals":4,"greater_invisibility":4,"phantasmal_killer":4,"vitriolic_sphere":4}
    concentration_spells={"dragons_breath","witch_bolt","enlarge_reduce","bestow_curse","conjure_minor_elementals","greater_invisibility","phantasmal_killer"}
    spells=ek["spells"]
    if not isinstance(spells,list) or not spells:raise ValueError("damage.eldritch_knight.spells must be non-empty")
    ids=[]
    for index,value in enumerate(spells):
        label=f"damage.eldritch_knight.spells[{index}]";spell=_object(value,label);mechanic=spell.get("mechanic")
        if mechanic not in mechanic_fields:raise ValueError(f"{label}.mechanic is unsupported")
        required=common|mechanic_fields[mechanic]
        if mechanic=="save_area":
            required|={"damage_dice_by_level"} if int(spell.get("spell_level",0))==0 else {"base_damage","slot_damage_dice"}
            if spell.get("id")=="shatter":required|={"save_disadvantage_creature_type"}
        _exact_keys(spell,required,label);spell_id=_string(spell["id"],f"{label}.id");ids.append(spell_id)
        if expected_mechanics.get(spell_id)!=mechanic:raise ValueError(f"{label} does not match the audited spell mechanic")
        _integer(spell["spell_level"],f"{label}.spell_level",0);_integer(spell["audit_comment_id"],f"{label}.audit_comment_id",1);_boolean(spell["concentration"],f"{label}.concentration")
        if spell["spell_level"]!=expected_levels[spell_id] or spell["action_type"]!=("bonus_action" if spell_id=="dragons_breath" else "action") or spell["concentration"]!=(spell_id in concentration_spells):raise ValueError(f"{label} has unsupported level, action, or concentration semantics")
        if spell["source_scope"]!="independently_expressed_phb_comparator_abstraction" or spell["disposition"]!="model":raise ValueError(f"{label} source scope or disposition is invalid")
        if spell["action_type"] not in {"action","bonus_action"}:raise ValueError(f"{label}.action_type is unsupported")
        if "damage_types" in spell:_string_list(spell["damage_types"],f"{label}.damage_types",allowed={"acid","cold","fire","force","lightning","necrotic","poison","psychic","radiant","slashing","thunder"})
        if "save" in spell and spell["save"] not in ABILITIES:raise ValueError(f"{label}.save is unsupported")
        for key in ("base_damage","repeat_damage","attack_damage","initial_damage","delayed_damage","weapon_hit_bonus","damage_event_bonus","damage"):
            if key in spell:_dice(spell[key],f"{label}.{key}")
        if "dart_damage" in spell:_dice(spell["dart_damage"],f"{label}.dart_damage",flat=True)
        if "damage_dice_by_level" in spell:
            packets=_object(spell["damage_dice_by_level"],f"{label}.damage_dice_by_level");expected_packet_levels={"11","15","20"} if spell_id=="poison_spray" else {"7","11","15","20"};_exact_keys(packets,expected_packet_levels,f"{label}.damage_dice_by_level")
            for level,packet in packets.items():_dice(packet,f"{label}.damage_dice_by_level.{level}")
        for key in ("slot_damage_dice","base_darts","slot_darts","base_attacks","slot_attacks","slot_damage_dice_each_event","melee_distance_feet"):
            if key in spell:_integer(spell[key],f"{label}.{key}",0)
        for key in ("critical_dice","automatic_hit","persists_on_initial_miss","weapon_damage_type_choice"):
            if key in spell:_boolean(spell[key],f"{label}.{key}")
        for key in ("critical_dice","automatic_hit","persists_on_initial_miss"):
            if key in spell and spell[key] is not True:raise ValueError(f"{label}.{key} must preserve the frozen mechanic")
        frozen_strings={
            "maximum_leaps":"slot_level","damage_type_choice":"once_at_cast_time","activation_action":"magic","repeat_action":"bonus_action","repeat_timing":("target_end_turn" if spell_id=="phantasmal_killer" else "later_turns"),"miss_result":"half_initial_only","mode":"caster_damage_events","initial_success":("half_and_ends" if spell_id=="phantasmal_killer" else "half_initial_only"),"repeat_success":"ends","delayed_timing":"target_end_next_turn","save_disadvantage_creature_type":"construct",
        }
        for key,expected in frozen_strings.items():
            if key in spell and spell[key]!=expected:raise ValueError(f"{label}.{key} is unsupported")
        expected_targeting={"true_strike":None,"acid_splash":"cluster","poison_spray":"primary","chromatic_orb":"distinct_cluster_targets","dragons_breath":"cluster","magic_missile":"selectable_darts","shatter":"cluster","witch_bolt":"fixed_primary","scorching_ray":"primary","melfs_acid_arrow":"primary","enlarge_reduce":"self","fireball":"cluster","lightning_bolt":"cluster","bestow_curse":"primary","conjure_minor_elementals":"self_emanation_melee_hits","greater_invisibility":"self","phantasmal_killer":"primary","vitriolic_sphere":"cluster"}
        if "targeting" in spell and spell["targeting"]!=expected_targeting[spell_id]:raise ValueError(f"{label}.targeting is unsupported")
        if spell_id=="greater_invisibility" and spell["suppressed_by_senses"]!=["blindsight","truesight"]:raise ValueError("Greater Invisibility sense suppression is not exact")
        if spell_id=="greater_invisibility" and spell["melee_distance_feet"]!=5:raise ValueError("Greater Invisibility melee sense distance is not exact")
        expected_save_result={"acid_splash":"zero","dragons_breath":"half","shatter":"half","fireball":"half","lightning_bolt":"half","bestow_curse":"ends"}
        if "save_result" in spell and spell["save_result"]!=expected_save_result[spell_id]:raise ValueError(f"{label}.save_result is unsupported")
        if spell_id=="dragons_breath" and (spell["damage_types"]!=["acid","cold","fire","lightning","poison"] or spell["damage_type_choice"]!="once_at_cast_time" or spell["audit_comment_id"]!=5349868410):raise ValueError("Dragon's Breath damage-type ruling is not exact")
        elif spell_id!="dragons_breath" and spell["audit_comment_id"]!=5322823489:raise ValueError(f"{label}.audit_comment_id is not the frozen disposition record")
    expected_ids=set(expected_mechanics)
    if len(ids)!=len(set(ids)) or set(ids)!=expected_ids:raise ValueError("damage.eldritch_knight.spells does not match the complete frozen nominal spell package")
    if ek["weapon"]["great_weapon_fighting"] is not False:raise ValueError("Eldritch Knight weapon must not use Great Weapon Fighting")
    spell_by_id={spell["id"]:spell for spell in spells}
    for level,members in _ELDRITCH_KNIGHT_DAMAGE_CANTRIPS.items():
        if any(spell_by_id[spell_id]["spell_level"]!=0 for spell_id in members):raise ValueError(f"damage.eldritch_knight.cantrips_by_level.{level} contains a leveled spell")
    for level,members in _ELDRITCH_KNIGHT_DAMAGE_PREPARED.items():
        if any(not 1<=spell_by_id[spell_id]["spell_level"]<=max(int(slot) for slot,count in slots[level].items() if count) for spell_id in members):raise ValueError(f"damage.eldritch_knight.prepared_spells_by_level.{level} is not slot-legal")
    policy=_object(ek["tactical_policy"],"damage.eldritch_knight.tactical_policy");expected_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","decision_information":"observed_state_only","preparation_choice":"fixed_before_target_and_cluster","spell_choice_timing":"before_resolution","bonus_action_ledger":"one_shared_per_turn","concentration_ledger":"one_active_spell"};_exact_keys(policy,set(expected_policy),"damage.eldritch_knight.tactical_policy")
    if policy!=expected_policy:raise ValueError("Unsupported Eldritch Knight tactical policy")


def _battle_master_loadouts(value:Any,label:str,expected:dict[str,tuple[str,...]])->dict[str,Any]:
    rows=_object(value,label);_exact_keys(rows,{"7","11","15","20"},label)
    for level,required in expected.items():
        maneuvers=rows[level]
        if not isinstance(maneuvers,list) or any(not isinstance(item,str) or not item for item in maneuvers):raise ValueError(f"{label}.{level} must be a maneuver string list")
        if len(maneuvers)!=len(set(maneuvers)):raise ValueError(f"{label}.{level} must be duplicate-free")
        if tuple(maneuvers)!=required:raise ValueError(f"{label}.{level} does not match the audited fixed loadout")
    return rows


def _validate_battle_master_effects(scenario:dict[str,Any],label:str)->None:
    effects=scenario["effects"]
    if not isinstance(effects,list) or not effects:raise ValueError(f"{label}.effects must be non-empty")
    ids=[]
    for index,value in enumerate(effects):
        effect_label=f"{label}.effects[{index}]";effect=_object(value,effect_label);required={"id","gate","duration"};allowed=required|{"conditions","outcomes","magnitude_feet","pricing_status","qualifiers","recovery"}
        if not required<=effect.keys() or not effect.keys()<=allowed:raise ValueError(f"{effect_label} keys are invalid")
        ids.append(_string(effect["id"],f"{effect_label}.id"));_string(effect["duration"],f"{effect_label}.duration")
        if effect["gate"]!="on_failed_save":raise ValueError(f"{effect_label}.gate is invalid")
        for key in ("conditions","outcomes"):
            if key in effect and (not isinstance(effect[key],list) or not effect[key] or any(not isinstance(item,str) or not item for item in effect[key])):raise ValueError(f"{effect_label}.{key} must be a non-empty string list")
        if not effect.get("conditions") and not effect.get("outcomes"):raise ValueError(f"{effect_label} must declare a condition or outcome")
        if "magnitude_feet" in effect:_integer(effect["magnitude_feet"],f"{effect_label}.magnitude_feet",0)
        if effect.get("pricing_status") not in {None,"candidate","context_required","unsupported"}:raise ValueError(f"{effect_label}.pricing_status is invalid")
        if "qualifiers" in effect:
            qualifiers=_object(effect["qualifiers"],f"{effect_label}.qualifiers")
            if any(not isinstance(key,str) or not key or not isinstance(item,(str,int,float,bool)) for key,item in qualifiers.items()):raise ValueError(f"{effect_label}.qualifiers is invalid")
        if "recovery" in effect:
            recovery=_object(effect["recovery"],f"{effect_label}.recovery");_exact_keys(recovery,{"timing","method","movement_cost"},f"{effect_label}.recovery")
            if recovery!={"timing":"target_turn","method":"stand","movement_cost":"half_speed"}:raise ValueError(f"{effect_label}.recovery is invalid")
            if effect["duration"]!="until_target_stands" or "prone" not in effect.get("conditions",[]):raise ValueError(f"{effect_label}.recovery requires recoverable Prone")
    if len(ids)!=len(set(ids)):raise ValueError(f"{label} effect IDs must be unique")


def load_comparators(path:Path=DEFAULT_COMPARATORS)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    data=_object(data,"comparator config");_exact_keys(data,{"format_version","source_ruleset","primary_comparator_ids","damage","control"},"comparator config")
    expected={"battle_master","eldritch_knight"}
    if data["format_version"]!=1:raise ValueError("Unsupported comparator format version")
    if data["source_ruleset"]!="2024 fifth-edition rules":raise ValueError("Unsupported comparator source ruleset")
    primary=data["primary_comparator_ids"]
    if not isinstance(primary,list) or len(primary)!=len(expected) or any(not isinstance(item,str) for item in primary) or set(primary)!=expected:raise ValueError("Primary comparators must be Battle Master and Eldritch Knight")
    damage=_object(data["damage"],"damage comparators");control=_object(data["control"],"control comparators")
    if set(damage)!=expected:raise ValueError("Damage comparator set is incomplete or unsupported")
    if set(control)!=expected:raise ValueError("Control comparator set is incomplete or unsupported")
    bm=_object(damage["battle_master"],"damage.battle_master");_exact_keys(bm,{"ability_modifier","weapon","magic_weapon_bonus_by_level","great_weapon_master_attack_action_bonus","graze_damage","hew_critical_bonus_attack_once_per_round","superiority_die_by_level","superiority_pool_by_level","known_maneuvers_by_level","relentless_minimum_level","relentless_die","tactical_policy"},"damage.battle_master")
    for key in ("ability_modifier","graze_damage","relentless_minimum_level","relentless_die"):_integer(bm[key],f"damage.battle_master.{key}",0)
    _weapon(bm["weapon"],"damage.battle_master.weapon");_level_map(bm["magic_weapon_bonus_by_level"],"damage.battle_master.magic_weapon_bonus_by_level");_level_map(bm["superiority_die_by_level"],"damage.battle_master.superiority_die_by_level");_level_map(bm["superiority_pool_by_level"],"damage.battle_master.superiority_pool_by_level");_battle_master_loadouts(bm["known_maneuvers_by_level"],"damage.battle_master.known_maneuvers_by_level",_BATTLE_MASTER_DAMAGE_LOADOUTS)
    if bm["great_weapon_master_attack_action_bonus"]!="proficiency_bonus":raise ValueError("Battle Master GWM bonus must be proficiency_bonus")
    _boolean(bm["hew_critical_bonus_attack_once_per_round"],"damage.battle_master.hew_critical_bonus_attack_once_per_round")
    bm_policy=_object(bm["tactical_policy"],"damage.battle_master.tactical_policy");_exact_keys(bm_policy,{"objective","maneuver_choice_timing","decision_information","on_hit_die_effect","on_miss_die_effect","maneuver_die_consumption","maximum_maneuver_dice_per_attack","feint_choice_timing","feint_resource_timing","feint_effect","bonus_action_ledger","relentless_die_options","relentless_uses_per_turn","relentless_superiority_pool_cost","relentless_refresh","hew_choice_timing"},"damage.battle_master.tactical_policy")
    _integer(bm_policy["maximum_maneuver_dice_per_attack"],"damage.battle_master.tactical_policy.maximum_maneuver_dice_per_attack",1);_integer(bm_policy["relentless_uses_per_turn"],"damage.battle_master.tactical_policy.relentless_uses_per_turn",1);_integer(bm_policy["relentless_superiority_pool_cost"],"damage.battle_master.tactical_policy.relentless_superiority_pool_cost",0)
    expected_bm_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","maneuver_choice_timing":"pre_roll_feint_or_post_roll_observed_result","decision_information":"observed_state_only","on_hit_die_effect":"damage","on_miss_die_effect":"attack_roll_bonus","maneuver_die_consumption":"on_use_before_die_result","maximum_maneuver_dice_per_attack":1,"feint_choice_timing":"before_attack_roll","feint_resource_timing":"before_attack_roll","feint_effect":"advantage_next_attack_same_target_same_turn_and_die_damage_on_hit","bonus_action_ledger":"one_per_turn_shared_by_feint_and_hew","relentless_die_options":"same_as_superiority_die","relentless_uses_per_turn":1,"relentless_superiority_pool_cost":0,"relentless_refresh":"start_of_next_turn","hew_choice_timing":"after_observed_critical"}
    if bm_policy!=expected_bm_policy:raise ValueError("Unsupported Battle Master tactical policy")
    ek=_object(damage["eldritch_knight"],"damage.eldritch_knight");_validate_eldritch_knight_damage(ek)
    for build_id,row_value in control.items():
        row=_object(row_value,f"control.{build_id}");common={"minimum_level","attack_ability_modifier","magic_weapon_bonus_by_level","save_dc_base","magic_resistance_applies","scenarios"};ability={"save_ability_modifier","known_maneuvers_by_level"} if build_id=="battle_master" else {"spellcasting_ability_modifier_by_level","spell_access","eldritch_strike_minimum_level","reliability_scenario_ids"};_exact_keys(row,common|ability,f"control.{build_id}")
        for key in ("minimum_level","attack_ability_modifier","save_dc_base"):_integer(row[key],f"control.{build_id}.{key}",0)
        _level_map(row["magic_weapon_bonus_by_level"],f"control.{build_id}.magic_weapon_bonus_by_level");_boolean(row["magic_resistance_applies"],f"control.{build_id}.magic_resistance_applies")
        if build_id=="battle_master":
            _integer(row["save_ability_modifier"],"control.battle_master.save_ability_modifier",0);_battle_master_loadouts(row["known_maneuvers_by_level"],"control.battle_master.known_maneuvers_by_level",_BATTLE_MASTER_CONTROL_LOADOUTS)
        else:
            _level_map(row["spellcasting_ability_modifier_by_level"],"control.eldritch_knight.spellcasting_ability_modifier_by_level");_integer(row["eldritch_strike_minimum_level"],"control.eldritch_knight.eldritch_strike_minimum_level",1)
            access=_object(row["spell_access"],"control.eldritch_knight.spell_access");_exact_keys(access,{"highest_slot_level_by_fighter_level"},"control.eldritch_knight.spell_access");slots=_level_map(access["highest_slot_level_by_fighter_level"],"control.eldritch_knight.spell_access.highest_slot_level_by_fighter_level")
            if any(int(value)<1 for value in slots.values()) or list(slots.values())!=sorted(slots.values()):raise ValueError("Eldritch Knight spell access must be positive and nondecreasing")
        if not isinstance(row["scenarios"],list) or not row["scenarios"]:raise ValueError(f"control.{build_id}.scenarios must be non-empty")
        for index,scenario_value in enumerate(row["scenarios"]):
            scenario=_object(scenario_value,f"control.{build_id}.scenarios[{index}]");required={"id","audit_comment_id","source_scope","disposition","save","hit_gated","effects"} if build_id=="battle_master" else {"id","spell_id","audit_comment_id","source_scope","disposition","spell_level","delivery","effects"};allowed=required|({"maximum_size","context_predicates"} if build_id=="battle_master" else {"save","hit_gated","spell_attack","automatic_effect","initial_save_advantage","primer_hit_disadvantage","required_creature_type","maximum_size","improved_war_magic_eligible","automatic_success_if","targeting","breaks","escapes","context_predicates","area_exit_policy","turn_branches"})
            if not required<=scenario.keys() or not scenario.keys()<=allowed:raise ValueError(f"control.{build_id}.scenarios[{index}] keys are invalid")
            if build_id=="eldritch_knight" and sum(("save" in scenario,bool(scenario.get("spell_attack")),bool(scenario.get("automatic_effect"))))!=1:raise ValueError(f"control.{build_id}.scenarios[{index}] must use exactly one resolution gate")
            for key in ("hit_gated","spell_attack","automatic_effect","initial_save_advantage","primer_hit_disadvantage","improved_war_magic_eligible"):
                if key in scenario:_boolean(scenario[key],f"control.{build_id}.scenarios[{index}].{key}")
            for key in ("id","spell_id","source_scope","disposition","save","delivery","required_creature_type","maximum_size","area_exit_policy"):
                if key in scenario:_string(scenario[key],f"control.{build_id}.scenarios[{index}].{key}")
            for key in ("spell_level","audit_comment_id"):
                if key in scenario:_integer(scenario[key],f"control.{build_id}.scenarios[{index}].{key}",0)
            if scenario.get("delivery") not in {None,"war_magic_cantrip","action_spell","reaction_spell"}:raise ValueError(f"control.{build_id}.scenarios[{index}] has unsupported delivery")
            if scenario["source_scope"]!="independently_expressed_phb_comparator_abstraction":raise ValueError(f"control.{build_id}.scenarios[{index}] source scope is invalid")
            if scenario["disposition"] not in {"modeled","modeled_mixed","diagnostic_unpriced"}:raise ValueError(f"control.{build_id}.scenarios[{index}] disposition is invalid")
            if build_id=="battle_master":
                if scenario["hit_gated"] is not True:raise ValueError(f"control.{build_id}.scenarios[{index}] must be hit gated")
                _validate_battle_master_effects(scenario,f"control.{build_id}.scenarios[{index}]")
                predicates=scenario.get("context_predicates",[])
                if not isinstance(predicates,list) or len(predicates)!=len(set(predicates)) or any(not isinstance(item,str) or not item for item in predicates):raise ValueError(f"control.{build_id}.scenarios[{index}].context_predicates is invalid")
            for key in ("conditions","outcomes"):
                if key in scenario and (not isinstance(scenario[key],list) or not scenario[key] or any(not isinstance(item,str) or not item for item in scenario[key])):raise ValueError(f"control.{build_id}.scenarios[{index}].{key} must be a non-empty string list")
            if build_id=="eldritch_knight":
                if int(scenario["spell_level"])>max(int(value) for value in slots.values()):raise ValueError(f"control.{build_id}.scenarios[{index}] exceeds maintained spell access")
                if int(scenario["spell_level"])==0 and scenario["delivery"]!="war_magic_cantrip":raise ValueError(f"control.{build_id}.scenarios[{index}] cantrip delivery is invalid")
                if 0<int(scenario["spell_level"])<=2 and scenario["delivery"]=="action_spell" and scenario.get("improved_war_magic_eligible") is not True:raise ValueError(f"control.{build_id}.scenarios[{index}] Improved War Magic eligibility is invalid")
                if int(scenario["spell_level"])>=3 and scenario.get("improved_war_magic_eligible") is not False:raise ValueError(f"control.{build_id}.scenarios[{index}] Improved War Magic eligibility is invalid")
                effects=scenario["effects"]
                if not isinstance(effects,list) or not effects:raise ValueError(f"control.{build_id}.scenarios[{index}].effects must be non-empty")
                effect_ids=[]
                for effect_index,effect_value in enumerate(effects):
                    effect_label=f"control.{build_id}.scenarios[{index}].effects[{effect_index}]";effect=_object(effect_value,effect_label);effect_required={"id","gate","duration"};effect_allowed=effect_required|{"conditions","outcomes","repeat_save_trigger","requires_condition_effective","magnitude_feet","magnitude","attack_scope","active_pattern","transition_checkpoint","disjoint_stage_group","suppressed_recovery_options","pricing_status","unpriced","qualifiers","branch_fraction","branch_ids","secondary_save","area_trigger","context_predicates"}
                    if not effect_required<=effect.keys() or not effect.keys()<=effect_allowed:raise ValueError(f"{effect_label} keys are invalid")
                    effect_ids.append(_string(effect["id"],f"{effect_label}.id"));_string(effect["duration"],f"{effect_label}.duration")
                    if effect["gate"] not in {"automatic","on_hit","on_failed_save","on_successful_save","after_failed_second_save"}:raise ValueError(f"{effect_label}.gate is invalid")
                    if effect["gate"]=="automatic" and not scenario.get("automatic_effect") and "save" not in scenario:raise ValueError(f"{effect_label} automatic gate lacks an automatic scenario")
                    if effect.get("repeat_save_trigger") not in {None,"end_of_affected_turn"}:raise ValueError(f"{effect_label}.repeat_save_trigger is invalid")
                    if effect.get("active_pattern") not in {None,"first_target_turn_only","remaining_after_first_target_turn"}:raise ValueError(f"{effect_label}.active_pattern is invalid")
                    if effect.get("active_pattern")=="first_target_turn_only" and effect["gate"]!="on_failed_save":raise ValueError(f"{effect_label} first-stage gate is invalid")
                    if effect.get("active_pattern")=="remaining_after_first_target_turn" and (effect["gate"]!="after_failed_second_save" or effect.get("transition_checkpoint")!="end_of_first_affected_turn"):raise ValueError(f"{effect_label} second-stage transition is invalid")
                    for key in ("requires_condition_effective","attack_scope","transition_checkpoint","disjoint_stage_group","pricing_status","area_trigger"):
                        if key in effect:_string(effect[key],f"{effect_label}.{key}")
                    if effect.get("pricing_status") not in {None,"candidate","context_required","unsupported"}:raise ValueError(f"{effect_label}.pricing_status is invalid")
                    if "magnitude_feet" in effect:_integer(effect["magnitude_feet"],f"{effect_label}.magnitude_feet",0)
                    if "magnitude" in effect and (isinstance(effect["magnitude"],bool) or not isinstance(effect["magnitude"],(int,float)) or float(effect["magnitude"])<0):raise ValueError(f"{effect_label}.magnitude is invalid")
                    if "magnitude" in effect and "magnitude_feet" in effect:raise ValueError(f"{effect_label} cannot declare two magnitudes")
                    if "unpriced" in effect:_boolean(effect["unpriced"],f"{effect_label}.unpriced")
                    for key in ("conditions","outcomes","suppressed_recovery_options"):
                        if key in effect and (not isinstance(effect[key],list) or not effect[key] or any(not isinstance(item,str) or not item for item in effect[key])):raise ValueError(f"{effect_label}.{key} must be a non-empty string list")
                    if not effect.get("conditions") and not effect.get("outcomes"):raise ValueError(f"{effect_label} must declare a condition or outcome")
                    for key in ("context_predicates",):
                        if key in effect and (not isinstance(effect[key],list) or any(not isinstance(item,str) or not item for item in effect[key])):raise ValueError(f"{effect_label}.{key} must be a string list")
                    if "qualifiers" in effect:
                        qualifiers=_object(effect["qualifiers"],f"{effect_label}.qualifiers")
                        if any(not isinstance(key,str) or not key or not isinstance(value,(str,int,float,bool)) for key,value in qualifiers.items()):raise ValueError(f"{effect_label}.qualifiers is invalid")
                    if "branch_fraction" in effect:
                        fraction=_object(effect["branch_fraction"],f"{effect_label}.branch_fraction");_exact_keys(fraction,{"numerator","denominator"},f"{effect_label}.branch_fraction");numerator=_integer(fraction["numerator"],f"{effect_label}.branch_fraction.numerator",0);denominator=_integer(fraction["denominator"],f"{effect_label}.branch_fraction.denominator",1)
                        if numerator>denominator:raise ValueError(f"{effect_label}.branch_fraction exceeds one")
                    if "branch_ids" in effect and (not isinstance(effect["branch_ids"],list) or not effect["branch_ids"] or len(effect["branch_ids"])!=len(set(effect["branch_ids"])) or any(not isinstance(item,str) or not item for item in effect["branch_ids"])):raise ValueError(f"{effect_label}.branch_ids is invalid")
                    if "secondary_save" in effect:
                        secondary=_object(effect["secondary_save"],f"{effect_label}.secondary_save");_exact_keys(secondary,{"ability","trigger"},f"{effect_label}.secondary_save");_string(secondary["ability"],f"{effect_label}.secondary_save.ability")
                        if secondary["trigger"]!="start_of_affected_turn":raise ValueError(f"{effect_label}.secondary_save.trigger is invalid")
                if len(effect_ids)!=len(set(effect_ids)):raise ValueError(f"control.{build_id}.scenarios[{index}] effect IDs must be unique")
                branches=scenario.get("turn_branches",[]);branch_ids=[];branch_total=Fraction(0,1)
                if not isinstance(branches,list):raise ValueError(f"control.{build_id}.scenarios[{index}].turn_branches must be a list")
                for branch_index,branch_value in enumerate(branches):
                    branch_label=f"control.{build_id}.scenarios[{index}].turn_branches[{branch_index}]";branch=_object(branch_value,branch_label);_exact_keys(branch,{"id","numerator","denominator"},branch_label);branch_ids.append(_string(branch["id"],f"{branch_label}.id"));numerator=_integer(branch["numerator"],f"{branch_label}.numerator",0);denominator=_integer(branch["denominator"],f"{branch_label}.denominator",1);branch_total+=Fraction(numerator,denominator)
                if branches and (len(branch_ids)!=len(set(branch_ids)) or branch_total!=1):raise ValueError(f"control.{build_id}.scenarios[{index}] turn branches must be unique and sum exactly to one")
                for effect in effects:
                    if not set(effect.get("branch_ids",[]))<=set(branch_ids):raise ValueError(f"control.{build_id}.scenarios[{index}] effect references an unknown turn branch")
                declared_conditions={str(condition).lower() for effect in effects for condition in effect.get("conditions",[])}
                for effect in effects:
                    dependency=effect.get("requires_condition_effective")
                    if dependency and dependency.lower() not in declared_conditions:raise ValueError(f"control.{build_id}.scenarios[{index}] effect dependency is not declared")
                staged_groups={str(effect["disjoint_stage_group"]):{str(member.get("active_pattern")) for member in effects if member.get("disjoint_stage_group")==effect["disjoint_stage_group"]} for effect in effects if effect.get("disjoint_stage_group")}
                if any(patterns!={"first_target_turn_only","remaining_after_first_target_turn"} for patterns in staged_groups.values()):raise ValueError(f"control.{build_id}.scenarios[{index}] disjoint staged effects must form a complete pair")
                automatic=scenario.get("automatic_success_if",[])
                if not isinstance(automatic,list) or len(automatic)!=len(set(automatic)) or not set(automatic)<={"condition_immunity:exhaustion","source_explicit:does_not_sleep"}:raise ValueError(f"control.{build_id}.scenarios[{index}].automatic_success_if is invalid")
                breaks=scenario.get("breaks",[])
                if not isinstance(breaks,list):raise ValueError(f"control.{build_id}.scenarios[{index}].breaks must be a list")
                break_ids=[]
                for break_index,break_value in enumerate(breaks):
                    break_label=f"control.{build_id}.scenarios[{index}].breaks[{break_index}]";break_row=_object(break_value,break_label);break_required={"id","trigger","resolution","baseline_disposition"};break_allowed=break_required|{"save","save_advantage","success","distance_feet","context_predicate"}
                    if not break_required<=break_row.keys() or not break_row.keys()<=break_allowed:raise ValueError(f"{break_label} keys are invalid")
                    break_ids.append(_string(break_row["id"],f"{break_label}.id"))
                    for key in ("trigger","resolution","baseline_disposition","save","success"):
                        if key in break_row:_string(break_row[key],f"{break_label}.{key}")
                    if break_row["trigger"] not in {"damage","external_action"} or break_row["resolution"] not in {"repeat_save","ends_effect"} or break_row["baseline_disposition"] not in {"inactive_controller_preserves_control","inactive_no_ally_turns"}:raise ValueError(f"{break_label} semantics are invalid")
                    if break_row["resolution"]=="repeat_save" and not {"save","save_advantage","success"}<=break_row.keys():raise ValueError(f"{break_label} repeat save is incomplete")
                    if "save_advantage" in break_row:_boolean(break_row["save_advantage"],f"{break_label}.save_advantage")
                    if "distance_feet" in break_row:_integer(break_row["distance_feet"],f"{break_label}.distance_feet",0)
                if len(break_ids)!=len(set(break_ids)):raise ValueError(f"control.{build_id}.scenarios[{index}] break IDs must be unique")
                for key in ("context_predicates",):
                    values=scenario.get(key,[])
                    if not isinstance(values,list) or len(values)!=len(set(values)) or any(not isinstance(item,str) or not item for item in values):raise ValueError(f"control.{build_id}.scenarios[{index}].{key} is invalid")
                escapes=scenario.get("escapes",[])
                if not isinstance(escapes,list):raise ValueError(f"control.{build_id}.scenarios[{index}].escapes must be a list")
                for escape_index,escape_value in enumerate(escapes):
                    escape_label=f"control.{build_id}.scenarios[{index}].escapes[{escape_index}]";escape=_object(escape_value,escape_label);_exact_keys(escape,{"action","check","dc","success"},escape_label)
                    for key in escape:_string(escape[key],f"{escape_label}.{key}")
                if "targeting" in scenario:
                    target_label=f"control.{build_id}.scenarios[{index}].targeting";targeting=_object(scenario["targeting"],target_label);mode=targeting.get("mode")
                    expected_targeting={"single_target":{"mode"},"capped_selectable":{"mode","base_target_cap","higher_slot_target_increment","higher_slot_levels_per_increment"},"area_choice":{"mode","creature_selection","area"},"area_predicate":{"mode","eligibility_predicate","baseline_visual_access","area"},"area":{"mode","area"},"capped_area_selectable":{"mode","target_cap","area"}}.get(mode)
                    if expected_targeting is None:raise ValueError(f"{target_label}.mode is invalid")
                    _exact_keys(targeting,expected_targeting,target_label)
                    for key in expected_targeting-{"mode","area","creature_selection","eligibility_predicate","baseline_visual_access"}:_integer(targeting[key],f"{target_label}.{key}",1)
                    for key in ("creature_selection","eligibility_predicate","baseline_visual_access"):
                        if key in targeting:_string(targeting[key],f"{target_label}.{key}")
                    if "area" in targeting:
                        area=_object(targeting["area"],f"{target_label}.area");shape=area.get("shape");expected_area={"sphere":{"shape","radius_feet"},"cube":{"shape","size_feet"},"cone":{"shape","size_feet","origin"},"line":{"shape","length_feet","width_feet","origin"},"cylinder":{"shape","radius_feet","height_feet"},"square":{"shape","size_feet"},"emanation":{"shape","radius_feet","origin","moves_with_source","enemy_only"},"wall_or_ring":{"shape"},"environmental_volume":{"shape"}}.get(shape)
                        if shape=="cube" and "origin" in area:expected_area={"shape","size_feet","origin"}
                        if expected_area is None:raise ValueError(f"{target_label}.area.shape is invalid")
                        _exact_keys(area,expected_area,f"{target_label}.area")
                        for key in expected_area-{"shape","origin","moves_with_source","enemy_only"}:_integer(area[key],f"{target_label}.area.{key}",1)
                        if "origin" in area:_string(area["origin"],f"{target_label}.area.origin")
                        for key in ("moves_with_source","enemy_only"):
                            if key in area:_boolean(area[key],f"{target_label}.area.{key}")
        if build_id=="battle_master":
            scenario_ids=[scenario["id"] for scenario in row["scenarios"]]
            if scenario_ids!=["menacing_attack","pushing_attack","trip_attack","goading_attack","disarming_attack"]:raise ValueError("control.battle_master scenarios do not match the audited package set")
        if build_id=="eldritch_knight":
            scenario_ids=[scenario["id"] for scenario in row["scenarios"]];reliability_ids=row["reliability_scenario_ids"]
            if not isinstance(reliability_ids,list) or not reliability_ids or any(not isinstance(item,str) for item in reliability_ids) or len(reliability_ids)!=len(set(reliability_ids)):raise ValueError("control.eldritch_knight.reliability_scenario_ids must be a unique non-empty string list")
            if not set(reliability_ids)<=set(scenario_ids):raise ValueError("control.eldritch_knight reliability scenarios must reference configured scenario IDs")
    return data


def _string(value:Any,label:str)->str:
    if not isinstance(value,str) or not value:raise ValueError(f"{label} must be a non-empty string")
    return value


def load_catalog(path:Path=DEFAULT_CATALOG)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    data=_object(data,"SRD creature catalog");_exact_keys(data,{"format_version","source","creatures"},"SRD creature catalog")
    if data["format_version"]!=1:raise ValueError("Unsupported SRD creature catalog format version")
    source=_object(data["source"],"catalog source");_exact_keys(source,{"ruleset","pdf_sha256","url","modification_notice"},"catalog source")
    if source["ruleset"]!="SRD 5.2.1" or source["pdf_sha256"]!="8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87":raise ValueError("Catalog must remain pinned to the verified SRD 5.2.1 source")
    for key in ("url","modification_notice"):_string(source[key],f"catalog source.{key}")
    creatures=data["creatures"]
    if not isinstance(creatures,list) or len(creatures)!=330:raise ValueError("SRD creature catalog must contain exactly 330 creatures")
    expected={"id","name","cr","ac","hp","ability_modifiers","saving_throw_bonuses","skill_bonuses","magic_resistance","legendary_resistance","sizes","creature_type","defenses","movement","senses","passive_perception","source"};ids:set[str]=set()
    for index,value in enumerate(creatures):
        label=f"creatures[{index}]";row=_object(value,label);_exact_keys(row,expected,label);creature_id=_string(row["id"],f"{label}.id")
        if not creature_id.startswith("srd521:") or creature_id in ids:raise ValueError(f"{label}.id must be a unique stable SRD 5.2.1 ID")
        ids.add(creature_id);_string(row["name"],f"{label}.name");_integer(row["ac"],f"{label}.ac",1);_integer(row["hp"],f"{label}.hp",1)
        cr=_object(row["cr"],f"{label}.cr");_exact_keys(cr,{"numerator","denominator"},f"{label}.cr");_integer(cr["numerator"],f"{label}.cr.numerator",0);_integer(cr["denominator"],f"{label}.cr.denominator",1)
        modifiers=_object(row["ability_modifiers"],f"{label}.ability_modifiers");_exact_keys(modifiers,set(ABILITIES),f"{label}.ability_modifiers")
        for ability,bonus in modifiers.items():_integer(bonus,f"{label}.ability_modifiers.{ability}")
        saves=_object(row["saving_throw_bonuses"],f"{label}.saving_throw_bonuses")
        if not saves.keys()<=set(ABILITIES):raise ValueError(f"{label}.saving_throw_bonuses contains an unknown ability")
        for ability,bonus in saves.items():_integer(bonus,f"{label}.saving_throw_bonuses.{ability}")
        skills=row["skill_bonuses"]
        if not isinstance(skills,list):raise ValueError(f"{label}.skill_bonuses must be a list")
        skill_ids=[]
        for skill_index,item_value in enumerate(skills):
            item=_object(item_value,f"{label}.skill_bonuses[{skill_index}]");_exact_keys(item,{"skill","bonus"},f"{label}.skill_bonuses[{skill_index}]");skill=_string(item["skill"],f"{label}.skill_bonuses[{skill_index}].skill")
            if skill not in SKILLS:raise ValueError(f"{label} has unknown skill {skill}")
            _integer(item["bonus"],f"{label}.skill_bonuses[{skill_index}].bonus");skill_ids.append(skill)
        if skill_ids!=sorted(set(skill_ids)):raise ValueError(f"{label}.skill_bonuses must be unique and sorted")
        _boolean(row["magic_resistance"],f"{label}.magic_resistance");legendary=_object(row["legendary_resistance"],f"{label}.legendary_resistance")
        _exact_keys(legendary,{"uses_per_day","lair_uses_per_day","policy"},f"{label}.legendary_resistance");_integer(legendary["uses_per_day"],f"{label}.legendary_resistance.uses_per_day",0)
        if legendary["lair_uses_per_day"] is not None:_integer(legendary["lair_uses_per_day"],f"{label}.legendary_resistance.lair_uses_per_day",0)
        if legendary["policy"]!="metadata_only":raise ValueError(f"{label}.legendary_resistance.policy must remain metadata_only")
        if not isinstance(row["sizes"],list) or not row["sizes"] or any(size not in SIZE_ORDER for size in row["sizes"]):raise ValueError(f"{label}.sizes is invalid")
        _string(row["creature_type"],f"{label}.creature_type")
        defenses=_object(row["defenses"],f"{label}.defenses");_exact_keys(defenses,{"damage_resistances","damage_immunities","damage_vulnerabilities","condition_immunities"},f"{label}.defenses")
        for family,facts in defenses.items():
            if not isinstance(facts,list):raise ValueError(f"{label}.defenses.{family} must be a list")
            fact_key="condition" if family=="condition_immunities" else "damage_type"
            for fact_index,fact_value in enumerate(facts):
                fact_label=f"{label}.defenses.{family}[{fact_index}]";fact=_object(fact_value,fact_label);required={fact_key,"qualifier_id","qualifier"};allowed=required|{"choices"}
                if not required<=fact.keys() or not fact.keys()<=allowed:raise ValueError(f"{fact_label} keys are invalid")
                choices=fact.get("choices",[])
                if fact[fact_key] is None:
                    if not isinstance(choices,list) or not choices:raise ValueError(f"{fact_label} must provide a value or choices")
                    for choice_index,choice in enumerate(choices):_string(choice,f"{fact_label}.choices[{choice_index}]")
                else:_string(fact[fact_key],f"{fact_label}.{fact_key}")
        movement=_object(row["movement"],f"{label}.movement");_exact_keys(movement,{"modes","hover","choice_groups"},f"{label}.movement");modes=_object(movement["modes"],f"{label}.movement.modes");_exact_keys(modes,set(MOVEMENT_MODES),f"{label}.movement.modes");_boolean(movement["hover"],f"{label}.movement.hover")
        if not isinstance(movement["choice_groups"],list):raise ValueError(f"{label}.movement.choice_groups must be a list")
        for mode,facts in modes.items():
            if not isinstance(facts,list):raise ValueError(f"{label}.movement.modes.{mode} must be a list")
            for fact_index,fact_value in enumerate(facts):
                fact=_object(fact_value,f"{label}.movement.modes.{mode}[{fact_index}]");_exact_keys(fact,{"feet","qualifier","choice_group_id"},f"{label}.movement.modes.{mode}[{fact_index}]");_integer(fact["feet"],f"{label}.movement.modes.{mode}[{fact_index}].feet",0)
        senses=_object(row["senses"],f"{label}.senses");_exact_keys(senses,set(SENSE_KINDS),f"{label}.senses")
        for kind,facts in senses.items():
            if not isinstance(facts,list):raise ValueError(f"{label}.senses.{kind} must be a list")
            for fact_index,fact_value in enumerate(facts):
                fact=_object(fact_value,f"{label}.senses.{kind}[{fact_index}]");_exact_keys(fact,{"range_feet","limitation"},f"{label}.senses.{kind}[{fact_index}]");_integer(fact["range_feet"],f"{label}.senses.{kind}[{fact_index}].range_feet",0)
        _integer(row["passive_perception"],f"{label}.passive_perception",0);locator=_object(row["source"],f"{label}.source");_exact_keys(locator,{"page","stat_block_order","anchor"},f"{label}.source");_integer(locator["page"],f"{label}.source.page",1);_integer(locator["stat_block_order"],f"{label}.source.stat_block_order",1);_string(locator["anchor"],f"{label}.source.anchor")
    return data


def load_profiles(path:Path=DEFAULT_ROSTERS,catalog:dict[str,Any]|None=None)->dict[str,list[dict[str,Any]]]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    data=_object(data,"SRD creature profiles");_exact_keys(data,{"format_version","source_catalog","methodology","profiles"},"SRD creature profiles")
    if data["format_version"]!=1 or data["source_catalog"]!="srd_creatures.json":raise ValueError("Unsupported SRD creature profile format")
    methodology=_object(data["methodology"],"profile methodology");_exact_keys(methodology,{"eligibility_policy","headline_selection","ordering"},"profile methodology")
    for key,value in methodology.items():_string(value,f"profile methodology.{key}")
    profiles=_object(data["profiles"],"profiles");_exact_keys(profiles,set(PROFILE_COUNTS),"profiles");catalog_ids={row["id"] for row in (catalog or load_catalog())["creatures"]}
    for profile,entries in profiles.items():
        if not isinstance(entries,list) or len(entries)!=PROFILE_COUNTS[profile]:raise ValueError(f"Profile {profile} must contain exactly {PROFILE_COUNTS[profile]} entries")
        seen:set[str]=set();counts={level:0 for level in PROFILE_LEVEL_COUNTS[profile]}
        for index,value in enumerate(entries):
            row=_object(value,f"profiles.{profile}[{index}]");_exact_keys(row,{"creature_id","benchmark_level"},f"profiles.{profile}[{index}]");creature_id=_string(row["creature_id"],f"profiles.{profile}[{index}].creature_id");level=_integer(row["benchmark_level"],f"profiles.{profile}[{index}].benchmark_level")
            if creature_id in seen:raise ValueError(f"Profile {profile} repeats {creature_id}")
            if creature_id not in catalog_ids:raise ValueError(f"Profile {profile} references missing creature {creature_id}")
            if level not in counts:raise ValueError(f"Profile {profile} uses unsupported benchmark level {level}")
            seen.add(creature_id);counts[level]+=1
        if counts!=PROFILE_LEVEL_COUNTS[profile]:raise ValueError(f"Profile {profile} per-level counts changed: {counts}")
    headline={(row["creature_id"],row["benchmark_level"]) for row in profiles["headline"]};census={(row["creature_id"],row["benchmark_level"]) for row in profiles["eligible_census"]}
    if not headline<census:raise ValueError("Headline profile must be a proper subset of eligible_census")
    return profiles


def _defense_values(creature:dict[str,Any],family:str)->frozenset[str]:
    key="condition" if family=="condition_immunities" else "damage_type";values=[]
    for fact in creature["defenses"][family]:
        qualifier=fact["qualifier_id"]
        if fact[key] is None:raise ValueError(f"{creature['id']} has unresolved choice-based {family} fact")
        if qualifier is not None and not (family=="condition_immunities" and qualifier=="source_default_mind_blank"):raise ValueError(f"{creature['id']} has unsupported qualified {family} fact")
        values.append(fact[key])
    return frozenset(values)


def _sense_range(creature:dict[str,Any],kind:str)->int:
    facts=creature["senses"][kind]
    if any(fact["limitation"] is not None for fact in facts):raise ValueError(f"{creature['id']} has unsupported qualified {kind}")
    return max((int(fact["range_feet"]) for fact in facts),default=0)


def _benchmark_locomotion_speed(creature:dict[str,Any])->int|None:
    speeds=[int(fact["feet"]) for facts in creature["movement"]["modes"].values() for fact in facts if int(fact["feet"])>0 and fact["qualifier"] is None and fact["choice_group_id"] is None]
    return max(speeds,default=None)


def load_targets(profile:str=DEFAULT_PROFILE,levels:set[int]|None=None,limit:int|None=None,catalog_path:Path=DEFAULT_CATALOG,profiles_path:Path=DEFAULT_ROSTERS)->list[Target]:
    catalog=load_catalog(catalog_path);profiles=load_profiles(profiles_path,catalog)
    if profile not in profiles:raise ValueError(f"Unknown target profile {profile!r}; expected one of {sorted(profiles)}")
    by_id={row["id"]:row for row in catalog["creatures"]};source=catalog["source"];rows=[]
    for member in profiles[profile]:
        level=member["benchmark_level"]
        if levels is not None and level not in levels:continue
        creature=by_id[member["creature_id"]];saves={**creature["ability_modifiers"],**creature["saving_throw_bonuses"]}
        skill_bonuses={str(item["skill"]):int(item["bonus"]) for item in creature["skill_bonuses"]}
        rows.append(Target(level,creature["name"],creature["ac"],saves,creature["magic_resistance"],creature["legendary_resistance"]["uses_per_day"],creature["sizes"][0],creature["creature_type"],_defense_values(creature,"condition_immunities"),_defense_values(creature,"damage_resistances"),_defense_values(creature,"damage_immunities"),_defense_values(creature,"damage_vulnerabilities"),creature["hp"],source["ruleset"],str(creature["source"]["page"]),source["url"],dict(creature["ability_modifiers"]),skill_bonuses,_sense_range(creature,"blindsight"),_sense_range(creature,"truesight"),_benchmark_locomotion_speed(creature)))
    if limit is not None:rows=rows[:limit]
    if not rows:raise ValueError("Target selection is empty")
    return rows


def file_sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(65536),b""):digest.update(chunk)
    return digest.hexdigest()


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


def modified_save_success_probability(target:Target,ability:str,dc:int,*,advantage:bool=False,disadvantage:bool=False,magic_resistance:bool=True,penalty_die_sides:int=0,flat_penalty:int=0)->float:
    """Enumerate a saving throw and any finite roll penalty exactly."""
    if penalty_die_sides<0:raise ValueError("Save penalty die cannot have negative sides")
    if flat_penalty<0:raise ValueError("Save penalty cannot be negative")
    has_advantage=advantage or (target.magic_resistance and magic_resistance);has_disadvantage=disadvantage
    first_rolls=range(1,21);second_rolls=range(1,21) if has_advantage!=has_disadvantage else (0,);penalties=range(1,penalty_die_sides+1) if penalty_die_sides else (0,)
    successes=total=0
    for first in first_rolls:
        for second in second_rolls:
            if has_advantage and not has_disadvantage:natural=max(first,second)
            elif has_disadvantage and not has_advantage:natural=min(first,second)
            else:natural=first
            for penalty in penalties:
                total+=1;successes+=natural+target.saves[ability]-penalty-flat_penalty>=dc
    return successes/total


def save_success_probability(target:Target,ability:str,dc:int,disadvantage:bool=False,magic_resistance:bool=True)->float:
    return modified_save_success_probability(target,ability,dc,disadvantage=disadvantage,magic_resistance=magic_resistance)


def ability_check_success_probability(target:Target,ability:str,dc:int,skill:str|None=None)->float:
    """Resolve an ordinary d20 ability check from explicit target facts.

    A listed skill bonus wins; otherwise the underlying ability modifier is
    used. The ``saves`` fallback exists only for small synthetic test targets
    created before check facts were projected and never invents proficiency.
    """
    if ability not in ABILITIES:raise ValueError(f"Unknown ability check ability: {ability}")
    if skill is not None and skill not in SKILLS:raise ValueError(f"Unknown ability check skill: {skill}")
    if dc<0:raise ValueError("Ability check DC cannot be negative")
    bonus=target.skill_bonuses.get(skill) if skill is not None else None
    if bonus is None:bonus=target.ability_modifiers.get(ability,target.saves[ability])
    return sum(roll+bonus>=dc for roll in range(1,21))/20


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
