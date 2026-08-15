"""Focused public-API integration against the frozen Issue #65 sentinels.

All fixtures are synthetic.  This module deliberately avoids the production
orchestrator, roster, matrix writer, report renderer, and evaluator entrypoint.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from fractions import Fraction
from pathlib import Path
import unittest
from typing import Any

from harness.damage_contract import (
    BATTLE_MASTER_PACKAGE_ID,
    DEFERRED_FINITE_MODE_IDS,
    NOMINAL_MODE_ID,
    TARGET_KNOWLEDGE_CONTRACT_ID,
    DamageSolution,
    DamageValue,
    NominalKernel,
    Proposal,
    ResourceCost,
    TargetKnowledge,
    UnsupportedDamageMode,
    apply_defense,
    attack_outcome_distribution,
    battle_master_hit_damage,
    battle_master_precision_expected,
    die_distribution,
    eldritch_knight_hit_damage,
    eldritch_knight_single_attack_expected,
    expected_typed_packet,
    manifested_strike_packet_options,
    reject_unsupported_mode,
    save_success_probability,
    solve_comparator,
    solve_kinetic_vanguard,
    studied_state_after_final_attack,
)
from harness.tests.damage_sentinel_oracles import cases_by_id, fraction


CASES = cases_by_id()


def frozen_value(sentinel_id: str, name: str) -> Fraction:
    matches = [
        fraction(item["fraction"])
        for item in CASES[sentinel_id]["numeric_oracles"]
        if item["name"] == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one frozen {sentinel_id}.{name} oracle")
    return matches[0]


def knowledge(
    *,
    ac: int = 15,
    saves: dict[str, int] | None = None,
    magic_resistance: bool = False,
    resistances: frozenset[str] = frozenset(),
    immunities: frozenset[str] = frozenset(),
    vulnerabilities: frozenset[str] = frozenset(),
) -> TargetKnowledge:
    save_map = saves or {
        "strength": 0,
        "dexterity": 0,
        "constitution": 0,
        "intelligence": 0,
        "wisdom": 0,
        "charisma": 0,
    }
    return TargetKnowledge(
        contract_id=TARGET_KNOWLEDGE_CONTRACT_ID,
        creature_id="synthetic-integration-target",
        ac=ac,
        saves=tuple(sorted(save_map.items())),
        magic_resistance=magic_resistance,
        legendary_resistance=0,
        legendary_resistance_lair=None,
        legendary_resistance_policy="metadata_only",
        damage_resistances=resistances,
        damage_immunities=immunities,
        damage_vulnerabilities=vulnerabilities,
        size="medium",
        creature_type="construct",
    )


@dataclass
class SyntheticDamageTarget:
    creature_id: str
    ac: int
    saves: dict[str, int]
    magic_resistance: bool
    legendary_resistance: int
    legendary_resistance_lair: int | None
    legendary_resistance_policy: str
    damage_resistances: frozenset[str]
    damage_immunities: frozenset[str]
    damage_vulnerabilities: frozenset[str]
    size: str
    creature_type: str
    target_sha256: str
    hp: int
    current_hp: int
    alive: bool
    validation_calls: int = 0

    def validate_identity(self) -> None:
        self.validation_calls += 1


class SyntheticProgressionModel:
    def __init__(
        self,
        *,
        level: int = 7,
        proficiency_bonus: int = 3,
        strike_die: int = 8,
        psi_points: int = 0,
        kv_attack_bonus: int = 5,
        psi_modifier: int = 5,
    ) -> None:
        self.level = level
        self._progressions = {
            ("proficiency_bonus", level): proficiency_bonus,
            ("manifested_strike_die", level): strike_die,
            ("psi_points", level): psi_points,
        }
        self._kv_attack_bonus = kv_attack_bonus
        self._psi_modifier = psi_modifier
        self.disciplines = {
            "pyrokinesis": {
                "damage_type": "fire",
                "signature_save": "dexterity",
                "graze_damage": "psionic_ability_modifier",
            }
        }
        self.features: dict[str, dict[str, Any]] = {}
        self.projection = {
            "core": {
                "action_economy": {
                    "standalone_psionic_action_limit_per_turn": 1,
                    "action_surge_allows_additional_standalone_psionic_action": False,
                },
                "manifested_strike": {
                    "holdout_damage_type": "force",
                    "holdout_damage_divisor": 2,
                    "critical_dice_multiplier": 2,
                },
                "overload": {
                    "tier_two_limit_per_attack_action": 1,
                    "mastery": {
                        "minimum_level": 99,
                        "uses_per_rest": 0,
                        "minimum_per_overload": 1,
                        "blood_tax_divisor": 2,
                    },
                },
            },
            "progressions": {
                "tier_minimum_levels": [
                    {"tier": 0, "minimum_level": 7},
                    {"tier": 1, "minimum_level": 7},
                    {"tier": 2, "minimum_level": 15},
                ]
            },
        }

    def progression(self, name: str, level: int) -> int:
        try:
            return self._progressions[(name, level)]
        except KeyError as error:
            raise AssertionError(
                f"Unexpected synthetic progression request: {(name, level)!r}"
            ) from error

    def kv_attack_bonus(self, level: int, psi_modifier: int) -> int:
        if (
            ("proficiency_bonus", level) not in self._progressions
            or psi_modifier != self._psi_modifier
        ):
            raise AssertionError("Unexpected synthetic Kinetic Vanguard attack request")
        return self._kv_attack_bonus

    def kv_save_dc(self, level: int, psi_modifier: int) -> int:
        return 8 + self.progression("proficiency_bonus", level) + psi_modifier

    def blood_tax(self, level: int, tier: int) -> int:
        return self.progression("proficiency_bonus", level) * tier


def synthetic_projection_target(
    *,
    ac: int = 15,
    saves: dict[str, int] | None = None,
    magic_resistance: bool = False,
    resistances: frozenset[str] = frozenset(),
    immunities: frozenset[str] = frozenset(),
    vulnerabilities: frozenset[str] = frozenset(),
    size: str = "medium",
    creature_type: str = "construct",
    target_sha256: str = "opaque-synthetic-target-sha",
    hp: int = 100,
    current_hp: int = 100,
    alive: bool = True,
) -> SyntheticDamageTarget:
    return SyntheticDamageTarget(
        creature_id="synthetic-integration-target",
        ac=ac,
        saves=saves
        or {
            "strength": 0,
            "dexterity": 0,
            "constitution": 0,
            "intelligence": 0,
            "wisdom": 0,
            "charisma": 0,
        },
        magic_resistance=magic_resistance,
        legendary_resistance=0,
        legendary_resistance_lair=None,
        legendary_resistance_policy="metadata_only",
        damage_resistances=resistances,
        damage_immunities=immunities,
        damage_vulnerabilities=vulnerabilities,
        size=size,
        creature_type=creature_type,
        target_sha256=target_sha256,
        hp=hp,
        current_hp=current_hp,
        alive=alive,
    )


def nominal_config(
    *,
    level: int = 7,
    attacks_per_action: int = 2,
    action_slots_by_round: tuple[int, int, int] = (1, 1, 1),
    cluster_sizes: tuple[int, ...] = (1,),
    studied_attacks: bool = False,
    combat_prowess: bool = False,
    psi_modifier: int = 5,
    first_level_hp: int = 10,
    later_level_hp: int = 6,
    blood_tax_hp_fraction: str = "0",
    excluded_stateful_features: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Synthetic config that crosses every public PR1 policy guard."""

    return {
        "damage_model": {
            "mode_id": NOMINAL_MODE_ID,
            "target_knowledge_contract_id": TARGET_KNOWLEDGE_CONTRACT_ID,
            "numeric_representation": "exact_fraction",
            "finite_hp_mode": "unsupported_in_pr1",
            "provider_ids": [
                "kinetic_vanguard",
                "battle_master",
                "eldritch_knight",
            ],
        },
        "methodology": {
            "rounds": 3,
            "cluster_sizes": list(cluster_sizes),
            "target_death": False,
            "ally_turns": False,
            "legal_positioning_assumed": True,
            "legendary_resistance": "metadata_only",
        },
        "fighter_progression": {
            str(level): {
                "attacks_per_action": attacks_per_action,
                "action_slots_by_round": list(action_slots_by_round),
                "studied_attacks": studied_attacks,
                "combat_prowess": combat_prowess,
            }
        },
        "fighter_mechanics": {
            "studied_attacks": {
                "trigger": "resolved_miss_after_hit_instead_effects",
                "benefit": "advantage_on_next_attack_against_same_target",
                "expiry": "end_of_next_turn",
            },
            "combat_prowess": {
                "trigger": "attack_roll_miss",
                "effect": "hit_instead",
                "uses_per_turn": 1,
                "reset": "start_of_next_turn",
                "activation_policy": "optimal_after_observed_miss",
                "eligible_after_failed_attack_roll_bonus": True,
            },
        },
        "damage_matrix": {
            "optimization": {
                "scope": "per_target_discipline_cluster",
                "objective": [
                    "aggregate_damage",
                    "primary_damage",
                    "least_self_damage",
                    "least_horizon_limited_use",
                    "least_persistent_pool_use",
                    "least_refreshable_use",
                    "smallest_canonical_action_id",
                ],
                "resource_cost_classes": {
                    "order": [
                        "self_damage",
                        "horizon_limited",
                        "persistent_pool",
                        "refreshable",
                    ],
                    "kinetic_vanguard": {
                        "self_damage": ["blood_tax"],
                        "horizon_limited": ["overload_mastery"],
                        "persistent_pool": ["psi"],
                        "refreshable": ["combat_prowess"],
                    },
                    "battle_master": {
                        "self_damage": [],
                        "horizon_limited": [],
                        "persistent_pool": ["superiority_die"],
                        "refreshable": [
                            "relentless",
                            "combat_prowess",
                            "hew",
                            "bonus_action",
                        ],
                    },
                    "eldritch_knight": {
                        "self_damage": [],
                        "horizon_limited": [],
                        "persistent_pool": [],
                        "refreshable": [
                            "true_strike_replacement",
                            "combat_prowess",
                        ],
                    },
                },
                "decision_timing": {
                    "pre_roll_declarations": "optimize_from_legally_observed_state",
                    "unobserved_outcome_lookahead": False,
                    "post_roll_decisions": [
                        "battle_master_precision",
                        "combat_prowess",
                        "battle_master_on_hit_die",
                        "hew_bonus_attack",
                    ],
                },
            },
            "non_damage_effect_boundary": {
                "rider_conditions_and_save_outcomes": "excluded_from_damage",
                "ally_turn_accuracy_and_damage": "excluded",
                "modeled_self_attack_exception": "thermal_fracture_ac_reduction",
            },
            "excluded_stateful_features": [
                {
                    "entity_id": entity_id,
                    "reason": "synthetic deferred target-turn state",
                }
                for entity_id in excluded_stateful_features
            ],
        },
        "kv_profile": {
            "psionic_ability_modifier": psi_modifier,
            "constitution_modifier": 0,
            "hit_point_model": {
                "first_level_base": first_level_hp,
                "later_level_average": later_level_hp,
            },
            "archery_attack_bonus": 0,
            "blood_tax_hp_fraction": blood_tax_hp_fraction,
            "advanced_training_policy": "disabled",
            "attack_replacement_policy": "all_manifested_strikes",
        },
    }


