"""YAML-driven damage benchmark with BM/EK headline matrices."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .authority import AuthorityModel,DEFAULT_AUTHORITY
from .comparison_report import NOTICE_COLUMNS,matrix_row,write_matrix
from .ek_damage_planner import EKDamagePlanner
from .model import DEFAULT_CATALOG,DEFAULT_COMPARATORS,DEFAULT_CONFIG,DEFAULT_PROFILE,DEFAULT_ROSTERS,PROFILE_COUNTS,Target,fighter_action_schedules,file_sha256,level_config,load_comparators,load_config,load_targets,save_success_probability


@dataclass(frozen=True)
class Package:
    entity_id:str|None;tier:int;psi:int;blood:int


@dataclass(frozen=True)
class Standalone:
    entity_id:str;tier:int;psi:int;blood:int;primary:float;aggregate:float;starts_zone:bool


@dataclass(frozen=True)
class _Score:
    primary:float;aggregate:float


@dataclass(frozen=True)
class _Decision:
    score:_Score;choice:tuple[Any,...]


@dataclass(frozen=True)
class _ScheduledScore:
    score:_Score
    primary_schedule:tuple[int,...]
    aggregate_schedule:tuple[int,...]


def _fighter_schedules(config:dict[str,Any],level:int)->tuple[tuple[int,...],...]:
    return fighter_action_schedules(level_config(config,level),int(config["methodology"]["rounds"]))


def _schedule_label(schedule:tuple[int,...])->str:
    return "["+",".join(str(value) for value in schedule)+"]"


def _target_count(rule:dict[str,Any],tier:int,cluster_size:int,pb:int)->int:
    target=next((item for item in rule.get("targeting_by_tier",[]) if int(item["tier"])==tier),None)
    if target is None:return 1
    kind=target["kind"]
    additional=int(target.get("additional_targets",0)) if kind=="fixed_additional" else pb if kind=="proficiency_bonus_additional" else cluster_size-1
    return 1+min(max(0,cluster_size-1),additional)


def _cluster_signature(model:AuthorityModel,config:dict[str,Any],discipline_id:str,level:int,cluster_size:int)->tuple[tuple[str,int,int],...]:
    """Identify cluster sizes that expose the same legal damage choices and target counts."""
    profile=config["kv_profile"];pb=model.progression("proficiency_bonus",level);tier_minimum={int(row["tier"]):int(row["minimum_level"]) for row in model.projection["progressions"]["tier_minimum_levels"]};excluded={item["entity_id"] for item in config["damage_matrix"]["excluded_stateful_features"]};signature=[]
    for rule in model.features.values():
        if rule["entity_id"] in excluded or discipline_id not in rule["discipline_ids"] or rule["damage_delivery"] not in {"on_hit_rider","standalone"} or level<int(rule["minimum_level"]):continue
        if profile["advanced_training_policy"]=="disabled" and rule["selectable_advanced_training"]:continue
        if rule.get("requires_additional_target") and cluster_size<2:continue
        for tier_row in rule["damage_tiers"]:
            tier=int(tier_row["tier"])
            if level>=tier_minimum[tier]:signature.append((str(rule["entity_id"]),tier,_target_count(rule,tier,cluster_size,pb)))
    return tuple(signature)


def _raw_distribution(damage:dict[str,Any],strike_die:int,psi_modifier:int)->dict[int,float]:
    kind=damage["kind"]
    if kind=="none":return {0:1.0}
    if kind=="fixed":return {int(damage["value"]):1.0}
    if kind=="dice":return _die_distribution(int(damage["count"]),int(damage["sides"]))
    if kind=="manifested_strike_dice":return _die_distribution(int(damage["count"]),strike_die)
    if kind=="psionic_ability_modifier":return {psi_modifier*int(damage.get("multiplier",1)):1.0}
    raise ValueError(f"Unsupported damage kind: {kind}")


def _rule_damage(target:Target,damage:dict[str,Any],damage_type:str,strike_die:int,psi_modifier:int,save_probability:float|None,ignore_resistance:bool=False)->float:
    distribution=_raw_distribution(damage,strike_die,psi_modifier)
    def profiled(value:int)->int:
        if ignore_resistance and damage_type.lower() in target.damage_resistances:
            adjusted=Target(**{**target.__dict__,"damage_resistances":frozenset(item for item in target.damage_resistances if item!=damage_type.lower())})
            return _profile_damage(adjusted,damage_type,value)
        return _profile_damage(target,damage_type,value)
    full=sum(probability*profiled(value) for value,probability in distribution.items());resolution=damage["resolution"]
    if resolution=="always":return full
    if save_probability is None:raise ValueError("Save-gated damage lacks a canonical save")
    if resolution=="failed_save":return (1-save_probability)*full
    if resolution=="half_on_success":
        half=sum(probability*profiled(value//2) for value,probability in distribution.items())
        return (1-save_probability)*full+save_probability*half
    raise ValueError(f"Unsupported damage resolution: {resolution}")


def _strike_packet_options(model:AuthorityModel,target:Target,discipline_id:str,level:int,psi_modifier:int,strike_die:int)->tuple[tuple[str,tuple[float,float,float]],...]:
    """Return every undominated pre-roll Manifested Strike damage-type declaration."""
    discipline=model.disciplines[discipline_id];core=model.projection["core"]["manifested_strike"];normal_type=discipline["damage_type"];holdout=core["holdout"];force_type=holdout["damage_type"];holdout_formula=model.holdout_formula(level)
    def packets(damage_type:str,formula:dict[str,Any]|None)->tuple[float,float,float]:
        def expected(count:int)->float:
            if formula is None:return sum(probability*_profile_damage(target,damage_type,roll+psi_modifier) for roll,probability in _die_distribution(count,strike_die).items())
            if formula["kind"]=="halve_total_rounded_down":return sum(probability*_profile_damage(target,damage_type,(roll+psi_modifier)//2) for roll,probability in _die_distribution(count,strike_die).items())
            if formula["kind"]=="dice_plus_psionic_ability_modifier":return sum(probability*_profile_damage(target,damage_type,roll+psi_modifier) for roll,probability in _die_distribution(count*int(formula["count"]),int(formula["sides"])).items())
            raise ValueError(f"Unsupported Holdout formula: {formula['kind']}")
        graze_value=psi_modifier//2 if formula and formula["kind"]=="halve_total_rounded_down" else psi_modifier
        graze=float(_profile_damage(target,damage_type,graze_value)) if discipline["mastery"]["kind"]=="graze" else 0.0
        return graze,expected(1),expected(int(core["critical_dice_multiplier"]))
    normal=packets(normal_type,None);holdout_packets=packets(force_type,holdout_formula)
    if all(left>=right for left,right in zip(normal,holdout_packets)):return (("normal",normal),)
    if all(left>=right for left,right in zip(holdout_packets,normal)):return (("holdout",holdout_packets),)
    return (("normal",normal),("holdout",holdout_packets))


def _psionic_apex_packet(model:AuthorityModel,target:Target,discipline_id:str,level:int)->float|None:
    packet=model.psionic_apex_strike_packet(discipline_id,level)
    if packet is None:return None
    if packet!={"discipline_id":"psychokinesis","uses_per_attack_action":1,"reset":"start_of_each_attack_action","damage_type":"force","damage":{"kind":"dice","count":3,"sides":8},"critical_dice_multiplier":1,"psi_cost":0,"blood_tax":0}:raise ValueError("Unsupported canonical Psionic Apex strike packet")
    damage=packet["damage"]
    return sum(probability*_profile_damage(target,packet["damage_type"],roll) for roll,probability in _die_distribution(int(damage["count"]),int(damage["sides"])).items())


def _rider_values(model:AuthorityModel,target:Target,discipline_id:str,cluster_size:int,level:int,pb:int,psi_modifier:int,strike_die:int,package:Package)->tuple[float,float]:
    if package.entity_id is None:return 0.0,0.0
    rule=model.features[package.entity_id];tier_row=next(item for item in rule["damage_tiers"] if int(item["tier"])==package.tier);discipline=model.disciplines[discipline_id];damage_type=discipline["damage_type"] if rule["damage_type"]=="discipline" else rule["damage_type"]
    save=tier_row.get("save");save_probability=None
    if save:
        save=model.disciplines[discipline_id]["signature_save"] if save=="discipline_signature" else save
        save_probability=save_success_probability(target,save,model.kv_save_dc(level,psi_modifier))
    ignore=package.tier in rule.get("ignore_resistance_tiers",[]);primary=_rule_damage(target,tier_row["damage"],damage_type,strike_die,psi_modifier,save_probability,ignore)
    count=_target_count(rule,package.tier,cluster_size,pb);secondary_damage=tier_row.get("secondary_damage",tier_row["damage"]);secondary=_rule_damage(target,secondary_damage,damage_type,strike_die,psi_modifier,save_probability,ignore)
    return primary,primary+max(0,count-1)*secondary


def _fracture(rule:dict[str,Any],tier:int)->int:
    return next((int(item["value"]) for item in rule.get("armor_class_reduction_by_tier",[]) if int(item["tier"])==tier),0)


class _KVDamagePlanner:
    """Exact finite-horizon policy over only information observable at each declaration."""

    def __init__(self,model:AuthorityModel,target:Target,packages:tuple[Package,...],rider_values:dict[Package,tuple[float,float]],strike_options:tuple[tuple[str,tuple[float,float,float]],...],standalones_by_round:tuple[tuple[Standalone,...],...],attack_bonus:int,attacks_per_action:int,action_slots_by_round:tuple[int,...],studied_enabled:bool,prowess_enabled:bool,psi_pool:int,blood_budget:int,mastery:dict[str,Any],mastery_uses:int,standalone_limit:int,apex_packet:float|None)->None:
        self.model=model;self.target=target;self.packages=packages;self.rider_values=rider_values;self.strike_options=strike_options;self.standalones_by_round=standalones_by_round;self.attack_bonus=attack_bonus;self.attacks_per_action=attacks_per_action;self.action_slots_by_round=action_slots_by_round;self.studied_enabled=studied_enabled;self.prowess_enabled=prowess_enabled;self.psi_pool=psi_pool;self.blood_budget=blood_budget;self.mastery=mastery;self.mastery_uses=mastery_uses;self.standalone_limit=standalone_limit;self.apex_packet=apex_packet
        self.fractures=tuple(_fracture(model.features[package.entity_id],package.tier) if package.entity_id else 0 for package in packages);self.tier_two_limit=int(model.projection["core"]["overload"]["tier_two_limit_per_attack_action"]);self._roll_probability_cache={}

    @staticmethod
    def _better(candidate:_Decision,best:_Decision|None)->bool:
        return best is None or (candidate.score.aggregate,candidate.score.primary)>(best.score.aggregate,best.score.primary)

    def _payment_options(self,tax:int,mastery_remaining:int,mastery_mode:int)->tuple[tuple[int,int,int,bool],...]:
        return self.model.overload_payment_options(tax,mastery_remaining,mastery_mode)

    @lru_cache(maxsize=None)
    def _round(self,round_index:int,studied:bool,psi:int,blood:int,mastery_remaining:int,zone_active:bool)->_Decision:
        if round_index==len(self.action_slots_by_round):return _Decision(_Score(0.0,0.0),("complete",))
        mastery_mode=0 if mastery_remaining else 2
        return self._actions(round_index,self.action_slots_by_round[round_index],studied,self.prowess_enabled,0,psi,blood,mastery_remaining,mastery_mode,zone_active,0,False)

    @lru_cache(maxsize=None)
    def _actions(self,round_index:int,action_slots_left:int,studied:bool,prowess:bool,ac_reduction:int,psi:int,blood:int,mastery_remaining:int,mastery_mode:int,zone_active:bool,standalone_count:int,attacked_this_turn:bool)->_Decision:
        if action_slots_left==0:
            carry_studied=studied if attacked_this_turn else False
            continuation=self._round(round_index+1,carry_studied,psi,blood,mastery_remaining,zone_active)
            return _Decision(continuation.score,("end_turn",carry_studied))
        best=None
        attack=self._attacks(round_index,action_slots_left-1,self.attacks_per_action,0,self.apex_packet is not None,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
        candidate=_Decision(attack.score,("attack",))
        if self._better(candidate,best):best=candidate
        if standalone_count<self.standalone_limit:
            for standalone_index,standalone in enumerate(self.standalones_by_round[round_index]):
                if standalone.starts_zone and zone_active:continue
                next_psi=psi+standalone.psi
                if next_psi>self.psi_pool:continue
                for tax,next_mastery,next_mode,activated in self._payment_options(standalone.blood,mastery_remaining,mastery_mode):
                    next_blood=blood+tax
                    if next_blood>self.blood_budget:continue
                    continuation=self._actions(round_index,action_slots_left-1,studied,prowess,ac_reduction,next_psi,next_blood,next_mastery,next_mode,zone_active or standalone.starts_zone,standalone_count+1,attacked_this_turn)
                    score=_Score(standalone.primary+continuation.score.primary,standalone.aggregate+continuation.score.aggregate);candidate=_Decision(score,("standalone",standalone_index,tax,next_mastery,next_mode,activated))
                    if self._better(candidate,best):best=candidate
        if best is None:raise RuntimeError("No legal action choice")
        return best

    def _roll_probabilities(self,studied:bool,ac_reduction:int)->tuple[tuple[str,float],...]:
        key=(studied,ac_reduction)
        if key not in self._roll_probability_cache:
            probabilities:dict[str,float]=defaultdict(float)
            for natural,probability in _natural_probabilities(self.studied_enabled and studied).items():
                outcome="critical" if natural==20 else "hit" if natural!=1 and natural+self.attack_bonus>=self.target.ac-ac_reduction else "miss";probabilities[outcome]+=probability
            self._roll_probability_cache[key]=tuple((outcome,probabilities[outcome]) for outcome in ("miss","hit","critical") if probabilities[outcome])
        return self._roll_probability_cache[key]

    def _roll_options(self,package_index:int,strike_index:int,outcome:str,apex_available:bool,prowess:bool,ac_reduction:int)->tuple[tuple[str,bool,bool,bool,int,float,float],...]:
        package=self.packages[package_index];strike=self.strike_options[strike_index][1];rider_primary,rider_aggregate=self.rider_values[package];fracture=self.fractures[package_index]
        if outcome!="miss":
            packet=strike[2 if outcome=="critical" else 1];apex=float(self.apex_packet) if apex_available else 0.0
            return ((outcome,False,False,prowess,max(ac_reduction,fracture),packet+rider_primary+apex,packet+rider_aggregate+apex),)
        options=[("miss",self.studied_enabled,apex_available,prowess,ac_reduction,strike[0],strike[0])]
        if prowess:
            apex=float(self.apex_packet) if apex_available else 0.0;options.append(("prowess",False,False,False,max(ac_reduction,fracture),strike[1]+rider_primary+apex,strike[1]+rider_aggregate+apex))
        return tuple(options)

    def _resolve_attack_roll(self,round_index:int,action_slots_after:int,attacks_left_after:int,tier_twos:int,apex_available:bool,package_index:int,strike_index:int,outcome:str,prowess:bool,ac_reduction:int,psi:int,blood:int,mastery_remaining:int,mastery_mode:int,zone_active:bool,standalone_count:int)->_Decision:
        best=None
        for resolution,next_studied,next_apex,next_prowess,next_reduction,primary,aggregate in self._roll_options(package_index,strike_index,outcome,apex_available,prowess,ac_reduction):
            continuation=self._attacks(round_index,action_slots_after,attacks_left_after,tier_twos,next_apex,next_studied,next_prowess,next_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
            candidate=_Decision(_Score(primary+continuation.score.primary,aggregate+continuation.score.aggregate),(resolution,next_studied,next_apex,next_prowess,next_reduction,primary,aggregate))
            if self._better(candidate,best):best=candidate
        if best is None:raise RuntimeError("No legal roll resolution")
        return best

    @lru_cache(maxsize=None)
    def _attacks(self,round_index:int,action_slots_after:int,attacks_left:int,tier_twos:int,apex_available:bool,studied:bool,prowess:bool,ac_reduction:int,psi:int,blood:int,mastery_remaining:int,mastery_mode:int,zone_active:bool,standalone_count:int)->_Decision:
        if attacks_left==0:
            continuation=self._actions(round_index,action_slots_after,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count,True)
            return _Decision(continuation.score,("end_attack_action",))
        best=None
        for package_index,package in enumerate(self.packages):
            next_tier_twos=tier_twos+int(package.tier==2)
            if next_tier_twos>self.tier_two_limit:continue
            next_psi=psi+package.psi
            if next_psi>self.psi_pool:continue
            for strike_index,_ in enumerate(self.strike_options):
                for tax,next_mastery,next_mode,activated in self._payment_options(package.blood,mastery_remaining,mastery_mode):
                    next_blood=blood+tax
                    if next_blood>self.blood_budget:continue
                    primary=aggregate=0.0
                    for outcome,probability in self._roll_probabilities(studied,ac_reduction):
                        resolution=self._resolve_attack_roll(round_index,action_slots_after,attacks_left-1,next_tier_twos,apex_available,package_index,strike_index,outcome,prowess,ac_reduction,next_psi,next_blood,next_mastery,next_mode,zone_active,standalone_count)
                        primary+=probability*resolution.score.primary;aggregate+=probability*resolution.score.aggregate
                    candidate=_Decision(_Score(primary,aggregate),("strike",package_index,strike_index,tax,next_mastery,next_mode,activated))
                    if self._better(candidate,best):best=candidate
        if best is None:raise RuntimeError("No legal Manifested Strike declaration")
        return best

    def solve(self)->_Score:
        return self._round(0,False,0,0,self.mastery_uses,False).score

    def selection(self)->str:
        studied=False;psi=blood=0;mastery_remaining=self.mastery_uses;zone_active=False;rounds=[]
        for round_index,initial_slots in enumerate(self.action_slots_by_round):
            prowess=self.prowess_enabled;ac_reduction=0;mastery_mode=0 if mastery_remaining else 2;standalone_count=0;attacked=False;slots=initial_slots;entries=[];mastery_activated=False
            while slots:
                action=self._actions(round_index,slots,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count,attacked)
                if action.choice[0]=="standalone":
                    _,index,tax,mastery_remaining,mastery_mode,activated=action.choice;standalone=self.standalones_by_round[round_index][index];psi+=standalone.psi;blood+=tax;zone_active=zone_active or standalone.starts_zone;standalone_count+=1;slots-=1;mastery_activated=mastery_activated or activated;entries.append(f"{standalone.entity_id}:T{standalone.tier}");continue
                labels=[];tier_twos=0;apex_available=self.apex_packet is not None
                for attacks_left in range(self.attacks_per_action,0,-1):
                    declaration=self._attacks(round_index,slots-1,attacks_left,tier_twos,apex_available,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
                    _,package_index,strike_index,tax,mastery_remaining,mastery_mode,activated=declaration.choice;package=self.packages[package_index];psi+=package.psi;blood+=tax;tier_twos+=int(package.tier==2);mastery_activated=mastery_activated or activated
                    grouped:dict[tuple[Any,...],float]=defaultdict(float)
                    for outcome,probability in self._roll_probabilities(studied,ac_reduction):
                        resolution=self._resolve_attack_roll(round_index,slots-1,attacks_left-1,tier_twos,apex_available,package_index,strike_index,outcome,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
                        grouped[resolution.choice]+=probability
                    resolved=sorted(grouped.items(),key=lambda item:(-item[1],repr(item[0])))[0][0];_,studied,apex_available,prowess,ac_reduction,_,_=resolved
                    if package.entity_id:labels.append(f"{package.entity_id}:T{package.tier}")
                    elif self.strike_options[strike_index][0]!="normal":labels.append(f"manifested_strike@{self.strike_options[strike_index][0]}")
                entries.append("attack("+(";".join(labels) if labels else "manifested_strike")+")");attacked=True;slots-=1
            if not attacked:studied=False
            marker=";mastery" if mastery_activated else "";rounds.append(f"R{round_index+1}[{','.join(entries)}{marker}]")
        return "|".join(rounds)+"|representative=locally-modal-path|policy=observed-state-adaptive"

    def clear(self)->None:
        self._roll_probability_cache.clear();self._attacks.cache_clear();self._actions.cache_clear();self._round.cache_clear()


def _validate_damage_policy_contract(model:AuthorityModel,config:dict[str,Any])->None:
    action_economy=model.projection["core"]["action_economy"]
    if action_economy!={"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False}:raise ValueError("Unsupported canonical standalone psionic Action policy")
    fighter=config["fighter_mechanics"]
    if fighter["studied_attacks"]!={"trigger":"resolved_miss_after_hit_instead_effects","benefit":"advantage_on_next_attack_against_same_target","expiry":"end_of_next_turn"}:raise ValueError("Unsupported Studied Attacks timing policy")
    if fighter["combat_prowess"]!={"trigger":"attack_roll_miss","effect":"hit_instead","uses_per_turn":1,"reset":"start_of_next_turn","activation_policy":"optimal_after_observed_miss","eligible_after_failed_attack_roll_bonus":True}:raise ValueError("Unsupported Combat Prowess timing policy")
    expected={"scope":"per_target_discipline_cluster","objective":["aggregate_damage","primary_damage"],"decision_timing":{"action_surge_schedule":"optimize_before_outcome_resolution","pre_roll_declarations":"optimize_from_legally_observed_state","unobserved_outcome_lookahead":False,"post_roll_decisions":["combat_prowess"]}}
    if config["damage_matrix"]["optimization"]!=expected:raise ValueError("Unsupported damage optimization contract")
    feedback={"rider_conditions_and_save_outcomes":"excluded_from_damage","ally_turn_accuracy_and_damage":"excluded","modeled_self_attack_exception":"thermal_fracture_ac_reduction"}
    if config["damage_matrix"]["control_feedback"]!=feedback:raise ValueError("Unsupported damage control-feedback boundary")
    if config["kv_profile"]["attack_replacement_policy"]!="all_manifested_strikes":raise ValueError("Unsupported KV attack replacement policy")


def _kv_dpr_for_schedule(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str,cluster_size:int,action_slots:tuple[int,...])->tuple[float,float,str]:
    _validate_damage_policy_contract(model,config)
    level=target.level;profile=config["kv_profile"];psi_modifier=int(profile["psionic_ability_modifier"]);pb=model.progression("proficiency_bonus",level);strike_die=model.progression("manifested_strike_die",level);psi_pool=model.progression("psi_points",level);progression=level_config(config,level);attacks_per_action=int(progression["attacks_per_action"]);studied_enabled=bool(progression["studied_attacks"]);prowess_enabled=bool(progression["combat_prowess"]);attack_bonus=model.kv_attack_bonus(level,psi_modifier)+int(profile["archery_attack_bonus"])
    mastery=model.projection["core"]["overload"]["mastery"];hp=int(profile["hit_point_model"]["first_level_base"])+int(profile["constitution_modifier"])+(level-1)*(int(profile["hit_point_model"]["later_level_average"])+int(profile["constitution_modifier"]));blood_budget=int(hp*float(profile["blood_tax_hp_fraction"]));mastery_uses=int(mastery["uses_per_rest"]) if level>=int(mastery["minimum_level"]) else 0
    exclusions={item["entity_id"] for item in config["damage_matrix"]["excluded_stateful_features"]}
    for entity_id in exclusions:
        feature=model.features.get(entity_id)
        if feature is None or feature.get("damage_timing")!="start_of_affected_turn_after_repeat_save":raise ValueError(f"Damage exclusion {entity_id} lacks the required canonical stateful timing")
    tier_minimum={int(row["tier"]):int(row["minimum_level"]) for row in model.projection["progressions"]["tier_minimum_levels"]};packages=[Package(None,0,0,0)]
    for rule in model.features.values():
        if discipline_id not in rule["discipline_ids"] or rule["damage_delivery"]!="on_hit_rider" or level<int(rule["minimum_level"]):continue
        if profile["advanced_training_policy"]=="disabled" and rule["selectable_advanced_training"]:continue
        if rule.get("requires_additional_target") and cluster_size<2:continue
        for tier_row in rule["damage_tiers"]:
            tier=int(tier_row["tier"])
            if level>=tier_minimum[tier]:packages.append(Package(rule["entity_id"],tier,int(rule["psi_cost"]),model.blood_tax(level,tier)))
    package_tuple=tuple(packages);rider_values={package:_rider_values(model,target,discipline_id,cluster_size,level,pb,psi_modifier,strike_die,package) for package in package_tuple};strike_options=_strike_packet_options(model,target,discipline_id,level,psi_modifier,strike_die)
    standalones_by_round=[]
    for round_index in range(len(action_slots)):
        standalones=[]
        for rule in model.features.values():
            if rule["entity_id"] in exclusions or discipline_id not in rule["discipline_ids"] or rule["damage_delivery"]!="standalone" or level<int(rule["minimum_level"]):continue
            if profile["advanced_training_policy"]=="disabled" and rule["selectable_advanced_training"]:continue
            if rule.get("requires_additional_target") and cluster_size<2:continue
            for tier_row in rule["damage_tiers"]:
                tier=int(tier_row["tier"])
                if level<tier_minimum[tier]:continue
                package=Package(rule["entity_id"],tier,int(rule["psi_cost"]),model.blood_tax(level,tier));primary,aggregate=_rider_values(model,target,discipline_id,cluster_size,level,pb,psi_modifier,strike_die,package)
                if rule.get("damage_repetition")=="remaining_round_starts":repetitions=max(0,int(config["methodology"]["rounds"])-1-round_index);primary*=repetitions;aggregate*=repetitions
                standalones.append(Standalone(rule["entity_id"],tier,package.psi,package.blood,primary,aggregate,bool(rule.get("starts_persistent_zone"))))
        standalones_by_round.append(tuple(standalones))
    standalone_limit=int(model.projection["core"]["action_economy"]["standalone_psionic_action_limit_per_turn"]);apex_packet=_psionic_apex_packet(model,target,discipline_id,level);planner=_KVDamagePlanner(model,target,package_tuple,rider_values,strike_options,tuple(standalones_by_round),attack_bonus,attacks_per_action,action_slots,studied_enabled,prowess_enabled,psi_pool,blood_budget,mastery,mastery_uses,standalone_limit,apex_packet)
    score=planner.solve();selection=planner.selection();planner.clear()
    return score.primary/len(action_slots),score.aggregate/len(action_slots),selection


def _kv_dpr(model:AuthorityModel,config:dict[str,Any],target:Target,discipline_id:str,cluster_size:int)->tuple[float,float,str,tuple[int,...]]:
    best:tuple[float,float,str,tuple[int,...]]|None=None
    for schedule in _fighter_schedules(config,target.level):
        primary,aggregate,selection=_kv_dpr_for_schedule(model,config,target,discipline_id,cluster_size,schedule)
        candidate=(primary,aggregate,selection,schedule)
        if best is None or (aggregate,primary)>(best[1],best[0]):best=candidate
    if best is None:raise RuntimeError("No legal Kinetic Vanguard Action Surge schedule")
    return best

def _die_distribution(count:int,sides:int,minimum:int|None=None)->dict[int,float]:
    distribution={0:1.0}
    faces=[max(face,minimum) if minimum is not None else face for face in range(1,sides+1)]
    for _ in range(count):
        next_distribution:dict[int,float]=defaultdict(float)
        for subtotal,probability in distribution.items():
            for face in faces:next_distribution[subtotal+face]+=probability/sides
        distribution=dict(next_distribution)
    return distribution


def _profile_damage(target:Target,damage_type:str,value:int)->int:
    damage_type=damage_type.lower()
    if damage_type in target.damage_immunities:return 0
    resistant=damage_type in target.damage_resistances
    vulnerable=damage_type in target.damage_vulnerabilities
    if resistant and vulnerable:return value
    if resistant:return value//2
    if vulnerable:return value*2
    return value


def _expected_packet(target:Target,damage_type:str,dice:list[tuple[int,int,int|None]],flat:int=0)->float:
    distribution={0:1.0}
    for count,sides,minimum in dice:
        die_distribution=_die_distribution(count,sides,minimum)
        next_distribution:dict[int,float]=defaultdict(float)
        for subtotal,probability in distribution.items():
            for roll,roll_probability in die_distribution.items():next_distribution[subtotal+roll]+=probability*roll_probability
        distribution=dict(next_distribution)
    return sum(probability*_profile_damage(target,damage_type,subtotal+flat) for subtotal,probability in distribution.items())


@lru_cache(maxsize=2)
def _natural_probabilities(advantage:bool)->dict[int,float]:
    if not advantage:return {natural:0.05 for natural in range(1,21)}
    values:dict[int,float]=defaultdict(float)
    for first in range(1,21):
        for second in range(1,21):values[max(first,second)]+=1/400
    return dict(values)


def _eldritch_knight_result(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target,cluster_size:int)->_ScheduledScore:
    policy=row["tactical_policy"];expected_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","decision_information":"observed_state_only","preparation_choice":"fixed_before_target_and_cluster","spell_choice_timing":"before_resolution","bonus_action_ledger":"one_shared_per_turn","concentration_ledger":"one_active_spell"}
    if policy!=expected_policy:raise ValueError("Unsupported Eldritch Knight tactical policy")
    results=[]
    for schedule in _fighter_schedules(config,target.level):
        planner=EKDamagePlanner(row,target,level_config(config,target.level),model.progression("proficiency_bonus",target.level),cluster_size,schedule)
        try:results.append((planner.solve(),schedule))
        finally:planner.clear()
    if not results:raise RuntimeError("No legal Eldritch Knight Action Surge schedule")
    primary_score,primary_schedule=max(results,key=lambda item:item[0].primary)
    aggregate_score,aggregate_schedule=max(results,key=lambda item:item[0].aggregate)
    return _ScheduledScore(_Score(primary_score.primary,aggregate_score.aggregate),primary_schedule,aggregate_schedule)


def _eldritch_knight_score(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target,cluster_size:int)->_Score:
    return _eldritch_knight_result(model,config,row,target,cluster_size).score


def _battle_master_damage(row:dict[str,Any],target:Target,pb:int,level:int,critical:bool,maneuver_sides:int,part_of_action:bool)->float:
    weapon=row["weapon"];weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(level)]);ability=int(row["ability_modifier"]);dice=[(int(weapon["count"])*(2 if critical else 1),int(weapon["sides"]),3 if weapon["great_weapon_fighting"] else None)]
    if maneuver_sides:dice.append((2 if critical else 1,maneuver_sides,None))
    gwm_bonus=pb if row["great_weapon_master_attack_action_bonus"]=="proficiency_bonus" and part_of_action else 0
    return _expected_packet(target,weapon["damage_type"],dice,ability+weapon_bonus+gwm_bonus)


def _battle_master_dpr_for_schedule(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target,action_slots_by_round:tuple[int,...])->float:
    policy=row["tactical_policy"];expected_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","maneuver_choice_timing":"pre_roll_feint_or_post_roll_observed_result","decision_information":"observed_state_only","on_hit_die_effect":"damage","on_miss_die_effect":"attack_roll_bonus","maneuver_die_consumption":"on_use_before_die_result","maximum_maneuver_dice_per_attack":1,"feint_choice_timing":"before_attack_roll","feint_resource_timing":"before_attack_roll","feint_effect":"advantage_next_attack_same_target_same_turn_and_die_damage_on_hit","bonus_action_ledger":"one_per_turn_shared_by_feint_and_hew","relentless_die_options":"same_as_superiority_die","relentless_uses_per_turn":1,"relentless_superiority_pool_cost":0,"relentless_refresh":"start_of_next_turn","hew_choice_timing":"after_observed_critical"}
    if policy!=expected_policy:raise ValueError("Unsupported Battle Master tactical policy")
    level=target.level;progression=level_config(config,level);pb=model.progression("proficiency_bonus",level);studied_enabled=bool(progression["studied_attacks"]);prowess_enabled=bool(progression["combat_prowess"]);attacks=int(progression["attacks_per_action"]);relentless_per_turn=int(policy["relentless_uses_per_turn"]) if level>=int(row["relentless_minimum_level"]) else 0;relentless_pool_cost=int(policy["relentless_superiority_pool_cost"]);hew_enabled=bool(row["hew_critical_bonus_attack_once_per_round"]);pool=int(row["superiority_pool_by_level"][str(level)]);prowess_after_failed_bonus=bool(config["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"])
    known=set(row["known_maneuvers_by_level"][str(level)]);feint_enabled="feinting_attack" in known;precision_enabled="precision_attack" in known;generic_on_hit_enabled=bool(known&{"disarming_attack","distracting_strike","goading_attack","maneuvering_attack","menacing_attack","pushing_attack","trip_attack"})
    attacks_by_round=tuple(int(actions)*attacks for actions in action_slots_by_round);weapon=row["weapon"];weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(level)]);ability=int(row["ability_modifier"]);attack_bonus=ability+pb+weapon_bonus;superiority_sides=int(row["superiority_die_by_level"][str(level)]);relentless_sides=int(row["relentless_die"]);graze=float(_profile_damage(target,weapon["damage_type"],int(row["graze_damage"])))

    @lru_cache(maxsize=None)
    def attack_damage(critical:bool,maneuver_sides:int,part_of_action:bool)->float:
        return _battle_master_damage(row,target,pb,level,critical,maneuver_sides,part_of_action)

    @lru_cache(maxsize=None)
    def optimize(round_index:int,attacks_remaining:int,studied:bool,superiority:int,prowess:bool,relentless:int,bonus_action:bool)->float:
        if attacks_remaining==0:
            if round_index+1==len(attacks_by_round):return 0.0
            return optimize(round_index+1,attacks_by_round[round_index+1],studied,superiority,prowess_enabled,relentless_per_turn,True)
        choices=[attack_value(round_index,attacks_remaining-1,studied,superiority,prowess,relentless,bonus_action,True,False,0)]
        if feint_enabled and bonus_action:
            if relentless:choices.append(attack_value(round_index,attacks_remaining-1,studied,superiority-relentless_pool_cost,prowess,relentless-1,False,True,True,relentless_sides))
            if superiority:choices.append(attack_value(round_index,attacks_remaining-1,studied,superiority-1,prowess,relentless,False,True,True,superiority_sides))
        return max(choices)

    @lru_cache(maxsize=None)
    def attack_value(round_index:int,remaining_main_attacks:int,studied:bool,superiority:int,prowess:bool,relentless:int,bonus_action:bool,part_of_action:bool,advantage:bool,committed_maneuver_sides:int)->float:
        """Resolve one attack after any Feint commitment, then choose only legal observed-result options."""
        maneuver_committed=committed_maneuver_sides>0
        def future(hit:bool,next_superiority:int,next_prowess:bool,next_relentless:int,next_bonus_action:bool,critical:bool)->float:
            next_studied=(not hit) if studied_enabled else False
            continuation=optimize(round_index,remaining_main_attacks,next_studied,next_superiority,next_prowess,next_relentless,next_bonus_action)
            if part_of_action and critical and hew_enabled and next_bonus_action:
                bonus=attack_value(round_index,remaining_main_attacks,next_studied,next_superiority,next_prowess,next_relentless,False,False,False,0)
                return max(continuation,bonus)
            return continuation
        def failed_precision(next_superiority:int,next_relentless:int)->float:
            outcomes=[graze+future(False,next_superiority,prowess,next_relentless,bonus_action,False)]
            if prowess and prowess_after_failed_bonus:outcomes.append(attack_damage(False,0,part_of_action)+future(True,next_superiority,False,next_relentless,bonus_action,False))
            return max(outcomes)
        expected=0.0
        for natural,natural_probability in _natural_probabilities(advantage or (studied_enabled and studied)).items():
            critical=natural==20;hit=critical or (natural!=1 and natural+attack_bonus>=target.ac);choices=[]
            if hit:
                choices.append(attack_damage(critical,committed_maneuver_sides,part_of_action)+future(True,superiority,prowess,relentless,bonus_action,critical))
                if not maneuver_committed and generic_on_hit_enabled:
                    if relentless:choices.append(attack_damage(critical,relentless_sides,part_of_action)+future(True,superiority-relentless_pool_cost,prowess,relentless-1,bonus_action,critical))
                    if superiority:choices.append(attack_damage(critical,superiority_sides,part_of_action)+future(True,superiority-1,prowess,relentless,bonus_action,critical))
            else:
                choices.append(graze+future(False,superiority,prowess,relentless,bonus_action,False));required=target.ac-(natural+attack_bonus)
                if not maneuver_committed and precision_enabled and natural!=1 and 1<=required<=relentless_sides and relentless:
                    success=(relentless_sides-required+1)/relentless_sides
                    choices.append(success*(attack_damage(False,0,part_of_action)+future(True,superiority-relentless_pool_cost,prowess,relentless-1,bonus_action,False))+(1-success)*failed_precision(superiority-relentless_pool_cost,relentless-1))
                if not maneuver_committed and precision_enabled and natural!=1 and 1<=required<=superiority_sides and superiority:
                    success=(superiority_sides-required+1)/superiority_sides
                    choices.append(success*(attack_damage(False,0,part_of_action)+future(True,superiority-1,prowess,relentless,bonus_action,False))+(1-success)*failed_precision(superiority-1,relentless))
                if prowess:
                    choices.append(attack_damage(False,committed_maneuver_sides,part_of_action)+future(True,superiority,False,relentless,bonus_action,False))
                    if not maneuver_committed and generic_on_hit_enabled:
                        if relentless:choices.append(attack_damage(False,relentless_sides,part_of_action)+future(True,superiority-relentless_pool_cost,False,relentless-1,bonus_action,False))
                        if superiority:choices.append(attack_damage(False,superiority_sides,part_of_action)+future(True,superiority-1,False,relentless,bonus_action,False))
            expected+=natural_probability*max(choices)
        return expected
    return optimize(0,attacks_by_round[0],False,pool,prowess_enabled,relentless_per_turn,True)/float(config["methodology"]["rounds"])


def _battle_master_result(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target)->_ScheduledScore:
    results=[(_battle_master_dpr_for_schedule(model,config,row,target,schedule),schedule) for schedule in _fighter_schedules(config,target.level)]
    if not results:raise RuntimeError("No legal Battle Master Action Surge schedule")
    value,schedule=max(results,key=lambda item:item[0])
    return _ScheduledScore(_Score(value,value),schedule,schedule)


def _battle_master_dpr(model:AuthorityModel,config:dict[str,Any],row:dict[str,Any],target:Target)->float:
    return _battle_master_result(model,config,row,target).score.primary


def _comparator_score(model:AuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:Target,comparator_id:str,cluster_size:int)->_Score:
    row=comparators["damage"][comparator_id]
    if comparator_id=="eldritch_knight":return _eldritch_knight_score(model,config,row,target,cluster_size)
    value=_battle_master_dpr(model,config,row,target);return _Score(value,value)


def _comparator_dpr(model:AuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:Target,comparator_id:str)->float:
    return _comparator_score(model,config,comparators,target,comparator_id,1).primary


def _discipline_damage_rows(arguments:tuple[AuthorityModel,dict[str,Any],Target,str,list[int],dict[int,_ScheduledScore],_ScheduledScore])->list[dict[str,Any]]:
    model,config,target,discipline,clusters,ek_by_cluster,bm=arguments;kv_cache={};detail=[]
    for cluster in clusters:
        signature=_cluster_signature(model,config,discipline,target.level,int(cluster))
        if signature not in kv_cache:kv_cache[signature]=_kv_dpr(model,config,target,discipline,int(cluster))
        primary,aggregate,selection,kv_schedule=kv_cache[signature];ek=ek_by_cluster[int(cluster)];detail.append({"Level":target.level,"Target":target.name,"Discipline":discipline,"Cluster Size":cluster,"KV Primary DPR":primary,"KV Aggregate DPR":aggregate,"Eldritch Knight Primary DPR":ek.score.primary,"Eldritch Knight Aggregate DPR":ek.score.aggregate,"Battle Master DPR":bm.score.primary,"KV Action Slots":_schedule_label(kv_schedule),"Eldritch Knight Primary Action Slots":_schedule_label(ek.primary_schedule),"Eldritch Knight Aggregate Action Slots":_schedule_label(ek.aggregate_schedule),"Battle Master Action Slots":_schedule_label(bm.primary_schedule),"Selection":selection})
    return detail


def _target_comparator_results(arguments:tuple[AuthorityModel,dict[str,Any],dict[str,Any],Target,list[int]])->tuple[Target,dict[int,_ScheduledScore],_ScheduledScore]:
    model,config,comparators,target,clusters=arguments
    ek={cluster:_eldritch_knight_result(model,config,comparators["damage"]["eldritch_knight"],target,cluster) for cluster in clusters}
    bm=_battle_master_result(model,config,comparators["damage"]["battle_master"],target)
    return target,ek,bm


def run(authority:Path,output_dir:Path,levels:set[int],target_limit:int|None,write_detail:bool=True,write_headline:bool=True,workers:int=1,profile:str=DEFAULT_PROFILE)->dict[str,Any]:
    model=AuthorityModel.load(authority);config=load_config();comparators=load_comparators();targets=load_targets(profile=profile,levels=levels,limit=target_limit);clusters=config["methodology"]["cluster_sizes"]
    cluster_values=[int(cluster) for cluster in clusters];comparator_arguments=[(model,config,comparators,target,cluster_values) for target in targets]
    if workers==1:
        comparator_results=map(_target_comparator_results,comparator_arguments)
        arguments=[(model,config,target,discipline,cluster_values,ek,bm) for target,ek,bm in comparator_results for discipline in model.disciplines]
        discipline_rows=map(_discipline_damage_rows,arguments)
        detail=[row for rows in discipline_rows for row in rows]
    else:
        with ProcessPoolExecutor(max_workers=workers,max_tasks_per_child=1) as executor:
            comparator_results=executor.map(_target_comparator_results,comparator_arguments)
            arguments=[(model,config,target,discipline,cluster_values,ek,bm) for target,ek,bm in comparator_results for discipline in model.disciplines]
            discipline_rows=executor.map(_discipline_damage_rows,arguments)
            detail=[row for rows in discipline_rows for row in rows]
    slug=model.rules_version.replace(".","-");output_dir.mkdir(parents=True,exist_ok=True)
    source_columns={"Rules Version":model.rules_version,"Authority SHA-256":model.authority_sha256,"Catalog SHA-256":file_sha256(DEFAULT_CATALOG),"Roster SHA-256":file_sha256(DEFAULT_ROSTERS),"Target Profile":profile,"Config SHA-256":file_sha256(DEFAULT_CONFIG),"Comparator Config SHA-256":file_sha256(DEFAULT_COMPARATORS),**NOTICE_COLUMNS}
    if write_detail:
        detail_rows=[{**row,**source_columns} for row in detail]
        with (output_dir/f"kv-{slug}-damage-detail.csv").open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(detail_rows[0]));writer.writeheader();writer.writerows(detail_rows)
    groups:dict[tuple[int,str,int],list[dict[str,Any]]]=defaultdict(list)
    for row in detail:groups[(int(row["Level"]),str(row["Discipline"]),int(row["Cluster Size"]))].append(row)
    rows=[]
    for (level,discipline,cluster),values in sorted(groups.items()):
        for scope,field,ek_field in (("primary-target DPR","KV Primary DPR","Eldritch Knight Primary DPR"),("aggregate cluster DPR","KV Aggregate DPR","Eldritch Knight Aggregate DPR")):
            mean=lambda key:sum(float(item[key]) for item in values)/len(values)
            rows.append(matrix_row({"Level":level,"Discipline":discipline,"Cluster Size":cluster,"Damage Scope":scope,"Profile":config["kv_profile"]["id"]},mean(field),mean(ek_field),mean("Battle Master DPR"),"damage"))
    provenance={"rules_version":model.rules_version,"authority_sha256":model.authority_sha256,"catalog_sha256":file_sha256(DEFAULT_CATALOG),"roster_sha256":file_sha256(DEFAULT_ROSTERS),"target_profile":profile,"config_sha256":file_sha256(DEFAULT_CONFIG),"comparator_config_sha256":file_sha256(DEFAULT_COMPARATORS),"evaluator":"exact_analytical_enumeration","aggregation":"equal-weight roster means; percentages from displayed aggregates"}
    paths=write_matrix(output_dir,model.rules_version,"damage",rows,provenance) if write_headline else {}
    return {"rules_version":model.rules_version,"detail_rows":len(detail),"matrix_rows":len(rows),"paths":paths}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--authority",type=Path,default=DEFAULT_AUTHORITY);parser.add_argument("--output-dir",type=Path,required=True);parser.add_argument("--profile",choices=tuple(PROFILE_COUNTS),default=DEFAULT_PROFILE);parser.add_argument("--levels",default="7,11,15,20");parser.add_argument("--target-limit",type=int);parser.add_argument("--workers",type=int,default=1);parser.add_argument("--validate-only",action="store_true");parser.add_argument("--matrix-only",action="store_true");parser.add_argument("--no-matrix",action="store_true");args=parser.parse_args()
    model=AuthorityModel.load(args.authority)
    if args.validate_only:load_config();load_comparators();load_targets(profile=args.profile);print(f"Validated Kinetic Vanguard {model.rules_version} authority {model.authority_sha256}, target profile {args.profile}, and isolated comparator config");return
    levels={int(value) for value in args.levels.split(",")}
    if args.workers<=0 or (args.target_limit is not None and args.target_limit<=0):parser.error("--workers and --target-limit must be positive")
    result=run(args.authority,args.output_dir,levels,args.target_limit,not args.matrix_only,not args.no_matrix,args.workers,args.profile);print(f"Damage harness wrote {result['detail_rows']} detail rows and {result['matrix_rows']} matrix rows for rules {result['rules_version']}")


if __name__=="__main__":main()
