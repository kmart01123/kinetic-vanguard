from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from types import MappingProxyType, SimpleNamespace

from harness.authority import ControlAuthorityV2Model
from harness.control_graph import (
    CONTROL_MAGNITUDE_KINDS,
    CompiledEvent,
    ControlGraphError,
    D20ProbabilityKernel,
    ProbabilityContext,
    ReliabilityEvent,
    ReliabilityTarget,
    SelectorContext,
    compile_control_authority,
    compile_magnitude,
    d20_attack_hit_probability,
    d20_save_success_probability,
    evaluate_reliability,
    resolve_roll_mode,
    validate_selector_membership,
)


ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def target(
    target_id: str,
    *,
    armor_class: int = 15,
    bonus: int = 0,
    condition_immunities: tuple[str, ...] = (),
    magic_resistance: bool = False,
    legendary_resistance: int = 0,
) -> ReliabilityTarget:
    return ReliabilityTarget(
        target_id,
        armor_class,
        {ability: bonus for ability in ABILITIES},
        condition_immunities=condition_immunities,
        magic_resistance=magic_resistance,
        legendary_resistance=legendary_resistance,
    )


def component_windows(result: object, component_id: str, target_id: str) -> dict[str, Fraction]:
    row = result.component(component_id, target_id)  # type: ignore[attr-defined]
    return dict(row.active_by_window)


class AlwaysFailureKernel:
    """Exact scripted kernel used to expose graph topology, not d20 arithmetic."""

    def outcome_probabilities(self, gate: object, _target: object, _context: object) -> dict[str, Fraction]:
        outcomes = {branch.outcome for branch in gate.branches}  # type: ignore[attr-defined]
        preferred = next(
            outcome
            for outcome in ("no_save", "damage_context", "other", "attack_hit", "save_failure")
            if outcome in outcomes
        )
        return {outcome: Fraction(outcome == preferred) for outcome in outcomes}


class HalfKernel:
    """Give each two-way gate a fair branch and deterministic gates mass one."""

    def outcome_probabilities(self, gate: object, _target: object, _context: object) -> dict[str, Fraction]:
        outcomes = [branch.outcome for branch in gate.branches]  # type: ignore[attr-defined]
        if len(outcomes) == 1:
            return {outcomes[0]: Fraction(1)}
        if len(outcomes) != 2:
            raise AssertionError(f"Unexpected test gate outcomes: {outcomes}")
        return {outcome: Fraction(1, 2) for outcome in outcomes}


class RecordingFailureKernel(AlwaysFailureKernel):
    def __init__(self) -> None:
        self.gate_ids: list[str] = []

    def outcome_probabilities(
        self,
        gate: object,
        target_value: object,
        context: object,
    ) -> dict[str, Fraction]:
        self.gate_ids.append(gate.gate_id)  # type: ignore[attr-defined]
        return super().outcome_probabilities(gate, target_value, context)


def same_event_guard_effect(compiled):
    base = compiled.program_for("mass_levitation", 0)
    template_gate = base.gate("mass_levitation_t0_concentration_end")
    template_branch = template_gate.branch_for_outcome("no_save")
    trigger = CompiledEvent.compile(
        {"kind": "turn", "owner": "controller", "turn_anchor": "end"}
    )
    active_component_id = "mass_levitation_persistent_elevation"
    applied_component_id = "mass_levitation_fall"
    terminate_gate_id = "mass_levitation_z_same_event_terminate"
    apply_gate_id = "mass_levitation_a_same_event_apply"

    def make_gate(
        gate_id: str,
        *,
        applies: tuple[str, ...] = (),
        terminates: tuple[str, ...] = (),
    ):
        branch_id = f"{gate_id}_branch"
        branch = replace(
            template_branch,
            branch_id=branch_id,
            qualified_id=replace(
                template_branch.qualified_id,
                local_id=branch_id,
            ),
            applies=applies,
            replaces=(),
            terminates=terminates,
            refreshes=(),
            next_gate_ids=(),
        )
        return replace(
            template_gate,
            gate_id=gate_id,
            qualified_id=replace(
                template_gate.qualified_id,
                local_id=gate_id,
            ),
            trigger=trigger,
            branches=(branch,),
            _branch_by_outcome=MappingProxyType({"no_save": branch}),
        )

    terminate_gate = make_gate(
        terminate_gate_id,
        terminates=(active_component_id,),
    )
    apply_gate = make_gate(
        apply_gate_id,
        applies=(applied_component_id,),
    )
    added_gates = (terminate_gate, apply_gate)
    gate_by_id = dict(base._gate_by_id)
    gate_by_id.update({gate.gate_id: gate for gate in added_gates})
    gates_by_event = dict(base._gates_by_event)
    gates_by_event[trigger.key] = tuple(
        sorted(added_gates, key=lambda gate: gate.gate_id)
    )
    outgoing = dict(base._outgoing)
    outgoing.update({gate.gate_id: () for gate in added_gates})
    effect = replace(
        base,
        root_gate_ids=(
            *base.root_gate_ids,
            terminate_gate_id,
            apply_gate_id,
        ),
        gates=tuple(
            sorted((*base.gates, *added_gates), key=lambda gate: gate.gate_id)
        ),
        _gate_by_id=MappingProxyType(gate_by_id),
        _gates_by_event=MappingProxyType(gates_by_event),
        _outgoing=MappingProxyType(outgoing),
    )
    return (
        effect,
        trigger,
        active_component_id,
        applied_component_id,
        terminate_gate_id,
        apply_gate_id,
    )


class ControlAuthorityCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.authority = ControlAuthorityV2Model.load(require_benchmark_ready=True)
        cls.compiled = compile_control_authority(cls.authority)

    def test_compiles_complete_ready_authority_and_preserves_profile_metadata(self) -> None:
        compiled = self.compiled
        self.assertEqual((compiled.projection_version, compiled.contract_version), ("2.1.0", "2.1.0"))
        self.assertEqual(compiled.schema_version, "3.1.0")
        self.assertEqual(compiled.rules_version, "14.2.0")
        self.assertEqual((len(compiled.programs), len(compiled.masteries), len(compiled.exclusions)), (35, 3, 14))
        self.assertEqual(sum(len(program.components) for program in compiled.programs), 76)
        self.assertEqual(sum(len(program.selectors) for program in compiled.programs), 41)
        self.assertEqual(sum(len(program.gates) for program in compiled.programs), 71)
        self.assertEqual(sum(len(gate.branches) for program in compiled.programs for gate in program.gates), 131)
        self.assertEqual(
            compiled.tactical_master.to_dict(),
            {
                "minimum_level": 9,
                "choice_mastery_ids": ["mastery_push", "mastery_sap", "mastery_slow"],
                "choice_timing": {"kind": "declaration"},
                "behavior": "replaces_kinetic_mastery",
            },
        )
        self.assertEqual(
            [mastery.mastery_id for mastery in compiled.masteries],
            ["mastery_slow", "mastery_push", "mastery_sap"],
        )

    def test_exclusions_are_preserved_but_never_executable(self) -> None:
        keys = {(row.entity_id, row.tier) for row in self.compiled.exclusions}
        self.assertEqual(len(keys), 14)
        self.assertIn(("advanced_beguile", 0), keys)
        self.assertIn(("thermal_fracture", 2), keys)
        with self.assertRaisesRegex(ControlGraphError, "No executable control program"):
            self.compiled.program_for("thermal_fracture", 2)

    def test_compiler_accepts_only_the_validated_model_boundary(self) -> None:
        with self.assertRaisesRegex(TypeError, "ControlAuthorityV2Model"):
            compile_control_authority(self.authority.projection)  # type: ignore[arg-type]

    def test_compiled_ir_is_frozen_and_all_local_ids_are_namespaced(self) -> None:
        with self.assertRaises(TypeError):
            self.compiled.active_profile["id"] = "changed"  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            self.compiled.projection_version = "changed"  # type: ignore[misc]

        qualified: list[str] = []
        effect_ids = [program.effect_id for program in self.compiled.programs]
        self.assertEqual(len(effect_ids), len(set(effect_ids)))
        for program in self.compiled.programs:
            objects = [*program.choices, *program.selectors, *program.components, *program.gates]
            for gate in program.gates:
                objects.extend(gate.branches)
            for selector in program.selectors:
                if selector.area is not None:
                    objects.append(selector.area)
            for value in objects:
                self.assertEqual(value.qualified_id.namespace, program.effect_id)
                qualified.append(str(value.qualified_id))
        self.assertEqual(len(qualified), len(set(qualified)))
        for mastery in self.compiled.masteries:
            self.assertEqual(mastery.component.qualified_id.namespace, mastery.mastery_id)

    def test_all_eleven_magnitude_kinds_have_an_explicit_dispatch(self) -> None:
        self.assertEqual(
            CONTROL_MAGNITUDE_KINDS,
            {
                "condition",
                "forced_movement",
                "speed_reduction",
                "speed_zero",
                "difficult_terrain",
                "persistent_elevation",
                "fall",
                "attack_disadvantage",
                "reaction_denial",
                "movement_option_denial",
                "numerical_modifier",
            },
        )
        active = {
            component.magnitude.kind
            for program in self.compiled.programs
            for component in program.components
        } | {mastery.component.magnitude.kind for mastery in self.compiled.masteries}
        self.assertEqual(CONTROL_MAGNITUDE_KINDS - active, {"movement_option_denial", "numerical_modifier"})
        self.assertEqual(
            compile_magnitude({"kind": "movement_option_denial", "movement_modes": ["fly"]}).kind,
            "movement_option_denial",
        )
        numerical = compile_magnitude({"kind": "numerical_modifier", "target": "armor_class", "value": -2})
        self.assertEqual(numerical.data.to_dict(), {"kind": "numerical_modifier", "target": "armor_class", "value": -2})
        with self.assertRaisesRegex(ControlGraphError, "Unsupported ControlMagnitudeV2"):
            compile_magnitude({"kind": "future_kind"})

    def test_choice_bindings_fail_closed_before_scenario_evaluation(self) -> None:
        effect = self.compiled.program_for("explosion_implosion", 0)
        with self.assertRaisesRegex(ControlGraphError, "missing=.*explosion_implosion_mode"):
            effect.bind_choices()
        with self.assertRaisesRegex(ControlGraphError, "does not allow"):
            effect.bind_choices({"explosion_implosion_mode": "sideways"})
        self.assertEqual(
            dict(effect.bind_choices({"explosion_implosion_mode": "explosion"})),
            {"explosion_implosion_mode": "explosion"},
        )
        with self.assertRaisesRegex(ControlGraphError, "choice bindings"):
            evaluate_reliability(
                effect,
                targets=[target("primary")],
                selector_membership={},
                kernel=AlwaysFailureKernel(),
            )

    def test_graph_indexes_ignore_resolution_array_order_and_preserve_transitions(self) -> None:
        original = self.compiled.program_for("snow_chains", 2)
        projection = deepcopy(self.authority.projection)
        ledger = projection["control_authority"]["ledger"]
        row = next(item for item in ledger if item["entity_id"] == "snow_chains" and item["tier"] == 2)
        row["model"]["resolutions"].reverse()
        reordered = compile_control_authority(ControlAuthorityV2Model(projection)).program_for("snow_chains", 2)
        self.assertEqual(reordered, original)
        self.assertEqual(
            [gate.gate_id for gate in original.gates_for_event({"kind": "hit"})],
            ["snow_chains_t2_attack"],
        )
        self.assertEqual(original.outgoing_gate_ids("snow_chains_t2_attack"), ("snow_chains_t2_save",))
        failure = original.gate("snow_chains_t2_save").branch_for_outcome("save_failure")
        self.assertEqual(failure.applies, ("snow_chains_stunned", "snow_chains_reaction_denial"))
        self.assertEqual(failure.replaces, ("snow_chains_restrained",))
        self.assertEqual((failure.terminates, failure.refreshes, failure.next_gate_ids), ((), (), ()))

        mass = self.compiled.program_for("mass_levitation", 2)
        repeat = mass.gate("mass_levitation_t2_repeat_saves")
        self.assertEqual(repeat.requires_active_component_ids, ("mass_levitation_persistent_elevation",))
        self.assertEqual(repeat.trigger.data.to_dict(), {"kind": "turn", "owner": "target", "turn_anchor": "start"})
        self.assertEqual(repeat.branch_for_outcome("save_failure").next_gate_ids, ("mass_levitation_t2_damage_context",))


class ExactProbabilityKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiled = compile_control_authority(ControlAuthorityV2Model.load(require_benchmark_ready=True))
        cls.kernel = D20ProbabilityKernel()

    def test_normal_advantage_disadvantage_and_opposition_are_exact(self) -> None:
        self.assertEqual(d20_attack_hit_probability(5, 15), Fraction(11, 20))
        self.assertEqual(d20_attack_hit_probability(5, 15, "advantage"), Fraction(319, 400))
        self.assertEqual(d20_attack_hit_probability(5, 15, "disadvantage"), Fraction(121, 400))
        self.assertEqual(d20_save_success_probability(0, 11), Fraction(1, 2))
        self.assertEqual(d20_save_success_probability(0, 11, "advantage"), Fraction(3, 4))
        self.assertEqual(d20_save_success_probability(0, 11, "disadvantage"), Fraction(1, 4))
        self.assertEqual(resolve_roll_mode(2, 1), "normal")
        self.assertEqual(resolve_roll_mode(0, 3), "disadvantage")

        gate = self.compiled.program_for("snow_chains", 0).gate("snow_chains_t0_attack")
        opposed = self.kernel.outcome_probabilities(
            gate,
            target("t"),
            ProbabilityContext(attack_bonus=5, attack_advantage_sources=1, attack_disadvantage_sources=1),
        )
        self.assertEqual(opposed, {"attack_hit": Fraction(11, 20), "attack_miss": Fraction(9, 20)})

    def test_magic_resistance_is_caller_identified_and_legendary_resistance_is_metadata_only(self) -> None:
        gate = self.compiled.program_for("advanced_phase_step", 2).gate("advanced_phase_step_t2_signature_saves")
        resistant = target("resistant", magic_resistance=True, legendary_resistance=3)
        ordinary = self.kernel.outcome_probabilities(
            gate,
            resistant,
            ProbabilityContext(save_dc=11, discipline_signature="wisdom", magical=False),
        )
        magical = self.kernel.outcome_probabilities(
            gate,
            resistant,
            ProbabilityContext(save_dc=11, discipline_signature="wisdom", magical=True),
        )
        no_legendary_uses = self.kernel.outcome_probabilities(
            gate,
            target("resistant", magic_resistance=True, legendary_resistance=0),
            ProbabilityContext(save_dc=11, discipline_signature="wisdom", magical=True),
        )
        self.assertEqual(ordinary["save_success"], Fraction(1, 2))
        self.assertEqual(magical["save_success"], Fraction(3, 4))
        self.assertEqual(no_legendary_uses, magical)
        with self.assertRaisesRegex(ControlGraphError, "magic_resistance"):
            target("invalid", magic_resistance="false")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ControlGraphError, "magic_resistance"):
            ReliabilityTarget.from_target(
                "invalid_from_target",
                SimpleNamespace(
                    ac=15,
                    saves={ability: 0 for ability in ABILITIES},
                    condition_immunities=(),
                    magic_resistance="false",
                    legendary_resistance=0,
                ),
            )
        with self.assertRaisesRegex(ControlGraphError, "magical"):
            ProbabilityContext(magical="false")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ControlGraphError, "discipline_signature"):
            self.kernel.outcome_probabilities(gate, resistant, ProbabilityContext(save_dc=11))

    def test_deterministic_no_save_and_damage_context_gates_have_unit_mass(self) -> None:
        no_save = self.compiled.program_for("frozen_ground", 0).gate("frozen_ground_t0_activation")
        damage = self.compiled.program_for("mass_levitation", 2).gate("mass_levitation_t2_damage_context")
        self.assertEqual(self.kernel.outcome_probabilities(no_save, None, ProbabilityContext()), {"no_save": Fraction(1)})
        self.assertEqual(
            self.kernel.outcome_probabilities(damage, None, ProbabilityContext()),
            {"damage_context": Fraction(1)},
        )


class CorrelatedReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiled = compile_control_authority(ControlAuthorityV2Model.load(require_benchmark_ready=True))
        cls.context = ProbabilityContext(attack_bonus=5, save_dc=11)

    def evaluate_one(
        self,
        entity_id: str,
        tier: int,
        *,
        condition_immunities: tuple[str, ...] = (),
        candidate_component_ids: tuple[str, ...],
    ):
        effect = self.compiled.program_for(entity_id, tier)
        return evaluate_reliability(
            effect,
            targets=[target("target", condition_immunities=condition_immunities)],
            selector_membership={selector.selector_id: ["target"] for selector in effect.selectors},
            selector_context=SelectorContext(
                controller_can_see_by_target={"target": True},
                target_size_by_id={"target": "medium"},
            ),
            context=self.context,
            candidate_component_ids=candidate_component_ids,
        )

    def test_candidate_component_ids_are_explicit_and_may_exclude_retained_state(self) -> None:
        effect = self.compiled.program_for("mass_levitation", 0)
        arguments = {
            "targets": [target("target")],
            "selector_membership": {"mass_levitation_targets": ["target"]},
            "selector_context": SelectorContext(
                controller_can_see_by_target={"target": True},
                target_size_by_id={"target": "medium"},
            ),
            "context": self.context,
        }
        with self.assertRaisesRegex(ControlGraphError, "supplied explicitly"):
            evaluate_reliability(effect, **arguments)
        result = evaluate_reliability(
            effect,
            **arguments,
            candidate_component_ids=(),
        )
        self.assertEqual(result.any_candidate_probability, Fraction(0))
        self.assertEqual(result.any_component_probability, Fraction(1, 2))

    def test_selector_membership_enforces_fixed_and_up_to_cardinality(self) -> None:
        snow = self.compiled.program_for("snow_chains", 0)
        with self.assertRaisesRegex(ControlGraphError, "requires exactly 1"):
            evaluate_reliability(
                snow,
                targets=[target("alpha"), target("beta")],
                selector_membership={
                    "snow_chains_target": ["alpha", "beta"]
                },
                kernel=AlwaysFailureKernel(),
                candidate_component_ids=(),
            )

        tempest = self.compiled.program_for("arctic_tempest", 0)
        target_ids = ("one", "two", "three", "four")
        with self.assertRaisesRegex(ControlGraphError, "allows at most 3"):
            evaluate_reliability(
                tempest,
                targets=[target(target_id) for target_id in target_ids],
                selector_membership={
                    "arctic_tempest_targets": list(target_ids)
                },
                kernel=AlwaysFailureKernel(),
                candidate_component_ids=(),
            )

    def test_selector_membership_excludes_primary_from_secondary(self) -> None:
        effect = self.compiled.program_for("explosion_implosion", 0)
        with self.assertRaisesRegex(ControlGraphError, "excludes primary"):
            evaluate_reliability(
                effect,
                targets=[target("overlap")],
                selector_membership={
                    "explosion_implosion_primary": ["overlap"],
                    "explosion_implosion_secondary_targets": ["overlap"],
                },
                kernel=AlwaysFailureKernel(),
                choices={"explosion_implosion_mode": "explosion"},
                candidate_component_ids=(),
            )

    def test_selector_context_validates_all_fact_dependent_rules(self) -> None:
        slam = self.compiled.program_for("telekinetic_slam", 0)
        slam_membership = {"telekinetic_slam_target": ["target"]}
        with self.assertRaisesRegex(
            ControlGraphError,
            "explicit controller visibility",
        ):
            validate_selector_membership(
                slam,
                target_ids=("target",),
                selector_membership=slam_membership,
            )
        with self.assertRaisesRegex(ControlGraphError, "controller to see"):
            validate_selector_membership(
                slam,
                target_ids=("target",),
                selector_membership=slam_membership,
                selector_context=SelectorContext(
                    controller_can_see_by_target={"target": False},
                ),
            )
        self.assertEqual(
            dict(
                validate_selector_membership(
                    slam,
                    target_ids=("target",),
                    selector_membership=slam_membership,
                    selector_context=SelectorContext(
                        controller_can_see_by_target={"target": True},
                    ),
                )
            ),
            {"telekinetic_slam_target": ("target",)},
        )

        levitation = self.compiled.program_for("mass_levitation", 0)
        three_targets = ("alpha", "beta", "gamma")
        levitation_membership = {
            "mass_levitation_targets": list(three_targets)
        }
        visible = {target_id: True for target_id in three_targets}
        with self.assertRaisesRegex(ControlGraphError, "uses 6 weighted slots"):
            validate_selector_membership(
                levitation,
                target_ids=three_targets,
                selector_membership=levitation_membership,
                selector_context=SelectorContext(
                    controller_can_see_by_target=visible,
                    target_size_by_id={
                        target_id: "large" for target_id in three_targets
                    },
                ),
            )
        with self.assertRaisesRegex(ControlGraphError, "exceeds maximum size"):
            validate_selector_membership(
                levitation,
                target_ids=("huge_target",),
                selector_membership={
                    "mass_levitation_targets": ["huge_target"]
                },
                selector_context=SelectorContext(
                    controller_can_see_by_target={"huge_target": True},
                    target_size_by_id={"huge_target": "huge"},
                ),
            )

        discharge = self.compiled.program_for("static_discharge", 2)
        discharge_membership = {
            "static_discharge_primary": ["primary"],
            "static_discharge_secondary": ["secondary_a", "secondary_b"],
        }
        discharge_targets = ("primary", "secondary_a", "secondary_b")
        with self.assertRaisesRegex(
            ControlGraphError,
            "controller_proficiency_bonus",
        ):
            validate_selector_membership(
                discharge,
                target_ids=discharge_targets,
                selector_membership=discharge_membership,
            )
        with self.assertRaisesRegex(
            ControlGraphError,
            "at most 1 target IDs",
        ):
            validate_selector_membership(
                discharge,
                target_ids=discharge_targets,
                selector_membership=discharge_membership,
                selector_context=SelectorContext(
                    controller_proficiency_bonus=1,
                ),
            )
        validated = validate_selector_membership(
            discharge,
            target_ids=discharge_targets,
            selector_membership=discharge_membership,
            selector_context=SelectorContext(
                controller_proficiency_bonus=2,
            ),
        )
        self.assertEqual(
            validated["static_discharge_secondary"],
            ("secondary_a", "secondary_b"),
        )
        self.assertEqual(
            validate_selector_membership(
                discharge,
                target_ids=("primary",),
                selector_membership={
                    "static_discharge_primary": ["primary"],
                    "static_discharge_secondary": [],
                },
            )["static_discharge_secondary"],
            (),
        )

    def test_snow_chains_partial_package_and_successful_save_remainder(self) -> None:
        result = self.evaluate_one(
            "snow_chains",
            1,
            candidate_component_ids=("snow_chains_restrained", "snow_chains_reaction_denial"),
        )
        speed = result.component("snow_chains_speed_zero", "target")
        restrained = result.component("snow_chains_restrained", "target")
        reaction = result.component("snow_chains_reaction_denial", "target")
        self.assertEqual(speed.initially_applied, Fraction(11, 20))
        self.assertEqual(restrained.initially_applied, Fraction(11, 40))
        self.assertEqual(reaction.initially_applied, Fraction(11, 40))
        self.assertEqual(speed.initially_applied - restrained.initially_applied, Fraction(11, 40))
        self.assertEqual(result.any_candidate_probability, Fraction(11, 40))
        self.assertEqual(result.any_component_probability, Fraction(11, 20))
        self.assertEqual(result.final_world_count, 3)

        gates = {(row.gate_id, row.target_ids): row.probability for row in result.gate_probabilities}
        self.assertEqual(gates[("snow_chains_t1_attack", ("target",))], Fraction(1))
        self.assertEqual(gates[("snow_chains_t1_save", ("target",))], Fraction(11, 20))
        branches = {(row.gate_id, row.outcome): row.probability for row in result.branch_probabilities}
        self.assertEqual(branches[("snow_chains_t1_attack", "attack_miss")], Fraction(9, 20))
        self.assertEqual(branches[("snow_chains_t1_save", "save_success")], Fraction(11, 40))
        self.assertEqual(branches[("snow_chains_t1_save", "save_failure")], Fraction(11, 40))

    def test_telekinetic_slam_t2_success_and_failure_movements_stay_distinct(self) -> None:
        effect = self.compiled.program_for("telekinetic_slam", 2)
        failed = effect.component("telekinetic_slam_failed_save_movement")
        successful = effect.component("telekinetic_slam_successful_save_movement")
        self.assertEqual((failed.magnitude.data["distance_feet"], failed.magnitude.data["distance_mode"]), (30, "exact"))
        self.assertEqual(
            (successful.magnitude.data["distance_feet"], successful.magnitude.data["distance_mode"]),
            (10, "up_to"),
        )
        result = self.evaluate_one(
            "telekinetic_slam",
            2,
            candidate_component_ids=(failed.component_id, successful.component_id),
        )
        self.assertEqual(result.component(failed.component_id, "target").ever_applied, Fraction(1, 2))
        self.assertEqual(result.component(successful.component_id, "target").ever_applied, Fraction(1, 2))
        self.assertEqual(result.component("telekinetic_slam_speed_zero", "target").ever_applied, Fraction(1, 2))
        self.assertEqual(result.any_candidate_probability, Fraction(1))
        self.assertEqual(result.any_component_probability, Fraction(1))

    def test_absolute_zero_t2_success_retains_speed_zero(self) -> None:
        result = self.evaluate_one(
            "absolute_zero",
            2,
            candidate_component_ids=("absolute_zero_speed_zero",),
        )
        self.assertEqual(result.component("absolute_zero_speed_zero", "target").initially_applied, Fraction(1))
        self.assertEqual(result.component("absolute_zero_stunned", "target").initially_applied, Fraction(1, 2))
        self.assertEqual(result.component("absolute_zero_restrained", "target").ever_applied, Fraction(0))
        self.assertEqual(result.any_candidate_probability, Fraction(1))
        branches = {(row.outcome, row.probability) for row in result.branch_probabilities}
        self.assertIn(("save_success", Fraction(1, 2)), branches)

    def test_shared_branch_correlation_is_not_marginal_multiplication(self) -> None:
        result = self.evaluate_one(
            "absolute_zero",
            1,
            candidate_component_ids=("absolute_zero_speed_zero", "absolute_zero_restrained"),
        )
        self.assertEqual(result.component("absolute_zero_speed_zero", "target").ever_applied, Fraction(1, 2))
        self.assertEqual(result.component("absolute_zero_restrained", "target").ever_applied, Fraction(1, 2))
        self.assertEqual(result.any_candidate_probability, Fraction(1, 2))
        self.assertNotEqual(result.any_candidate_probability, Fraction(3, 4))
        self.assertEqual(result.final_world_count, 2)

    def test_condition_immunity_suppresses_only_the_condition_component(self) -> None:
        result = self.evaluate_one(
            "snow_chains",
            1,
            condition_immunities=("restrained",),
            candidate_component_ids=("snow_chains_restrained", "snow_chains_reaction_denial"),
        )
        self.assertEqual(result.component("snow_chains_speed_zero", "target").ever_applied, Fraction(11, 20))
        self.assertEqual(result.component("snow_chains_restrained", "target").ever_applied, Fraction(0))
        self.assertEqual(result.component("snow_chains_reaction_denial", "target").ever_applied, Fraction(11, 40))
        self.assertEqual(result.any_candidate_probability, Fraction(11, 40))
        self.assertEqual(len(result.immunity_suppressions), 1)
        suppression = result.immunity_suppressions[0]
        self.assertEqual((suppression.component_id, suppression.condition, suppression.probability), ("snow_chains_restrained", "restrained", Fraction(11, 40)))

    def test_independent_targets_enumerate_joint_worlds_and_are_permutation_invariant(self) -> None:
        effect = self.compiled.program_for("frozen_ground", 0)
        event = ReliabilityEvent.create(
            "target_turn_1",
            {"kind": "turn", "owner": "target", "turn_anchor": "start"},
            target_ids=("alpha", "beta"),
        )
        first = evaluate_reliability(
            effect,
            targets=[target("beta"), target("alpha")],
            selector_membership={"frozen_ground_area_targets": ["beta", "alpha"]},
            context=ProbabilityContext(save_dc=11),
            events=(event,),
            candidate_component_ids=("frozen_ground_speed_zero",),
        )
        second = evaluate_reliability(
            effect,
            targets=[target("alpha"), target("beta")],
            selector_membership={"frozen_ground_area_targets": ["alpha", "beta"]},
            context=ProbabilityContext(save_dc=11),
            events=(event,),
            candidate_component_ids=("frozen_ground_speed_zero",),
        )
        self.assertEqual(first, second)
        self.assertEqual(first.target_ids, ("alpha", "beta"))
        self.assertEqual(dict(first.any_candidate_by_target), {"alpha": Fraction(1, 2), "beta": Fraction(1, 2)})
        self.assertEqual(first.any_candidate_probability, Fraction(3, 4))
        self.assertEqual(first.final_world_count, 4)

    def test_repeat_save_survival_and_active_windows_are_exact(self) -> None:
        effect = self.compiled.program_for("mass_levitation", 0)
        trigger = {"kind": "turn", "owner": "target", "turn_anchor": "start"}
        result = evaluate_reliability(
            effect,
            targets=[target("target")],
            selector_membership={"mass_levitation_targets": ["target"]},
            selector_context=SelectorContext(
                controller_can_see_by_target={"target": True},
                target_size_by_id={"target": "medium"},
            ),
            kernel=HalfKernel(),
            events=(
                ReliabilityEvent.create("target_turn_1", trigger, target_ids=("target",)),
                ReliabilityEvent.create("target_turn_2", trigger, target_ids=("target",)),
            ),
            candidate_component_ids=("mass_levitation_persistent_elevation",),
        )
        elevation = result.component("mass_levitation_persistent_elevation", "target")
        self.assertEqual(elevation.initially_applied, Fraction(1, 2))
        self.assertEqual(elevation.ever_applied, Fraction(1, 2))
        windows = dict(elevation.active_by_window)
        self.assertEqual(windows["initial:mass_levitation_t0_initial_saves"], Fraction(1, 2))
        self.assertEqual(windows["target_turn_1"], Fraction(1, 4))
        self.assertEqual(windows["target_turn_2"], Fraction(1, 8))
        self.assertEqual(
            [(row.event_id, row.probability) for row in result.repeat_survival],
            [("target_turn_1", Fraction(1, 4)), ("target_turn_2", Fraction(1, 8))],
        )
        self.assertEqual(result.component("mass_levitation_fall", "target").ever_applied, Fraction(3, 8))

    def test_reliability_event_rejects_duplicate_semantic_ids(self) -> None:
        trigger = {
            "kind": "turn",
            "owner": "target",
            "turn_anchor": "start",
        }
        duplicates = {
            "target_ids": ("target", "target"),
            "gate_ids": ("gate", "gate"),
            "expire_component_ids": ("component", "component"),
        }
        for field_name, values in duplicates.items():
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(
                    ControlGraphError,
                    f"duplicate {field_name}",
                ):
                    ReliabilityEvent.create(
                        "duplicate_field",
                        trigger,
                        **{field_name: values},
                    )
        ordered = ReliabilityEvent.create(
            "ordered",
            trigger,
            target_ids=("beta", "alpha"),
            gate_ids=("gate_z", "gate_a"),
            expire_component_ids=("component_z", "component_a"),
        )
        self.assertEqual(ordered.target_ids, ("beta", "alpha"))
        self.assertEqual(ordered.gate_ids, ("gate_z", "gate_a"))
        self.assertEqual(
            ordered.expire_component_ids,
            ("component_z", "component_a"),
        )

    def test_same_event_guards_use_pre_event_snapshot_and_caller_order(self) -> None:
        (
            effect,
            trigger,
            active_component_id,
            applied_component_id,
            terminate_gate_id,
            apply_gate_id,
        ) = same_event_guard_effect(self.compiled)
        for gate_order in (
            (terminate_gate_id, apply_gate_id),
            (apply_gate_id, terminate_gate_id),
        ):
            with self.subTest(gate_order=gate_order):
                kernel = RecordingFailureKernel()
                result = evaluate_reliability(
                    effect,
                    targets=[target("target")],
                    selector_membership={
                        "mass_levitation_targets": ["target"]
                    },
                    selector_context=SelectorContext(
                        controller_can_see_by_target={"target": True},
                        target_size_by_id={"target": "medium"},
                    ),
                    kernel=kernel,
                    events=(
                        ReliabilityEvent.create(
                            "same_event",
                            trigger,
                            target_ids=("target",),
                            gate_ids=gate_order,
                        ),
                    ),
                    candidate_component_ids=(),
                )
                self.assertEqual(kernel.gate_ids[-2:], list(gate_order))
                self.assertEqual(
                    result.component(
                        active_component_id,
                        "target",
                    ).initially_applied,
                    Fraction(1),
                )
                self.assertEqual(
                    result.component(
                        applied_component_id,
                        "target",
                    ).ever_applied,
                    Fraction(1),
                )
                self.assertEqual(
                    component_windows(
                        result,
                        active_component_id,
                        "target",
                    )["same_event"],
                    Fraction(0),
                )
                event_gate_probability = {
                    row.gate_id: row.probability
                    for row in result.gate_probabilities
                    if row.event_id == "same_event"
                }
                self.assertEqual(
                    event_gate_probability,
                    {
                        terminate_gate_id: Fraction(1),
                        apply_gate_id: Fraction(1),
                    },
                )

    def test_duplicate_reliability_event_ids_are_rejected(self) -> None:
        effect = self.compiled.program_for("mass_levitation", 0)
        trigger = {"kind": "turn", "owner": "target", "turn_anchor": "start"}
        events = (
            ReliabilityEvent.create("duplicate", trigger, target_ids=("target",), window_id="one"),
            ReliabilityEvent.create("duplicate", trigger, target_ids=("target",), window_id="two"),
        )
        with self.assertRaisesRegex(ControlGraphError, "Duplicate reliability event ID"):
            evaluate_reliability(
                effect,
                targets=[target("target")],
                selector_membership={"mass_levitation_targets": ["target"]},
                selector_context=SelectorContext(
                    controller_can_see_by_target={"target": True},
                    target_size_by_id={"target": "medium"},
                ),
                kernel=HalfKernel(),
                events=events,
                candidate_component_ids=(),
            )

    def test_cross_selector_edges_reach_secondary_targets_and_honor_choice(self) -> None:
        effect = self.compiled.program_for("explosion_implosion", 0)
        result = evaluate_reliability(
            effect,
            targets=[target("primary"), target("secondary_a"), target("secondary_b")],
            selector_membership={
                "explosion_implosion_primary": ["primary"],
                "explosion_implosion_secondary_targets": ["secondary_a", "secondary_b"],
            },
            kernel=AlwaysFailureKernel(),
            choices={"explosion_implosion_mode": "explosion"},
            candidate_component_ids=tuple(
                component.component_id for component in effect.components
            ),
        )
        for target_id in ("secondary_a", "secondary_b"):
            self.assertEqual(result.component("explosion_implosion_restrained", target_id).ever_applied, Fraction(1))
            self.assertEqual(result.component("explosion_implosion_outward_movement", target_id).ever_applied, Fraction(1))
            self.assertEqual(result.component("explosion_implosion_inward_movement", target_id).ever_applied, Fraction(0))


if __name__ == "__main__":
    unittest.main()