def eldritch_knight_row() -> dict[str, Any]:
    return {
        "regular_attack_ability_modifier": 5,
        "true_strike_ability_modifier_by_level": {"7": 3},
        "weapon": {
            "count": 1,
            "sides": 8,
            "damage_type": "slashing",
            "great_weapon_fighting": False,
        },
        "magic_weapon_bonus_by_level": {"7": 1},
        "dueling_damage_bonus": 2,
        "true_strike_damage_by_level": {"7": {"count": 1, "sides": 6}},
        "true_strike_maximum_uses_per_attack_action": 1,
        "true_strike_damage_type": "radiant",
        "true_strike_base_damage_modes": ["radiant_base", "weapon_normal_base"],
        "tactical_policy": {
            "objective": NOMINAL_MODE_ID,
            "true_strike_choice_timing": "before_attack_roll",
            "decision_information": f"{TARGET_KNOWLEDGE_CONTRACT_ID}_and_observed_state",
            "true_strike_use_count": "zero_to_configured_maximum_per_attack_action",
        },
    }


def battle_master_row(
    *,
    level: int = 7,
    ability_modifier: int = 5,
    magic_weapon_bonus: int = 1,
    weapon_count: int = 2,
    weapon_sides: int = 6,
    great_weapon_fighting: bool = True,
    superiority_die: int = 8,
    superiority_pool: int = 1,
    relentless_minimum_level: int = 15,
    relentless_die: int = 8,
    hew_enabled: bool = True,
) -> dict[str, Any]:
    return {
        "ability_modifier": ability_modifier,
        "weapon": {
            "count": weapon_count,
            "sides": weapon_sides,
            "damage_type": "slashing",
            "great_weapon_fighting": great_weapon_fighting,
        },
        "magic_weapon_bonus_by_level": {str(level): magic_weapon_bonus},
        "great_weapon_master_attack_action_bonus": "proficiency_bonus",
        "graze_damage": 0,
        "hew_critical_bonus_attack_once_per_fighter_turn": hew_enabled,
        "hew_bonus_action_reserved": True,
        "hew_follow_up_weapon": "same_weapon",
        "superiority_die_by_level": {str(level): superiority_die},
        "superiority_pool_by_level": {str(level): superiority_pool},
        "relentless_minimum_level": relentless_minimum_level,
        "relentless_die": relentless_die,
        "tactical_policy": {
            "objective": NOMINAL_MODE_ID,
            "maneuver_choice_timing": "after_observed_attack_roll_result",
            "on_hit_die_effect": BATTLE_MASTER_PACKAGE_ID,
            "on_miss_die_effect": "attack_roll_bonus",
            "maneuver_die_consumption": "on_use_before_die_result",
            "maximum_maneuver_dice_per_attack": 1,
            "relentless_die_options": "same_as_superiority_die",
            "relentless_uses_per_turn": 1,
            "relentless_superiority_pool_cost": 0,
            "relentless_refresh": "start_of_next_turn",
            "hew_choice_timing": "after_observed_critical",
        },
    }


def simple_eldritch_knight_row(level: int) -> dict[str, Any]:
    return {
        "regular_attack_ability_modifier": 3,
        "true_strike_ability_modifier_by_level": {str(level): 0},
        "weapon": {
            "count": 1,
            "sides": 8,
            "damage_type": "slashing",
            "great_weapon_fighting": False,
        },
        "magic_weapon_bonus_by_level": {str(level): 0},
        "dueling_damage_bonus": 0,
        "true_strike_damage_by_level": {str(level): {"count": 0, "sides": 6}},
        "true_strike_maximum_uses_per_attack_action": 1,
        "true_strike_damage_type": "radiant",
        "true_strike_base_damage_modes": ["radiant_base", "weapon_normal_base"],
        "tactical_policy": {
            "objective": NOMINAL_MODE_ID,
            "true_strike_choice_timing": "before_attack_roll",
            "decision_information": f"{TARGET_KNOWLEDGE_CONTRACT_ID}_and_observed_state",
            "true_strike_use_count": "zero_to_configured_maximum_per_attack_action",
        },
    }


def kinetic_feature(
    entity_id: str,
    *,
    discipline_id: str = "synthetic_discipline",
    delivery: str = "on_hit_rider",
    tier: int = 0,
    damage: dict[str, Any] | None = None,
    secondary_damage: dict[str, Any] | None = None,
    save: str | None = None,
    damage_type: str = "force",
    psi_cost: int = 0,
    repeatability: str = "unlimited",
    targeting_kind: str | None = None,
    armor_class_reduction: int = 0,
    starts_persistent_zone: bool = False,
    damage_repetition: str | None = None,
    damage_timing: str | None = None,
) -> dict[str, Any]:
    tier_row: dict[str, Any] = {
        "tier": tier,
        "damage": damage or {"kind": "none", "resolution": "always"},
    }
    if secondary_damage is not None:
        tier_row["secondary_damage"] = secondary_damage
    if save is not None:
        tier_row["save"] = save
    rule: dict[str, Any] = {
        "entity_id": entity_id,
        "discipline_ids": [discipline_id],
        "damage_delivery": delivery,
        "minimum_level": 7,
        "selectable_advanced_training": False,
        "requires_additional_target": False,
        "damage_tiers": [tier_row],
        "psi_cost": psi_cost,
        "repeatability": repeatability,
        "damage_type": damage_type,
        "ignore_resistance_tiers": [],
    }
    if targeting_kind is not None:
        rule["targeting_by_tier"] = [{"tier": tier, "kind": targeting_kind}]
    if armor_class_reduction:
        rule["armor_class_reduction_by_tier"] = [
            {"tier": tier, "value": armor_class_reduction}
        ]
    if starts_persistent_zone:
        rule["starts_persistent_zone"] = True
    if damage_repetition is not None:
        rule["damage_repetition"] = damage_repetition
    if damage_timing is not None:
        rule["damage_timing"] = damage_timing
    return rule


def synthetic_kinetic_model(
    *features: dict[str, Any],
    level: int = 7,
    proficiency_bonus: int = 3,
    strike_die: int = 8,
    psi_points: int = 0,
    attack_bonus: int = 5,
    psi_modifier: int = 5,
    discipline_id: str = "synthetic_discipline",
    discipline_damage_type: str = "slashing",
    graze: bool = False,
    tier_minimum_levels: dict[int, int] | None = None,
    mastery: dict[str, Any] | None = None,
) -> SyntheticProgressionModel:
    model = SyntheticProgressionModel(
        level=level,
        proficiency_bonus=proficiency_bonus,
        strike_die=strike_die,
        psi_points=psi_points,
        kv_attack_bonus=attack_bonus,
        psi_modifier=psi_modifier,
    )
    discipline: dict[str, Any] = {
        "damage_type": discipline_damage_type,
        "signature_save": "dexterity",
    }
    if graze:
        discipline["graze_damage"] = "psionic_ability_modifier"
    model.disciplines = {discipline_id: discipline}
    model.features = {str(feature["entity_id"]): feature for feature in features}
    minimums = tier_minimum_levels or {0: 7, 1: 7, 2: 15}
    model.projection["progressions"]["tier_minimum_levels"] = [
        {"tier": tier, "minimum_level": minimum_level}
        for tier, minimum_level in sorted(minimums.items())
    ]
    if mastery is not None:
        model.projection["core"]["overload"]["mastery"] = mastery
    return model


