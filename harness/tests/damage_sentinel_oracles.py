"""Independent exact oracles for the frozen Issue #65 damage sentinels.

This module intentionally imports only Python standard-library modules.  It
does not import the production damage contract, providers, evaluator, target
projection, catalog, reporter, or configuration loaders.  Its functions only
accept one of the fifty frozen synthetic fixtures from the adjacent JSON data
contract; they are not a second general-purpose damage evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "damage-sentinels-v1.json"
EXPECTED_CASE_IDS = tuple(f"S{index:02d}" for index in range(1, 51))


@dataclass(frozen=True)
class OracleResult:
    numbers: tuple[tuple[str, Fraction], ...]
    facts: dict[str, Any]

    def number_map(self) -> dict[str, Fraction]:
        return dict(self.numbers)


def fraction(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("Boolean is not an exact numeric fixture")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"Unsupported exact fixture value: {value!r}")


def mean(values: object) -> Fraction:
    sequence = tuple(values)  # type: ignore[arg-type]
    if not sequence:
        raise ValueError("Cannot average an empty exact sequence")
    return sum((fraction(value) for value in sequence), Fraction()) / len(sequence)


def die_distribution(count: int, sides: int, minimum: int | None = None) -> dict[int, Fraction]:
    distribution = {0: Fraction(1)}
    faces = tuple(max(minimum, face) if minimum is not None else face for face in range(1, sides + 1))
    for _ in range(count):
        next_distribution: dict[int, Fraction] = {}
        for subtotal, probability in distribution.items():
            for face in faces:
                total = subtotal + face
                next_distribution[total] = next_distribution.get(total, Fraction()) + probability / sides
        distribution = next_distribution
    if sum(distribution.values(), Fraction()) != 1:
        raise AssertionError("Die distribution lost exact probability mass")
    return distribution


def distribution_mean(distribution: dict[int, Fraction]) -> Fraction:
    return sum((value * probability for value, probability in distribution.items()), Fraction())


def attack_probabilities(attack_bonus: int, armor_class: int, advantage: bool = False) -> dict[str, Fraction]:
    counts = {"miss": 0, "hit": 0, "critical": 0}
    rolls = ((first, second) for first in range(1, 21) for second in range(1, 21)) if advantage else ((roll, roll) for roll in range(1, 21))
    total = 400 if advantage else 20
    for first, second in rolls:
        natural = max(first, second) if advantage else first
        outcome = "miss" if natural == 1 else "critical" if natural == 20 else "hit" if natural + attack_bonus >= armor_class else "miss"
        counts[outcome] += 1
    return {name: Fraction(count, total) for name, count in counts.items()}


def attack_expected(probabilities: dict[str, Fraction], hit_damage: Fraction, critical_damage: Fraction) -> Fraction:
    return probabilities["hit"] * hit_damage + probabilities["critical"] * critical_damage


def exact_result(numbers: dict[str, object] | None = None, facts: dict[str, Any] | None = None) -> OracleResult:
    exact_numbers = tuple((name, fraction(value)) for name, value in (numbers or {}).items())
    return OracleResult(exact_numbers, facts or {})


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Damage sentinel corpus must be a JSON object")
    return value


def canonical_corpus_bytes(corpus: dict[str, Any] | None = None) -> bytes:
    value = load_corpus() if corpus is None else corpus
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_corpus_sha256(corpus: dict[str, Any] | None = None) -> str:
    return hashlib.sha256(canonical_corpus_bytes(corpus)).hexdigest()


def cases_by_id(corpus: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    value = load_corpus() if corpus is None else corpus
    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Damage sentinel corpus cases must be a list")
    result: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValueError("Every damage sentinel must be an object with a string id")
        if case["id"] in result:
            raise ValueError(f"Duplicate damage sentinel id: {case['id']}")
        result[case["id"]] = case
    return result


def _s01(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    probabilities = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"])
    die = mean(range(1, inputs["weapon_die"] + 1))
    expected = attack_expected(probabilities, die + inputs["flat"], 2 * die + inputs["flat"])
    return exact_result({"miss_probability": probabilities["miss"], "hit_probability": probabilities["hit"], "critical_probability": probabilities["critical"], "expected_damage": expected}, {"selected": "ordinary_attack"})


def _s02(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    probabilities = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"], True)
    die = mean(range(1, inputs["weapon_die"] + 1))
    expected = attack_expected(probabilities, die + inputs["flat"], 2 * die + inputs["flat"])
    return exact_result({"miss_probability": probabilities["miss"], "hit_probability": probabilities["hit"], "critical_probability": probabilities["critical"], "expected_damage": expected}, {"selected": "advantage_attack"})


def _s03(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    ordinary = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"])
    advantage = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"], True)
    die = mean(range(1, inputs["weapon_die"] + 1))
    hit = die + inputs["flat"]
    critical = 2 * die + inputs["flat"]
    ordinary_value = attack_expected(ordinary, hit, critical)
    advantage_value = attack_expected(advantage, hit, critical)
    total = ordinary_value + ordinary["miss"] * advantage_value + (1 - ordinary["miss"]) * ordinary_value
    return exact_result(
        {"two_attack_expected_damage": total},
        {
            "lookahead": False,
            "same_target_required": True,
            "prior_studied_benefit_consumed": True,
            "fresh_final_miss_establishes_studied": True,
        },
    )


def _s04(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    probabilities = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"])
    die = mean(range(1, inputs["weapon_die"] + 1))
    hit = die + inputs["flat"]
    critical = 2 * die + inputs["flat"]
    expected = (probabilities["miss"] + probabilities["hit"]) * hit + probabilities["critical"] * critical
    return exact_result({"expected_damage": expected}, {"selected": "use_prowess", "establishes_studied": False})


def _s05(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    outcomes = tuple((face + inputs["flat"]) // 2 for face in range(1, inputs["die"] + 1))
    return exact_result({"expected_damage": mean(outcomes)}, {"round_per_outcome": True})


def _s06(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    damage = 0 if inputs["immune"] else inputs["raw_damage"] * (2 if inputs["vulnerable"] else 1)
    return exact_result({"damage": damage}, {"immunity_prevents_revival": inputs["immune"] and damage == 0})


def _s07(case: dict[str, Any]) -> OracleResult:
    raw = case["inputs"]["raw_damage"]
    return exact_result({"vulnerable_damage": raw * 2, "cancelled_damage": raw}, {"cancel_before_rounding": True})


def _s08(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    full = mean(range(1, inputs["die"] + 1))
    success = mean(face // 2 for face in range(1, inputs["die"] + 1))
    save = fraction(inputs["save_success_probability"])
    return exact_result({"full_branch_mean": full, "success_branch_mean": success, "expected_damage": (1 - save) * full + save * success}, {"floor_per_damage_outcome": True})


def _s09(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    normal = sum(Fraction(roll + inputs["save_bonus"] >= inputs["dc"], 20) for roll in range(1, 21))
    failures = sum(1 for roll in range(1, 21) if roll + inputs["save_bonus"] < inputs["dc"])
    magic = 1 - Fraction(failures * failures, 400)
    damage = inputs["failed_save_damage"]
    return exact_result({"normal_save_probability": normal, "magic_resistance_save_probability": magic, "normal_expected_damage": (1 - normal) * damage, "magic_resistance_expected_damage": (1 - magic) * damage}, {"legendary_resistance_spend": False})


def _s10(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    raw = tuple(face + inputs["flat"] for face in range(1, inputs["die"] + 1))
    holdout = tuple(value // inputs["holdout_divisor"] for value in raw)
    resisted = tuple(value // 2 for value in holdout)
    normal = 0 if inputs["fire_immune"] else mean(raw)
    selected = "force_holdout" if mean(resisted) > normal else "normal_fire"
    return exact_result({"normal_fire": normal, "holdout_without_force_resistance": mean(holdout), "force_resisted_holdout": mean(resisted)}, {"raw_outcomes": list(raw), "holdout_outcomes": list(holdout), "resisted_outcomes": list(resisted), "selected": selected})


def _s11(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    expected = fraction(inputs["base_expected"]) + fraction(inputs["hit_probability"]) * inputs["rider_damage"]
    return exact_result({"expected_damage": expected}, {"rider_critical_multiplier": 1, "psi_after_declaration": 1 - inputs["psi_cost"]})


def _s12(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    damage = inputs["rider_damage"] if inputs["forced_outcome"] != "miss" else 0
    return exact_result({"damage": damage}, {"psi_after": case["starting_state"]["psi"] - inputs["psi_cost"], "rider_resolved": inputs["forced_outcome"] != "miss"})


def _s13(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    full = mean(range(1, inputs["rider_die"] + 1))
    half = mean(face // 2 for face in range(1, inputs["rider_die"] + 1))
    save = fraction(inputs["save_success_probability"])
    return exact_result({"expected_rider_damage": (1 - save) * full + save * half}, {"psi_after": case["starting_state"]["psi"] - inputs["psi_cost"]})


def _s14(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    return exact_result({"signature_total": inputs["strikes"] * inputs["signature_damage"]}, {"non_signature_uses": min(inputs["strikes"], inputs["non_signature_repeat_limit"]), "riders_per_strike": 1})


def _s15(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    one_action = inputs["tier_two_damage"]
    return exact_result({"one_action_total": one_action, "two_action_total": one_action * inputs["attack_actions"]}, {"uses_per_action": 1})


def _s16(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    pb = inputs["proficiency_bonus"]
    costs = {tier: tier * pb for tier in inputs["tiers"]}
    after = inputs["starting_budget"] - costs[2]
    return exact_result({"tier_zero_cost": costs[0], "tier_one_cost": costs[1], "tier_two_cost": costs[2], "budget_after_tier_two": after}, {"next_positive_tier_legal": after >= pb})


def _s17(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    activated = sum(tax // inputs["divisor"] for tax in inputs["taxes"])
    return exact_result({"activated_tax": activated, "declined_tax": sum(inputs["taxes"])}, {"late_activation_legal": False})


def _s18(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    attack = inputs["attack_packets_per_action"] * inputs["packet_damage"]
    standalone = inputs["standalone_damage"]
    total = standalone + attack * (inputs["action_slots"] - 1)
    return exact_result({"attack_action_damage": attack, "standalone_damage": standalone, "two_slot_total": total}, {"selected_first_action": "standalone" if standalone > attack else "attack", "standalone_uses": min(1, inputs["standalone_limit_per_turn"])})


def _s19(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    values = {size: inputs["primary_damage"] + (size - 1) * inputs["secondary_damage"] for size in inputs["cluster_sizes"]}
    return exact_result({"cluster_one": values[1], "cluster_three": values[3], "cluster_six": values[6]}, {"primary_damage": inputs["primary_damage"]})


def _s20(case: dict[str, Any]) -> OracleResult:
    sides = case["inputs"]["superiority_die"]
    die = mean(range(1, sides + 1))
    return exact_result({"noncritical_increment": die, "critical_increment": 2 * die}, {"maximum_dice": 1, "named_maneuver": False})


def _s21(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    required = inputs["known_armor_class"] - inputs["observed_attack_total"]
    successes = sum(face >= required for face in range(1, inputs["precision_die"] + 1))
    probability = Fraction(successes, inputs["precision_die"])
    expected = probability * inputs["corrected_hit_damage"] + (1 - probability) * inputs["graze_damage"]
    return exact_result({"success_probability": probability, "expected_damage": expected}, {"required_correction": required, "die_spent_on_failure": True})


def _s22(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    die = mean(range(1, inputs["die"] + 1))
    total = inputs["forced_hits"] * inputs["base_damage_each"] + die * min(inputs["forced_hits"], inputs["pool"])
    return exact_result({"total_damage": total}, {"dice_spent": 1, "canonical_spend": "first_hit"})


def _s23(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    normal = mean(range(1, inputs["normal_die"] + 1))
    relentless = mean(range(1, inputs["relentless_die"] + 1))
    return exact_result({"total_increment": normal + relentless}, {"normal_dice_spent": 1, "relentless_tokens_spent": 1})


def _s24(case: dict[str, Any]) -> OracleResult:
    sides = case["inputs"]["relentless_die"]
    return exact_result({"increment": mean(range(1, sides + 1))}, {"refresh_next_turn": True})


def _s25(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    gwf = mean(max(inputs["gwf_minimum"], face) for face in range(1, inputs["die"] + 1))
    normal = inputs["greatsword_dice"] * gwf
    critical = 2 * inputs["greatsword_dice"] * gwf
    attack_flat = inputs["ability"] + inputs["magic"] + inputs["proficiency_bonus"]
    hew_flat = inputs["ability"] + inputs["magic"]
    return exact_result({"gwf_die_mean": gwf, "normal_weapon_dice": normal, "critical_weapon_dice": critical, "attack_action_flat": attack_flat, "hew_flat": hew_flat, "graze_damage": inputs["graze"]}, {"gwm_on_hew": False})


def _s26(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    die = mean(range(1, inputs["weapon_die"] + 1))
    total = inputs["critical_dice"] * die + inputs["followup_dice"] * die
    return exact_result({"total_damage": total}, {"gwm_on_followup": False, "recursive_hew": False})


def _s27(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    first = min(inputs["main_packet"], inputs["target_hp"][0])
    second = min(inputs["followup_packet"], inputs["target_hp"][1])
    kills = int(first == inputs["target_hp"][0]) + int(second == inputs["target_hp"][1])
    return exact_result({"actual_hp_removed": first + second, "kills": kills}, {"retargeted": True})


def _s28(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    actual = min(inputs["main_packet"], inputs["target_hp"][0])
    return exact_result({"actual_hp_removed": actual, "kills": int(actual == inputs["target_hp"][0])}, {"followup_legal": False})


def _s29(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    first_actual = min(inputs["critical_packet"], inputs["target_hp"][0])
    first_overkill = max(0, inputs["critical_packet"] - inputs["target_hp"][0])
    second_actual = min(inputs["followup_packet"], inputs["target_hp"][1])
    kills = int(first_actual == inputs["target_hp"][0]) + int(second_actual == inputs["target_hp"][1])
    return exact_result({"actual_hp_removed": first_actual + second_actual, "overkill": first_overkill, "kills": kills}, {"hew_entitlements": 1})


def _s30(case: dict[str, Any]) -> OracleResult:
    scenarios = set(case["inputs"]["scenarios"])
    return exact_result(facts={"bonus_action_spent": "bonus_action_spent" not in scenarios, "wrong_weapon": "wrong_weapon" not in scenarios, "no_living_target": "no_living_target" not in scenarios, "declined_opportunity_expires": "declined_then_later_trigger" in scenarios, "later_main_trigger_possible": "declined_then_later_trigger" in scenarios})


def _s31(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    ordinary_probabilities = attack_probabilities(inputs["ordinary_attack_bonus"], inputs["armor_class"])
    true_probabilities = attack_probabilities(inputs["true_strike_attack_bonus"], inputs["armor_class"])
    weapon = mean(range(1, inputs["weapon_die"] + 1))
    upgrade = mean(range(1, inputs["upgrade_die"] + 1))
    ordinary = attack_expected(ordinary_probabilities, weapon + inputs["ordinary_flat"], 2 * weapon + inputs["ordinary_flat"])
    true_strike = attack_expected(true_probabilities, weapon + upgrade + inputs["true_strike_flat"], 2 * weapon + 2 * upgrade + inputs["true_strike_flat"])
    zero = inputs["attacks_per_action"] * ordinary
    one = (inputs["attacks_per_action"] - 1) * ordinary + true_strike
    selected = 0 if zero > one else 1
    return exact_result({"ordinary_attack": ordinary, "true_strike_attack": true_strike, "zero_replacements_action": zero, "one_replacement_action": one}, {"selected_replacements": selected})


def _s32(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    action_count = sum(inputs["action_slots_by_round"])
    total = inputs["attacks_per_action"] * action_count * inputs["unit_damage"]
    return exact_result({"total_damage": total, "dpr": Fraction(total, 3)}, {"attack_action_ids": action_count})


def _s33(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    attacks = [inputs["attacks_per_action"] * slots for slots in inputs["action_slots_by_round"]]
    total = sum(attacks) * inputs["unit_damage"]
    return exact_result({"total_damage": total, "dpr": Fraction(total, 3)}, {"attacks_by_round": attacks})


def _s34(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    attacks = [inputs["attacks_per_action"] * slots for slots in inputs["action_slots_by_round"]]
    hits = sum(count - 1 for count in attacks)
    return exact_result({"total_hits": hits, "dpr": Fraction(hits * inputs["unit_damage"], 3)}, {"attacks_by_round": attacks, "studied_after_horizon": False})


def _s35(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    attacks = [inputs["attacks_per_action"] * slots for slots in inputs["action_slots_by_round"]]
    total = sum(attacks) * inputs["unit_damage"]
    return exact_result({"total_hits": total, "dpr": Fraction(total, 3), "prowess_uses": len(attacks)}, {"attacks_by_round": attacks})


def _tie_winner(left: list[Any], right: list[Any]) -> str:
    left_key = (fraction(left[0]), fraction(left[1]), -fraction(left[2]), -fraction(left[3]), -fraction(left[4]), -fraction(left[5]))
    right_key = (fraction(right[0]), fraction(right[1]), -fraction(right[2]), -fraction(right[3]), -fraction(right[4]), -fraction(right[5]))
    if left_key != right_key:
        return str(left[6] if left_key > right_key else right[6])
    return min(str(left[6]), str(right[6]))


def _s36(case: dict[str, Any]) -> OracleResult:
    pairs = case["inputs"]["tie_pairs"]
    winners = [_tie_winner(pair["left"], pair["right"]) for pair in pairs]
    damage_first = _tie_winner([11, 0, 9, 9, 9, 9, "costly"], [10, 10, 0, 0, 0, 0, "cheap"]) == "costly"
    return exact_result(facts={"winners": winners, "resource_never_beats_damage": damage_first})


def _s37(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    weights = [fraction(value) for value in inputs["weights"]]
    weighted = sum((weight * value for weight, value in zip(weights, inputs["values"], strict=True)), Fraction())
    return exact_result({"weighted_value": weighted}, {"weight_total": str(sum(weights, Fraction()))})


def _s38(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    damage = range(1, inputs["die"] + 1)
    actual = [min(value, inputs["target_hp"]) for value in damage]
    overkill = [max(0, value - inputs["target_hp"]) for value in damage]
    kills = [int(value >= inputs["target_hp"]) for value in damage]
    return exact_result({"expected_actual": mean(actual), "expected_overkill": mean(overkill), "kill_probability": mean(kills)}, {"actual_outcomes": actual, "overkill_outcomes": overkill})


def _s39(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    hp = list(inputs["target_hp"])
    actual = kills = 0
    for index, packet in enumerate(inputs["attacks"]):
        removed = min(packet, hp[index])
        actual += removed
        hp[index] -= removed
        kills += hp[index] == 0
    return exact_result({"actual_hp_removed": actual, "kills": kills}, {"retargeted": True})


def _s40(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    actual = sum(min(packet, hp) for packet, hp in zip(inputs["packet_damage"], inputs["target_hp"], strict=True))
    overkill = sum(max(0, packet - hp) for packet, hp in zip(inputs["packet_damage"], inputs["target_hp"], strict=True))
    kills = sum(packet >= hp and hp > 0 for packet, hp in zip(inputs["packet_damage"], inputs["target_hp"], strict=True))
    reversed_actual = sum(min(packet, hp) for packet, hp in zip(reversed(inputs["packet_damage"]), reversed(inputs["target_hp"]), strict=True))
    return exact_result({"actual_hp_removed": actual, "overkill": overkill, "kills": kills}, {"order_invariant": actual == reversed_actual})


def _s41(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    before = attack_probabilities(inputs["attack_bonus"], inputs["initial_armor_class"])
    after = attack_probabilities(inputs["attack_bonus"], inputs["initial_armor_class"] - inputs["reduction"])
    return exact_result({"before_hit_probability": before["hit"] + before["critical"], "after_hit_probability": after["hit"] + after["critical"]}, {"first_attack_benefits": False})


def _s42(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    hp = dict(inputs["cohort_hp"])
    packet_counts = {target: 0 for target in hp}
    actual = overkill = kills = 0
    for _round in inputs["packet_rounds"]:
        for target in tuple(hp):
            if hp[target] <= 0:
                continue
            packet_counts[target] += 1
            packet = inputs["packet_damage"]
            removed = min(packet, hp[target])
            actual += removed
            overkill += max(0, packet - hp[target])
            hp[target] -= removed
            kills += hp[target] == 0
    return exact_result({"actual_hp_removed": actual, "overkill": overkill, "kills": kills}, {"A_packets": packet_counts["A"], "B_packets": packet_counts["B"], "C_packets": 0, "activation_damage": 0})


def _s43(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    legal = not inputs["requires_target_turn_repeated_save_state"] or case["starting_state"]["target_turn_state_modeled"]
    return exact_result(facts={"legal": legal, "fail_closed_if_emitted": not legal})


def _s44(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    original = (inputs["primary_hp"], tuple(sorted(inputs["secondary_hp"])))
    secondary_swap = (inputs["primary_hp"], tuple(sorted(reversed(inputs["secondary_hp"]))))
    primary_swap = (inputs["secondary_hp"][0], tuple(sorted((inputs["primary_hp"], inputs["secondary_hp"][1]))))
    return exact_result(facts={"secondary_swap_invariant": original == secondary_swap, "primary_swap_invariant": original == primary_swap, "hp_averaging_allowed": False})


def _s45(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    resisted = inputs["raw_damage"] // 2 if inputs["resistant"] else inputs["raw_damage"]
    bypass = 0 if inputs["immune"] else inputs["raw_damage"]
    return exact_result({"resisted_damage": resisted, "bypass_damage": bypass, "immune_damage": 0}, {"bypass_immunity": False})


def _s46(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    views = [json.dumps(inputs["static_target"], sort_keys=True, separators=(",", ":")) for _provider in inputs["providers"]]
    static_fields = set(inputs["static_target"])
    future_fields = set(inputs["future_fields"])
    nominal_dynamic: dict[str, Any] = {}
    finite_dynamic = dict(inputs["finite_dynamic"])
    return exact_result(facts={"provider_views_equal": len(set(views)) == 1, "future_fields_absent": static_fields.isdisjoint(future_fields), "nominal_dynamic_hp_present": "current_hp" in nominal_dynamic, "finite_dynamic_hp_present": "current_hp" in finite_dynamic and "alive" in finite_dynamic})


def _true_strike_values(inputs: dict[str, Any]) -> tuple[Fraction, Fraction]:
    probabilities = attack_probabilities(inputs["attack_bonus"], inputs["armor_class"])
    weapon = mean(range(1, inputs["weapon_die"] + 1))
    upgrade = mean(range(1, inputs["upgrade_die"] + 1))
    radiant = Fraction() if inputs["radiant_immune"] else attack_expected(probabilities, weapon + upgrade + inputs["flat"], 2 * weapon + 2 * upgrade + inputs["flat"])
    weapon_component_hit = Fraction() if inputs["weapon_immune"] else weapon + inputs["flat"]
    weapon_component_critical = Fraction() if inputs["weapon_immune"] else 2 * weapon + inputs["flat"]
    upgrade_hit = Fraction() if inputs["radiant_immune"] else upgrade
    upgrade_critical = Fraction() if inputs["radiant_immune"] else 2 * upgrade
    normal = attack_expected(probabilities, weapon_component_hit + upgrade_hit, weapon_component_critical + upgrade_critical)
    return radiant, normal


def _s47(case: dict[str, Any]) -> OracleResult:
    radiant, normal = _true_strike_values(case["inputs"])
    return exact_result({"radiant_base": radiant, "weapon_normal_base": normal}, {"selected": "radiant_base" if radiant > normal else "weapon_normal_base"})


def _s48(case: dict[str, Any]) -> OracleResult:
    radiant, normal = _true_strike_values(case["inputs"])
    return exact_result({"radiant_base": radiant, "weapon_normal_base": normal}, {"selected": "radiant_base" if radiant > normal else "weapon_normal_base"})


def _s49(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    weapon_hit = die_distribution(1, inputs["weapon_die"])
    upgrade_hit = die_distribution(1, inputs["upgrade_die"])
    weapon_critical = die_distribution(2, inputs["weapon_die"])
    upgrade_critical = die_distribution(2, inputs["upgrade_die"])

    def combined(weapon: dict[int, Fraction], upgrade: dict[int, Fraction]) -> Fraction:
        return sum((weapon_value + upgrade_value + inputs["flat"]) // 2 * weapon_probability * upgrade_probability for weapon_value, weapon_probability in weapon.items() for upgrade_value, upgrade_probability in upgrade.items())

    def split(weapon: dict[int, Fraction], upgrade: dict[int, Fraction]) -> Fraction:
        return sum(((weapon_value + inputs["flat"]) // 2 + upgrade_value // 2) * weapon_probability * upgrade_probability for weapon_value, weapon_probability in weapon.items() for upgrade_value, upgrade_probability in upgrade.items())

    fixed_hit = inputs["fixed_noncritical_faces"]
    fixed_critical = inputs["fixed_critical_faces"]
    fixed_radiant_hit = (sum(fixed_hit["weapon"]) + sum(fixed_hit["upgrade"]) + inputs["flat"]) // 2
    fixed_split_hit = (sum(fixed_hit["weapon"]) + inputs["flat"]) // 2 + sum(fixed_hit["upgrade"]) // 2
    fixed_radiant_critical = (sum(fixed_critical["weapon"]) + sum(fixed_critical["upgrade"]) + inputs["flat"]) // 2
    fixed_split_critical = (sum(fixed_critical["weapon"]) + inputs["flat"]) // 2 + sum(fixed_critical["upgrade"]) // 2
    raw_critical = distribution_mean(weapon_critical) + distribution_mean(upgrade_critical) + inputs["flat"]
    return exact_result({"radiant_noncritical": combined(weapon_hit, upgrade_hit), "split_noncritical": split(weapon_hit, upgrade_hit), "radiant_critical": combined(weapon_critical, upgrade_critical), "split_critical": split(weapon_critical, upgrade_critical), "raw_neutral_critical": raw_critical, "fixed_radiant_noncritical": fixed_radiant_hit, "fixed_split_noncritical": fixed_split_hit, "fixed_radiant_critical": fixed_radiant_critical, "fixed_split_critical": fixed_split_critical}, {"flats_doubled": False, "eligible_weapon_dice_doubled": True, "eligible_upgrade_dice_doubled": True})


def _s50(case: dict[str, Any]) -> OracleResult:
    inputs = case["inputs"]
    actions = inputs["actions"]
    removed_winner = max(actions, key=lambda name: (actions[name]["actual"], actions[name]["primary"], actions[name]["kills"], -actions[name]["overkill"], tuple(-ord(character) for character in name)))
    kill_winner = max(actions, key=lambda name: (actions[name]["kills"], actions[name]["actual"], actions[name]["primary"], -actions[name]["overkill"], tuple(-ord(character) for character in name)))
    early = tuple(inputs["earliness"]["early_cdf"])
    late = tuple(inputs["earliness"]["late_cdf"])
    return exact_result({"H_actual": actions["H"]["actual"], "H_kills": actions["H"]["kills"], "K_actual": actions["K"]["actual"], "K_kills": actions["K"]["kills"], "early_first_cdf": early[0], "late_first_cdf": late[0]}, {"finite_hp_removed_v1": removed_winner, "finite_hp_kill_cleave_v1": kill_winner, "earliest_exhaustion_winner": "Early" if early > late else "Late"})


ORACLES: dict[str, Callable[[dict[str, Any]], OracleResult]] = {
    f"s{index:02d}": globals()[f"_s{index:02d}"] for index in range(1, 51)
}


def evaluate_case(case: dict[str, Any]) -> OracleResult:
    oracle_id = case.get("oracle")
    if not isinstance(oracle_id, str) or oracle_id not in ORACLES:
        raise ValueError(f"Unsupported or missing frozen oracle id: {oracle_id!r}")
    return ORACLES[oracle_id](case)
