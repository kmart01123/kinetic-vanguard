from __future__ import annotations

import json
import math
import unittest
from fractions import Fraction

from harness.control_timeline import (
    TIMELINE_ENGINE_VERSION,
    ConcentrationTracker,
    DisplacementEpochs,
    TimelineError,
    airborne_fall_transition,
    area_entry,
    area_response,
    build_schedule,
    concentration_dc,
    displacement_function,
    effective_movement_speeds,
    enumerate_prone_movement_operations,
    prone_movement_response,
    repeat_save_survival,
    resolve_expiry_index,
    typed_event_matches,
    vertical_displacement_vector,
)


def route(
    route_id: str,
    *,
    mode: str = "walk",
    distance: int = 30,
    compatible: bool = True,
    multiplier: int = 1,
    environment: str = "grounded",
) -> dict[str, object]:
    return {
        "route_id": route_id,
        "mode": mode,
        "distance_to_exit_ft": distance,
        "compatible": compatible,
        "movement_cost_multiplier": multiplier,
        "environment": environment,
    }


def target_trace(schedule: object, target_id: str) -> list[dict[str, object]]:
    records = []
    for event in schedule.events:
        if event.target_id != target_id:
            continue
        record = event.to_dict()
        record.pop("sequence")
        records.append(record)
    return records


