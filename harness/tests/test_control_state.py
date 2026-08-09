from __future__ import annotations

import json
import unittest

from harness.control_catalog import SenseQueryResult

from harness.control_state import (
    NORMALIZATION_RULES_VERSION,
    ControlState,
    ControlStateError,
    concentration_check_dc,
)
from harness.control_timeline import build_schedule


def component(
    component_id: str,
    magnitude: dict[str, object],
    *,
    key: str | None = None,
    mode: str = "nonstacking",
    refresh: str = "duration",
) -> dict[str, object]:
    return {
        "component_id": component_id,
        "target_selector_ids": ["target"],
        "magnitude": magnitude,
        "duration": {
            "kind": "relative",
            "owner": "controller",
            "anchor": "end_turn",
            "offset_turns": 1,
        },
        "cadence": {"apply": [{"kind": "hit"}], "repeat": [], "end": []},
        "stacking": {
            "key": key or component_id,
            "mode": mode,
            "refresh": refresh,
            "dominates_component_ids": [],
        },
    }


def apply(
    state: ControlState,
    definition: dict[str, object],
    *,
    target: str = "target_a",
    effect: str = "test_effect",
    event: str = "event_apply",
    expiry: str | None = "event_expire",
    invocation: str = "invocation_1",
    immunities: set[str] | None = None,
    source_actor: str = "controller",
) -> object:
    return state.apply_component(
        effect_id=effect,
        component=definition,
        target_id=target,
        source_actor_id=source_actor,
        event_id=event,
        invocation_id=invocation,
        expiry_event_id=expiry,
        condition_immunities=immunities or set(),
    )


class ControlStateTransitionTests(unittest.TestCase):
    def test_normalization_contract_is_explicitly_versioned(self) -> None:
        self.assertEqual(NORMALIZATION_RULES_VERSION, "1.0.0")

    def test_condition_immunity_removes_only_condition_component(self) -> None:
        state = ControlState()
        restrained = component("restrained_component", {"kind": "condition", "condition": "restrained"})
        speed_zero = component(
            "speed_zero_component",
            {"kind": "speed_zero", "movement_modes": ["walk"]},
        )
        self.assertIsNone(apply(state, restrained, immunities={"restrained"}))
        self.assertIsNotNone(apply(state, speed_zero, immunities={"restrained"}, invocation="invocation_2"))
        self.assertEqual([row.component_id for row in state.active_components()], ["speed_zero_component"])
        self.assertEqual(state.suppression_records[0].reason, "target_condition_immunity")

    def test_reapplication_refreshes_expiry_without_duplicate_active_state(self) -> None:
        state = ControlState()
        slow = component(
            "slow",
            {
                "kind": "speed_reduction",
                "reduction": {"kind": "flat_feet", "value": 10},
                "movement_modes": ["walk"],
            },
        )
        first = apply(state, slow, expiry="old_expiry")
        second = apply(
            state,
            slow,
            event="reapply",
            expiry="new_expiry",
            invocation="invocation_2",
        )
        self.assertIs(first, second)
        self.assertEqual(len(state.active_components()), 1)
        self.assertEqual(state.active_components()[0].expiry_event_id, "new_expiry")
        self.assertFalse(state.refresh_records[0]["immediate_persistent_contribution"])

    def test_branch_transition_uses_explicit_replacement_before_apply(self) -> None:
        state = ControlState()
        weak = component("weak_speed_zero", {"kind": "speed_zero", "movement_modes": ["walk"]})
        strong = component("strong_restrained", {"kind": "condition", "condition": "restrained"})
        apply(state, weak)
        record = state.apply_branch(
            effect_id="test_effect",
            branch={
                "branch_id": "failure",
                "outcome": "save_failure",
                "applies": ["strong_restrained"],
                "replaces": ["weak_speed_zero"],
                "terminates": [],
                "refreshes": [],
                "next_gate_ids": [],
            },
            components_by_id={"weak_speed_zero": weak, "strong_restrained": strong},
            target_id="target_a",
            source_actor_id="controller",
            event_id="save_event",
            invocation_id="invocation_1",
        )
        self.assertEqual([row.component_id for row in state.active_components()], ["strong_restrained"])
        self.assertEqual(record["transition_order"][0:3], [
            "capture_pre_event_state",
            "evaluate_active_guards",
            "resolve_gate_branch",
        ])
        self.assertEqual(state.replacement_records[0]["reason"], "explicit_branch_replacement")

    def test_active_guard_reads_pre_event_snapshot(self) -> None:
        state = ControlState()
        fall = component("fall", {"kind": "fall", "origin": "current_position"})
        record = state.apply_branch(
            effect_id="test_effect",
            branch={
                "branch_id": "guarded",
                "outcome": "no_save",
                "applies": ["fall"],
                "replaces": [],
                "terminates": [],
                "refreshes": [],
                "next_gate_ids": [],
            },
            components_by_id={"fall": fall},
            target_id="target_a",
            source_actor_id="controller",
            event_id="concentration_end",
            invocation_id="invocation_1",
            required_active_component_ids=["elevation"],
        )
        self.assertEqual(record["operation"], "guard_suppressed")
        self.assertEqual(record["missing_active_component_ids"], ["elevation"])
        self.assertFalse(state.active_components())

    def test_effect_id_namespaces_instance_identity_and_targeted_termination(self) -> None:
        state = ControlState()
        shared = component(
            "shared",
            {"kind": "reaction_denial", "scope": "all_reactions"},
        )
        first = apply(state, shared, effect="effect_a", event="apply", invocation="same")
        second = apply(state, shared, effect="effect_b", event="apply", invocation="same")
        self.assertNotEqual(first.instance_id, second.instance_id)
        self.assertIn(":effect_a:", first.instance_id)
        self.assertIn(":effect_b:", second.instance_id)
        removed = state.terminate(
            target_id="target_a",
            component_id="shared",
            event_id="end_a",
            effect_id="effect_a",
        )
        self.assertEqual(removed, (first,))
        self.assertEqual([item.effect_id for item in state.active_components()], ["effect_b"])