def solve_synthetic_kinetic(
    model: SyntheticProgressionModel,
    config: dict[str, Any],
    target: SyntheticDamageTarget,
    *,
    discipline_id: str = "synthetic_discipline",
    cluster_size: int = 1,
) -> DamageSolution:
    return solve_kinetic_vanguard(
        model,
        config,
        target,  # type: ignore[arg-type]
        model.level,
        discipline_id,
        cluster_size,
    )


class ExactPrimitiveIntegrationTests(unittest.TestCase):
    def test_s01_s02_attack_outcomes_match_exact_frozen_probabilities(self) -> None:
        target = knowledge(ac=15)
        ordinary = dict(attack_outcome_distribution(target, 5))
        advantage = dict(attack_outcome_distribution(target, 5, advantage=True))
        self.assertEqual(
            ordinary,
            {
                "miss": frozen_value("S01", "miss_probability"),
                "hit": frozen_value("S01", "hit_probability"),
                "critical": frozen_value("S01", "critical_probability"),
            },
        )
        self.assertEqual(
            advantage,
            {
                "miss": frozen_value("S02", "miss_probability"),
                "hit": frozen_value("S02", "hit_probability"),
                "critical": frozen_value("S02", "critical_probability"),
            },
        )
        self.assertTrue(all(isinstance(value, Fraction) for value in ordinary.values()))
        self.assertTrue(all(isinstance(value, Fraction) for value in advantage.values()))

    def test_s05_s07_s10_s45_defense_and_rounding_order(self) -> None:
        resisted_fire = knowledge(resistances=frozenset({"fire"}))
        self.assertEqual(
            expected_typed_packet(resisted_fire, "fire", ((1, 6, None),), 1),
            frozen_value("S05", "expected_damage"),
        )

        vulnerable_fire = knowledge(vulnerabilities=frozenset({"fire"}))
        cancelling_fire = knowledge(
            resistances=frozenset({"fire"}),
            vulnerabilities=frozenset({"fire"}),
        )
        self.assertEqual(
            apply_defense(vulnerable_fire, "fire", 9),
            frozen_value("S07", "vulnerable_damage"),
        )
        self.assertEqual(
            apply_defense(cancelling_fire, "fire", 9),
            frozen_value("S07", "cancelled_damage"),
        )
        immune_vulnerable_fire = knowledge(
            immunities=frozenset({"fire"}),
            vulnerabilities=frozenset({"fire"}),
        )
        self.assertEqual(
            apply_defense(immune_vulnerable_fire, "fire", 9),
            frozen_value("S06", "damage"),
        )
        self.assertEqual(
            expected_typed_packet(
                immune_vulnerable_fire,
                "fire",
                (),
                9,
            ),
            frozen_value("S06", "damage"),
        )

        holdout_target = knowledge(
            resistances=frozenset({"force"}),
            immunities=frozenset({"fire"}),
        )
        force_neutral = knowledge(immunities=frozenset({"fire"}))
        self.assertEqual(
            expected_typed_packet(holdout_target, "fire", ((1, 8, None),), 5),
            frozen_value("S10", "normal_fire"),
        )
        self.assertEqual(
            expected_typed_packet(
                force_neutral,
                "force",
                ((1, 8, None),),
                5,
                raw_divisor=2,
            ),
            frozen_value("S10", "holdout_without_force_resistance"),
        )
        self.assertEqual(
            expected_typed_packet(
                holdout_target,
                "force",
                ((1, 8, None),),
                5,
                raw_divisor=2,
            ),
            frozen_value("S10", "force_resisted_holdout"),
        )

        self.assertEqual(
            apply_defense(resisted_fire, "fire", 9),
            frozen_value("S45", "resisted_damage"),
        )
        self.assertEqual(
            apply_defense(resisted_fire, "fire", 9, ignore_resistance=True),
            frozen_value("S45", "bypass_damage"),
        )
        immune_fire = knowledge(immunities=frozenset({"fire"}))
        self.assertEqual(
            apply_defense(immune_fire, "fire", 9, ignore_resistance=True),
            frozen_value("S45", "immune_damage"),
        )

    def test_s09_s21_s37_exact_save_correction_and_aggregation(self) -> None:
        saves = {
            "strength": 0,
            "dexterity": 0,
            "constitution": 0,
            "intelligence": 0,
            "wisdom": 4,
            "charisma": 0,
        }
        normal = knowledge(saves=saves)
        resistant = knowledge(saves=saves, magic_resistance=True)
        self.assertEqual(
            save_success_probability(normal, "wisdom", 15),
            frozen_value("S09", "normal_save_probability"),
        )
        self.assertEqual(
            save_success_probability(resistant, "wisdom", 15),
            frozen_value("S09", "magic_resistance_save_probability"),
        )

        save_target = knowledge()
        save_success = save_success_probability(save_target, "dexterity", 11)
        full = expected_typed_packet(save_target, "force", ((1, 6, None),))
        successful_half = expected_typed_packet(
            save_target,
            "force",
            ((1, 6, None),),
            raw_divisor=2,
        )
        half_on_success = NominalKernel.expectation(
            (
                (
                    1 - save_success,
                    DamageValue(primary=full, aggregate=full),
                ),
                (
                    save_success,
                    DamageValue(
                        primary=successful_half,
                        aggregate=successful_half,
                    ),
                ),
            )
        ).primary
        self.assertEqual(save_success, Fraction(1, 2))
        self.assertEqual(full, frozen_value("S08", "full_branch_mean"))
        self.assertEqual(
            successful_half,
            frozen_value("S08", "success_branch_mean"),
        )
        self.assertEqual(half_on_success, frozen_value("S08", "expected_damage"))

        precision = dict(die_distribution(1, 8))
        precision_success = sum(
            (probability for roll, probability in precision.items() if roll >= 3),
            Fraction(),
        )
        precision_expected = precision_success * 10 + (1 - precision_success) * 5
        self.assertEqual(precision_success, frozen_value("S21", "success_probability"))
        self.assertEqual(precision_expected, frozen_value("S21", "expected_damage"))

        aggregate = NominalKernel.expectation(
            (
                (Fraction(1, 3), DamageValue(primary=Fraction(3), aggregate=Fraction(3))),
                (Fraction(2, 3), DamageValue(primary=Fraction(6), aggregate=Fraction(6))),
            )
        )
        self.assertEqual(aggregate.primary, frozen_value("S37", "weighted_value"))
        self.assertEqual(aggregate.aggregate, frozen_value("S37", "weighted_value"))

    def test_s36_exact_damage_cost_and_canonical_tie_order(self) -> None:
        def proposal(values: list[Any]) -> Proposal:
            return Proposal(
                f"tie_probe.{values[6]}",
                DamageValue(
                    primary=fraction(values[1]),
                    aggregate=fraction(values[0]),
                    cost=ResourceCost(
                        self_damage=fraction(values[2]),
                        horizon_limited=fraction(values[3]),
                        persistent_pool=fraction(values[4]),
                        refreshable=fraction(values[5]),
                    ),
                ),
            )

        winners = []
        for pair in CASES["S36"]["inputs"]["tie_pairs"]:
            selected = NominalKernel.choose((proposal(pair["left"]), proposal(pair["right"])))
            winners.append(selected.action_id.removeprefix("tie_probe."))
        self.assertEqual(winners, CASES["S36"]["contract_expectations"]["winners"])

        costly_more_damage = Proposal(
            "tie_probe.costly",
            DamageValue(
                primary=Fraction(0),
                aggregate=Fraction(11),
                cost=ResourceCost(Fraction(9), Fraction(9), Fraction(9), Fraction(9)),
            ),
        )
        cheap_less_damage = Proposal(
            "tie_probe.cheap",
            DamageValue(primary=Fraction(10), aggregate=Fraction(10)),
        )
        self.assertEqual(
            NominalKernel.choose((cheap_less_damage, costly_more_damage)).action_id,
            "tie_probe.costly",
        )


