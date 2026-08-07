"""Frozen benchmark inputs and shared probability helpers."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
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


def load_config(path:Path=DEFAULT_CONFIG)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:return json.load(stream)


def load_comparators(path:Path=DEFAULT_COMPARATORS)->dict[str,Any]:
    with path.open(encoding="utf-8") as stream:data=json.load(stream)
    expected=["battle_master","eldritch_knight"]
    if data.get("format_version")!=1:raise ValueError("Unsupported comparator format version")
    if data.get("primary_comparator_ids")!=expected:raise ValueError("Primary comparators must be Battle Master and Eldritch Knight")
    if set(data.get("damage",{}))!=set(expected):raise ValueError("Damage comparator set is incomplete or unsupported")
    if set(data.get("control",{}))!=set(expected):raise ValueError("Control comparator set is incomplete or unsupported")
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
