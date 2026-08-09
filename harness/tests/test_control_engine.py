"""Public-facade and architecture tests for the shared control engine."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from fractions import Fraction
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from harness.control_catalog import DIAGNOSTIC_FAMILIES, SenseQueryResult
from harness.control_engine import (
    AreaGeometryUpdate,
    AreaRouteGeometry,
    ControlEngine,
    ControlEngineError,
    ControlEngineResult,
    ENGINE_VERSION,
    ScenarioConvention,
    VersionProvenance,
    reliability_result_to_dict,
    validate_engine,
)
from harness.control_graph import (
    D20ProbabilityKernel,
    ImmunitySuppression,
    ProbabilityKernelIdentity,
    ProbabilityContext,
    ReliabilityEvent,
    ReliabilityResult,
    ReliabilityTarget,
    QualifiedId,
    SelectorContext,
    _frozen_map,
)
from harness.control_timeline import ConcentrationTracker, TimelineError


def _reliability_for_targets(
    effect_id: str,
    target_ids: tuple[str, ...],
    *,
    immunity_suppressions: tuple[ImmunitySuppression, ...] = (),
) -> ReliabilityResult:
    return ReliabilityResult(
        effect_id=effect_id,
        target_ids=target_ids,
        component_reliability=(),
        gate_probabilities=(),
        branch_probabilities=(),
        repeat_survival=(),
        immunity_suppressions=immunity_suppressions,
        any_candidate_probability=Fraction(0),
        any_component_probability=Fraction(0),
        any_candidate_by_target=tuple(
            (target_id, Fraction(0)) for target_id in target_ids
        ),
        any_component_by_target=tuple(
            (target_id, Fraction(0)) for target_id in target_ids
        ),
        final_world_count=1,
    )


def _reliability(
    effect_id: str,
    target_id: str = "fixture_target",
) -> ReliabilityResult:
    return _reliability_for_targets(effect_id, (target_id,))


def _single_selector_membership(program, target_id: str) -> dict[str, list[str]]:
    return {
        selector.selector_id: [target_id]
        for selector in program.selectors
    }


def _selector_context_for(*target_ids: str) -> SelectorContext:
    return SelectorContext(
        controller_can_see_by_target={target_id: True for target_id in target_ids},
        target_size_by_id={target_id: "medium" for target_id in target_ids},
        controller_proficiency_bonus=6,
    )


def _activate_component(
    state,
    program,
    component,
    *,
    target_id: str = "target",
    event_id: str = "fixture:apply",
) -> None:
    state.apply_component(
        effect_id=program.effect_id,
        component={
            "component_id": component.component_id,
            "magnitude": component.magnitude.data.to_dict(),
            "duration": component.duration.to_dict(),
            "stacking": component.stacking.data.to_dict(),
        },
        target_id=target_id,
        source_actor_id="controller",
        event_id=event_id,
        invocation_id="fixture_invocation",
    )


class ControlEngineFacadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ControlEngine.load()

    def test_load_validates_every_shared_input_without_damage_or_planner_data(self) -> None:
        self.assertEqual(self.engine.authority.projection_version, "2.1.0")
        self.assertEqual(len(self.engine.authority.programs), 35)
        self.assertEqual(len(self.engine.authority.masteries), 3)
        self.assertEqual(len(self.engine.authority.exclusions), 14)
        self.assertEqual(len(self.engine.targets), 28)
        self.assertEqual(len(self.engine.catalog.conditions), 7)
        self.assertEqual(self.engine.config.horizon_rounds, 3)

    def test_version_block_carries_every_selected_identity_and_digest(self) -> None:
        identity = self.engine.version_provenance(
            initiative_convention="fighter_first_v1",
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
        ).to_dict()
        self.assertEqual(identity["engine_version"], ENGINE_VERSION)
        self.assertEqual(identity["authority_projection_version"], "2.1.0")
        self.assertEqual(identity["consequence_catalog_version"], "1.0.0")
        self.assertEqual(identity["primitive_contract_version"], "1.0.0")
        self.assertEqual(identity["normalization_rules_version"], "1.0.0")
        self.assertEqual(identity["timeline_engine_version"], "1.0.0")
        self.assertEqual(identity["engine_config_version"], "1.0.0")
        for key in (
            "engine_implementation_digest",
            "authority_projection_digest",
            "target_supplement_digest",
            "consequence_catalog_digest",
            "engine_config_digest",
        ):
            self.assertRegex(identity[key], r"^[0-9a-f]{64}$")

    def test_unknown_methodology_variant_fails_closed(self) -> None:
        with self.assertRaisesRegex(ControlEngineError, "initiative"):
            self.engine.version_provenance(
                initiative_convention="hidden_default",
                area_response_convention="shortest_route_v1",
                displacement_function_id="sqrt_5ft_v1",
            )

    def test_exact_reliability_serialization_retains_fraction_records(self) -> None:
        serialized = reliability_result_to_dict(_reliability("fixture"))
        self.assertEqual(
            serialized["any_candidate_probability"],
            {"numerator": 0, "denominator": 1},
        )
        self.assertEqual(serialized["explored_state_count"], 1)
        json.dumps(serialized, sort_keys=True, allow_nan=False)

    def test_facade_assembles_all_required_result_surfaces_weight_free(self) -> None:
        program = self.engine.authority.programs[0]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["fixture_target"],
            target_attack_counts={"fixture_target": [1, 0, 2]},
        )
        state = self.engine._new_state()
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="log2_5ft_v1",
            state=state,
        ).to_dict()
        self.assertEqual(
            set(result["primitive_contributions"]),
            set(DIAGNOSTIC_FAMILIES),
        )
        self.assertEqual(result["compiled_program_id"], program.effect_id)
        self.assertEqual(result["explored_state_count"], 1)
        self.assertNotIn("control_value", json.dumps(result).lower())
        first = json.dumps(result, sort_keys=True, allow_nan=False)
        second = json.dumps(result, sort_keys=True, allow_nan=False)
        self.assertEqual(first, second)

    def test_tremorsense_location_awareness_reaches_public_result(self) -> None:
        program = self.engine.authority.programs[0]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["fixture_target"],
            target_attack_counts={"fixture_target": 0},
        )
        resolution = SenseQueryResult(
            alternative_sight=False,
            location_detection=True,
            alternative_sight_evidence=("no_alternative_sight",),
            location_detection_evidence=("tremorsense_contact",),
            alternative_sight_missing_context=(),
            location_detection_missing_context=(),
        )
        normalization = self.engine._new_state().normalize_for_window(
            target_id="fixture_target",
            window_id="fixture_location_window",
            window_kind="location_opportunity",
            context={"sense_resolution": resolution},
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=self.engine._new_state(),
            normalization_results=(normalization,),
        ).to_dict()
        [contribution] = result["primitive_contributions"][
            "retained_unpriced"
        ]
        self.assertEqual(
            contribution["primitive_id"],
            "nonsight_location_awareness",
        )
        self.assertEqual(
            contribution["source_component_ids"],
            ["target_sense:fixture_target:tremorsense"],
        )
        self.assertEqual(
            contribution["context"]["location_detection_evidence"],
            ["tremorsense_contact"],
        )

    def test_scheduled_reaction_normalization_uses_interval_authority(self) -> None:
        program = self.engine.program("snow_chains_t1_control")
        reaction_component = program.component(
            "snow_chains_reaction_denial"
        )
        state = self.engine._new_state()
        _activate_component(state, program, reaction_component)
        unavailable_schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "reaction_window", "target_id": "target"}]
            },
            target_events_by_round={
                "target": {
                    1: [{"kind": "reaction_window", "phase": "start"}]
                }
            },
            target_attack_counts={"target": 0},
            initial_reaction_availability={"target": False},
        )
        reaction_events = [
            event
            for event in unavailable_schedule.events
            if event.kind == "reaction_window"
        ]
        pre_turn = next(
            event
            for event in reaction_events
            if event.reaction_interval_id.startswith("horizon:")
        )
        reset_marker = next(
            event
            for event in reaction_events
            if event.event_id == event.window_id
            and not event.reaction_interval_id.startswith("horizon:")
        )
        post_reset = next(
            event
            for event in reaction_events
            if ":script:" in event.event_id
            and not event.reaction_interval_id.startswith("horizon:")
        )

        unavailable = self.engine._normalize_scheduled_window(
            state=state,
            schedule=unavailable_schedule,
            target_id="target",
            event_id=pre_turn.event_id,
        )
        marker = self.engine._normalize_scheduled_window(
            state=state,
            schedule=unavailable_schedule,
            target_id="target",
            event_id=reset_marker.event_id,
        )
        available_after_reset = self.engine._normalize_scheduled_window(
            state=state,
            schedule=unavailable_schedule,
            target_id="target",
            event_id=post_reset.event_id,
        )
        self.assertFalse(unavailable.contributions)
        self.assertEqual(
            unavailable.suppressions[-1].reason,
            "reaction_unavailable_at_interval_start",
        )
        self.assertFalse(marker.contributions)
        [post_contribution] = available_after_reset.contributions
        self.assertEqual(post_contribution.primitive_id, "reaction_denial")
        self.assertEqual(
            post_contribution.event_or_window_id,
            post_reset.reaction_interval_id,
        )
        self.assertTrue(post_contribution.context["reaction_available"])

        assembled = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=unavailable_schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=state,
            normalization_results=(
                unavailable,
                marker,
                available_after_reset,
            ),
        ).to_dict()
        self.assertEqual(
            len(assembled["primitive_contributions"]["denial"]),
            1,
        )
        [availability_suppression] = [
            row
            for row in assembled["suppression_and_dominance_records"]
            if row["reason"] == "reaction_unavailable_at_interval_start"
        ]
        self.assertEqual(
            availability_suppression["suppressed_source_component_ids"],
            ["snow_chains_t1_control:snow_chains_reaction_denial"],
        )

        available_schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "reaction_window", "target_id": "target"}]
            },
            target_attack_counts={"target": 0},
            initial_reaction_availability={"target": True},
        )
        available_pre_turn = next(
            event
            for event in available_schedule.events
            if event.kind == "reaction_window"
            and event.reaction_interval_id.startswith("horizon:")
        )
        initial = self.engine._normalize_scheduled_window(
            state=state,
            schedule=available_schedule,
            target_id="target",
            event_id=available_pre_turn.event_id,
        )
        self.assertEqual(
            [item.primitive_id for item in initial.contributions],
            ["reaction_denial"],
        )
        with self.assertRaisesRegex(
            ControlEngineError,
            "derived from the schedule",
        ):
            self.engine._normalize_scheduled_window(
                state=state,
                schedule=unavailable_schedule,
                target_id="target",
                event_id=pre_turn.event_id,
                context={"reaction_available": True},
            )

    def test_all_attacks_is_one_public_affected_turn_not_per_attack(self) -> None:
        program = self.engine.program("electron_burst_t2_control")
        state = self.engine._new_state()
        _activate_component(
            state,
            program,
            program.component("electron_burst_attack_disadvantage"),
        )
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": [2, 0, 0]},
        )
        active_turn = next(
            event for event in schedule.events
            if event.kind == "target_active_turn_opportunity"
            and event.round == 1
        )
        attacks = [
            event for event in schedule.events
            if event.kind == "target_attack_opportunity"
            and event.round == 1
        ]
        normalizations = [
            self.engine._normalize_scheduled_window(
                state=state,
                schedule=schedule,
                target_id="target",
                event_id=event.event_id,
            )
            for event in (active_turn, *attacks)
        ]
        self.assertEqual(
            [
                contribution.primitive_id
                for result in normalizations[1:]
                for contribution in result.contributions
                if contribution.primitive_id
                == "offensive_impairment_all_attacks"
            ],
            [],
        )
        assembled = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=state,
            normalization_results=normalizations,
        ).to_dict()
        rows = [
            row for row in assembled["primitive_contributions"]["denial"]
            if row["primitive_id"] == "offensive_impairment_all_attacks"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["unit"], "affected_target_turn")
        self.assertEqual(rows[0]["event_or_window_id"], active_turn.window_id)

    def test_result_model_rejects_all_nested_weight_and_temperature_keys(self) -> None:
        program = self.engine.authority.programs[0]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
        )
        base = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="banded_10ft_v1",
            state=self.engine._new_state(),
        )
        with self.assertRaisesRegex(ControlEngineError, "issued only"):
            replace(
                base,
                final_normalized_state={
                    "target": {"nested": {"control_value": 1}}
                },
            )

    def test_result_uses_schedule_target_order_after_identity_set_validation(self) -> None:
        program = self.engine.authority.programs[0]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target_z", "target_a"],
            target_attack_counts={"target_z": 0, "target_a": 0},
        )
        reliability = _reliability_for_targets(
            program.effect_id,
            ("target_a", "target_z"),
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=reliability,
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=self.engine._new_state(),
        ).to_dict()
        self.assertEqual(result["target_ids"], ["target_z", "target_a"])
        self.assertEqual(
            [
                row["target_id"]
                for row in result["any_candidate_reliability"]["by_target"]
            ],
            ["target_z", "target_a"],
        )
        with self.assertRaisesRegex(ControlEngineError, "same identities"):
            self.engine._assemble_result_legacy(
                effect=program,
                reliability=_reliability_for_targets(
                    program.effect_id,
                    ("target_a", "different_target"),
                ),
                schedule=schedule,
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                state=self.engine._new_state(),
            )

    def test_result_preserves_reliability_immunity_suppression_with_reason(self) -> None:
        program = self.engine.program_for("absolute_zero", 1)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            target_attack_counts={"target": 0},
        )
        suppression = ImmunitySuppression(
            event_id="initial:fixture_gate",
            gate_id="fixture_gate",
            branch_id="fixture_branch",
            target_id="target",
            component_id="absolute_zero_restrained",
            condition="restrained",
            probability=Fraction(1, 2),
        )
        reliability = _reliability_for_targets(
            program.effect_id,
            ("target",),
            immunity_suppressions=(suppression,),
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=reliability,
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=self.engine._new_state(),
        ).to_dict()
        [record] = result["suppression_and_dominance_records"]
        self.assertEqual(
            record["record_type"],
            "reliability_immunity_suppression",
        )
        self.assertEqual(record["reason"], "target_condition_immunity")
        self.assertEqual(record["probability"], {"numerator": 1, "denominator": 2})

    def test_default_candidate_set_excludes_retained_fall_and_elevation(self) -> None:
        program = self.engine.program_for("mass_levitation", 0)
        candidates = set(self.engine.candidate_component_ids(program))
        self.assertIn("mass_levitation_initial_lift", candidates)
        self.assertIn("mass_levitation_restrained", candidates)
        self.assertNotIn("mass_levitation_persistent_elevation", candidates)
        self.assertNotIn("mass_levitation_fall", candidates)
        selector_membership = {
            selector.selector_id: ()
            for selector in program.selectors
        }
        with self.assertRaisesRegex(ControlEngineError, "cannot reclassify"):
            self.engine.reliability(
                program,
                targets=(),
                selector_membership=selector_membership,
                selector_context=_selector_context_for(),
                candidate_component_ids=("mass_levitation_fall",),
                include_initial=False,
            )

    def test_validation_summary_is_compact_and_preserves_scope_counts(self) -> None:
        summary = validate_engine()
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["compiled_programs"], 35)
        self.assertEqual(summary["compiled_masteries"], 3)
        self.assertEqual(summary["preserved_exclusions"], 14)
        self.assertEqual(summary["control_target_rows"], 28)
        self.assertEqual(summary["fixture_cases"], 72)
        self.assertEqual(len(summary["initiative_schedules"]), 2)
        self.assertEqual(len(summary["area_response_conventions"]), 2)
        self.assertEqual(len(summary["displacement_functions"]), 3)


class ControlExecutionSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ControlEngine.load()

    def _absolute_zero_session(
        self,
        *,
        target_id: str = "target",
        save_inputs: Mapping[str, Any] | None = None,
        normalize_movement: bool = False,
        normalize_attack: bool = False,
        target_mechanics: Mapping[str, Any] | None = None,
        kernel: Any = None,
        area_response_convention: str = "fixed_occupancy_v1",
        area_geometry_updates: Sequence[AreaGeometryUpdate] = (),
    ):
        program = self.engine.program("absolute_zero_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            [target_id],
            controller_events_by_round={
                1: [{
                    "kind": "save_opportunity",
                    "target_id": target_id,
                    "window_id": "initial_save_window",
                }],
            },
            target_attack_counts={target_id: [1, 0, 0]},
        )
        save_event = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        operation_inputs: dict[str, dict[str, Any]] = {}
        if save_inputs is not None:
            operation_inputs[save_event.event_id] = dict(save_inputs)
        if normalize_movement:
            movement_event = next(
                event for event in schedule.events
                if event.kind == "target_movement_opportunity"
            )
            operation_inputs[movement_event.event_id] = {
                "normalization_target_ids": [target_id],
                "normalization_context": {
                    "movement_mode": "walk",
                    "movement_mode_speeds_ft": {"walk": 30},
                },
            }
        if normalize_attack:
            attack_event = next(
                event for event in schedule.events
                if event.kind == "target_attack_opportunity"
            )
            operation_inputs[attack_event.event_id] = {
                "normalization_target_ids": [target_id],
                "normalization_context": {},
            }
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                target_id,
                15,
                {"constitution": 2},
            ),),
            selector_membership={
                "absolute_zero_target": (target_id,),
            },
            selector_context=_selector_context_for("target"),
            schedule=schedule,
            target_mechanics={
                target_id: dict(target_mechanics or {}),
            },
            area_response_convention=area_response_convention,
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            kernel=kernel,
            operation_inputs_by_event=operation_inputs or None,
            area_geometry_updates=area_geometry_updates,
        )
        return session, schedule, save_event

    @staticmethod
    def _finish_absolute_zero(session, save_event, *, outcome="save_success"):
        session.advance_to(save_event.event_id)
        record = session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome=outcome,
            target_id="target",
        )
        session.close_event()
        session.complete()
        return record

    def _finish_absolute_zero_with_normalization(self, session, save_event):
        session.advance_to(save_event.event_id)
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        movement = next(
            event for event in session.schedule.events
            if event.kind == "target_movement_opportunity"
        )
        session.advance_to(movement.event_id)
        normalization = session.normalize(target_id="target")
        session.close_event()
        session.complete()
        return normalization

    @staticmethod
    def _rewrite_record_payload(record, payload: Mapping[str, Any]) -> None:
        payload_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        identity = {
            "scenario_digest": record.scenario_digest,
            "event_id": record.event_id,
            "event_sequence": record.event_sequence,
            "operation_sequence": record.operation_sequence,
            "target_id": record.target_id,
            "record_kind": record.record_kind,
            "pre_event_state": json.loads(record.pre_event_state_json),
            "pre_operation_state": json.loads(record.pre_operation_state_json),
            "post_operation_state": json.loads(record.post_operation_state_json),
            "pre_event_route_state": json.loads(
                record.pre_event_route_state_json
            ),
            "pre_operation_route_state": json.loads(
                record.pre_operation_route_state_json
            ),
            "post_operation_route_state": json.loads(
                record.post_operation_route_state_json
            ),
            "payload": json.loads(payload_json),
        }
        record_json = json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        object.__setattr__(record, "payload_json", payload_json)
        object.__setattr__(
            record,
            "payload_sha256",
            hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        )
        object.__setattr__(
            record,
            "record_sha256",
            hashlib.sha256(record_json.encode("utf-8")).hexdigest(),
        )

    def _frozen_ground_session(
        self,
        *,
        initiative: str = "fighter_first_v1",
        target_ids: tuple[str, ...] = ("target",),
        initial_prone: bool = False,
        initial_conditions: tuple[str, ...] = (),
        base_speed: int = 30,
        base_speeds: Mapping[str, int] | None = None,
        route_mode: str = "walk",
        route_distance: int = 5,
        route_multiplier: int = 1,
        route_compatible: bool = True,
        include_start_turn_save: bool = False,
        concentration_save_bonus: int | None = 2,
        raw_second_movement_routes: Sequence[Mapping[str, Any]] | None = None,
        bind_round_one_normalization: bool = True,
    ):
        program = self.engine.program("frozen_ground_t0_control")
        schedule = self.engine.schedule(
            initiative,
            target_ids,
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={target_id: [1, 0, 0] for target_id in target_ids},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        operation_inputs: dict[str, dict[str, Any]] = {}
        reliability_events: tuple[ReliabilityEvent, ...] = ()
        if include_start_turn_save:
            if len(target_ids) != 1:
                raise AssertionError("start-turn helper supports one target")
            target_id = target_ids[0]
            target_start = next(
                event for event in schedule.events
                if event.kind == "target_turn_start"
                and event.round == 1
                and event.target_id == target_id
            )
            gate = program.gate("frozen_ground_t0_start_turn_save")
            reliability_event = ReliabilityEvent.create(
                "frozen_ground_round_1_start_save",
                gate.trigger,
                target_ids=(target_id,),
                gate_ids=(gate.gate_id,),
                window_id=target_start.event_id,
            )
            reliability_events = (reliability_event,)
            operation_inputs[target_start.event_id] = {
                "reliability_event_ids": [reliability_event.event_id],
            }
        for target_id in target_ids:
            active = next(
                event for event in schedule.events
                if event.kind == "target_active_turn_opportunity"
                and event.round == 1
                and event.target_id == target_id
            )
            attack = next(
                event for event in schedule.events
                if event.kind == "target_attack_opportunity"
                and event.round == 1
                and event.target_id == target_id
            )
            if bind_round_one_normalization:
                operation_inputs[active.event_id] = {
                    "normalization_target_ids": [target_id],
                }
                operation_inputs[attack.event_id] = {
                    "normalization_target_ids": [target_id],
                }
        if raw_second_movement_routes is not None:
            if len(target_ids) != 1:
                raise AssertionError("raw route override helper supports one target")
            second_movement = next(
                event for event in schedule.events
                if event.kind == "target_movement_opportunity"
                and event.round == 2
                and event.target_id == target_ids[0]
            )
            operation_inputs[second_movement.event_id] = {
                "area_routes": [dict(route) for route in raw_second_movement_routes],
            }
        mechanics = {
            target_id: {
                "initial_conditions": list(dict.fromkeys((
                    *(("prone",) if initial_prone else ()),
                    *initial_conditions,
                ))),
                "base_speeds_ft": dict(
                    base_speeds
                    if base_speeds is not None
                    else {"walk": base_speed}
                ),
                "movement_mode": (
                    "walk"
                    if base_speeds is None or "walk" in base_speeds
                    else next(iter(base_speeds))
                ),
                "area_membership": True,
                "area_routes": [{
                    "route_id": f"{target_id}_{route_mode}_exit",
                    "mode": route_mode,
                    "distance_to_exit_ft": route_distance,
                    "compatible": route_compatible,
                    "movement_cost_multiplier": route_multiplier,
                    "environment": "grounded",
                }],
            }
            for target_id in target_ids
        }
        session = self.engine.execution_session(
            program,
            targets=tuple(
                ReliabilityTarget(
                    target_id,
                    15,
                    {"constitution": 2, "dexterity": 2},
                )
                for target_id in target_ids
            ),
            selector_membership={
                "frozen_ground_area_targets": target_ids,
            },
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics=mechanics,
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=reliability_events,
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=concentration_save_bonus,
        )
        return session, schedule, activation

    @staticmethod
    def _route_geometry(
        route_id: str,
        *,
        distance: int | float,
        mode: str = "walk",
        compatible: bool = True,
        multiplier: int | float = 1,
        environment: str = "grounded",
    ) -> AreaRouteGeometry:
        return AreaRouteGeometry(
            route_id=route_id,
            mode=mode,
            distance_to_exit_ft=distance,
            compatible=compatible,
            movement_cost_multiplier=multiplier,
            environment=environment,
        )

    def _area_route_row(self, session, target_id: str = "target") -> dict[str, Any]:
        rows = session.area_route_snapshot(target_id)
        self.assertEqual(len(rows), 1)
        return dict(rows[0])

    @staticmethod
    def _movement_event(schedule, *, round_number: int, target_id: str = "target"):
        return next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
            and event.round == round_number
            and event.target_id == target_id
        )

    def _activate_frozen_ground(
        self,
        session,
        activation,
        target_ids: Sequence[str] = ("target",),
    ) -> None:
        session.advance_to(activation.event_id)
        session.start_concentration()
        for target_id in sorted(target_ids):
            activation_record = session.apply_branch(
                gate_id="frozen_ground_t0_activation",
                outcome="no_save",
                target_id=target_id,
            )
            self.assertEqual(
                activation_record.to_dict()["payload"]["gate_id"],
                "frozen_ground_t0_activation",
            )
        session.close_event()

    def _ball_lightning_route_session(
        self,
        *,
        initial_distance: int = 60,
        update_membership: bool | None = None,
        update_distance: int = 10,
        update_route_id: str = "moved_exit",
    ) -> tuple[Any, Any, Mapping[str, Any]]:
        program = self.engine.program("ball_lightning_t2_control")
        controller_events: dict[int, list[dict[str, Any]]] = {
            1: [{"kind": "activation"}],
        }
        if update_membership is not None:
            controller_events[2] = [{"kind": "instantaneous_resolution"}]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round=controller_events,
            target_attack_counts={"target": [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        target_start = next(
            event for event in schedule.events
            if event.kind == "target_turn_start" and event.round == 1
        )
        gate = program.gate("ball_lightning_start_turn_save")
        reliability_event = ReliabilityEvent.create(
            "ball_lightning_round_1_start_save",
            gate.trigger,
            target_ids=("target",),
            gate_ids=(gate.gate_id,),
            window_id=target_start.event_id,
        )
        operation_inputs = {
            target_start.event_id: {
                "reliability_event_ids": [reliability_event.event_id],
            },
        }
        update_event = None
        geometry_updates: tuple[AreaGeometryUpdate, ...] = ()
        if update_membership is not None:
            update_event = next(
                event for event in schedule.events
                if event.kind == "instantaneous_resolution"
            )
            routes = (
                (self._route_geometry(
                    update_route_id,
                    distance=update_distance,
                ),)
                if update_membership else ()
            )
            geometry_updates = (AreaGeometryUpdate(
                effect_id=program.effect_id,
                area_id="ball_lightning_sphere",
                target_id="target",
                event_id=update_event.event_id,
                event_sequence=update_event.sequence,
                new_membership=update_membership,
                routes=routes,
            ),)
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget("target", 15, {"charisma": 2}),),
            selector_membership={
                "ball_lightning_area_targets": ("target",),
            },
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={
                "target": {
                    "base_speeds_ft": {"walk": 30},
                    "movement_mode": "walk",
                    "area_membership": True,
                    "area_routes": [self._route_geometry(
                        "initial_exit",
                        distance=initial_distance,
                    ).route_input()],
                },
            },
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=(reliability_event,),
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
            area_geometry_updates=geometry_updates,
        )
        return session, schedule, {
            "activation": activation,
            "target_start": target_start,
            "gate": gate,
            "update": update_event,
        }

    def _activate_ball_lightning(
        self,
        session,
        events: Mapping[str, Any],
    ) -> None:
        activation = events["activation"]
        target_start = events["target_start"]
        gate = events["gate"]
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.close_event()
        session.advance_to(target_start.event_id)
        session.apply_branch(
            gate_id=gate.gate_id,
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()

    def _ball_membership_session(
        self,
        *,
        initiative: str = "fighter_first_v1",
        area_response_convention: str = "shortest_route_v1",
        target_ids: tuple[str, ...] = ("target",),
        route_distances: Mapping[str, int] | None = None,
        initial_membership: Mapping[str, bool] | None = None,
        speed_zero_first_movement: Sequence[str] = (),
        initial_conditions: Mapping[str, Sequence[str]] | None = None,
        geometry_update: tuple[int, str, bool, int] | None = None,
    ) -> tuple[Any, Any, Mapping[str, Any]]:
        program = self.engine.program("ball_lightning_t2_control")
        controller_events: dict[int, list[dict[str, Any]]] = {
            1: [{"kind": "activation"}],
        }
        if geometry_update is not None:
            update_round, _target_id, _membership, _distance = geometry_update
            controller_events.setdefault(update_round, []).append({
                "kind": "instantaneous_resolution",
            })
        schedule = self.engine.schedule(
            initiative,
            target_ids,
            controller_events_by_round=controller_events,
            target_attack_counts={target_id: [1, 0, 0] for target_id in target_ids},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        gate = program.gate("ball_lightning_start_turn_save")
        starts_by_target: dict[str, tuple[Any, ...]] = {}
        movements_by_target: dict[str, tuple[Any, ...]] = {}
        reliability_events: list[ReliabilityEvent] = []
        operation_inputs: dict[str, dict[str, Any]] = {}
        for target_id in target_ids:
            starts = tuple(
                event for event in schedule.events
                if event.kind == "target_turn_start"
                and event.target_id == target_id
                and event.sequence > activation.sequence
            )[:2]
            if len(starts) != 2:
                raise AssertionError("membership helper requires two post-activation turns")
            starts_by_target[target_id] = starts
            for start in starts:
                reliability_event = ReliabilityEvent.create(
                    f"ball_lightning_{target_id}_round_{start.round}_start_save",
                    gate.trigger,
                    target_ids=(target_id,),
                    gate_ids=(gate.gate_id,),
                    window_id=start.event_id,
                )
                reliability_events.append(reliability_event)
                operation_inputs[start.event_id] = {
                    "reliability_event_ids": [reliability_event.event_id],
                }
            movements_by_target[target_id] = tuple(
                event for event in schedule.events
                if event.kind == "target_movement_opportunity"
                and event.target_id == target_id
                and event.sequence > activation.sequence
            )[:2]

        route_distances = dict(route_distances or {})
        initial_membership = dict(initial_membership or {})
        initial_conditions = dict(initial_conditions or {})
        speed_zero_targets = set(speed_zero_first_movement)
        target_mechanics: dict[str, dict[str, Any]] = {}
        for target_id in target_ids:
            member = initial_membership.get(target_id, True)
            mechanics: dict[str, Any] = {
                "base_speeds_ft": {"walk": 30},
                "movement_mode": "walk",
                "initial_conditions": list(initial_conditions.get(target_id, ())),
            }
            if area_response_convention == "shortest_route_v1":
                mechanics["area_membership"] = member
            if member and area_response_convention == "shortest_route_v1":
                mechanics["area_routes"] = [self._route_geometry(
                    f"{target_id}_initial_exit",
                    distance=route_distances.get(target_id, 10),
                ).route_input()]
            if target_id in speed_zero_targets:
                [first_movement] = movements_by_target[target_id][:1]
                mechanics["base_speeds_ft_by_event"] = {
                    first_movement.event_id: {"walk": 0},
                }
            target_mechanics[target_id] = mechanics

        update_event = None
        updates: tuple[AreaGeometryUpdate, ...] = ()
        if geometry_update is not None:
            update_round, update_target, new_membership, update_distance = (
                geometry_update
            )
            update_event = next(
                event for event in schedule.events
                if event.kind == "instantaneous_resolution"
                and event.round == update_round
            )
            routes = (
                (self._route_geometry(
                    f"{update_target}_reentry_exit",
                    distance=update_distance,
                ),)
                if new_membership else ()
            )
            updates = (AreaGeometryUpdate(
                effect_id=program.effect_id,
                area_id="ball_lightning_sphere",
                target_id=update_target,
                event_id=update_event.event_id,
                event_sequence=update_event.sequence,
                new_membership=new_membership,
                routes=routes,
            ),)

        session = self.engine.execution_session(
            program,
            targets=tuple(
                ReliabilityTarget(target_id, 15, {"charisma": 2})
                for target_id in target_ids
            ),
            selector_membership={
                "ball_lightning_area_targets": target_ids,
            },
            selector_context=_selector_context_for(*target_ids),
            schedule=schedule,
            target_mechanics=target_mechanics,
            area_response_convention=area_response_convention,
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=tuple(reliability_events),
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
            area_geometry_updates=updates,
        )
        return session, schedule, {
            "activation": activation,
            "gate": gate,
            "starts_by_target": starts_by_target,
            "movements_by_target": movements_by_target,
            "update": update_event,
        }

    @staticmethod
    def _start_ball_concentration(session, activation) -> None:
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.close_event()

    @staticmethod
    def _apply_ball_start_save(session, event, *, target_id: str, outcome: str):
        session.advance_to(event.event_id)
        record = session.apply_branch(
            gate_id="ball_lightning_start_turn_save",
            outcome=outcome,
            target_id=target_id,
        )
        session.close_event()
        return record

    def _completed_zero_area_result(
        self,
        area_response_convention: str,
    ) -> dict[str, Any]:
        session, schedule, save = self._absolute_zero_session(
            normalize_movement=True,
            normalize_attack=True,
            area_response_convention=area_response_convention,
        )
        session.advance_to(save.event_id)
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
        )
        session.advance_to(movement.event_id)
        session.normalize(target_id="target")
        session.close_event()
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity"
        )
        session.advance_to(attack.event_id)
        session.normalize(target_id="target")
        session.close_event()
        session.complete()
        return session.result().to_dict()

    def _mass_levitation_session(self, *, bind_future: bool):
        program = self.engine.program("mass_levitation_t2_control")
        controller_events: dict[int, list[dict[str, Any]]] = {
            1: [
                {"kind": "activation"},
                {"kind": "save_opportunity", "target_id": "target"},
            ],
        }
        if bind_future:
            controller_events[2] = [{"kind": "concentration_end"}]
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round=controller_events,
            target_attack_counts={"target": [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        save = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        reliability_events: list[ReliabilityEvent] = []
        operation_inputs: dict[str, dict[str, Any]] = {}
        events: dict[str, Any] = {
            "activation": activation,
            "save": save,
        }
        if bind_future:
            target_start = next(
                event for event in schedule.events
                if event.kind == "target_turn_start" and event.round == 1
            )
            controller_start = next(
                event for event in schedule.events
                if event.kind == "controller_turn_start" and event.round == 2
            )
            end = next(
                event for event in schedule.events
                if event.kind == "concentration_end"
            )
            for label, gate_id, event in (
                (
                    "repeat",
                    "mass_levitation_t2_repeat_saves",
                    target_start,
                ),
                (
                    "reposition",
                    "mass_levitation_t2_controller_reposition",
                    controller_start,
                ),
                (
                    "end",
                    "mass_levitation_t2_concentration_end",
                    end,
                ),
            ):
                gate = program.gate(gate_id)
                reliability_event = ReliabilityEvent.create(
                    f"mass_{label}_event",
                    gate.trigger,
                    target_ids=("target",),
                    gate_ids=(gate.gate_id,),
                    window_id=event.event_id,
                )
                reliability_events.append(reliability_event)
                operation_inputs[event.event_id] = {
                    "reliability_event_ids": [reliability_event.event_id],
                }
                events[label] = event
            damage_gate = program.gate("mass_levitation_t2_damage_context")
            damage_event = ReliabilityEvent.create(
                "mass_damage_event",
                damage_gate.trigger,
                target_ids=("target",),
                gate_ids=(damage_gate.gate_id,),
                window_id="mass_damage_window",
            )
            reliability_events.insert(1, damage_event)
            operation_inputs[target_start.event_id][
                "reliability_event_ids"
            ].append(damage_event.event_id)
            events["damage"] = target_start
            operation_inputs[controller_start.event_id][
                "displacement_vectors"
            ] = {"mass_levitation_reposition": [10, 0, 0]}
            operation_inputs[end.event_id]["concentration_end_reason"] = (
                "voluntary_end"
            )
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget("target", 15, {"strength": 2}),),
            selector_membership={"mass_levitation_targets": ("target",)},
            selector_context=_selector_context_for("target"),
            schedule=schedule,
            target_mechanics={
                "target": {
                    "base_speeds_ft": {"walk": 30},
                    "movement_mode": "walk",
                },
            },
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=tuple(reliability_events),
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
        )
        return session, schedule, events

    def _completed_absolute_zero_session(self):
        session, _schedule, save = self._absolute_zero_session()
        self._finish_absolute_zero(session, save)
        return session

    def _explosion_implosion_session(self, option: str):
        program = self.engine.program("explosion_implosion_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["primary"],
            controller_events_by_round={
                1: [{"kind": "hit", "target_id": "primary"}],
            },
            target_attack_counts={"primary": [0, 0, 0]},
        )
        hit = next(event for event in schedule.events if event.kind == "hit")
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                "primary",
                15,
                {"strength": 2},
            ),),
            selector_membership={
                "explosion_implosion_primary": ("primary",),
                "explosion_implosion_secondary_targets": (),
            },
            selector_context=_selector_context_for("primary"),
            schedule=schedule,
            target_mechanics={"primary": {}},
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(
                attack_bonus=5,
                save_dc=15,
            ),
            choices={"explosion_implosion_mode": option},
        )
        session.advance_to(hit.event_id)
        session.apply_branch(
            gate_id="explosion_implosion_t0_attack",
            outcome="attack_hit",
            target_id="primary",
        )
        session.apply_branch(
            gate_id="explosion_implosion_t0_primary_save",
            outcome="save_success",
            target_id="primary",
        )
        session.close_event()
        session.complete()
        session.result()
        return session

    def test_supported_session_is_deterministic_and_direct_facade_is_closed(self) -> None:
        first, _schedule, first_save = self._absolute_zero_session()
        second, _schedule_2, second_save = self._absolute_zero_session()
        self.assertEqual(first.scenario_digest, second.scenario_digest)
        self._finish_absolute_zero(first, first_save)
        self._finish_absolute_zero(second, second_save)
        first_result = first.result()
        second_result = second.result()
        self.assertEqual(
            json.dumps(first_result.to_dict(), sort_keys=True),
            json.dumps(second_result.to_dict(), sort_keys=True),
        )
        self.assertEqual(first_result.scenario_digest, first.scenario_digest)
        self.assertEqual(
            first_result.scenario_record["probability_kernel"]["kernel_id"],
            "openai.kinetic_vanguard.d20",
        )
        with self.assertRaisesRegex(TypeError, "mappingproxy"):
            first_result.scenario_record["fabricated"] = True
        with self.assertRaisesRegex(ControlEngineError, "issued only"):
            replace(first_result, explored_state_count=999)
        for operation in (
            self.engine.new_state,
            self.engine.new_displacement_epochs,
            self.engine.assemble_result,
            self.engine.apply_resolved_branch,
            self.engine.normalize_scheduled_window,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ControlEngineError, "session"):
                    operation()

    def test_scenario_inputs_reject_coercible_non_json_values(self) -> None:
        class ToDictValue:
            def to_dict(self):
                return {"coerced": True}

        invalid_values = (
            ("tuple", ("walk",)),
            ("set", {"walk"}),
            ("fraction", Fraction(1, 2)),
            ("to_dict", ToDictValue()),
            ("nested_non_string_key", {"nested": {1: "walk"}}),
        )
        for label, value in invalid_values:
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "strict JSON|invalid JSON object key",
                ):
                    self._absolute_zero_session(
                        target_mechanics={"invalid": value},
                    )

        valid, _schedule, _save = self._absolute_zero_session()
        program = self.engine.program("absolute_zero_t0_control")
        with self.assertRaisesRegex(
            ControlEngineError,
            "operation_inputs_by_event must be an object",
        ):
            self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={"absolute_zero_target": ("target",)},
                selector_context=_selector_context_for("target"),
                schedule=valid.schedule,
                target_mechanics={"target": {}},
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
                operation_inputs_by_event=[],  # type: ignore[arg-type]
            )
        for label, payload in (
            ("tuple", {"value": ("x",)}),
            ("non_string_key", {1: "x"}),
        ):
            with self.subTest(schedule_payload=label):
                bad_schedule = self.engine.schedule(
                    "fighter_first_v1",
                    ["target"],
                    controller_events_by_round={
                        1: [{
                            "kind": "save_opportunity",
                            "target_id": "target",
                            "payload": payload,
                        }],
                    },
                    target_attack_counts={"target": [0, 0, 0]},
                )
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "strict JSON|invalid JSON object key",
                ):
                    self.engine.execution_session(
                        program,
                        targets=(ReliabilityTarget(
                            "target",
                            15,
                            {"constitution": 2},
                        ),),
                        selector_membership={
                            "absolute_zero_target": ("target",),
                        },
                        selector_context=_selector_context_for("target"),
                        schedule=bad_schedule,
                        target_mechanics={"target": {}},
                        area_response_convention="fixed_occupancy_v1",
                        displacement_function_id="sqrt_5ft_v1",
                        probability_context=ProbabilityContext(save_dc=15),
                    )
        malformed_events = (
            replace(valid.schedule.events[0], sequence=1),
            *valid.schedule.events[1:],
        )
        malformed_schedule = replace(valid.schedule, events=malformed_events)
        with self.assertRaisesRegex(ControlEngineError, "schedule shape"):
            self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={"absolute_zero_target": ("target",)},
                selector_context=_selector_context_for("target"),
                schedule=malformed_schedule,
                target_mechanics={"target": {}},
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
            )
        unknown_kind_schedule = replace(
            valid.schedule,
            events=(
                replace(valid.schedule.events[0], kind="fictional"),
                *valid.schedule.events[1:],
            ),
        )
        with self.assertRaisesRegex(ControlEngineError, "event identities"):
            self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={"absolute_zero_target": ("target",)},
                selector_context=_selector_context_for("target"),
                schedule=unknown_kind_schedule,
                target_mechanics={"target": {}},
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
            )
        reordered = list(valid.schedule.events)
        movement_index = next(
            index for index, event in enumerate(reordered)
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        attack_index = next(
            index for index, event in enumerate(reordered)
            if event.kind == "target_attack_opportunity" and event.round == 1
        )
        reordered[movement_index], reordered[attack_index] = (
            reordered[attack_index],
            reordered[movement_index],
        )
        reordered = [
            replace(event, sequence=index)
            for index, event in enumerate(reordered)
        ]
        attack_before_movement = replace(
            valid.schedule,
            events=tuple(reordered),
        )
        with self.assertRaisesRegex(ControlEngineError, "movement before"):
            self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={"absolute_zero_target": ("target",)},
                selector_context=_selector_context_for("target"),
                schedule=attack_before_movement,
                target_mechanics={"target": {}},
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
            )

    def test_malformed_area_route_is_rejected_before_session_mutation(self) -> None:
        with self.assertRaisesRegex(
            ControlEngineError,
            r"target_mechanics\.target\.area_routes\[0\] is invalid: "
            "route compatibility must be boolean",
        ):
            self._frozen_ground_session(
                initial_prone=True,
                route_compatible=1,  # type: ignore[arg-type]
            )

    def test_schedule_grammar_is_canonical_and_reaction_bound(self) -> None:
        program = self.engine.program("absolute_zero_t0_control")

        def construct(schedule):
            return self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={"absolute_zero_target": ("target",)},
                selector_context=_selector_context_for("target"),
                schedule=schedule,
                target_mechanics={"target": {}},
                area_response_convention="fixed_occupancy_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
            )

        def schedule_with(*, attacks=1, initial_reaction=False, target_rows=None):
            return self.engine.schedule(
                "fighter_first_v1",
                ["target"],
                controller_events_by_round={
                    1: [{
                        "kind": "save_opportunity",
                        "target_id": "target",
                        "window_id": "initial_save_window",
                    }],
                },
                target_events_by_round=target_rows,
                target_attack_counts={"target": [attacks, 0, 0]},
                initial_reaction_availability={
                    "target": initial_reaction,
                },
            )

        def resequence(events):
            return tuple(
                replace(event, sequence=index)
                for index, event in enumerate(events)
            )

        valid = schedule_with()
        construct(valid)
        horizon = next(
            interval for interval in valid.reaction_intervals
            if interval.horizon_entry_partial
        )
        self.assertIs(horizon.initially_available, False)

        corruptions: dict[str, Any] = {}

        zero_attack = schedule_with(attacks=0)
        events = list(zero_attack.events)
        active_index = next(
            index for index, event in enumerate(events)
            if event.kind == "target_active_turn_opportunity"
            and event.round == 1
        )
        end_index = next(
            index for index, event in enumerate(events)
            if event.kind == "target_turn_end" and event.round == 1
        )
        events[active_index], events[end_index] = (
            events[end_index],
            events[active_index],
        )
        corruptions["zero_attack_end_before_active"] = replace(
            zero_attack,
            events=resequence(events),
        )

        movement_index = next(
            index for index, event in enumerate(valid.events)
            if event.kind == "target_movement_opportunity"
            and event.round == 1
        )
        events = list(valid.events)
        events[movement_index] = replace(
            events[movement_index],
            turn_id="r1:controller:turn",
            turn_owner="controller",
            actor_id="controller",
        )
        corruptions["foreign_owned_movement"] = replace(
            valid,
            events=tuple(events),
        )

        corruptions["missing_reaction_authority"] = replace(
            valid,
            events=tuple(
                replace(event, reaction_interval_id=None)
                for event in valid.events
            ),
            reaction_intervals=(),
        )

        events = list(valid.events)
        round_end_index = next(
            index for index, event in enumerate(events)
            if event.kind == "round_end" and event.round == 1
        )
        round_end = events.pop(round_end_index)
        target_start_index = next(
            index for index, event in enumerate(events)
            if event.kind == "target_turn_start" and event.round == 1
        )
        events.insert(target_start_index, round_end)
        corruptions["round_end_before_target_turn"] = replace(
            valid,
            events=resequence(events),
        )

        active_index = next(
            index for index, event in enumerate(valid.events)
            if event.kind == "target_active_turn_opportunity"
            and event.round == 1
        )
        events = list(valid.events)
        events[active_index] = replace(
            events[active_index],
            window_id=123,  # type: ignore[arg-type]
        )
        corruptions["non_string_window"] = replace(
            valid,
            events=tuple(events),
        )
        events = list(valid.events)
        events[active_index] = replace(
            events[active_index],
            round=True,  # type: ignore[arg-type]
        )
        corruptions["boolean_round"] = replace(
            valid,
            events=tuple(events),
        )

        events = list(valid.events)
        save_index = next(
            index for index, event in enumerate(events)
            if event.kind == "save_opportunity"
        )
        save = events.pop(save_index)
        attack_index = next(
            index for index, event in enumerate(events)
            if event.kind == "target_attack_opportunity"
            and event.round == 1
        )
        events.insert(attack_index, save)
        corruptions["controller_script_inside_target_turn"] = replace(
            valid,
            events=resequence(events),
        )

        scripted = schedule_with(
            target_rows={
                "target": {
                    1: [{
                        "kind": "damage_context",
                        "phase": "after_attacks",
                    }],
                },
            },
        )
        events = list(scripted.events)
        scripted_index = next(
            index for index, event in enumerate(events)
            if event.kind == "damage_context"
        )
        scripted_event = events.pop(scripted_index)
        attack_index = next(
            index for index, event in enumerate(events)
            if event.kind == "target_attack_opportunity"
            and event.round == 1
        )
        events.insert(attack_index, scripted_event)
        corruptions["script_between_active_and_attack"] = replace(
            scripted,
            events=resequence(events),
        )

        corruptions["missing_horizon_interval"] = replace(
            valid,
            reaction_intervals=tuple(
                interval for interval in valid.reaction_intervals
                if not interval.horizon_entry_partial
            ),
        )

        events = list(valid.events)
        controller_save_index = next(
            index for index, event in enumerate(events)
            if event.kind == "save_opportunity"
        )
        future_interval = next(
            interval for interval in valid.reaction_intervals
            if not interval.horizon_entry_partial and interval.round == 1
        )
        events[controller_save_index] = replace(
            events[controller_save_index],
            reaction_interval_id=future_interval.interval_id,
        )
        corruptions["future_reaction_interval"] = replace(
            valid,
            events=tuple(events),
        )

        events = list(valid.events)
        events[controller_save_index] = replace(
            events[controller_save_index],
            window_id=None,
        )
        corruptions["save_without_window"] = replace(
            valid,
            events=tuple(events),
        )
        events = list(valid.events)
        events[controller_save_index] = replace(
            events[controller_save_index],
            kind="reaction_window",
            reaction_interval_id=horizon.interval_id,
            payload={"availability_interval": True},
        )
        corruptions["script_claims_target_availability_opening"] = replace(
            valid,
            events=tuple(events),
        )

        opening_index = next(
            index for index, event in enumerate(valid.events)
            if event.kind == "reaction_window"
            and event.payload.get("availability_interval") is True
        )
        normal_interval = next(
            interval for interval in valid.reaction_intervals
            if not interval.horizon_entry_partial and interval.round == 1
        )
        events = list(valid.events)
        events[opening_index] = replace(
            events[opening_index],
            window_id=None,
        )
        corruptions["target_opening_without_window"] = replace(
            valid,
            events=tuple(events),
            reaction_intervals=tuple(
                replace(interval, window_id=None)
                if interval is normal_interval else interval
                for interval in valid.reaction_intervals
            ),
        )
        events = list(valid.events)
        events[opening_index] = replace(
            events[opening_index],
            payload={"availability_interval": True, "extra": 1},
        )
        corruptions["target_opening_extra_payload"] = replace(
            valid,
            events=tuple(events),
        )

        unknown_horizon = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{
                    "kind": "save_opportunity",
                    "target_id": "target",
                }],
            },
            target_attack_counts={"target": [1, 0, 0]},
        )
        unknown_horizon_interval = next(
            interval for interval in unknown_horizon.reaction_intervals
            if interval.horizon_entry_partial
        )
        events = list(unknown_horizon.events)
        save_index = next(
            index for index, event in enumerate(events)
            if event.kind == "save_opportunity"
        )
        events[save_index] = replace(
            events[save_index],
            kind="reaction_window",
            reaction_interval_id=unknown_horizon_interval.interval_id,
        )
        corruptions["reaction_with_unknown_initial_availability"] = replace(
            unknown_horizon,
            events=tuple(events),
        )

        round_one = [event for event in valid.events if event.round == 1]
        round_two = [event for event in valid.events if event.round == 2]
        round_three = [event for event in valid.events if event.round == 3]
        corruptions["globally_reordered_rounds"] = replace(
            valid,
            events=resequence([*round_two, *round_one, *round_three]),
        )

        for label, schedule in corruptions.items():
            with self.subTest(label=label):
                with self.assertRaises(ControlEngineError):
                    construct(schedule)

    def test_public_session_rejects_test_only_kernel_before_invocation(self) -> None:
        class CountingTestKernel:
            identity = ProbabilityKernelIdentity.create(
                "tests.session.counting",
                "1.0.0",
                {"fixture": "must_not_run"},
                test_only=True,
            )

            def __init__(self) -> None:
                self.calls = 0

            def outcome_probabilities(self, gate, target, context):
                self.calls += 1
                return {
                    branch.outcome: Fraction(1, len(gate.branches))
                    for branch in gate.branches
                }

        kernel = CountingTestKernel()
        with self.assertRaisesRegex(ControlEngineError, "test-only"):
            self._absolute_zero_session(kernel=kernel)
        self.assertEqual(kernel.calls, 0)

    def test_concentration_program_requires_bound_tracker_at_construction(self) -> None:
        with self.assertRaisesRegex(
            ControlEngineError,
            "requires a bound concentration_save_bonus",
        ):
            self._frozen_ground_session(concentration_save_bonus=None)

    def test_branch_preflight_failure_is_atomic_and_recoverable(self) -> None:
        session, _schedule, events = self._mass_levitation_session(
            bind_future=False,
        )
        session.advance_to(events["activation"].event_id)
        session.start_concentration()
        session.close_event()
        session.advance_to(events["save"].event_id)
        before_state = session.state_snapshot()
        before_records = session.issued_records()
        before_required = set(session._current_required_operations)
        with self.assertRaisesRegex(ControlEngineError, "no remaining bound"):
            session.apply_branch(
                gate_id="mass_levitation_t2_initial_saves",
                outcome="save_failure",
                target_id="target",
            )
        self.assertEqual(session.state_snapshot(), before_state)
        self.assertEqual(session.issued_records(), before_records)
        self.assertEqual(session._current_required_operations, before_required)
        session.apply_branch(
            gate_id="mass_levitation_t2_initial_saves",
            outcome="save_success",
            target_id="target",
        )
        session.close_event()
        session.complete()
        session.result()

    def test_mass_levitation_concentration_end_owns_compiled_end_gate(self) -> None:
        session, schedule, events = self._mass_levitation_session(
            bind_future=True,
        )
        session.advance_to(events["activation"].event_id)
        session.start_concentration()
        session.close_event()
        session.advance_to(events["save"].event_id)
        session.apply_branch(
            gate_id="mass_levitation_t2_initial_saves",
            outcome="save_failure",
            target_id="target",
        )
        session.resolve_displacement(
            target_id="target",
            component_id="mass_levitation_initial_lift",
        )
        session.close_event()
        session.advance_to(events["repeat"].event_id)
        session.apply_branch(
            gate_id="mass_levitation_t2_repeat_saves",
            outcome="save_failure",
            target_id="target",
        )
        session.apply_branch(
            gate_id="mass_levitation_t2_damage_context",
            outcome="damage_context",
            target_id="target",
        )
        session.close_event()
        first_movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.advance_to(events["reposition"].event_id)
        session.apply_branch(
            gate_id="mass_levitation_t2_controller_reposition",
            outcome="no_save",
            target_id="target",
        )
        session.resolve_displacement(
            target_id="target",
            component_id="mass_levitation_reposition",
        )
        session.close_event()
        session.advance_to(events["end"].event_id)
        with self.assertRaisesRegex(ControlEngineError, "owned by end_concentration"):
            session.apply_branch(
                gate_id="mass_levitation_t2_concentration_end",
                outcome="no_save",
                target_id="target",
            )
        end_record = session.end_concentration()
        end = end_record.to_dict()["payload"]
        self.assertTrue(end["changed"])
        self.assertIsNone(session._concentration_tracker.active_effect_id)
        self.assertEqual(
            [
                row["gate_id"]
                for row in end["concentration_end_gate_transitions"]
            ],
            ["mass_levitation_t2_concentration_end"],
        )
        session.close_event()
        second_movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 2
        )
        session.advance_to(second_movement.event_id)
        session.resolve_movement_response(target_id="target")
        with self.assertRaisesRegex(ControlEngineError, "already consumed"):
            session.resolve_movement_response(target_id="target")
        session.close_event()
        session.complete()
        result = session.result().to_dict()
        self.assertTrue(result["concentration_records"])
        self.assertEqual(result["final_normalized_state"]["target"]["conditions"], [])

    def test_cursor_rejects_unknown_future_open_earlier_and_foreign_events(self) -> None:
        session, schedule, _save = self._absolute_zero_session()
        foreign, _foreign_schedule, _foreign_save = self._absolute_zero_session()
        with self.assertRaisesRegex(ControlEngineError, "Unknown"):
            session.advance("fictional:event")
        with self.assertRaisesRegex(ControlEngineError, "Cannot skip future"):
            session.advance(schedule.events[1].event_id)
        with self.assertRaisesRegex(ControlEngineError, "another execution"):
            session.advance(foreign.event_reference(schedule.events[0].event_id))
        session.advance(schedule.events[0].event_id)
        with self.assertRaisesRegex(ControlEngineError, "explicitly closed"):
            session.advance(schedule.events[1].event_id)
        session.close_event()
        session.advance(schedule.events[1].event_id)
        session.close_event()
        with self.assertRaisesRegex(ControlEngineError, "backward"):
            session.advance(schedule.events[0].event_id)

    def test_negative_01_branch_against_earlier_event_after_cursor_advanced(self) -> None:
        session, _schedule, save_event = self._absolute_zero_session()
        session.advance_to(save_event.event_id)
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_success",
            target_id="target",
        )
        session.close_event()
        later_attack = next(
            event for event in session.schedule.events
            if event.kind == "target_attack_opportunity"
        )
        session.advance_to(later_attack.event_id)
        with self.assertRaisesRegex(ControlEngineError, "not a required operation"):
            session.apply_branch(
                gate_id="absolute_zero_t0_save",
                outcome="save_failure",
                target_id="target",
            )

    def test_negative_02_earlier_attack_cannot_be_reopened_after_later_apply(self) -> None:
        program = self.engine.program("absolute_zero_t0_control")
        schedule = self.engine.schedule(
            "target_before_fighter_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "save_opportunity", "target_id": "target"}],
            },
            target_attack_counts={"target": [1, 0, 0]},
        )
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity"
        )
        save = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        self.assertLess(attack.sequence, save.sequence)
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                "target",
                15,
                {"constitution": 2},
            ),),
            selector_membership={"absolute_zero_target": ("target",)},
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={"target": {}},
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
        )
        session.advance_to(attack.event_id)
        session.close_event()
        session.advance_to(save.event_id)
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        with self.assertRaisesRegex(ControlEngineError, "backward"):
            session.advance(attack.event_id)

    def test_negative_03_unknown_event_id_is_rejected(self) -> None:
        session, _schedule, _save = self._absolute_zero_session()
        with self.assertRaisesRegex(ControlEngineError, "Unknown"):
            session.advance("fictional:event")

    def test_negative_04_valid_event_reference_from_other_session_is_rejected(self) -> None:
        session, schedule, _save = self._absolute_zero_session()
        foreign, _foreign_schedule, _foreign_save = self._absolute_zero_session()
        reference = foreign.event_reference(schedule.events[0].event_id)
        with self.assertRaisesRegex(ControlEngineError, "another execution"):
            session.advance(reference)

    def test_negative_05_gate_source_absent_from_pre_event_state_is_rejected(self) -> None:
        program = self.engine.program("mass_levitation_t2_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": "activation"},
                    {"kind": "save_opportunity", "target_id": "target"},
                ],
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        save = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        target_start = next(
            event for event in schedule.events
            if event.kind == "target_turn_start" and event.round == 1
        )
        repeat_gate = program.gate("mass_levitation_t2_repeat_saves")
        repeat_event = ReliabilityEvent.create(
            "repeat_without_source",
            repeat_gate.trigger,
            target_ids=("target",),
            gate_ids=(repeat_gate.gate_id,),
            window_id=target_start.event_id,
        )
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget("target", 15, {"strength": 2}),),
            selector_membership={"mass_levitation_targets": ("target",)},
            selector_context=_selector_context_for("target"),
            schedule=schedule,
            target_mechanics={"target": {}},
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=(repeat_event,),
            operation_inputs_by_event={
                target_start.event_id: {
                    "reliability_event_ids": [repeat_event.event_id],
                },
            },
            concentration_save_bonus=2,
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.close_event()
        session.advance_to(save.event_id)
        session.apply_branch(
            gate_id="mass_levitation_t2_initial_saves",
            outcome="save_success",
            target_id="target",
        )
        session.close_event()
        session.advance_to(target_start.event_id)
        with self.assertRaisesRegex(ControlEngineError, "absent from the pre-event"):
            session.apply_branch(
                gate_id=repeat_gate.gate_id,
                outcome="save_failure",
                target_id="target",
            )

    def test_required_branch_cannot_be_skipped_backdated_or_normalized_after_apply(self) -> None:
        session, schedule, save_event = self._absolute_zero_session(
            save_inputs={"normalization_target_ids": ["target"]},
        )
        session.advance_to(save_event.event_id)
        with self.assertRaisesRegex(ControlEngineError, "unresolved required"):
            session.close_event()
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_failure",
            target_id="target",
        )
        with self.assertRaisesRegex(ControlEngineError, "same-event component"):
            session.normalize(target_id="target")
        # The failed normalization remains unresolved, so this execution cannot
        # be repaired by sorting or by silently closing the event.
        with self.assertRaisesRegex(ControlEngineError, "normalization"):
            session.close_event()

        backdated, backdated_schedule, backdated_save = self._absolute_zero_session()
        self._finish_absolute_zero(backdated, backdated_save)
        with self.assertRaisesRegex(ControlEngineError, "explicitly advanced"):
            backdated.apply_branch(
                gate_id="absolute_zero_t0_save",
                outcome="save_success",
                target_id="target",
            )
        self.assertEqual(backdated.cursor, len(backdated_schedule.events) - 1)

    def test_result_rejects_foreign_mixed_fabricated_and_stale_records(self) -> None:
        first, _schedule, first_save = self._absolute_zero_session()
        second, _schedule_2, second_save = self._absolute_zero_session()
        first_record = self._finish_absolute_zero(first, first_save)
        second_record = self._finish_absolute_zero(second, second_save)
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or fabricated"):
            first._assemble_for_test(records=(second_record,))
        with self.assertRaisesRegex(ControlEngineError, "complete session-issued"):
            first._assemble_for_test(records=(
                first_record,
                second_record,
            ))
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or fabricated"):
            first._assemble_for_test(records=(
                replace(first_record, record_kind="normalization"),
            ))
        with self.assertRaisesRegex(ControlEngineError, "complete session-issued"):
            first._assemble_for_test(records=())
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            first._assemble_for_test(reliability=second._reliability)

        tampered, _tampered_schedule, tampered_save = self._absolute_zero_session()
        tampered_record = self._finish_absolute_zero(tampered, tampered_save)
        object.__setattr__(tampered_record, "record_kind", "fictional")
        with self.assertRaisesRegex(ControlEngineError, "kind is fabricated"):
            tampered.result()

        stale, _stale_schedule, stale_save = self._absolute_zero_session()
        self._finish_absolute_zero(stale, stale_save)
        stale._scenario_json = stale._scenario_json.replace(
            "control_execution_session_v1",
            "control_execution_session_stale",
        )
        with self.assertRaisesRegex(ControlEngineError, "scenario digest is stale"):
            stale.result()

    def test_issued_envelope_sequence_and_target_cannot_be_rewritten(self) -> None:
        sequence_session, _schedule, sequence_save = self._absolute_zero_session()
        sequence_record = self._finish_absolute_zero(
            sequence_session,
            sequence_save,
        )
        object.__setattr__(sequence_record, "operation_sequence", 99)
        self._rewrite_record_payload(
            sequence_record,
            sequence_record.to_dict()["payload"],
        )
        with self.assertRaisesRegex(ControlEngineError, "exact executed"):
            sequence_session.result()

        target_session, _schedule_2, target_save = self._absolute_zero_session()
        target_record = self._finish_absolute_zero(target_session, target_save)
        object.__setattr__(target_record, "target_id", None)
        self._rewrite_record_payload(
            target_record,
            target_record.to_dict()["payload"],
        )
        with self.assertRaisesRegex(ControlEngineError, "target does not match"):
            target_session.result()

    def test_benign_payload_rewrite_fails_engine_owned_issuance_attestation(self) -> None:
        session, _schedule, save_event = self._absolute_zero_session(
            normalize_movement=True,
        )
        normalization = self._finish_absolute_zero_with_normalization(
            session,
            save_event,
        )
        payload = normalization.to_dict()["payload"]
        self.assertTrue(payload["contributions"])
        payload["contributions"][0]["context"]["base_speed_feet"] = 31
        self._rewrite_record_payload(normalization, payload)
        with self.assertRaisesRegex(ControlEngineError, "issuance attestation"):
            session.result()

    def test_negative_06_exact_stream_position_cannot_mix_same_scenario_executions(self) -> None:
        first, _first_schedule, first_save = self._absolute_zero_session(
            normalize_movement=True,
        )
        second, _second_schedule, second_save = self._absolute_zero_session(
            normalize_movement=True,
        )
        self._finish_absolute_zero_with_normalization(first, first_save)
        self._finish_absolute_zero_with_normalization(second, second_save)
        first_records = first.issued_records()
        second_records = second.issued_records()
        self.assertEqual(len(first_records), len(second_records))
        self.assertGreaterEqual(len(first_records), 2)
        mixed = list(first_records)
        mixed[1] = second_records[1]
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or fabricated"):
            first._assemble_for_test(records=tuple(mixed))

    def test_negative_07_reliability_with_different_selector_membership_is_rejected(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            target_ids=("alpha", "beta"),
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        for target_id in ("alpha", "beta"):
            session.apply_branch(
                gate_id="frozen_ground_t0_activation",
                outcome="no_save",
                target_id=target_id,
            )
        session.close_event()
        while session.cursor + 1 < len(schedule.events):
            event = schedule.events[session.cursor + 1]
            session.advance(event.event_id)
            if (
                event.kind == "target_movement_opportunity"
                and event.round == 1
            ):
                session.resolve_movement_response(target_id=str(event.target_id))
            elif (
                event.kind in {
                    "target_active_turn_opportunity",
                    "target_attack_opportunity",
                }
                and event.round == 1
            ):
                session.normalize(target_id=str(event.target_id))
            session.close_event()
        alternate = self.engine.reliability(
            session._program,
            targets=session._targets,
            selector_membership={
                "frozen_ground_area_targets": ("alpha",),
            },
            selector_context=session._selector_context,
            context=session._reliability.scenario.probability_context,
        )
        self.assertNotEqual(
            alternate.scenario_digest,
            session._reliability_digest,
        )
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            session._assemble_for_test(reliability=alternate)

    def test_negative_08_reliability_with_different_choice_bindings_is_rejected(self) -> None:
        explosion = self._explosion_implosion_session("explosion")
        implosion = self._explosion_implosion_session("implosion")
        self.assertNotEqual(explosion.scenario_digest, implosion.scenario_digest)
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            explosion._assemble_for_test(reliability=implosion._reliability)

    def test_negative_09_reliability_with_different_probability_context_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        alternate = self.engine.reliability(
            session._program,
            targets=session._targets,
            selector_membership=session._membership,
            selector_context=session._selector_context,
            context=ProbabilityContext(save_dc=16),
        )
        self.assertNotEqual(
            alternate.scenario_digest,
            session._reliability_digest,
        )
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            session._assemble_for_test(reliability=alternate)

    def test_negative_10_reliability_with_different_kernel_identity_is_rejected(self) -> None:
        class AlternateD20Kernel:
            identity = ProbabilityKernelIdentity.create(
                "tests.session.alternate_d20",
                "1.0.0",
                {
                    "algorithm": "delegate_exact_uniform_d20",
                    "parameters": {
                        "delegate_kernel_id": "openai.kinetic_vanguard.d20",
                    },
                },
            )

            def outcome_probabilities(self, gate, target, context):
                return D20ProbabilityKernel().outcome_probabilities(
                    gate,
                    target,
                    context,
                )

        session = self._completed_absolute_zero_session()
        alternate = self.engine.reliability(
            session._program,
            targets=session._targets,
            selector_membership=session._membership,
            selector_context=session._selector_context,
            kernel=AlternateD20Kernel(),
            context=session._reliability.scenario.probability_context,
        )
        self.assertNotEqual(
            alternate.scenario_digest,
            session._reliability_digest,
        )
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            session._assemble_for_test(reliability=alternate)

    def test_negative_11_reliability_with_different_event_script_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        gate = session._program.gate("absolute_zero_t0_save")
        alternate_event = ReliabilityEvent.create(
            "different_initial_save_event",
            gate.trigger,
            target_ids=("target",),
            gate_ids=(gate.gate_id,),
            window_id="different_initial_save_window",
        )
        alternate = self.engine.reliability(
            session._program,
            targets=session._targets,
            selector_membership=session._membership,
            selector_context=session._selector_context,
            context=session._reliability.scenario.probability_context,
            events=(alternate_event,),
            include_initial=False,
        )
        self.assertNotEqual(
            alternate.scenario_digest,
            session._reliability_digest,
        )
        with self.assertRaisesRegex(ControlEngineError, "foreign, stale, or malformed"):
            session._assemble_for_test(reliability=alternate)

    def test_negative_12_fabricated_reliability_gate_id_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        reliability = session._reliability
        fabricated = replace(
            reliability,
            gate_probabilities=(
                replace(
                    reliability.gate_probabilities[0],
                    gate_id="fictional_gate",
                ),
                *reliability.gate_probabilities[1:],
            ),
        )
        with self.assertRaisesRegex(ControlEngineError, "unknown gate ID"):
            session._assemble_for_test(reliability=fabricated)

    def test_negative_13_fabricated_branch_to_gate_relationship_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        reliability = session._reliability
        fabricated = replace(
            reliability,
            branch_probabilities=(
                replace(
                    reliability.branch_probabilities[0],
                    branch_id="fictional_other_gate_branch",
                ),
                *reliability.branch_probabilities[1:],
            ),
        )
        with self.assertRaisesRegex(ControlEngineError, "does not belong to gate"):
            session._assemble_for_test(reliability=fabricated)

    def test_negative_14_unknown_component_reliability_row_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        reliability = session._reliability
        fabricated = replace(
            reliability,
            component_reliability=(
                replace(
                    reliability.component_reliability[0],
                    component_id="fictional_component",
                ),
                *reliability.component_reliability[1:],
            ),
        )
        with self.assertRaisesRegex(ControlEngineError, "unknown component ID"):
            session._assemble_for_test(reliability=fabricated)

    def test_negative_15_primitive_contribution_fictional_window_is_rejected(self) -> None:
        session, _schedule, save_event = self._absolute_zero_session(
            normalize_movement=True,
        )
        normalization = self._finish_absolute_zero_with_normalization(
            session,
            save_event,
        )
        payload = normalization.to_dict()["payload"]
        self.assertTrue(payload["contributions"])
        payload["contributions"][0]["event_or_window_id"] = "fictional_window"
        self._rewrite_record_payload(normalization, payload)
        with self.assertRaisesRegex(ControlEngineError, "fictional window"):
            session.result()

    def test_negative_16_primitive_contribution_inactive_source_is_rejected(self) -> None:
        session, _schedule, save_event = self._absolute_zero_session(
            normalize_movement=True,
        )
        normalization = self._finish_absolute_zero_with_normalization(
            session,
            save_event,
        )
        payload = normalization.to_dict()["payload"]
        self.assertTrue(payload["contributions"])
        payload["contributions"][0]["source_component_ids"] = [
            "absolute_zero_t0_control:fictional_component",
        ]
        self._rewrite_record_payload(normalization, payload)
        with self.assertRaisesRegex(ControlEngineError, "not active in the pre-state"):
            session.result()

    def test_negative_17_malformed_or_out_of_range_probability_is_rejected(self) -> None:
        for probability, message in (
            (0.5, "exact fractions.Fraction"),
            (Fraction(3, 2), "between zero and one"),
        ):
            with self.subTest(probability=probability):
                session = self._completed_absolute_zero_session()
                reliability = session._reliability
                fabricated = replace(
                    reliability,
                    gate_probabilities=(
                        replace(
                            reliability.gate_probabilities[0],
                            probability=probability,
                        ),
                        *reliability.gate_probabilities[1:],
                    ),
                )
                with self.assertRaisesRegex(ControlEngineError, message):
                    session._assemble_for_test(reliability=fabricated)

    def test_negative_18_duplicate_semantic_probability_row_is_rejected(self) -> None:
        session = self._completed_absolute_zero_session()
        reliability = session._reliability
        fabricated = replace(
            reliability,
            gate_probabilities=(
                *reliability.gate_probabilities,
                reliability.gate_probabilities[0],
            ),
        )
        with self.assertRaisesRegex(ControlEngineError, "Duplicate semantic gate"):
            session._assemble_for_test(reliability=fabricated)

    def test_prone_stands_before_attack_and_outgoing_impairment_is_absent(self) -> None:
        session, schedule, save_event = self._absolute_zero_session(
            normalize_attack=True,
            target_mechanics={
                "initial_conditions": ["prone"],
                "base_speeds_ft": {"walk": 30},
                "movement_mode": "walk",
            },
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity" and event.round == 1
        )
        session.advance_to(save_event.event_id)
        session.apply_branch(
            gate_id="absolute_zero_t0_save",
            outcome="save_success",
            target_id="target",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        [stand_record] = session.resolve_movement_response(target_id="target")
        stand = stand_record.to_dict()["payload"]
        self.assertTrue(stand["stood"])
        self.assertEqual(stand["standing_cost_ft"], 15)
        self.assertEqual(stand["remaining_movement_ft"], 15)
        self.assertLess(movement.sequence, attack.sequence)
        self.assertFalse(any(
            row["magnitude"].get("condition") == "prone"
            for row in session.state_snapshot("target")
        ))
        session.close_event()
        session.advance_to(attack.event_id)
        attack_record = session.normalize(target_id="target")
        primitives = {
            row["primitive_id"]
            for row in attack_record.to_dict()["payload"]["contributions"]
        }
        self.assertNotIn("offensive_impairment_all_attacks", primitives)
        session.close_event()
        session.complete()
        session.result()

    def test_prone_standing_cost_precedes_frozen_ground_route_progress(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            initial_prone=True,
            route_distance=10,
            route_multiplier=2,
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.apply_branch(
            gate_id="frozen_ground_t0_activation",
            outcome="no_save",
            target_id="target",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        response = record.to_dict()["payload"]
        route = response["selected_route"]
        self.assertTrue(route["prone_response"]["stood"])
        self.assertEqual(route["prone_response"]["standing_cost_ft"], 15)
        self.assertEqual(route["prone_response"]["remaining_movement_ft"], 15)
        self.assertEqual(route["movement_cost_multiplier"], 2)
        self.assertEqual(route["progress_ft"], 7.5)
        self.assertEqual(route["remaining_distance_ft"], 2.5)
        self.assertFalse(response["exited"])

    def test_prone_stands_when_area_route_is_incompatible_and_independent_survives(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            initial_prone=True,
            initial_conditions=("blinded",),
            base_speeds={"walk": 30, "fly": 0},
            route_mode="fly",
            route_compatible=False,
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.apply_branch(
            gate_id="frozen_ground_t0_activation",
            outcome="no_save",
            target_id="target",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        [area_record] = session.resolve_movement_response(target_id="target")
        area = area_record.to_dict()["payload"]
        stand = area["prone_response"]
        self.assertTrue(stand["stood"])
        self.assertEqual(stand["standing_cost_ft"], 15)
        self.assertEqual(area["events"][0]["movement_mode"], "walk")
        self.assertFalse(area["exited"])
        self.assertEqual(area["reason"], "movement_unavailable")
        self.assertIn("initial_blinded", area["retained_component_ids"])
        active_ids = {
            row["component_id"] for row in session.state_snapshot("target")
        }
        self.assertNotIn("initial_prone", active_ids)
        self.assertIn("initial_blinded", active_ids)
        self.assertIn("frozen_ground_difficult_terrain", active_ids)

    def test_speed_zero_keeps_prone_and_frozen_area_through_attacks(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            initial_prone=True,
            include_start_turn_save=True,
        )
        target_start = next(
            event for event in schedule.events
            if event.kind == "target_turn_start" and event.round == 1
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        active = next(
            event for event in schedule.events
            if event.kind == "target_active_turn_opportunity" and event.round == 1
        )
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity" and event.round == 1
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.apply_branch(
            gate_id="frozen_ground_t0_activation",
            outcome="no_save",
            target_id="target",
        )
        session.close_event()
        session.advance_to(target_start.event_id)
        session.apply_branch(
            gate_id="frozen_ground_t0_start_turn_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        [movement_record] = session.resolve_movement_response(target_id="target")
        movement_payload = movement_record.to_dict()["payload"]
        self.assertFalse(movement_payload["exited"])
        self.assertTrue(movement_payload["prone_after"])
        self.assertEqual(movement_payload["reason"], "movement_unavailable")
        self.assertEqual(
            movement_payload["movement_authority"]["effective_speeds_ft"],
            {"walk": 0},
        )
        session.close_event()
        session.advance_to(active.event_id)
        active_record = session.normalize(target_id="target")
        session.close_event()
        session.advance_to(attack.event_id)
        attack_record = session.normalize(target_id="target")
        session.close_event()
        active_ids = {
            row["component_id"] for row in session.state_snapshot("target")
        }
        self.assertIn("initial_prone", active_ids)
        self.assertIn("frozen_ground_difficult_terrain", active_ids)
        self.assertIn("frozen_ground_speed_zero", active_ids)
        active_primitives = {
            row["primitive_id"]
            for row in active_record.to_dict()["payload"]["contributions"]
        }
        attack_primitives = {
            row["primitive_id"]
            for row in attack_record.to_dict()["payload"]["contributions"]
        }
        self.assertIn("offensive_impairment_all_attacks", active_primitives)
        self.assertNotIn("offensive_impairment_all_attacks", attack_primitives)

    def test_ball_lightning_exits_pre_attack_at_real_initiative_round(self) -> None:
        observed_rounds: dict[str, int] = {}
        for initiative, expected_round in (
            ("fighter_first_v1", 1),
            ("target_before_fighter_v1", 2),
        ):
            with self.subTest(initiative=initiative):
                program = self.engine.program("ball_lightning_t2_control")
                schedule = self.engine.schedule(
                    initiative,
                    ["target"],
                    controller_events_by_round={1: [{"kind": "activation"}]},
                    target_attack_counts={"target": [1, 1, 0]},
                )
                activation = next(
                    event for event in schedule.events
                    if event.kind == "activation"
                )
                target_start = next(
                    event for event in schedule.events
                    if event.kind == "target_turn_start"
                    and event.round == expected_round
                )
                movement = next(
                    event for event in schedule.events
                    if event.kind == "target_movement_opportunity"
                    and event.round == expected_round
                )
                active = next(
                    event for event in schedule.events
                    if event.kind == "target_active_turn_opportunity"
                    and event.round == expected_round
                )
                attack = next(
                    event for event in schedule.events
                    if event.kind == "target_attack_opportunity"
                    and event.round == expected_round
                )
                gate = program.gate("ball_lightning_start_turn_save")
                reliability_event = ReliabilityEvent.create(
                    f"ball_start_{expected_round}",
                    gate.trigger,
                    target_ids=("target",),
                    gate_ids=(gate.gate_id,),
                    window_id=target_start.event_id,
                )
                session = self.engine.execution_session(
                    program,
                    targets=(ReliabilityTarget(
                        "target",
                        15,
                        {"charisma": 2},
                    ),),
                    selector_membership={
                        "ball_lightning_area_targets": ("target",),
                    },
                    selector_context=SelectorContext(),
                    schedule=schedule,
                    target_mechanics={
                        "target": {
                            "base_speeds_ft": {"walk": 30},
                            "movement_mode": "walk",
                            "area_membership": True,
                            "area_routes": [{
                                "route_id": "ball_exit",
                                "mode": "walk",
                                "distance_to_exit_ft": 5,
                                "compatible": True,
                                "movement_cost_multiplier": 1,
                                "environment": "grounded",
                            }],
                        },
                    },
                    area_response_convention="shortest_route_v1",
                    displacement_function_id="sqrt_5ft_v1",
                    probability_context=ProbabilityContext(save_dc=15),
                    reliability_events=(reliability_event,),
                    operation_inputs_by_event={
                        target_start.event_id: {
                            "reliability_event_ids": [reliability_event.event_id],
                        },
                        active.event_id: {
                            "normalization_target_ids": ["target"],
                        },
                        attack.event_id: {
                            "normalization_target_ids": ["target"],
                        },
                    },
                    concentration_save_bonus=2,
                )
                session.advance_to(activation.event_id)
                session.start_concentration()
                session.close_event()
                session.advance_to(target_start.event_id)
                session.apply_branch(
                    gate_id=gate.gate_id,
                    outcome="save_failure",
                    target_id="target",
                )
                session.close_event()
                session.advance_to(movement.event_id)
                [area_record] = session.resolve_movement_response(
                    target_id="target",
                )
                area = area_record.to_dict()["payload"]
                self.assertTrue(area["exited"])
                self.assertEqual(
                    set(area["ended_component_ids"]),
                    {
                        "ball_lightning_attack_disadvantage",
                        "ball_lightning_reaction_denial",
                    },
                )
                session.close_event()
                session.advance_to(active.event_id)
                active_record = session.normalize(target_id="target")
                session.close_event()
                session.advance_to(attack.event_id)
                attack_record = session.normalize(target_id="target")
                session.close_event()
                self.assertEqual(
                    active_record.to_dict()["payload"]["contributions"],
                    [],
                )
                self.assertEqual(
                    attack_record.to_dict()["payload"]["contributions"],
                    [],
                )
                self.assertLess(movement.sequence, active.sequence)
                self.assertLess(active.sequence, attack.sequence)
                session.complete()
                session.result()
                observed_rounds[initiative] = target_start.round
        self.assertEqual(observed_rounds, {
            "fighter_first_v1": 1,
            "target_before_fighter_v1": 2,
        })

    def test_shared_frozen_activation_is_target_permutation_invariant(self) -> None:
        final_by_order: dict[tuple[str, ...], dict[str, list[str]]] = {}
        for target_ids in (("alpha", "beta"), ("beta", "alpha")):
            with self.subTest(target_ids=target_ids):
                session, schedule, activation = self._frozen_ground_session(
                    target_ids=target_ids,
                )
                session.advance_to(activation.event_id)
                session.start_concentration()
                for target_id in sorted(target_ids):
                    session.apply_branch(
                        gate_id="frozen_ground_t0_activation",
                        outcome="no_save",
                        target_id=target_id,
                    )
                self.assertEqual(
                    {
                        target_id: {
                            row["component_id"]
                            for row in session.state_snapshot(target_id)
                        }
                        for target_id in target_ids
                    },
                    {
                        target_id: {"frozen_ground_difficult_terrain"}
                        for target_id in target_ids
                    },
                )
                session.close_event()
                while session.cursor + 1 < len(schedule.events):
                    event = schedule.events[session.cursor + 1]
                    session.advance(event.event_id)
                    if (
                        event.kind == "target_movement_opportunity"
                        and event.round == 1
                    ):
                        session.resolve_movement_response(
                            target_id=str(event.target_id),
                        )
                    elif (
                        event.kind
                        in {
                            "target_active_turn_opportunity",
                            "target_attack_opportunity",
                        }
                        and event.round == 1
                    ):
                        session.normalize(target_id=str(event.target_id))
                    session.close_event()
                result = session.result().to_dict()
                final_by_order[target_ids] = {
                    target_id: sorted(
                        row["component_id"]
                        for row in result["final_normalized_state"][target_id][
                            "active_components"
                        ]
                    )
                    for target_id in sorted(target_ids)
                }
        self.assertEqual(
            final_by_order[("alpha", "beta")],
            final_by_order[("beta", "alpha")],
        )

    def test_displacement_prone_and_epoch_share_one_movement_budget(self) -> None:
        program = self.engine.program("telekinetic_slam_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "save_opportunity", "target_id": "target"}],
            },
            target_attack_counts={"target": [1, 0, 0]},
        )
        save = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget("target", 15, {"strength": 2}),),
            selector_membership={"telekinetic_slam_target": ("target",)},
            selector_context=_selector_context_for("target"),
            schedule=schedule,
            target_mechanics={
                "target": {
                    "initial_conditions": ["prone"],
                    "base_speeds_ft": {"walk": 30},
                    "movement_mode": "walk",
                },
            },
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            operation_inputs_by_event={
                save.event_id: {
                    "displacement_vectors": {
                        "telekinetic_slam_failed_save_movement": [10, 0, 0],
                    },
                },
            },
        )
        session.advance_to(save.event_id)
        session.apply_branch(
            gate_id="telekinetic_slam_t0_save",
            outcome="save_failure",
            target_id="target",
        )
        session.resolve_displacement(
            target_id="target",
            component_id="telekinetic_slam_failed_save_movement",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        prone_record, epoch_record = session.resolve_movement_response(
            target_id="target",
        )
        self.assertTrue(prone_record.to_dict()["payload"]["stood"])
        epoch = epoch_record.to_dict()["payload"]["record"]
        self.assertTrue(epoch["reset"])
        self.assertEqual(epoch["reason"], "legal_self_movement_response")
        with self.assertRaisesRegex(ControlEngineError, "already consumed"):
            session.resolve_movement_response(target_id="target")

    def test_frozen_ground_exits_before_active_turn_and_attack_normalization(self) -> None:
        program = self.engine.program("frozen_ground_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "activation", "target_id": "target"}],
            },
            target_attack_counts={"target": [1, 0, 0]},
        )
        activation = next(event for event in schedule.events if event.kind == "activation")
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity" and event.round == 1
        )
        active_turn = next(
            event for event in schedule.events
            if event.kind == "target_active_turn_opportunity" and event.round == 1
        )
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity" and event.round == 1
        )
        operation_inputs = {
            activation.event_id: {"required_operations": ["concentration_start"]},
            active_turn.event_id: {"normalization_target_ids": ["target"]},
            attack.event_id: {"normalization_target_ids": ["target"]},
        }
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                "target",
                15,
                {"dexterity": 2},
            ),),
            selector_membership={"frozen_ground_area_targets": ("target",)},
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={
                "target": {
                    "base_speeds_ft": {"walk": 30},
                    "movement_mode": "walk",
                    "area_membership": True,
                    "area_routes": [{
                        "route_id": "walk_exit",
                        "mode": "walk",
                        "distance_to_exit_ft": 5,
                        "compatible": True,
                        "movement_cost_multiplier": 1,
                        "environment": "grounded",
                    }],
                },
            },
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.apply_branch(
            gate_id="frozen_ground_t0_activation",
            outcome="no_save",
            target_id="target",
        )
        session.close_event()
        session.advance_to(movement.event_id)
        [area_record] = session.resolve_movement_response(target_id="target")
        area_payload = area_record.to_dict()["payload"]
        self.assertTrue(area_payload["exited"])
        self.assertEqual(
            area_payload["ended_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        session.close_event()
        session.advance_to(active_turn.event_id)
        active_record = session.normalize(target_id="target")
        session.close_event()
        session.advance_to(attack.event_id)
        attack_record = session.normalize(target_id="target")
        session.close_event()
        self.assertEqual(active_record.to_dict()["payload"]["contributions"], [])
        self.assertEqual(attack_record.to_dict()["payload"]["contributions"], [])
        self.assertLess(movement.sequence, active_turn.sequence)
        self.assertLess(active_turn.sequence, attack.sequence)
        session.complete()
        result = session.result().to_dict()
        self.assertEqual(
            result["final_normalized_state"]["target"]["active_components"],
            [],
        )


    def test_area_route_01_frozen_progress_is_carried_then_exits(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            route_distance=20,
            bind_round_one_normalization=False,
        )
        self._activate_frozen_ground(session, activation)
        first = self._movement_event(schedule, round_number=1)
        second = self._movement_event(schedule, round_number=2)

        session.advance_to(first.event_id)
        [first_record] = session.resolve_movement_response(target_id="target")
        first_payload = first_record.to_dict()["payload"]
        self.assertEqual(first_payload["selected_route"]["progress_ft"], 15)
        self.assertEqual(
            first_payload["selected_route"]["remaining_distance_ft"],
            5,
        )
        carried = self._area_route_row(session)
        self.assertEqual(carried["selected_route_id"], "target_walk_exit")
        self.assertEqual(carried["remaining_distance_ft"], 5)
        session.close_event()

        session.advance_to(second.event_id)
        [second_record] = session.resolve_movement_response(target_id="target")
        second_payload = second_record.to_dict()["payload"]
        self.assertTrue(second_payload["exited"])
        self.assertEqual(second_payload["selected_route"]["distance_before_ft"], 5)
        final_route = self._area_route_row(session)
        self.assertFalse(final_route["membership"])
        self.assertEqual(final_route["remaining_distance_ft"], 0)
        self.assertEqual(final_route["closed_reason"], "route_exhausted")

    def test_area_route_02_second_response_requires_no_restatement(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            route_distance=20,
            bind_round_one_normalization=False,
        )
        self._activate_frozen_ground(session, activation)
        first = self._movement_event(schedule, round_number=1)
        second = self._movement_event(schedule, round_number=2)
        scenario = session.scenario_record
        self.assertEqual(
            scenario["initial_area_route_states"][0]["routes"][0][
                "distance_to_exit_exact"
            ],
            {"numerator": 20, "denominator": 1},
        )
        self.assertNotIn(second.event_id, scenario["operation_inputs_by_event"])

        session.advance_to(first.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.advance_to(second.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        self.assertTrue(record.to_dict()["payload"]["exited"])

    def test_area_route_03_speed_zero_preserves_full_initial_route(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            route_distance=20,
            include_start_turn_save=True,
            bind_round_one_normalization=False,
        )
        self._activate_frozen_ground(session, activation)
        target_start = next(
            event for event in schedule.events
            if event.kind == "target_turn_start" and event.round == 1
        )
        session.advance_to(target_start.event_id)
        session.apply_branch(
            gate_id="frozen_ground_t0_start_turn_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        movement = self._movement_event(schedule, round_number=1)
        session.advance_to(movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        self.assertEqual(record.to_dict()["payload"]["reason"], "movement_unavailable")
        route = self._area_route_row(session)
        self.assertTrue(route["membership"])
        self.assertIsNone(route["selected_route_id"])
        self.assertEqual(
            route["routes"][0]["distance_to_exit_exact"],
            {"numerator": 20, "denominator": 1},
        )

    def test_area_route_04_speed_recovery_uses_preserved_distance(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            route_distance=20,
            include_start_turn_save=True,
            bind_round_one_normalization=False,
        )
        self._activate_frozen_ground(session, activation)
        target_start = next(
            event for event in schedule.events
            if event.kind == "target_turn_start" and event.round == 1
        )
        session.advance_to(target_start.event_id)
        session.apply_branch(
            gate_id="frozen_ground_t0_start_turn_save",
            outcome="save_failure",
            target_id="target",
        )
        session.close_event()
        first = self._movement_event(schedule, round_number=1)
        session.advance_to(first.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()

        second = self._movement_event(schedule, round_number=2)
        session.advance_to(second.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        selected = record.to_dict()["payload"]["selected_route"]
        self.assertEqual(selected["distance_before_ft"], 20)
        self.assertEqual(selected["progress_ft"], 15)
        self.assertEqual(selected["remaining_distance_ft"], 5)

    def test_area_route_05_raw_reset_to_original_distance_is_rejected(self) -> None:
        reset = self._route_geometry(
            "target_walk_exit",
            distance=20,
        ).route_input()
        with self.assertRaisesRegex(ControlEngineError, "raw route overrides"):
            self._frozen_ground_session(
                route_distance=20,
                raw_second_movement_routes=(reset,),
                bind_round_one_normalization=False,
            )

    def test_area_route_06_raw_remaining_distance_shrink_is_rejected(self) -> None:
        shrink = self._route_geometry(
            "target_walk_exit",
            distance=1,
        ).route_input()
        with self.assertRaisesRegex(ControlEngineError, "raw route overrides"):
            self._frozen_ground_session(
                route_distance=20,
                raw_second_movement_routes=(shrink,),
                bind_round_one_normalization=False,
            )

    def test_area_route_07_raw_route_switch_is_rejected(self) -> None:
        switched = self._route_geometry(
            "different_exit",
            distance=5,
        ).route_input()
        with self.assertRaisesRegex(ControlEngineError, "raw route overrides"):
            self._frozen_ground_session(
                route_distance=20,
                raw_second_movement_routes=(switched,),
                bind_round_one_normalization=False,
            )

    def test_area_route_08_compiled_ball_geometry_update_records_old_and_new(self) -> None:
        session, schedule, events = self._ball_lightning_route_session(
            initial_distance=60,
            update_membership=True,
            update_distance=10,
            update_route_id="repositioned_exit",
        )
        self._activate_ball_lightning(session, events)
        first = self._movement_event(schedule, round_number=1)
        session.advance_to(first.event_id)
        session.resolve_movement_response(target_id="target")
        self.assertEqual(self._area_route_row(session)["remaining_distance_ft"], 30)
        session.close_event()

        update_event = events["update"]
        self.assertIsNotNone(update_event)
        session.advance_to(update_event.event_id)
        record = session.apply_area_geometry_update(target_id="target")
        payload = record.to_dict()["payload"]
        self.assertEqual(record.record_kind, "area_geometry_update")
        self.assertEqual(payload["effect_id"], "ball_lightning_t2_control")
        self.assertEqual(payload["area_id"], "ball_lightning_sphere")
        self.assertEqual(payload["canonical_reason"], "controller_reposition")
        self.assertEqual(
            payload["compiled_movement_authority"]["controller_action"],
            "bonus_action",
        )
        self.assertFalse(payload["moved_area_counts_as_entry"])
        self.assertEqual(
            payload["old_route_state"]["remaining_distance_ft"],
            30,
        )
        self.assertEqual(
            payload["new_route_state"]["routes"][0]["route_id"],
            "repositioned_exit",
        )
        self.assertNotEqual(
            payload["pre_route_state_sha256"],
            payload["post_route_state_sha256"],
        )
        session.close_event()
        second = self._movement_event(schedule, round_number=2)
        session.advance_to(second.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.complete()
        result = session.result().to_dict()
        self.assertEqual(
            [
                row["transition_kind"]
                for row in result["area_route_transitions"]
            ],
            [
                "movement_progress",
                "explicit_geometry_update",
                "route_exit",
            ],
        )
        [final_route] = result["final_area_route_states"]
        self.assertFalse(final_route["membership"])
        self.assertEqual(
            final_route["routes"][0]["route_id"],
            "repositioned_exit",
        )

    def test_area_route_09_foreign_session_geometry_record_is_rejected(self) -> None:
        sessions: list[tuple[Any, Any]] = []
        for _index in range(2):
            session, schedule, events = self._ball_lightning_route_session(
                update_membership=True,
            )
            self._activate_ball_lightning(session, events)
            first = self._movement_event(schedule, round_number=1)
            session.advance_to(first.event_id)
            session.resolve_movement_response(target_id="target")
            session.close_event()
            update_event = events["update"]
            session.advance_to(update_event.event_id)
            update_record = session.apply_area_geometry_update(target_id="target")
            session.close_event()
            second = self._movement_event(schedule, round_number=2)
            session.advance_to(second.event_id)
            session.resolve_movement_response(target_id="target")
            session.close_event()
            session.complete()
            sessions.append((session, update_record))
        first_session, first_update = sessions[0]
        _second_session, foreign_update = sessions[1]
        mixed = tuple(
            foreign_update if record is first_update else record
            for record in first_session.issued_records()
        )
        with self.assertRaisesRegex(
            ControlEngineError,
            "foreign, stale, or fabricated",
        ):
            first_session._assemble_for_test(records=mixed)

    def test_area_route_10_rewritten_geometry_transition_cannot_enter_result(self) -> None:
        session, schedule, events = self._ball_lightning_route_session(
            update_membership=True,
        )
        self._activate_ball_lightning(session, events)
        first = self._movement_event(schedule, round_number=1)
        session.advance_to(first.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        update_event = events["update"]
        session.advance_to(update_event.event_id)
        update_record = session.apply_area_geometry_update(target_id="target")
        session.close_event()
        second = self._movement_event(schedule, round_number=2)
        session.advance_to(second.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.complete()
        payload = update_record.to_dict()["payload"]
        payload["new_route_state"]["membership"] = False
        self._rewrite_record_payload(update_record, payload)
        with self.assertRaisesRegex(
            ControlEngineError,
            "issuance attestation|route|stale",
        ):
            session.result()

    def test_area_route_11_ball_components_end_only_at_carried_zero(self) -> None:
        session, schedule, events = self._ball_lightning_route_session(
            initial_distance=45,
        )
        self._activate_ball_lightning(session, events)
        first = self._movement_event(schedule, round_number=1)
        session.advance_to(first.event_id)
        [first_record] = session.resolve_movement_response(target_id="target")
        self.assertEqual(
            first_record.to_dict()["payload"]["selected_route"][
                "remaining_distance_ft"
            ],
            15,
        )
        self.assertEqual(
            {
                row["component_id"] for row in session.state_snapshot("target")
            },
            {
                "ball_lightning_attack_disadvantage",
                "ball_lightning_reaction_denial",
            },
        )
        session.close_event()
        second = self._movement_event(schedule, round_number=2)
        session.advance_to(second.event_id)
        [second_record] = session.resolve_movement_response(target_id="target")
        payload = second_record.to_dict()["payload"]
        self.assertTrue(payload["exited"])
        self.assertEqual(
            set(payload["ended_component_ids"]),
            {
                "ball_lightning_attack_disadvantage",
                "ball_lightning_reaction_denial",
            },
        )
        self.assertEqual(session.state_snapshot("target"), ())

        exit_session, exit_schedule, exit_events = (
            self._ball_lightning_route_session(
                initial_distance=60,
                update_membership=False,
            )
        )
        self._activate_ball_lightning(exit_session, exit_events)
        exit_movement = self._movement_event(
            exit_schedule,
            round_number=1,
        )
        exit_session.advance_to(exit_movement.event_id)
        [progress_record] = exit_session.resolve_movement_response(
            target_id="target",
        )
        self.assertEqual(
            progress_record.to_dict()["payload"]["selected_route"][
                "remaining_distance_ft"
            ],
            30,
        )
        self.assertEqual(len(exit_session.state_snapshot("target")), 2)
        exit_session.close_event()
        update_event = exit_events["update"]
        exit_session.advance_to(update_event.event_id)
        exit_record = exit_session.apply_area_geometry_update(
            target_id="target",
        )
        exit_payload = exit_record.to_dict()["payload"]
        self.assertEqual(
            set(exit_payload["ended_component_ids"]),
            {
                "ball_lightning_attack_disadvantage",
                "ball_lightning_reaction_denial",
            },
        )
        self.assertFalse(exit_payload["membership_after"])
        self.assertEqual(
            exit_payload["new_route_state"]["closed_reason"],
            "explicit_area_exit",
        )
        self.assertEqual(exit_session.state_snapshot("target"), ())

    def test_area_route_12_frozen_failed_save_component_survives_typed_exit(self) -> None:
        program = self.engine.program_for("frozen_ground", 0)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            target_events_by_round={
                "target": {1: [{"kind": "exit", "phase": "after_movement"}]},
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        exit_event = next(event for event in schedule.events if event.kind == "exit")
        state = self.engine._new_state()
        for component_id in (
            "frozen_ground_difficult_terrain",
            "frozen_ground_speed_zero",
        ):
            _activate_component(state, program, program.component(component_id))
        response = self.engine._resolve_area_response(
            state=state,
            schedule=schedule,
            effect=program,
            target_ids=("target",),
            selector_membership=_single_selector_membership(program, "target"),
            selector_context=_selector_context_for("target"),
            target_id="target",
            event_id=exit_event.event_id,
            area_response_convention="shortest_route_v1",
            membership=True,
            effect_active=True,
            post_movement_membership=False,
        )
        self.assertEqual(
            response["ended_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        self.assertEqual(
            response["retained_component_ids"],
            ["frozen_ground_speed_zero"],
        )
        self.assertEqual(
            [row.component_id for row in state.active_components("target")],
            ["frozen_ground_speed_zero"],
        )

    def test_area_route_13_prone_cost_precedes_carried_progress(self) -> None:
        session, schedule, activation = self._frozen_ground_session(
            initial_prone=True,
            route_distance=20,
            bind_round_one_normalization=False,
        )
        self._activate_frozen_ground(session, activation)
        movement = self._movement_event(schedule, round_number=1)
        session.advance_to(movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        selected = record.to_dict()["payload"]["selected_route"]
        self.assertEqual(selected["prone_response"]["standing_cost_ft"], 15)
        self.assertEqual(
            selected["prone_response"]["remaining_movement_ft"],
            15,
        )
        self.assertEqual(selected["progress_ft"], 7.5)
        self.assertEqual(selected["remaining_distance_ft"], 12.5)
        route = self._area_route_row(session)
        self.assertEqual(
            route["remaining_distance_exact"],
            {"numerator": 25, "denominator": 2},
        )

    def test_area_route_14_fixed_occupancy_creates_no_route_state(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={"target": [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget("target", 15, {"charisma": 2}),),
            selector_membership={
                "ball_lightning_area_targets": ("target",),
            },
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={"target": {}},
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            concentration_save_bonus=2,
        )
        self.assertEqual(session.area_route_snapshot(), ())
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.close_event()
        session.complete()
        result = session.result().to_dict()
        self.assertEqual(result["area_route_transitions"], [])
        self.assertEqual(result["final_area_route_states"], [])

    def test_area_route_15_initiative_conventions_preserve_response_progress(self) -> None:
        observed: dict[str, list[tuple[bool, int | float]]] = {}
        for initiative, movement_rounds in (
            ("fighter_first_v1", (1, 2)),
            ("target_before_fighter_v1", (2, 3)),
        ):
            with self.subTest(initiative=initiative):
                session, schedule, activation = self._frozen_ground_session(
                    initiative=initiative,
                    route_distance=20,
                    bind_round_one_normalization=False,
                )
                self._activate_frozen_ground(session, activation)
                progress: list[tuple[bool, int | float]] = []
                for round_number in movement_rounds:
                    movement = self._movement_event(
                        schedule,
                        round_number=round_number,
                    )
                    session.advance_to(movement.event_id)
                    session.resolve_movement_response(target_id="target")
                    row = self._area_route_row(session)
                    progress.append((
                        bool(row["membership"]),
                        row["remaining_distance_ft"],
                    ))
                    session.close_event()
                observed[initiative] = progress
        self.assertEqual(
            observed["fighter_first_v1"],
            observed["target_before_fighter_v1"],
        )
        self.assertEqual(observed["fighter_first_v1"], [(True, 5), (False, 0)])

    def test_area_route_16_target_permutation_preserves_independent_routes(self) -> None:
        observed: dict[tuple[str, ...], dict[str, tuple[Any, ...]]] = {}
        for target_ids in (("alpha", "beta"), ("beta", "alpha")):
            with self.subTest(target_ids=target_ids):
                session, schedule, activation = self._frozen_ground_session(
                    target_ids=target_ids,
                    route_distance=40,
                    bind_round_one_normalization=False,
                )
                self._activate_frozen_ground(session, activation, target_ids)
                pending = {
                    self._movement_event(
                        schedule,
                        round_number=1,
                        target_id=target_id,
                    ).event_id
                    for target_id in target_ids
                }
                while pending:
                    event = schedule.events[session.cursor + 1]
                    session.advance(event.event_id)
                    if event.event_id in pending:
                        session.resolve_movement_response(
                            target_id=str(event.target_id),
                        )
                        pending.remove(event.event_id)
                    session.close_event()
                observed[target_ids] = {
                    target_id: (
                        row["membership"],
                        row["selected_route_id"],
                        row["remaining_distance_ft"],
                        row["movement_mode"],
                        row["environment"],
                        row["movement_cost_basis"],
                    )
                    for target_id in sorted(target_ids)
                    for row in (self._area_route_row(session, target_id),)
                }
        self.assertEqual(
            observed[("alpha", "beta")],
            observed[("beta", "alpha")],
        )

    def test_area_membership_01_success_without_components_still_requires_exit_response(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session()
        self._start_ball_concentration(session, events["activation"])
        [first_start] = events["starts_by_target"]["target"][:1]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        self.assertEqual(session.state_snapshot("target"), ())
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        with self.assertRaisesRegex(ControlEngineError, "target movement response"):
            session.close_event()
        [record] = session.resolve_movement_response(target_id="target")
        payload = record.to_dict()["payload"]
        self.assertTrue(payload["exited"])
        self.assertEqual(payload["ended_component_ids"], [])
        self.assertFalse(self._area_route_row(session)["membership"])

    def test_area_membership_02_successful_exit_precedes_active_and_attack_windows(
        self,
    ) -> None:
        session, schedule, events = self._ball_membership_session()
        self._start_ball_concentration(session, events["activation"])
        [first_start] = events["starts_by_target"]["target"][:1]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        [movement] = events["movements_by_target"]["target"][:1]
        active = next(
            event for event in schedule.events
            if event.kind == "target_active_turn_opportunity"
            and event.target_id == "target"
            and event.round == movement.round
        )
        attack = next(
            event for event in schedule.events
            if event.kind == "target_attack_opportunity"
            and event.target_id == "target"
            and event.round == movement.round
        )
        session.advance_to(movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        self.assertTrue(record.to_dict()["payload"]["exited"])
        self.assertLess(movement.sequence, active.sequence)
        self.assertLess(active.sequence, attack.sequence)
        session.close_event()
        session.advance_to(active.event_id)
        self.assertFalse(self._area_route_row(session)["membership"])
        active_record = session.normalize(target_id="target")
        self.assertEqual(
            active_record.to_dict()["payload"]["contributions"],
            [],
        )
        self.assertEqual(session.state_snapshot("target"), ())
        session.close_event()
        session.advance_to(attack.event_id)
        attack_record = session.normalize(target_id="target")
        self.assertEqual(
            attack_record.to_dict()["payload"]["contributions"],
            [],
        )
        self.assertEqual(session.state_snapshot("target"), ())

    def test_area_membership_03_exit_prunes_later_recurring_gate_requirement(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session()
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.advance_to(second_start.event_id)
        session.close_event()
        self.assertFalse(self._area_route_row(session)["membership"])

    def test_area_membership_04_direct_later_gate_for_nonmember_fails_closed(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session()
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        session.advance_to(second_start.event_id)
        with self.assertRaisesRegex(
            ControlEngineError,
            r"Area-owned gate .* nonmember",
        ):
            session.apply_branch(
                gate_id="ball_lightning_start_turn_save",
                outcome="save_success",
                target_id="target",
            )
        session.close_event()

    def test_area_membership_05_speed_zero_preserves_member_and_later_gate(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            route_distances={"target": 45},
            speed_zero_first_movement=("target",),
        )
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_failure",
        )
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        [blocked] = session.resolve_movement_response(target_id="target")
        blocked_payload = blocked.to_dict()["payload"]
        self.assertEqual(blocked_payload["reason"], "movement_unavailable")
        self.assertEqual(
            blocked_payload["movement_authority"]["effective_speeds_ft"],
            {"walk": 0},
        )
        route = self._area_route_row(session)
        self.assertTrue(route["membership"])
        self.assertEqual(
            route["routes"][0]["distance_to_exit_exact"],
            {"numerator": 45, "denominator": 1},
        )
        session.close_event()
        record = self._apply_ball_start_save(
            session,
            second_start,
            target_id="target",
            outcome="save_success",
        )
        self.assertEqual(
            record.to_dict()["payload"]["gate_id"],
            "ball_lightning_start_turn_save",
        )

    def test_area_membership_06_speed_recovery_consumes_preserved_route(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            route_distances={"target": 45},
            speed_zero_first_movement=("target",),
        )
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_failure",
        )
        first_movement, second_movement = events["movements_by_target"]["target"]
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        self._apply_ball_start_save(
            session,
            second_start,
            target_id="target",
            outcome="save_success",
        )
        session.advance_to(second_movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        selected = record.to_dict()["payload"]["selected_route"]
        self.assertEqual(selected["distance_before_ft"], 45)
        self.assertEqual(selected["progress_ft"], 30)
        self.assertEqual(selected["remaining_distance_ft"], 15)
        self.assertEqual(self._area_route_row(session)["remaining_distance_ft"], 15)

    def test_area_membership_07_compiled_reentry_restores_later_gate_eligibility(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            geometry_update=(2, "target", True, 12),
        )
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        update = events["update"]
        session.advance_to(update.event_id)
        update_record = session.apply_area_geometry_update(target_id="target")
        self.assertTrue(update_record.to_dict()["payload"]["membership_after"])
        session.close_event()
        recurring = self._apply_ball_start_save(
            session,
            second_start,
            target_id="target",
            outcome="save_success",
        )
        self.assertEqual(
            recurring.to_dict()["payload"]["gate_id"],
            "ball_lightning_start_turn_save",
        )

    def test_area_membership_08_moved_reentry_does_not_execute_entry_gate(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            initial_membership={"target": False},
            geometry_update=(2, "target", True, 12),
        )
        self._start_ball_concentration(session, events["activation"])
        [first_start] = events["starts_by_target"]["target"][:1]
        session.advance_to(first_start.event_id)
        session.close_event()
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        session.close_event()
        update = events["update"]
        session.advance_to(update.event_id)
        record = session.apply_area_geometry_update(target_id="target")
        payload = record.to_dict()["payload"]
        self.assertFalse(payload["moved_area_counts_as_entry"])
        self.assertEqual(payload["entry_gate_opportunity_ids"], [])
        self.assertEqual(record.record_kind, "area_geometry_update")
        self.assertFalse(any(
            issued.record_kind == "branch_transition"
            and issued.event_id == update.event_id
            for issued in session.issued_records()
        ))

    def test_area_membership_09_compiled_exit_prunes_gates_and_area_components(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            route_distances={"target": 45},
            speed_zero_first_movement=("target",),
            initial_conditions={"target": ("blinded",)},
            geometry_update=(2, "target", False, 0),
        )
        self._start_ball_concentration(session, events["activation"])
        first_start, second_start = events["starts_by_target"]["target"]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_failure",
        )
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        session.resolve_movement_response(target_id="target")
        session.close_event()
        update = events["update"]
        session.advance_to(update.event_id)
        record = session.apply_area_geometry_update(target_id="target")
        payload = record.to_dict()["payload"]
        self.assertEqual(
            set(payload["ended_component_ids"]),
            {
                "ball_lightning_attack_disadvantage",
                "ball_lightning_reaction_denial",
            },
        )
        self.assertEqual(
            {row["component_id"] for row in session.state_snapshot("target")},
            {"initial_blinded"},
        )
        self.assertFalse(self._area_route_row(session)["membership"])
        session.close_event()
        session.advance_to(second_start.event_id)
        session.close_event()

    def test_area_membership_10_member_without_components_carries_route_progress(
        self,
    ) -> None:
        session, _schedule, events = self._ball_membership_session(
            route_distances={"target": 45},
        )
        self._start_ball_concentration(session, events["activation"])
        [first_start] = events["starts_by_target"]["target"][:1]
        self._apply_ball_start_save(
            session,
            first_start,
            target_id="target",
            outcome="save_success",
        )
        self.assertEqual(session.state_snapshot("target"), ())
        [first_movement] = events["movements_by_target"]["target"][:1]
        session.advance_to(first_movement.event_id)
        [record] = session.resolve_movement_response(target_id="target")
        payload = record.to_dict()["payload"]
        self.assertFalse(payload["exited"])
        self.assertEqual(payload["ended_component_ids"], [])
        self.assertEqual(payload["selected_route"]["remaining_distance_ft"], 15)
        route = self._area_route_row(session)
        self.assertTrue(route["membership"])
        self.assertEqual(route["remaining_distance_ft"], 15)

    def test_area_membership_11_target_permutation_preserves_membership_and_gates(
        self,
    ) -> None:
        observed: dict[tuple[str, ...], dict[str, Any]] = {}
        for target_ids in (("alpha", "beta"), ("beta", "alpha")):
            with self.subTest(target_ids=target_ids):
                session, schedule, events = self._ball_membership_session(
                    target_ids=target_ids,
                    route_distances={"alpha": 10, "beta": 45},
                )
                self._start_ball_concentration(session, events["activation"])
                first_starts = {
                    rows[0].event_id: target_id
                    for target_id, rows in events["starts_by_target"].items()
                }
                second_starts = {
                    rows[1].event_id: target_id
                    for target_id, rows in events["starts_by_target"].items()
                }
                first_progress: dict[str, tuple[bool, int | float]] = {}
                later_gate_eligible: dict[str, bool] = {}
                last_second_start = max(
                    schedule.event(event_id).sequence
                    for event_id in second_starts
                )
                while session.cursor < last_second_start:
                    event = schedule.events[session.cursor + 1]
                    session.advance(event.event_id)
                    if event.event_id in first_starts:
                        session.apply_branch(
                            gate_id="ball_lightning_start_turn_save",
                            outcome="save_success",
                            target_id=first_starts[event.event_id],
                        )
                    elif event.event_id in second_starts:
                        target_id = second_starts[event.event_id]
                        member = self._area_route_row(session, target_id)["membership"]
                        later_gate_eligible[target_id] = bool(member)
                        if member:
                            session.apply_branch(
                                gate_id="ball_lightning_start_turn_save",
                                outcome="save_success",
                                target_id=target_id,
                            )
                    elif (
                        event.kind == "target_movement_opportunity"
                        and event.target_id in target_ids
                    ):
                        target_id = str(event.target_id)
                        route = self._area_route_row(session, target_id)
                        if route["membership"]:
                            session.resolve_movement_response(target_id=target_id)
                            if event.round == 1:
                                updated = self._area_route_row(session, target_id)
                                first_progress[target_id] = (
                                    bool(updated["membership"]),
                                    updated["remaining_distance_ft"],
                                )
                    session.close_event()
                observed[target_ids] = {
                    "first_progress": first_progress,
                    "later_gate_eligible": later_gate_eligible,
                }
        self.assertEqual(
            observed[("alpha", "beta")],
            observed[("beta", "alpha")],
        )
        self.assertEqual(
            observed[("alpha", "beta")],
            {
                "first_progress": {
                    "alpha": (False, 0),
                    "beta": (True, 15),
                },
                "later_gate_eligible": {
                    "alpha": False,
                    "beta": True,
                },
            },
        )

    def test_area_membership_12_initiative_conventions_use_correct_live_rounds(
        self,
    ) -> None:
        observed: dict[str, tuple[int, bool]] = {}
        for initiative, expected_round in (
            ("fighter_first_v1", 1),
            ("target_before_fighter_v1", 2),
        ):
            with self.subTest(initiative=initiative):
                session, _schedule, events = self._ball_membership_session(
                    initiative=initiative,
                )
                self._start_ball_concentration(session, events["activation"])
                first_start, second_start = events["starts_by_target"]["target"]
                self._apply_ball_start_save(
                    session,
                    first_start,
                    target_id="target",
                    outcome="save_success",
                )
                [first_movement] = events["movements_by_target"]["target"][:1]
                session.advance_to(first_movement.event_id)
                session.resolve_movement_response(target_id="target")
                session.close_event()
                session.advance_to(second_start.event_id)
                session.close_event()
                observed[initiative] = (
                    int(first_movement.round),
                    bool(self._area_route_row(session)["membership"]),
                )
                self.assertEqual(first_movement.round, expected_round)
        self.assertEqual(
            observed,
            {
                "fighter_first_v1": (1, False),
                "target_before_fighter_v1": (2, False),
            },
        )

    def test_area_membership_binding_tamper_fails_every_identity_boundary(
        self,
    ) -> None:
        tampered_values = {
            "_area_gate_bindings": MappingProxyType({}),
            "_persistent_area_ids": frozenset(),
            "_area_target_ids_by_area": MappingProxyType({}),
        }
        for field_name, tampered_value in tampered_values.items():
            with self.subTest(field=field_name, boundary="advance"):
                session, _schedule, events = self._ball_membership_session(
                    initial_membership={"target": False},
                )
                original = getattr(session, field_name)
                setattr(session, field_name, tampered_value)
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "runtime bindings",
                ):
                    session.advance_to(events["activation"].event_id)
                setattr(session, field_name, original)

            with self.subTest(field=field_name, boundary="apply"):
                session, _schedule, events = self._ball_membership_session()
                self._start_ball_concentration(session, events["activation"])
                [first_start] = events["starts_by_target"]["target"][:1]
                session.advance_to(first_start.event_id)
                original = getattr(session, field_name)
                setattr(session, field_name, tampered_value)
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "runtime bindings",
                ):
                    session.apply_branch(
                        gate_id="ball_lightning_start_turn_save",
                        outcome="save_success",
                        target_id="target",
                    )
                setattr(session, field_name, original)

            with self.subTest(field=field_name, boundary="result"):
                session, _schedule, events = self._ball_membership_session(
                    initial_membership={"target": False},
                )
                self._start_ball_concentration(session, events["activation"])
                session.complete()
                original = getattr(session, field_name)
                setattr(session, field_name, tampered_value)
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "runtime bindings",
                ):
                    session.result()
                setattr(session, field_name, original)
                session.result()

        for convention in ("shortest_route_v1", "fixed_occupancy_v1"):
            with self.subTest(convention=convention, boundary="root_replay"):
                session, _schedule, events = self._ball_membership_session(
                    area_response_convention=convention,
                )
                self._start_ball_concentration(session, events["activation"])
                [first_start] = events["starts_by_target"]["target"][:1]
                session.advance_to(first_start.event_id)
                requirement = "branch:ball_lightning_start_turn_save:target"
                self.assertIn(requirement, session._current_required_operations)
                session._current_required_operations.discard(requirement)
                session.close_event()
                if convention == "shortest_route_v1":
                    [first_movement] = events["movements_by_target"]["target"][:1]
                    session.advance_to(first_movement.event_id)
                    session.resolve_movement_response(target_id="target")
                    session.close_event()
                else:
                    second_start = events["starts_by_target"]["target"][1]
                    self._apply_ball_start_save(
                        session,
                        second_start,
                        target_id="target",
                        outcome="save_success",
                    )
                session.complete()
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "Area-owned root-gate execution",
                ):
                    session.result()

    def test_zero_area_01_both_conventions_create_and_complete_sessions(self) -> None:
        results = {
            convention: self._completed_zero_area_result(convention)
            for convention in ("shortest_route_v1", "fixed_occupancy_v1")
        }
        self.assertEqual(
            {result["compiled_program_id"] for result in results.values()},
            {"absolute_zero_t0_control"},
        )
        self.assertEqual(
            {
                result["scenario_convention"]["area_response_convention"]
                for result in results.values()
            },
            {"shortest_route_v1", "fixed_occupancy_v1"},
        )

    def test_zero_area_02_both_conventions_have_identical_mechanical_evidence(
        self,
    ) -> None:
        shortest = self._completed_zero_area_result("shortest_route_v1")
        fixed = self._completed_zero_area_result("fixed_occupancy_v1")
        mechanical_fields = (
            "gate_probabilities",
            "branch_probabilities",
            "component_reliability",
            "any_candidate_reliability",
            "any_component_reliability",
            "event_state_transitions",
            "primitive_contributions",
            "final_normalized_state",
        )
        for field in mechanical_fields:
            with self.subTest(field=field):
                self.assertEqual(shortest[field], fixed[field])

    def test_zero_area_03_scenario_provenance_differs_only_by_area_convention(
        self,
    ) -> None:
        shortest = self._completed_zero_area_result("shortest_route_v1")
        fixed = self._completed_zero_area_result("fixed_occupancy_v1")
        self.assertNotEqual(shortest["scenario_digest"], fixed["scenario_digest"])
        shortest_scenario = json.loads(json.dumps(shortest["scenario_record"]))
        fixed_scenario = json.loads(json.dumps(fixed["scenario_record"]))
        self.assertEqual(
            shortest_scenario["area_response_convention"],
            "shortest_route_v1",
        )
        self.assertEqual(
            fixed_scenario["area_response_convention"],
            "fixed_occupancy_v1",
        )
        for scenario in (shortest_scenario, fixed_scenario):
            scenario["area_response_convention"] = "selected_convention"
            scenario["versions"]["area_response_convention"] = (
                "selected_convention"
            )
        self.assertEqual(shortest_scenario, fixed_scenario)

    def test_zero_area_04_both_conventions_emit_no_area_route_state(self) -> None:
        for convention in ("shortest_route_v1", "fixed_occupancy_v1"):
            with self.subTest(convention=convention):
                result = self._completed_zero_area_result(convention)
                self.assertEqual(result["area_membership_and_route_records"], [])
                self.assertEqual(result["area_route_transitions"], [])
                self.assertEqual(result["final_area_route_states"], [])

    def test_zero_area_05_geometry_update_is_rejected(self) -> None:
        program = self.engine.program("absolute_zero_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ("target",),
            controller_events_by_round={
                1: [{"kind": "instantaneous_resolution"}],
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        update_event = next(
            event for event in schedule.events
            if event.kind == "instantaneous_resolution"
        )
        update = AreaGeometryUpdate(
            effect_id=program.effect_id,
            area_id="foreign_area",
            target_id="target",
            event_id=update_event.event_id,
            event_sequence=update_event.sequence,
            new_membership=False,
            routes=(),
        )
        with self.assertRaisesRegex(
            ControlEngineError,
            r"zero compiled areas|does not accept AreaGeometryUpdate",
        ):
            self.engine.execution_session(
                program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"constitution": 2},
                ),),
                selector_membership={
                    "absolute_zero_target": ("target",),
                },
                selector_context=_selector_context_for("target"),
                schedule=schedule,
                target_mechanics={"target": {}},
                area_response_convention="shortest_route_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
                area_geometry_updates=(update,),
            )

    def test_zero_area_06_multiple_compiled_areas_are_rejected(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        [area_selector] = [
            selector for selector in program.selectors
            if selector.area is not None
        ]
        area = area_selector.area
        self.assertIsNotNone(area)
        second_area_id = "synthetic_second_area"
        second_area_data = area.data.to_dict()
        second_area_data["area_id"] = second_area_id
        second_area = replace(
            area,
            area_id=second_area_id,
            qualified_id=QualifiedId(
                area.qualified_id.namespace,
                second_area_id,
            ),
            data=_frozen_map(second_area_data),
        )
        second_selector_id = "synthetic_second_area_targets"
        second_selector = replace(
            area_selector,
            selector_id=second_selector_id,
            qualified_id=QualifiedId(
                area_selector.qualified_id.namespace,
                second_selector_id,
            ),
            area=second_area,
        )
        selectors = (*program.selectors, second_selector)
        synthetic_program = replace(
            program,
            selectors=selectors,
            _selector_by_id=MappingProxyType({
                selector.selector_id: selector for selector in selectors
            }),
        )
        authority = self.engine.authority
        programs = tuple(
            synthetic_program if row.effect_id == program.effect_id else row
            for row in authority.programs
        )
        program_by_id = dict(authority._program_by_id)
        program_by_id[program.effect_id] = synthetic_program
        program_by_key = dict(authority._program_by_key)
        program_by_key[(program.entity_id, program.tier)] = synthetic_program
        synthetic_authority = replace(
            authority,
            programs=programs,
            _program_by_id=MappingProxyType(program_by_id),
            _program_by_key=MappingProxyType(program_by_key),
        )
        synthetic_engine = ControlEngine(
            catalog=self.engine.catalog,
            config=self.engine.config,
            authority=synthetic_authority,
            targets=self.engine.targets,
            target_supplement_digest=self.engine.target_supplement_digest,
        )
        schedule = synthetic_engine.schedule(
            "fighter_first_v1",
            ("target",),
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={"target": [0, 0, 0]},
        )
        with self.assertRaisesRegex(
            ControlEngineError,
            "do not support programs with multiple compiled areas",
        ):
            synthetic_engine.execution_session(
                synthetic_program,
                targets=(ReliabilityTarget(
                    "target",
                    15,
                    {"charisma": 2},
                ),),
                selector_membership={
                    "ball_lightning_area_targets": ("target",),
                    second_selector_id: ("target",),
                },
                selector_context=_selector_context_for("target"),
                schedule=schedule,
                target_mechanics={
                    "target": {
                        "base_speeds_ft": {"walk": 30},
                        "movement_mode": "walk",
                        "area_membership": True,
                        "area_routes": [self._route_geometry(
                            "target_exit",
                            distance=10,
                        ).route_input()],
                    },
                },
                area_response_convention="shortest_route_v1",
                displacement_function_id="sqrt_5ft_v1",
                probability_context=ProbabilityContext(save_dc=15),
                concentration_save_bonus=2,
            )


class ControlEngineIntegrationBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = ControlEngine.load()

    def test_compiled_branch_applies_to_state_with_timeline_expiry(self) -> None:
        program = self.engine.program_for("absolute_zero", 0)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {
                        "kind": "save_opportunity",
                        "target_id": "target",
                    }
                ]
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        event = next(
            row for row in schedule.events
            if row.kind == "save_opportunity"
        )
        state = self.engine._new_state()
        transition = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="absolute_zero_t0_save",
            outcome="save_failure",
            target_id="target",
            source_actor_id="controller",
            event_id=event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=_single_selector_membership(program, "target"),
            selector_context=_selector_context_for("target"),
        )
        self.assertEqual(transition["operation"], "branch_transition")
        self.assertEqual(
            [row.component_id for row in state.active_components("target")],
            ["absolute_zero_speed_zero"],
        )
        self.assertEqual(
            state.active_components("target")[0].expiry_event_id,
            "r2:controller:turn:end",
        )

    def test_branch_requires_typed_event_selectors_and_reachable_invocation_edge(self) -> None:
        program = self.engine.program("explosion_implosion_t0_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["primary", "secondary"],
            controller_events_by_round={
                1: [
                    {"kind": "hit", "target_id": "primary"},
                    {"kind": "save_opportunity", "target_id": "secondary"},
                ]
            },
            target_attack_counts={"primary": 0, "secondary": 0},
        )
        hit_event = next(
            event
            for event in schedule.events
            if event.kind == "hit" and event.target_id == "primary"
        )
        save_event = next(
            event
            for event in schedule.events
            if event.kind == "save_opportunity"
            and event.target_id == "secondary"
        )
        membership = {
            "explosion_implosion_primary": ["primary"],
            "explosion_implosion_secondary_targets": ["secondary"],
        }
        choices = {"explosion_implosion_mode": "explosion"}
        state = self.engine._new_state()
        with self.assertRaisesRegex(ControlEngineError, "no prior reachable"):
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id="explosion_implosion_t0_secondary_saves",
                outcome="save_failure",
                target_id="secondary",
                source_actor_id="controller",
                event_id=save_event.event_id,
                invocation_id="invocation",
                schedule=schedule,
                selector_membership=membership,
                selector_context=_selector_context_for("primary", "secondary"),
                choices=choices,
            )
        with self.assertRaisesRegex(ControlEngineError, "does not match"):
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id="explosion_implosion_t0_attack",
                outcome="attack_hit",
                target_id="primary",
                source_actor_id="controller",
                event_id=save_event.event_id,
                invocation_id="invocation",
                schedule=schedule,
                selector_membership=membership,
                selector_context=_selector_context_for("primary", "secondary"),
                choices=choices,
            )
        with self.assertRaisesRegex(ControlEngineError, "Selector membership"):
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id="explosion_implosion_t0_attack",
                outcome="attack_hit",
                target_id="primary",
                source_actor_id="controller",
                event_id=hit_event.event_id,
                invocation_id="invocation",
                schedule=schedule,
                selector_membership={
                    "explosion_implosion_primary": ["primary"]
                },
                selector_context=_selector_context_for("primary", "secondary"),
                choices=choices,
            )
        root = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="explosion_implosion_t0_attack",
            outcome="attack_hit",
            target_id="primary",
            source_actor_id="controller",
            event_id=hit_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("primary", "secondary"),
            choices=choices,
        )
        self.assertEqual(root["gate_id"], "explosion_implosion_t0_attack")
        self.assertEqual(
            root["next_gate_ids"],
            [
                "explosion_implosion_t0_primary_save",
                "explosion_implosion_t0_secondary_saves",
            ],
        )
        with self.assertRaisesRegex(ControlEngineError, "already resolved"):
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id="explosion_implosion_t0_attack",
                outcome="attack_hit",
                target_id="primary",
                source_actor_id="controller",
                event_id=hit_event.event_id,
                invocation_id="invocation",
                schedule=schedule,
                selector_membership=membership,
                selector_context=_selector_context_for("primary", "secondary"),
                choices=choices,
            )
        with self.assertRaisesRegex(ControlEngineError, "other_invocation"):
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id="explosion_implosion_t0_secondary_saves",
                outcome="save_failure",
                target_id="secondary",
                source_actor_id="controller",
                event_id=save_event.event_id,
                invocation_id="other_invocation",
                schedule=schedule,
                selector_membership=membership,
                selector_context=_selector_context_for("primary", "secondary"),
                choices=choices,
            )
        transition = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="explosion_implosion_t0_secondary_saves",
            outcome="save_failure",
            target_id="secondary",
            source_actor_id="controller",
            event_id=save_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("primary", "secondary"),
            choices=choices,
        )
        self.assertEqual(
            transition["filtered_branch"]["applies"],
            [
                "explosion_implosion_restrained",
                "explosion_implosion_outward_movement",
            ],
        )
        self.assertEqual(len(transition["pending_displacement_requests"]), 1)
        self.assertEqual(
            [component.component_id for component in state.active_components("secondary")],
            ["explosion_implosion_restrained"],
        )
        self.assertEqual(
            state.audit_ledger[-1]["invocation_id"],
            "invocation",
        )

    def test_refresh_branch_computes_and_records_timeline_expiry(self) -> None:
        program = self.engine.program("glacial_spike_t1_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": "hit", "target_id": "target"},
                    {"kind": "save_opportunity", "target_id": "target"},
                ]
            },
            target_attack_counts={"target": 0},
        )
        hit_event = next(event for event in schedule.events if event.kind == "hit")
        save_event = next(
            event for event in schedule.events if event.kind == "save_opportunity"
        )
        membership = _single_selector_membership(program, "target")
        state = self.engine._new_state()
        self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="glacial_spike_t1_attack",
            outcome="attack_hit",
            target_id="target",
            source_actor_id="controller",
            event_id=hit_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
        )
        transition = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="glacial_spike_t1_save",
            outcome="save_success",
            target_id="target",
            source_actor_id="controller",
            event_id=save_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
        )
        self.assertEqual(
            transition["refresh_expiry_event_ids"],
            {"glacial_spike_speed_reduction": "r2:controller:turn:end"},
        )
        self.assertEqual(
            state.active_components("target")[0].expiry_event_id,
            "r2:controller:turn:end",
        )

    def test_instantaneous_lift_and_fall_surface_outputs_without_persistent_state(self) -> None:
        program = self.engine.program_for("mass_levitation", 0)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "save_opportunity", "target_id": "target"}]
            },
            target_attack_counts={"target": 0},
        )
        initial_event = next(
            event
            for event in schedule.events
            if event.kind == "save_opportunity"
        )
        repeat_event = next(
            event
            for event in schedule.events
            if event.kind == "target_turn_start"
            and event.target_id == "target"
        )
        membership = _single_selector_membership(program, "target")
        state = self.engine._new_state()
        initial = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="mass_levitation_t0_initial_saves",
            outcome="save_failure",
            target_id="target",
            source_actor_id="controller",
            event_id=initial_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
        )
        self.assertEqual(len(initial["pending_displacement_requests"]), 1)
        self.assertNotIn(
            "mass_levitation_initial_lift",
            [component.component_id for component in state.active_components("target")],
        )
        fall = self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id="mass_levitation_t0_repeat_saves",
            outcome="save_success",
            target_id="target",
            source_actor_id="controller",
            event_id=repeat_event.event_id,
            invocation_id="invocation",
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
        )
        [fall_contribution] = fall["instantaneous_contributions"]
        self.assertEqual(fall_contribution["primitive_id"], "fall_transition")
        self.assertEqual(fall_contribution["family"], "retained_unpriced")
        self.assertEqual(state.active_components("target"), ())
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=state,
            event_state_transitions=(initial, fall),
        ).to_dict()
        self.assertEqual(
            [
                row["primitive_id"]
                for row in result["primitive_contributions"]["retained_unpriced"]
            ],
            ["fall_transition"],
        )
        self.assertEqual(
            result["final_normalized_state"]["target"]["active_components"],
            [],
        )

    def test_displacement_resolution_enters_public_vector_once(self) -> None:
        program = self.engine.program_for("telekinetic_shove", 0)
        component = next(
            component
            for component in program.components
            if component.magnitude.kind == "forced_movement"
        )
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "hit", "target_id": "target"}]
            },
            target_attack_counts={"target": 0},
        )
        event = next(event for event in schedule.events if event.kind == "hit")
        resolution = self.engine._resolve_displacement(
            component=component,
            target_id="target",
            event_id=event.event_id,
            epochs=self.engine._new_displacement_epochs(),
            displacement_function_id="sqrt_5ft_v1",
            vector_feet=[10, 0, 0],
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=self.engine._new_state(),
            displacement_records=(resolution, resolution),
        ).to_dict()
        [contribution] = result["primitive_contributions"]["denial"]
        self.assertEqual(contribution["primitive_id"], "forced_displacement")
        self.assertEqual(contribution["event_or_window_id"], event.event_id)
        self.assertEqual(len(result["displacement_epoch_records"]), 1)

    def test_typed_self_movement_boundaries_enter_public_result(self) -> None:
        program = self.engine.program_for("telekinetic_shove", 0)
        component = next(
            component for component in program.components
            if component.magnitude.kind == "forced_movement"
        )
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "hit", "target_id": "target"}]
            },
            target_attack_counts={"target": 0},
        )
        hit = next(event for event in schedule.events if event.kind == "hit")
        movement_events = [
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
        ]
        epochs = self.engine._new_displacement_epochs()
        movement_state = self.engine._new_state()
        frozen_program = self.engine.program_for("frozen_ground", 0)
        forced = self.engine._resolve_displacement(
            component=component,
            target_id="target",
            event_id=hit.event_id,
            epochs=epochs,
            displacement_function_id="sqrt_5ft_v1",
            vector_feet=[10, 0, 0],
        )
        legal_reset = self.engine._resolve_self_movement_epoch(
            epochs=epochs,
            state=movement_state,
            schedule=schedule,
            target_id="target",
            event_id=movement_events[0].event_id,
            legal=True,
            base_speeds_ft={"walk": 30},
            movement_mode="walk",
        )
        _activate_component(
            movement_state,
            frozen_program,
            frozen_program.component("frozen_ground_speed_zero"),
            event_id="fixture:speed_zero:apply",
        )
        speed_zero = self.engine._resolve_self_movement_epoch(
            epochs=epochs,
            state=movement_state,
            schedule=schedule,
            target_id="target",
            event_id=movement_events[1].event_id,
            legal=True,
            base_speeds_ft={"walk": 30},
            movement_mode="walk",
        )
        self.assertTrue(legal_reset["record"]["reset"])
        self.assertEqual(legal_reset["record"]["new_epoch"], 2)
        self.assertFalse(speed_zero["record"]["reset"])
        self.assertEqual(speed_zero["record"]["new_epoch"], 2)
        self.assertEqual(speed_zero["record"]["reason"], "speed_zero")
        self.assertEqual(
            speed_zero["record"]["movement_authority"]["effective_speeds_ft"],
            {"walk": 0},
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=movement_state,
            displacement_records=(forced, legal_reset, speed_zero),
        ).to_dict()
        self.assertEqual(
            [row["kind"] for row in result["displacement_epoch_records"]],
            [
                "forced_displacement",
                "displacement_epoch_boundary",
                "displacement_epoch_boundary",
            ],
        )
        self.assertEqual(
            len(result["primitive_contributions"]["denial"]),
            1,
        )

    def test_prone_lifecycle_mutates_state_only_after_a_legal_stand(self) -> None:
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={"target": [0, 0, 0]},
        )
        movement_events = [
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
        ]
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        state = self.engine._new_state()
        state.apply_component(
            effect_id="fixture_prone",
            component={
                "component_id": "fixture_prone_component",
                "magnitude": {"kind": "condition", "condition": "prone"},
                "duration": {
                    "kind": "concentration",
                    "maximum_value": 1,
                    "unit": "minute",
                },
                "stacking": {
                    "key": "fixture_prone",
                    "mode": "nonstacking",
                    "refresh": "none",
                },
            },
            target_id="target",
            source_actor_id="controller",
            event_id="fixture:apply",
            invocation_id="fixture_invocation",
        )
        frozen_program = self.engine.program_for("frozen_ground", 0)
        _activate_component(
            state,
            frozen_program,
            frozen_program.component("frozen_ground_speed_zero"),
            event_id="fixture:prone:speed_zero",
        )
        before_rejected = state.snapshot()
        with self.assertRaisesRegex(ControlEngineError, "typed movement"):
            self.engine._resolve_prone_movement(
                state=state,
                schedule=schedule,
                target_id="target",
                event_id=activation.event_id,
                base_speeds_ft={"walk": 30},
                movement_mode="walk",
            )
        with self.assertRaisesRegex(TimelineError, "resolve exactly once"):
            self.engine._resolve_prone_movement(
                state=state,
                schedule=schedule,
                target_id="target",
                event_id="fixture:not_in_schedule",
                base_speeds_ft={"walk": 30},
                movement_mode="walk",
            )
        self.assertEqual(state.snapshot(), before_rejected)
        blocked = self.engine._resolve_prone_movement(
            state=state,
            schedule=schedule,
            target_id="target",
            event_id=movement_events[0].event_id,
            base_speeds_ft={"walk": 30},
            movement_mode="walk",
        )
        self.assertFalse(blocked["stood"])
        self.assertEqual(blocked["reason"], "speed_zero")
        self.assertEqual(
            blocked["movement_authority"]["effective_speeds_ft"],
            {"walk": 0},
        )
        self.assertEqual(
            {
                component.component_id
                for component in state.active_components("target")
            },
            {"fixture_prone_component", "frozen_ground_speed_zero"},
        )
        state.terminate(
            target_id="target",
            component_id="frozen_ground_speed_zero",
            effect_id=frozen_program.effect_id,
            event_id="fixture:prone:speed_zero:end",
            reason="duration_expiry",
        )
        stood = self.engine._resolve_prone_movement(
            state=state,
            schedule=schedule,
            target_id="target",
            event_id=movement_events[1].event_id,
            base_speeds_ft={"walk": 30},
            movement_mode="walk",
        )
        self.assertTrue(stood["stood"])
        self.assertEqual(state.active_components("target"), ())
        self.assertEqual(
            state.final_normalized_state(self.engine.catalog)["target"]["conditions"],
            [],
        )

    def test_area_exit_and_area_end_records_match_mutated_state(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        for effect_active, convention in (
            (True, "shortest_route_v1"),
            (False, "fixed_occupancy_v1"),
        ):
            with self.subTest(effect_active=effect_active):
                schedule = self.engine.schedule(
                    "fighter_first_v1",
                    ["target"],
                    controller_events_by_round={
                        1: [{"kind": "concentration_end"}]
                    },
                    target_attack_counts={"target": [0, 0, 0]},
                )
                event_kind = (
                    "target_movement_opportunity"
                    if effect_active else "concentration_end"
                )
                response_event = next(
                    event for event in schedule.events
                    if event.kind == event_kind
                )
                state = self.engine._new_state()
                for component in program.components:
                    _activate_component(state, program, component)
                response = self.engine._resolve_area_response(
                    state=state,
                    schedule=schedule,
                    effect=program,
                    target_ids=("target",),
                    selector_membership=_single_selector_membership(program, "target"),
                    selector_context=_selector_context_for("target"),
                    target_id="target",
                    event_id=response_event.event_id,
                    area_response_convention=convention,
                    membership=True,
                    effect_active=effect_active,
                    routes=(
                        [
                            {
                                "route_id": "walk_exit",
                                "mode": "walk",
                                "distance_to_exit_ft": 5,
                                "compatible": True,
                                "movement_cost_multiplier": 1,
                                "environment": "grounded",
                            }
                        ]
                        if effect_active
                        else None
                    ),
                    base_speeds_ft=(
                        {"walk": 30} if effect_active else None
                    ),
                )
                self.assertTrue(response["exited"])
                self.assertEqual(
                    set(response["ended_component_ids"]),
                    {component.component_id for component in program.components},
                )
                self.assertEqual(state.active_components("target"), ())
                self.assertEqual(response["active_components_after"], [])

    def test_assembler_rejects_forged_prone_and_area_event_ownership(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={"target": [0, 0, 0]},
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        state = self.engine._new_state()
        state.apply_component(
            effect_id="fixture_prone",
            component={
                "component_id": "fixture_prone_component",
                "magnitude": {"kind": "condition", "condition": "prone"},
                "duration": {
                    "kind": "concentration",
                    "maximum_value": 1,
                    "unit": "minute",
                },
                "stacking": {
                    "key": "fixture_prone",
                    "mode": "nonstacking",
                    "refresh": "none",
                },
            },
            target_id="target",
            source_actor_id="controller",
            event_id="fixture:apply",
            invocation_id="fixture_invocation",
        )
        prone_record = self.engine._resolve_prone_movement(
            state=state,
            schedule=schedule,
            target_id="target",
            event_id=movement.event_id,
            base_speeds_ft={"walk": 30},
            movement_mode="walk",
        )
        for component in program.components:
            _activate_component(state, program, component)
        area_record = self.engine._resolve_area_response(
            state=state,
            schedule=schedule,
            effect=program,
            target_ids=("target",),
            selector_membership=_single_selector_membership(program, "target"),
            selector_context=_selector_context_for("target"),
            target_id="target",
            event_id=movement.event_id,
            area_response_convention="shortest_route_v1",
            membership=True,
            effect_active=True,
            routes=[{
                "route_id": "walk_exit",
                "mode": "walk",
                "distance_to_exit_ft": 5,
                "compatible": True,
                "movement_cost_multiplier": 1,
                "environment": "grounded",
            }],
            base_speeds_ft={"walk": 30},
        )
        assembled = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability(program.effect_id, "target"),
            schedule=schedule,
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=state,
            prone_records=(prone_record, prone_record),
            area_records=(area_record, area_record),
        ).to_dict()
        self.assertEqual(len(assembled["prone_standing_records"]), 1)
        self.assertEqual(
            len(assembled["area_membership_and_route_records"]),
            1,
        )
        for field_name, record in (
            ("prone_records", prone_record),
            ("area_records", area_record),
        ):
            with self.assertRaisesRegex(
                ControlEngineError,
                "closed record shape",
            ):
                self.engine._assemble_result_legacy(
                    effect=program,
                    reliability=_reliability(program.effect_id, "target"),
                    schedule=schedule,
                    area_response_convention="shortest_route_v1",
                    displacement_function_id="sqrt_5ft_v1",
                    state=state,
                    **{
                        field_name: ({
                            "kind": record["kind"],
                            "event_id": record["event_id"],
                            "target_id": "target",
                        },)
                    },
                )
            with self.assertRaisesRegex(ControlEngineError, "conflicts"):
                self.engine._assemble_result_legacy(
                    effect=program,
                    reliability=_reliability(program.effect_id, "target"),
                    schedule=schedule,
                    area_response_convention="shortest_route_v1",
                    displacement_function_id="sqrt_5ft_v1",
                    state=state,
                    **{
                        field_name: (
                            record,
                            {**record, "ended_component_ids": []},
                        )
                    },
                )
        for field_name, record in (
            ("prone_records", prone_record),
            ("area_records", area_record),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(
                    ControlEngineError,
                    "typed target event",
                ):
                    self.engine._assemble_result_legacy(
                        effect=program,
                        reliability=_reliability(
                            program.effect_id,
                            "target",
                        ),
                        schedule=schedule,
                        area_response_convention="shortest_route_v1",
                        displacement_function_id="sqrt_5ft_v1",
                        state=state,
                        **{
                            field_name: (
                                {
                                    **record,
                                    "event_id": activation.event_id,
                                },
                            )
                        },
                    )

    def test_frozen_ground_movement_uses_active_state_authority(self) -> None:
        program = self.engine.program_for("frozen_ground", 0)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [{"kind": "concentration_end"}]
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        movement_events = iter(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
        )
        area_end_event = next(
            event for event in schedule.events
            if event.kind == "concentration_end"
        )
        state = self.engine._new_state()
        for component_id in (
            "frozen_ground_difficult_terrain",
            "frozen_ground_speed_zero",
        ):
            _activate_component(
                state,
                program,
                program.component(component_id),
            )
        membership = _single_selector_membership(program, "target")
        selector_context = _selector_context_for("target")

        def resolve(distance_to_exit_ft: int) -> dict[str, object]:
            event = next(movement_events)
            return self.engine._resolve_area_response(
                state=state,
                schedule=schedule,
                effect=program,
                target_ids=("target",),
                selector_membership=membership,
                selector_context=selector_context,
                target_id="target",
                event_id=event.event_id,
                area_response_convention="shortest_route_v1",
                membership=True,
                effect_active=True,
                routes=[{
                    "route_id": "walk_out",
                    "mode": "walk",
                    "distance_to_exit_ft": distance_to_exit_ft,
                    "compatible": True,
                    "movement_cost_multiplier": 1,
                    "environment": "grounded",
                }],
                base_speeds_ft={"walk": 30},
            )

        blocked = resolve(20)
        self.assertFalse(blocked["exited"])
        self.assertEqual(blocked["reason"], "movement_unavailable")
        self.assertEqual(
            blocked["movement_authority"]["effective_speeds_ft"],
            {"walk": 0},
        )
        self.assertEqual(
            blocked["movement_authority"][
                "active_area_movement_cost_multiplier"
            ],
            {"numerator": 2, "denominator": 1},
        )
        [route_authority] = blocked["movement_authority"]["route_multipliers"]
        self.assertEqual(
            route_authority["base_movement_cost_multiplier"],
            {"numerator": 1, "denominator": 1},
        )
        self.assertEqual(
            route_authority["effective_movement_cost_multiplier"],
            {"numerator": 2, "denominator": 1},
        )
        self.assertEqual(
            blocked["area_bound_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        self.assertEqual(
            blocked["retained_component_ids"],
            ["frozen_ground_speed_zero"],
        )
        self.assertEqual(
            {
                component.component_id
                for component in state.active_components("target")
            },
            {
                "frozen_ground_difficult_terrain",
                "frozen_ground_speed_zero",
            },
        )

        state.terminate(
            target_id="target",
            component_id="frozen_ground_speed_zero",
            effect_id=program.effect_id,
            event_id="fixture:frozen_ground:speed_zero:end",
            reason="duration_expiry",
        )
        progress = resolve(20)
        self.assertFalse(progress["exited"])
        self.assertEqual(
            progress["movement_authority"]["effective_speeds_ft"],
            {"walk": 30},
        )
        self.assertEqual(
            progress["selected_route"]["movement_cost_multiplier"],
            2,
        )
        self.assertEqual(progress["selected_route"]["progress_ft"], 15)
        self.assertEqual(
            progress["selected_route"]["remaining_distance_ft"],
            5,
        )
        self.assertEqual(progress["ended_component_ids"], [])

        exited = resolve(5)
        self.assertTrue(exited["exited"])
        self.assertEqual(
            exited["ended_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        self.assertEqual(state.active_components("target"), ())

        area_end_state = self.engine._new_state()
        for component_id in (
            "frozen_ground_difficult_terrain",
            "frozen_ground_speed_zero",
        ):
            _activate_component(
                area_end_state,
                program,
                program.component(component_id),
            )
        area_ended = self.engine._resolve_area_response(
            state=area_end_state,
            schedule=schedule,
            effect=program,
            target_ids=("target",),
            selector_membership=membership,
            selector_context=selector_context,
            target_id="target",
            event_id=area_end_event.event_id,
            area_response_convention="fixed_occupancy_v1",
            membership=True,
            effect_active=False,
        )
        self.assertEqual(
            area_ended["ended_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        self.assertEqual(
            [
                component.component_id
                for component in area_end_state.active_components("target")
            ],
            ["frozen_ground_speed_zero"],
        )

    def test_active_area_typed_target_exit_ends_only_area_bound_state(self) -> None:
        program = self.engine.program_for("frozen_ground", 0)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target", "other"],
            controller_events_by_round={
                1: [{"kind": "exit", "target_id": "target"}],
            },
            target_events_by_round={
                "target": {
                    1: [{"kind": "exit", "phase": "after_movement"}],
                },
                "other": {
                    1: [{"kind": "exit", "phase": "after_movement"}],
                },
            },
            target_attack_counts={
                "target": [0, 0, 0],
                "other": [0, 0, 0],
            },
        )
        target_exit = next(
            event for event in schedule.events
            if event.kind == "exit"
            and event.target_id == "target"
            and event.turn_owner == "target"
        )
        other_exit = next(
            event for event in schedule.events
            if event.kind == "exit"
            and event.target_id == "other"
        )
        controller_exit = next(
            event for event in schedule.events
            if event.kind == "exit"
            and event.turn_owner == "controller"
        )
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
            and event.target_id == "target"
        )
        state = self.engine._new_state()
        for component_id in (
            "frozen_ground_difficult_terrain",
            "frozen_ground_speed_zero",
        ):
            _activate_component(
                state,
                program,
                program.component(component_id),
            )
        common = {
            "state": state,
            "schedule": schedule,
            "effect": program,
            "target_ids": ("target", "other"),
            "selector_membership": _single_selector_membership(
                program,
                "target",
            ),
            "selector_context": _selector_context_for("target", "other"),
            "target_id": "target",
            "area_response_convention": "shortest_route_v1",
            "membership": True,
            "effect_active": True,
        }
        before_snapshot = state.snapshot()
        before_audit = json.loads(json.dumps(state.audit_ledger))
        with self.assertRaisesRegex(
            ControlEngineError,
            "requires shortest_route_v1",
        ):
            self.engine._resolve_area_response(
                **{
                    **common,
                    "area_response_convention": "fixed_occupancy_v1",
                    "event_id": target_exit.event_id,
                    "post_movement_membership": False,
                }
            )
        self.assertEqual(state.snapshot(), before_snapshot)
        self.assertEqual(state.audit_ledger, before_audit)
        invalid_calls = (
            (
                {"event_id": target_exit.event_id},
                "explicit post_movement_membership false",
            ),
            (
                {
                    "event_id": target_exit.event_id,
                    "post_movement_membership": True,
                },
                "explicit post_movement_membership false",
            ),
            (
                {
                    "event_id": controller_exit.event_id,
                    "post_movement_membership": False,
                },
                "exact typed exit event",
            ),
            (
                {
                    "event_id": other_exit.event_id,
                    "post_movement_membership": False,
                },
                "exact typed exit event",
            ),
            (
                {
                    "event_id": movement.event_id,
                    "post_movement_membership": False,
                },
                "valid only for an active typed exit",
            ),
            (
                {
                    "event_id": target_exit.event_id,
                    "post_movement_membership": False,
                    "base_speeds_ft": {"walk": 30},
                },
                "does not accept movement or route inference",
            ),
        )
        for extra, message in invalid_calls:
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(ControlEngineError, message):
                    self.engine._resolve_area_response(**common, **extra)
                self.assertEqual(state.snapshot(), before_snapshot)
                self.assertEqual(state.audit_ledger, before_audit)

        response = self.engine._resolve_area_response(
            **common,
            event_id=target_exit.event_id,
            post_movement_membership=False,
        )
        self.assertEqual(response["reason"], "typed_target_exit")
        self.assertTrue(response["membership_before"])
        self.assertFalse(response["membership_after"])
        self.assertTrue(response["exited"])
        self.assertIsNone(response["movement_authority"])
        self.assertIsNone(response["selected_route"])
        self.assertEqual(
            response["ended_component_ids"],
            ["frozen_ground_difficult_terrain"],
        )
        self.assertEqual(
            response["retained_component_ids"],
            ["frozen_ground_speed_zero"],
        )
        self.assertEqual(
            [
                component.component_id
                for component in state.active_components("target")
            ],
            ["frozen_ground_speed_zero"],
        )
        assembled = self.engine._assemble_result_legacy(
            effect=program,
            reliability=_reliability_for_targets(
                program.effect_id,
                ("target", "other"),
            ),
            schedule=schedule,
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=state,
            area_records=(response,),
        ).to_dict()
        self.assertEqual(
            assembled["area_membership_and_route_records"],
            [response],
        )

    def test_ball_lightning_moved_area_cannot_rewrite_entry_policy(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        blocked = self.engine._resolve_compiled_area_entry(
            effect=program,
            target_ids=("target",),
            selector_membership=_single_selector_membership(program, "target"),
            selector_context=_selector_context_for("target"),
            target_id="target",
            turn_id="round_1_target_turn",
            was_member=False,
            is_member=True,
            caused_by_area_movement=True,
        )
        self.assertFalse(blocked["triggered"])
        self.assertEqual(blocked["reason"], "moved_area_does_not_count")
        self.assertFalse(
            blocked["entry_policy"]["moved_area_counts_as_entry"]
        )
        self.assertEqual(blocked["gate_opportunity_ids"], [])
        entered = self.engine._resolve_compiled_area_entry(
            effect=program,
            target_ids=("target",),
            selector_membership=_single_selector_membership(program, "target"),
            selector_context=_selector_context_for("target"),
            target_id="target",
            turn_id="round_1_target_turn",
            was_member=False,
            is_member=True,
            caused_by_area_movement=False,
        )
        self.assertTrue(entered["triggered"])
        self.assertEqual(
            entered["gate_opportunity_ids"],
            ["ball_lightning_entry_save"],
        )

    def _mass_levitation_concentration_scenario(
        self,
        *,
        tier: int = 0,
    ) -> dict[str, object]:
        program = self.engine.program_for("mass_levitation", tier)
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": "damage_context"},
                    {"kind": "activation"},
                    {"kind": "save_opportunity", "target_id": "target"},
                    {"kind": "damage_context"},
                    {"kind": "concentration_end"},
                    {"kind": "activation"},
                    {"kind": "concentration_end"},
                ]
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        activations = [
            event for event in schedule.events if event.kind == "activation"
        ]
        end_events = [
            event for event in schedule.events
            if event.kind == "concentration_end"
        ]
        damage_events = [
            event for event in schedule.events
            if event.kind == "damage_context"
        ]
        save_event = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        membership = _single_selector_membership(program, "target")
        state = self.engine._new_state()
        invocation_id = f"mass_levitation_t{tier}_invocation"
        self.engine._apply_resolved_branch(
            state=state,
            effect=program,
            gate_id=f"mass_levitation_t{tier}_initial_saves",
            outcome="save_failure",
            target_id="target",
            source_actor_id="controller",
            event_id=save_event.event_id,
            invocation_id=invocation_id,
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
        )
        tracker = ConcentrationTracker(save_bonus=0)
        start = self.engine._start_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            event_id=activations[0].event_id,
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
            invocation_id=invocation_id,
            source_actor_id="controller",
        )
        return {
            "program": program,
            "schedule": schedule,
            "membership": membership,
            "selector_context": _selector_context_for("target"),
            "state": state,
            "tracker": tracker,
            "invocation_id": invocation_id,
            "activations": activations,
            "end_events": end_events,
            "pre_start_damage_event": damage_events[0],
            "damage_events": damage_events[1:],
            "start": start,
        }

    def test_concentration_replacement_executes_old_compiled_end_gate(self) -> None:
        scenario = self._mass_levitation_concentration_scenario(tier=0)
        second_program = self.engine.program_for("mass_levitation", 1)
        before_snapshot = scenario["state"].snapshot()
        before_audit = list(scenario["state"].audit_ledger)
        before_records = list(scenario["tracker"].records)
        with self.assertRaisesRegex(ControlEngineError, "immediate next"):
            self.engine._start_concentration(
                state=scenario["state"],
                tracker=scenario["tracker"],
                effect=second_program,
                event_id=scenario["activations"][1].event_id,
                replacement_end_event_id=scenario["end_events"][1].event_id,
                schedule=scenario["schedule"],
                selector_membership=_single_selector_membership(
                    second_program,
                    "target",
                ),
                selector_context=_selector_context_for("target"),
                invocation_id="mass_levitation_t1_invocation",
                source_actor_id="controller",
            )
        self.assertEqual(scenario["state"].snapshot(), before_snapshot)
        self.assertEqual(scenario["state"].audit_ledger, before_audit)
        self.assertEqual(scenario["tracker"].records, before_records)
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            scenario["program"].effect_id,
        )
        replacement = self.engine._start_concentration(
            state=scenario["state"],
            tracker=scenario["tracker"],
            effect=second_program,
            event_id=scenario["activations"][1].event_id,
            replacement_end_event_id=scenario["end_events"][0].event_id,
            schedule=scenario["schedule"],
            selector_membership=_single_selector_membership(
                second_program,
                "target",
            ),
            selector_context=_selector_context_for("target"),
            invocation_id="mass_levitation_t1_invocation",
            source_actor_id="controller",
        )
        self.assertEqual(
            [record["kind"] for record in replacement["tracker_records"]],
            ["concentration_end", "concentration_start"],
        )
        [end_transition] = replacement["applied_end_transitions"]
        self.assertEqual(
            end_transition["reason"],
            "new_concentration_replacement",
        )
        self.assertEqual(len(end_transition["ended_state_instances"]), 2)
        [gate_transition] = end_transition[
            "concentration_end_gate_transitions"
        ]
        self.assertEqual(
            gate_transition["gate_id"],
            "mass_levitation_t0_concentration_end",
        )
        self.assertEqual(
            [row["primitive_id"] for row in gate_transition[
                "instantaneous_contributions"
            ]],
            ["fall_transition"],
        )
        self.assertEqual(scenario["state"].active_components("target"), ())
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            second_program.effect_id,
        )

    def test_failed_concentration_check_executes_fall_and_final_ledger_agrees(
        self,
    ) -> None:
        scenario = self._mass_levitation_concentration_scenario()
        common = {
            "state": scenario["state"],
            "tracker": scenario["tracker"],
            "effect": scenario["program"],
            "schedule": scenario["schedule"],
            "selector_membership": scenario["membership"],
            "selector_context": scenario["selector_context"],
            "invocation_id": scenario["invocation_id"],
            "source_actor_id": "controller",
            "amount": 1,
            "source": "later_blood_tax",
            "event_id": scenario["damage_events"][0].event_id,
            "concentration_end_event_id": scenario["end_events"][0].event_id,
            "outcome": "failure",
        }
        before_snapshot = scenario["state"].snapshot()
        before_audit = list(scenario["state"].audit_ledger)
        before_records = list(scenario["tracker"].records)
        with self.assertRaisesRegex(ControlEngineError, "immediate next"):
            self.engine._check_concentration(
                **{
                    **common,
                    "concentration_end_event_id": (
                        scenario["end_events"][1].event_id
                    ),
                },
                success_probability=Fraction(1, 2),
            )
        self.assertEqual(scenario["state"].snapshot(), before_snapshot)
        self.assertEqual(scenario["state"].audit_ledger, before_audit)
        self.assertEqual(scenario["tracker"].records, before_records)
        missing_end = {
            key: value for key, value in common.items()
            if key != "concentration_end_event_id"
        }
        with self.assertRaisesRegex(
            ControlEngineError,
            "required on check failure",
        ):
            self.engine._check_concentration(
                **missing_end,
                success_probability=Fraction(1, 2),
            )
        with self.assertRaisesRegex(TimelineError, "zero probability"):
            self.engine._check_concentration(
                **common,
                success_probability=Fraction(1),
            )
        self.assertEqual(
            len(scenario["state"].active_components("target")),
            2,
        )
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            scenario["program"].effect_id,
        )

        lifecycle = self.engine._check_concentration(
            **common,
            success_probability=Fraction(1, 2),
        )
        self.assertEqual(
            [record["kind"] for record in lifecycle["tracker_records"]],
            ["concentration_check", "concentration_end"],
        )
        self.assertEqual(
            lifecycle["tracker_records"][0]["event_id"],
            scenario["damage_events"][0].event_id,
        )
        self.assertEqual(
            lifecycle["tracker_records"][1]["event_id"],
            scenario["end_events"][0].event_id,
        )
        [end_transition] = lifecycle["applied_end_transitions"]
        self.assertEqual(end_transition["reason"], "failed_concentration_save")
        [gate_transition] = end_transition[
            "concentration_end_gate_transitions"
        ]
        [fall] = gate_transition["instantaneous_contributions"]
        self.assertEqual(fall["primitive_id"], "fall_transition")
        self.assertEqual(scenario["state"].active_components("target"), ())
        self.assertIsNone(scenario["tracker"].active_effect_id)
        self.assertNotIn(
            "mass_levitation_fall",
            [
                row["component_id"]
                for row in end_transition["active_components_after"]
            ],
        )
        ledger_end = next(
            row
            for row in reversed(scenario["state"].audit_ledger)
            if row.get("operation") == "concentration_end"
        )
        self.assertEqual(ledger_end["operation"], "concentration_end")
        self.assertEqual(ledger_end["active_components_after"], [])
        self.assertEqual(
            ledger_end["fall_transitions"][0]["source_component_ids"],
            ["mass_levitation_fall"],
        )
        assembled = self.engine._assemble_result_legacy(
            effect=scenario["program"],
            reliability=_reliability(
                scenario["program"].effect_id,
                "target",
            ),
            schedule=scenario["schedule"],
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=scenario["state"],
            concentration_records=(lifecycle, lifecycle),
        ).to_dict()
        self.assertEqual(assembled["concentration_records"], [lifecycle])

    def test_successful_concentration_check_validates_only_damage_cause(self) -> None:
        scenario = self._mass_levitation_concentration_scenario()
        common = {
            "state": scenario["state"],
            "tracker": scenario["tracker"],
            "effect": scenario["program"],
            "schedule": scenario["schedule"],
            "selector_membership": scenario["membership"],
            "selector_context": scenario["selector_context"],
            "invocation_id": scenario["invocation_id"],
            "source_actor_id": "controller",
            "amount": 12,
            "source": "damage",
            "outcome": "success",
            "success_probability": Fraction(1, 2),
        }
        before_records = list(scenario["tracker"].records)
        before_snapshot = scenario["state"].snapshot()
        before_audit = list(scenario["state"].audit_ledger)
        with self.assertRaisesRegex(ControlEngineError, "after concentration startup"):
            self.engine._check_concentration(
                **common,
                event_id=scenario["pre_start_damage_event"].event_id,
            )
        with self.assertRaisesRegex(ControlEngineError, "damage_context"):
            self.engine._check_concentration(
                **common,
                event_id=scenario["activations"][1].event_id,
            )
        with self.assertRaisesRegex(
            ControlEngineError,
            "invalid on check success",
        ):
            self.engine._check_concentration(
                **common,
                event_id=scenario["damage_events"][0].event_id,
                concentration_end_event_id=scenario["end_events"][0].event_id,
            )
        self.assertEqual(scenario["tracker"].records, before_records)
        self.assertEqual(scenario["state"].snapshot(), before_snapshot)
        self.assertEqual(scenario["state"].audit_ledger, before_audit)
        lifecycle = self.engine._check_concentration(
            **common,
            event_id=scenario["damage_events"][0].event_id,
        )
        self.assertEqual(
            [row["kind"] for row in lifecycle["tracker_records"]],
            ["concentration_check"],
        )
        self.assertEqual(
            lifecycle["check_record"]["event_id"],
            scenario["damage_events"][0].event_id,
        )
        self.assertEqual(lifecycle["applied_end_transitions"], [])
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            scenario["program"].effect_id,
        )

    def test_concentration_lifecycle_audits_are_exact_and_non_aliasing(
        self,
    ) -> None:
        scenario = self._mass_levitation_concentration_scenario()
        start = scenario["start"]
        check = self.engine._check_concentration(
            state=scenario["state"],
            tracker=scenario["tracker"],
            effect=scenario["program"],
            schedule=scenario["schedule"],
            selector_membership=scenario["membership"],
            selector_context=scenario["selector_context"],
            invocation_id=scenario["invocation_id"],
            source_actor_id="controller",
            amount=12,
            source="damage",
            event_id=scenario["damage_events"][0].event_id,
            outcome="success",
            success_probability=Fraction(1, 2),
        )
        reconciliation = self.engine._reconcile_concentration_duration(
            state=scenario["state"],
            tracker=scenario["tracker"],
            effect=scenario["program"],
            schedule=scenario["schedule"],
            selector_membership=scenario["membership"],
            selector_context=scenario["selector_context"],
            invocation_id=scenario["invocation_id"],
            source_actor_id="controller",
            event_id="r1:controller:turn:end",
        )
        saved = [
            json.loads(json.dumps(row))
            for row in (start, check, reconciliation)
        ]
        operations = [row["kind"] for row in saved]
        audits = [
            next(
                row
                for row in reversed(scenario["state"].audit_ledger)
                if row.get("operation") == operation
            )
            for operation in operations
        ]
        for operation, row, audit in zip(
            operations,
            saved,
            audits,
            strict=True,
        ):
            self.assertEqual(audit, {"operation": operation, **row})
        self.assertIsNot(audits[0]["start_record"], start["start_record"])
        self.assertIsNot(audits[1]["check_record"], check["check_record"])
        self.assertIsNot(
            audits[2]["active_components_after"],
            reconciliation["active_components_after"],
        )
        assembled = self.engine._assemble_result_legacy(
            effect=scenario["program"],
            reliability=_reliability(
                scenario["program"].effect_id,
                "target",
            ),
            schedule=scenario["schedule"],
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=scenario["state"],
            concentration_records=tuple(saved),
        ).to_dict()
        self.assertEqual(len(assembled["concentration_records"]), 3)

        start["start_record"]["authority_metadata"][
            "concentration_component_ids"
        ] = []
        check["check_record"]["dc"] = 999
        check["tracker_records"][0]["dc"] = 999
        reconciliation["status"] = "before_expiry"
        reconciliation["expected_expiry_event_id"] = (
            "r2:controller:turn:start"
        )
        for operation, row, audit in zip(
            operations,
            saved,
            audits,
            strict=True,
        ):
            self.assertEqual(audit, {"operation": operation, **row})
        for forged, message in (
            (start, "concentration_component_ids"),
            (check, "numerics"),
            (reconciliation, "audit ledger"),
        ):
            with self.assertRaisesRegex(ControlEngineError, message):
                self.engine._assemble_result_legacy(
                    effect=scenario["program"],
                    reliability=_reliability(
                        scenario["program"].effect_id,
                        "target",
                    ),
                    schedule=scenario["schedule"],
                    area_response_convention="fixed_occupancy_v1",
                    displacement_function_id="sqrt_5ft_v1",
                    state=scenario["state"],
                    concentration_records=(forged,),
                )

    def test_concentration_authority_ids_cannot_be_emptied_or_forged(self) -> None:
        scenario = self._mass_levitation_concentration_scenario()
        metadata = scenario["start"]["start_record"]["authority_metadata"]
        self.assertEqual(
            metadata["concentration_component_ids"],
            [
                "mass_levitation_persistent_elevation",
                "mass_levitation_restrained",
            ],
        )
        self.assertEqual(
            metadata["fall_component_ids"],
            ["mass_levitation_fall"],
        )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            self.engine._start_concentration(
                state=scenario["state"],
                tracker=scenario["tracker"],
                effect=scenario["program"],
                event_id=scenario["activations"][1].event_id,
                replacement_end_event_id=scenario["end_events"][0].event_id,
                schedule=scenario["schedule"],
                selector_membership=scenario["membership"],
                selector_context=scenario["selector_context"],
                invocation_id=scenario["invocation_id"],
                source_actor_id="controller",
                concentration_component_ids=(),
            )
        forged_membership = {
            selector.selector_id: []
            for selector in scenario["program"].selectors
        }
        with self.assertRaisesRegex(
            ControlEngineError,
            "do not match the active compiled slot",
        ):
            self.engine._end_concentration(
                state=scenario["state"],
                tracker=scenario["tracker"],
                effect=scenario["program"],
                schedule=scenario["schedule"],
                selector_membership=forged_membership,
                selector_context=scenario["selector_context"],
                invocation_id=scenario["invocation_id"],
                source_actor_id="controller",
                reason="voluntary_end",
                event_id=scenario["end_events"][0].event_id,
            )
        self.assertEqual(
            len(scenario["state"].active_components("target")),
            2,
        )
        result = self.engine._end_concentration(
            state=scenario["state"],
            tracker=scenario["tracker"],
            effect=scenario["program"],
            schedule=scenario["schedule"],
            selector_membership=scenario["membership"],
            selector_context=scenario["selector_context"],
            invocation_id=scenario["invocation_id"],
            source_actor_id="controller",
            reason="voluntary_end",
            event_id=scenario["end_events"][0].event_id,
        )
        self.assertEqual(len(result["ended_state_instances"]), 2)
        self.assertEqual(scenario["state"].active_components("target"), ())

    def test_explicit_end_derives_and_terminates_compiled_area_state(self) -> None:
        program = self.engine.program("ball_lightning_t2_control")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": "activation"},
                    {"kind": "concentration_end"},
                ]
            },
            target_attack_counts={"target": 0},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        end_event = next(
            event for event in schedule.events
            if event.kind == "concentration_end"
        )
        state = self.engine._new_state()
        for component in program.components:
            _activate_component(state, program, component)
        tracker = ConcentrationTracker(save_bonus=0)
        membership = _single_selector_membership(program, "target")
        start = self.engine._start_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            event_id=activation.event_id,
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
            invocation_id="ball_lightning_invocation",
            source_actor_id="controller",
        )
        metadata = start["start_record"]["authority_metadata"]
        self.assertEqual(metadata["concentration_component_ids"], [])
        self.assertEqual(metadata["area_ids"], ["ball_lightning_sphere"])
        self.assertEqual(
            set(metadata["area_component_ids"]),
            {component.component_id for component in program.components},
        )
        ended = self.engine._end_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            schedule=schedule,
            selector_membership=membership,
            selector_context=_selector_context_for("target"),
            invocation_id="ball_lightning_invocation",
            source_actor_id="controller",
            reason="voluntary_end",
            event_id=end_event.event_id,
        )
        self.assertEqual(len(ended["ended_state_instances"]), 2)
        self.assertEqual(state.active_components("target"), ())
        self.assertEqual(ended["active_components_after"], [])

    def test_duration_reconciliation_ends_only_at_exact_canonical_boundary(
        self,
    ) -> None:
        canonical_program = self.engine.program_for("mass_levitation", 0)
        maximum_duration = {"value": 1, "unit": "round"}
        components = tuple(
            replace(
                component,
                duration=_frozen_map({
                    "kind": "concentration",
                    "maximum_value": 1,
                    "unit": "round",
                }),
            )
            if component.duration.get("kind") == "concentration"
            else component
            for component in canonical_program.components
        )
        concentration = canonical_program.concentration.to_dict()
        concentration["maximum_duration"] = maximum_duration
        program = replace(
            canonical_program,
            components=components,
            concentration=_frozen_map(concentration),
            _component_by_id=MappingProxyType({
                component.component_id: component
                for component in components
            }),
        )
        programs = tuple(
            program if row.effect_id == program.effect_id else row
            for row in self.engine.authority.programs
        )
        authority = replace(
            self.engine.authority,
            programs=programs,
            _program_by_id=MappingProxyType({
                row.effect_id: row for row in programs
            }),
            _program_by_key=MappingProxyType({
                (row.entity_id, row.tier): row for row in programs
            }),
        )
        engine = ControlEngine(
            catalog=self.engine.catalog,
            config=self.engine.config,
            authority=authority,
            targets=self.engine.targets,
            target_supplement_digest=self.engine.target_supplement_digest,
        )
        schedule = engine.schedule(
            "fighter_first_v1",
            ["target"],
            controller_events_by_round={
                1: [
                    {"kind": "activation"},
                    {"kind": "save_opportunity", "target_id": "target"},
                ]
            },
            target_attack_counts={"target": [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        save_event = next(
            event for event in schedule.events
            if event.kind == "save_opportunity"
        )
        membership = _single_selector_membership(program, "target")
        selector_context = _selector_context_for("target")
        state = engine._new_state()
        invocation_id = "one_round_mass_levitation"
        self.engine._apply_resolved_branch(
            state=state,
            effect=canonical_program,
            gate_id="mass_levitation_t0_initial_saves",
            outcome="save_failure",
            target_id="target",
            source_actor_id="controller",
            event_id=save_event.event_id,
            invocation_id=invocation_id,
            schedule=schedule,
            selector_membership=membership,
            selector_context=selector_context,
        )
        tracker = ConcentrationTracker(save_bonus=0)
        before_snapshot = state.snapshot()
        with self.assertRaisesRegex(ControlEngineError, "loaded authority"):
            engine._start_concentration(
                state=state,
                tracker=tracker,
                effect=canonical_program,
                event_id=activation.event_id,
                schedule=schedule,
                selector_membership=membership,
                selector_context=selector_context,
                invocation_id=invocation_id,
                source_actor_id="controller",
            )
        self.assertEqual(state.snapshot(), before_snapshot)
        self.assertEqual(tracker.records, [])
        start = engine._start_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            event_id=activation.event_id,
            schedule=schedule,
            selector_membership=membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id="controller",
        )
        scenario = {
            "program": program,
            "schedule": schedule,
            "membership": membership,
            "selector_context": selector_context,
            "state": state,
            "tracker": tracker,
            "invocation_id": invocation_id,
        }
        boundary = start["start_record"]["authority_metadata"][
            "duration_boundary"
        ]
        self.assertEqual(boundary["start_event_id"], activation.event_id)
        self.assertEqual(
            boundary["duration_anchor_event_id"],
            "r1:controller:turn:start",
        )
        self.assertEqual(boundary["expiry_event_id"], "r2:controller:turn:start")
        common = {
            "state": scenario["state"],
            "tracker": scenario["tracker"],
            "effect": scenario["program"],
            "schedule": scenario["schedule"],
            "selector_membership": scenario["membership"],
            "selector_context": scenario["selector_context"],
            "invocation_id": scenario["invocation_id"],
            "source_actor_id": "controller",
        }
        early = engine._reconcile_concentration_duration(
            **common,
            event_id="r1:controller:turn:end",
        )
        self.assertEqual(early["status"], "before_expiry")
        self.assertFalse(early["ended"])
        self.assertEqual(
            early["expected_expiry_event_id"],
            "r2:controller:turn:start",
        )
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            scenario["program"].effect_id,
        )
        self.assertEqual(
            len(scenario["state"].active_components("target")),
            2,
        )

        ended = engine._reconcile_concentration_duration(
            **common,
            event_id="r2:controller:turn:start",
        )
        self.assertEqual(ended["reason"], "duration_expiry")
        self.assertEqual(ended["event_id"], "r2:controller:turn:start")
        [gate_transition] = ended["concentration_end_gate_transitions"]
        [fall] = gate_transition["instantaneous_contributions"]
        self.assertEqual(fall["primitive_id"], "fall_transition")
        self.assertEqual(scenario["state"].active_components("target"), ())
        self.assertIsNone(scenario["tracker"].active_effect_id)

        assembled = engine._assemble_result_legacy(
            effect=scenario["program"],
            reliability=_reliability(
                scenario["program"].effect_id,
                "target",
            ),
            schedule=scenario["schedule"],
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=scenario["state"],
            concentration_records=(start, start, early, early, ended, ended),
        ).to_dict()
        self.assertEqual(
            [
                (
                    row.get("event_id")
                    or row.get("start_record", {}).get("event_id")
                    or row.get("check_record", {}).get("event_id")
                )
                for row in assembled["concentration_records"]
            ],
            [
                activation.event_id,
                "r1:controller:turn:end",
                "r2:controller:turn:start",
            ],
        )
        for forged in (
            {"kind": "arbitrary_concentration_record"},
            {"kind": "concentration_end", "event_id": ended["event_id"]},
            {**ended, "ended_component_ids": []},
        ):
            with self.assertRaises(ControlEngineError):
                engine._assemble_result_legacy(
                    effect=program,
                    reliability=_reliability(program.effect_id, "target"),
                    schedule=schedule,
                    area_response_convention="fixed_occupancy_v1",
                    displacement_function_id="sqrt_5ft_v1",
                    state=state,
                    concentration_records=(forged,),
                )
        with self.assertRaisesRegex(
            ControlEngineError,
            "no engine-owned concentration authority context",
        ):
            engine._reconcile_concentration_duration(
                **common,
                event_id="r2:controller:turn:start",
            )

    def test_compiled_concentration_duration_is_explicitly_beyond_horizon(
        self,
    ) -> None:
        scenario = self._mass_levitation_concentration_scenario()
        boundary = scenario["start"]["start_record"]["authority_metadata"][
            "duration_boundary"
        ]
        self.assertEqual(boundary["maximum_duration"], {
            "value": 1,
            "unit": "minute",
        })
        self.assertEqual(boundary["duration_rounds"], 10)
        self.assertEqual(boundary["status"], "beyond_horizon")
        self.assertIsNone(boundary["expiry_event_id"])
        with self.assertRaisesRegex(
            ControlEngineError,
            "beyond the maintained timeline horizon",
        ):
            self.engine._end_concentration(
                state=scenario["state"],
                tracker=scenario["tracker"],
                effect=scenario["program"],
                schedule=scenario["schedule"],
                selector_membership=scenario["membership"],
                selector_context=scenario["selector_context"],
                invocation_id=scenario["invocation_id"],
                source_actor_id="controller",
                reason="duration_expiry",
                event_id=scenario["end_events"][0].event_id,
            )
        self.assertEqual(
            scenario["tracker"].active_effect_id,
            scenario["program"].effect_id,
        )
        self.assertEqual(
            len(scenario["state"].active_components("target")),
            2,
        )

    def test_horizontal_displacement_requires_exact_caller_geometry(self) -> None:
        component = next(
            component
            for program in self.engine.authority.programs
            for component in program.components
            if (
                component.magnitude.kind == "forced_movement"
                and component.magnitude.data.get("distance_feet") == 10
                and component.magnitude.data.get("distance_mode") == "exact"
                and component.magnitude.data.get("axis") == "horizontal"
            )
        )
        request = self.engine.displacement_request(
            component=component,
            target_id="target",
        )
        self.assertTrue(request.caller_vector_required)
        magnitude = component.magnitude.data.to_dict()
        self.assertEqual(request.direction, magnitude["direction"])
        self.assertEqual(request.destination, magnitude["destination"])
        self.assertEqual(request.path, magnitude["path"])
        self.assertEqual(request.resolution_order, magnitude["resolution_order"])
        with self.assertRaisesRegex(ControlEngineError, "must supply"):
            self.engine._resolve_displacement(
                component=component,
                target_id="target",
                event_id="fixture:displacement",
                epochs=self.engine._new_displacement_epochs(),
                displacement_function_id="sqrt_5ft_v1",
            )
        with self.assertRaisesRegex(ControlEngineError, "wrong distance"):
            self.engine._resolve_displacement(
                component=component,
                target_id="target",
                event_id="fixture:displacement",
                epochs=self.engine._new_displacement_epochs(),
                displacement_function_id="sqrt_5ft_v1",
                vector_feet=[5, 0, 0],
            )
        resolution = self.engine._resolve_displacement(
            component=component,
            target_id="target",
            event_id="fixture:displacement",
            epochs=self.engine._new_displacement_epochs(),
            displacement_function_id="sqrt_5ft_v1",
            vector_feet=[10, 0, 0],
        )
        self.assertEqual(
            resolution["contribution"]["primitive_id"],
            "forced_displacement",
        )
        self.assertAlmostEqual(
            resolution["contribution"]["quantity"],
            2 ** 0.5,
        )
        self.assertEqual(
            resolution["record"]["function_id"],
            "sqrt_5ft_v1",
        )
        self.assertEqual(
            resolution["contribution"]["event_or_window_id"],
            "fixture:displacement",
        )

    def test_structured_vertical_lift_derives_its_vector(self) -> None:
        component = next(
            component
            for program in self.engine.authority.programs
            for component in program.components
            if (
                component.magnitude.kind == "forced_movement"
                and component.magnitude.data.get("movement_mode") == "lift"
                and component.magnitude.data.get("axis") == "vertical"
            )
        )
        request = self.engine.displacement_request(
            component=component,
            target_id="target",
        )
        self.assertFalse(request.caller_vector_required)
        self.assertEqual(
            request.derived_vector_feet,
            (0.0, 0.0, request.distance_feet),
        )
        resolution = self.engine._resolve_displacement(
            component=component,
            target_id="target",
            event_id="fixture:displacement",
            epochs=self.engine._new_displacement_epochs(),
            displacement_function_id="banded_10ft_v1",
        )
        self.assertGreater(
            resolution["contribution"]["quantity"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