class TimelineScheduleTests(unittest.TestCase):
    def test_version_boundaries_attack_counts_and_reaction_intervals(self) -> None:
        self.assertEqual(TIMELINE_ENGINE_VERSION, "2.0.0")
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            schedule = build_schedule(
                convention,
                ["target_b", "target_a"],
                target_attack_counts={
                    "target_b": [1, 0, 2],
                    "target_a": {1: 2, 2: 1, 3: 0},
                },
            )
            self.assertEqual(schedule.rounds, 3)
            self.assertEqual(schedule.target_ids, ("target_b", "target_a"))
            self.assertEqual(schedule.events[0].event_id, "r1:round:start")
            self.assertEqual(schedule.events[-1].event_id, "r3:round:end")
            self.assertEqual(
                [event.round for event in schedule.events if event.kind == "round_start"],
                [1, 2, 3],
            )
            for round_number in range(1, 4):
                round_events = [
                    event for event in schedule.events if event.round == round_number
                ]
                self.assertEqual(round_events[0].kind, "round_start")
                self.assertEqual(round_events[-1].kind, "round_end")
                controller_start = next(
                    event.sequence
                    for event in round_events
                    if event.kind == "controller_turn_start"
                )
                target_starts = [
                    event for event in round_events if event.kind == "target_turn_start"
                ]
                self.assertEqual(
                    [event.target_id for event in target_starts],
                    ["target_b", "target_a"],
                )
                if convention == "fighter_first_v1":
                    self.assertLess(controller_start, target_starts[0].sequence)
                else:
                    self.assertGreater(controller_start, target_starts[-1].sequence)
            attacks = [
                event
                for event in schedule.events
                if event.kind == "target_attack_opportunity"
            ]
            self.assertEqual(
                sum(event.target_id == "target_b" for event in attacks),
                3,
            )
            self.assertEqual(
                sum(event.target_id == "target_a" for event in attacks),
                3,
            )
            self.assertEqual(len(schedule.reaction_intervals), 8)
            first = schedule.reaction_intervals[0]
            self.assertEqual(first.interval_id, "horizon:target:target_b:reaction_interval")
            self.assertEqual(first.start_event_id, "r1:round:start")
            self.assertEqual(first.end_before_event_id, "r1:target:target_b:turn:start")
            self.assertIsNone(first.initially_available)
            self.assertTrue(first.horizon_entry_partial)
            first_reset = schedule.reaction_intervals[2]
            self.assertEqual(first_reset.interval_id, "r1:target:target_b:reaction_interval")
            self.assertEqual(
                first_reset.start_event_id,
                "r1:target:target_b:turn:start",
            )
            self.assertEqual(
                first_reset.end_before_event_id,
                "r2:target:target_b:turn:start",
            )
            last = schedule.reaction_intervals[-1]
            self.assertEqual(last.end_before_event_id, "r3:round:end")
            json.dumps(schedule.to_dict(), sort_keys=True, allow_nan=False)

    def test_controller_reaction_windows_bind_to_the_exact_target_interval(self) -> None:
        scripted = {1: [{"kind": "reaction_window", "target_id": "target"}]}
        with self.assertRaisesRegex(TimelineError, "initial_reaction_availability"):
            build_schedule(
                "fighter_first_v1",
                ["target"],
                controller_events_by_round=scripted,
                target_attack_counts={"target": 0},
            )
        fighter_first = build_schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round=scripted,
            target_attack_counts={"target": 0},
            initial_reaction_availability={"target": True},
        )
        target_first = build_schedule(
            "target_before_fighter_v1",
            ["target"],
            controller_events_by_round=scripted,
            target_attack_counts={"target": 0},
        )
        fighter_window = next(
            event for event in fighter_first.events
            if event.turn_owner == "controller" and event.kind == "reaction_window"
        )
        target_window = next(
            event for event in target_first.events
            if event.turn_owner == "controller" and event.kind == "reaction_window"
        )
        self.assertEqual(fighter_window.reaction_interval_id, "horizon:target:target:reaction_interval")
        self.assertEqual(target_window.reaction_interval_id, "r1:target:target:reaction_interval")

    def test_attack_counts_and_scripted_opportunities_must_be_explicit(self) -> None:
        with self.assertRaisesRegex(TimelineError, "explicitly cover"):
            build_schedule(
                "fighter_first_v1",
                ["target"],
                target_attack_counts={},
            )
        with self.assertRaisesRegex(TimelineError, "exactly three"):
            build_schedule(
                "fighter_first_v1",
                ["target"],
                target_attack_counts={"target": [1, 2]},
            )
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": [0, 2, 1]},
            controller_events_by_round={
                1: [
                    {"kind": "declaration"},
                    {"kind": "activation", "target_id": "target"},
                    {"kind": "controller_attack_opportunity", "target_id": "target"},
                    {"kind": "hit", "target_id": "target"},
                ]
            },
            target_events_by_round={
                "target": {
                    1: [
                        {"kind": "save_opportunity", "phase": "start"},
                        {"kind": "entry", "phase": "before_movement"},
                        {"kind": "exit", "phase": "after_movement"},
                    ]
                }
            },
        )
        round_one_attacks = [
            event
            for event in schedule.events
            if event.round == 1 and event.kind == "target_attack_opportunity"
        ]
        self.assertEqual(round_one_attacks, [])
        self.assertEqual(
            [
                event.kind
                for event in schedule.events
                if event.event_id.startswith("r1:controller:controller:script")
            ],
            ["declaration", "activation", "controller_attack_opportunity", "hit"],
        )
        save = schedule.event("r1:target:target:script:000:save_opportunity")
        self.assertTrue(save.window_id)
        self.assertEqual(save.reaction_interval_id, "r1:target:target:reaction_interval")

    def test_target_movement_response_precedes_active_and_attack_windows(self) -> None:
        target_events = {
            "target": {
                1: [
                    {"kind": "save_opportunity", "phase": "start"},
                    {"kind": "entry", "phase": "before_movement"},
                    {"kind": "exit", "phase": "after_movement"},
                    {"kind": "damage_context", "phase": "after_attacks"},
                    {"kind": "instantaneous_resolution", "phase": "end"},
                ]
            }
        }
        expected_kinds = [
            "target_turn_start",
            "reaction_window",
            "save_opportunity",
            "entry",
            "target_movement_opportunity",
            "exit",
            "target_active_turn_opportunity",
            "target_attack_opportunity",
            "target_attack_opportunity",
            "damage_context",
            "instantaneous_resolution",
            "target_turn_end",
        ]
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            with self.subTest(convention=convention):
                schedule = build_schedule(
                    convention,
                    ["target"],
                    target_events_by_round=target_events,
                    target_attack_counts={"target": [2, 0, 0]},
                )
                first_turn_kinds = [
                    event.kind
                    for event in schedule.events
                    if event.turn_id == "r1:target:target:turn"
                ]
                self.assertEqual(first_turn_kinds, expected_kinds)
                turn_start = schedule.event("r1:target:target:turn:start")
                reaction = schedule.event("r1:target:target:reaction_window")
                movement = schedule.event("r1:target:target:turn:movement")
                active_turn = schedule.event("r1:target:target:turn:active_turn")
                first_attack = schedule.event("r1:target:target:turn:attack:001")
                self.assertEqual(reaction.sequence, turn_start.sequence + 1)
                self.assertLess(movement.sequence, active_turn.sequence)
                self.assertLess(active_turn.sequence, first_attack.sequence)
                self.assertEqual(
                    sum(
                        event.kind == "target_movement_opportunity"
                        for event in schedule.events
                        if event.turn_id == movement.turn_id
                    ),
                    1,
                )

        for retired_phase in ("before_active_turn", "before_attacks"):
            with self.subTest(retired_phase=retired_phase):
                with self.assertRaisesRegex(TimelineError, "phase is unsupported"):
                    build_schedule(
                        "fighter_first_v1",
                        ["target"],
                        target_events_by_round={
                            "target": {
                                1: [{"kind": "activation", "phase": retired_phase}]
                            }
                        },
                        target_attack_counts={"target": [1, 0, 0]},
                    )

    def test_duplicate_scripted_window_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(TimelineError, "duplicate window IDs"):
            build_schedule(
                "fighter_first_v1",
                ["target"],
                controller_events_by_round={
                    1: [
                        {"kind": "declaration", "window_id": "duplicate"},
                        {"kind": "activation", "window_id": "duplicate"},
                    ]
                },
                target_attack_counts={"target": 0},
            )

    def test_condition_execution_bridge_kinds_and_opportunity_windows_are_typed(self) -> None:
        kinds = (
            "attack_opportunity",
            "action_proposal",
            "condition_application",
            "condition_end",
            "initiative_opportunity",
            "fall_transition",
        )
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": kind, "target_id": "target"}
                    for kind in kinds
                ],
            },
            target_events_by_round={
                "target": {
                    1: [{"kind": "save_opportunity", "phase": "start"}],
                },
            },
            target_attack_counts={"target": 0},
        )
        events = {
            event.kind: event
            for event in schedule.events
            if event.kind in set(kinds) | {"save_opportunity"}
        }
        self.assertEqual(set(events), set(kinds) | {"save_opportunity"})
        for kind in (
            "attack_opportunity",
            "action_proposal",
            "initiative_opportunity",
            "save_opportunity",
        ):
            with self.subTest(kind=kind):
                self.assertEqual(
                    events[kind].window_id,
                    events[kind].event_id + ":window",
                )
        for kind in ("condition_application", "condition_end", "fall_transition"):
            with self.subTest(kind=kind):
                self.assertIsNone(events[kind].window_id)

        with self.assertRaisesRegex(TimelineError, "unknown fields"):
            build_schedule(
                "fighter_first_v1",
                ["target"],
                controller_events_by_round={
                    1: [{
                        "kind": "condition_application",
                        "condition_id": "prone",
                    }],
                },
                target_attack_counts={"target": 0},
            )

    def test_caller_order_is_stable_and_independent_targets_are_permutation_invariant(self) -> None:
        left = build_schedule(
            "fighter_first_v1",
            ["alpha", "beta"],
            target_attack_counts={"alpha": [1, 2, 0], "beta": [0, 1, 1]},
        )
        right = build_schedule(
            "fighter_first_v1",
            ["beta", "alpha"],
            target_attack_counts={"alpha": [1, 2, 0], "beta": [0, 1, 1]},
        )
        self.assertEqual(
            [
                event.target_id
                for event in left.events
                if event.round == 1 and event.kind == "target_turn_start"
            ],
            ["alpha", "beta"],
        )
        self.assertEqual(
            [
                event.target_id
                for event in right.events
                if event.round == 1 and event.kind == "target_turn_start"
            ],
            ["beta", "alpha"],
        )
        for target_id in ("alpha", "beta"):
            self.assertEqual(target_trace(left, target_id), target_trace(right, target_id))
            for schedule in (left, right):
                for round_number in range(1, 4):
                    movement = schedule.event(
                        f"r{round_number}:target:{target_id}:turn:movement"
                    )
                    active_turn = schedule.event(
                        f"r{round_number}:target:{target_id}:turn:active_turn"
                    )
                    self.assertLess(movement.sequence, active_turn.sequence)
                    for event in schedule.events:
                        if (
                            event.turn_id == movement.turn_id
                            and event.kind == "target_attack_opportunity"
                        ):
                            self.assertLess(movement.sequence, event.sequence)
            self.assertEqual(
                [
                    interval.to_dict()
                    for interval in left.reaction_intervals
                    if interval.target_id == target_id
                ],
                [
                    interval.to_dict()
                    for interval in right.reaction_intervals
                    if interval.target_id == target_id
                ],
            )

    def test_relative_controller_boundaries_are_exact_under_both_initiatives(self) -> None:
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            schedule = build_schedule(
                convention,
                ["target"],
                target_attack_counts={"target": 1},
                controller_events_by_round={1: [{"kind": "activation"}]},
            )
            applied = "r1:controller:controller:script:000:activation"
            start_index = resolve_expiry_index(
                schedule,
                applied,
                {
                    "kind": "relative",
                    "owner": "controller",
                    "anchor": "start_turn",
                    "offset_turns": 1,
                },
            )
            end_index = resolve_expiry_index(
                schedule,
                applied,
                {
                    "kind": "relative",
                    "owner": "controller",
                    "anchor": "end_turn",
                    "offset_turns": 1,
                },
            )
            self.assertEqual(schedule.events[start_index].event_id, "r2:controller:turn:start")
            self.assertEqual(schedule.events[end_index].event_id, "r2:controller:turn:end")

    def test_concentration_rounds_use_the_same_canonical_turn_anchor(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
        )
        duration = {
            "kind": "concentration",
            "maximum_value": 1,
            "unit": "round",
        }
        cases = (
            ("r1:controller:turn:start", "r2:controller:turn:start", None),
            (
                "r1:target:target:turn:end",
                "r2:target:target:turn:end",
                "target",
            ),
        )
        for applied_id, expected_id, target_id in cases:
            with self.subTest(applied_id=applied_id):
                expiry_index = resolve_expiry_index(
                    schedule,
                    applied_id,
                    duration,
                    target_id=target_id,
                )
                self.assertEqual(
                    schedule.events[expiry_index].event_id,
                    expected_id,
                )

        self.assertIsNone(resolve_expiry_index(
            schedule,
            "r1:controller:turn:start",
            {
                "kind": "concentration",
                "maximum_value": 1,
                "unit": "minute",
            },
        ))

    def test_in_horizon_concentration_script_anchor_fails_closed(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={"target": 0},
        )
        with self.assertRaisesRegex(
            TimelineError,
            "canonical controller/target turn start or end anchor",
        ):
            resolve_expiry_index(
                schedule,
                "r1:controller:controller:script:000:activation",
                {
                    "kind": "concentration",
                    "maximum_value": 1,
                    "unit": "round",
                },
            )

    def test_target_relative_boundaries_change_round_with_initiative(self) -> None:
        for convention, expected_round in (
            ("fighter_first_v1", 1),
            ("target_before_fighter_v1", 2),
        ):
            schedule = build_schedule(
                convention,
                ["target"],
                target_attack_counts={"target": 0},
                controller_events_by_round={1: [{"kind": "activation"}]},
            )
            applied = "r1:controller:controller:script:000:activation"
            start_index = resolve_expiry_index(
                schedule,
                applied,
                {
                    "kind": "relative",
                    "owner": "target",
                    "anchor": "start_turn",
                    "offset_turns": 1,
                },
                target_id="target",
            )
            end_index = resolve_expiry_index(
                schedule,
                applied,
                {
                    "kind": "relative",
                    "owner": "target",
                    "anchor": "end_turn",
                    "offset_turns": 1,
                },
                target_id="target",
            )
            self.assertEqual(
                schedule.events[start_index].event_id,
                f"r{expected_round}:target:target:turn:start",
            )
            self.assertEqual(
                schedule.events[end_index].event_id,
                f"r{expected_round}:target:target:turn:end",
            )

    def test_initiative_changes_the_order_of_covered_windows(self) -> None:
        fighter_first = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 1},
            controller_events_by_round={1: [{"kind": "activation"}]},
        )
        target_first = build_schedule(
            "target_before_fighter_v1",
            ["target"],
            target_attack_counts={"target": 1},
            controller_events_by_round={1: [{"kind": "activation"}]},
        )
        activation = "r1:controller:controller:script:000:activation"
        active_turn = "r1:target:target:turn:active_turn"
        self.assertLess(
            fighter_first.event(activation).sequence,
            fighter_first.event(active_turn).sequence,
        )
        self.assertGreater(
            target_first.event(activation).sequence,
            target_first.event(active_turn).sequence,
        )
        for schedule in (fighter_first, target_first):
            movement = schedule.event("r1:target:target:turn:movement")
            attack = schedule.event("r1:target:target:turn:attack:001")
            self.assertLess(movement.sequence, schedule.event(active_turn).sequence)
            self.assertLess(movement.sequence, attack.sequence)

    def test_frozen_ground_triggering_turn_expiry_is_exact(self) -> None:
        controller_entry = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
            controller_events_by_round={
                1: [{"kind": "entry", "target_id": "target"}]
            },
        )
        entry_id = "r1:controller:controller:script:000:entry"
        expiry = resolve_expiry_index(
            controller_entry,
            entry_id,
            {
                "kind": "relative",
                "owner": "triggering_turn",
                "anchor": "end_turn",
                "offset_turns": 0,
            },
        )
        self.assertEqual(controller_entry.events[expiry].event_id, "r1:controller:turn:end")

        target_start = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
            target_events_by_round={
                "target": {1: [{"kind": "activation", "phase": "start"}]}
            },
        )
        activation_id = "r1:target:target:script:000:activation"
        expiry = resolve_expiry_index(
            target_start,
            activation_id,
            {
                "kind": "relative",
                "owner": "triggering_turn",
                "anchor": "end_turn",
                "offset_turns": 0,
            },
        )
        self.assertEqual(target_start.events[expiry].event_id, "r1:target:target:turn:end")

    def test_typed_event_matching_and_state_driven_durations(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
            target_events_by_round={
                "target": {
                    1: [
                        {"kind": "entry", "phase": "before_movement"},
                        {"kind": "instantaneous_resolution", "phase": "end"},
                    ]
                }
            },
        )
        entry = schedule.event("r1:target:target:script:000:entry")
        instant = schedule.event(
            "r1:target:target:script:001:instantaneous_resolution"
        )
        self.assertTrue(
            typed_event_matches(
                entry,
                {"kind": "entry", "owner": "any_creature", "turn_anchor": "during_turn"},
                target_id="target",
            )
        )
        self.assertTrue(
            typed_event_matches(instant, {"kind": "instantaneous_resolution"})
        )
        end = schedule.event("r1:target:target:turn:end")
        self.assertTrue(
            typed_event_matches(
                end,
                {"kind": "turn", "owner": "target", "turn_anchor": "end"},
                target_id="target",
            )
        )
        self.assertTrue(
            typed_event_matches(
                end,
                {"kind": "turn", "owner": "triggering_turn", "turn_anchor": "end"},
                triggering_turn_id=end.turn_id,
            )
        )
        with self.assertRaisesRegex(TimelineError, "must use end"):
            typed_event_matches(
                end,
                {"kind": "turn", "owner": "triggering_turn", "turn_anchor": "start"},
                triggering_turn_id=end.turn_id,
            )
        self.assertEqual(
            resolve_expiry_index(
                schedule,
                instant.event_id,
                {"kind": "instantaneous"},
            ),
            instant.sequence,
        )
        self.assertIsNone(
            resolve_expiry_index(
                schedule,
                entry.event_id,
                {"kind": "while_in_area", "area_id": "frozen_ground"},
            )
        )
        self.assertIsNone(
            resolve_expiry_index(
                schedule,
                entry.event_id,
                {"kind": "concentration", "maximum_value": 1, "unit": "minute"},
            )
        )

    def test_hit_and_damage_context_match_the_requested_target(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target", "other"],
            controller_events_by_round={
                1: [
                    {"kind": "hit", "target_id": "target"},
                    {"kind": "damage_context", "target_id": "target"},
                    {"kind": "activation", "target_id": "target"},
                ]
            },
            target_attack_counts={"target": 0, "other": 0},
        )
        hit = next(event for event in schedule.events if event.kind == "hit")
        damage = next(
            event for event in schedule.events
            if event.kind == "damage_context"
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        for event in (hit, damage):
            self.assertTrue(typed_event_matches(
                event,
                {"kind": event.kind},
                target_id="target",
            ))
            self.assertFalse(typed_event_matches(
                event,
                {"kind": event.kind},
                target_id="other",
            ))
        self.assertTrue(typed_event_matches(
            activation,
            {"kind": "activation"},
            target_id="other",
        ))


    def test_compiled_save_trigger_matches_only_the_target_save_opportunity(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target", "other"],
            target_attack_counts={"target": 0, "other": 0},
            target_events_by_round={
                "target": {
                    1: [
                        {"kind": "save_opportunity", "phase": "start"},
                        {"kind": "activation", "phase": "end"},
                    ]
                }
            },
        )
        save = schedule.event("r1:target:target:script:000:save_opportunity")
        activation = schedule.event("r1:target:target:script:001:activation")

        self.assertTrue(typed_event_matches(save, {"kind": "save"}, target_id="target"))
        self.assertFalse(typed_event_matches(save, {"kind": "save"}, target_id="other"))
        self.assertFalse(
            typed_event_matches(activation, {"kind": "save"}, target_id="target")
        )
        with self.assertRaisesRegex(TimelineError, "save event has unknown fields"):
            typed_event_matches(
                save,
                {"kind": "save", "owner": "target"},
                target_id="target",
            )


class ProneAndAreaTests(unittest.TestCase):
    def test_remain_prone_and_stand_are_distinct_actor_selected_operations(self) -> None:
        operations = enumerate_prone_movement_operations(
            target_id="target",
            actor_id="target",
            prone=True,
            current_speed_ft=25,
            movement_budget_ft=25,
        )
        self.assertEqual(
            operations[:2],
            [
                {
                    "kind": "remain_prone",
                    "actor_id": "target",
                    "target_id": "target",
                },
                {
                    "kind": "stand",
                    "actor_id": "target",
                    "target_id": "target",
                },
            ],
        )
        remain = prone_movement_response(
            target_id="target",
            actor_id="target",
            kind="remain_prone",
            prone=True,
            current_speed_ft=25,
            movement_budget_ft=25,
        )
        stand = prone_movement_response(
            target_id="target",
            actor_id="target",
            kind="stand",
            prone=True,
            current_speed_ft=25,
            movement_budget_ft=25,
        )
        self.assertEqual(
            (remain["stood"], remain["remaining_movement_ft"], remain["prone_after"]),
            (False, 25, True),
        )
        self.assertEqual(
            (stand["standing_cost_ft"], stand["remaining_movement_ft"]),
            (12, 13),
        )
        self.assertFalse(stand["prone_after"])
        with self.assertRaisesRegex(TimelineError, "explicit prone_operation"):
            area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=[route("exit", distance=5)],
                effective_speeds_ft={"walk": 25},
                prone=True,
            )

    def test_speed_zero_stand_rejection_is_atomic_and_ignores_other_positive_modes(self) -> None:
        operation = {
            "kind": "stand",
            "actor_id": "target",
            "target_id": "target",
        }
        routes = [route(
            "fly_exit",
            mode="fly",
            distance=20,
            environment="airborne",
        )]
        speeds = {"walk": 0, "fly": 60}
        with self.assertRaisesRegex(TimelineError, "Speed 0"):
            area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=routes,
                effective_speeds_ft=speeds,
                prone=True,
                prone_operation=operation,
                current_speed_ft=0,
                movement_budget_ft=60,
            )
        self.assertEqual(operation, {
            "kind": "stand",
            "actor_id": "target",
            "target_id": "target",
        })
        self.assertEqual(speeds, {"walk": 0, "fly": 60})
        self.assertEqual(routes, [route(
            "fly_exit",
            mode="fly",
            distance=20,
            environment="airborne",
        )])

    def test_prone_standing_cost_is_applied_before_area_exit(self) -> None:
        result = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("ground_exit", distance=20)],
            effective_speeds_ft={"walk": 30},
            prone=True,
            prone_operation={
                "kind": "stand",
                "actor_id": "target",
                "target_id": "target",
            },
            current_speed_ft=30,
            movement_budget_ft=30,
        )
        self.assertFalse(result["exited"])
        self.assertEqual(
            result["selected_route"]["prone_response"]["standing_cost_ft"],
            15,
        )
        self.assertEqual(
            result["selected_route"]["prone_response"]["remaining_movement_ft"],
            15,
        )
        self.assertEqual(result["selected_route"]["progress_ft"], 15)
        self.assertEqual(result["selected_route"]["remaining_distance_ft"], 5)
        self.assertEqual([event["kind"] for event in result["events"]], ["stand"])

    def test_no_usable_area_route_cannot_stand_but_can_remain_prone(self) -> None:
        context = {
            "target_id": "target",
            "membership": True,
            "effect_active": True,
            "routes": [route(
                "incompatible_exit",
                mode="fly",
                distance=20,
                compatible=False,
                environment="airborne",
            )],
            "effective_speeds_ft": {"walk": 30, "fly": 60},
            "prone": True,
            "current_speed_ft": 30,
            "movement_budget_ft": 30,
        }
        with self.assertRaisesRegex(TimelineError, "valid usable route"):
            area_response(
                "shortest_route_v1",
                **context,
                prone_operation={
                    "kind": "stand",
                    "actor_id": "target",
                    "target_id": "target",
                },
            )
        remain = area_response(
            "shortest_route_v1",
            **context,
            prone_operation={
                "kind": "remain_prone",
                "actor_id": "target",
                "target_id": "target",
            },
        )
        self.assertEqual(remain["reason"], "remain_prone")
        self.assertTrue(remain["prone_after"])
        self.assertIsNone(remain["selected_route"])

    def test_voluntary_drop_prone_costs_no_action_or_movement(self) -> None:
        response = prone_movement_response(
            target_id="target",
            actor_id="target",
            kind="drop_prone",
            prone=False,
            current_speed_ft=30,
            movement_budget_ft=17,
        )
        self.assertEqual(response["action_cost"], 0)
        self.assertEqual(response["movement_cost_ft"], 0)
        self.assertEqual(response["remaining_movement_ft"], 17)
        self.assertTrue(response["dropped_prone"])
        self.assertTrue(response["prone_after"])

    def test_crawl_costs_two_feet_per_foot_and_retains_prone(self) -> None:
        response = prone_movement_response(
            target_id="target",
            actor_id="target",
            kind="crawl",
            prone=True,
            current_speed_ft=30,
            movement_budget_ft=25,
            distance_feet=10,
        )
        self.assertEqual(response["crawl_extra_cost_ft"], 10)
        self.assertEqual(response["movement_cost_ft"], 20)
        self.assertEqual(response["remaining_movement_ft"], 5)
        self.assertTrue(response["prone_after"])

    def test_crawl_in_difficult_terrain_costs_three_feet_per_foot(self) -> None:
        result = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("difficult_exit", distance=10, multiplier=2)],
            effective_speeds_ft={"walk": 30},
            prone=True,
            prone_operation={
                "kind": "crawl",
                "actor_id": "target",
                "target_id": "target",
                "distance_feet": 10,
            },
            current_speed_ft=30,
            movement_budget_ft=30,
        )
        response = result["prone_response"]
        self.assertEqual(response["crawl_extra_cost_ft"], 20)
        self.assertEqual(response["movement_cost_ft"], 30)
        self.assertEqual(response["remaining_movement_ft"], 0)
        self.assertTrue(result["exited"])
        self.assertTrue(result["prone_after"])

    def test_selected_stand_clears_prone_before_first_attack(self) -> None:
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            with self.subTest(convention=convention):
                schedule = build_schedule(
                    convention,
                    ["target"],
                    target_attack_counts={"target": [1, 0, 0]},
                )
                movement = schedule.event("r1:target:target:turn:movement")
                attack = schedule.event("r1:target:target:turn:attack:001")
                response = prone_movement_response(
                    target_id="target",
                    actor_id="target",
                    kind="stand",
                    prone=True,
                    current_speed_ft=30,
                    movement_budget_ft=30,
                )
                self.assertLess(movement.sequence, attack.sequence)
                self.assertTrue(response["stood"])
                self.assertFalse(response["prone_after"])

    def test_frozen_ground_exit_is_available_before_later_turn_windows(self) -> None:
        speeds = {"walk": 30}
        response = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("frozen_exit", distance=15, multiplier=2)],
            effective_speeds_ft=speeds,
            while_in_area_component_ids=["frozen_ground_difficult_terrain"],
        )
        self.assertTrue(response["exited"])
        self.assertEqual(response["ended_component_ids"], [
            "frozen_ground_difficult_terrain"
        ])
        self.assertEqual(speeds, {"walk": 30})
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            schedule = build_schedule(
                convention,
                ["target"],
                target_attack_counts={"target": [1, 0, 0]},
            )
            movement = schedule.event("r1:target:target:turn:movement")
            active_turn = schedule.event("r1:target:target:turn:active_turn")
            attack = schedule.event("r1:target:target:turn:attack:001")
            self.assertLess(movement.sequence, active_turn.sequence)
            self.assertLess(movement.sequence, attack.sequence)

    def test_ball_lightning_exit_ends_only_while_in_area_components_pre_attack(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": [1, 0, 0]},
        )
        response = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("ball_lightning_exit", distance=10)],
            effective_speeds_ft={"walk": 30},
            while_in_area_component_ids=[
                "ball_lightning_attack_disadvantage",
                "ball_lightning_reaction_denial",
            ],
            independent_component_ids=["independently_timed_component"],
        )
        movement = schedule.event("r1:target:target:turn:movement")
        active_turn = schedule.event("r1:target:target:turn:active_turn")
        attack = schedule.event("r1:target:target:turn:attack:001")
        self.assertTrue(response["exited"])
        self.assertLess(movement.sequence, active_turn.sequence)
        self.assertLess(movement.sequence, attack.sequence)
        self.assertEqual(response["ended_component_ids"], [
            "ball_lightning_attack_disadvantage",
            "ball_lightning_reaction_denial",
        ])
        self.assertEqual(
            response["retained_component_ids"],
            ["independently_timed_component"],
        )

    def test_speed_zero_preserves_prone_and_area_exposure_through_attacks(self) -> None:
        schedule = build_schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": [2, 0, 0]},
        )
        response = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("blocked_exit", distance=5)],
            effective_speeds_ft={"walk": 30},
            speed_zero=True,
            prone=True,
            prone_operation={
                "kind": "remain_prone",
                "actor_id": "target",
                "target_id": "target",
            },
            current_speed_ft=0,
            movement_budget_ft=0,
            while_in_area_component_ids=["area_exposure"],
        )
        movement = schedule.event("r1:target:target:turn:movement")
        attacks = [
            event
            for event in schedule.events
            if event.turn_id == movement.turn_id
            and event.kind == "target_attack_opportunity"
        ]
        self.assertEqual(response["reason"], "remain_prone")
        self.assertTrue(response["membership_after"])
        self.assertTrue(response["prone_after"])
        self.assertEqual(len(attacks), 2)
        self.assertTrue(all(movement.sequence < event.sequence for event in attacks))
        self.assertFalse(any(
            event.kind == "target_movement_opportunity"
            and event.sequence > attacks[-1].sequence
            and event.turn_id == movement.turn_id
            for event in schedule.events
        ))

    def test_frozen_ground_cost_reduces_progress_without_mutating_speed(self) -> None:
        speeds = effective_movement_speeds({"walk": 30})
        result = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("ground_exit", distance=40, multiplier=2)],
            effective_speeds_ft=speeds,
        )
        self.assertEqual(speeds["walk"], 30)
        self.assertEqual(result["selected_route"]["progress_ft"], 15)
        self.assertEqual(result["selected_route"]["remaining_distance_ft"], 25)
        self.assertTrue(result["membership_after"])

    def test_mixed_speed_operations_require_and_honor_explicit_order(self) -> None:
        with self.assertRaisesRegex(TimelineError, "explicit operation order"):
            effective_movement_speeds(
                {"walk": 25},
                flat_reductions_ft={"walk": 5},
                fractional_multipliers={"walk": Fraction(1, 2)},
            )
        flat_first = effective_movement_speeds(
            {"walk": 25},
            flat_reductions_ft={"walk": 5},
            fractional_multipliers={"walk": Fraction(1, 2)},
            mixed_operation_order=("flat", "fraction"),
        )
        fraction_first = effective_movement_speeds(
            {"walk": 25},
            flat_reductions_ft={"walk": 5},
            fractional_multipliers={"walk": Fraction(1, 2)},
            mixed_operation_order=("fraction", "flat"),
        )
        self.assertEqual(flat_first["walk"], 10)
        self.assertEqual(fraction_first["walk"], 7)

    def test_remaining_route_distance_is_deterministic_across_three_turns(self) -> None:
        distances = [40, 25, 10]
        remaining = []
        final = None
        for distance in distances:
            final = area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=[route("ground_exit", distance=distance, multiplier=2)],
                effective_speeds_ft={"walk": 30},
                while_in_area_component_ids=["ball_lightning_area"],
                independent_component_ids=["frozen_ground_failed_save"],
            )
            remaining.append(
                final["selected_route"]["remaining_distance_ft"]
            )
        self.assertEqual(remaining, [25, 10, 0])
        self.assertTrue(final["exited"])
        self.assertEqual(final["ended_component_ids"], ["ball_lightning_area"])
        self.assertEqual(
            final["retained_component_ids"],
            ["frozen_ground_failed_save"],
        )

    def test_shortest_legal_route_uses_typed_mode_and_environment(self) -> None:
        result = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[
                route("slow_ground", distance=20, multiplier=2),
                route(
                    "fast_air",
                    mode="fly",
                    distance=40,
                    multiplier=1,
                    environment="airborne",
                ),
                route(
                    "blocked_liquid",
                    mode="swim",
                    distance=5,
                    compatible=False,
                    environment="liquid",
                ),
            ],
            effective_speeds_ft={"walk": 30, "fly": 60, "swim": 30},
        )
        selected = result["selected_route"]
        self.assertEqual(selected["route_id"], "fast_air")
        self.assertEqual(selected["mode"], "fly")
        self.assertEqual(selected["environment"], "airborne")
        self.assertTrue(result["exited"])

    def test_movement_mode_denial_blocks_only_the_affected_route(self) -> None:
        result = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[
                route("walk_exit", distance=5),
                route(
                    "fly_exit",
                    mode="fly",
                    distance=10,
                    environment="airborne",
                ),
            ],
            effective_speeds_ft={"walk": 30, "fly": 30},
            denied_modes=["walk"],
        )
        self.assertTrue(result["exited"])
        self.assertEqual(result["selected_route"]["route_id"], "fly_exit")

    def test_speed_zero_and_fixed_occupancy_preserve_membership(self) -> None:
        blocked = area_response(
            "shortest_route_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            routes=[route("exit", distance=5)],
            effective_speeds_ft={"walk": 30},
            speed_zero=True,
        )
        self.assertEqual(blocked["reason"], "movement_unavailable")
        self.assertTrue(blocked["membership_after"])
        fixed = area_response(
            "fixed_occupancy_v1",
            target_id="target",
            membership=True,
            effect_active=True,
            while_in_area_component_ids=["area_effect"],
        )
        self.assertEqual(fixed["reason"], "fixed_occupancy")
        self.assertTrue(fixed["membership_after"])

    def test_missing_route_data_fails_closed(self) -> None:
        with self.assertRaisesRegex(TimelineError, "typed route"):
            area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=None,
                effective_speeds_ft={"walk": 30},
            )
        incomplete = route("bad")
        incomplete.pop("distance_to_exit_ft")
        with self.assertRaisesRegex(TimelineError, "missing=.*distance_to_exit_ft"):
            area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=[incomplete],
                effective_speeds_ft={"walk": 30},
            )
        with self.assertRaisesRegex(TimelineError, "Missing effective speed"):
            area_response(
                "shortest_route_v1",
                target_id="target",
                membership=True,
                effect_active=True,
                routes=[route("air", mode="fly", environment="airborne")],
                effective_speeds_ft={"walk": 30},
            )

    def test_moving_area_entry_and_once_per_turn_frequency_are_explicit(self) -> None:
        ignored = area_entry(
            target_id="target",
            turn_id="turn_1",
            was_member=False,
            is_member=True,
            caused_by_area_movement=True,
            moved_area_counts_as_entry=False,
            frequency="once_per_turn",
        )
        self.assertFalse(ignored["triggered"])
        self.assertEqual(ignored["reason"], "moved_area_does_not_count")
        accepted = area_entry(
            target_id="target",
            turn_id="turn_1",
            was_member=False,
            is_member=True,
            caused_by_area_movement=True,
            moved_area_counts_as_entry=True,
            frequency="once_per_turn",
        )
        self.assertTrue(accepted["triggered"])
        duplicate = area_entry(
            target_id="target",
            turn_id="turn_1",
            was_member=False,
            is_member=True,
            caused_by_area_movement=True,
            moved_area_counts_as_entry=True,
            frequency="once_per_turn",
            prior_trigger_turn_ids=accepted["triggered_turn_ids"],
        )
        self.assertFalse(duplicate["triggered"])
        self.assertEqual(duplicate["reason"], "once_per_turn_already_triggered")


