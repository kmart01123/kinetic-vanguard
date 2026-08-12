"""YAML-driven damage benchmark with BM/EK headline matrices."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

from .authority import DamageAuthorityModel,DEFAULT_AUTHORITY
from .creature_catalog import (
    ROSTER_CONTRACT_VERSION,
    CONSUMER_REQUIREMENTS_VERSION,
    RosterEntry,
    load_catalog,
    load_consumer_requirements,
    load_profile,
)
from .creature_damage_projection import (
    DAMAGE_PROJECTION_ID,
    DAMAGE_PROJECTION_VERSION,
    DamageTarget,
    project_damage_target,
)
from .damage_report import NOTICE_COLUMNS,damage_matrix_row,provenance_columns,write_damage_matrix
from .model import DEFAULT_COMPARATORS,DEFAULT_CONFIG,file_sha256,level_config,load_comparators,load_config,save_success_probability


DAMAGE_RESULT_CONTRACT_VERSION = "2.0.0"
DAMAGE_EVALUATOR_ID = "exact_analytical_enumeration"
RUN_MANIFEST_FILENAME = "run-manifest.json"
DAMAGE_EVALUATOR_IMPLEMENTATION_PATHS = (
    ("harness/authority.py", Path(__file__).with_name("authority.py")),
    ("harness/creature_catalog.py", Path(__file__).with_name("creature_catalog.py")),
    ("harness/creature_damage_projection.py", Path(__file__).with_name("creature_damage_projection.py")),
    ("harness/damage_harness.py", Path(__file__)),
    ("harness/damage_report.py", Path(__file__).with_name("damage_report.py")),
    ("harness/model.py", Path(__file__).with_name("model.py")),
)


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
class DamageInputBundle:
    model:DamageAuthorityModel
    config:dict[str,Any]
    comparators:dict[str,Any]
    entries:tuple[RosterEntry,...]
    targets:tuple[DamageTarget,...]
    identity:dict[str,Any]


def _target_count(rule:dict[str,Any],tier:int,cluster_size:int,pb:int)->int:
    target=next((item for item in rule.get("targeting_by_tier",[]) if int(item["tier"])==tier),None)
    if target is None:return 1
    kind=target["kind"]
    additional=int(target.get("additional_targets",0)) if kind=="fixed_additional" else pb if kind=="proficiency_bonus_additional" else cluster_size-1
    return 1+min(max(0,cluster_size-1),additional)


def _cluster_signature(model:DamageAuthorityModel,config:dict[str,Any],discipline_id:str,level:int,cluster_size:int)->tuple[tuple[str,int,int],...]:
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


def _rule_damage(target:DamageTarget,damage:dict[str,Any],damage_type:str,strike_die:int,psi_modifier:int,save_probability:float|None,ignore_resistance:bool=False)->float:
    distribution=_raw_distribution(damage,strike_die,psi_modifier)
    def profiled(value:int)->int:
        return _profile_damage(target,damage_type,value,ignore_resistance)
    full=sum(probability*profiled(value) for value,probability in distribution.items());resolution=damage["resolution"]
    if resolution=="always":return full
    if save_probability is None:raise ValueError("Save-gated damage lacks a canonical save")
    if resolution=="failed_save":return (1-save_probability)*full
    if resolution=="half_on_success":
        half=sum(probability*profiled(value//2) for value,probability in distribution.items())
        return (1-save_probability)*full+save_probability*half
    raise ValueError(f"Unsupported damage resolution: {resolution}")


def _strike_packet_options(model:DamageAuthorityModel,target:DamageTarget,discipline_id:str,level:int,psi_modifier:int,strike_die:int)->tuple[tuple[str,tuple[float,float,float]],...]:
    """Return every undominated pre-roll Manifested Strike damage-type declaration."""
    discipline=model.disciplines[discipline_id];core=model.projection["core"]["manifested_strike"];normal_type=discipline["damage_type"];force_type=core["holdout_damage_type"];divisor=int(core["holdout_damage_divisor"])
    def packets(damage_type:str,holdout:bool)->tuple[float,float,float]:
        def expected(count:int)->float:
            return sum(probability*_profile_damage(target,damage_type,(roll+psi_modifier)//divisor if holdout else roll+psi_modifier) for roll,probability in _die_distribution(count,strike_die).items())
        graze=float(_profile_damage(target,damage_type,psi_modifier//divisor if holdout else psi_modifier)) if discipline.get("graze_damage")=="psionic_ability_modifier" else 0.0
        return graze,expected(1),expected(int(core["critical_dice_multiplier"]))
    normal=packets(normal_type,False);holdout=packets(force_type,True)
    if all(left>=right for left,right in zip(normal,holdout)):return (("normal",normal),)
    if all(left>=right for left,right in zip(holdout,normal)):return (("holdout",holdout),)
    return (("normal",normal),("holdout",holdout))


def _rider_values(model:DamageAuthorityModel,target:DamageTarget,discipline_id:str,cluster_size:int,level:int,pb:int,psi_modifier:int,strike_die:int,package:Package)->tuple[float,float]:
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

    def __init__(self,model:DamageAuthorityModel,target:DamageTarget,packages:tuple[Package,...],rider_values:dict[Package,tuple[float,float]],strike_options:tuple[tuple[str,tuple[float,float,float]],...],standalones_by_round:tuple[tuple[Standalone,...],...],attack_bonus:int,attacks_per_action:int,action_slots_by_round:tuple[int,...],studied_enabled:bool,prowess_enabled:bool,psi_pool:int,blood_budget:int,mastery:dict[str,Any],mastery_uses:int,standalone_limit:int)->None:
        self.model=model;self.target=target;self.packages=packages;self.rider_values=rider_values;self.strike_options=strike_options;self.standalones_by_round=standalones_by_round;self.attack_bonus=attack_bonus;self.attacks_per_action=attacks_per_action;self.action_slots_by_round=action_slots_by_round;self.studied_enabled=studied_enabled;self.prowess_enabled=prowess_enabled;self.psi_pool=psi_pool;self.blood_budget=blood_budget;self.mastery=mastery;self.mastery_uses=mastery_uses;self.standalone_limit=standalone_limit
        limited=sorted({str(package.entity_id) for package in packages if package.entity_id and model.features[package.entity_id]["repeatability"]=="once_per_attack_action"});bits={entity_id:1<<index for index,entity_id in enumerate(limited)}
        self.package_bits=tuple(bits.get(package.entity_id,0) for package in packages);self.fractures=tuple(_fracture(model.features[package.entity_id],package.tier) if package.entity_id else 0 for package in packages);self.tier_two_limit=int(model.projection["core"]["overload"]["tier_two_limit_per_attack_action"]);self._roll_probability_cache={}

    @staticmethod
    def _better(candidate:_Decision,best:_Decision|None)->bool:
        return best is None or (candidate.score.aggregate,candidate.score.primary)>(best.score.aggregate,best.score.primary)

    def _mastered_tax(self,tax:int)->int:
        return max(int(self.mastery["minimum_per_overload"]),tax//int(self.mastery["blood_tax_divisor"]))

    def _payment_options(self,tax:int,mastery_remaining:int,mastery_mode:int)->tuple[tuple[int,int,int,bool],...]:
        if tax==0:return ((0,mastery_remaining,mastery_mode,False),)
        if mastery_mode==1:return ((self._mastered_tax(tax),mastery_remaining,1,False),)
        raw=(tax,mastery_remaining,2,False)
        if mastery_mode==0 and mastery_remaining:return (raw,(self._mastered_tax(tax),mastery_remaining-1,1,True))
        return (raw,)

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
        attack=self._attacks(round_index,action_slots_left-1,self.attacks_per_action,0,0,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
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

    def _roll_options(self,package_index:int,strike_index:int,outcome:str,prowess:bool,ac_reduction:int)->tuple[tuple[str,bool,bool,int,float,float],...]:
        package=self.packages[package_index];strike=self.strike_options[strike_index][1];rider_primary,rider_aggregate=self.rider_values[package];fracture=self.fractures[package_index]
        if outcome!="miss":
            packet=strike[2 if outcome=="critical" else 1]
            return ((outcome,False,prowess,max(ac_reduction,fracture),packet+rider_primary,packet+rider_aggregate),)
        options=[("miss",self.studied_enabled,prowess,ac_reduction,strike[0],strike[0])]
        if prowess:options.append(("prowess",False,False,max(ac_reduction,fracture),strike[1]+rider_primary,strike[1]+rider_aggregate))
        return tuple(options)

    def _resolve_attack_roll(self,round_index:int,action_slots_after:int,attacks_left_after:int,used_mask:int,tier_twos:int,package_index:int,strike_index:int,outcome:str,prowess:bool,ac_reduction:int,psi:int,blood:int,mastery_remaining:int,mastery_mode:int,zone_active:bool,standalone_count:int)->_Decision:
        best=None
        for resolution,next_studied,next_prowess,next_reduction,primary,aggregate in self._roll_options(package_index,strike_index,outcome,prowess,ac_reduction):
            continuation=self._attacks(round_index,action_slots_after,attacks_left_after,used_mask,tier_twos,next_studied,next_prowess,next_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
            candidate=_Decision(_Score(primary+continuation.score.primary,aggregate+continuation.score.aggregate),(resolution,next_studied,next_prowess,next_reduction,primary,aggregate))
            if self._better(candidate,best):best=candidate
        if best is None:raise RuntimeError("No legal roll resolution")
        return best

    @lru_cache(maxsize=None)
    def _attacks(self,round_index:int,action_slots_after:int,attacks_left:int,used_mask:int,tier_twos:int,studied:bool,prowess:bool,ac_reduction:int,psi:int,blood:int,mastery_remaining:int,mastery_mode:int,zone_active:bool,standalone_count:int)->_Decision:
        if attacks_left==0:
            continuation=self._actions(round_index,action_slots_after,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count,True)
            return _Decision(continuation.score,("end_attack_action",))
        best=None
        for package_index,package in enumerate(self.packages):
            bit=self.package_bits[package_index]
            if bit and used_mask&bit:continue
            next_tier_twos=tier_twos+int(package.tier==2)
            if next_tier_twos>self.tier_two_limit:continue
            next_psi=psi+package.psi
            if next_psi>self.psi_pool:continue
            next_mask=used_mask|bit
            for strike_index,_ in enumerate(self.strike_options):
                for tax,next_mastery,next_mode,activated in self._payment_options(package.blood,mastery_remaining,mastery_mode):
                    next_blood=blood+tax
                    if next_blood>self.blood_budget:continue
                    primary=aggregate=0.0
                    for outcome,probability in self._roll_probabilities(studied,ac_reduction):
                        resolution=self._resolve_attack_roll(round_index,action_slots_after,attacks_left-1,next_mask,next_tier_twos,package_index,strike_index,outcome,prowess,ac_reduction,next_psi,next_blood,next_mastery,next_mode,zone_active,standalone_count)
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
                labels=[];used_mask=tier_twos=0
                for attacks_left in range(self.attacks_per_action,0,-1):
                    declaration=self._attacks(round_index,slots-1,attacks_left,used_mask,tier_twos,studied,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
                    _,package_index,strike_index,tax,mastery_remaining,mastery_mode,activated=declaration.choice;package=self.packages[package_index];psi+=package.psi;blood+=tax;used_mask|=self.package_bits[package_index];tier_twos+=int(package.tier==2);mastery_activated=mastery_activated or activated
                    grouped:dict[tuple[Any,...],float]=defaultdict(float)
                    for outcome,probability in self._roll_probabilities(studied,ac_reduction):
                        resolution=self._resolve_attack_roll(round_index,slots-1,attacks_left-1,used_mask,tier_twos,package_index,strike_index,outcome,prowess,ac_reduction,psi,blood,mastery_remaining,mastery_mode,zone_active,standalone_count)
                        grouped[resolution.choice]+=probability
                    resolved=sorted(grouped.items(),key=lambda item:(-item[1],repr(item[0])))[0][0];_,studied,prowess,ac_reduction,_,_=resolved
                    if package.entity_id:labels.append(f"{package.entity_id}:T{package.tier}")
                    elif self.strike_options[strike_index][0]!="normal":labels.append(f"manifested_strike@{self.strike_options[strike_index][0]}")
                entries.append("attack("+(";".join(labels) if labels else "manifested_strike")+")");attacked=True;slots-=1
            if not attacked:studied=False
            marker=";mastery" if mastery_activated else "";rounds.append(f"R{round_index+1}[{','.join(entries)}{marker}]")
        return "|".join(rounds)+"|representative=locally-modal-path|policy=observed-state-adaptive"

    def clear(self)->None:
        self._roll_probability_cache.clear();self._attacks.cache_clear();self._actions.cache_clear();self._round.cache_clear()


def _validate_damage_policy_contract(model:DamageAuthorityModel,config:dict[str,Any])->None:
    action_economy=model.projection["core"]["action_economy"]
    if action_economy!={"standalone_psionic_action_limit_per_turn":1,"action_surge_allows_additional_standalone_psionic_action":False}:raise ValueError("Unsupported canonical standalone psionic Action policy")
    fighter=config["fighter_mechanics"]
    if fighter["studied_attacks"]!={"trigger":"resolved_miss_after_hit_instead_effects","benefit":"advantage_on_next_attack_against_same_target","expiry":"end_of_next_turn"}:raise ValueError("Unsupported Studied Attacks timing policy")
    if fighter["combat_prowess"]!={"trigger":"attack_roll_miss","effect":"hit_instead","uses_per_turn":1,"reset":"start_of_next_turn","activation_policy":"optimal_after_observed_miss","eligible_after_failed_attack_roll_bonus":True}:raise ValueError("Unsupported Combat Prowess timing policy")
    expected={"scope":"per_target_discipline_cluster","objective":["aggregate_damage","primary_damage"],"decision_timing":{"pre_roll_declarations":"optimize_from_legally_observed_state","unobserved_outcome_lookahead":False,"post_roll_decisions":["combat_prowess"]}}
    if config["damage_matrix"]["optimization"]!=expected:raise ValueError("Unsupported damage optimization contract")
    boundary={"rider_conditions_and_save_outcomes":"excluded_from_damage","ally_turn_accuracy_and_damage":"excluded","modeled_self_attack_exception":"thermal_fracture_ac_reduction"}
    if config["damage_matrix"]["non_damage_effect_boundary"]!=boundary:raise ValueError("Unsupported non-damage effect boundary")
    if config["kv_profile"]["attack_replacement_policy"]!="all_manifested_strikes":raise ValueError("Unsupported KV attack replacement policy")


def _kv_dpr(model:DamageAuthorityModel,config:dict[str,Any],target:DamageTarget,level:int,discipline_id:str,cluster_size:int)->tuple[float,float,str]:
    _validate_damage_policy_contract(model,config)
    profile=config["kv_profile"];psi_modifier=int(profile["psionic_ability_modifier"]);pb=model.progression("proficiency_bonus",level);strike_die=model.progression("manifested_strike_die",level);psi_pool=model.progression("psi_points",level);progression=level_config(config,level);attacks_per_action=int(progression["attacks_per_action"]);action_slots=tuple(int(value) for value in progression["action_slots_by_round"]);studied_enabled=bool(progression["studied_attacks"]);prowess_enabled=bool(progression["combat_prowess"]);attack_bonus=model.kv_attack_bonus(level,psi_modifier)+int(profile["archery_attack_bonus"])
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
    standalone_limit=int(model.projection["core"]["action_economy"]["standalone_psionic_action_limit_per_turn"]);planner=_KVDamagePlanner(model,target,package_tuple,rider_values,strike_options,tuple(standalones_by_round),attack_bonus,attacks_per_action,action_slots,studied_enabled,prowess_enabled,psi_pool,blood_budget,mastery,mastery_uses,standalone_limit)
    score=planner.solve();selection=planner.selection();planner.clear()
    return score.primary/len(action_slots),score.aggregate/len(action_slots),selection

def _die_distribution(count:int,sides:int,minimum:int|None=None)->dict[int,float]:
    distribution={0:1.0}
    faces=[max(face,minimum) if minimum is not None else face for face in range(1,sides+1)]
    for _ in range(count):
        next_distribution:dict[int,float]=defaultdict(float)
        for subtotal,probability in distribution.items():
            for face in faces:next_distribution[subtotal+face]+=probability/sides
        distribution=dict(next_distribution)
    return distribution


def _profile_damage(target:DamageTarget,damage_type:str,value:int,ignore_resistance:bool=False)->int:
    damage_type=damage_type.lower()
    if damage_type in target.damage_immunities:return 0
    resistant=damage_type in target.damage_resistances and not ignore_resistance
    vulnerable=damage_type in target.damage_vulnerabilities
    if resistant and vulnerable:return value
    if resistant:return value//2
    if vulnerable:return value*2
    return value


def _expected_packet(target:DamageTarget,damage_type:str,dice:list[tuple[int,int,int|None]],flat:int=0)->float:
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


def _eldritch_knight_dpr(model:DamageAuthorityModel,config:dict[str,Any],row:dict[str,Any],target:DamageTarget,level:int)->float:
    policy=row["tactical_policy"];expected_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","true_strike_choice_timing":"before_attack_roll","decision_information":"observed_state_only","true_strike_use_count":"exactly_configured_per_attack_action"}
    if policy!=expected_policy:raise ValueError("Unsupported Eldritch Knight tactical policy")
    progression=level_config(config,level);pb=model.progression("proficiency_bonus",level)
    studied_enabled=bool(progression["studied_attacks"]);prowess_enabled=bool(progression["combat_prowess"]);attacks=int(progression["attacks_per_action"]);actions_by_round=tuple(int(value) for value in progression["action_slots_by_round"])
    weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(level)]);regular_ability=int(row["regular_attack_ability_modifier"]);true_ability=int(row["true_strike_ability_modifier_by_level"][str(level)])
    true_damage=row["true_strike_damage_by_level"][str(level)];true_count=int(true_damage["count"]);true_sides=int(true_damage["sides"])
    weapon=row["weapon"];weapon_count=int(weapon["count"]);weapon_sides=int(weapon["sides"]);weapon_minimum=3 if bool(weapon["great_weapon_fighting"]) else None;dueling=int(row["dueling_damage_bonus"]);true_uses=int(row["true_strike_uses_per_attack_action"])
    if true_uses>attacks:raise ValueError("True Strike uses per Attack action cannot exceed attacks per action")
    cache:dict[tuple[bool,bool],float]={}
    def expected_hit_damage(true_strike:bool,critical:bool)->float:
        key=(true_strike,critical)
        if key in cache:return cache[key]
        ability=true_ability if true_strike else regular_ability
        value=_expected_packet(target,weapon["damage_type"],[(weapon_count*(2 if critical else 1),weapon_sides,weapon_minimum)],ability+weapon_bonus+dueling)
        if true_strike:value+=_expected_packet(target,row["true_strike_damage_type"],[(true_count*(2 if critical else 1),true_sides,None)])
        cache[key]=value;return value

    @lru_cache(maxsize=None)
    def optimize(round_index:int,action_index:int,attacks_remaining:int,true_remaining:int,studied:bool,prowess:bool)->float:
        """Choose the next attack before its roll from only the currently observed state."""
        if attacks_remaining==0:
            if true_remaining:raise RuntimeError("True Strike allocation did not fit its Attack action")
            if action_index+1<actions_by_round[round_index]:return optimize(round_index,action_index+1,attacks,true_uses,studied,prowess)
            if round_index+1==len(actions_by_round):return 0.0
            return optimize(round_index+1,0,attacks,true_uses,studied,prowess_enabled)
        legal=[]
        if attacks_remaining>true_remaining:legal.append(False)
        if true_remaining:legal.append(True)
        expected_values=[]
        for true_strike in legal:
            ability=true_ability if true_strike else regular_ability;bonus=ability+pb+weapon_bonus;expected=0.0
            for natural,natural_probability in _natural_probabilities(studied_enabled and studied).items():
                critical=natural==20;hit=critical or (natural!=1 and natural+bonus>=target.ac);next_attacks=attacks_remaining-1;next_true=true_remaining-int(true_strike)
                if hit:
                    outcome=expected_hit_damage(true_strike,critical)+optimize(round_index,action_index,next_attacks,next_true,False,prowess)
                else:
                    next_studied=studied_enabled;outcomes=[optimize(round_index,action_index,next_attacks,next_true,next_studied,prowess)]
                    if prowess:outcomes.append(expected_hit_damage(true_strike,False)+optimize(round_index,action_index,next_attacks,next_true,False,False))
                    outcome=max(outcomes)
                expected+=natural_probability*outcome
            expected_values.append(expected)
        return max(expected_values)
    return optimize(0,0,attacks,true_uses,False,prowess_enabled)/3.0


def _battle_master_damage(row:dict[str,Any],target:DamageTarget,pb:int,level:int,critical:bool,maneuver_sides:int,part_of_action:bool)->float:
    weapon=row["weapon"];weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(level)]);ability=int(row["ability_modifier"]);dice=[(int(weapon["count"])*(2 if critical else 1),int(weapon["sides"]),3 if weapon["great_weapon_fighting"] else None)]
    if maneuver_sides:dice.append((2 if critical else 1,maneuver_sides,None))
    gwm_bonus=pb if row["great_weapon_master_attack_action_bonus"]=="proficiency_bonus" and part_of_action else 0
    return _expected_packet(target,weapon["damage_type"],dice,ability+weapon_bonus+gwm_bonus)


def _battle_master_dpr(model:DamageAuthorityModel,config:dict[str,Any],row:dict[str,Any],target:DamageTarget,level:int)->float:
    policy=row["tactical_policy"];expected_policy={"objective":"maximum_expected_damage_over_benchmark_horizon","maneuver_choice_timing":"after_observed_attack_roll_result","on_hit_die_effect":"damage","on_miss_die_effect":"attack_roll_bonus","maneuver_die_consumption":"on_use_before_die_result","maximum_maneuver_dice_per_attack":1,"relentless_die_options":"same_as_superiority_die","relentless_uses_per_turn":1,"relentless_superiority_pool_cost":0,"relentless_refresh":"start_of_next_turn","hew_choice_timing":"after_observed_critical"}
    if policy!=expected_policy:raise ValueError("Unsupported Battle Master tactical policy")
    progression=level_config(config,level);pb=model.progression("proficiency_bonus",level);studied_enabled=bool(progression["studied_attacks"]);prowess_enabled=bool(progression["combat_prowess"]);attacks=int(progression["attacks_per_action"]);relentless_per_turn=int(policy["relentless_uses_per_turn"]) if level>=int(row["relentless_minimum_level"]) else 0;relentless_pool_cost=int(policy["relentless_superiority_pool_cost"]);hew_enabled=bool(row["hew_critical_bonus_attack_once_per_round"]);pool=int(row["superiority_pool_by_level"][str(level)]);prowess_after_failed_bonus=bool(config["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"])
    attacks_by_round=tuple(int(actions)*attacks for actions in progression["action_slots_by_round"]);weapon=row["weapon"];weapon_bonus=int(row["magic_weapon_bonus_by_level"][str(level)]);ability=int(row["ability_modifier"]);attack_bonus=ability+pb+weapon_bonus;superiority_sides=int(row["superiority_die_by_level"][str(level)]);relentless_sides=int(row["relentless_die"]);graze=float(_profile_damage(target,weapon["damage_type"],int(row["graze_damage"])))

    @lru_cache(maxsize=None)
    def attack_damage(critical:bool,maneuver_sides:int,part_of_action:bool)->float:
        return _battle_master_damage(row,target,pb,level,critical,maneuver_sides,part_of_action)

    @lru_cache(maxsize=None)
    def optimize(round_index:int,attacks_remaining:int,studied:bool,superiority:int,prowess:bool,relentless:int,hew:bool)->float:
        if attacks_remaining==0:
            if round_index+1==len(attacks_by_round):return 0.0
            return optimize(round_index+1,attacks_by_round[round_index+1],studied,superiority,prowess_enabled,relentless_per_turn,hew_enabled)
        return attack_value(round_index,attacks_remaining-1,studied,superiority,prowess,relentless,hew,True)

    @lru_cache(maxsize=None)
    def attack_value(round_index:int,remaining_main_attacks:int,studied:bool,superiority:int,prowess:bool,relentless:int,hew:bool,part_of_action:bool)->float:
        """Choose a maneuver after this roll, then continue without seeing future rolls."""
        def future(hit:bool,next_superiority:int,next_prowess:bool,next_relentless:int,next_hew:bool,critical:bool)->float:
            next_studied=(not hit) if studied_enabled else False
            continuation=optimize(round_index,remaining_main_attacks,next_studied,next_superiority,next_prowess,next_relentless,next_hew)
            if part_of_action and critical and next_hew:
                bonus=attack_value(round_index,remaining_main_attacks,next_studied,next_superiority,next_prowess,next_relentless,False,False)
                return max(continuation,bonus)
            return continuation
        def failed_precision(next_superiority:int,next_relentless:int)->float:
            outcomes=[graze+future(False,next_superiority,prowess,next_relentless,hew,False)]
            if prowess and prowess_after_failed_bonus:outcomes.append(attack_damage(False,0,part_of_action)+future(True,next_superiority,False,next_relentless,hew,False))
            return max(outcomes)
        expected=0.0
        for natural,natural_probability in _natural_probabilities(studied_enabled and studied).items():
            critical=natural==20;hit=critical or (natural!=1 and natural+attack_bonus>=target.ac);choices=[]
            if hit:
                choices.append(attack_damage(critical,0,part_of_action)+future(True,superiority,prowess,relentless,hew,critical))
                if relentless:choices.append(attack_damage(critical,relentless_sides,part_of_action)+future(True,superiority-relentless_pool_cost,prowess,relentless-1,hew,critical))
                if superiority:choices.append(attack_damage(critical,superiority_sides,part_of_action)+future(True,superiority-1,prowess,relentless,hew,critical))
            else:
                choices.append(graze+future(False,superiority,prowess,relentless,hew,False));required=target.ac-(natural+attack_bonus)
                if natural!=1 and 1<=required<=relentless_sides and relentless:
                    success=(relentless_sides-required+1)/relentless_sides
                    choices.append(success*(attack_damage(False,0,part_of_action)+future(True,superiority-relentless_pool_cost,prowess,relentless-1,hew,False))+(1-success)*failed_precision(superiority-relentless_pool_cost,relentless-1))
                if natural!=1 and 1<=required<=superiority_sides and superiority:
                    success=(superiority_sides-required+1)/superiority_sides
                    choices.append(success*(attack_damage(False,0,part_of_action)+future(True,superiority-1,prowess,relentless,hew,False))+(1-success)*failed_precision(superiority-1,relentless))
                if prowess:
                    choices.append(attack_damage(False,0,part_of_action)+future(True,superiority,False,relentless,hew,False))
                    if relentless:choices.append(attack_damage(False,relentless_sides,part_of_action)+future(True,superiority-relentless_pool_cost,False,relentless-1,hew,False))
                    if superiority:choices.append(attack_damage(False,superiority_sides,part_of_action)+future(True,superiority-1,False,relentless,hew,False))
            expected+=natural_probability*max(choices)
        return expected
    return optimize(0,attacks_by_round[0],False,pool,prowess_enabled,relentless_per_turn,hew_enabled)/3.0


def _comparator_dpr(model:DamageAuthorityModel,config:dict[str,Any],comparators:dict[str,Any],target:DamageTarget,level:int,comparator_id:str)->float:
    row=comparators["damage"][comparator_id]
    return _battle_master_dpr(model,config,row,target,level) if comparator_id=="battle_master" else _eldritch_knight_dpr(model,config,row,target,level)


def _discipline_damage_rows(arguments:tuple[DamageAuthorityModel,dict[str,Any],RosterEntry,DamageTarget,str,list[int],float,float])->list[dict[str,Any]]:
    model,config,entry,target,discipline,clusters,ek,bm=arguments;kv_cache={};detail=[];level=entry.benchmark_level
    for cluster in clusters:
        signature=_cluster_signature(model,config,discipline,level,int(cluster))
        if signature not in kv_cache:kv_cache[signature]=_kv_dpr(model,config,target,level,discipline,int(cluster))
        primary,aggregate,selection=kv_cache[signature];detail.append({"Level":level,"Creature ID":target.creature_id,"Target":target.name,"Target Profile ID":entry.profile_id,"Target Profile SHA-256":entry.profile_sha256,"Target Weight Numerator":entry.weight.numerator,"Target Weight Denominator":entry.weight.denominator,"Discipline":discipline,"Cluster Size":cluster,"KV Primary DPR":primary,"KV Aggregate DPR":aggregate,"Eldritch Knight DPR":ek,"Battle Master DPR":bm,"Selection":selection})
    return detail


def _canonical_sha256(value:Any)->str:
    encoded=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluator_implementation_sha256(paths:tuple[tuple[str,Path],...]=DAMAGE_EVALUATOR_IMPLEMENTATION_PATHS)->str:
    """Bind every maintained Python module that can change damage results."""
    labels=[label for label,_ in paths]
    if labels!=sorted(labels) or len(labels)!=len(set(labels)):raise ValueError("Damage evaluator implementation paths must have unique sorted labels")
    return _canonical_sha256([{"path":label,"sha256":file_sha256(path)} for label,path in paths])


def _detail_scope_evidence(row:dict[str,Any])->dict[str,str]:
    evidence:dict[str,str]={}
    for prefix,value_field in (("Primary Target","KV Primary DPR"),("Aggregate Cluster","KV Aggregate DPR")):
        scope=damage_matrix_row({},float(row[value_field]),float(row["Eldritch Knight DPR"]),float(row["Battle Master DPR"]))
        for field in ("KV as % of EK","KV as % of BM","Lower Comparator","Upper Comparator","Lower Boundary","Upper Boundary","Band","Boundary Delta %"):
            evidence[f"{prefix} {field}"]=scope[field]
    return evidence


def _projection_digest(entries:list[RosterEntry],targets:list[DamageTarget])->str:
    if not entries or len(entries)!=len(targets):raise ValueError("Damage target projections must cover a non-empty active roster profile exactly")
    for entry,target in zip(entries,targets,strict=True):
        if entry.creature_id!=target.creature_id or entry.catalog_sha256!=target.catalog_sha256:raise ValueError("Damage target projections do not match active roster identities")
        target.validate_identity()
    return _canonical_sha256({"projection_id":DAMAGE_PROJECTION_ID,"projection_version":DAMAGE_PROJECTION_VERSION,"profile_id":entries[0].profile_id,"profile_sha256":entries[0].profile_sha256,"targets":[{"creature_id":entry.creature_id,"target_sha256":target.target_sha256} for entry,target in zip(entries,targets,strict=True)]})


def load_damage_input_bundle(authority:Path,levels:set[int],trials:int,seed:int)->DamageInputBundle:
    model=DamageAuthorityModel.load(authority);config=load_config();comparators=load_comparators();catalog=load_catalog();requirements=load_consumer_requirements(catalog=catalog);profile_id=str(config["methodology"]["target_profile_id"]);entries=load_profile(profile_id,levels,catalog=catalog);targets=[project_damage_target(entry.creature_id,catalog=catalog,requirements=requirements) for entry in entries]
    if any(entry.profile_id!=entries[0].profile_id or entry.profile_sha256!=entries[0].profile_sha256 or entry.roster_sha256!=entries[0].roster_sha256 for entry in entries):raise ValueError("Active target profile identities are inconsistent")
    projection_sha256=_projection_digest(entries,targets)
    identity={"damage_result_contract_version":DAMAGE_RESULT_CONTRACT_VERSION,"rules_version":model.rules_version,"authority_sha256":model.authority_sha256,"catalog_contract_version":targets[0].catalog_contract_version,"catalog_sha256":targets[0].catalog_sha256,"roster_contract_version":ROSTER_CONTRACT_VERSION,"roster_sha256":entries[0].roster_sha256,"target_profile_id":entries[0].profile_id,"target_profile_version":entries[0].profile_version,"target_profile_sha256":entries[0].profile_sha256,"damage_target_projection_id":DAMAGE_PROJECTION_ID,"damage_target_projection_version":DAMAGE_PROJECTION_VERSION,"damage_target_projection_sha256":projection_sha256,"consumer_requirements_version":CONSUMER_REQUIREMENTS_VERSION,"damage_consumer_requirements_sha256":requirements.sha256_for("damage_target"),"config_sha256":file_sha256(DEFAULT_CONFIG),"comparator_config_sha256":file_sha256(DEFAULT_COMPARATORS),"evaluator":DAMAGE_EVALUATOR_ID,"evaluator_implementation_sha256":evaluator_implementation_sha256(),"trials":trials,"seed":seed,"trial_seed_role":"historical_compatibility_metadata","aggregation":"exact rational target-profile weights; percentages from displayed aggregates","status":config["methodology"]["status"]}
    return DamageInputBundle(model,config,comparators,tuple(entries),tuple(targets),identity)


def _write_run_manifest(output_dir:Path,inputs:dict[str,Any],outputs:dict[str,Path],detail_rows:int,matrix_rows:int)->Path:
    manifest={"format_version":1,"damage_result_contract_version":DAMAGE_RESULT_CONTRACT_VERSION,"inputs":inputs,"outputs":{name:{"file":path.name,"sha256":file_sha256(path)} for name,path in sorted(outputs.items())},"row_counts":{"detail":detail_rows,"matrix":matrix_rows}}
    path=output_dir/RUN_MANIFEST_FILENAME
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return path


def run(authority:Path,output_dir:Path,levels:set[int],trials:int,seed:int,write_detail:bool=True,write_headline:bool=True,workers:int=1)->dict[str,Any]:
    inputs=load_damage_input_bundle(authority,levels,trials,seed);model=inputs.model;config=inputs.config;comparators=inputs.comparators;entries=list(inputs.entries);targets=list(inputs.targets);input_identity=inputs.identity;projection_sha256=str(input_identity["damage_target_projection_sha256"]);clusters=config["methodology"]["cluster_sizes"]
    arguments=[]
    for entry,target in zip(entries,targets,strict=True):
        level=entry.benchmark_level;ek=_comparator_dpr(model,config,comparators,target,level,"eldritch_knight");bm=_comparator_dpr(model,config,comparators,target,level,"battle_master")
        for discipline in model.disciplines:arguments.append((model,config,entry,target,discipline,[int(cluster) for cluster in clusters],ek,bm))
    if workers==1:discipline_rows=map(_discipline_damage_rows,arguments)
    else:
        with ProcessPoolExecutor(max_workers=workers,max_tasks_per_child=1) as executor:discipline_rows=executor.map(_discipline_damage_rows,arguments)
    detail=[{**row,**_detail_scope_evidence(row)} for rows in discipline_rows for row in rows]
    slug=model.rules_version.replace(".","-");output_dir.mkdir(parents=True,exist_ok=True)
    source_columns={**provenance_columns(input_identity),**NOTICE_COLUMNS}
    output_paths:dict[str,Path]={}
    if write_detail:
        detail_rows=[{**row,**source_columns} for row in detail]
        detail_path=output_dir/f"kv-{slug}-damage-detail.csv"
        with detail_path.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(detail_rows[0]));writer.writeheader();writer.writerows(detail_rows)
        output_paths["detail_csv"]=detail_path
    groups:dict[tuple[int,str,int],list[dict[str,Any]]]=defaultdict(list)
    for row in detail:groups[(int(row["Level"]),str(row["Discipline"]),int(row["Cluster Size"]))].append(row)
    rows=[]
    for (level,discipline,cluster),values in sorted(groups.items()):
        weights=[Fraction(int(item["Target Weight Numerator"]),int(item["Target Weight Denominator"])) for item in values];weight_total=sum(weights,Fraction())
        if weight_total!=1:raise ValueError(f"Active target-profile weights for level {level} do not sum to one")
        for scope,field in (("primary-target DPR","KV Primary DPR"),("aggregate cluster DPR","KV Aggregate DPR")):
            weighted=lambda key:sum(float(weight)*float(item[key]) for weight,item in zip(weights,values,strict=True))
            rows.append(damage_matrix_row({"Level":level,"Discipline":discipline,"Cluster Size":cluster,"Damage Scope":scope,"Profile":config["kv_profile"]["id"]},weighted(field),weighted("Eldritch Knight DPR"),weighted("Battle Master DPR")))
    if write_headline:
        matrix_paths=write_damage_matrix(output_dir,model.rules_version,rows,input_identity)
        output_paths.update({f"matrix_{name}":path for name,path in matrix_paths.items()})
    manifest_path=_write_run_manifest(output_dir,input_identity,output_paths,len(detail),len(rows));output_paths["manifest"]=manifest_path
    return {"rules_version":model.rules_version,"detail_rows":len(detail),"matrix_rows":len(rows),"paths":output_paths,"inputs":input_identity}


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--authority",type=Path,default=DEFAULT_AUTHORITY);parser.add_argument("--output-dir",type=Path,required=True);parser.add_argument("--levels",default="7,11,15,20");parser.add_argument("--trials",type=int);parser.add_argument("--seed",type=int);parser.add_argument("--workers",type=int,default=1);parser.add_argument("--validate-only",action="store_true");parser.add_argument("--matrix-only",action="store_true");parser.add_argument("--no-matrix",action="store_true");args=parser.parse_args()
    model=DamageAuthorityModel.load(args.authority)
    if args.validate_only:
        config=load_config();load_comparators();catalog=load_catalog();requirements=load_consumer_requirements(catalog=catalog);entries=load_profile(str(config["methodology"]["target_profile_id"]),catalog=catalog)
        for entry in entries:project_damage_target(entry.creature_id,catalog=catalog,requirements=requirements)
        print(f"Validated Kinetic Vanguard {model.rules_version} authority {model.authority_sha256}, catalog {catalog.sha256}, and {len(entries)} headline DamageTarget projections");return
    config=load_config();trials=args.trials if args.trials is not None else int(config["methodology"]["damage_default_trials"]);seed=args.seed if args.seed is not None else int(config["methodology"]["damage_seed"]);levels={int(value) for value in args.levels.split(",")}
    if trials<=0 or args.workers<=0:parser.error("--trials and --workers must be positive")
    result=run(args.authority,args.output_dir,levels,trials,seed,not args.matrix_only,not args.no_matrix,args.workers);print(f"Damage harness wrote {result['detail_rows']} detail rows and {result['matrix_rows']} matrix rows for rules {result['rules_version']}")


if __name__=="__main__":main()
