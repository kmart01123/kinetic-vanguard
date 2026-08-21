"""Compact exact finite-horizon Eldritch Knight damage planner."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass,replace
from functools import lru_cache
from typing import Any,Callable

from .model import Target,attack_probabilities,modified_save_success_probability


@dataclass(frozen=True)
class EKScore:
    primary:float=0.0
    aggregate:float=0.0

    def __add__(self,other:EKScore)->EKScore:
        return EKScore(self.primary+other.primary,self.aggregate+other.aggregate)

    def scaled(self,factor:float)->EKScore:
        return EKScore(self.primary*factor,self.aggregate*factor)


@dataclass(frozen=True)
class EKState:
    round_index:int
    actions_left:int
    studied:bool
    prowess:bool
    slots:tuple[int,int,int,int]
    bonus_available:bool
    concentration:str=""
    concentration_type:str=""
    attacked_this_turn:bool=False
    eldritch_strike:bool=False
    eldritch_strike_fresh:bool=False
    delayed_packets:tuple[tuple[str,int,int],...]=()
    ordinary_action_available:bool=True
    slotted_spell_cast_this_turn:bool=False


def _best(scores:list[EKScore])->EKScore:
    if not scores:raise RuntimeError("No legal Eldritch Knight choice")
    return EKScore(max(score.primary for score in scores),max(score.aggregate for score in scores))


@lru_cache(maxsize=None)
def _die_distribution(count:int,sides:int)->tuple[tuple[int,float],...]:
    distribution={0:1.0}
    for _ in range(count):
        next_distribution:dict[int,float]=defaultdict(float)
        for subtotal,probability in distribution.items():
            for face in range(1,sides+1):next_distribution[subtotal+face]+=probability/sides
        distribution=dict(next_distribution)
    return tuple(sorted(distribution.items()))


@lru_cache(maxsize=None)
def chromatic_orb_duplicate_probability(dice_count:int)->float:
    """Count equal-d8 tuples exactly; no sampling or average shortcut."""
    if dice_count<=0:return 0.0
    if dice_count>8:return 1.0
    distinct=1
    for offset in range(dice_count):distinct*=8-offset
    return 1-distinct/(8**dice_count)


class EKDamagePlanner:
    """Exact DP over the state required by issue #102's frozen EK package."""

    def __init__(self,row:dict[str,Any],target:Target,progression:dict[str,Any],proficiency_bonus:int,cluster_size:int,action_slots_by_round:tuple[int,...])->None:
        if cluster_size<=0:raise ValueError("Eldritch Knight cluster size must be positive")
        self.row=row;self.target=target;self.level=target.level;self.level_key=str(target.level);self.progression=progression;self.pb=proficiency_bonus;self.cluster_size=cluster_size;self.actions_by_round=tuple(int(value) for value in action_slots_by_round);self.rounds=len(self.actions_by_round)
        self.attacks=int(progression["attacks_per_action"])
        if not self.actions_by_round or any(value not in {1,2} for value in self.actions_by_round):raise ValueError("Eldritch Knight action schedule must contain one or two action slots per round")
        self.studied_enabled=bool(progression["studied_attacks"]);self.prowess_enabled=bool(progression["combat_prowess"])
        self.eldritch_strike_enabled=self.level>=int(row["eldritch_strike_minimum_level"])
        self.spells={str(spell["id"]):spell for spell in row["spells"]};self.cantrips=tuple(row["cantrips_by_level"][self.level_key]);self.prepared=tuple(row["prepared_spells_by_level"][self.level_key])
        pool=row["spell_slots_by_level"][self.level_key];self.initial_slots=tuple(int(pool[str(level)]) for level in range(1,5))
        self.spell_ability=int(row["spellcasting_ability_modifier_by_level"][self.level_key]);self.spell_attack_bonus=self.spell_ability+self.pb;self.spell_save_dc=int(row["save_dc_base"])+self.spell_attack_bonus
        self.weapon_bonus=int(row["magic_weapon_bonus_by_level"][self.level_key]);self.regular_attack_bonus=int(row["regular_attack_ability_modifier"])+self.pb+self.weapon_bonus;self.true_strike_attack_bonus=self.spell_ability+self.pb+self.weapon_bonus
        self._packet_cache:dict[tuple[int,int,int,str,bool,bool],float]={}

    def _profile(self,damage_type:str,value:int)->int:
        damage_type=damage_type.lower()
        if damage_type in self.target.damage_immunities:return 0
        resistant=damage_type in self.target.damage_resistances;vulnerable=damage_type in self.target.damage_vulnerabilities
        if resistant and vulnerable:return value
        if resistant:return value//2
        if vulnerable:return value*2
        return value

    def _packet(self,packet:dict[str,Any],damage_type:str,*,count:int|None=None,critical:bool=False,half:bool=False)->float:
        base_count=int(packet["count"] if count is None else count);flat=int(packet.get("flat",0));key=(base_count,int(packet["sides"]),flat,damage_type,critical,half)
        if key in self._packet_cache:return self._packet_cache[key]
        dice_count=base_count*(2 if critical else 1);total=0.0
        for roll,probability in _die_distribution(dice_count,int(packet["sides"])):
            value=roll+flat
            if half:value//=2
            total+=probability*self._profile(damage_type,value)
        self._packet_cache[key]=total;return total

    def _curse_packet(self,critical:bool=False)->float:
        packet=self.spells["bestow_curse"]["damage_event_bonus"]
        return self._packet(packet,self.spells["bestow_curse"]["damage_types"][0],critical=critical)

    def _damage_score(self,primary:float,aggregate:float|None=None)->EKScore:
        return EKScore(primary,primary if aggregate is None else aggregate)

    def _best_damage_type(self,damage_types:list[str])->str:
        def multiplier(damage_type:str)->int:
            value=damage_type.lower()
            if value in self.target.damage_immunities:return 0
            if value in self.target.damage_resistances and value not in self.target.damage_vulnerabilities:return 1
            if value in self.target.damage_vulnerabilities and value not in self.target.damage_resistances:return 4
            return 2
        return max(damage_types,key=multiplier)

    def _consume_slot(self,state:EKState,slot:int)->EKState:
        if state.slotted_spell_cast_this_turn:raise ValueError("Eldritch Knight already expended a spell slot to cast a spell this turn")
        if not 1<=slot<=4 or state.slots[slot-1]<=0:raise ValueError("Eldritch Knight spell slot is unavailable")
        slots=list(state.slots);slots[slot-1]-=1;return replace(state,slots=tuple(slots),slotted_spell_cast_this_turn=True)

    def _consume_action_states(self,state:EKState,*,magic:bool)->tuple[EKState,...]:
        if state.actions_left<=0:return ()
        if magic:
            if not state.ordinary_action_available:return ()
            return (replace(state,actions_left=state.actions_left-1,ordinary_action_available=False),)
        choices=[]
        if state.ordinary_action_available:choices.append(replace(state,actions_left=state.actions_left-1,ordinary_action_available=False))
        if state.actions_left>int(state.ordinary_action_available):choices.append(replace(state,actions_left=state.actions_left-1))
        return tuple(dict.fromkeys(choices))

    def _slot_options(self,state:EKState,spell:dict[str,Any])->tuple[int,...]:
        if state.slotted_spell_cast_this_turn:return ()
        minimum=int(spell["spell_level"])
        return tuple(level for level,count in enumerate(state.slots,1) if count and level>=minimum)

    def _recast_is_dominated(self,state:EKState,spell_id:str)->bool:
        return state.concentration==spell_id and spell_id in {"enlarge_reduce","bestow_curse","conjure_minor_elementals","greater_invisibility"}

    def _canonical_state(self,state:EKState,pending_casts:int=0)->EKState:
        remaining_actions=state.actions_left+sum(self.actions_by_round[state.round_index+1:])
        remaining_bonus_casts=0
        if "dragons_breath" in self.prepared:
            remaining_bonus_casts=int(state.bonus_available)+max(0,self.rounds-state.round_index-1)
        cap=remaining_actions+remaining_bonus_casts+pending_casts
        slots=tuple(min(count,cap) for count in state.slots)
        return state if slots==state.slots else replace(state,slots=slots)

    def _replace_concentration(self,state:EKState,spell_id:str="",damage_type:str="")->EKState:
        return replace(state,concentration=spell_id,concentration_type=damage_type)

    def _schedule_delayed(self,state:EKState,damage_type:str,packet:dict[str,Any])->EKState:
        event=(damage_type,int(packet["count"]),int(packet["sides"]))
        return replace(state,delayed_packets=tuple(sorted((*state.delayed_packets,event))))

    def _consume_primer(self,state:EKState)->EKState:
        return replace(state,eldritch_strike=False,eldritch_strike_fresh=False)

    def _has_primer(self,state:EKState)->bool:
        return self.eldritch_strike_enabled and state.eldritch_strike

    def _save_success(self,spell:dict[str,Any],*,primer:bool=False,repeat:bool=False)->float:
        disadvantage=bool(primer and not repeat)
        if spell.get("save_disadvantage_creature_type")==self.target.creature_type:disadvantage=True
        return modified_save_success_probability(self.target,str(spell["save"]),self.spell_save_dc,disadvantage=disadvantage)

    def _melee_invisibility_advantage(self,state:EKState)->bool:
        if state.concentration!="greater_invisibility":return False
        spell=self.spells["greater_invisibility"];distance=int(spell["melee_distance_feet"])
        for sense in spell["suppressed_by_senses"]:
            if sense=="blindsight" and self.target.blindsight_range>=distance:return False
            if sense=="truesight" and self.target.truesight_range>=distance:return False
        return True

    def _ranged_invisibility_advantage(self,state:EKState)->bool:
        if state.concentration!="greater_invisibility":return False
        spell=self.spells["greater_invisibility"]
        for sense in spell["suppressed_by_senses"]:
            if sense=="blindsight" and self.target.blindsight_range>0:return False
            if sense=="truesight" and self.target.truesight_range>0:return False
        return True

    def _attack_value(self,state:EKState,attack_bonus:int,same_primary:bool,advantage:bool,on_hit:Callable[[bool,EKState],EKScore],on_miss:Callable[[EKState],EKScore])->EKScore:
        miss_probability,hit_probability,critical_probability=attack_probabilities(attack_bonus,self.target.ac,advantage or (same_primary and self.studied_enabled and state.studied))
        hit_state=replace(state,studied=False if same_primary else state.studied,attacked_this_turn=True)
        hit=on_hit(False,hit_state);critical=on_hit(True,hit_state)
        miss_state=replace(state,studied=True if self.studied_enabled and same_primary else state.studied,attacked_this_turn=True);miss_choices=[on_miss(miss_state)]
        if state.prowess:
            prowess_state=replace(hit_state,prowess=False)
            miss_choices.append(on_hit(False,prowess_state))
        miss=_best(miss_choices)
        return miss.scaled(miss_probability)+hit.scaled(hit_probability)+critical.scaled(critical_probability)

    def _weapon_damage(self,state:EKState,true_strike:bool,critical:bool)->float:
        weapon=self.row["weapon"];ability=self.spell_ability if true_strike else int(self.row["regular_attack_ability_modifier"])
        packet={"count":int(weapon["count"]),"sides":int(weapon["sides"]),"flat":ability+self.weapon_bonus+int(self.row["dueling_damage_bonus"])}
        weapon_damage_type=str(weapon["damage_type"])
        if true_strike:
            spell=self.spells["true_strike"]
            if spell["weapon_damage_type_choice"]:weapon_damage_type=self._best_damage_type([weapon_damage_type,spell["damage_types"][0]])
        value=self._packet(packet,weapon_damage_type,critical=critical)
        if true_strike:
            packet=spell["damage_dice_by_level"][self.level_key];value+=self._packet(packet,spell["damage_types"][0],critical=critical)
        if state.concentration=="enlarge_reduce":value+=self._packet(self.spells["enlarge_reduce"]["weapon_hit_bonus"],weapon_damage_type,critical=critical)
        if state.concentration=="conjure_minor_elementals":value+=self._packet(self.spells["conjure_minor_elementals"]["weapon_hit_bonus"],state.concentration_type,critical=critical)
        if state.concentration=="bestow_curse" and value>0:value+=self._curse_packet(critical)
        return value

    def _weapon_attack(self,state:EKState,true_strike:bool,after:Callable[[EKState],EKScore])->EKScore:
        bonus=self.true_strike_attack_bonus if true_strike else self.regular_attack_bonus
        def on_hit(critical:bool,next_state:EKState)->EKScore:
            primed=replace(next_state,eldritch_strike=True,eldritch_strike_fresh=True) if self.eldritch_strike_enabled else next_state
            damage=self._weapon_damage(state,true_strike,critical)
            return self._damage_score(damage)+after(primed)
        return self._attack_value(state,bonus,True,self._melee_invisibility_advantage(state),on_hit,after)

    def _spell_attack_damage(self,state:EKState,spell:dict[str,Any],packet:dict[str,Any],damage_type:str,critical:bool)->float:
        value=self._packet(packet,damage_type,critical=critical)
        if state.concentration=="bestow_curse" and value>0:value+=self._curse_packet(critical)
        return value

    def _single_spell_attack(self,state:EKState,spell:dict[str,Any],packet:dict[str,Any],damage_type:str,after:Callable[[EKState],EKScore],*,miss_score:EKScore=EKScore(),invisibility_advantage:bool|None=None)->EKScore:
        def on_hit(critical:bool,next_state:EKState)->EKScore:
            return self._damage_score(self._spell_attack_damage(state,spell,packet,damage_type,critical))+after(next_state)
        def on_miss(next_state:EKState)->EKScore:return miss_score+after(next_state)
        advantage=self._ranged_invisibility_advantage(state) if invisibility_advantage is None else invisibility_advantage
        return self._attack_value(state,self.spell_attack_bonus,True,advantage,on_hit,on_miss)

    def _save_area_score(self,state:EKState,spell:dict[str,Any],packet:dict[str,Any],damage_type:str)->tuple[EKScore,EKState]:
        primer=self._has_primer(state);primary_success=self._save_success(spell,primer=primer);secondary_success=self._save_success(spell)
        full=self._packet(packet,damage_type);half=self._packet(packet,damage_type,half=True);zero=spell.get("save_result")=="zero"
        primary=(1-primary_success)*full+primary_success*(0.0 if zero else half);secondary=(1-secondary_success)*full+secondary_success*(0.0 if zero else half)
        curse_primary=0.0
        if state.concentration=="bestow_curse" and damage_type not in self.target.damage_immunities:
            curse_primary=self._curse_packet()*((1-primary_success) if zero else 1.0)
        return self._damage_score(primary+curse_primary,primary+curse_primary+(self.cluster_size-1)*secondary),self._consume_primer(state) if primer else state

    def _spell_packet(self,spell:dict[str,Any],slot:int)->dict[str,int]:
        if int(spell["spell_level"])==0:return spell["damage_dice_by_level"][self.level_key]
        base=spell["base_damage"];return {"count":int(base["count"])+max(0,slot-int(spell["spell_level"]))*int(spell.get("slot_damage_dice",0)),"sides":int(base["sides"])}

    def _chromatic_value(self,state:EKState,spell:dict[str,Any],slot:int,damage_type:str,target_index:int,leaps_left:int,after:Callable[[EKState],EKScore])->EKScore:
        same_primary=target_index==0;packet=self._spell_packet(spell,slot)
        def on_hit(critical:bool,next_state:EKState)->EKScore:
            count=int(packet["count"])*(2 if critical else 1);damage=self._packet(packet,damage_type,critical=critical)
            if same_primary and state.concentration=="bestow_curse" and damage>0:damage+=self._curse_packet(critical)
            continuation=after(next_state)
            if leaps_left and target_index+1<self.cluster_size:
                leap=self._chromatic_value(next_state,spell,slot,damage_type,target_index+1,leaps_left-1,after)
                probability=chromatic_orb_duplicate_probability(count);continuation=leap.scaled(probability)+continuation.scaled(1-probability)
            score=EKScore(damage,damage) if same_primary else EKScore(0.0,damage)
            return score+continuation
        return self._attack_value(state,self.spell_attack_bonus,same_primary,self._ranged_invisibility_advantage(state),on_hit,after)

    def _multiple_attacks(self,state:EKState,spell:dict[str,Any],count:int,damage_type:str,after:Callable[[EKState],EKScore])->EKScore:
        packet=spell["attack_damage"]
        def sequence(current:EKState,remaining:int)->EKScore:
            if remaining==0:return after(current)
            return self._single_spell_attack(current,spell,packet,damage_type,lambda next_state:sequence(next_state,remaining-1))
        return sequence(state,count)

    def _melf_value(self,state:EKState,spell:dict[str,Any],slot:int,after:Callable[[EKState],EKScore])->EKScore:
        extra=max(0,slot-int(spell["spell_level"]))*int(spell["slot_damage_dice_each_event"]);damage_type=spell["damage_types"][0]
        initial={"count":int(spell["initial_damage"]["count"])+extra,"sides":int(spell["initial_damage"]["sides"])};delayed={"count":int(spell["delayed_damage"]["count"])+extra,"sides":int(spell["delayed_damage"]["sides"])}
        def on_hit(critical:bool,next_state:EKState)->EKScore:
            first=self._packet(initial,damage_type,critical=critical);curse=0.0
            if state.concentration=="bestow_curse" and first>0:curse+=self._curse_packet(critical)
            return self._damage_score(first+curse)+after(self._schedule_delayed(next_state,damage_type,delayed))
        def on_miss(next_state:EKState)->EKScore:
            first=self._packet(initial,damage_type,half=True);curse=0.0
            if state.concentration=="bestow_curse" and first>0:curse=self._curse_packet()
            return self._damage_score(first+curse)+after(next_state)
        return self._attack_value(state,self.spell_attack_bonus,True,self._ranged_invisibility_advantage(state),on_hit,on_miss)

    def _vitriolic_value(self,state:EKState,spell:dict[str,Any],after:Callable[[EKState],EKScore])->EKScore:
        primer=self._has_primer(state);success=self._save_success(spell,primer=primer);secondary_success=self._save_success(spell);damage_type=spell["damage_types"][0]
        initial=spell["initial_damage"];delayed=spell["delayed_damage"];full_initial=self._packet(initial,damage_type);half_initial=self._packet(initial,damage_type,half=True);later=self._packet(delayed,damage_type)
        secondary=(1-secondary_success)*(full_initial+later)+secondary_success*half_initial;curse=self._curse_packet() if state.concentration=="bestow_curse" and damage_type not in self.target.damage_immunities else 0.0
        next_state=self._consume_primer(state) if primer else state
        failed=self._damage_score(full_initial+curse,full_initial+curse+(self.cluster_size-1)*secondary)+after(self._schedule_delayed(next_state,damage_type,delayed))
        succeeded=self._damage_score(half_initial+curse,half_initial+curse+(self.cluster_size-1)*secondary)+after(next_state)
        return failed.scaled(1-success)+succeeded.scaled(success)

    def _magic_missile_value(self,state:EKState,spell:dict[str,Any],slot:int,after:Callable[[EKState],EKScore])->EKScore:
        darts=int(spell["base_darts"])+max(0,slot-int(spell["spell_level"]))*int(spell["slot_darts"]);damage=darts*self._packet(spell["dart_damage"],spell["damage_types"][0]);curse=0.0
        if state.concentration=="bestow_curse" and damage>0:curse=self._curse_packet()
        return self._damage_score(damage+curse)+after(state)

    def _cast_value(self,state:EKState,spell_id:str,slot:int,after:Callable[[EKState],EKScore])->EKScore:
        spell=self.spells[spell_id];current=state if slot==0 else self._consume_slot(state,slot);mechanic=spell["mechanic"]
        if mechanic=="true_strike":return self._weapon_attack(current,True,after)
        if mechanic=="spell_attack":
            packet=spell["damage_dice_by_level"][self.level_key]
            return self._single_spell_attack(current,spell,packet,self._best_damage_type(spell["damage_types"]),after)
        if mechanic=="save_area":
            packet=self._spell_packet(spell,slot);damage,next_state=self._save_area_score(current,spell,packet,self._best_damage_type(spell["damage_types"]))
            return damage+after(next_state)
        if mechanic=="chromatic_orb":
            return self._chromatic_value(current,spell,slot,self._best_damage_type(spell["damage_types"]),0,min(slot,self.cluster_size-1),after)
        if mechanic=="magic_missile":return self._magic_missile_value(current,spell,slot,after)
        if mechanic=="witch_bolt":
            active=self._replace_concentration(current,"witch_bolt_pending");packet=self._spell_packet(spell,slot);damage_type=spell["damage_types"][0]
            return self._single_spell_attack(active,spell,packet,damage_type,after,invisibility_advantage=self._ranged_invisibility_advantage(current))
        if mechanic=="multiple_spell_attacks":
            count=int(spell["base_attacks"])+max(0,slot-int(spell["spell_level"]))*int(spell["slot_attacks"])
            return self._multiple_attacks(current,spell,count,spell["damage_types"][0],after)
        if mechanic=="melfs_acid_arrow":return self._melf_value(current,spell,slot,after)
        if mechanic=="self_enlarge":return after(self._replace_concentration(current,"enlarge_reduce"))
        if mechanic=="conjure_minor_elementals":return after(self._replace_concentration(current,"conjure_minor_elementals",self._best_damage_type(spell["damage_types"])))
        if mechanic=="greater_invisibility":return after(self._replace_concentration(current,"greater_invisibility"))
        if mechanic=="bestow_curse_damage":
            cleared=self._replace_concentration(current);primer=self._has_primer(cleared);success=self._save_success(spell,primer=primer);resolved=self._consume_primer(cleared) if primer else cleared
            return after(resolved).scaled(success)+after(self._replace_concentration(resolved,"bestow_curse")).scaled(1-success)
        if mechanic=="phantasmal_killer":
            cleared=self._replace_concentration(current);primer=self._has_primer(cleared);success=self._save_success(spell,primer=primer);resolved=self._consume_primer(cleared) if primer else cleared;damage_type=spell["damage_types"][0]
            full=self._packet(spell["damage"],damage_type);half=self._packet(spell["damage"],damage_type,half=True)
            ended=self._damage_score(half)+after(resolved);active=self._damage_score(full)+after(self._replace_concentration(resolved,"phantasmal_killer"))
            return ended.scaled(success)+active.scaled(1-success)
        if mechanic=="vitriolic_sphere":return self._vitriolic_value(current,spell,after)
        raise ValueError(f"Unsupported frozen Eldritch Knight spell mechanic: {mechanic}")

    def _sequence(self,state:EKState,attacks_remaining:int,special_id:str,special_slot:int,special_pending:bool)->EKScore:
        return self._sequence_cached(self._canonical_state(state,int(special_pending and special_slot>0)),attacks_remaining,special_id,special_slot,special_pending)

    @lru_cache(maxsize=None)
    def _sequence_cached(self,state:EKState,attacks_remaining:int,special_id:str,special_slot:int,special_pending:bool)->EKScore:
        if attacks_remaining==0 and not special_pending:return self._turn(state)
        choices=[]
        if attacks_remaining:
            choices.append(self._weapon_attack(state,False,lambda next_state:self._sequence(next_state,attacks_remaining-1,special_id,special_slot,special_pending)))
        if special_pending:
            choices.append(self._cast_value(state,special_id,special_slot,lambda next_state:self._sequence(next_state,attacks_remaining,special_id,special_slot,False)))
        return _best(choices)

    def _attack_action(self,state:EKState,special_id:str="",special_slot:int=0,replacement_cost:int=0)->EKScore:
        if replacement_cost>self.attacks:raise ValueError("Eldritch Knight attack replacement exceeds the Attack action")
        return _best([self._sequence(after_action,self.attacks-replacement_cost,special_id,special_slot,bool(special_id)) for after_action in self._consume_action_states(state,magic=False)])

    def _cast_dragons_breath(self,state:EKState,slot:int)->EKState:
        spell=self.spells["dragons_breath"]
        if not state.bonus_available:raise ValueError("Dragon's Breath requires the shared bonus action")
        spent=self._consume_slot(state,slot);damage_type=self._best_damage_type(spell["damage_types"])
        return replace(spent,bonus_available=False,concentration=f"dragons_breath:{slot}",concentration_type=damage_type)

    def _dragons_breath(self,state:EKState)->EKScore:
        spell=self.spells["dragons_breath"];packet=self._spell_packet(spell,int(state.concentration.split(":",1)[1]));damage,next_state=self._save_area_score(state,spell,packet,state.concentration_type)
        return _best([damage+self._turn(after_action) for after_action in self._consume_action_states(next_state,magic=True)])

    def _witch_repeat(self,state:EKState)->EKScore:
        spell=self.spells["witch_bolt"];damage=self._packet(spell["repeat_damage"],spell["damage_types"][0])
        return self._damage_score(damage)+self._turn(replace(state,bonus_available=False))

    def _finish_turn(self,state:EKState)->EKScore:
        def next_round(next_state:EKState)->EKScore:
            if next_state.round_index+1==self.rounds:return EKScore()
            concentration=next_state.concentration
            if concentration=="witch_bolt_pending":concentration="witch_bolt"
            actions=self.actions_by_round[next_state.round_index+1]
            return self._turn(EKState(next_state.round_index+1,actions,next_state.studied if next_state.attacked_this_turn else False,self.prowess_enabled,next_state.slots,True,concentration,next_state.concentration_type,False,next_state.eldritch_strike_fresh if self.eldritch_strike_enabled else False,False,(),ordinary_action_available=bool(actions),slotted_spell_cast_this_turn=False))
        delayed=EKScore();resolved=state
        if state.delayed_packets:
            primary=0.0
            for damage_type,count,sides in state.delayed_packets:
                packet_damage=self._packet({"count":count,"sides":sides},damage_type);primary+=packet_damage
                if state.concentration=="bestow_curse" and packet_damage>0:primary+=self._curse_packet()
            delayed=self._damage_score(primary);resolved=replace(state,delayed_packets=())
        if resolved.concentration!="phantasmal_killer":return delayed+next_round(resolved)
        spell=self.spells["phantasmal_killer"];success=self._save_success(spell,repeat=True);damage=self._packet(spell["damage"],spell["damage_types"][0]);ended=next_round(self._replace_concentration(resolved));active=self._damage_score(damage)+next_round(resolved)
        return delayed+ended.scaled(success)+active.scaled(1-success)

    def _turn(self,state:EKState)->EKScore:
        return self._turn_cached(self._canonical_state(state))

    @lru_cache(maxsize=None)
    def _turn_cached(self,state:EKState)->EKScore:
        choices=[]
        if state.bonus_available:
            if state.concentration=="witch_bolt":choices.append(self._witch_repeat(state))
            if "dragons_breath" in self.prepared and not state.concentration.startswith("dragons_breath:"):
                spell=self.spells["dragons_breath"]
                for slot in self._slot_options(state,spell):
                    choices.append(self._turn(self._cast_dragons_breath(state,slot)))
        if state.actions_left==0:
            choices.append(self._finish_turn(state));return _best(choices)
        choices.append(self._attack_action(state))
        war=self.row["war_magic"]
        if self.level>=int(war["minimum_level"]):
            for spell_id in self.cantrips:choices.append(self._attack_action(state,spell_id,0,int(war["attack_replacement_cost"])))
        improved=self.row["improved_war_magic"]
        if self.level>=int(improved["minimum_level"]):
            eligible=set(int(value) for value in improved["eligible_spell_levels"])
            for spell_id in self.prepared:
                spell=self.spells[spell_id]
                if spell["action_type"]!="action" or int(spell["spell_level"]) not in eligible:continue
                if self._recast_is_dominated(state,spell_id):continue
                for slot in self._slot_options(state,spell):choices.append(self._attack_action(state,spell_id,slot,int(improved["attack_replacement_cost"])))
        for spell_id in self.prepared:
            spell=self.spells[spell_id]
            if spell["action_type"]!="action":continue
            if self._recast_is_dominated(state,spell_id):continue
            if self.level>=int(improved["minimum_level"]) and int(spell["spell_level"]) in set(int(value) for value in improved["eligible_spell_levels"]):continue
            for slot in self._slot_options(state,spell):
                for after_action in self._consume_action_states(state,magic=True):choices.append(self._cast_value(after_action,spell_id,slot,self._turn))
        if state.concentration.startswith("dragons_breath:") and state.ordinary_action_available:choices.append(self._dragons_breath(state))
        return _best(choices)

    def solve(self)->EKScore:
        initial=EKState(0,self.actions_by_round[0],False,self.prowess_enabled,self.initial_slots,True,ordinary_action_available=bool(self.actions_by_round[0]))
        total=self._turn(initial);return total.scaled(1/self.rounds)

    def clear(self)->None:
        self._turn_cached.cache_clear();self._sequence_cached.cache_clear();self._packet_cache.clear()