class SharedNominalProviderIntegrationTests(unittest.TestCase):
    def solve_eldritch_knight(
        self,
        *,
        level: int,
        attacks_per_action: int,
        action_slots_by_round: tuple[int, int, int],
        target: SyntheticDamageTarget,
        studied_attacks: bool = False,
        combat_prowess: bool = False,
    ) -> DamageSolution:
        model = SyntheticProgressionModel(level=level, proficiency_bonus=2)
        return solve_comparator(
            model,
            nominal_config(
                level=level,
                attacks_per_action=attacks_per_action,
                action_slots_by_round=action_slots_by_round,
                studied_attacks=studied_attacks,
                combat_prowess=combat_prowess,
            ),
            {"damage": {"eldritch_knight": simple_eldritch_knight_row(level)}},
            target,  # type: ignore[arg-type]
            level,
            "eldritch_knight",
        )

    def test_s03_studied_carry_matches_exact_two_attack_oracle(self) -> None:
        model = SyntheticProgressionModel(level=15, proficiency_bonus=2)
        row = simple_eldritch_knight_row(15)
        target = knowledge(ac=15)
        ordinary = eldritch_knight_single_attack_expected(
            model, row, target, 15, "ordinary"
        )
        advantage = eldritch_knight_single_attack_expected(
            model, row, target, 15, "ordinary", advantage=True
        )
        ordinary_miss = dict(attack_outcome_distribution(target, 5))["miss"]
        two_attack_expected = ordinary + ordinary_miss * advantage + (
            1 - ordinary_miss
        ) * ordinary
        self.assertEqual(
            two_attack_expected,
            frozen_value("S03", "two_attack_expected_damage"),
        )
        self.assertEqual(2 * ordinary, Fraction(87, 10))
        self.assertFalse(
            studied_state_after_final_attack(True, final_hit=True),
            "the prior Studied benefit is consumed when its attack hits",
        )
        self.assertTrue(
            studied_state_after_final_attack(True, final_hit=False),
            "a final miss establishes a fresh Studied benefit",
        )
        self.assertFalse(
            studied_state_after_final_attack(False, final_hit=False),
            "the mechanic remains disabled when the level feature is absent",
        )

        three_attacks = self.solve_eldritch_knight(
            level=15,
            attacks_per_action=3,
            action_slots_by_round=(1, 1, 1),
            target=synthetic_projection_target(ac=15),
            studied_attacks=True,
        )
        advantage_miss = dict(
            attack_outcome_distribution(target, 5, advantage=True)
        )["miss"]
        studied_probability = Fraction()
        expected_horizon = Fraction()
        for _attack in range(9):
            expected_horizon += (
                (1 - studied_probability) * ordinary
                + studied_probability * advantage
            )
            studied_probability = (
                (1 - studied_probability) * ordinary_miss
                + studied_probability * advantage_miss
            )
        expected_dpr = Fraction(
            49448754197395951472721,
            3276800000000000000000,
        )
        self.assertEqual(expected_horizon / 3, expected_dpr)
        self.assertEqual(three_attacks.primary_dpr, expected_dpr)
        self.assertEqual(
            three_attacks.trace,
            (
                "R1[A1[ordinary:hit,ordinary:hit,ordinary:hit]]",
                "R2[A1[ordinary:hit,ordinary:hit,ordinary:hit]]",
                "R3[A1[ordinary:hit,ordinary:hit,ordinary:hit]]",
                "representative=locally-modal-path",
                "policy=exact-observed-state",
            ),
        )

    def test_s04_prowess_hit_instead_does_not_establish_studied(self) -> None:
        one_attack = self.solve_eldritch_knight(
            level=20,
            attacks_per_action=1,
            action_slots_by_round=(1, 1, 1),
            target=synthetic_projection_target(ac=15),
            studied_attacks=True,
            combat_prowess=True,
        )
        self.assertEqual(
            one_attack.primary_dpr,
            frozen_value("S04", "expected_damage"),
        )

    def test_s32_s33_public_solver_consumes_every_configured_attack(self) -> None:
        for sentinel_id, level in (("S32", 7), ("S33", 11)):
            with self.subTest(sentinel_id=sentinel_id):
                fixture = CASES[sentinel_id]["inputs"]
                model = SyntheticProgressionModel(level=level, proficiency_bonus=2)
                row = simple_eldritch_knight_row(level)
                target = knowledge(ac=15)
                unit = eldritch_knight_single_attack_expected(
                    model, row, target, level, "ordinary"
                )
                solution = solve_comparator(
                    model,
                    nominal_config(
                        level=level,
                        attacks_per_action=int(fixture["attacks_per_action"]),
                        action_slots_by_round=tuple(fixture["action_slots_by_round"]),  # type: ignore[arg-type]
                    ),
                    {"damage": {"eldritch_knight": row}},
                    synthetic_projection_target(ac=15),  # type: ignore[arg-type]
                    level,
                    "eldritch_knight",
                )
                self.assertEqual(
                    solution.primary_dpr / unit,
                    frozen_value(sentinel_id, "dpr"),
                )
                self.assertEqual(
                    sum(entry.count("ordinary:") for entry in solution.trace[:3]),
                    int(frozen_value(sentinel_id, "total_damage")),
                )

    def test_s34_s35_schedules_bind_stateful_public_traces(self) -> None:
        studied_fixture = CASES["S34"]
        studied = self.solve_eldritch_knight(
            level=15,
            attacks_per_action=3,
            action_slots_by_round=(2, 1, 1),
            target=synthetic_projection_target(ac=18),
            studied_attacks=True,
        )
        unstudied = self.solve_eldritch_knight(
            level=15,
            attacks_per_action=3,
            action_slots_by_round=(2, 1, 1),
            target=synthetic_projection_target(ac=18),
        )
        self.assertEqual(
            [entry.count("ordinary:") for entry in studied.trace[:3]],
            studied_fixture["contract_expectations"]["attacks_by_round"],
        )
        scripted_hits = sum(
            attacks - 1
            for attacks in studied_fixture["contract_expectations"]["attacks_by_round"]
        )
        self.assertEqual(Fraction(scripted_hits), frozen_value("S34", "total_hits"))
        self.assertEqual(Fraction(scripted_hits, 3), frozen_value("S34", "dpr"))
        self.assertGreater(studied.primary_dpr, unstudied.primary_dpr)

        prowess_fixture = CASES["S35"]
        prowess = self.solve_eldritch_knight(
            level=20,
            attacks_per_action=4,
            action_slots_by_round=(2, 2, 1),
            target=synthetic_projection_target(ac=100),
            combat_prowess=True,
        )
        attacks_by_round = [entry.count("ordinary:") for entry in prowess.trace[:3]]
        self.assertEqual(
            attacks_by_round,
            prowess_fixture["contract_expectations"]["attacks_by_round"],
        )
        self.assertEqual(
            Fraction(sum(attacks_by_round)),
            frozen_value("S35", "total_hits"),
        )
        self.assertEqual(
            Fraction(sum(attacks_by_round), 3),
            frozen_value("S35", "dpr"),
        )
        self.assertEqual(
            Fraction(sum(entry.count("miss.combat_prowess") for entry in prowess.trace[:3])),
            frozen_value("S35", "prowess_uses"),
        )


class BattleMasterPublicIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = SyntheticProgressionModel()
        self.row = battle_master_row()
        self.target = knowledge()

    def maneuver_increment(self, sides: int, *, critical: bool = False) -> Fraction:
        return battle_master_hit_damage(
            self.model,
            self.row,
            self.target,
            7,
            critical=critical,
            maneuver_sides=sides,
        ) - battle_master_hit_damage(
            self.model,
            self.row,
            self.target,
            7,
            critical=critical,
        )

    def test_s20_s22_s23_s24_exact_maneuver_and_resource_mechanics(self) -> None:
        d8 = self.maneuver_increment(8)
        critical_d8 = self.maneuver_increment(8, critical=True)
        d10 = self.maneuver_increment(10)
        self.assertEqual(d8, frozen_value("S20", "noncritical_increment"))
        self.assertEqual(critical_d8, frozen_value("S20", "critical_increment"))

        s22 = CASES["S22"]["inputs"]
        self.assertEqual(
            Fraction(s22["forced_hits"] * s22["base_damage_each"]) + d8,
            frozen_value("S22", "total_damage"),
        )
        self.assertEqual(
            ResourceCost(persistent_pool=Fraction(1)).persistent_pool,
            Fraction(CASES["S22"]["contract_expectations"]["dice_spent"]),
        )

        self.assertEqual(d10 + d8, frozen_value("S23", "total_increment"))
        combined_cost = ResourceCost(persistent_pool=Fraction(1)) + ResourceCost(
            refreshable=Fraction(1)
        )
        self.assertEqual(
            combined_cost.persistent_pool,
            Fraction(CASES["S23"]["contract_expectations"]["normal_dice_spent"]),
        )
        self.assertEqual(
            combined_cost.refreshable,
            Fraction(CASES["S23"]["contract_expectations"]["relentless_tokens_spent"]),
        )

        self.assertEqual(d8, frozen_value("S24", "increment"))
        self.assertTrue(CASES["S24"]["contract_expectations"]["refresh_next_turn"])

        relentless_model = SyntheticProgressionModel(level=15)
        enabled_row = battle_master_row(
            level=15,
            superiority_die=10,
            superiority_pool=0,
            relentless_minimum_level=15,
            hew_enabled=False,
        )
        disabled_row = battle_master_row(
            level=15,
            superiority_die=10,
            superiority_pool=0,
            relentless_minimum_level=99,
            hew_enabled=False,
        )
        config = nominal_config(
            level=15,
            attacks_per_action=1,
            action_slots_by_round=(1, 1, 1),
        )
        enabled = solve_comparator(
            relentless_model,
            config,
            {"damage": {"battle_master": enabled_row}},
            synthetic_projection_target(ac=0),  # type: ignore[arg-type]
            15,
            "battle_master",
        )
        disabled = solve_comparator(
            relentless_model,
            config,
            {"damage": {"battle_master": disabled_row}},
            synthetic_projection_target(ac=0),  # type: ignore[arg-type]
            15,
            "battle_master",
        )
        self.assertEqual(
            enabled.primary_dpr - disabled.primary_dpr,
            frozen_value("S24", "increment"),
        )

    def test_s25_s26_gwf_gwm_graze_and_nonrecursive_hew_packets(self) -> None:
        gwf_mean = sum(
            Fraction(roll) * probability
            for roll, probability in die_distribution(1, 6, minimum=3)
        )
        self.assertEqual(gwf_mean, frozen_value("S25", "gwf_die_mean"))

        normal = battle_master_hit_damage(
            self.model, self.row, self.target, 7
        )
        critical = battle_master_hit_damage(
            self.model, self.row, self.target, 7, critical=True
        )
        hew = battle_master_hit_damage(
            self.model,
            self.row,
            self.target,
            7,
            part_of_attack_action=False,
        )
        self.assertEqual(
            normal - frozen_value("S25", "normal_weapon_dice"),
            frozen_value("S25", "attack_action_flat"),
        )
        self.assertEqual(
            critical - frozen_value("S25", "critical_weapon_dice"),
            frozen_value("S25", "attack_action_flat"),
        )
        self.assertEqual(
            hew - frozen_value("S25", "normal_weapon_dice"),
            frozen_value("S25", "hew_flat"),
        )
        self.assertEqual(
            apply_defense(
                self.target,
                "slashing",
                int(CASES["S25"]["inputs"]["graze"]),
            ),
            frozen_value("S25", "graze_damage"),
        )
        self.assertFalse(CASES["S25"]["contract_expectations"]["gwm_on_hew"])

        s26_row = battle_master_row(
            ability_modifier=0,
            magic_weapon_bonus=0,
            weapon_count=1,
            weapon_sides=6,
            great_weapon_fighting=False,
            superiority_pool=0,
            hew_enabled=False,
        )
        critical_trigger = battle_master_hit_damage(
            self.model,
            s26_row,
            self.target,
            7,
            critical=True,
            part_of_attack_action=False,
        )
        one_followup = battle_master_hit_damage(
            self.model,
            s26_row,
            self.target,
            7,
            part_of_attack_action=False,
        )
        self.assertEqual(
            critical_trigger + one_followup,
            frozen_value("S26", "total_damage"),
        )
        self.assertFalse(CASES["S26"]["contract_expectations"]["recursive_hew"])

        hew_model = SyntheticProgressionModel(proficiency_bonus=0)
        enabled_row = battle_master_row(
            ability_modifier=0,
            magic_weapon_bonus=0,
            weapon_count=1,
            weapon_sides=6,
            great_weapon_fighting=False,
            superiority_pool=0,
            relentless_minimum_level=99,
            hew_enabled=True,
        )
        disabled_row = battle_master_row(
            ability_modifier=0,
            magic_weapon_bonus=0,
            weapon_count=1,
            weapon_sides=6,
            great_weapon_fighting=False,
            superiority_pool=0,
            relentless_minimum_level=99,
            hew_enabled=False,
        )
        config = nominal_config(attacks_per_action=1)
        enabled = solve_comparator(
            hew_model,
            config,
            {"damage": {"battle_master": enabled_row}},
            synthetic_projection_target(ac=0),  # type: ignore[arg-type]
            7,
            "battle_master",
        )
        disabled = solve_comparator(
            hew_model,
            config,
            {"damage": {"battle_master": disabled_row}},
            synthetic_projection_target(ac=0),  # type: ignore[arg-type]
            7,
            "battle_master",
        )
        hew_dpr_increment = enabled.primary_dpr - disabled.primary_dpr
        self.assertEqual(hew_dpr_increment, Fraction(7, 40))
        self.assertEqual(
            critical_trigger + 20 * hew_dpr_increment,
            frozen_value("S26", "total_damage"),
        )

    def test_s21_precision_spends_before_result_and_public_solver_uses_it(self) -> None:
        corrected = DamageValue(primary=Fraction(10), aggregate=Fraction(10))
        failed = DamageValue(primary=Fraction(5), aggregate=Fraction(5))
        precision = battle_master_precision_expected(
            3,
            8,
            corrected,
            failed,
            cost=ResourceCost(persistent_pool=Fraction(1)),
        )
        success = (precision.primary - failed.primary) / (
            corrected.primary - failed.primary
        )
        self.assertEqual(success, frozen_value("S21", "success_probability"))
        self.assertEqual(precision.primary, frozen_value("S21", "expected_damage"))
        self.assertEqual(precision.aggregate, frozen_value("S21", "expected_damage"))
        self.assertEqual(precision.cost.persistent_pool, Fraction(1))
        self.assertEqual(precision.cost.refreshable, Fraction())

        relentless_precision = battle_master_precision_expected(
            3,
            8,
            corrected,
            failed,
            cost=ResourceCost(refreshable=Fraction(1)),
        )
        self.assertEqual(relentless_precision.primary, precision.primary)
        self.assertEqual(relentless_precision.cost.persistent_pool, Fraction())
        self.assertEqual(relentless_precision.cost.refreshable, Fraction(1))

        for level, pool in ((7, 1), (15, 0)):
            with self.subTest(level=level, pool=pool):
                model = SyntheticProgressionModel(level=level)
                row = battle_master_row(
                    level=level,
                    ability_modifier=2,
                    magic_weapon_bonus=0,
                    weapon_count=1,
                    weapon_sides=2,
                    great_weapon_fighting=False,
                    superiority_die=8 if level == 7 else 10,
                    superiority_pool=pool,
                    hew_enabled=False,
                )
                projected = synthetic_projection_target(ac=15)
                solution = solve_comparator(
                    model,
                    nominal_config(
                        level=level,
                        attacks_per_action=1,
                        action_slots_by_round=(1, 0, 0),
                    ),
                    {"damage": {"battle_master": row}},
                    projected,  # type: ignore[arg-type]
                    level,
                    "battle_master",
                )
                # One attack across a three-round horizon: ordinary hits use
                # one d8, a critical doubles it, and miss corrections 1..8
                # have success probabilities 1, 7/8, ..., 1/8.
                self.assertEqual(solution.primary_dpr, Fraction(125, 48))
                self.assertEqual(solution.aggregate_dpr, Fraction(125, 48))
                self.assertEqual(solution.provider_id, "battle_master")
                self.assertTrue(solution.trace[0].startswith("R1["))
                self.assertIn("representative=locally-modal-path", solution.trace)
                self.assertEqual(projected.validation_calls, 1)


class KineticVanguardPublicIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = SyntheticProgressionModel()

    def test_s11_s12_paid_rider_is_on_hit_only_and_costs_on_a_miss(self) -> None:
        rider = kinetic_feature(
            "fixed_rider",
            damage={"kind": "fixed", "value": 4, "resolution": "always"},
            psi_cost=1,
        )
        model = synthetic_kinetic_model(
            rider,
            proficiency_bonus=2,
            psi_points=1,
            psi_modifier=3,
        )
        config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=3,
        )
        packets = manifested_strike_packet_options(
            model, knowledge(ac=15), "synthetic_discipline", 3, 8
        )
        self.assertEqual(
            packets,
            (("normal", (Fraction(), Fraction(15, 2), Fraction(12))),),
        )
        solution = solve_synthetic_kinetic(
            model, config, synthetic_projection_target(ac=15)
        )
        self.assertEqual(
            3 * solution.primary_dpr,
            frozen_value("S11", "expected_damage"),
        )
        self.assertEqual(solution.trace[0].count("fixed_rider:T0"), 1)

        miss_config = nominal_config(
            attacks_per_action=2,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=3,
        )
        miss_target = synthetic_projection_target(ac=100)
        rider_on_misses = solve_synthetic_kinetic(model, miss_config, miss_target)
        plain_model = synthetic_kinetic_model(
            proficiency_bonus=2,
            psi_points=1,
            psi_modifier=3,
        )
        plain_on_misses = solve_synthetic_kinetic(
            plain_model,
            miss_config,
            synthetic_projection_target(ac=100),
        )
        self.assertEqual(
            3 * (rider_on_misses.primary_dpr - plain_on_misses.primary_dpr),
            Fraction(1, 5),
        )
        self.assertEqual(rider_on_misses.trace[0].count("fixed_rider:T0"), 1)
        self.assertEqual(packets[0][1][0], frozen_value("S12", "damage"))

    def test_s08_s13_saved_rider_floors_each_successful_damage_outcome(self) -> None:
        saved_rider = kinetic_feature(
            "saved_rider",
            damage={
                "kind": "dice",
                "count": 1,
                "sides": 6,
                "resolution": "half_on_success",
            },
            save="dexterity",
            psi_cost=1,
        )
        model = synthetic_kinetic_model(
            saved_rider,
            psi_points=1,
            attack_bonus=0,
            psi_modifier=4,
        )
        plain_model = synthetic_kinetic_model(
            psi_points=1,
            attack_bonus=0,
            psi_modifier=4,
        )
        config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=4,
        )
        saves = {
            "strength": 0,
            "dexterity": 4,
            "constitution": 0,
            "intelligence": 0,
            "wisdom": 0,
            "charisma": 0,
        }
        target = synthetic_projection_target(ac=0, saves=saves)
        solution = solve_synthetic_kinetic(model, config, target)
        control = solve_synthetic_kinetic(
            plain_model,
            config,
            synthetic_projection_target(ac=0, saves=saves),
        )
        conditional_rider = (
            3 * (solution.primary_dpr - control.primary_dpr) / Fraction(19, 20)
        )
        self.assertEqual(
            conditional_rider,
            frozen_value("S13", "expected_rider_damage"),
        )
        self.assertEqual(solution.trace[0].count("saved_rider:T0"), 1)

    def test_s14_repeatability_and_one_rider_per_strike(self) -> None:
        signature = kinetic_feature(
            "signature_rider",
            damage={"kind": "fixed", "value": 5, "resolution": "always"},
        )
        limited = kinetic_feature(
            "limited_rider",
            damage={"kind": "fixed", "value": 6, "resolution": "always"},
            repeatability="once_per_attack_action",
        )
        config = nominal_config(
            attacks_per_action=2,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=0,
        )
        target = synthetic_projection_target(ac=0)
        baseline = solve_synthetic_kinetic(
            synthetic_kinetic_model(attack_bonus=0, psi_modifier=0),
            config,
            target,
        )
        signature_solution = solve_synthetic_kinetic(
            synthetic_kinetic_model(signature, attack_bonus=0, psi_modifier=0),
            config,
            synthetic_projection_target(ac=0),
        )
        self.assertEqual(
            3
            * (signature_solution.primary_dpr - baseline.primary_dpr)
            / Fraction(19, 20),
            frozen_value("S14", "signature_total"),
        )
        self.assertEqual(signature_solution.trace[0].count("signature_rider:T0"), 2)

        limited_solution = solve_synthetic_kinetic(
            synthetic_kinetic_model(limited, attack_bonus=0, psi_modifier=0),
            config,
            synthetic_projection_target(ac=0),
        )
        self.assertEqual(limited_solution.trace[0].count("limited_rider:T0"), 1)
        self.assertEqual(
            limited_solution.trace[0].count(":T0"),
            CASES["S14"]["contract_expectations"]["non_signature_uses"],
        )

    def test_s15_one_tier_two_rider_per_attack_action(self) -> None:
        tier_two = kinetic_feature(
            "tier_two_rider",
            tier=2,
            damage={"kind": "fixed", "value": 10, "resolution": "always"},
        )
        for action_count, oracle_name in (
            (1, "one_action_total"),
            (2, "two_action_total"),
        ):
            with self.subTest(action_count=action_count):
                config = nominal_config(
                    attacks_per_action=2,
                    action_slots_by_round=(action_count, 0, 0),
                    psi_modifier=0,
                )
                model = synthetic_kinetic_model(
                    tier_two,
                    proficiency_bonus=0,
                    attack_bonus=0,
                    psi_modifier=0,
                    tier_minimum_levels={0: 7, 1: 7, 2: 7},
                )
                control_model = synthetic_kinetic_model(
                    proficiency_bonus=0,
                    attack_bonus=0,
                    psi_modifier=0,
                    tier_minimum_levels={0: 7, 1: 7, 2: 7},
                )
                solution = solve_synthetic_kinetic(
                    model, config, synthetic_projection_target(ac=0)
                )
                control = solve_synthetic_kinetic(
                    control_model, config, synthetic_projection_target(ac=0)
                )
                self.assertEqual(
                    3
                    * (solution.primary_dpr - control.primary_dpr)
                    / Fraction(19, 20),
                    frozen_value("S15", oracle_name),
                )
                self.assertEqual(
                    solution.trace[0].count("tier_two_rider:T2"),
                    action_count,
                )

    def test_s16_blood_tax_budget_is_consumed_before_next_declaration(self) -> None:
        tier_two = kinetic_feature(
            "taxed_rider",
            tier=2,
            damage={"kind": "fixed", "value": 10, "resolution": "always"},
        )
        model = synthetic_kinetic_model(
            tier_two,
            proficiency_bonus=4,
            attack_bonus=0,
            psi_modifier=0,
            tier_minimum_levels={0: 7, 1: 7, 2: 7},
        )
        control_model = synthetic_kinetic_model(
            proficiency_bonus=4,
            attack_bonus=0,
            psi_modifier=0,
            tier_minimum_levels={0: 7, 1: 7, 2: 7},
        )
        config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(2, 0, 0),
            psi_modifier=0,
            first_level_hp=8,
            later_level_hp=0,
            blood_tax_hp_fraction="1",
        )
        solution = solve_synthetic_kinetic(
            model, config, synthetic_projection_target(ac=0)
        )
        control = solve_synthetic_kinetic(
            control_model, config, synthetic_projection_target(ac=0)
        )
        fixture = CASES["S16"]["inputs"]
        taxes = [Fraction(model.blood_tax(7, tier)) for tier in fixture["tiers"]]
        self.assertEqual(taxes[0], frozen_value("S16", "tier_zero_cost"))
        self.assertEqual(taxes[1], frozen_value("S16", "tier_one_cost"))
        self.assertEqual(taxes[2], frozen_value("S16", "tier_two_cost"))
        self.assertEqual(
            Fraction(fixture["starting_budget"]) - taxes[2],
            frozen_value("S16", "budget_after_tier_two"),
        )
        self.assertEqual(
            3 * (solution.primary_dpr - control.primary_dpr) / Fraction(19, 20),
            Fraction(10),
        )
        self.assertEqual(solution.trace[0].count("taxed_rider:T2"), 1)

    def test_s17_mastery_activates_on_first_positive_tax_or_locks(self) -> None:
        tier_one = kinetic_feature(
            "tax_one",
            tier=1,
            damage={"kind": "fixed", "value": 10, "resolution": "always"},
            repeatability="once_per_attack_action",
        )
        tier_two = kinetic_feature(
            "tax_two",
            tier=2,
            damage={"kind": "fixed", "value": 10, "resolution": "always"},
            repeatability="once_per_attack_action",
        )
        mastery = {
            "minimum_level": 7,
            "uses_per_rest": 1,
            "minimum_per_overload": 0,
            "blood_tax_divisor": 2,
        }
        model = synthetic_kinetic_model(
            tier_one,
            tier_two,
            proficiency_bonus=6,
            attack_bonus=0,
            psi_modifier=0,
            tier_minimum_levels={0: 7, 1: 7, 2: 7},
            mastery=mastery,
        )
        locked_model = synthetic_kinetic_model(
            tier_one,
            tier_two,
            proficiency_bonus=6,
            attack_bonus=0,
            psi_modifier=0,
            tier_minimum_levels={0: 7, 1: 7, 2: 7},
        )
        config = nominal_config(
            attacks_per_action=2,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=0,
            first_level_hp=9,
            later_level_hp=0,
            blood_tax_hp_fraction="1",
        )
        solution = solve_synthetic_kinetic(
            model, config, synthetic_projection_target(ac=0)
        )
        locked = solve_synthetic_kinetic(
            locked_model, config, synthetic_projection_target(ac=0)
        )
        taxes = CASES["S17"]["inputs"]["taxes"]
        divisor = CASES["S17"]["inputs"]["divisor"]
        self.assertEqual(
            Fraction(sum(tax // divisor for tax in taxes)),
            frozen_value("S17", "activated_tax"),
        )
        self.assertEqual(
            Fraction(sum(taxes)),
            frozen_value("S17", "declined_tax"),
        )
        self.assertIn(";mastery", solution.trace[0])
        self.assertEqual(solution.trace[0].count("tax_one:T1"), 1)
        self.assertEqual(solution.trace[0].count("tax_two:T2"), 1)
        self.assertEqual(
            locked.trace[0].count("tax_one:T1") + locked.trace[0].count("tax_two:T2"),
            1,
        )

    def test_s18_standalone_replaces_one_of_two_action_slots(self) -> None:
        standalone = kinetic_feature(
            "standalone_burst",
            delivery="standalone",
            damage={"kind": "fixed", "value": 9, "resolution": "always"},
        )
        model = synthetic_kinetic_model(
            standalone,
            strike_die=9,
            attack_bonus=0,
            psi_modifier=0,
        )
        config = nominal_config(
            attacks_per_action=2,
            action_slots_by_round=(2, 0, 0),
            psi_modifier=0,
        )
        solution = solve_synthetic_kinetic(
            model, config, synthetic_projection_target(ac=6)
        )
        self.assertEqual(
            3 * solution.primary_dpr,
            frozen_value("S18", "two_slot_total"),
        )
        self.assertEqual(solution.trace[0].count("standalone_burst:T0"), 1)
        self.assertEqual(solution.trace[0].count("attack("), 1)

    def test_s19_cluster_primary_identity_and_aggregate_remainder(self) -> None:
        clustered = kinetic_feature(
            "clustered_rider",
            damage={"kind": "fixed", "value": 4, "resolution": "always"},
            secondary_damage={
                "kind": "fixed",
                "value": 2,
                "resolution": "always",
            },
            targeting_kind="cluster_remainder",
        )
        config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(1, 0, 0),
            cluster_sizes=(1, 3, 6),
            psi_modifier=0,
        )
        for cluster_size, oracle_name in (
            (1, "cluster_one"),
            (3, "cluster_three"),
            (6, "cluster_six"),
        ):
            with self.subTest(cluster_size=cluster_size):
                model = synthetic_kinetic_model(
                    clustered, attack_bonus=0, psi_modifier=0
                )
                control_model = synthetic_kinetic_model(
                    attack_bonus=0, psi_modifier=0
                )
                solution = solve_synthetic_kinetic(
                    model,
                    config,
                    synthetic_projection_target(ac=0),
                    cluster_size=cluster_size,
                )
                control = solve_synthetic_kinetic(
                    control_model,
                    config,
                    synthetic_projection_target(ac=0),
                    cluster_size=cluster_size,
                )
                primary = (
                    3
                    * (solution.primary_dpr - control.primary_dpr)
                    / Fraction(19, 20)
                )
                aggregate = (
                    3
                    * (solution.aggregate_dpr - control.aggregate_dpr)
                    / Fraction(19, 20)
                )
                self.assertEqual(primary, Fraction(4))
                self.assertEqual(aggregate, frozen_value("S19", oracle_name))

    def test_s41_fracture_changes_only_attacks_after_qualifying_hit(self) -> None:
        fracture = kinetic_feature(
            "fracture_rider",
            damage={"kind": "fixed", "value": 1, "resolution": "always"},
            armor_class_reduction=3,
        )
        control_rider = kinetic_feature(
            "fracture_rider",
            damage={"kind": "fixed", "value": 1, "resolution": "always"},
        )
        config = nominal_config(
            attacks_per_action=2,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=3,
        )
        target = knowledge(ac=18)
        before = dict(attack_outcome_distribution(target, 8))
        after = dict(attack_outcome_distribution(target, 8, ac_reduction=3))
        before_land = before["hit"] + before["critical"]
        after_land = after["hit"] + after["critical"]
        self.assertEqual(before_land, frozen_value("S41", "before_hit_probability"))
        self.assertEqual(after_land, frozen_value("S41", "after_hit_probability"))

        solution = solve_synthetic_kinetic(
            synthetic_kinetic_model(
                fracture, attack_bonus=8, psi_modifier=3
            ),
            config,
            synthetic_projection_target(ac=18),
        )
        control = solve_synthetic_kinetic(
            synthetic_kinetic_model(
                control_rider, attack_bonus=8, psi_modifier=3
            ),
            config,
            synthetic_projection_target(ac=18),
        )
        self.assertEqual(
            3 * (solution.primary_dpr - control.primary_dpr),
            Fraction(561, 800),
        )
        self.assertEqual(solution.trace[0].count("fracture_rider:T0"), 2)

    def test_s42_nominal_zone_packets_and_s43_exclusion_remain_static(self) -> None:
        ball_lightning = kinetic_feature(
            "ball_lightning",
            delivery="standalone",
            damage={"kind": "fixed", "value": 4, "resolution": "always"},
            damage_type="psychic",
            targeting_kind="cluster_remainder",
            starts_persistent_zone=True,
            damage_repetition="remaining_round_starts",
        )
        zone_model = synthetic_kinetic_model(
            ball_lightning, attack_bonus=0, psi_modifier=0
        )
        zone_config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(1, 0, 0),
            cluster_sizes=(2,),
            psi_modifier=0,
        )
        zone = solve_synthetic_kinetic(
            zone_model,
            zone_config,
            synthetic_projection_target(
                immunities=frozenset({"slashing", "force"})
            ),
            cluster_size=2,
        )
        self.assertEqual(3 * zone.primary_dpr, Fraction(8))
        self.assertEqual(3 * zone.aggregate_dpr, Fraction(16))
        self.assertIn("ball_lightning:T0", zone.trace[0])
        self.assertEqual(CASES["S42"]["contract_expectations"]["activation_damage"], 0)

        mass_levitation = kinetic_feature(
            "mass_levitation",
            delivery="standalone",
            damage={"kind": "fixed", "value": 99, "resolution": "always"},
            damage_timing="start_of_affected_turn_after_repeat_save",
        )
        excluded_config = nominal_config(
            attacks_per_action=1,
            action_slots_by_round=(1, 0, 0),
            psi_modifier=0,
            excluded_stateful_features=("mass_levitation",),
        )
        excluded = solve_synthetic_kinetic(
            synthetic_kinetic_model(
                mass_levitation, attack_bonus=0, psi_modifier=0
            ),
            excluded_config,
            synthetic_projection_target(ac=0),
        )
        control = solve_synthetic_kinetic(
            synthetic_kinetic_model(attack_bonus=0, psi_modifier=0),
            nominal_config(
                attacks_per_action=1,
                action_slots_by_round=(1, 0, 0),
                psi_modifier=0,
            ),
            synthetic_projection_target(ac=0),
        )
        self.assertEqual(excluded.primary_dpr, control.primary_dpr)
        self.assertNotIn("mass_levitation", "|".join(excluded.trace))

        invalid_mass = dict(mass_levitation)
        invalid_mass["damage_timing"] = "activation"
        with self.assertRaisesRegex(ValueError, "lacks canonical deferred timing"):
            solve_synthetic_kinetic(
                synthetic_kinetic_model(
                    invalid_mass, attack_bonus=0, psi_modifier=0
                ),
                excluded_config,
                synthetic_projection_target(ac=0),
            )

    def test_s10_typed_holdout_packets_flow_through_public_provider(self) -> None:
        target = knowledge(
            resistances=frozenset({"force"}),
            immunities=frozenset({"fire"}),
        )
        options = manifested_strike_packet_options(
            self.model, target, "pyrokinesis", 5, 8
        )
        self.assertEqual(tuple(name for name, _packet in options), ("holdout",))
        holdout = options[0][1]
        self.assertEqual(holdout, (Fraction(1), Fraction(2), Fraction(25, 8)))
        self.assertEqual(holdout[1], frozen_value("S10", "force_resisted_holdout"))

        force_neutral = knowledge(immunities=frozenset({"fire"}))
        neutral_holdout = manifested_strike_packet_options(
            self.model, force_neutral, "pyrokinesis", 5, 8
        )[0][1]
        self.assertEqual(
            neutral_holdout[1],
            frozen_value("S10", "holdout_without_force_resistance"),
        )

        projected = synthetic_projection_target(
            ac=15,
            resistances=frozenset({"force"}),
            immunities=frozenset({"fire"}),
        )
        solution = solve_kinetic_vanguard(
            self.model,
            nominal_config(attacks_per_action=1),
            projected,  # type: ignore[arg-type]
            7,
            "pyrokinesis",
            1,
        )
        self.assertEqual(solution.primary_dpr, Fraction(257, 160))
        self.assertEqual(solution.aggregate_dpr, Fraction(257, 160))
        self.assertEqual(solution.provider_id, "kinetic_vanguard")
        self.assertEqual(
            solution.trace[:3],
            tuple(
                f"R{round_index}[attack(manifested_strike@holdout)]"
                for round_index in range(1, 4)
            ),
        )
        self.assertEqual(projected.validation_calls, 1)

    def test_equal_typed_strikes_survive_pruning_and_full_id_selects_holdout(self) -> None:
        immune = knowledge(immunities=frozenset({"fire", "force"}))
        options = manifested_strike_packet_options(
            self.model, immune, "pyrokinesis", 5, 8
        )
        zero_packet = (Fraction(), Fraction(), Fraction())
        self.assertEqual(options, (("normal", zero_packet), ("holdout", zero_packet)))

        selected = NominalKernel.choose(
            Proposal(
                f"strike.{name}.manifested_strike.payment.none",
                DamageValue(primary=packet[1], aggregate=packet[1]),
            )
            for name, packet in options
        )
        self.assertEqual(
            selected.action_id,
            "strike.holdout.manifested_strike.payment.none",
        )

        projected = synthetic_projection_target(
            immunities=frozenset({"fire", "force"})
        )
        solution = solve_kinetic_vanguard(
            self.model,
            nominal_config(attacks_per_action=1),
            projected,  # type: ignore[arg-type]
            7,
            "pyrokinesis",
            1,
        )
        self.assertEqual(solution.primary_dpr, Fraction())
        self.assertEqual(
            solution.trace[:3],
            tuple(
                f"R{round_index}[attack(manifested_strike@holdout)]"
                for round_index in range(1, 4)
            ),
        )


class EldritchKnightPublicIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = SyntheticProgressionModel()
        self.row = eldritch_knight_row()

    def test_s31_true_strike_is_optional_and_zero_replacements_win(self) -> None:
        target = knowledge(ac=15)
        ordinary = eldritch_knight_single_attack_expected(
            self.model, self.row, target, 7, "ordinary"
        )
        radiant = eldritch_knight_single_attack_expected(
            self.model, self.row, target, 7, "radiant_base"
        )
        normal_base = eldritch_knight_single_attack_expected(
            self.model, self.row, target, 7, "weapon_normal_base"
        )
        self.assertEqual(ordinary, frozen_value("S31", "ordinary_attack"))
        self.assertEqual(radiant, frozen_value("S31", "true_strike_attack"))
        self.assertEqual(normal_base, frozen_value("S31", "true_strike_attack"))
        zero_replacements = 2 * ordinary
        one_replacement = ordinary + max(radiant, normal_base)
        self.assertEqual(
            zero_replacements,
            frozen_value("S31", "zero_replacements_action"),
        )
        self.assertEqual(
            one_replacement,
            frozen_value("S31", "one_replacement_action"),
        )
        self.assertGreater(zero_replacements, one_replacement)

        projected = synthetic_projection_target(ac=15)
        config = nominal_config()
        solution = solve_comparator(
            self.model,
            config,
            {"damage": {"eldritch_knight": self.row}},
            projected,  # type: ignore[arg-type]
            7,
            "eldritch_knight",
        )
        self.assertIsInstance(solution, DamageSolution)
        self.assertEqual(solution.mode_id, NOMINAL_MODE_ID)
        self.assertEqual(solution.provider_id, "eldritch_knight")
        frozen_action_schedule = Fraction(
            sum(config["fighter_progression"]["7"]["action_slots_by_round"]), 3
        )
        self.assertEqual(solution.primary_dpr, zero_replacements * frozen_action_schedule)
        self.assertEqual(solution.aggregate_dpr, zero_replacements * frozen_action_schedule)
        self.assertEqual(
            solution.trace[:3],
            tuple(
                f"R{round_index}[A1[ordinary:hit,ordinary:hit]]"
                for round_index in range(1, 4)
            ),
        )
        self.assertEqual(projected.validation_calls, 1)

    def test_s47_s48_each_true_strike_base_mode_can_win(self) -> None:
        slashing_immune = knowledge(ac=15, immunities=frozenset({"slashing"}))
        radiant_immune = knowledge(ac=15, immunities=frozenset({"radiant"}))

        radiant_wins = eldritch_knight_single_attack_expected(
            self.model, self.row, slashing_immune, 7, "radiant_base"
        )
        normal_loses = eldritch_knight_single_attack_expected(
            self.model, self.row, slashing_immune, 7, "weapon_normal_base"
        )
        self.assertEqual(radiant_wins, frozen_value("S47", "radiant_base"))
        self.assertEqual(normal_loses, frozen_value("S47", "weapon_normal_base"))
        self.assertGreater(radiant_wins, normal_loses)

        radiant_loses = eldritch_knight_single_attack_expected(
            self.model, self.row, radiant_immune, 7, "radiant_base"
        )
        normal_wins = eldritch_knight_single_attack_expected(
            self.model, self.row, radiant_immune, 7, "weapon_normal_base"
        )
        self.assertEqual(radiant_loses, frozen_value("S48", "radiant_base"))
        self.assertEqual(normal_wins, frozen_value("S48", "weapon_normal_base"))
        self.assertGreater(normal_wins, radiant_loses)

    def test_s49_like_typed_packets_combine_and_critical_flats_do_not_double(self) -> None:
        target = knowledge(
            resistances=frozenset({"slashing", "radiant"})
        )
        self.assertEqual(
            eldritch_knight_hit_damage(self.row, target, 7, "radiant_base"),
            frozen_value("S49", "radiant_noncritical"),
        )
        self.assertEqual(
            eldritch_knight_hit_damage(self.row, target, 7, "weapon_normal_base"),
            frozen_value("S49", "split_noncritical"),
        )
        self.assertEqual(
            eldritch_knight_hit_damage(
                self.row, target, 7, "radiant_base", critical=True
            ),
            frozen_value("S49", "radiant_critical"),
        )
        self.assertEqual(
            eldritch_knight_hit_damage(
                self.row, target, 7, "weapon_normal_base", critical=True
            ),
            frozen_value("S49", "split_critical"),
        )

        neutral = knowledge()
        self.assertEqual(
            eldritch_knight_hit_damage(
                self.row, neutral, 7, "radiant_base", critical=True
            ),
            frozen_value("S49", "raw_neutral_critical"),
        )

        fixed = CASES["S49"]["inputs"]
        hit = fixed["fixed_noncritical_faces"]
        critical = fixed["fixed_critical_faces"]
        fixed_radiant_hit = apply_defense(
            target,
            "radiant",
            sum(hit["weapon"]) + sum(hit["upgrade"]) + fixed["flat"],
        )
        fixed_split_hit = apply_defense(
            target, "slashing", sum(hit["weapon"]) + fixed["flat"]
        ) + apply_defense(target, "radiant", sum(hit["upgrade"]))
        fixed_radiant_critical = apply_defense(
            target,
            "radiant",
            sum(critical["weapon"]) + sum(critical["upgrade"]) + fixed["flat"],
        )
        fixed_split_critical = apply_defense(
            target, "slashing", sum(critical["weapon"]) + fixed["flat"]
        ) + apply_defense(target, "radiant", sum(critical["upgrade"]))
        self.assertEqual(
            fixed_radiant_hit, frozen_value("S49", "fixed_radiant_noncritical")
        )
        self.assertEqual(
            fixed_split_hit, frozen_value("S49", "fixed_split_noncritical")
        )
        self.assertEqual(
            fixed_radiant_critical, frozen_value("S49", "fixed_radiant_critical")
        )
        self.assertEqual(
            fixed_split_critical, frozen_value("S49", "fixed_split_critical")
        )


