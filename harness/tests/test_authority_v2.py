from __future__ import annotations

import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from harness.authority import (
    CONTROL_PROJECTION_VERSION,
    DEFAULT_AUTHORITY,
    AuthorityError,
    ControlAuthorityV2Model,
    load_control_projection_v2,
    validate_control_projection_v2,
)


def _ledger(projection: dict[str, object]) -> list[dict[str, object]]:
    return projection["control_authority"]["ledger"]  # type: ignore[index,return-value]


def _row(projection: dict[str, object], entity_id: str, tier: int) -> dict[str, object]:
    return next(row for row in _ledger(projection) if row["entity_id"] == entity_id and row["tier"] == tier)


def _model(projection: dict[str, object], entity_id: str, tier: int) -> dict[str, object]:
    return _row(projection, entity_id, tier)["model"]  # type: ignore[return-value]


def _canonical(projection: dict[str, object], entity_id: str) -> dict[str, object]:
    rows = projection["canonical_inputs"]["entities"]  # type: ignore[index]
    return next(row for row in rows if row["entity_id"] == entity_id)  # type: ignore[return-value]


class ControlAuthorityV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection = load_control_projection_v2()

    def assert_rejected(self, mutate: object, pattern: str | None = None) -> None:
        projection = deepcopy(self.projection)
        mutate(projection)  # type: ignore[operator]
        with self.assertRaises(AuthorityError) as caught:
            validate_control_projection_v2(projection)
        if pattern is not None:
            self.assertRegex(str(caught.exception), pattern)

    def test_real_projection_is_complete_ready_and_versioned(self) -> None:
        self.assertEqual(self.projection["projection_version"], "2.1.0")
        self.assertEqual(self.projection["schema_version"], "3.1.0")
        self.assertEqual(self.projection["control_authority"]["contract_version"], "2.1.0")
        self.assertEqual(self.projection["supported_level_range"], {"minimum": 3, "maximum": 20})
        self.assertEqual(
            self.projection["coverage"],
            {"total": 49, "modeled": 35, "excluded_by_profile": 14, "unsupported_error": 0, "benchmark_ready": True},
        )
        model = ControlAuthorityV2Model(deepcopy(self.projection))
        self.assertEqual((len(model.modeled), len(model.excluded_by_profile), len(model.unsupported)), (35, 14, 0))
        self.assertTrue(model.require_benchmark_ready().benchmark_ready)

    def test_loader_explicitly_requests_2_1_and_is_deterministic(self) -> None:
        with patch("harness.authority._run_projector", return_value=deepcopy(self.projection)) as projector:
            loaded = load_control_projection_v2()
        projector.assert_called_once_with(DEFAULT_AUTHORITY, CONTROL_PROJECTION_VERSION)
        self.assertEqual(loaded, self.projection)
        second = load_control_projection_v2()
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(encode(self.projection), encode(second))

    def test_canonical_inputs_are_sorted_complete_and_drive_policy(self) -> None:
        entities = self.projection["canonical_inputs"]["entities"]
        ids = [row["entity_id"] for row in entities]
        modeled_ids = sorted({row["entity_id"] for row in _ledger(self.projection) if row["disposition"] == "modeled"})
        self.assertEqual(ids, modeled_ids)
        self.assertEqual(_model(self.projection, "forked_lightning", 2)["policy"]["repeatability"], "once_per_turn")
        self.assertEqual(_canonical(self.projection, "forked_lightning")["feature_rule_repeatability"], "once_per_attack_action")
        self.assert_rejected(
            lambda value: _canonical(value, "forked_lightning").__setitem__("psi_cost", 99),
            "derive from canonical",
        )
        self.assert_rejected(
            lambda value: value["canonical_inputs"]["entities"].pop(),
            "canonical input entity universe|lacks projected",
        )

    def test_exact_ledger_and_maintained_exclusions_are_fail_closed(self) -> None:
        keys = [(row["entity_id"], row["tier"]) for row in _ledger(self.projection)]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(any(row["disposition"] == "unsupported_error" for row in _ledger(self.projection)))
        self.assert_rejected(lambda value: _ledger(value).pop(), "at least 49|exactly 49")
        excluded = next(row for row in _ledger(self.projection) if row["disposition"] == "excluded_by_profile")
        self.assert_rejected(
            lambda value: _row(value, excluded["entity_id"], excluded["tier"]).__setitem__("reason", "outside_headline_control_value"),
            "maintained profile exclusion",
        )
        self.assert_rejected(lambda value: value["coverage"].__setitem__("modeled", 34), "does not match ledger count")

    def test_control_count_rejects_ambiguous_exact_proficiency_bonus(self) -> None:
        static = _model(self.projection, "static_discharge", 2)
        secondary = next(selector for selector in static["target_selectors"] if selector["role"] == "secondary")
        self.assertEqual(secondary["count"], {"kind": "up_to_proficiency_bonus"})
        self.assert_rejected(
            lambda value: next(
                selector for selector in _model(value, "static_discharge", 2)["target_selectors"]
                if selector["role"] == "secondary"
            )["count"].__setitem__("kind", "proficiency_bonus"),
            "unsupported value",
        )

    def test_typed_events_save_roles_and_damage_context_are_strict(self) -> None:
        frozen = _model(self.projection, "frozen_ground", 0)
        recurring = next(gate for gate in frozen["resolutions"] if gate["resolution"]["kind"] == "saving_throw")
        self.assertEqual(recurring["resolution"]["role"], "recurring")
        self.assert_rejected(
            lambda value: next(
                gate for gate in _model(value, "frozen_ground", 0)["resolutions"]
                if gate["resolution"]["kind"] == "saving_throw"
            )["resolution"].__setitem__("role", "initial"),
            "recurring timing|initial saves",
        )
        static = _model(self.projection, "static_discharge", 2)
        context = next(gate for gate in static["resolutions"] if gate["resolution"]["kind"] == "damage_context")
        self.assertEqual(context["trigger"], {"kind": "damage_context"})
        self.assert_rejected(
            lambda value: next(
                gate for gate in _model(value, "static_discharge", 2)["resolutions"]
                if gate["resolution"]["kind"] == "damage_context"
            )["resolution"]["branches"][0].__setitem__("outcome", "other"),
            "incomplete damage_context",
        )

    def test_mass_contingent_gates_require_active_elevation_guard(self) -> None:
        for tier in (0, 1, 2):
            model = _model(self.projection, "mass_levitation", tier)
            guarded = [gate for gate in model["resolutions"] if "requires_active_component_ids" in gate]
            self.assertTrue(guarded)
            self.assertTrue(all(gate["requires_active_component_ids"] == ["mass_levitation_persistent_elevation"] for gate in guarded))
        self.assert_rejected(
            lambda value: next(
                gate for gate in _model(value, "mass_levitation", 2)["resolutions"]
                if gate.get("requires_active_component_ids")
            ).pop("requires_active_component_ids"),
            "guarded",
        )

    def test_choices_placement_and_persistent_area_movement_are_strict(self) -> None:
        phase = _model(self.projection, "advanced_phase_step", 2)
        area = next(selector["area"] for selector in phase["target_selectors"] if "area" in selector)
        self.assertEqual(area["placement"]["arrival"]["range"], {"feet": 30, "origin": "departure_space"})
        self.assert_rejected(
            lambda value: next(
                selector["area"] for selector in _model(value, "advanced_phase_step", 2)["target_selectors"]
                if "area" in selector
            )["placement"]["arrival"].__setitem__("occupancy", "not_specified"),
            "unsupported value",
        )
        ball = _model(self.projection, "ball_lightning", 2)
        movement = next(selector["area"]["movement"] for selector in ball["target_selectors"] if "area" in selector)
        self.assertEqual(movement["timing"], {"kind": "turn", "owner": "controller", "turn_anchor": "during"})
        self.assertEqual(movement["distance_mode"], "up_to")
        self.assert_rejected(lambda value: value["control_authority"]["masteries"][1]["component"]["magnitude"].pop("path"), "missing")

    def test_concentration_is_derived_for_frozen_ball_and_mass(self) -> None:
        for entity_id, tier in (("frozen_ground", 0), ("ball_lightning", 2), ("mass_levitation", 2)):
            concentration = _model(self.projection, entity_id, tier)["concentration"]
            self.assertEqual(concentration["kind"], "required")
            self.assertEqual(concentration["startup"], "on_activation")
        self.assert_rejected(
            lambda value: _model(value, "frozen_ground", 0).__setitem__("concentration", {"kind": "none"}),
            "canonical concentration",
        )

    def test_cross_references_graph_and_stacking_fail_closed(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["components"][0]["target_selector_ids"].__setitem__(0, "missing_selector"),
            "unknown selectors",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["relationships"]["replacement_groups"][0]["component_ids"].pop(),
            "must match component declarations",
        )
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["resolutions"][0]["resolution"]["branches"].pop(),
            "incomplete saving_throw",
        )

    def test_root_shape_schema_compatibility_and_snapshot_are_exact(self) -> None:
        self.assert_rejected(lambda value: value.__setitem__("projection_version", "2.0.0"), "version")
        self.assert_rejected(lambda value: value.__setitem__("schema_version", "3.0.0"), "3.1.0")
        self.assert_rejected(lambda value: value.__setitem__("legacy_control_labels", []), "unknown")
        source = deepcopy(self.projection)
        model = ControlAuthorityV2Model(source)
        source["coverage"]["benchmark_ready"] = False
        view = model.projection
        view["coverage"]["benchmark_ready"] = False
        self.assertTrue(model.benchmark_ready)
        self.assertTrue(model.projection["coverage"]["benchmark_ready"])


if __name__ == "__main__":
    unittest.main()
