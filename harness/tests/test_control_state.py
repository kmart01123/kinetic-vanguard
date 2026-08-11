from __future__ import annotations

import json
import unittest
from copy import deepcopy

from harness.control_catalog import SenseQueryResult

from harness.control_state import (
    NORMALIZATION_RULES_VERSION,
    ControlState,
    ControlStateError,
    condition_instance_id_for,
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
    application_sequence: int | None = None,
    condition_instance_id: str | None = None,
    source_program_id: str | None = None,
    issuance_id: str | None = None,
    provenance_id: str | None = None,
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
        application_sequence=application_sequence,
        condition_instance_id=condition_instance_id,
        source_program_id=source_program_id,
        issuance_id=issuance_id,
        provenance_id=provenance_id,
    )


def condition_catalog(
    inclusions: dict[str, tuple[str, ...] | list[str]],
) -> dict[str, object]:
    return {
        "conditions": {
            condition_id: {
                "includes": list(includes),
                "primitives": [],
            }
            for condition_id, includes in inclusions.items()
        }
    }


class ControlStateTransitionTests(unittest.TestCase):
    def test_normalization_contract_is_explicitly_versioned(self) -> None:
        self.assertEqual(NORMALIZATION_RULES_VERSION, "2.0.0")

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

    def test_noncondition_reapplication_refreshes_without_duplicate_active_state(self) -> None:
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