class MobilityNormalizationTests(unittest.TestCase):
    def test_restrained_and_independent_speed_zero_produce_one_effective_loss(self) -> None:
        state = ControlState()
        apply(state, component("restrained", {"kind": "condition", "condition": "restrained"}))
        apply(
            state,
            component("direct_zero", {"kind": "speed_zero", "movement_modes": ["walk"]}),
            effect="other_effect",
            invocation="invocation_2",
        )
        effective = state.effective_speeds("target_a", {"walk": 30})
        self.assertEqual(effective["walk"], 0)

    def test_longer_lesser_reduction_resumes_after_speed_zero_expires(self) -> None:
        state = ControlState()
        slow = component(
            "slow",
            {
                "kind": "speed_reduction",
                "reduction": {"kind": "flat_feet", "value": 10},
                "movement_modes": ["walk"],
            },
        )
        zero = component("zero", {"kind": "speed_zero", "movement_modes": ["walk"]})
        apply(state, slow, expiry="late_expiry")
        apply(state, zero, effect="other_effect", expiry="early_expiry", invocation="invocation_2")
        self.assertEqual(state.effective_speeds("target_a", {"walk": 30})["walk"], 0)
        state.expire("early_expiry")
        self.assertEqual(state.effective_speeds("target_a", {"walk": 30})["walk"], 20)

    def test_full_denials_dominate_reduction_sources_in_mobility_ledger(self) -> None:
        denial_cases = (
            (
                "speed_zero",
                component(
                    "zero",
                    {"kind": "speed_zero", "movement_modes": ["walk"]},
                ),
                "walk",
            ),
            (
                "movement_option_denial",
                component(
                    "deny_fly",
                    {
                        "kind": "movement_option_denial",
                        "movement_modes": ["fly"],
                    },
                ),
                "fly",
            ),
            (
                "restrained",
                component(
                    "restrained",
                    {"kind": "condition", "condition": "restrained"},
                ),
                "walk",
            ),
        )
        for label, denial, mode in denial_cases:
            with self.subTest(label=label):
                state = ControlState()
                reduction = component(
                    "slow",
                    {
                        "kind": "speed_reduction",
                        "reduction": {"kind": "flat_feet", "value": 10},
                        "movement_modes": [mode],
                    },
                )
                apply(state, reduction, effect="slow_effect")
                apply(
                    state,
                    denial,
                    effect="denial_effect",
                    invocation="invocation_2",
                )
                dominated = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"{label}_dominated",
                    window_kind="target_movement_opportunity",
                    context={"movement_mode_speeds_ft": {mode: 30}},
                )
                mobility = next(
                    item for item in dominated.contributions
                    if item.primitive_id == "mobility_loss_feet"
                )
                dominant_source = (
                    f"denial_effect:{denial['component_id']}"
                )
                self.assertEqual(mobility.quantity, 30)
                self.assertEqual(
                    mobility.source_component_ids,
                    (dominant_source,),
                )
                suppression = next(
                    item for item in dominated.suppressions
                    if item.reason
                    == "full_mobility_denial_dominates_speed_reduction"
                )
                self.assertEqual(
                    suppression.dominant_source_component_ids,
                    (dominant_source,),
                )
                self.assertEqual(
                    suppression.suppressed_source_component_ids,
                    ("slow_effect:slow",),
                )
                self.assertEqual(
                    suppression.context,
                    {"movement_mode": mode},
                )

                state.terminate(
                    target_id="target_a",
                    component_id=str(denial["component_id"]),
                    effect_id="denial_effect",
                    event_id=f"{label}_ends",
                )
                resumed = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"{label}_resumed",
                    window_kind="target_movement_opportunity",
                    context={"movement_mode_speeds_ft": {mode: 30}},
                )
                resumed_mobility = next(
                    item for item in resumed.contributions
                    if item.primitive_id == "mobility_loss_feet"
                )
                self.assertEqual(resumed_mobility.quantity, 10)
                self.assertEqual(
                    resumed_mobility.source_component_ids,
                    ("slow_effect:slow",),
                )
                self.assertFalse(resumed.suppressions)

    def test_full_denial_precedes_mixed_reduction_order_check(self) -> None:
        state = ControlState()
        flat = component(
            "flat",
            {
                "kind": "speed_reduction",
                "reduction": {"kind": "flat_feet", "value": 10},
                "movement_modes": ["walk"],
            },
        )
        fraction = component(
            "fraction",
            {
                "kind": "speed_reduction",
                "reduction": {
                    "kind": "fraction",
                    "numerator": 1,
                    "denominator": 2,
                },
                "movement_modes": ["walk"],
            },
        )
        zero = component(
            "zero",
            {"kind": "speed_zero", "movement_modes": ["walk"]},
        )
        apply(state, flat, effect="flat_effect")
        apply(
            state,
            fraction,
            effect="fraction_effect",
            invocation="invocation_2",
        )
        apply(
            state,
            zero,
            effect="zero_effect",
            invocation="invocation_3",
        )

        dominated = state.normalize_for_window(
            target_id="target_a",
            window_id="mixed_dominated",
            window_kind="target_movement_opportunity",
            context={"movement_mode_speeds_ft": {"walk": 30}},
        )
        mobility = next(
            item for item in dominated.contributions
            if item.primitive_id == "mobility_loss_feet"
        )
        self.assertEqual(mobility.source_component_ids, ("zero_effect:zero",))
        suppression = next(
            item for item in dominated.suppressions
            if item.reason
            == "full_mobility_denial_dominates_speed_reduction"
        )
        self.assertEqual(
            set(suppression.suppressed_source_component_ids),
            {"flat_effect:flat", "fraction_effect:fraction"},
        )

        state.terminate(
            target_id="target_a",
            component_id="zero",
            effect_id="zero_effect",
            event_id="zero_ends",
        )
        with self.assertRaisesRegex(ControlStateError, "explicit.*operation order"):
            state.normalize_for_window(
                target_id="target_a",
                window_id="mixed_requires_order",
                window_kind="target_movement_opportunity",
                context={"movement_mode_speeds_ft": {"walk": 30}},
            )
        resumed = state.normalize_for_window(
            target_id="target_a",
            window_id="mixed_resumed",
            window_kind="target_movement_opportunity",
            context={
                "movement_mode_speeds_ft": {"walk": 30},
                "mixed_speed_operation_order": ("flat", "fraction"),
            },
        )
        resumed_mobility = next(
            item for item in resumed.contributions
            if item.primitive_id == "mobility_loss_feet"
        )
        self.assertEqual(resumed_mobility.quantity, 20)
        self.assertEqual(
            set(resumed_mobility.source_component_ids),
            {"flat_effect:flat", "fraction_effect:fraction"},
        )

    def test_difficult_terrain_changes_cost_not_speed(self) -> None:
        state = ControlState()
        terrain = component(
            "terrain",
            {"kind": "difficult_terrain", "scope": "area", "movement_cost_multiplier": 2},
        )
        apply(state, terrain)
        self.assertEqual(state.effective_speeds("target_a", {"walk": 30})["walk"], 30)
        self.assertEqual(state.area_movement_cost_multiplier("target_a"), 2)

    def test_movement_mode_denial_is_exact_to_named_mode(self) -> None:
        state = ControlState()
        denial = component(
            "fly_denial",
            {"kind": "movement_option_denial", "movement_modes": ["fly"]},
        )
        apply(state, denial)
        effective = state.effective_speeds("target_a", {"walk": 30, "fly": 60})
        self.assertEqual(effective["walk"], 30)
        self.assertEqual(effective["fly"], 0)

    def test_flat_reductions_stack_only_across_authorized_keys(self) -> None:
        state = ControlState()
        reduction = {
            "kind": "speed_reduction",
            "reduction": {"kind": "flat_feet", "value": 10},
            "movement_modes": ["walk"],
        }
        apply(state, component("slow_a", reduction, key="shared"))
        apply(state, component("slow_b", reduction, key="shared"), invocation="invocation_2")
        self.assertEqual(state.effective_speeds("target_a", {"walk": 30})["walk"], 20)
        apply(
            state,
            component("slow_c", reduction, key="independent", mode="stacks"),
            effect="other_effect",
            invocation="invocation_3",
        )
        self.assertEqual(state.effective_speeds("target_a", {"walk": 30})["walk"], 10)

    def test_flat_nonstacking_keys_are_namespaced_per_effect(self) -> None:
        state = ControlState()
        five = {
            "kind": "speed_reduction",
            "reduction": {"kind": "flat_feet", "value": 5},
            "movement_modes": ["walk"],
        }
        ten = {
            "kind": "speed_reduction",
            "reduction": {"kind": "flat_feet", "value": 10},
            "movement_modes": ["walk"],
        }
        apply(state, component("slow_a", five, key="shared"), effect="effect_a")
        apply(state, component("slow_b", ten, key="shared"), effect="effect_b")
        self.assertEqual(
            state.effective_speeds("target_a", {"walk": 30})["walk"],
            15,
        )

    def test_mixed_flat_fractional_speed_requires_explicit_order(self) -> None:
        state = ControlState()
        apply(state, component(
            "flat",
            {
                "kind": "speed_reduction",
                "reduction": {"kind": "flat_feet", "value": 10},
                "movement_modes": ["walk"],
            },
        ))
        apply(state, component(
            "fraction",
            {
                "kind": "speed_reduction",
                "reduction": {"kind": "fraction", "numerator": 1, "denominator": 2},
                "movement_modes": ["walk"],
            },
        ), effect="other_effect", invocation="invocation_2")
        with self.assertRaisesRegex(ControlStateError, "explicit.*operation order"):
            state.effective_speeds("target_a", {"walk": 30})
        self.assertEqual(
            state.effective_speeds(
                "target_a",
                {"walk": 30},
                mixed_operation_order=("flat", "fraction"),
            )["walk"],
            10,
        )


