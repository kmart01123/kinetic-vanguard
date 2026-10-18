"""Canonical rider allocations resolved entirely by the triggering strike."""
from typing import Any


def validate_spec(spec:dict[str,Any])->None:
    expected={"kind":"exchange_targets_for_dice","minimum_dice_per_target":1,"secondary_target_eligibility":"hostile","packet":"per_target"}
    if set(spec)!=set(expected)|{"minimum_targets","dice_budget","maximum_targets"} or any(spec.get(k)!=v for k,v in expected.items()):
        raise ValueError("Unsupported damage allocation contract")
    minimum=spec["minimum_targets"];budget=spec["dice_budget"];maximum=spec["maximum_targets"]
    if any(type(n) is not int for n in [spec["minimum_dice_per_target"],minimum,budget,maximum]) or not 2<=minimum<=budget<=5 or maximum!=budget:
        raise ValueError("Unsupported allocation capacity")


def compositions(total:int):
    if total==0:
        yield ()
        return
    for first in range(1,total+1):
        for rest in compositions(total-first):yield (first,)+rest


def allocations(spec:dict[str,Any],cluster_size:int)->list[tuple[int,...]]:
    validate_spec(spec)
    # cluster_size counts the primary and hostile secondaries in this homogeneous roster.
    # Secondary identities are interchangeable only within that roster.
    return sorted({(a[0],*sorted(a[1:])) for a in compositions(spec["dice_budget"]) if spec["minimum_targets"]<=len(a)<=min(cluster_size,spec["maximum_targets"])})


def validate_allocation(spec:dict[str,Any],allocation:tuple[int,...],*,secondary_hostile:tuple[bool,...])->None:
    validate_spec(spec)
    if not allocation or any(type(n) is not int or n<1 for n in allocation) or sum(allocation)!=spec["dice_budget"] or not spec["minimum_targets"]<=len(allocation)<=spec["maximum_targets"]:
        raise ValueError("Invalid declared rider allocation")
    if len(secondary_hostile)!=len(allocation)-1 or any(hostile is not True for hostile in secondary_hostile):
        raise ValueError("Every secondary target must be hostile")