class ConditionInstanceLifecycleTests(unittest.TestCase):
    def test_source_relative_conditions_reject_self_source_before_mutation(self) -> None:
        for condition_id in ("charmed", "frightened"):
            with self.subTest(condition_id=condition_id):
                state = ControlState(
                    catalog=condition_catalog({condition_id: ()})
                )
                with self.assertRaisesRegex(ControlStateError, "non-self source"):
                    apply(
                        state,
                        component(
                            condition_id,
                            {"kind": "condition", "condition": condition_id},
                        ),
                        source_actor="target_a",
                    )
                self.assertEqual(state.instance_registry(), ())
                self.assertEqual(state.snapshot(), [])

    def test_atomic_preview_clone_shares_catalog_but_not_mutable_state(self) -> None:
        state = ControlState(catalog=condition_catalog({"blinded": ()}))
        preview = deepcopy(state)
        self.assertIs(preview._catalog, state._catalog)
        apply(
            preview,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
            application_sequence=2,
        )
        self.assertEqual(state.instance_registry(), ())
        self.assertEqual(len(preview.instance_registry()), 1)

    def test_independent_same_condition_sources_are_distinct_but_derive_once(self) -> None:
        state = ControlState(
            catalog=condition_catalog({"restrained": ()})
        )
        restrained = component(
            "restrained",
            {"kind": "condition", "condition": "restrained"},
        )
        apply(
            state,
            restrained,
            source_actor="source_a",
            application_sequence=3,
            issuance_id="issuance_a",
            provenance_id="provenance_a",
        )
        apply(
            state,
            restrained,
            source_actor="source_b",
            application_sequence=4,
            issuance_id="issuance_b",
            provenance_id="provenance_b",
        )

        instances = state.active_condition_instances("target_a")
        self.assertEqual(len(instances), 2)
        self.assertEqual(
            {item.source_actor_id for item in instances},
            {"source_a", "source_b"},
        )
        self.assertEqual(len({item.instance_id for item in instances}), 2)
        self.assertEqual(
            state.derived_current_conditions("target_a"),
            ("restrained",),
        )
        self.assertEqual(
            state.final_normalized_state()["target_a"]["conditions"],
            ["restrained"],
        )
        self.assertEqual(len(state.active_components("target_a")), 2)

    def test_included_condition_has_separate_queryable_identity_and_lineage(self) -> None:
        state = ControlState(
            catalog=condition_catalog({
                "stunned": ("incapacitated",),
                "incapacitated": (),
            })
        )
        stunned = component(
            "stunned",
            {"kind": "condition", "condition": "stunned"},
        )
        active = apply(
            state,
            stunned,
            source_actor="stunning_source",
            application_sequence=7,
            source_program_id="stun_program",
            issuance_id="stun_issuance",
            provenance_id="stun_provenance",
        )

        by_condition = {
            item.condition_id: item
            for item in state.active_condition_instances("target_a")
        }
        self.assertEqual(set(by_condition), {"stunned", "incapacitated"})
        self.assertEqual(
            by_condition["incapacitated"].parent_condition_instance_id,
            by_condition["stunned"].instance_id,
        )
        self.assertEqual(
            active.condition_instance_id,
            by_condition["stunned"].instance_id,
        )
        self.assertEqual(
            state.derived_current_conditions("target_a"),
            ("incapacitated", "stunned"),
        )
        lineage = state.lineage_records("target_a")
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["parent_condition_id"], "stunned")
        self.assertEqual(lineage[0]["child_condition_id"], "incapacitated")
        self.assertEqual(lineage[0]["issuance_id"], "stun_issuance")

        child = by_condition["incapacitated"]
        before_child_end = (
            state.snapshot(),
            state.instance_registry(),
            state.lineage_records(),
            state.condition_lifecycle_records(),
            deepcopy(state.audit_ledger),
        )
        with self.assertRaisesRegex(
            ControlStateError,
            "Included condition instances end only through their exact root",
        ):
            state.end_condition_instance(
                child.instance_id,
                event_id="invalid_child_end",
                event_sequence=8,
                reason="source_end",
                expected_source_actor_id="stunning_source",
                expected_issuance_id="stun_issuance",
            )
        self.assertEqual(
            (
                state.snapshot(),
                state.instance_registry(),
                state.lineage_records(),
                state.condition_lifecycle_records(),
                state.audit_ledger,
            ),
            before_child_end,
        )

    def test_parent_end_cleans_only_its_child_and_independent_child_survives(self) -> None:
        state = ControlState(
            catalog=condition_catalog({
                "stunned": ("incapacitated",),
                "incapacitated": (),
            })
        )
        stunned_component = component(
            "stunned",
            {"kind": "condition", "condition": "stunned"},
        )
        incapacitated_component = component(
            "incapacitated",
            {"kind": "condition", "condition": "incapacitated"},
        )
        apply(
            state,
            stunned_component,
            effect="stun_effect",
            source_actor="stun_source",
            application_sequence=1,
            issuance_id="stun_issuance",
            provenance_id="stun_provenance",
        )
        apply(
            state,
            incapacitated_component,
            effect="independent_effect",
            source_actor="independent_source",
            application_sequence=2,
            issuance_id="independent_issuance",
            provenance_id="independent_provenance",
        )
        stunned_root = next(
            item
            for item in state.active_condition_instances("target_a")
            if item.condition_id == "stunned"
        )

        ended = state.end_condition_instance(
            stunned_root.instance_id,
            event_id="stun_source_end",
            event_sequence=3,
            reason="source_end",
            expected_source_actor_id="stun_source",
            expected_issuance_id="stun_issuance",
        )

        self.assertEqual(
            {item.condition_id for item in ended},
            {"stunned", "incapacitated"},
        )
        remaining = state.active_condition_instances("target_a")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].condition_id, "incapacitated")
        self.assertEqual(remaining[0].source_actor_id, "independent_source")
        self.assertEqual(
            state.derived_current_conditions("target_a"),
            ("incapacitated",),
        )
        self.assertEqual(
            [item.effect_id for item in state.active_components("target_a")],
            ["independent_effect"],
        )
        ended_rows = [
            row
            for row in state.instance_registry("target_a")
            if row["status"] == "ended"
        ]
        self.assertEqual(len(ended_rows), 2)
        self.assertTrue(all(row["end_reason"] == "source_end" for row in ended_rows))

    def test_same_source_stunned_applications_keep_independent_child_lineages(
        self,
    ) -> None:
        state = ControlState(
            catalog=condition_catalog({
                "stunned": ("incapacitated",),
                "incapacitated": (),
            })
        )
        stunned = component(
            "stunned",
            {"kind": "condition", "condition": "stunned"},
        )
        direct_incapacitated = component(
            "incapacitated",
            {"kind": "condition", "condition": "incapacitated"},
        )
        roots = []
        for sequence, invocation in ((1, "invocation_a"), (2, "invocation_b")):
            roots.append(apply(
                state,
                stunned,
                event=f"stunned_{invocation}",
                invocation=invocation,
                source_actor="same_source",
                application_sequence=sequence,
                source_program_id="stun_program",
                issuance_id=f"issuance_{invocation}",
                provenance_id=f"provenance_{invocation}",
            ))
        independent = apply(
            state,
            direct_incapacitated,
            effect="independent_effect",
            event="independent_incapacitated",
            invocation="independent_invocation",
            source_actor="independent_source",
            application_sequence=3,
            issuance_id="independent_issuance",
            provenance_id="independent_provenance",
        )

        lineages = state.lineage_records("target_a")
        self.assertEqual(len(lineages), 2)
        self.assertEqual(
            {row["source_invocation_id"] for row in lineages},
            {"invocation_a", "invocation_b"},
        )
        self.assertEqual(
            state.derived_current_conditions("target_a"),
            ("incapacitated", "stunned"),
        )
        self.assertEqual(len(state.active_condition_instances("target_a")), 5)

        state.end_condition_instance(
            roots[0].condition_instance_id,
            event_id="end_a",
            event_sequence=4,
            reason="source_end",
            expected_source_actor_id="same_source",
            expected_issuance_id="issuance_invocation_a",
        )
        active = state.active_condition_instances("target_a")
        self.assertEqual(
            {row.source_invocation_id for row in active},
            {"invocation_b", "independent_invocation"},
        )
        self.assertEqual(len(active), 3)
        state.end_condition_instance(
            roots[1].condition_instance_id,
            event_id="end_b",
            event_sequence=5,
            reason="source_end",
            expected_source_actor_id="same_source",
            expected_issuance_id="issuance_invocation_b",
        )
        remaining = state.active_condition_instances("target_a")
        self.assertEqual([row.instance_id for row in remaining], [independent.condition_instance_id])
        self.assertEqual(
            state.derived_current_conditions("target_a"),
            ("incapacitated",),
        )

    def test_condition_transitions_are_exact_or_invocation_qualified_and_atomic(
        self,
    ) -> None:
        restrained = component(
            "restrained",
            {"kind": "condition", "condition": "restrained"},
        )
        stunned = component(
            "stunned",
            {"kind": "condition", "condition": "stunned"},
        )

        def populated(invocations: tuple[str, ...]) -> ControlState:
            state = ControlState()
            for sequence, invocation in enumerate(invocations, 1):
                apply(
                    state,
                    restrained,
                    event=f"apply_{sequence}",
                    invocation=invocation,
                    application_sequence=sequence,
                    issuance_id=f"issuance_{sequence}",
                    provenance_id=f"provenance_{sequence}",
                )
            return state

        state = populated(("invocation_a", "invocation_b"))
        unchanged = (
            state.snapshot(),
            state.instance_registry(),
            state.condition_lifecycle_records(),
            deepcopy(state.audit_ledger),
        )
        with self.assertRaisesRegex(ControlStateError, "requires an exact"):
            state.terminate(
                target_id="target_a",
                component_id="restrained",
                effect_id="test_effect",
                event_id="ambiguous_end",
            )
        with self.assertRaisesRegex(ControlStateError, "requires an exact"):
            state.refresh(
                target_id="target_a",
                component_id="restrained",
                effect_id="test_effect",
                event_id="ambiguous_refresh",
            )
        self.assertEqual(
            (
                state.snapshot(),
                state.instance_registry(),
                state.condition_lifecycle_records(),
                state.audit_ledger,
            ),
            unchanged,
        )

        state.apply_branch(
            effect_id="test_effect",
            branch={
                "branch_id": "replace_restrained",
                "outcome": "save_failure",
                "applies": ["stunned"],
                "replaces": ["restrained"],
                "terminates": [],
                "refreshes": [],
                "next_gate_ids": [],
            },
            components_by_id={"restrained": restrained, "stunned": stunned},
            target_id="target_a",
            source_actor_id="controller",
            event_id="replace_a",
            invocation_id="invocation_a",
            application_sequence=3,
            issuance_id="replacement_issuance",
            provenance_id="replacement_provenance",
        )
        active_roots = [
            row
            for row in state.active_condition_instances("target_a")
            if row.parent_condition_instance_id is None
        ]
        self.assertEqual(
            {(row.condition_id, row.source_invocation_id) for row in active_roots},
            {("restrained", "invocation_b"), ("stunned", "invocation_a")},
        )
        self.assertEqual(
            state.replacement_records[-1]["selected_source_invocation_id"],
            "invocation_a",
        )

        ambiguous = populated(("invocation_a", "invocation_a"))
        before = (
            ambiguous.snapshot(),
            ambiguous.instance_registry(),
            ambiguous.condition_lifecycle_records(),
            deepcopy(ambiguous.audit_ledger),
        )
        with self.assertRaisesRegex(ControlStateError, "ambiguous within invocation"):
            ambiguous.apply_branch(
                effect_id="test_effect",
                branch={
                    "branch_id": "ambiguous_replace",
                    "outcome": "save_failure",
                    "applies": ["stunned"],
                    "replaces": ["restrained"],
                    "terminates": [],
                    "refreshes": [],
                    "next_gate_ids": [],
                },
                components_by_id={"restrained": restrained, "stunned": stunned},
                target_id="target_a",
                source_actor_id="controller",
                event_id="ambiguous_replace",
                invocation_id="invocation_a",
                application_sequence=3,
                issuance_id="ambiguous_issuance",
                provenance_id="ambiguous_provenance",
            )
        self.assertEqual(
            (
                ambiguous.snapshot(),
                ambiguous.instance_registry(),
                ambiguous.condition_lifecycle_records(),
                ambiguous.audit_ledger,
            ),
            before,
        )

    def test_cycle_duplicate_lineage_and_broken_chain_fail_atomically(self) -> None:
        invalid_catalogs = (
            (
                "cycle",
                condition_catalog({"alpha": ("beta",), "beta": ("alpha",)}),
                "Condition inclusion cycle",
            ),
            (
                "duplicate direct child",
                {
                    "conditions": {
                        "alpha": {
                            "includes": ["beta", "beta"],
                            "primitives": [],
                        },
                        "beta": {"includes": [], "primitives": []},
                    }
                },
                "duplicate lineage",
            ),
            (
                "duplicate diamond child",
                condition_catalog({
                    "alpha": ("left", "right"),
                    "left": ("shared",),
                    "right": ("shared",),
                    "shared": (),
                }),
                "repeats condition",
            ),
            (
                "broken child",
                condition_catalog({"alpha": ("missing",)}),
                "Broken condition inclusion",
            ),
        )
        definition = component(
            "alpha",
            {"kind": "condition", "condition": "alpha"},
        )
        for label, catalog, message in invalid_catalogs:
            with self.subTest(label=label):
                state = ControlState(catalog=catalog)
                with self.assertRaisesRegex(ControlStateError, message):
                    apply(
                        state,
                        definition,
                        application_sequence=1,
                        issuance_id="issuance",
                        provenance_id="provenance",
                    )
                self.assertFalse(state.active_components())
                self.assertEqual(state.instance_registry(), ())
                self.assertFalse(state.audit_ledger)

    def test_exact_identity_rejects_rewrite_duplicate_wrong_source_and_double_end(self) -> None:
        catalog = condition_catalog({"prone": ()})
        prone = component(
            "prone",
            {"kind": "condition", "condition": "prone"},
            mode="independent",
        )
        expected_id = condition_instance_id_for(
            condition_id="prone",
            target_id="target_a",
            source_actor_id="source",
            source_program_id="program",
            source_effect_id="test_effect",
            source_invocation_id="invocation_1",
            source_component_id="prone",
            application_event_id="event_apply",
            application_sequence=5,
            duration=prone["duration"],
            expiry_event_id="event_expire",
            issuance_id="issuance",
            provenance_id="provenance",
        )
        state = ControlState(catalog=catalog)
        active = apply(
            state,
            prone,
            source_actor="source",
            application_sequence=5,
            condition_instance_id=expected_id,
            source_program_id="program",
            issuance_id="issuance",
            provenance_id="provenance",
        )
        self.assertEqual(active.condition_instance_id, expected_id)

        rewritten = f"{expected_id[:-1]}{'0' if expected_id[-1] != '0' else '1'}"
        with self.assertRaisesRegex(ControlStateError, "Unknown or stale"):
            state.end_condition_instance(
                rewritten,
                event_id="end",
                event_sequence=6,
                reason="source_end",
                expected_source_actor_id="source",
            )
        with self.assertRaisesRegex(ControlStateError, "source actor mismatch"):
            state.end_condition_instance(
                expected_id,
                event_id="end",
                event_sequence=6,
                reason="source_end",
                expected_source_actor_id="wrong_source",
            )
        with self.assertRaisesRegex(ControlStateError, "issuance mismatch"):
            state.end_condition_instance(
                expected_id,
                event_id="end",
                event_sequence=6,
                reason="source_end",
                expected_source_actor_id="source",
                expected_issuance_id="wrong_issuance",
            )
        state.end_condition_instance(
            expected_id,
            event_id="end",
            event_sequence=6,
            reason="source_end",
            expected_source_actor_id="source",
            expected_issuance_id="issuance",
        )
        with self.assertRaisesRegex(ControlStateError, "already ended"):
            state.end_condition_instance(
                expected_id,
                event_id="second_end",
                event_sequence=7,
                reason="source_end",
                expected_source_actor_id="source",
            )

        duplicate_state = ControlState(catalog=catalog)
        apply(
            duplicate_state,
            prone,
            source_actor="source",
            application_sequence=5,
            condition_instance_id=expected_id,
            source_program_id="program",
            issuance_id="issuance",
            provenance_id="provenance",
        )
        before_duplicate = (
            duplicate_state.snapshot(),
            duplicate_state.instance_registry(),
            duplicate_state.lineage_records(),
            duplicate_state.condition_lifecycle_records(),
            deepcopy(duplicate_state.audit_ledger),
        )
        with self.assertRaisesRegex(ControlStateError, "Duplicate condition instance ID"):
            apply(
                duplicate_state,
                prone,
                source_actor="source",
                application_sequence=5,
                condition_instance_id=expected_id,
                source_program_id="program",
                issuance_id="issuance",
                provenance_id="provenance",
            )
        self.assertEqual(
            (
                duplicate_state.snapshot(),
                duplicate_state.instance_registry(),
                duplicate_state.lineage_records(),
                duplicate_state.condition_lifecycle_records(),
                duplicate_state.audit_ledger,
            ),
            before_duplicate,
        )

        rewritten_state = ControlState(catalog=catalog)
        with self.assertRaisesRegex(ControlStateError, "does not match"):
            apply(
                rewritten_state,
                prone,
                source_actor="source",
                application_sequence=5,
                condition_instance_id="condition_rewritten",
                source_program_id="program",
                issuance_id="issuance",
                provenance_id="provenance",
            )
        self.assertEqual(rewritten_state.instance_registry(), ())

    def test_same_source_applications_keep_independent_lifecycles_and_one_mechanic(
        self,
    ) -> None:
        restrained_a = component(
            "restrained",
            {"kind": "condition", "condition": "restrained"},
        )
        restrained_b = deepcopy(restrained_a)
        restrained_b["duration"]["offset_turns"] = 2

        def populated(
            invocation_a: str = "invocation_a",
            invocation_b: str = "invocation_b",
        ) -> tuple[ControlState, object, object]:
            state = ControlState()
            first = apply(
                state,
                restrained_a,
                event="application_a",
                expiry="expiry_a",
                invocation=invocation_a,
                application_sequence=1,
                source_program_id="shared_program",
                issuance_id="issuance_a",
                provenance_id="provenance_a",
            )
            second = apply(
                state,
                restrained_b,
                event="application_b",
                expiry="expiry_b",
                invocation=invocation_b,
                application_sequence=2,
                source_program_id="shared_program",
                issuance_id="issuance_b",
                provenance_id="provenance_b",
            )
            return state, first, second

        state, first, second = populated()
        self.assertNotEqual(first.condition_instance_id, second.condition_instance_id)
        roots = state.active_condition_instances("target_a")
        self.assertEqual(len(roots), 2)
        self.assertEqual(
            {row.source_invocation_id for row in roots},
            {"invocation_a", "invocation_b"},
        )
        self.assertEqual(
            {row.application_event_id for row in roots},
            {"application_a", "application_b"},
        )
        self.assertEqual({row.application_sequence for row in roots}, {1, 2})
        self.assertEqual({row.issuance_id for row in roots}, {"issuance_a", "issuance_b"})
        self.assertEqual(
            {row.provenance_id for row in roots},
            {"provenance_a", "provenance_b"},
        )
        self.assertEqual({row.expiry_event_id for row in roots}, {"expiry_a", "expiry_b"})
        self.assertEqual(len({json.dumps(row.duration, sort_keys=True) for row in roots}), 2)
        self.assertEqual(state.derived_current_conditions("target_a"), ("restrained",))
        self.assertEqual(len(state.active_components("target_a")), 2)
        self.assertFalse(state.refresh_records)
        normalized = state.normalize_for_window(
            target_id="target_a",
            window_id="attack",
            window_kind="target_attack_opportunity",
        )
        self.assertEqual(len(normalized.contributions), 1)
        self.assertEqual(
            set(normalized.contributions[0].source_component_ids),
            {
                f"condition_instance:{first.condition_instance_id}",
                f"condition_instance:{second.condition_instance_id}",
            },
        )
        self.assertEqual(
            {row["source_invocation_id"] for row in state.condition_lifecycle_records()},
            {"invocation_a", "invocation_b"},
        )

        state.expire("expiry_a", event_sequence=3)
        self.assertEqual(
            [row.source_invocation_id for row in state.active_condition_instances()],
            ["invocation_b"],
        )
        state.end_condition_instance(
            second.condition_instance_id,
            event_id="end_b",
            event_sequence=4,
            reason="source_end",
            expected_source_actor_id="controller",
            expected_issuance_id="issuance_b",
        )
        self.assertEqual(state.derived_current_conditions("target_a"), ())

        exact_end_state, exact_first, exact_second = populated()
        exact_end_state.end_condition_instance(
            exact_first.condition_instance_id,
            event_id="end_a",
            event_sequence=3,
            reason="countered",
            expected_source_actor_id="controller",
            expected_issuance_id="issuance_a",
        )
        self.assertEqual(
            [row.instance_id for row in exact_end_state.active_condition_instances()],
            [exact_second.condition_instance_id],
        )

        same_invocation, same_first, same_second = populated(
            "shared_invocation",
            "shared_invocation",
        )
        self.assertNotEqual(
            same_first.condition_instance_id,
            same_second.condition_instance_id,
        )
        self.assertEqual(len(same_invocation.active_condition_instances()), 2)

    def test_registry_lineage_and_lifecycle_serialization_is_deterministic(self) -> None:
        catalog = condition_catalog({"restrained": ()})
        restrained = component(
            "restrained",
            {"kind": "condition", "condition": "restrained"},
        )

        def populated(order: tuple[str, ...]) -> ControlState:
            state = ControlState(catalog=catalog)
            for application_id in order:
                sequence = 1 if application_id == "application_a" else 2
                apply(
                    state,
                    restrained,
                    effect="shared_effect",
                    event=application_id,
                    expiry=f"expiry_{application_id[-1]}",
                    invocation=f"invocation_{application_id[-1]}",
                    source_actor="shared_source",
                    application_sequence=sequence,
                    source_program_id="shared_program",
                    issuance_id=f"issuance_{application_id[-1]}",
                    provenance_id=f"provenance_{application_id[-1]}",
                )
            return state

        first = populated(("application_a", "application_b"))
        second = populated(("application_b", "application_a"))
        self.assertEqual(len(first.active_condition_instances()), 2)
        self.assertEqual(len(second.active_condition_instances()), 2)
        first_serialized = json.dumps(
            {
                "components": first.snapshot(),
                "registry": first.instance_registry(),
                "lineage": first.lineage_records(),
                "lifecycle": first.condition_lifecycle_records(),
                "derived": first.derived_current_conditions("target_a"),
                "normalized": first.final_normalized_state(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        second_serialized = json.dumps(
            {
                "components": second.snapshot(),
                "registry": second.instance_registry(),
                "lineage": second.lineage_records(),
                "lifecycle": second.condition_lifecycle_records(),
                "derived": second.derived_current_conditions("target_a"),
                "normalized": second.final_normalized_state(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(first_serialized, second_serialized)


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
                applied_denial = apply(
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
                    f"condition_instance:{applied_denial.condition_instance_id}"
                    if applied_denial.condition_instance_id is not None
                    else f"denial_effect:{denial['component_id']}"
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
                    instance_id=applied_denial.instance_id,
                    source_invocation_id=applied_denial.source_invocation_id,
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
        effect_a = apply(
            state,
            restrained,
            effect="effect_a",
            source_actor="source_a",
        )
        effect_b = apply(
            state,
            restrained,
            effect="effect_b",
            source_actor="source_b",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="restrained_attack",
            window_kind="target_attack_opportunity",
        )
        self.assertEqual(len(result.contributions), 1)
        contribution = result.contributions[0]
        self.assertEqual(
            set(contribution.source_component_ids),
            {
                f"condition_instance:{effect_a.condition_instance_id}",
                f"condition_instance:{effect_b.condition_instance_id}",
            },
        )
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
            window_kind="controller_attack_opportunity",
        )
        self.assertEqual(first.contributions[0].primitive_id, "offensive_impairment_next_attack")
        self.assertFalse(state.active_components())
        second = state.normalize_for_window(
            target_id="target_a",
            window_id="attack_2",
            window_kind="target_attack_opportunity",
        )
        self.assertFalse(second.contributions)

    def test_all_attacks_emits_for_each_scheduled_attack_opportunity(self) -> None:
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
        self.assertEqual(len(all_attacks), 2)
        self.assertTrue(all(item.unit == "attack_opportunity" for item in all_attacks))
        self.assertEqual(
            [item.event_or_window_id for item in all_attacks],
            [windows[1].window_id, windows[2].window_id],
        )

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
        self.assertFalse(denied_turn.suppressions)
        denied_attack = state.normalize_for_window(
            target_id="target_a",
            window_id="impossible_attack",
            window_kind="target_attack_opportunity",
        )
        self.assertFalse(denied_attack.contributions)
        self.assertEqual(
            {row.primitive_id for row in denied_attack.suppressions},
            {
                "offensive_impairment_all_attacks",
                "offensive_impairment_next_attack",
            },
        )
        next_attack = next(
            item for item in state.active_components("target_a")
            if item.component_id == "next_attack"
        )
        self.assertEqual(next_attack.remaining_tokens, 1)
        incapacitated = next(
            item
            for item in state.active_components("target_a")
            if item.component_id == "incapacitated"
        )
        state.terminate(
            target_id="target_a",
            component_id="incapacitated",
            effect_id="denial_effect",
            event_id="denial_ends",
            instance_id=incapacitated.instance_id,
            source_invocation_id=incapacitated.source_invocation_id,
        )
        resumed_turn = state.normalize_for_window(
            target_id="target_a",
            window_id="resumed_turn",
            window_kind="target_active_turn_opportunity",
        )
        self.assertFalse(resumed_turn.contributions)
        resumed = state.normalize_for_window(
            target_id="target_a",
            window_id="legal_attack",
            window_kind="target_attack_opportunity",
        )
        self.assertEqual(
            {item.primitive_id for item in resumed.contributions},
            {
                "offensive_impairment_all_attacks",
                "offensive_impairment_next_attack",
            },
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
    def test_included_and_direct_incapacitated_consequences_do_not_amplify(self) -> None:
        state = ControlState()
        stunned = apply(
            state,
            component("stunned", {"kind": "condition", "condition": "stunned"}),
            effect="stun_effect",
            source_actor="stun_source",
            application_sequence=1,
            issuance_id="stun_issuance",
            provenance_id="stun_provenance",
        )
        independent = apply(
            state,
            component(
                "incapacitated",
                {"kind": "condition", "condition": "incapacitated"},
            ),
            effect="independent_effect",
            event="independent_apply",
            invocation="invocation_2",
            source_actor="independent_source",
            application_sequence=2,
            issuance_id="independent_issuance",
            provenance_id="independent_provenance",
        )
        instances = {
            item.instance_id: item
            for item in state.active_condition_instances("target_a")
        }
        included = next(
            item
            for item in instances.values()
            if item.parent_condition_instance_id == stunned.condition_instance_id
            and item.condition_id == "incapacitated"
        )
        self.assertEqual(included.source_actor_id, "stun_source")
        self.assertEqual(
            instances[independent.condition_instance_id].source_actor_id,
            "independent_source",
        )

        result = state.normalize_for_window(
            target_id="target_a",
            window_id="shared_reaction_window",
            window_kind="reaction_window",
        )
        reaction_denials = [
            item
            for item in result.contributions
            if item.primitive_id == "reaction_denial"
        ]
        self.assertEqual(len(reaction_denials), 1)
        self.assertEqual(reaction_denials[0].quantity, 1.0)
        expected_sources = {
            f"condition_instance:{included.instance_id}",
            f"condition_instance:{independent.condition_instance_id}",
        }
        self.assertEqual(
            set(reaction_denials[0].source_component_ids),
            expected_sources,
        )
        overlap = [
            item
            for item in result.suppressions
            if item.primitive_id == "reaction_denial"
            and item.reason == "identical_primitive_maximum_presence"
        ]
        self.assertEqual(len(overlap), 1)
        self.assertEqual(
            set(
                overlap[0].dominant_source_component_ids
                + overlap[0].suppressed_source_component_ids
            ),
            expected_sources,
        )

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

    def test_blinded_attack_effects_persist_with_alternative_sight(self) -> None:
        state = ControlState()
        apply(
            state,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
        )
        without_sight = state.normalize_for_window(
            target_id="target_a",
            window_id="attack_without_sight",
            window_kind="target_attack_opportunity",
            context={"alternative_sight_resolution": False},
        )
        with_sight = state.normalize_for_window(
            target_id="target_a",
            window_id="attack_with_sight",
            window_kind="target_attack_opportunity",
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
        self.assertIn(
            "offensive_impairment_all_attacks",
            {item.primitive_id for item in with_sight.contributions},
        )

    def test_identical_unconditional_attack_boole_collapse_without_amplifying(self) -> None:
        state = ControlState()
        blinded = apply(
            state,
            component("blinded", {"kind": "condition", "condition": "blinded"}),
            effect="blind_effect",
        )
        restrained = apply(
            state,
            component(
                "restrained",
                {"kind": "condition", "condition": "restrained"},
            ),
            effect="restrained_effect",
            invocation="invocation_2",
        )
        expected = {
            "target_attack_opportunity": "offensive_impairment_all_attacks",
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
                    set(matching[0].source_component_ids),
                    {
                        f"condition_instance:{blinded.condition_instance_id}",
                        f"condition_instance:{restrained.condition_instance_id}",
                    },
                )
                suppression = next(
                    item for item in result.suppressions
                    if item.reason
                    == "identical_primitive_maximum_presence"
                )
                self.assertEqual(
                    suppression.dominant_source_component_ids,
                    (f"condition_instance:{blinded.condition_instance_id}",),
                )
                self.assertEqual(
                    suppression.suppressed_source_component_ids,
                    (f"condition_instance:{restrained.condition_instance_id}",),
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
        charmed = apply(
            state,
            component("charmed", {"kind": "condition", "condition": "charmed"}),
            effect="charm_effect",
            source_actor="charmer_a",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="charmed_action",
            window_kind="action_proposal",
            context={"source_actor_id": "untrusted_caller_value"},
        )
        restriction = next(item for item in result.contributions)
        self.assertEqual(restriction.context["source_actor_id"], "charmer_a")
        self.assertEqual(
            restriction.source_component_ids,
            (f"condition_instance:{charmed.condition_instance_id}",),
        )
        self.assertNotIn("source_context_by_actor_id", restriction.context)

    def test_frightened_uses_context_for_its_own_source_actor(self) -> None:
        state = ControlState()
        fear = component("frightened", {"kind": "condition", "condition": "frightened"})
        fear_a = apply(
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
            window_id="frightened_attack",
            window_kind="target_attack_opportunity",
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
        self.assertEqual(
            impairment.source_component_ids,
            (f"condition_instance:{fear_a.condition_instance_id}",),
        )
        self.assertEqual(impairment.context["source_actor_id"], "source_a")
        self.assertIs(impairment.context["source_in_line_of_sight"], True)
        self.assertNotIn("source_context_by_actor_id", impairment.context)

    def test_visible_frightened_sources_max_collapse_after_predicates_pass(self) -> None:
        state = ControlState()
        fear = component(
            "frightened",
            {"kind": "condition", "condition": "frightened"},
        )
        fear_a = apply(
            state,
            fear,
            effect="fear_a",
            source_actor="source_a",
        )
        fear_b = apply(
            state,
            fear,
            effect="fear_b",
            source_actor="source_b",
            invocation="invocation_2",
        )
        result = state.normalize_for_window(
            target_id="target_a",
            window_id="both_frightened_sources_visible_attack",
            window_kind="target_attack_opportunity",
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
            {
                f"condition_instance:{fear_a.condition_instance_id}",
                f"condition_instance:{fear_b.condition_instance_id}",
            },
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
            "target_attack_opportunity": (
                "offensive_impairment_all_attacks",
                "denial",
                "candidate",
                False,
            ),
            "incoming_attack_opportunity": (
                "defensive_attack_advantage",
                "enablement",
                "candidate",
                False,
            ),
            "sight_opportunity": (
                "sight_option_denial",
                "retained_unpriced",
                "retained_unpriced",
                True,
            ),
        }
        for window_kind, (
            primitive_id,
            family,
            disposition,
            unresolved,
        ) in cases.items():
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
                self.assertEqual(contribution.family, family)
                self.assertEqual(contribution.disposition, disposition)
                self.assertEqual(
                    bool(contribution.context.get("unresolved_requirements")),
                    unresolved,
                )

        generic_attack = state.normalize_for_window(
            target_id="target_a",
            window_id="unresolved_generic_attack_opportunity",
            window_kind="attack_opportunity",
            context={"sense_resolution": resolution},
        )
        self.assertEqual(
            {
                item.primitive_id for item in generic_attack.contributions
            },
            {
                "defensive_attack_advantage",
                "offensive_impairment_all_attacks",
            },
        )

if __name__ == "__main__":
    unittest.main()