class DirectPrimitiveNormalizationTests(unittest.TestCase):
    def test_duplicate_reaction_denial_uses_maximum_presence(self) -> None:
        state = ControlState()
        direct = component("reaction", {"kind": "reaction_denial", "scope": "all_reactions"})
        apply(state, direct, effect="effect_a", source_actor="source_a")
        apply(state, direct, effect="effect_b", source_actor="source_b")
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="reaction_1",
            window_kind="reaction_window",
        )
        self.assertEqual(len(result.contributions), 1)
        self.assertEqual(result.contributions[0].primitive_id, "reaction_denial")
        self.assertEqual(set(result.contributions[0].source_component_ids), {"effect_a:reaction", "effect_b:reaction"})
        self.assertNotIn("source_actor_id", result.contributions[0].context)
        self.assertEqual(result.suppressions[0].reason, "identical_primitive_maximum_presence")

    def test_condition_overlap_ignores_incidental_source_actor(self) -> None:
        state = ControlState()
        restrained = component(
            "restrained",
            {"kind": "condition", "condition": "restrained"},
        )
        apply(state, restrained, effect="effect_a", source_actor="source_a")
        apply(state, restrained, effect="effect_b", source_actor="source_b")
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="restrained_turn",
            window_kind="target_active_turn_opportunity",
        )
        self.assertEqual(len(result.contributions), 1)
        contribution = result.contributions[0]
        self.assertEqual(set(contribution.source_component_ids), {"effect_a:restrained", "effect_b:restrained"})
        self.assertNotIn("source_actor_id", contribution.context)

    def test_authority_dominance_compares_qualified_source_ids(self) -> None:
        state = ControlState()
        state.register_relationships(
            "effect_a",
            {
                "dominance": [
                    {
                        "dominant_component_id": "strong",
                        "suppressed_component_ids": ["weak"],
                    }
                ]
            },
        )
        direct = {"kind": "reaction_denial", "scope": "all_reactions"}
        apply(state, component("strong", direct), effect="effect_a")
        apply(state, component("weak", direct), effect="effect_a")
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="reaction_dominance",
            window_kind="reaction_window",
        )
        self.assertEqual(result.contributions[0].source_component_ids, ("effect_a:strong",))
        suppression = next(row for row in result.suppressions if row.reason == "explicit_authority_dominance")
        self.assertEqual(suppression.dominant_source_component_ids, ("effect_a:strong",))
        self.assertEqual(suppression.suppressed_source_component_ids, ("effect_a:weak",))

    def test_next_attack_token_is_distinct_and_consumed_once(self) -> None:
        state = ControlState()
        sap = component(
            "sap",
            {"kind": "attack_disadvantage", "scope": "next_attack", "count": 1},
        )
        apply(state, sap)
        first = state.normalize_for_window(
            target_id="target_a",
            window_id="attack_1",
            window_kind="target_attack_opportunity",
        )
        self.assertEqual(first.contributions[0].primitive_id, "offensive_impairment_next_attack")
        self.assertFalse(state.active_components())
        second = state.normalize_for_window(
            target_id="target_a",
            window_id="attack_2",
            window_kind="target_attack_opportunity",
        )
        self.assertFalse(second.contributions)

    def test_all_attacks_emits_once_for_a_scheduled_turn_with_two_attacks(self) -> None:
        state = ControlState()
        apply(
            state,
            component(
                "all_attacks",
                {"kind": "attack_disadvantage", "scope": "all_attacks"},
            ),
        )
        schedule = build_schedule(
            "fighter_first_v1",
            ["target_a"],
            target_attack_counts={"target_a": [2, 0, 0]},
        )
        windows = [
            event
            for event in schedule.events
            if event.round == 1
            and event.target_id == "target_a"
            and event.kind
            in {"target_active_turn_opportunity", "target_attack_opportunity"}
        ]
        self.assertEqual(
            [event.kind for event in windows],
            [
                "target_active_turn_opportunity",
                "target_attack_opportunity",
                "target_attack_opportunity",
            ],
        )
        contributions = []
        for event in windows:
            self.assertIsNotNone(event.window_id)
            contributions.extend(
                state.normalize_for_window(
                    target_id="target_a",
                    window_id=event.window_id or "",
                    window_kind=event.kind,
                ).contributions
            )
        all_attacks = [
            item
            for item in contributions
            if item.primitive_id == "offensive_impairment_all_attacks"
        ]
        self.assertEqual(len(all_attacks), 1)
        self.assertEqual(all_attacks[0].unit, "affected_target_turn")
        self.assertEqual(all_attacks[0].event_or_window_id, windows[0].window_id)

    def test_active_turn_denial_suppresses_scripted_attacks_without_consuming_tokens(self) -> None:
        state = ControlState()
        apply(
            state,
            component("incapacitated", {"kind": "condition", "condition": "incapacitated"}),
            effect="denial_effect",
        )
        apply(
            state,
            component("all_attacks", {"kind": "attack_disadvantage", "scope": "all_attacks"}),
            effect="all_attacks_effect",
            invocation="invocation_2",
        )
        apply(
            state,
            component(
                "next_attack",
                {"kind": "attack_disadvantage", "scope": "next_attack", "count": 1},
            ),
            effect="next_attack_effect",
            invocation="invocation_3",
        )
        denied_turn = state.normalize_for_window(
            target_id="target_a",
            window_id="denied_turn",
            window_kind="target_active_turn_opportunity",
        )
        self.assertNotIn(
            "offensive_impairment_all_attacks",
            {item.primitive_id for item in denied_turn.contributions},
        )
        self.assertEqual(
            {
                row.primitive_id
                for row in denied_turn.suppressions
                if row.reason == "active_turn_denial_removes_attack_opportunity"
            },
            {"offensive_impairment_all_attacks"},
        )
        denied_attack = state.normalize_for_window(
            target_id="target_a",
            window_id="impossible_attack",
            window_kind="target_attack_opportunity",
        )
        self.assertFalse(denied_attack.contributions)
        self.assertEqual(
            {row.primitive_id for row in denied_attack.suppressions},
            {"offensive_impairment_next_attack"},
        )
        next_attack = next(
            item for item in state.active_components("target_a")
            if item.component_id == "next_attack"
        )
        self.assertEqual(next_attack.remaining_tokens, 1)
        state.terminate(
            target_id="target_a",
            component_id="incapacitated",
            effect_id="denial_effect",
            event_id="denial_ends",
        )
        resumed_turn = state.normalize_for_window(
            target_id="target_a",
            window_id="resumed_turn",
            window_kind="target_active_turn_opportunity",
        )
        self.assertEqual(
            {item.primitive_id for item in resumed_turn.contributions},
            {"offensive_impairment_all_attacks"},
        )
        resumed = state.normalize_for_window(
            target_id="target_a",
            window_id="legal_attack",
            window_kind="target_attack_opportunity",
        )
        self.assertEqual(
            {item.primitive_id for item in resumed.contributions},
            {"offensive_impairment_next_attack"},
        )
        self.assertNotIn(
            "next_attack",
            {item.component_id for item in state.active_components("target_a")},
        )

    def test_different_targets_never_suppress_one_another(self) -> None:
        state = ControlState()
        direct = component("reaction", {"kind": "reaction_denial", "scope": "all_reactions"})
        apply(state, direct, target="target_a")
        apply(state, direct, target="target_b", invocation="invocation_2")
        first = state.normalize_for_window(
            target_id="target_a", window_id="window_a", window_kind="reaction_window"
        )
        second = state.normalize_for_window(
            target_id="target_b", window_id="window_b", window_kind="reaction_window"
        )
        self.assertEqual(len(first.contributions), 1)
        self.assertEqual(len(second.contributions), 1)
        self.assertEqual(first.contributions[0].target_id, "target_a")
        self.assertEqual(second.contributions[0].target_id, "target_b")

    def test_mobility_vector_aggregates_sources_once(self) -> None:
        state = ControlState()
        apply(state, component("zero_a", {"kind": "speed_zero", "movement_modes": ["walk"]}))
        apply(
            state,
            component("zero_b", {"kind": "speed_zero", "movement_modes": ["walk"]}),
            effect="other_effect",
            invocation="invocation_2",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="move_1",
            window_kind="target_movement_opportunity",
            context={"base_speeds": {"walk": 30}},
        )
        mobility = [item for item in result.contributions if item.primitive_id == "mobility_loss_feet"]
        self.assertEqual(len(mobility), 1)
        self.assertEqual(mobility[0].quantity, 30)
        self.assertEqual(set(mobility[0].source_component_ids), {"test_effect:zero_a", "other_effect:zero_b"})

    def test_concentration_dc_formula_is_capped_and_floored(self) -> None:
        self.assertEqual(concentration_check_dc(1), 10)
        self.assertEqual(concentration_check_dc(21), 10)
        self.assertEqual(concentration_check_dc(22), 11)
        self.assertEqual(concentration_check_dc(100), 30)


