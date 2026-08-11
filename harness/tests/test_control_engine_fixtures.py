from __future__ import annotations

import inspect
import json
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from harness.control_catalog import (
    DEFAULT_CONTROL_CATALOG,
    CatalogError,
    SenseContext,
    expand_condition,
    query_sense,
    validate_control_catalog,
)
from harness.control_engine import (
    ControlEngine,
    ControlEngineError,
    ENGINE_VERSION,
    _replace_control_engine_result,
)
from harness.control_graph import (
    ProbabilityContext,
    ProbabilityKernelIdentity,
    ReliabilityEvent,
    ReliabilityResult,
    ReliabilityTarget,
    SelectorContext,
    evaluate_reliability,
)
from harness.control_state import ControlState
from harness.control_timeline import (
    ConcentrationTracker,
    DisplacementEpochs,
    TimelineError,
    TimelineSchedule,
    area_entry,
    area_response,
    build_schedule,
    enumerate_prone_movement_operations,
    prone_movement_response,
    repeat_save_survival,
    resolve_expiry_index,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "control_engine_v2.json"
CASE_KEYS = {"id", "category", "invariant", "operation", "input", "expected"}
CATEGORY_COUNTS = {
    "catalog_and_senses": 8,
    "partial_reliability": 7,
    "overlap_and_dominance": 9,
    "prone": 8,
    "timing_and_initiative": 8,
    "repeat_saves": 5,
    "concentration": 6,
    "areas": 10,
    "displacement": 7,
    "weight_and_scope_boundary": 4,
}
EXPECTED_INVARIANTS = (
    "Blinded without alternative sight.",
    "Blinded with Blindsight inside range.",
    "Blinded with Blindsight outside range.",
    "Tremorsense does not cancel Blinded.",
    "Tremorsense rejects airborne detection.",
    "Truesight is absent from the nonvisual input boundary.",
    "Stunned includes Incapacitated exactly once.",
    "Condition inclusion cycles are rejected.",
    "Snow Chains hit-gated no-save Speed 0 plus failed-save Restrained.",
    "Snow Chains successful save retains Speed 0.",
    "Telekinetic Slam T2 success and failure movement remain distinct.",
    "Absolute Zero T2 has a successful-save Speed-0 remainder.",
    "Component marginals and any-candidate probability preserve shared-branch correlation.",
    "Independent targets do not suppress one another.",
    "Condition immunity removes only the immune condition component, not unrelated components.",
    "Restrained plus independent Speed 0 counts mobility denial once.",
    "Longer Slow resumes after shorter independent Speed 0 ends.",
    "Stunned plus direct reaction denial counts reaction denial once.",
    "Active-turn denial suppresses offensive impairment at each scripted attack opportunity.",
    "Stunned automatic Dexterity failure dominates Restrained Dexterity disadvantage.",
    "Blinded plus Restrained does not double-count one attack opportunity.",
    "Reapplication refreshes expiry without immediate duplicate persistent contribution.",
    "Explicit branch replacement overrides generic normalization.",
    "Different targets remain independent at each attack opportunity.",
    "Remain Prone and stand are distinct actor-selected operations.",
    "Explicit standing consumes half current Speed rounded down.",
    "Speed 0 rejects an explicit stand operation without mutation.",
    "Speed returning makes stand available without selecting it automatically.",
    "Each incoming attack opportunity uses the distance-specific Prone consequence.",
    "A missing-distance attack opportunity retains both Prone contexts as unresolved.",
    "Until controller-start-next under `fighter_first_v1`.",
    "Until controller-end-next under `fighter_first_v1`.",
    "The same durations under `target_before_fighter_v1`.",
    "Frozen Ground entry during another creature’s turn expires at that triggering turn’s end.",
    "Frozen Ground target-start exposure expires at that target turn's end.",
    "Initiative order changes a window count where mechanically expected.",
    "Independent target ordering is permutation-invariant.",
    "Mass Levitation T0 repeat-save success ends state and causes fall.",
    "Mass Levitation T1 repeat save uses Disadvantage.",
    "Mass Levitation T2 successful repeat save prevents its damage-context continuation.",
    "Failed repeat saves preserve active state.",
    "Exact three-round survival with a simple hand probability such as 1/2.",
    "Startup Blood Tax does not cause a check.",
    "Later Blood Tax causes the correct DC.",
    "Failed later concentration save ends the effect.",
    "Starting a second concentration effect ends the first.",
    "Incapacitated controller event ends concentration.",
    "Mass Levitation concentration end causes current-position falls.",
    "Frozen Ground route progress is session-owned across movement opportunities.",
    "Speed 0 preserves session-owned route distance until expiry.",
    "A target exits by the shortest supplied legal route.",
    "Ball Lightning membership drives exit after a successful save applies no components.",
    "Frozen Ground’s separately timed failed-save effect does not end merely because the target exits.",
    "Fixed occupancy preserves membership.",
    "Missing distance-to-exit data fails closed.",
    "Moving-area entry frequency respects `moved_area_counts_as_entry`.",
    "10-foot push gives nonzero output under all three functions.",
    "10-foot push followed by 10-foot pull in one epoch does not double-count.",
    "10 then 20 feet in the same direction adds only the incremental maximum.",
    "Perpendicular vectors use net vector distance rather than total path.",
    "A legal self-movement response resets the epoch.",
    "Speed 0 prevents epoch reset.",
    "No cliff, hazard, opportunity attack, falling damage, or ally-combo value appears.",
    "Engine result contains no final primitive weights.",
    "Engine result contains no combined Control Value.",
    "Engine result contains no HOT/IDEAL/COLD/SENSITIVE field.",
    "Engine performs no action, tier, target, resource, or comparator optimization.",
    "Both initiative conventions put the first movement response after start processing and before active and attack windows.",
    "Explicit standing and route progress share one pre-attack movement budget.",
    "Frozen Ground can be exited on the immediate legal movement response without changing Speed.",
    "Ball Lightning while-in-area consequences end on the immediate legal exit response.",
    "Speed 0 preserves Prone and area exposure at the pre-attack movement response.",
)


def exact_fraction(value: Any) -> Fraction:
    if isinstance(value, str):
        return Fraction(value)
    if isinstance(value, Mapping):
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    return Fraction(value)


def path_value(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, (list, tuple)) else current[part]
    return current


def component_definition(row: Mapping[str, Any]) -> dict[str, Any]:
    component_id = str(row["component_id"])
    return {
        "component_id": component_id,
        "target_selector_ids": ["target"],
        "magnitude": deepcopy(row["magnitude"]),
        "duration": deepcopy(
            row.get(
                "duration",
                {
                    "kind": "relative",
                    "owner": "controller",
                    "anchor": "end_turn",
                    "offset_turns": 1,
                },
            )
        ),
        "cadence": {"apply": [{"kind": "hit"}], "repeat": [], "end": []},
        "stacking": {
            "key": row.get("stacking_key", component_id),
            "mode": row.get("stacking_mode", "nonstacking"),
            "refresh": row.get("refresh", "duration"),
            "dominates_component_ids": list(row.get("dominates_component_ids", [])),
        },
    }


class FixtureKernel:
    identity = ProbabilityKernelIdentity.create(
        "test-only.control-engine-fixture",
        "1.0.0",
        {"fixture": "caller-supplied exact outcome table"},
        test_only=True,
    )

    def __init__(self, outcomes: Mapping[str, Mapping[str, Any]]) -> None:
        self.outcomes = {
            gate_id: {
                outcome: exact_fraction(probability)
                for outcome, probability in distribution.items()
            }
            for gate_id, distribution in outcomes.items()
        }

    def outcome_probabilities(
        self,
        gate: Any,
        target: ReliabilityTarget | None,
        context: ProbabilityContext,
    ) -> Mapping[str, Fraction]:
        del target, context
        try:
            return self.outcomes[gate.gate_id]
        except KeyError as error:
            raise AssertionError(f"Fixture omitted probabilities for {gate.gate_id}") from error


class ControlEngineFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.cases = cls.fixture["cases"]
        cls.engine = ControlEngine.load()
        cls.catalog = cls.engine.catalog
        cls.compiled = cls.engine.authority

    def test_fixture_contract_has_exact_numbered_named_invariants(self) -> None:
        self.assertEqual(set(self.fixture), {"format_version", "engine_version", "cases"})
        self.assertEqual(self.fixture["format_version"], 1)
        self.assertEqual(self.fixture["engine_version"], ENGINE_VERSION)
        self.assertEqual(len(self.cases), 72)
        self.assertEqual([case["id"] for case in self.cases], list(range(1, 73)))
        self.assertEqual(
            tuple(case["invariant"] for case in self.cases),
            EXPECTED_INVARIANTS,
        )
        self.assertEqual(len(set(EXPECTED_INVARIANTS)), 72)
        self.assertTrue(all(set(case) == CASE_KEYS for case in self.cases))
        self.assertTrue(all(isinstance(case["input"], dict) for case in self.cases))
        self.assertTrue(all(isinstance(case["expected"], dict) for case in self.cases))
        self.assertEqual(
            Counter(case["category"] for case in self.cases),
            Counter(CATEGORY_COUNTS),
        )

        serialized = json.dumps(self.fixture, sort_keys=True)
        for convention in ("fighter_first_v1", "target_before_fighter_v1"):
            self.assertIn(convention, serialized)
        for convention in ("shortest_route_v1", "fixed_occupancy_v1"):
            self.assertIn(convention, serialized)
        for function_id in ("sqrt_5ft_v1", "log2_5ft_v1", "banded_10ft_v1"):
            self.assertIn(function_id, serialized)

    def test_every_fixture_case_executes(self) -> None:
        dispatch = {
            "sense_query": self.run_sense_query,
            "condition_sense": self.run_condition_sense,
            "sense_reject": self.run_sense_reject,
            "condition_expansion": self.run_condition_expansion,
            "catalog_cycle": self.run_catalog_cycle,
            "reliability": self.run_reliability,
            "graph_branches": self.run_graph_branches,
            "graph_gate": self.run_graph_gate,
            "state_independence": self.run_state_independence,
            "state_window": self.run_state_window,
            "state_speed_resume": self.run_state_speed_resume,
            "state_refresh": self.run_state_refresh,
            "state_replacement": self.run_state_replacement,
            "prone_response": self.run_prone_response,
            "prone_sequence": self.run_prone_sequence,
            "prone_context": self.run_prone_context,
            "timeline_expiry": self.run_timeline_expiry,
            "schedule_order": self.run_schedule_order,
            "schedule_target_turn_order": self.run_schedule_target_turn_order,
            "schedule_permutation": self.run_schedule_permutation,
            "levitation_repeat": self.run_levitation_repeat,
            "repeat_survival": self.run_repeat_survival,
            "concentration_scenario": self.run_concentration_scenario,
            "session_area_route": self.run_session_area_route,
            "session_area_membership": self.run_session_area_membership,
            "area_response": self.run_area_response,
            "area_error": self.run_area_error,
            "area_entry": self.run_area_entry,
            "displacement": self.run_displacement,
            "displacement_scope": self.run_displacement_scope,
            "result_boundary": self.run_result_boundary,
            "signature_boundary": self.run_signature_boundary,
        }
        self.assertEqual(
            set(dispatch),
            {case["operation"] for case in self.cases},
        )
        for case in self.cases:
            with self.subTest(case_id=case["id"], invariant=case["invariant"]):
                dispatch[case["operation"]](case)

    def sense_result(self, inputs: Mapping[str, Any]) -> Any:
        return query_sense(
            inputs["nonvisual_senses"],
            context=SenseContext(**inputs["context"]),
        )

    def run_condition_sense(self, case: Mapping[str, Any]) -> None:
        result = self.sense_result(case["input"])
        expected = case["expected"]
        self.assertEqual(result.alternative_sight, expected["alternative_sight"])
        self.assertEqual(
            [spec.primitive_id for spec in expand_condition(self.catalog, case["input"]["condition_id"])],
            expected["primitive_ids"],
        )

    def run_sense_query(self, case: Mapping[str, Any]) -> None:
        result = self.sense_result(case["input"])
        expected = case["expected"]
        for name in ("alternative_sight", "location_detection"):
            if name in expected:
                self.assertEqual(getattr(result, name), expected[name])
        if "evidence_contains" in expected:
            self.assertIn(expected["evidence_contains"], result.alternative_sight_evidence)
        if "location_evidence_contains" in expected:
            self.assertIn(
                expected["location_evidence_contains"],
                result.location_detection_evidence,
            )

    def run_sense_reject(self, case: Mapping[str, Any]) -> None:
        with self.assertRaises(CatalogError) as caught:
            self.sense_result(case["input"])
        self.assertIn(case["expected"]["error_contains"], str(caught.exception))

    def run_condition_expansion(self, case: Mapping[str, Any]) -> None:
        condition_id = case["input"]["condition_id"]
        condition = self.catalog.conditions[condition_id]
        specs = expand_condition(self.catalog, condition_id)
        expected = case["expected"]
        self.assertEqual(list(condition.includes), expected["includes"])
        counts = Counter(spec.primitive_id for spec in specs)
        for primitive_id, count in expected["primitive_counts"].items():
            self.assertEqual(counts[primitive_id], count)
        for primitive_id in expected["absent_primitive_ids"]:
            self.assertNotIn(primitive_id, counts)

    def run_catalog_cycle(self, case: Mapping[str, Any]) -> None:
        value = json.loads(DEFAULT_CONTROL_CATALOG.read_text(encoding="utf-8"))
        by_id = {row["condition_id"]: row for row in value["conditions"]}
        for source, target in case["input"]["edges"]:
            by_id[source]["includes"] = [target]
        with self.assertRaises(CatalogError) as caught:
            validate_control_catalog(value)
        self.assertIn(case["expected"]["error_contains"], str(caught.exception))

    def reliability_result(self, inputs: Mapping[str, Any]) -> ReliabilityResult:
        effect = self.compiled.program(inputs["effect_id"])
        target_ids = tuple(inputs.get("target_ids", ["target"]))
        targets = [
            ReliabilityTarget(
                target_id,
                15,
                {
                    "strength": 0,
                    "dexterity": 0,
                    "constitution": 0,
                    "intelligence": 0,
                    "wisdom": 0,
                    "charisma": 0,
                },
                condition_immunities=inputs.get("condition_immunities", []),
            )
            for target_id in target_ids
        ]
        membership = {
            selector.selector_id: list(target_ids)
            for selector in effect.selectors
        }
        return evaluate_reliability(
            effect,
            targets=targets,
            selector_membership=membership,
            kernel=FixtureKernel(inputs["outcomes"]),
            context=ProbabilityContext(
                attack_bonus=5,
                save_dc=15,
                discipline_signature="strength",
            ),
            candidate_component_ids=self.engine.candidate_component_ids(effect),
        )

    def run_reliability(self, case: Mapping[str, Any]) -> None:
        result = self.reliability_result(case["input"])
        expected = case["expected"]
        for component_id, probability in expected.get("ever_applied", {}).items():
            self.assertEqual(
                result.component(component_id, "target").ever_applied,
                exact_fraction(probability),
            )
        if "any_candidate_probability" in expected:
            self.assertEqual(
                result.any_candidate_probability,
                exact_fraction(expected["any_candidate_probability"]),
            )
        if "final_world_count" in expected:
            self.assertEqual(result.final_world_count, expected["final_world_count"])
        if "immunity_component_ids" in expected:
            self.assertEqual(
                sorted({row.component_id for row in result.immunity_suppressions}),
                expected["immunity_component_ids"],
            )
        if "immunity_conditions" in expected:
            self.assertEqual(
                sorted({row.condition for row in result.immunity_suppressions}),
                expected["immunity_conditions"],
            )

    def run_graph_branches(self, case: Mapping[str, Any]) -> None:
        effect = self.compiled.program(case["input"]["effect_id"])
        gate = effect.gate(case["input"]["gate_id"])
        actual = {
            branch.outcome: list(branch.applies)
            for branch in gate.branches
        }
        self.assertEqual(actual, case["expected"]["applies_by_outcome"])
        first, second = case["expected"]["distinct_component_ids"]
        self.assertNotEqual(effect.component(first).magnitude.data, effect.component(second).magnitude.data)

    def run_graph_gate(self, case: Mapping[str, Any]) -> None:
        gate = self.compiled.program(case["input"]["effect_id"]).gate(
            case["input"]["gate_id"]
        )
        for field_name, expected in case["expected"].items():
            self.assertEqual(getattr(gate, field_name), expected)

    def apply_components(
        self,
        state: ControlState,
        rows: list[Mapping[str, Any]],
    ) -> None:
        for index, row in enumerate(rows):
            state.apply_component(
                effect_id=row.get("effect_id", "fixture_effect"),
                component=component_definition(row),
                target_id=row.get("target_id", "target"),
                source_actor_id="controller",
                event_id=row.get("event_id", f"apply_{index}"),
                invocation_id=row.get("invocation_id", f"invocation_{index}"),
                expiry_event_id=row.get("expiry_event_id", "expiry"),
                condition_immunities=set(row.get("condition_immunities", [])),
            )

    def run_state_independence(self, case: Mapping[str, Any]) -> None:
        state = ControlState()
        rows = [
            {
                "component_id": "component",
                "target_id": target_id,
                "magnitude": case["input"]["magnitude"],
                "invocation_id": f"invocation_{index}",
            }
            for index, target_id in enumerate(case["input"]["target_ids"])
        ]
        self.apply_components(state, rows)
        results = [
            state.normalize_for_window(
                target_id=target_id,
                window_id=f"window_{target_id}",
                window_kind=case["input"]["window_kind"],
            )
            for target_id in case["input"]["target_ids"]
        ]
        expected = case["expected"]
        for target_id, result in zip(case["input"]["target_ids"], results, strict=True):
            matches = [
                contribution
                for contribution in result.contributions
                if contribution.primitive_id == expected["primitive_id"]
            ]
            self.assertEqual(len(matches), expected["contribution_count_per_target"])
            self.assertTrue(all(item.target_id == target_id for item in matches))
        self.assertEqual(
            sum(len(result.suppressions) for result in results),
            expected["suppression_count"],
        )

    def run_state_window(self, case: Mapping[str, Any]) -> None:
        state = ControlState()
        self.apply_components(state, case["input"]["components"])
        window = case["input"]["window"]
        result = state.normalize_for_window(
            target_id=window["target_id"],
            window_id=window["window_id"],
            window_kind=window["window_kind"],
            context=window.get("context"),
        )
        expected = case["expected"]
        counts = Counter(item.primitive_id for item in result.contributions)
        for primitive_id, count in expected.get("contribution_counts", {}).items():
            self.assertEqual(counts[primitive_id], count)
        contribution_ids = {item.primitive_id for item in result.contributions}
        for primitive_id in expected.get("contribution_ids_contains", []):
            self.assertIn(primitive_id, contribution_ids)
        for primitive_id in expected.get("contribution_ids_absent", []):
            self.assertNotIn(primitive_id, contribution_ids)
        for primitive_id, quantity in expected.get("quantities", {}).items():
            matches = [item for item in result.contributions if item.primitive_id == primitive_id]
            self.assertEqual([item.quantity for item in matches], [quantity])
        for primitive_id, source_ids in expected.get("source_component_ids", {}).items():
            match = next(
                item for item in result.contributions if item.primitive_id == primitive_id
            )
            self.assertEqual(sorted(match.source_component_ids), source_ids)
        reasons = {row.reason for row in result.suppressions}
        for reason in expected.get("suppression_reasons_contains", []):
            self.assertIn(reason, reasons)

    def run_state_speed_resume(self, case: Mapping[str, Any]) -> None:
        state = ControlState()
        self.apply_components(state, case["input"]["components"])
        target_id = case["input"]["target_id"]
        base_speeds = case["input"]["base_speeds"]
        before = state.effective_speeds(target_id, base_speeds)
        state.expire(case["input"]["expire_event_id"])
        after = state.effective_speeds(target_id, base_speeds)
        self.assertEqual(
            {key: before[key] for key in case["expected"]["before"]},
            case["expected"]["before"],
        )
        self.assertEqual(
            {key: after[key] for key in case["expected"]["after"]},
            case["expected"]["after"],
        )
        self.assertEqual(
            [row.component_id for row in state.active_components(target_id)],
            case["expected"]["active_component_ids"],
        )

    def run_state_refresh(self, case: Mapping[str, Any]) -> None:
        state = ControlState()
        row = case["input"]["component"]
        first = {**row, "expiry_event_id": case["input"]["first_expiry_event_id"]}
        second = {
            **row,
            "expiry_event_id": case["input"]["second_expiry_event_id"],
            "event_id": "reapply",
            "invocation_id": "invocation_2",
        }
        self.apply_components(state, [first])
        self.apply_components(state, [second])
        expected = case["expected"]
        active = state.active_components("target")
        self.assertEqual(len(active), expected["active_count"])
        self.assertEqual(active[0].expiry_event_id, expected["expiry_event_id"])
        self.assertEqual(
            state.refresh_records[0]["immediate_persistent_contribution"],
            expected["immediate_persistent_contribution"],
        )

    def run_state_replacement(self, case: Mapping[str, Any]) -> None:
        state = ControlState()
        weak = case["input"]["weak_component"]
        strong = case["input"]["strong_component"]
        self.apply_components(state, [weak])
        definitions = {
            weak["component_id"]: component_definition(weak),
            strong["component_id"]: component_definition(strong),
        }
        state.apply_branch(
            effect_id="fixture_effect",
            branch=case["input"]["branch"],
            components_by_id=definitions,
            target_id="target",
            source_actor_id="controller",
            event_id="replacement",
            invocation_id="invocation_replacement",
        )
        self.assertEqual(
            [row.component_id for row in state.active_components("target")],
            case["expected"]["active_component_ids"],
        )
        self.assertEqual(
            state.replacement_records[0]["reason"],
            case["expected"]["replacement_reason"],
        )

    def run_prone_response(self, case: Mapping[str, Any]) -> None:
        inputs = deepcopy(case["input"])
        expected = case["expected"]
        selected_kinds = inputs.pop("selected_kinds", None)
        if selected_kinds is not None:
            operations = enumerate_prone_movement_operations(**inputs)
            self.assertEqual(
                [operation["kind"] for operation in operations[:len(selected_kinds)]],
                expected["enumerated_kinds_prefix"],
            )
            by_kind = {operation["kind"]: operation for operation in operations}
            for kind in selected_kinds:
                operation = by_kind[kind]
                result = prone_movement_response(
                    **inputs,
                    kind=operation["kind"],
                    distance_feet=operation.get("distance_feet"),
                )
                for key, value in expected["responses"][kind].items():
                    self.assertEqual(result[key], value)
            return
        error_contains = expected.get("error_contains")
        if error_contains is not None:
            before = deepcopy(inputs)
            with self.assertRaisesRegex(TimelineError, error_contains):
                prone_movement_response(**inputs)
            self.assertEqual(inputs, before)
            return
        result = prone_movement_response(**inputs)
        for key, value in expected.items():
            self.assertEqual(result[key], value)

    def run_prone_sequence(self, case: Mapping[str, Any]) -> None:
        prone = True
        rows = []
        stand_available = []
        for speed, selected_kind in zip(
            case["input"]["speeds_ft"],
            case["input"]["selected_kinds"],
            strict=True,
        ):
            operations = enumerate_prone_movement_operations(
                target_id=case["input"]["target_id"],
                actor_id=case["input"]["actor_id"],
                prone=prone,
                current_speed_ft=speed,
                movement_budget_ft=speed,
            )
            stand_available.append(any(row["kind"] == "stand" for row in operations))
            selected = next(row for row in operations if row["kind"] == selected_kind)
            row = prone_movement_response(
                target_id=case["input"]["target_id"],
                actor_id=case["input"]["actor_id"],
                kind=selected["kind"],
                prone=prone,
                current_speed_ft=speed,
                movement_budget_ft=speed,
            )
            rows.append(row)
            prone = row["prone_after"]
        self.assertEqual(
            [row["stood"] for row in rows],
            case["expected"]["stood_by_opportunity"],
        )
        self.assertEqual(
            [row["prone_after"] for row in rows],
            case["expected"]["prone_after_by_opportunity"],
        )
        self.assertEqual(
            stand_available,
            case["expected"]["stand_available_by_opportunity"],
        )

    def prone_contributions(self, distance: int | None) -> tuple[Any, ...]:
        state = ControlState()
        self.apply_components(
            state,
            [{"component_id": "prone", "magnitude": {"kind": "condition", "condition": "prone"}}],
        )
        context: dict[str, Any] = {
            "target_airborne": False,
            "target_can_hover": False,
        }
        if distance is not None:
            context["attacker_distance_ft"] = distance
        return state.normalize_for_window(
            target_id="target",
            window_id=f"incoming_{distance}",
            window_kind="incoming_attack_opportunity",
            context=context,
        ).contributions

    def run_prone_context(self, case: Mapping[str, Any]) -> None:
        expected = case["expected"]
        rows = {
            distance: self.prone_contributions(distance)
            for distance in case["input"]["distances_ft"]
        }
        if "primitive_by_distance" in expected:
            for distance, primitive_id in expected["primitive_by_distance"].items():
                contributions = rows[int(distance)]
                self.assertEqual([item.primitive_id for item in contributions], [primitive_id])
                self.assertEqual(
                    [item.disposition for item in contributions],
                    [expected["disposition_by_distance"][distance]],
                )
                self.assertEqual(
                    [item.unit for item in contributions],
                    [expected["unit_by_distance"][distance]],
                )
        else:
            contributions = rows[None]
            self.assertEqual(
                [item.primitive_id for item in contributions],
                expected["primitive_ids"],
            )
            self.assertEqual(
                sorted({item.disposition for item in contributions}),
                sorted(expected["dispositions"]),
            )
            self.assertEqual(
                sorted({item.unit for item in contributions}),
                sorted(expected["units"]),
            )
            if expected["unresolved_context"]:
                self.assertTrue(
                    all(item.context.get("unresolved_requirements") for item in contributions)
                )

    def fixture_schedule(self, inputs: Mapping[str, Any]) -> TimelineSchedule:
        target_ids = inputs.get("target_ids", ["target"])
        return build_schedule(
            inputs["convention"],
            target_ids,
            controller_events_by_round=inputs.get("controller_events_by_round"),
            target_events_by_round=inputs.get("target_events_by_round"),
            target_attack_counts=inputs.get(
                "attack_counts",
                {target_id: 0 for target_id in target_ids},
            ),
        )

    def run_timeline_expiry(self, case: Mapping[str, Any]) -> None:
        schedule = self.fixture_schedule(case["input"])
        duration_component = case["input"].get("compiled_duration_component")
        if duration_component is not None:
            program = self.engine.program_for(
                duration_component["mastery_id"],
                duration_component["tier"],
            )
            durations = [
                program.component(duration_component["component_id"]).duration.to_dict()
            ]
        else:
            durations = case["input"].get(
                "durations",
                [case["input"].get("duration")],
            )
        expiry_ids = []
        for duration in durations:
            index = resolve_expiry_index(
                schedule,
                case["input"]["applied_event_id"],
                duration,
                target_id=case["input"].get("target_id"),
            )
            self.assertIsNotNone(index)
            expiry_ids.append(schedule.events[index].event_id)
        if "expiry_event_id" in case["expected"]:
            self.assertEqual(expiry_ids, [case["expected"]["expiry_event_id"]])
        else:
            self.assertEqual(expiry_ids, case["expected"]["expiry_event_ids"])

    def run_schedule_order(self, case: Mapping[str, Any]) -> None:
        actual = {}
        for convention in case["input"]["conventions"]:
            schedule = build_schedule(
                convention,
                ["target"],
                controller_events_by_round=case["input"]["controller_events_by_round"],
                target_attack_counts={"target": 0},
            )
            activation_sequence = schedule.event(case["input"]["activation_event_id"]).sequence
            actual[convention] = sum(
                event.kind == case["input"]["window_kind"]
                and event.sequence > activation_sequence
                for event in schedule.events
            )
        self.assertEqual(actual, case["expected"]["covered_target_window_count"])

    def run_schedule_target_turn_order(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        expected = case["expected"]
        for convention in inputs["conventions"]:
            schedule = build_schedule(
                convention,
                ["target"],
                target_events_by_round=inputs["target_events_by_round"],
                target_attack_counts=inputs["attack_counts"],
            )
            first_turn = [
                event
                for event in schedule.events
                if event.turn_id == "r1:target:target:turn"
            ]
            self.assertEqual(
                [event.kind for event in first_turn],
                expected["first_turn_kinds"],
            )
            if expected["reaction_opens_at_turn_start"]:
                self.assertEqual(first_turn[0].kind, "target_turn_start")
                self.assertEqual(first_turn[1].kind, "reaction_window")
                self.assertEqual(
                    first_turn[0].reaction_interval_id,
                    first_turn[1].reaction_interval_id,
                )
            self.assertEqual(
                sum(
                    event.kind == "target_movement_opportunity"
                    for event in first_turn
                ),
                expected["movement_opportunities_per_turn"],
            )
            movement_index = next(
                index
                for index, event in enumerate(first_turn)
                if event.kind == "target_movement_opportunity"
            )
            active_index = next(
                index
                for index, event in enumerate(first_turn)
                if event.kind == "target_active_turn_opportunity"
            )
            attack_indices = [
                index
                for index, event in enumerate(first_turn)
                if event.kind == "target_attack_opportunity"
            ]
            self.assertLess(movement_index, active_index)
            self.assertTrue(all(movement_index < index for index in attack_indices))

    def run_schedule_permutation(self, case: Mapping[str, Any]) -> None:
        schedules = [
            build_schedule(
                case["input"]["convention"],
                order,
                target_attack_counts=case["input"]["attack_counts"],
            )
            for order in case["input"]["target_orders"]
        ]
        if case["expected"]["caller_orders_preserved"]:
            self.assertEqual(
                [list(schedule.target_ids) for schedule in schedules],
                case["input"]["target_orders"],
            )
        for target_id in case["input"]["attack_counts"]:
            traces = []
            for schedule in schedules:
                trace = []
                for event in schedule.events:
                    if event.target_id != target_id:
                        continue
                    row = event.to_dict()
                    row.pop("sequence")
                    trace.append(row)
                traces.append(trace)
            self.assertEqual(traces[0], traces[1])

    def run_levitation_repeat(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        effect = self.compiled.program(inputs["effect_id"])
        target = ReliabilityTarget(
            "target",
            15,
            {
                "strength": 0,
                "dexterity": 0,
                "constitution": 0,
                "intelligence": 0,
                "wisdom": 0,
                "charisma": 0,
            },
        )
        self.assertIn(inputs["initial_gate_id"], effect.root_gate_ids)
        repeat_gate = effect.gate(inputs["repeat_gate_id"])
        result = evaluate_reliability(
            effect,
            targets=[target],
            selector_membership={
                selector.selector_id: ["target"]
                for selector in effect.selectors
            },
            selector_context=SelectorContext(
                controller_can_see_by_target={"target": True},
                target_size_by_id={"target": "medium"},
            ),
            kernel=FixtureKernel(inputs["outcomes"]),
            context=ProbabilityContext(save_dc=15, discipline_signature="strength"),
            events=[
                ReliabilityEvent.create(
                    "repeat_1",
                    repeat_gate.trigger,
                    target_ids=["target"],
                    gate_ids=[repeat_gate.gate_id],
                    window_id="repeat_1",
                )
            ],
            candidate_component_ids=self.engine.candidate_component_ids(effect),
        )
        expected = case["expected"]
        elevation = result.component("mass_levitation_persistent_elevation", "target")
        restrained = result.component("mass_levitation_restrained", "target")
        fall = result.component("mass_levitation_fall", "target")
        elevation_windows = dict(elevation.active_by_window)
        restrained_windows = dict(restrained.active_by_window)
        if "active_elevation_at_repeat" in expected:
            self.assertEqual(
                elevation_windows["repeat_1"],
                exact_fraction(expected["active_elevation_at_repeat"]),
            )
        if "active_restrained_at_repeat" in expected:
            self.assertEqual(
                restrained_windows["repeat_1"],
                exact_fraction(expected["active_restrained_at_repeat"]),
            )
        self.assertEqual(
            fall.ever_applied,
            exact_fraction(expected["fall_ever_applied"]),
        )
        if "repeat_survival" in expected:
            survival = sum(
                row.probability
                for row in result.repeat_survival
                if row.gate_id == inputs["repeat_gate_id"]
            )
            self.assertEqual(survival, exact_fraction(expected["repeat_survival"]))
        if "damage_gate_probability" in expected:
            damage_probability = sum(
                row.probability
                for row in result.gate_probabilities
                if row.gate_id == inputs["damage_gate_id"]
            )
            self.assertEqual(
                damage_probability,
                exact_fraction(expected["damage_gate_probability"]),
            )

    def run_repeat_survival(self, case: Mapping[str, Any]) -> None:
        result = repeat_save_survival(
            exact_fraction(case["input"]["failure_probability"]),
            case["input"]["repeat_count"],
        )
        self.assertEqual(
            exact_fraction(result["survival_probability"]),
            exact_fraction(case["expected"]["survival_probability"]),
        )
        self.assertEqual(
            [exact_fraction(row["active_after"]) for row in result["records"]],
            [exact_fraction(value) for value in case["expected"]["active_after_each"]],
        )

    def run_concentration_scenario(self, case: Mapping[str, Any]) -> None:
        if "compiled_effect" in case["input"]:
            self.run_compiled_concentration_scenario(case)
            return
        tracker = ConcentrationTracker(
            owner_actor_id=case["input"]["owner_actor_id"],
            save_bonus=case["input"]["save_bonus"],
        )
        for raw in case["input"]["steps"]:
            step = deepcopy(raw)
            kind = step.pop("kind")
            if kind == "start":
                tracker.start(**step)
            elif kind == "check":
                if "success_probability" in step:
                    step["success_probability"] = exact_fraction(step["success_probability"])
                tracker.check(**step)
            elif kind == "end":
                tracker.end(**step)
            else:  # pragma: no cover - fixture contract closes this
                self.fail(f"Unknown concentration step {kind}")
        result = tracker.to_dict()
        expected = case["expected"]
        self.assertEqual(result["owner_actor_id"], expected["owner_actor_id"])
        self.assertEqual(result["active_effect_id"], expected["active_effect_id"])
        if "record_kinds" in expected:
            self.assertEqual(
                [record["kind"] for record in result["records"]],
                expected["record_kinds"],
            )
        for path, value in expected.get("record_paths", {}).items():
            self.assertEqual(path_value(result, path), value)
        json.dumps(result, sort_keys=True, allow_nan=False)
    def run_compiled_concentration_scenario(
        self,
        case: Mapping[str, Any],
    ) -> None:
        inputs = case["input"]
        compiled_effect = inputs["compiled_effect"]
        program = self.engine.program_for(
            compiled_effect["mastery_id"],
            compiled_effect["tier"],
        )
        target_ids = tuple(inputs["target_ids"])
        controller_events = [{"kind": "activation"}]
        controller_events.extend(
            {"kind": "save_opportunity", "target_id": target_id}
            for target_id in target_ids
        )
        controller_events.append({"kind": "concentration_end"})
        if "replacement_effect" in inputs:
            controller_events.append({"kind": "activation"})
        schedule = self.engine.schedule(
            "fighter_first_v1",
            target_ids,
            controller_events_by_round={1: controller_events},
            target_attack_counts={
                target_id: [0, 0, 0] for target_id in target_ids
            },
        )
        activation_events = [
            event for event in schedule.events if event.kind == "activation"
        ]
        end_event = next(
            event
            for event in schedule.events
            if event.kind == "concentration_end"
        )
        save_events = {
            event.target_id: event
            for event in schedule.events
            if event.kind == "save_opportunity"
        }
        selector_membership = {
            selector.selector_id: list(target_ids)
            for selector in program.selectors
        }
        selector_context = SelectorContext(
            controller_can_see_by_target={
                target_id: True for target_id in target_ids
            },
            target_size_by_id={
                target_id: "medium" for target_id in target_ids
            },
            controller_proficiency_bonus=6,
        )
        state = self.engine._new_state()
        invocation_id = f"fixture:{case['id']}:invocation"
        for target_id in target_ids:
            self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id=f"mass_levitation_t{compiled_effect['tier']}_initial_saves",
                outcome="save_failure",
                target_id=target_id,
                source_actor_id=inputs["owner_actor_id"],
                event_id=save_events[target_id].event_id,
                invocation_id=invocation_id,
                schedule=schedule,
                selector_membership=selector_membership,
                selector_context=selector_context,
            )
        tracker = ConcentrationTracker(
            owner_actor_id=inputs["owner_actor_id"],
            save_bonus=inputs["save_bonus"],
        )
        expected = case["expected"]
        self.assertEqual(tracker.owner_actor_id, expected["owner_actor_id"])
        start = self.engine._start_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            event_id=activation_events[0].event_id,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=inputs["owner_actor_id"],
        )
        replacement_effect = inputs.get("replacement_effect")
        if replacement_effect is not None:
            replacement_program = self.engine.program_for(
                replacement_effect["mastery_id"],
                replacement_effect["tier"],
            )
            replacement_membership = {
                selector.selector_id: list(target_ids)
                for selector in replacement_program.selectors
            }
            replacement = self.engine._start_concentration(
                state=state,
                tracker=tracker,
                effect=replacement_program,
                event_id=activation_events[1].event_id,
                replacement_end_event_id=end_event.event_id,
                schedule=schedule,
                selector_membership=replacement_membership,
                selector_context=selector_context,
                invocation_id=f"{invocation_id}:replacement",
                source_actor_id=inputs["owner_actor_id"],
            )
            self.assertEqual(
                tracker.active_effect_id,
                expected["active_effect_id"],
            )
            self.assertEqual(
                [row["kind"] for row in replacement["tracker_records"]],
                expected["record_kinds"],
            )
            [end_transition] = replacement["applied_end_transitions"]
            self.assertEqual(
                end_transition["reason"],
                expected["replacement_reason"],
            )
            self.assertTrue(
                all(
                    not state.active_components(target_id)
                    for target_id in target_ids
                )
            )
            json.dumps(
                {"start": start, "replacement": replacement},
                sort_keys=True,
                allow_nan=False,
            )
            return
        ended = self.engine._end_concentration(
            state=state,
            tracker=tracker,
            effect=program,
            schedule=schedule,
            selector_membership=selector_membership,
            selector_context=selector_context,
            invocation_id=invocation_id,
            source_actor_id=inputs["owner_actor_id"],
            reason=inputs["end_reason"],
            event_id=end_event.event_id,
        )
        self.assertIsNone(tracker.active_effect_id)
        self.assertEqual(ended["reason"], inputs["end_reason"])
        self.assertEqual(
            start["start_record"]["authority_metadata"][
                "concentration_component_ids"
            ],
            expected["concentration_component_ids"],
        )
        self.assertEqual(
            start["start_record"]["authority_metadata"]["fall_component_ids"],
            expected["fall_component_ids"],
        )
        self.assertEqual(
            [row["target_id"] for row in ended["fall_transitions"]],
            expected["fall_target_ids"],
        )
        for transition in ended["fall_transitions"]:
            self.assertEqual(transition["origin"], expected["fall_origin"])
            self.assertEqual(transition["damage"], expected["fall_damage"])
            self.assertEqual(
                transition["altitude_ft"],
                expected["fall_altitude_ft"],
            )
        self.assertTrue(
            all(not state.active_components(target_id) for target_id in target_ids)
        )
        json.dumps(
            {"start": start, "end": ended},
            sort_keys=True,
            allow_nan=False,
        )


    def run_compiled_area_lifecycle(
        self,
        *,
        case: Mapping[str, Any],
        params: Mapping[str, Any],
        program: Any,
        convention: str,
        lifecycle: Mapping[str, Any],
    ) -> dict[str, Any]:
        target_id = params["target_id"]
        target_events = [{"kind": "entry", "phase": "before_movement"}]
        if lifecycle["kind"] == "typed_target_exit":
            target_events.append({"kind": "exit", "phase": "after_movement"})
        elif lifecycle["kind"] != "speed_zero_expiry_then_exit":
            self.fail(f"Unknown compiled area lifecycle {lifecycle['kind']!r}")
        schedule = self.engine.schedule(
            "fighter_first_v1",
            [target_id],
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_events_by_round={target_id: {1: target_events}},
            target_attack_counts={target_id: [0, 0, 0]},
        )
        activation_event = next(
            event for event in schedule.events if event.kind == "activation"
        )
        entry_event = next(
            event
            for event in schedule.events
            if event.kind == "entry" and event.target_id == target_id
        )
        selector_membership = {
            selector.selector_id: [target_id]
            for selector in program.selectors
        }
        selector_context = SelectorContext(
            controller_can_see_by_target={target_id: True},
            target_size_by_id={target_id: "medium"},
            controller_proficiency_bonus=6,
        )
        state = self.engine._new_state()
        invocation_id = f"fixture:{case['id']}:invocation"

        def apply_branch(
            specification: Mapping[str, Any],
            event_id: str,
        ) -> dict[str, Any]:
            return self.engine._apply_resolved_branch(
                state=state,
                effect=program,
                gate_id=specification["gate_id"],
                outcome=specification["outcome"],
                target_id=target_id,
                source_actor_id="controller",
                event_id=event_id,
                invocation_id=invocation_id,
                schedule=schedule,
                selector_membership=selector_membership,
                selector_context=selector_context,
            )

        activation_transition = apply_branch(
            lifecycle["activation"],
            activation_event.event_id,
        )
        speed_zero_transition = apply_branch(
            lifecycle["speed_zero"],
            entry_event.event_id,
        )
        [speed_zero_component_id] = speed_zero_transition[
            "filtered_branch"
        ]["applies"]
        speed_zero_state = next(
            component
            for component in speed_zero_transition["active_components_after"]
            if component["component_id"] == speed_zero_component_id
        )
        expiry_event_id = speed_zero_state["expiry_event_id"]
        self.assertIsInstance(expiry_event_id, str)
        expiry_event = schedule.event(expiry_event_id)
        compiled_transitions = {
            "activation": {
                "gate_id": activation_transition["gate_id"],
                "branch_id": activation_transition["branch_id"],
                "event_id": activation_transition["event_id"],
                "applied_component_ids": activation_transition[
                    "filtered_branch"
                ]["applies"],
            },
            "speed_zero": {
                "gate_id": speed_zero_transition["gate_id"],
                "branch_id": speed_zero_transition["branch_id"],
                "event_id": speed_zero_transition["event_id"],
                "applied_component_ids": speed_zero_transition[
                    "filtered_branch"
                ]["applies"],
            },
        }
        common = {
            "state": state,
            "schedule": schedule,
            "effect": program,
            "target_ids": (target_id,),
            "selector_membership": selector_membership,
            "selector_context": selector_context,
            "target_id": target_id,
            "area_response_convention": convention,
            "membership": params["membership"],
            "effect_active": params["effect_active"],
        }
        if lifecycle["kind"] == "typed_target_exit":
            exit_event = next(
                event
                for event in schedule.events
                if event.kind == "exit" and event.target_id == target_id
            )
            result = self.engine._resolve_area_response(
                **common,
                event_id=exit_event.event_id,
                post_movement_membership=params["post_movement_membership"],
            )
            result.update({
                "compiled_transitions": compiled_transitions,
                "speed_zero_expiry_event_id": expiry_event_id,
                "active_component_ids_after": sorted(
                    component.component_id
                    for component in state.active_components(target_id)
                ),
            })
            return result

        movement_events = [
            event
            for event in schedule.events
            if event.kind == "target_movement_opportunity"
            and event.target_id == target_id
        ]
        blocked = self.engine._resolve_area_response(
            **common,
            event_id=movement_events[0].event_id,
            routes=params["routes"],
            base_speeds_ft=params["base_speeds_ft"],
        )
        expired = state.expire(expiry_event_id)
        active_after_expiry = sorted(
            component.component_id
            for component in state.active_components(target_id)
        )
        next_movement = self.engine._resolve_area_response(
            **common,
            event_id=movement_events[1].event_id,
            routes=params["routes"],
            base_speeds_ft=params["base_speeds_ft"],
        )
        return {
            "compiled_transitions": compiled_transitions,
            "speed_zero_expiry_event_id": expiry_event_id,
            "speed_zero_expiry_event_kind": expiry_event.kind,
            "blocked": blocked,
            "expired_component_ids": [
                component.component_id for component in expired
            ],
            "active_component_ids_after_expiry": active_after_expiry,
            "next_movement": next_movement,
            "active_component_ids_after": sorted(
                component.component_id
                for component in state.active_components(target_id)
            ),
        }

    def run_area_response(self, case: Mapping[str, Any]) -> None:
        params = deepcopy(case["input"])
        compiled_effect = params.pop("compiled_effect", None)
        compiled_branch = params.pop("compiled_branch", None)
        compiled_lifecycle = params.pop("compiled_lifecycle", None)
        convention = params.pop("convention")
        speeds_before = deepcopy(params.get("effective_speeds_ft"))
        if compiled_lifecycle is not None:
            self.assertIsNotNone(compiled_effect)
            program = self.engine.program_for(
                compiled_effect["mastery_id"],
                compiled_effect["tier"],
            )
            result = self.run_compiled_area_lifecycle(
                case=case,
                params=params,
                program=program,
                convention=convention,
                lifecycle=compiled_lifecycle,
            )
        elif compiled_effect is None:
            result = area_response(convention, **params)
        else:
            program = self.engine.program_for(
                compiled_effect["mastery_id"],
                compiled_effect["tier"],
            )
            target_id = params["target_id"]
            state = self.engine._new_state()
            active_components = program.components
            if compiled_branch is not None:
                branch = program.gate(
                    compiled_branch["gate_id"]
                ).branch_for_outcome(compiled_branch["outcome"])
                active_components = tuple(
                    program.component(component_id)
                    for component_id in branch.applies
                )
            for component in active_components:
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
                    event_id=f"fixture:{case['id']}:apply",
                    invocation_id=f"fixture:{case['id']}:invocation",
                )
            selector_membership = {
                selector.selector_id: [target_id]
                for selector in program.selectors
            }
            effect_active = params["effect_active"]
            schedule = self.engine.schedule(
                "fighter_first_v1",
                [target_id],
                controller_events_by_round=(
                    {1: [{"kind": "concentration_end"}]}
                    if not effect_active else None
                ),
                target_attack_counts={target_id: [0, 0, 0]},
            )
            response_event_kind = (
                "target_movement_opportunity"
                if effect_active else "concentration_end"
            )
            response_event = next(
                event for event in schedule.events
                if event.kind == response_event_kind
            )
            result = self.engine._resolve_area_response(
                state=state,
                schedule=schedule,
                effect=program,
                target_ids=(target_id,),
                selector_membership=selector_membership,
                selector_context=SelectorContext(
                    controller_can_see_by_target={target_id: True},
                    target_size_by_id={target_id: "medium"},
                    controller_proficiency_bonus=6,
                ),
                event_id=response_event.event_id,
                area_response_convention=convention,
                **params,
            )
        expected = case["expected"]
        for path, value in expected.get("paths", {}).items():
            self.assertEqual(path_value(result, path), value)
        for field_name in ("ended_component_ids", "retained_component_ids"):
            if field_name in expected:
                self.assertEqual(result[field_name], expected[field_name])
        if "effective_speeds_unchanged" in expected:
            self.assertEqual(
                params["effective_speeds_ft"],
                expected["effective_speeds_unchanged"],
            )
            self.assertEqual(params["effective_speeds_ft"], speeds_before)
        json.dumps(result, sort_keys=True, allow_nan=False)

    def run_session_area_route(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        target_id = "target"
        program = self.engine.program("frozen_ground_t0_control")
        schedule = self.engine.schedule(
            inputs["initiative_convention"],
            (target_id,),
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={target_id: [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        operation_inputs: dict[str, dict[str, Any]] = {}
        reliability_events: tuple[ReliabilityEvent, ...] = ()
        target_start = None
        if inputs["speed_zero_on_first_response"]:
            target_start = next(
                event for event in schedule.events
                if event.kind == "target_turn_start" and event.round == 1
            )
            gate = program.gate("frozen_ground_t0_start_turn_save")
            reliability_event = ReliabilityEvent.create(
                f"fixture:{case['id']}:start-save",
                gate.trigger,
                target_ids=(target_id,),
                gate_ids=(gate.gate_id,),
                window_id=target_start.event_id,
            )
            reliability_events = (reliability_event,)
            operation_inputs[target_start.event_id] = {
                "reliability_event_ids": [reliability_event.event_id],
            }
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                target_id,
                15,
                {"constitution": 2, "dexterity": 2},
            ),),
            selector_membership={
                "frozen_ground_area_targets": (target_id,),
            },
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={
                target_id: {
                    "base_speeds_ft": {
                        "walk": inputs["base_speed_ft"],
                    },
                    "movement_mode": "walk",
                    "area_membership": True,
                    "area_routes": [{
                        "route_id": "ground_exit",
                        "mode": "walk",
                        "distance_to_exit_ft": inputs["route_distance_ft"],
                        "compatible": True,
                        "movement_cost_multiplier": 1,
                        "environment": "grounded",
                    }],
                },
            },
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=reliability_events,
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
        )
        initial_route = dict(session.area_route_snapshot(target_id)[0])
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.apply_branch(
            gate_id="frozen_ground_t0_activation",
            outcome="no_save",
            target_id=target_id,
        )
        session.close_event()
        if target_start is not None:
            session.advance_to(target_start.event_id)
            session.resolve_save_opportunity(
                actor_id=target_id,
                ability=gate.ability,
            )
            session.apply_branch(
                gate_id="frozen_ground_t0_start_turn_save",
                outcome="save_failure",
                target_id=target_id,
            )
            session.close_event()
        movement_events = [
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
            and event.target_id == target_id
        ]
        session.advance_to(movement_events[0].event_id)
        [first_record] = session.resolve_movement_response(target_id=target_id)
        first_route = dict(session.area_route_snapshot(target_id)[0])
        session.close_event()
        session.advance_to(movement_events[1].event_id)
        [second_record] = session.resolve_movement_response(target_id=target_id)
        second_route = dict(session.area_route_snapshot(target_id)[0])
        result = {
            "initial_route": initial_route,
            "first_response": first_record.to_dict()["payload"],
            "route_after_first": first_route,
            "second_response": second_record.to_dict()["payload"],
            "route_after_second": second_route,
            "second_response_restates_routes": (
                "area_routes" in session.scenario_record[
                    "operation_inputs_by_event"
                ].get(movement_events[1].event_id, {})
            ),
        }
        for path, value in case["expected"]["paths"].items():
            self.assertEqual(path_value(result, path), value)
        json.dumps(result, sort_keys=True, allow_nan=False)

    def run_session_area_membership(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        target_id = "target"
        program = self.engine.program("ball_lightning_t2_control")
        schedule = self.engine.schedule(
            inputs["initiative_convention"],
            (target_id,),
            controller_events_by_round={1: [{"kind": "activation"}]},
            target_attack_counts={target_id: [0, 0, 0]},
        )
        activation = next(
            event for event in schedule.events if event.kind == "activation"
        )
        starts = tuple(
            event for event in schedule.events
            if event.kind == "target_turn_start"
            and event.target_id == target_id
            and event.sequence > activation.sequence
        )[:2]
        self.assertEqual(len(starts), 2)
        gate = program.gate("ball_lightning_start_turn_save")
        reliability_events = tuple(
            ReliabilityEvent.create(
                f"fixture:{case['id']}:round-{event.round}:start-save",
                gate.trigger,
                target_ids=(target_id,),
                gate_ids=(gate.gate_id,),
                window_id=event.event_id,
            )
            for event in starts
        )
        operation_inputs = {
            event.event_id: {
                "reliability_event_ids": [reliability_event.event_id],
            }
            for event, reliability_event in zip(
                starts,
                reliability_events,
                strict=True,
            )
        }
        session = self.engine.execution_session(
            program,
            targets=(ReliabilityTarget(
                target_id,
                15,
                {"charisma": 2},
            ),),
            selector_membership={
                "ball_lightning_area_targets": (target_id,),
            },
            selector_context=SelectorContext(),
            schedule=schedule,
            target_mechanics={
                target_id: {
                    "base_speeds_ft": {"walk": inputs["base_speed_ft"]},
                    "movement_mode": "walk",
                    "area_membership": True,
                    "area_routes": [{
                        "route_id": "ball_lightning_exit",
                        "mode": "walk",
                        "distance_to_exit_ft": inputs["route_distance_ft"],
                        "compatible": True,
                        "movement_cost_multiplier": 1,
                        "environment": "grounded",
                    }],
                },
            },
            area_response_convention="shortest_route_v1",
            displacement_function_id="sqrt_5ft_v1",
            probability_context=ProbabilityContext(save_dc=15),
            reliability_events=reliability_events,
            operation_inputs_by_event=operation_inputs,
            concentration_save_bonus=2,
        )
        session.advance_to(activation.event_id)
        session.start_concentration()
        session.close_event()
        session.advance_to(starts[0].event_id)
        session.resolve_save_opportunity(
            actor_id=target_id,
            ability=gate.ability,
        )
        success = session.apply_branch(
            gate_id=gate.gate_id,
            outcome="save_success",
            target_id=target_id,
        )
        session.close_event()
        active_before_movement = [
            row["component_id"] for row in session.state_snapshot(target_id)
        ]
        movement = next(
            event for event in schedule.events
            if event.kind == "target_movement_opportunity"
            and event.target_id == target_id
            and event.sequence > activation.sequence
        )
        session.advance_to(movement.event_id)
        [response] = session.resolve_movement_response(target_id=target_id)
        session.close_event()
        route_after = dict(session.area_route_snapshot(target_id)[0])
        session.advance_to(starts[1].event_id)
        session.close_event()
        result = {
            "success": success.to_dict()["payload"],
            "active_component_ids_before_movement": active_before_movement,
            "movement": response.to_dict()["payload"],
            "route_after": route_after,
            "later_recurring_gate_pruned": True,
        }
        for path, value in case["expected"]["paths"].items():
            self.assertEqual(path_value(result, path), value)
        json.dumps(result, sort_keys=True, allow_nan=False)

    def run_area_error(self, case: Mapping[str, Any]) -> None:
        params = deepcopy(case["input"])
        convention = params.pop("convention")
        with self.assertRaises(TimelineError) as caught:
            area_response(convention, **params)
        self.assertIn(case["expected"]["error_contains"], str(caught.exception))

    def run_area_entry(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        expected = case["expected"]
        compiled_effect = inputs.get("compiled_effect")
        if compiled_effect is None:
            common = {
                key: value
                for key, value in inputs.items()
                if key != "moved_area_counts_as_entry"
            }
            ignored = area_entry(**common, moved_area_counts_as_entry=False)
            accepted = area_entry(**common, moved_area_counts_as_entry=True)
            duplicate = area_entry(
                **common,
                moved_area_counts_as_entry=True,
                prior_trigger_turn_ids=accepted["triggered_turn_ids"],
            )
        else:
            program = self.engine.program_for(
                compiled_effect["mastery_id"],
                compiled_effect["tier"],
            )
            target_id = inputs["target_id"]
            common = {
                "effect": program,
                "target_ids": (target_id,),
                "selector_membership": {
                    selector.selector_id: [target_id]
                    for selector in program.selectors
                },
                "selector_context": SelectorContext(
                    controller_can_see_by_target={target_id: True},
                    target_size_by_id={target_id: "medium"},
                    controller_proficiency_bonus=6,
                ),
                "target_id": target_id,
                "turn_id": inputs["turn_id"],
                "was_member": inputs["was_member"],
                "is_member": inputs["is_member"],
            }
            ignored = self.engine._resolve_compiled_area_entry(
                **common,
                caused_by_area_movement=True,
            )
            accepted = self.engine._resolve_compiled_area_entry(
                **common,
                caused_by_area_movement=False,
            )
            duplicate = self.engine._resolve_compiled_area_entry(
                **common,
                caused_by_area_movement=False,
                prior_trigger_turn_ids=accepted["triggered_turn_ids"],
            )
        self.assertEqual(ignored["triggered"], expected["moved_area_triggered"])
        self.assertEqual(accepted["triggered"], expected["ordinary_entry_triggered"])
        self.assertEqual(duplicate["triggered"], expected["duplicate_triggered"])
        self.assertEqual(duplicate["reason"], expected["duplicate_reason"])
        if compiled_effect is not None:
            self.assertEqual(
                ignored["entry_policy"]["moved_area_counts_as_entry"],
                expected["moved_area_counts_as_entry"],
            )
            self.assertEqual(
                accepted["gate_opportunity_ids"],
                expected["gate_opportunity_ids"],
            )

    def displacement_result(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        tracker = DisplacementEpochs()
        for raw in inputs["steps"]:
            step = deepcopy(raw)
            kind = step.pop("kind")
            if kind == "apply":
                tracker.apply(**step)
            elif kind == "self_movement":
                tracker.self_movement_opportunity(**step)
            else:  # pragma: no cover - fixture contract closes this
                self.fail(f"Unknown displacement step {kind}")
        return tracker.to_dict()

    def run_displacement(self, case: Mapping[str, Any]) -> None:
        result = self.displacement_result(case["input"])
        expected = case["expected"]
        for path, value in expected.get("paths", {}).items():
            self.assertEqual(path_value(result, path), value)
        for path, value in expected.get("approximate_paths", {}).items():
            self.assertAlmostEqual(path_value(result, path), value)
        for path, limit in expected.get("less_than", {}).items():
            self.assertLess(path_value(result, path), limit)
        for index in expected.get("zero_increment_record_indexes", []):
            self.assertTrue(
                all(
                    row["incremental_value"] == 0
                    for row in result["records"][index]["functions"]
                )
            )
        if "positive_function_ids" in expected:
            functions = {
                row["function_id"]: row["incremental_value"]
                for row in result["records"][0]["functions"]
            }
            self.assertEqual(
                [function_id for function_id, value in functions.items() if value > 0],
                expected["positive_function_ids"],
            )
            self.assertEqual(
                list(functions),
                case["input"]["function_ids"],
            )
        for key, increment in expected.get("function_increments", {}).items():
            _records, index, function_id = key.split(".")
            functions = {
                row["function_id"]: row["incremental_value"]
                for row in result["records"][int(index)]["functions"]
            }
            self.assertEqual(functions[function_id], increment)
        for key, increment in expected.get("approximate_function_increments", {}).items():
            _records, index, function_id = key.split(".")
            functions = {
                row["function_id"]: row["incremental_value"]
                for row in result["records"][int(index)]["functions"]
            }
            self.assertAlmostEqual(functions[function_id], increment)
        json.dumps(result, sort_keys=True, allow_nan=False)

    def run_displacement_scope(self, case: Mapping[str, Any]) -> None:
        payload = json.dumps(
            self.displacement_result(case["input"]),
            sort_keys=True,
            allow_nan=False,
        ).lower().replace("_", " ").replace("-", " ")
        for token in case["expected"]["forbidden_tokens"]:
            normalized_token = token.lower().replace("_", " ").replace("-", " ")
            self.assertNotIn(normalized_token, payload)

    def run_result_boundary(self, case: Mapping[str, Any]) -> None:
        inputs = case["input"]
        program = self.engine.program_for(
            inputs["mastery_id"],
            inputs["tier"],
        )
        target_id = "target"
        reliability = ReliabilityResult(
            effect_id=program.effect_id,
            target_ids=(target_id,),
            component_reliability=(),
            gate_probabilities=(),
            branch_probabilities=(),
            repeat_survival=(),
            immunity_suppressions=(),
            any_candidate_probability=Fraction(0),
            any_component_probability=Fraction(0),
            any_candidate_by_target=((target_id, Fraction(0)),),
            any_component_by_target=((target_id, Fraction(0)),),
            final_world_count=1,
        )
        schedule = self.engine.schedule(
            "fighter_first_v1",
            (target_id,),
            target_attack_counts={target_id: [0, 0, 0]},
        )
        result = self.engine._assemble_result_legacy(
            effect=program,
            reliability=reliability,
            schedule=schedule,
            area_response_convention="fixed_occupancy_v1",
            displacement_function_id="sqrt_5ft_v1",
            state=self.engine._new_state(),
        )
        serialized = result.to_dict()
        expected = case["expected"]
        if "action_optimization" in expected:
            self.assertEqual(
                serialized["scenario_convention"]["action_optimization"],
                expected["action_optimization"],
            )

        def nested_keys(value: Any) -> set[str]:
            if isinstance(value, Mapping):
                return {str(key).casefold() for key in value} | set().union(
                    *(nested_keys(item) for item in value.values())
                )
            if isinstance(value, (list, tuple)):
                return set().union(*(nested_keys(item) for item in value))
            return set()

        present = nested_keys(serialized)
        with self.assertRaisesRegex(ControlEngineError, "issued only"):
            replace(result, explored_state_count=result.explored_state_count)
        for forbidden in expected["forbidden_fields"]:
            self.assertNotIn(forbidden.casefold(), present)
            tainted = _replace_control_engine_result(
                result,
                final_normalized_state={
                    target_id: {"nested": {forbidden: 1}}
                },
            )
            with self.assertRaisesRegex(ControlEngineError, "forbidden"):
                tainted.to_dict()
        json.dumps(serialized, sort_keys=True, allow_nan=False)

    def run_signature_boundary(self, case: Mapping[str, Any]) -> None:
        functions = {
            "evaluate_reliability": evaluate_reliability,
            "build_schedule": build_schedule,
            "area_response": area_response,
        }
        parameters = {
            parameter
            for name in case["input"]["function_names"]
            for parameter in inspect.signature(functions[name]).parameters
        }
        for forbidden in case["expected"]["forbidden_parameters"]:
            self.assertNotIn(forbidden, parameters)
        if "mastery_id" in case["input"]:
            self.run_result_boundary(case)


if __name__ == "__main__":
    unittest.main()