class TargetKnowledgeAndBoundaryIntegrationTests(unittest.TestCase):
    def test_nominal_optimization_contract_fails_closed_before_target_projection(self) -> None:
        config = nominal_config()
        config["damage_matrix"]["optimization"]["scope"] = "mutated_scope"
        projected = synthetic_projection_target()
        with self.assertRaisesRegex(ValueError, "optimization contract"):
            solve_comparator(
                SyntheticProgressionModel(),
                config,
                {"damage": {"eldritch_knight": eldritch_knight_row()}},
                projected,  # type: ignore[arg-type]
                7,
                "eldritch_knight",
            )
        self.assertEqual(projected.validation_calls, 0)

    def test_s46_projection_adapter_is_equal_static_and_contains_no_future_or_hp_state(self) -> None:
        fixture = CASES["S46"]["inputs"]
        static = fixture["static_target"]
        projected = [
            synthetic_projection_target(
                ac=static["armor_class"],
                saves=dict(static["saves"]),
                magic_resistance=static["magic_resistance"],
                resistances=frozenset(static["resistances"]),
                immunities=frozenset(static["immunities"]),
                vulnerabilities=frozenset(static["vulnerabilities"]),
                size=static["size"],
                creature_type=static["creature_type"],
            )
            for _provider in fixture["providers"]
        ]
        for target in projected:
            target.legendary_resistance = static["legendary_resistance_uses"]
            target.legendary_resistance_policy = static["legendary_resistance_policy"]
        views = [TargetKnowledge.from_damage_target(target) for target in projected]  # type: ignore[arg-type]
        self.assertEqual(len({view.digest for view in views}), 1)
        self.assertTrue(all(target.validation_calls == 1 for target in projected))
        self.assertTrue(all(view.contract_id == TARGET_KNOWLEDGE_CONTRACT_ID for view in views))

        low_hp = synthetic_projection_target(
            target_sha256="opaque-source-sha-a",
            hp=23,
            current_hp=1,
        )
        high_hp = synthetic_projection_target(
            target_sha256="opaque-source-sha-b",
            hp=999,
            current_hp=999,
        )
        low_hp_view = TargetKnowledge.from_damage_target(low_hp)  # type: ignore[arg-type]
        high_hp_view = TargetKnowledge.from_damage_target(high_hp)  # type: ignore[arg-type]
        self.assertNotEqual(low_hp.target_sha256, high_hp.target_sha256)
        self.assertNotEqual((low_hp.hp, low_hp.current_hp), (high_hp.hp, high_hp.current_hp))
        self.assertEqual(low_hp_view, high_hp_view)
        self.assertEqual(low_hp_view.digest, high_hp_view.digest)

        target_fields = {field.name for field in fields(TargetKnowledge)}
        self.assertTrue(set(fixture["future_fields"]).isdisjoint(target_fields))
        self.assertNotIn("target_sha256", target_fields)
        self.assertNotIn("hp", target_fields)
        self.assertNotIn("current_hp", target_fields)
        self.assertNotIn("alive", target_fields)
        expected = CASES["S46"]["contract_expectations"]
        self.assertTrue(expected["provider_views_equal"])
        self.assertTrue(expected["future_fields_absent"])
        self.assertFalse(expected["nominal_dynamic_hp_present"])
        self.assertTrue(expected["finite_dynamic_hp_present"])

    def test_every_deferred_finite_facet_fails_closed_before_provider_inputs(self) -> None:
        cases_with_finite_facets = {
            sentinel_id
            for sentinel_id, case in CASES.items()
            if any(facet["phase"] == "pr2" for facet in case["integration_facets"])
        }
        self.assertEqual(
            cases_with_finite_facets,
            {"S27", "S28", "S29", "S30", "S38", "S39", "S40", "S42", "S44", "S46", "S50"},
        )
        reject_unsupported_mode(NOMINAL_MODE_ID)
        for mode_id in (*DEFERRED_FINITE_MODE_IDS, "finite_hp"):
            with self.subTest(mode_id=mode_id):
                with self.assertRaisesRegex(UnsupportedDamageMode, "PR2"):
                    reject_unsupported_mode(mode_id)
                with self.assertRaisesRegex(UnsupportedDamageMode, "PR2"):
                    solve_comparator(
                        None, None, None, None, 7, "eldritch_knight", mode_id=mode_id  # type: ignore[arg-type]
                    )
                with self.assertRaisesRegex(UnsupportedDamageMode, "PR2"):
                    solve_kinetic_vanguard(
                        None, None, None, 7, "pyrokinesis", 1, mode_id=mode_id  # type: ignore[arg-type]
                    )

    def test_focused_module_has_no_roster_matrix_report_or_evaluator_entrypoint(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        called_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
        self.assertTrue(
            {
                "harness.damage_harness",
                "harness.damage_report",
                "harness.creature_catalog",
                "harness.creature_damage_projection",
                "harness.readme_damage",
                "harness.model",
                "concurrent.futures",
                "multiprocessing",
            }.isdisjoint(imported_modules)
        )
        self.assertEqual(
            {module for module in imported_modules if module.startswith("harness")},
            {
                "harness.damage_contract",
                "harness.tests.damage_sentinel_oracles",
            },
        )
        self.assertTrue(
            {
                "run",
                "run_damage",
                "load_profile",
                "project_profile_damage_targets",
                "write_damage_matrix",
            }.isdisjoint(called_names)
        )


if __name__ == "__main__":
    unittest.main()