class CatalogPrimitiveNormalizationTests(unittest.TestCase):
    def test_save_opportunity_filters_other_abilities_before_dominance(self) -> None:
        state = ControlState()
        apply(
            state,
            component("stunned", {"kind": "condition", "condition": "stunned"}),
        )
        apply(
            state,
            component("restrained", {"kind": "condition", "condition": "restrained"}),
            effect="other_effect",
            invocation="invocation_2",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="dexterity_save",
            window_kind="save_opportunity",
            context={"save_ability": "dexterity"},
        )
        self.assertEqual(
            [
                (item.primitive_id, item.context["save_ability"])
                for item in result.contributions
            ],
            [("save_auto_failure", "dexterity")],
        )
        self.assertEqual(
            [item.reason for item in result.suppressions],
            ["automatic_failure_dominates_disadvantage"],
        )

    def test_blinded_attack_effects_require_exact_alternative_sight_context(self) -> None:
        state = ControlState()
        apply(
            state,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
        )
        without_sight = state.normalize_for_window(
            target_id="target_a",
            window_id="turn_without_sight",
            window_kind="target_active_turn_opportunity",
            context={"alternative_sight_resolution": False},
        )
        with_sight = state.normalize_for_window(
            target_id="target_a",
            window_id="turn_with_sight",
            window_kind="target_active_turn_opportunity",
            context={"alternative_sight_resolution": True},
        )
        self.assertEqual(
            [
                item.primitive_id
                for item in without_sight.contributions
                if item.primitive_id == "offensive_impairment_all_attacks"
            ],
            ["offensive_impairment_all_attacks"],
        )
        self.assertNotIn(
            "offensive_impairment_all_attacks",
            {item.primitive_id for item in with_sight.contributions},
        )

    def test_known_attack_boolean_dominates_unresolved_duplicate(self) -> None:
        state = ControlState()
        apply(
            state,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
            effect="blind_effect",
        )
        apply(
            state,
            component(
                "restrained",
                {"kind": "condition", "condition": "restrained"},
            ),
            effect="restrained_effect",
            invocation="invocation_2",
        )
        expected = {
            "target_active_turn_opportunity": "offensive_impairment_all_attacks",
            "incoming_attack_opportunity": "defensive_attack_advantage",
        }
        for window_kind, primitive_id in expected.items():
            with self.subTest(window_kind=window_kind):
                result = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"known_{window_kind}",
                    window_kind=window_kind,
                )
                matching = [
                    item for item in result.contributions
                    if item.primitive_id == primitive_id
                ]
                self.assertEqual(len(matching), 1)
                self.assertNotEqual(
                    matching[0].disposition,
                    "retained_unpriced",
                )
                self.assertEqual(
                    matching[0].source_component_ids,
                    ("restrained_effect:restrained",),
                )
                suppression = next(
                    item for item in result.suppressions
                    if item.reason
                    == "known_primitive_dominates_unresolved_duplicate"
                )
                self.assertEqual(
                    suppression.dominant_source_component_ids,
                    ("restrained_effect:restrained",),
                )
                self.assertEqual(
                    suppression.suppressed_source_component_ids,
                    ("blind_effect:blinded",),
                )


