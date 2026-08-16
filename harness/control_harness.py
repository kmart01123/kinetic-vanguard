"""YAML-driven control reliability benchmark and selection-audit matrix."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .authority import AuthorityModel,DEFAULT_AUTHORITY
from .comparison_report import NOTICE_COLUMNS,matrix_row,write_matrix
from .model import DEFAULT_CATALOG,DEFAULT_COMPARATORS,DEFAULT_CONFIG,DEFAULT_PROFILE,DEFAULT_ROSTERS,PROFILE_COUNTS,Target,attack_probabilities,file_sha256,level_config,load_comparators,load_config,load_targets,save_success_probability,target_is_eligible


def _effect_available(target:Target,effect:dict[str,Any],target_role:str)->bool:
    role=effect.get("target_role","all")
    if role not in {"all",target_role}:return False
    dependency=effect.get("requires_condition")
    if dependency and dependency.lower() in target.condition_immunities:return False
    conditions=list(effect.get("conditions",[]));outcomes=list(effect.get("outcomes",[]))
    return bool(outcomes) or any(condition.lower() not in target.condition_immunities for condition in conditions)


def _comparator_effect_available(target:Target,scenario:dict[str,Any])->bool:
    conditions=list(scenario.get("conditions",[]));outcomes=list(scenario.get("outcomes",[]))
    return bool(outcomes) or any(condition.lower() not in target.condition_immunities for condition in conditions)


def _repeat_rider_probability(model:AuthorityModel,config:dict[str,Any],level:int,tier:int,psi_cost:int,attempt_success:float)->float:
    """Optimize retry legality for one fixed rider tier without target identity state."""
    if model.projection["core"]["manifested_strike"]["rider_repeatability"]!="per_manifested_strike":raise ValueError("Unsupported canonical rider repeatability")
    if not 0.0<=attempt_success<=1.0:raise ValueError("Attempt probability must be between zero and one")
    progression=level_config(config,level);attacks=int(progression["attacks_per_action"]);psi_pool=model.progression("psi_points",level)
    profile=config["kv_profile"];hp=int(profile["hit_point_model"]["first_level_base"])+int(profile["constitution_modifier"])+(level-1)*(int(profile["hit_point_model"]["later_level_average"])+int(profile["constitution_modifier"]));blood_budget=int(hp*float(profile["blood_tax_hp_fraction"]))
    mastery=model.projection["core"]["overload"]["mastery"];mastery_remaining=int(mastery["uses_per_rest"]) if level>=int(mastery["minimum_level"]) else 0;tier_two_limit=int(model.projection["core"]["overload"]["tier_two_limit_per_attack_action"]);blood_tax=model.blood_tax(level,tier)
    @lru_cache(maxsize=None)
    def choose(attacks_remaining:int,psi_spent:int,blood_spent:int,tier_twos:int,remaining_mastery:int,mastery_mode:int)->float:
        if attacks_remaining==0 or (tier==2 and tier_twos>=tier_two_limit):return 0.0
        next_psi=psi_spent+psi_cost
        if next_psi>psi_pool:return 0.0
        best=0.0
        for paid_tax,next_mastery,next_mode,_ in model.overload_payment_options(blood_tax,remaining_mastery,mastery_mode):
            next_blood=blood_spent+paid_tax
            if next_blood>blood_budget:continue
            continuation=choose(attacks_remaining-1,next_psi,next_blood,tier_twos+int(tier==2),next_mastery,next_mode)
            best=max(best,attempt_success+(1-attempt_success)*continuation)
        return best
    return choose(attacks,0,0,0,mastery_remaining,0 if mastery_remaining else 2)


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


def _eldritch_strike_primer_probability(attacks:int,hit_probability:float)->float:
    """Return the chance that one ordinary primer Attack action establishes a mark."""
    if attacks<0:raise ValueError("Eldritch Strike primer attacks cannot be negative")
    if not 0.0<=hit_probability<=1.0:raise ValueError("Eldritch Strike primer probability must be between zero and one")
    return 1-(1-hit_probability)**attacks


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
    named=repeat(named_single);mastery_value=repeat(mastery_single);whole=max(named,mastery_value);repeat_count=int(config["methodology"]["rounds"])-1 if control.get("repeat_save_trigger")=="start_of_affected_turn" else 0
    after=[]
    for effect in effects:
        value=repeat(effect_probability(effect))
        if repeat_count and effect["gate"]=="on_failed_save":value*=repeat_failed**repeat_count
        after.append(value)
    repeat=max([mastery_value,*after]);suffix=f":{target_role}" if target_role!="primary" else ""
    return {"build":discipline_id,"scenario":f"{entity_id}:T{tier}{suffix}","eligible":eligible,"reach":100*reach,"named":100*named,"mastery":100*mastery_value,"whole":100*whole,"after_repeats":100*repeat}


def _mastery_scenario(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str)->dict[str,Any]:
    mastery=model.disciplines[discipline_id]["mastery"];profile=config["kv_profile"]
    bonus=model.kv_attack_bonus(target.level,int(profile["psionic_ability_modifier"]))+int(profile["archery_attack_bonus"]);probabilities=attack_probabilities(bonus,target.ac);reach=probabilities[1]+probabilities[2]
    eligible=not mastery.get("maximum_size") or target_is_eligible(target,mastery["maximum_size"])
    whole=reach if eligible and mastery["control_outcomes"] else 0.0
    return {"build":discipline_id,"scenario":f"mastery:{mastery['kind']}","eligible":eligible,"reach":100*reach,"named":0.0,"mastery":100*whole,"whole":100*whole,"after_repeats":100*whole}


def _comparator_scenario(model:AuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:Target,build_id:str,scenario:dict[str,Any])->dict[str,Any]:
    row=comparators["control"][build_id];minimum=int(scenario.get("minimum_level",row["minimum_level"]));eligible=target.level>=minimum and target_is_eligible(target,scenario.get("maximum_size"))
    available=_comparator_effect_available(target,scenario)
    pb=model.progression("proficiency_bonus",target.level);weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(target.level)]);bonus=pb+int(row["attack_ability_modifier"])+weapon_bonus;reach=1.0
    if scenario.get("hit_gated"):
        probabilities=attack_probabilities(bonus,target.ac);reach=probabilities[1]+probabilities[2]
    if not eligible or not available:value=0.0
    else:
        save_modifier=int(row["save_ability_modifier_by_level"][str(target.level)]) if "save_ability_modifier_by_level" in row else int(row["save_ability_modifier"]);dc=int(row["save_dc_base"])+pb+save_modifier;normal_fail=1-save_success_probability(target,scenario["save"],dc,False,bool(row["magic_resistance_applies"]))
        if build_id=="battle_master" and scenario.get("hit_gated"):
            attacks=int(level_config(config,target.level)["attacks_per_action"]);superiority_dice=int(comparators["damage"]["battle_master"]["superiority_pool_by_level"][str(target.level)])
            value=_battle_master_retry_probability(attacks,superiority_dice,reach,normal_fail)
        elif scenario.get("primer_hit_disadvantage"):
            attacks=int(level_config(config,target.level)["attacks_per_action"]);primer=attack_probabilities(bonus,target.ac);primer_mark=_eldritch_strike_primer_probability(attacks,primer[1]+primer[2]);disadvantaged_fail=1-save_success_probability(target,scenario["save"],dc,True,bool(row["magic_resistance_applies"]));value=primer_mark*disadvantaged_fail+(1-primer_mark)*normal_fail
        else:value=reach*normal_fail
    return {"build":build_id,"scenario":scenario["id"],"eligible":eligible,"reach":100*reach,"named":100*value,"mastery":0.0,"whole":100*value,"after_repeats":100*value}


def _best(rows:list[dict[str,Any]])->dict[str,Any]:
    if not rows:raise ValueError("Configured scenario set is empty at this level")
    return max(rows,key=lambda row:(float(row["whole"]),str(row["scenario"])))


def run(authority:Path,output_dir:Path,levels:set[int],target_limit:int|None,trials:int,seed:int,write_detail:bool=True,write_headline:bool=True,profile:str=DEFAULT_PROFILE)->dict[str,Any]:
    model=AuthorityModel.load(authority);config=load_config();comparators=load_comparators();targets=load_targets(profile=profile,levels=levels,limit=target_limit);detail=[];audit=[];envelopes=[]
    scenario_sets=config["control_matrix"]["kv_scenarios"]
    for target in targets:
        comparator_best={}
        for build in ("battle_master","eldritch_knight"):
            values=[_comparator_scenario(model,config,comparators,target,build,scenario) for scenario in comparators["control"][build]["scenarios"]]
            detail.extend({"Level":target.level,"Target":target.name,**value} for value in values);comparator_best[build]=_best(values)
            audit.append({"Level":target.level,"Target":target.name,"Discipline":"all","Build":build,"Selected Scenario":comparator_best[build]["scenario"],"Whole-package control stick %":f"{comparator_best[build]['whole']:.6f}","Eligible":comparator_best[build]["eligible"]})
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
            best=_best(values);detail.extend({"Level":target.level,"Target":target.name,**value} for value in values)
            audit.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"Build":"kinetic_vanguard","Selected Scenario":best["scenario"],"Whole-package control stick %":f"{best['whole']:.6f}","Eligible":best["eligible"]})
            envelopes.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"KV":best["whole"],"Eldritch Knight":comparator_best["eldritch_knight"]["whole"],"Battle Master":comparator_best["battle_master"]["whole"]})
    slug=model.rules_version.replace(".","-");output_dir.mkdir(parents=True,exist_ok=True)
    source_columns={"Rules Version":model.rules_version,"Authority SHA-256":model.authority_sha256,"Catalog SHA-256":file_sha256(DEFAULT_CATALOG),"Roster SHA-256":file_sha256(DEFAULT_ROSTERS),"Target Profile":profile,"Config SHA-256":file_sha256(DEFAULT_CONFIG),"Comparator Config SHA-256":file_sha256(DEFAULT_COMPARATORS),**NOTICE_COLUMNS}
    if write_detail:
        detail_rows=[]
        for item in detail:detail_rows.append({"Level":item["Level"],"Target":item["Target"],"Build":item["build"],"Scenario":item["scenario"],"Eligible":item["eligible"],"Reach/Hit %":f"{item['reach']:.6f}","Named control stick %":f"{item['named']:.6f}","Mastery control floor %":f"{item['mastery']:.6f}","Whole-package control stick %":f"{item['whole']:.6f}","Still controlled after configured repeats %":f"{item['after_repeats']:.6f}",**source_columns})
        audit_rows=[{**row,**source_columns} for row in audit]
        with (output_dir/f"kv-{slug}-control-detail.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(detail_rows[0]));writer.writeheader();writer.writerows(detail_rows)
        with (output_dir/f"kv-{slug}-control-selection-audit.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(audit_rows[0]));writer.writeheader();writer.writerows(audit_rows)
    groups:dict[tuple[int,str],list[dict[str,Any]]]=defaultdict(list)
    for row in envelopes:groups[(int(row["Level"]),str(row["Discipline"]))].append(row)
    rows=[]
    for (level,discipline),values in sorted(groups.items()):
        mean=lambda key:sum(float(item[key]) for item in values)/len(values)
        rows.append(matrix_row({"Level":level,"Discipline":discipline,"Metric":config["control_matrix"]["metric"],"Profile":config["kv_profile"]["id"]},mean("KV"),mean("Eldritch Knight"),mean("Battle Master"),"control"))
    provenance={"rules_version":model.rules_version,"authority_sha256":model.authority_sha256,"catalog_sha256":file_sha256(DEFAULT_CATALOG),"roster_sha256":file_sha256(DEFAULT_ROSTERS),"target_profile":profile,"config_sha256":file_sha256(DEFAULT_CONFIG),"comparator_config_sha256":file_sha256(DEFAULT_COMPARATORS),"trials":trials,"seed":seed,"evaluator":"exact_analytical_enumeration","trial_seed_role":"historical_compatibility_metadata","aggregation":config["control_matrix"]["aggregation"],"status":config["methodology"]["status"]}
    paths=write_matrix(output_dir,model.rules_version,"control",rows,provenance) if write_headline else {}
    return {"rules_version":model.rules_version,"detail_rows":len(detail),"audit_rows":len(audit),"matrix_rows":len(rows),"paths":paths}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--authority",type=Path,default=DEFAULT_AUTHORITY);parser.add_argument("--output-dir",type=Path,required=True);parser.add_argument("--profile",choices=tuple(PROFILE_COUNTS),default=DEFAULT_PROFILE);parser.add_argument("--levels",default="7,11,15,20");parser.add_argument("--target-limit",type=int);parser.add_argument("--trials",type=int);parser.add_argument("--seed",type=int);parser.add_argument("--validate-only",action="store_true");parser.add_argument("--matrix-only",action="store_true");parser.add_argument("--no-matrix",action="store_true");args=parser.parse_args()
    model=AuthorityModel.load(args.authority)
    if args.validate_only:load_config();load_comparators();load_targets(profile=args.profile);print(f"Validated Kinetic Vanguard {model.rules_version} authority {model.authority_sha256}, target profile {args.profile}, and isolated comparator config");return
    config=load_config();trials=args.trials if args.trials is not None else int(config["methodology"]["control_default_trials"]);seed=args.seed if args.seed is not None else int(config["methodology"]["control_seed"]);levels={int(value) for value in args.levels.split(",")}
    if trials<=0 or (args.target_limit is not None and args.target_limit<=0):parser.error("--trials and --target-limit must be positive")
    result=run(args.authority,args.output_dir,levels,args.target_limit,trials,seed,not args.matrix_only,not args.no_matrix,args.profile);print(f"Control harness wrote {result['detail_rows']} detail rows, {result['audit_rows']} audit rows, and {result['matrix_rows']} matrix rows for rules {result['rules_version']}")


if __name__=="__main__":main()