class RepeatSaveAndConcentrationTests(unittest.TestCase):
    def test_three_failed_repeat_saves_have_exact_one_eighth_survival(self) -> None:
        result = repeat_save_survival(Fraction(1, 2), 3)
        self.assertEqual(
            result["survival_probability"],
            {"numerator": 1, "denominator": 8},
        )
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(
            result["records"][1]["active_after"],
            {"numerator": 1, "denominator": 4},
        )

    def test_repeat_save_success_can_create_authoritative_current_position_fall(self) -> None:
        fall = airborne_fall_transition(
            target_id="target",
            airborne=True,
            can_hover=True,
            structured_fall=True,
            source_component_id="mass_levitation_elevation",
        )
        self.assertTrue(fall["falls"])
        self.assertEqual(fall["origin"], "current_position")
        self.assertIsNone(fall["damage"])
        self.assertIsNone(fall["altitude_ft"])

    def test_startup_blood_tax_is_exempt_and_later_tax_uses_exact_dc(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=0,
        )
        start = tracker.start(
            "mass_levitation",
            event_id="activation",
            startup_blood_tax=7,
        )
        self.assertFalse(start["check_required"])
        self.assertEqual(start["reason"], "startup_blood_tax_exemption")
        check = tracker.check(
            amount=40,
            source="later_blood_tax",
            event_id="later_tax",
            outcome="success",
            roll_kernel=[
                {"roll": 10, "probability": Fraction(1, 2)},
                {"roll": 20, "probability": Fraction(1, 2)},
            ],
        )
        self.assertEqual(check["dc"], 20)
        self.assertEqual(
            check["success_probability"],
            {"numerator": 1, "denominator": 2},
        )
        self.assertEqual([row["kind"] for row in tracker.records], [
            "concentration_start",
            "concentration_check",
        ])
        self.assertTrue(all(
            row["owner_actor_id"] == "controller"
            for row in tracker.records
        ))
        self.assertEqual(concentration_dc(0), 10)
        self.assertEqual(concentration_dc(21), 10)
        self.assertEqual(concentration_dc(100), 30)

    def test_failed_later_check_ends_components_area_and_structured_elevation(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=3,
        )
        tracker.start(
            "mass_levitation",
            event_id="activation",
            concentration_component_ids=["elevation", "impairment"],
            area_ids=["levitation_area"],
            fall_target_ids=["target_a", "target_b"],
        )
        tracker.check(
            amount=12,
            source="damage",
            event_id="damage_event",
            outcome="failure",
            success_probability=Fraction(1, 2),
        )
        self.assertIsNone(tracker.active_effect_id)
        end = tracker.records[-1]
        self.assertEqual(end["reason"], "failed_concentration_save")
        self.assertEqual(end["ended_component_ids"], ["elevation", "impairment"])
        self.assertEqual(end["ended_area_ids"], ["levitation_area"])
        self.assertTrue(end["execute_concentration_end_gates"])
        self.assertEqual(
            [row["target_id"] for row in end["fall_transitions"]],
            ["target_a", "target_b"],
        )
        self.assertTrue(all(row["origin"] == "current_position" for row in end["fall_transitions"]))
        self.assertTrue(all(row["damage"] is None for row in end["fall_transitions"]))

    def test_concentration_check_rejects_a_zero_probability_selected_outcome(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=0,
        )
        tracker.start("effect", event_id="activation")
        with self.assertRaisesRegex(TimelineError, "zero probability"):
            tracker.check(
                amount=10,
                source="damage",
                event_id="impossible_failure",
                outcome="failure",
                success_probability=1,
            )
        with self.assertRaisesRegex(TimelineError, "zero probability"):
            tracker.check(
                amount=10,
                source="damage",
                event_id="impossible_success",
                outcome="success",
                success_probability=0,
            )
        self.assertEqual(
            [row["kind"] for row in tracker.records],
            ["concentration_start"],
        )
        self.assertEqual(tracker.active_effect_id, "effect")

    def test_concentration_roll_kernel_requires_unique_d20_outcomes(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=0,
        )
        tracker.start("effect", event_id="activation")
        cases = (
            ([{"roll": 100, "probability": 1}], "between 1 and 20"),
            ([{"roll": 10, "probability": Fraction(1, 2)}, {"roll": 10, "probability": Fraction(1, 2)}], "duplicate roll"),
        )
        for index, (kernel, message) in enumerate(cases):
            with self.subTest(message=message):
                with self.assertRaisesRegex(TimelineError, message):
                    tracker.check(
                        amount=10,
                        source="damage",
                        event_id=f"invalid_kernel_{index}",
                        outcome="success",
                        roll_kernel=kernel,
                    )
        self.assertEqual([row["kind"] for row in tracker.records], ["concentration_start"])

    def test_one_slot_replacement_and_every_explicit_end_reason_are_recorded(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=0,
        )
        tracker.start("first", event_id="first_start")
        tracker.start("second", event_id="second_start")
        self.assertEqual(tracker.records[1]["reason"], "new_concentration_replacement")
        self.assertEqual(tracker.records[1]["effect_id"], "first")
        self.assertEqual(tracker.active_effect_id, "second")
        tracker.end(reason="voluntary_end", event_id="voluntary")
        for reason in (
            "duration_expiry",
            "controller_incapacitated",
            "controller_death",
        ):
            tracker.start(reason, event_id=reason + "_start")
            end = tracker.end(reason=reason, event_id=reason + "_end")
            self.assertTrue(end["changed"])
            self.assertEqual(end["reason"], reason)
        json.dumps(tracker.to_dict(), sort_keys=True, allow_nan=False)

    def test_concentration_end_requires_the_exact_asserted_owner(self) -> None:
        tracker = ConcentrationTracker(
            owner_actor_id="controller",
            save_bonus=0,
        )
        start = tracker.start("effect", event_id="activation")
        before = tracker.to_dict()
        with self.assertRaisesRegex(TimelineError, "does not match"):
            tracker.end(
                reason="controller_incapacitated",
                event_id="wrong_owner_end",
                owner_actor_id="other_actor",
            )
        self.assertEqual(tracker.to_dict(), before)
        end = tracker.end(
            reason="controller_incapacitated",
            event_id="exact_owner_end",
            owner_actor_id="controller",
        )
        self.assertEqual(start["owner_actor_id"], "controller")
        self.assertEqual(end["owner_actor_id"], "controller")
        self.assertEqual(tracker.to_dict()["owner_actor_id"], "controller")
        self.assertIsNone(tracker.active_effect_id)

    def test_airborne_fall_requires_supplied_state_and_preserves_hover_exception(self) -> None:
        grounded = airborne_fall_transition(
            target_id="grounded",
            airborne=False,
            can_hover=False,
            prone=True,
        )
        hover = airborne_fall_transition(
            target_id="hover",
            airborne=True,
            can_hover=True,
            fly_speed_ft=0,
        )
        prone = airborne_fall_transition(
            target_id="prone",
            airborne=True,
            can_hover=False,
            prone=True,
        )
        self.assertFalse(grounded["falls"])
        self.assertEqual(grounded["reason"], "not_airborne")
        self.assertFalse(hover["falls"])
        self.assertEqual(hover["reason"], "hover_or_explicit_prevention")
        self.assertTrue(prone["falls"])


