"""YAML-driven damage benchmark with BM/EK headline matrices."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from .authority import AuthorityModel,DEFAULT_AUTHORITY
from .comparison_report import matrix_row,write_matrix
from .model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,DEFAULT_ROSTER,Target,attack_probabilities,damage_multiplier,expected_damage,file_sha256,level_config,load_comparators,load_config,load_targets,save_success_probability


def _target_count(rule:dict[str,Any],tier:int,cluster_size:int,pb:int)->int:
    target=next((item for item in rule.get("targeting_by_tier",[]) if int(item["tier"])==tier),None)
    if target is None:return 1
    kind=target["kind"]
    additional=int(target.get("additional_targets",0)) if kind=="fixed_additional" else pb if kind=="proficiency_bonus_additional" else cluster_size-1
    return 1+min(max(0,cluster_size-1),additional)


def _save_adjusted(value:float,damage:dict[str,Any],save:str|None,target:Target,dc:int)->float:
    if damage["resolution"]=="always":return value
    if save is None:raise ValueError("Save-gated damage lacks a canonical save")
    success=save_success_probability(target,save,dc)
    return value*(1-success) if damage["resolution"]=="failed_save" else value*(1-0.5*success)


def _feature_value(model:AuthorityModel,rule:dict[str,Any],tier:int,target:Target,cluster_size:int,level:int,pb:int,psi_modifier:int,strike_die:int)->tuple[float,float]:
    damage_tier=next((item for item in rule["damage_tiers"] if int(item["tier"])==tier),None)
    if damage_tier is None:return 0.0,0.0
    discipline=model.disciplines[rule["discipline_ids"][0]]
    damage_type=discipline["damage_type"] if rule["damage_type"]=="discipline" else rule["damage_type"]
    ignore=tier in rule.get("ignore_resistance_tiers",[])
    raw=expected_damage(damage_tier["damage"],strike_die,psi_modifier)
    save_dc=model.kv_save_dc(level,psi_modifier)
    primary=_save_adjusted(raw,damage_tier["damage"],damage_tier.get("save"),target,save_dc)*damage_multiplier(target,damage_type,ignore)
    count=_target_count(rule,tier,cluster_size,pb)
    secondary_damage=damage_tier.get("secondary_damage",damage_tier["damage"])
    secondary_raw=expected_damage(secondary_damage,strike_die,psi_modifier)
    secondary=_save_adjusted(secondary_raw,secondary_damage,damage_tier.get("save"),target,save_dc)*damage_multiplier(target,damage_type,ignore)
    return primary,primary+max(0,count-1)*secondary


def _kv_dpr(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str,cluster_size:int)->tuple[float,float,str]:
    level=target.level;profile=config["kv_profile"];psi_modifier=int(profile["psionic_ability_modifier"]);pb=model.progression("proficiency_bonus",level);strike_die=model.progression("manifested_strike_die",level);psi=model.progression("psi_points",level)
    progression=level_config(config,level);attacks=int(progression["attacks_per_action"]);actions=int(progression["attack_actions_over_three_rounds"])
    attack_bonus=model.kv_attack_bonus(level,psi_modifier)+int(profile["archery_attack_bonus"]);miss,hit,critical=attack_probabilities(attack_bonus,target.ac);trigger=hit+critical
    discipline=model.disciplines[discipline_id];core=model.projection["core"]["manifested_strike"]
    normal_mult=damage_multiplier(target,discipline["damage_type"]);holdout_mult=damage_multiplier(target,core["holdout_damage_type"])/float(core["holdout_damage_divisor"])
    base_mult=max(normal_mult,holdout_mult);base=(hit*((strike_die+1)/2+psi_modifier)+critical*(core["critical_dice_multiplier"]*(strike_die+1)/2+psi_modifier))*base_mult
    if discipline["mastery"]["kind"]=="graze":base+=miss*psi_modifier*base_mult
    blood_budget=(10+int(profile["constitution_modifier"])+(level-1)*(6+int(profile["constitution_modifier"])))*float(profile["blood_tax_hp_fraction"])
    tier_minimum={int(row["tier"]):int(row["minimum_level"]) for row in model.projection["progressions"]["tier_minimum_levels"]}
    candidates=[]
    for rule in model.features.values():
        if discipline_id not in rule["discipline_ids"] or not rule["damage_tiers"] or level<int(rule["minimum_level"]):continue
        if rule.get("requires_additional_target") and cluster_size<2:continue
        for damage_tier in rule["damage_tiers"]:
            tier=int(damage_tier["tier"])
            if level<tier_minimum[tier]:continue
            blood=model.blood_tax(level,tier);cost=int(rule["psi_cost"])
            if blood>blood_budget or cost>psi:continue
            primary,aggregate=_feature_value(model,rule,tier,target,cluster_size,level,pb,psi_modifier,strike_die)
            candidates.append({"entity_id":rule["entity_id"],"tier":tier,"cost":cost,"blood":blood,"primary":primary,"aggregate":aggregate,"delivery":rule["damage_delivery"],"repeatability":rule["repeatability"]})
    remaining_psi=psi;remaining_blood=blood_budget;primary_total=aggregate_total=0.0;selected=[]
    for _ in range(actions):
        affordable=[item for item in candidates if item["cost"]<=remaining_psi and item["blood"]<=remaining_blood]
        standalone=[item for item in affordable if item["delivery"]=="standalone"]
        riders=[item for item in affordable if item["delivery"]=="on_hit_rider"]
        best_rider=max(riders,key=lambda item:(item["aggregate"],item["primary"]),default=None)
        attack_primary=attacks*base+(trigger*best_rider["primary"] if best_rider else 0.0)
        attack_aggregate=attacks*base+(trigger*best_rider["aggregate"] if best_rider else 0.0)
        best_standalone=max(standalone,key=lambda item:(item["aggregate"],item["primary"]),default=None)
        if best_standalone and best_standalone["aggregate"]>attack_aggregate:
            choice=best_standalone;primary_total+=choice["primary"];aggregate_total+=choice["aggregate"]
        else:
            choice=best_rider;primary_total+=attack_primary;aggregate_total+=attack_aggregate
        if choice:
            remaining_psi-=choice["cost"];remaining_blood-=choice["blood"];selected.append(f"{choice['entity_id']}:T{choice['tier']}")
    return primary_total/3.0,aggregate_total/3.0,";".join(selected) or "manifested_strike"


def _die_average(count:int,sides:int,great_weapon_fighting:bool=False)->float:
    average=(sides+1)/2
    if great_weapon_fighting:average=sum((sum(range(1,sides+1))/sides if face<=2 else face) for face in range(1,sides+1))/sides
    return count*average


def _comparator_dpr(model:AuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:Target,comparator_id:str)->float:
    level=target.level;pb=model.progression("proficiency_bonus",level);progression=level_config(config,level);attacks=int(progression["attacks_per_action"]);actions=int(progression["attack_actions_over_three_rounds"]);total_attacks=attacks*actions
    row=comparators["damage"][comparator_id];bonus=pb+int(row["ability_modifier"])+int(row["attack_bonus_adjustment"]);miss,hit,critical=attack_probabilities(bonus,target.ac);weapon=row["weapon"]
    dice=_die_average(int(weapon["count"]),int(weapon["sides"]),bool(weapon["great_weapon_fighting"]));mult=damage_multiplier(target,weapon["damage_type"])
    total=total_attacks*(hit*(dice+row["ability_modifier"])+critical*(2*dice+row["ability_modifier"]))*mult
    if comparator_id=="battle_master":
        turns=3;total+=turns*float(row["great_weapon_master_damage_per_turn"])*(1-miss**attacks)*mult
        superiority=(int(row["superiority_die_by_level"][str(level)])+1)/2*mult;total+=min(float(row["maneuver_uses_over_three_rounds"][str(level)]),total_attacks*(hit+critical))*superiority
    else:
        true=row["true_strike_damage_by_level"][str(level)];extra=_die_average(int(true["count"]),int(true["sides"]))*damage_multiplier(target,row["true_strike_damage_type"])
        total+=int(row["true_strike_uses_over_three_rounds"])*(hit+critical)*extra
    return total/3.0


def run(authority:Path,output_dir:Path,levels:set[int],target_limit:int|None,trials:int,seed:int,write_detail:bool=True,write_headline:bool=True)->dict[str,Any]:
    model=AuthorityModel.load(authority);config=load_config();comparators=load_comparators();targets=load_targets(levels=levels,limit=target_limit);clusters=config["methodology"]["cluster_sizes"]
    detail=[]
    for target in targets:
        ek=_comparator_dpr(model,config,comparators,target,"eldritch_knight");bm=_comparator_dpr(model,config,comparators,target,"battle_master")
        for discipline in model.disciplines:
            for cluster in clusters:
                primary,aggregate,selection=_kv_dpr(model,config,target,discipline,int(cluster));detail.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"Cluster Size":cluster,"KV Primary DPR":primary,"KV Aggregate DPR":aggregate,"Eldritch Knight DPR":ek,"Battle Master DPR":bm,"Selection":selection})
    slug=model.rules_version.replace(".","-");output_dir.mkdir(parents=True,exist_ok=True)
    source_columns={"Rules Version":model.rules_version,"Authority SHA-256":model.authority_sha256,"Roster SHA-256":file_sha256(DEFAULT_ROSTER),"Config SHA-256":file_sha256(DEFAULT_CONFIG),"Comparator Config SHA-256":file_sha256(DEFAULT_COMPARATORS)}
    if write_detail:
        detail_rows=[{**row,**source_columns} for row in detail]
        with (output_dir/f"kv-{slug}-damage-detail.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(detail_rows[0]));writer.writeheader();writer.writerows(detail_rows)
    groups:dict[tuple[int,str,int],list[dict[str,Any]]]=defaultdict(list)
    for row in detail:groups[(int(row["Level"]),str(row["Discipline"]),int(row["Cluster Size"]))].append(row)
    rows=[]
    for (level,discipline,cluster),values in sorted(groups.items()):
        for scope,field in (("primary-target DPR","KV Primary DPR"),("aggregate cluster DPR","KV Aggregate DPR")):
            mean=lambda key:sum(float(item[key]) for item in values)/len(values)
            rows.append(matrix_row({"Level":level,"Discipline":discipline,"Cluster Size":cluster,"Damage Scope":scope,"Profile":config["kv_profile"]["id"]},mean(field),mean("Eldritch Knight DPR"),mean("Battle Master DPR"),"damage"))
    provenance={"rules_version":model.rules_version,"authority_sha256":model.authority_sha256,"roster_sha256":file_sha256(DEFAULT_ROSTER),"config_sha256":file_sha256(DEFAULT_CONFIG),"comparator_config_sha256":file_sha256(DEFAULT_COMPARATORS),"trials":trials,"seed":seed,"aggregation":"equal-weight roster means; percentages from displayed aggregates","status":"PORTED_UNDER_REVIEW"}
    paths=write_matrix(output_dir,model.rules_version,"damage",rows,provenance) if write_headline else {}
    return {"rules_version":model.rules_version,"detail_rows":len(detail),"matrix_rows":len(rows),"paths":paths}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--authority",type=Path,default=DEFAULT_AUTHORITY);parser.add_argument("--output-dir",type=Path,required=True);parser.add_argument("--levels",default="7,11,15,20");parser.add_argument("--target-limit",type=int);parser.add_argument("--trials",type=int);parser.add_argument("--seed",type=int);parser.add_argument("--validate-only",action="store_true");parser.add_argument("--matrix-only",action="store_true");parser.add_argument("--no-matrix",action="store_true");args=parser.parse_args()
    model=AuthorityModel.load(args.authority)
    if args.validate_only:load_config();load_comparators();print(f"Validated Kinetic Vanguard {model.rules_version} authority {model.authority_sha256} and isolated comparator config");return
    config=load_config();trials=args.trials if args.trials is not None else int(config["methodology"]["damage_default_trials"]);seed=args.seed if args.seed is not None else int(config["methodology"]["damage_seed"]);levels={int(value) for value in args.levels.split(",")}
    if trials<=0 or (args.target_limit is not None and args.target_limit<=0):parser.error("--trials and --target-limit must be positive")
    result=run(args.authority,args.output_dir,levels,args.target_limit,trials,seed,not args.matrix_only,not args.no_matrix);print(f"Damage harness wrote {result['detail_rows']} detail rows and {result['matrix_rows']} matrix rows for rules {result['rules_version']}")


if __name__=="__main__":main()