class CanonicalContextAndSenseTests(unittest.TestCase):
    def test_movement_window_accepts_canonical_mode_speeds(self) -> None:
        state = ControlState()
        apply(
            state,
            component("zero", {"kind": "speed_zero", "movement_modes": ["walk"]}),
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="move_canonical",
            window_kind="target_movement_opportunity",
            context={"movement_mode_speeds_ft": {"walk": 30}},
        )
        mobility = next(
            item for item in result.contributions
            if item.primitive_id == "mobility_loss_feet"
        )
        self.assertEqual(mobility.quantity, 30)

    def test_concentration_break_prefers_canonical_context_and_preserves_alias(self) -> None:
        state = ControlState()
        apply(
            state,
            component("incapacitated", {"kind": "condition", "condition": "incapacitated"}),
        )
        contexts = (
            (
                {"target_is_concentrating": True, "target_concentrating": False},
                "canonical",
            ),
            ({"target_concentrating": True}, "legacy"),
        )
        for context, label in contexts:
            with self.subTest(label=label):
                result = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"concentration_{label}",
                    window_kind="condition_application",
                    context=context,
                )
                self.assertEqual(
                    [item.primitive_id for item in result.contributions],
                    ["concentration_break"],
                )

    def test_fall_transition_uses_canonical_prevention_and_preserves_alias(self) -> None:
        state = ControlState()
        apply(
            state,
            component("prone", {"kind": "condition", "condition": "prone"}),
        )
        contexts = (
            (
                {"target_airborne": True, "hover_or_explicit_fall_prevention": False},
                True,
                "canonical_fall",
            ),
            (
                {"target_airborne": True, "hover_or_explicit_fall_prevention": True},
                False,
                "canonical_prevention",
            ),
            ({"target_airborne": True, "target_can_hover": True}, False, "legacy"),
        )
        for context, expected_fall, label in contexts:
            with self.subTest(label=label):
                result = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"fall_{label}",
                    window_kind="instantaneous_resolution",
                    context=context,
                )
                primitive_ids = {item.primitive_id for item in result.contributions}
                self.assertEqual("fall_transition" in primitive_ids, expected_fall)

    def test_charmed_contribution_uses_active_source_actor_id(self) -> None:
        state = ControlState()
        apply(
            state,
            component("charmed", {"kind": "condition", "condition": "charmed"}),
            effect="charm_effect",
            source_actor="charmer_a",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="charmed_turn",
            window_kind="target_active_turn_opportunity",
            context={"source_actor_id": "untrusted_caller_value"},
        )
        restriction = next(item for item in result.contributions)
        self.assertEqual(restriction.context["source_actor_id"], "charmer_a")
        self.assertEqual(restriction.source_component_ids, ("charm_effect:charmed",))
        self.assertNotIn("source_context_by_actor_id", restriction.context)

    def test_frightened_uses_context_for_its_own_source_actor(self) -> None:
        state = ControlState()
        fear = component("frightened", {"kind": "condition", "condition": "frightened"})
        apply(
            state,
            fear,
            effect="fear_a",
            source_actor="source_a",
        )
        apply(
            state,
            fear,
            effect="fear_b",
            source_actor="source_b",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="frightened_turn",
            window_kind="target_active_turn_opportunity",
            context={
                "source_context_by_actor_id": {
                    "source_a": {"source_in_line_of_sight": True},
                    "source_b": {"source_in_line_of_sight": False},
                }
            },
        )
        impairments = [
            item
            for item in result.contributions
            if item.primitive_id == "offensive_impairment_all_attacks"
        ]
        self.assertEqual(len(impairments), 1)
        impairment = impairments[0]
        self.assertEqual(impairment.source_component_ids, ("fear_a:frightened",))
        self.assertEqual(impairment.context["source_actor_id"], "source_a")
        self.assertIs(impairment.context["source_in_line_of_sight"], True)
        self.assertNotIn("source_context_by_actor_id", impairment.context)

    def test_visible_frightened_sources_max_collapse_after_predicates_pass(self) -> None:
        state = ControlState()
        fear = component(
            "frightened",
            {"kind": "condition", "condition": "frightened"},
        )
        apply(
            state,
            fear,
            effect="fear_a",
            source_actor="source_a",
        )
        apply(
            state,
            fear,
            effect="fear_b",
            source_actor="source_b",
            invocation="invocation_2",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="both_frightened_sources_visible_turn",
            window_kind="target_active_turn_opportunity",
            context={
                "source_context_by_actor_id": {
                    "source_a": {"source_in_line_of_sight": True},
                    "source_b": {"source_in_line_of_sight": True},
                }
            },
        )
        impairments = [
            item for item in result.contributions
            if item.primitive_id == "offensive_impairment_all_attacks"
        ]
        self.assertEqual(len(impairments), 1)
        self.assertEqual(
            set(impairments[0].source_component_ids),
            {"fear_a:frightened", "fear_b:frightened"},
        )
        self.assertNotIn("source_actor_id", impairments[0].context)
        self.assertEqual(
            [
                item.reason for item in result.suppressions
                if item.primitive_id == "offensive_impairment_all_attacks"
            ],
            ["identical_primitive_maximum_presence"],
        )

    def test_typed_sense_result_emits_location_awareness_in_both_windows(self) -> None:
        resolution = SenseQueryResult(
            alternative_sight=False,
            location_detection=True,
            alternative_sight_evidence=("no_alternative_sight",),
            location_detection_evidence=("tremorsense_contact",),
            alternative_sight_missing_context=(),
            location_detection_missing_context=(),
        )
        for window_kind in ("location_opportunity", "sight_opportunity"):
            with self.subTest(window_kind=window_kind):
                result = ControlState().normalize_for_window(
                    target_id="target_a",
                    window_id=window_kind,
                    window_kind=window_kind,
                    context={"sense_resolution": resolution},
                )
                self.assertEqual(len(result.contributions), 1)
                contribution = result.contributions[0]
                self.assertEqual(
                    contribution.source_component_ids,
                    ("target_sense:target_a:tremorsense",),
                )
                self.assertEqual(contribution.active_source_effect_id, "target_sense:target_a")
                self.assertEqual(contribution.family, "retained_unpriced")
                self.assertEqual(contribution.primitive_id, "nonsight_location_awareness")
                self.assertEqual(contribution.unit, "location_detection_opportunity")
                self.assertEqual(contribution.disposition, "retained_unpriced")
                self.assertEqual(contribution.context["sense_resolution"], resolution.as_dict())
                self.assertEqual(contribution.context["location_detection_evidence"], ["tremorsense_contact"])
                json.dumps(contribution.to_dict())

    def test_mapping_sense_result_retains_unresolved_and_omits_false_detection(self) -> None:
        unresolved = {
            "alternative_sight": None,
            "location_detection": None,
            "alternative_sight_evidence": [],
            "location_detection_evidence": ["range_known"],
            "alternative_sight_missing_context": [],
            "location_detection_missing_context": ["target_airborne", "same_surface_or_liquid"],
        }
        result = ControlState().normalize_for_window(
            target_id="target_a",
            window_id="unresolved_location",
            window_kind="location_opportunity",
            context={"sense_resolution": unresolved},
        )
        self.assertEqual(len(result.contributions), 1)
        contribution = result.contributions[0]
        self.assertEqual(contribution.context["unresolved_requirements"], ["same_surface_or_liquid", "target_airborne"])
        self.assertEqual(contribution.context["location_detection_missing_context"], ["target_airborne", "same_surface_or_liquid"])
        self.assertEqual(contribution.context["location_detection_evidence"], ["range_known"])
        false_resolution = {**unresolved, "location_detection": False}
        for window_kind in ("location_opportunity", "sight_opportunity"):
            with self.subTest(window_kind=window_kind):
                absent = ControlState().normalize_for_window(
                    target_id="target_a",
                    window_id=f"false_{window_kind}",
                    window_kind=window_kind,
                    context={"sense_resolution": false_resolution},
                )
                self.assertFalse(absent.contributions)

    def test_unresolved_alternative_sight_retains_blinded_mechanics(self) -> None:
        state = ControlState()
        apply(
            state,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
        )
        resolution = SenseQueryResult(
            alternative_sight=None,
            location_detection=False,
            alternative_sight_evidence=("blindsight_distance_unresolved",),
            location_detection_evidence=("no_tremorsense",),
            alternative_sight_missing_context=("interaction_distance_ft",),
            location_detection_missing_context=(),
        )
        cases = {
            "target_active_turn_opportunity": "offensive_impairment_all_attacks",
            "incoming_attack_opportunity": "defensive_attack_advantage",
            "sight_opportunity": "sight_option_denial",
        }
        for window_kind, primitive_id in cases.items():
            with self.subTest(window_kind=window_kind):
                result = state.normalize_for_window(
                    target_id="target_a",
                    window_id=f"unresolved_{window_kind}",
                    window_kind=window_kind,
                    context={"sense_resolution": resolution},
                )
                contribution = next(
                    item for item in result.contributions
                    if item.primitive_id == primitive_id
                )
                self.assertEqual(contribution.family, "retained_unpriced")
                self.assertEqual(contribution.disposition, "retained_unpriced")
                self.assertTrue(contribution.context["unresolved_requirements"])

        attack = state.normalize_for_window(
            target_id="target_a",
            window_id="unresolved_target_attack_opportunity",
            window_kind="target_attack_opportunity",
            context={"sense_resolution": resolution},
        )
        self.assertFalse(attack.contributions)

if __name__ == "__main__":
    unittest.main()