class DisplacementEpochTests(unittest.TestCase):
    def test_ten_foot_push_is_nonzero_under_all_registered_functions(self) -> None:
        self.assertAlmostEqual(displacement_function("sqrt_5ft_v1", 10), math.sqrt(2))
        self.assertAlmostEqual(displacement_function("log2_5ft_v1", 10), math.log2(3))
        self.assertEqual(displacement_function("banded_10ft_v1", 10), 1)
        tracker = DisplacementEpochs()
        record = tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="push",
        )
        self.assertTrue(
            all(row["incremental_value"] > 0 for row in record["functions"])
        )

    def test_push_then_pull_does_not_farm_inside_the_prior_maximum(self) -> None:
        tracker = DisplacementEpochs()
        tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="push",
        )
        pull = tracker.apply(
            target_id="target",
            vector_ft=(-10, 0),
            source_component_id="pull",
        )
        self.assertEqual(pull["raw_net_feet"], 0)
        self.assertEqual(pull["previous_epoch_maximum_feet"], 10)
        self.assertEqual(pull["new_epoch_maximum_feet"], 10)
        self.assertTrue(
            all(row["incremental_value"] == 0 for row in pull["functions"])
        )

    def test_same_direction_rewards_only_incremental_maximum(self) -> None:
        tracker = DisplacementEpochs()
        tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="first_push",
        )
        second = tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="second_push",
        )
        functions = {
            row["function_id"]: row["incremental_value"]
            for row in second["functions"]
        }
        self.assertEqual(second["raw_net_feet"], 20)
        self.assertAlmostEqual(
            functions["sqrt_5ft_v1"],
            2 - math.sqrt(2),
        )
        self.assertAlmostEqual(
            functions["log2_5ft_v1"],
            math.log2(5) - math.log2(3),
        )
        self.assertEqual(functions["banded_10ft_v1"], 1)

    def test_perpendicular_vectors_use_net_euclidean_distance(self) -> None:
        tracker = DisplacementEpochs()
        tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="east",
        )
        north = tracker.apply(
            target_id="target",
            vector_ft=(0, 10),
            source_component_id="north",
        )
        self.assertEqual(north["net_vector_ft"], [10.0, 10.0, 0.0])
        self.assertAlmostEqual(north["raw_net_feet"], math.sqrt(200))
        self.assertLess(north["raw_net_feet"], 20)
        self.assertEqual(vertical_displacement_vector(15), (0.0, 0.0, 15.0))

    def test_legal_self_movement_resets_but_speed_zero_carries_epoch(self) -> None:
        tracker = DisplacementEpochs()
        tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="push",
        )
        blocked = tracker.self_movement_opportunity(
            target_id="target",
            legal=True,
            speed_zero=True,
        )
        self.assertFalse(blocked["reset"])
        no_gain = tracker.apply(
            target_id="target",
            vector_ft=(-10, 0),
            source_component_id="pull",
        )
        self.assertTrue(
            all(row["incremental_value"] == 0 for row in no_gain["functions"])
        )
        reset = tracker.self_movement_opportunity(
            target_id="target",
            legal=True,
        )
        self.assertTrue(reset["reset"])
        self.assertEqual(reset["new_epoch"], 2)
        new_epoch = tracker.apply(
            target_id="target",
            vector_ft=(10, 0),
            source_component_id="new_push",
        )
        self.assertEqual(new_epoch["previous_epoch_maximum_feet"], 0)
        self.assertTrue(
            all(row["incremental_value"] > 0 for row in new_epoch["functions"])
        )

    def test_displacement_records_are_json_safe_and_contain_no_speculative_value(self) -> None:
        tracker = DisplacementEpochs()
        tracker.apply(
            target_id="target",
            vector_ft=(0, 0, 10),
            source_component_id="vertical_lift",
        )
        payload = json.dumps(tracker.to_dict(), sort_keys=True, allow_nan=False)
        for forbidden in (
            "cliff",
            "hazard",
            "opportunity_attack",
            "falling_damage",
            "ally_combo",
        ):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
