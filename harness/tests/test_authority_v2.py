from __future__ import annotations

import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from harness.authority import (
    CONTROL_PROJECTION_VERSION,
    DEFAULT_AUTHORITY,
    AuthorityError,
    AuthorityModel,
    ControlAuthorityV2Model,
    load_control_projection_v2,
    load_projection,
    validate_control_projection_v2,
)


def _ledger(projection: dict[str, object]) -> list[dict[str, object]]:
    return projection["control_authority"]["ledger"]  # type: ignore[index,return-value]


def _row(projection: dict[str, object], entity_id: str, tier: int) -> dict[str, object]:
    return next(row for row in _ledger(projection) if row["entity_id"] == entity_id and row["tier"] == tier)


def _model(projection: dict[str, object], entity_id: str, tier: int) -> dict[str, object]:
    return _row(projection, entity_id, tier)["model"]  # type: ignore[return-value]


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

    def test_real_projection_has_exact_current_coverage_and_separate_statuses(self) -> None:
        self.assertEqual(self.projection["projection_version"], "2.0.0")
        self.assertEqual(self.projection["supported_level_range"], {"minimum": 3, "maximum": 20})
        self.assertEqual(
            self.projection["coverage"],
            {
                "total": 49,
                "modeled": 9,
                "excluded_by_profile": 14,
                "unsupported_error": 26,
                "benchmark_ready": False,
            },
        )
        model = ControlAuthorityV2Model(deepcopy(self.projection))
        self.assertEqual(len(model.modeled), 9)
        self.assertEqual(len(model.excluded_by_profile), 14)
        self.assertEqual(len(model.unsupported), 26)
        self.assertTrue(all("profile_id" in row and "model" not in row for row in model.excluded_by_profile))
        self.assertTrue(all("profile_id" not in row and "model" not in row for row in model.unsupported))

    def test_v2_loader_explicitly_requests_v2_and_output_is_deterministic(self) -> None:
        with patch("harness.authority._run_projector", return_value=deepcopy(self.projection)) as projector:
            loaded = load_control_projection_v2()
        projector.assert_called_once_with(DEFAULT_AUTHORITY, CONTROL_PROJECTION_VERSION)
        self.assertEqual(loaded, self.projection)
        second = load_control_projection_v2()
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(encode(self.projection), encode(second))


    def test_root_and_nested_shapes_are_exact_and_versioned(self) -> None:
        self.assert_rejected(lambda value: value.__setitem__("projection_version", "1.0.0"), "version")
        self.assert_rejected(lambda value: value.__setitem__("legacy_control_labels", []), "unknown")
        self.assert_rejected(
            lambda value: value["control_authority"]["active_profile"].__setitem__("label", "official"),
            "unknown",
        )
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["target_selectors"][0]["restrictions"][0].__setitem__(
                "requirement", True
            ),
            "non-empty string",
        )

    def test_stable_ids_integer_tiers_and_exact_ledger_inventory_are_required(self) -> None:
        self.assert_rejected(lambda value: _ledger(value)[0].__setitem__("entity_id", "Bad-ID"), "stable")
        self.assert_rejected(lambda value: _ledger(value)[0].__setitem__("tier", "0"), "integer")
        self.assert_rejected(lambda value: _ledger(value)[0].__setitem__("entity_id", "aaa_zero"), "canonical 49")

    def test_json_integral_numbers_match_schema_integer_semantics(self) -> None:
        integral = deepcopy(self.projection)
        integral["control_authority"]["policy_inputs"]["horizon_rounds"] = 3.0
        _model(integral, "mass_levitation", 0)["target_selectors"][0]["count"]["slots"] = 5.0
        _model(integral, "ball_lightning", 2)["policy"]["overload_tier"] = 2.0
        integral["coverage"]["total"] = 49.0
        self.assertIs(validate_control_projection_v2(integral), integral)

        for invalid in (1.5, float("nan"), float("inf"), float("-inf"), True):
            with self.subTest(invalid=invalid):
                self.assert_rejected(
                    lambda value, candidate=invalid: value["control_authority"]["policy_inputs"].__setitem__(
                        "horizon_rounds", candidate
                    ),
                    "integer",
                )

    def test_ledger_sorting_uniqueness_and_coverage_are_recomputed(self) -> None:
        def reorder(value: dict[str, object]) -> None:
            rows = _ledger(value)
            rows[0], rows[1] = rows[1], rows[0]

        self.assert_rejected(reorder, "sorted")
        self.assert_rejected(
            lambda value: value["coverage"].__setitem__("modeled", value["coverage"]["modeled"] + 1),
            "does not match ledger count",
        )
        self.assert_rejected(lambda value: value["coverage"].__setitem__("benchmark_ready", True), "benchmark_ready")

    def test_magnitudes_are_structured_and_complete(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["components"][0]["magnitude"].__setitem__(
                "kind", "legacy_label"
            ),
            "unsupported value",
        )
        self.assert_rejected(
            lambda value: value["control_authority"]["masteries"][1]["component"]["magnitude"].pop(
                "distance_feet"
            ),
            "missing",
        )
        self.assert_rejected(
            lambda value: value["control_authority"]["masteries"][1]["component"]["magnitude"].__setitem__(
                "direction", "not an id"
            ),
            "unsupported value",
        )
        self.assert_rejected(
            lambda value: value["control_authority"]["masteries"][2]["component"]["magnitude"].pop("count"),
            "missing",
        )
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["components"][1]["magnitude"].__setitem__(
                "count", 1
            ),
            "unknown",
        )

        def legacy_weighted_slots(value: dict[str, object]) -> None:
            count = _model(value, "mass_levitation", 0)["target_selectors"][0]["count"]
            count["slots"] = [{"slot_id": "slot_one", "weight": 1}]

        self.assert_rejected(legacy_weighted_slots, "integer")

        def proficiency_bonus_with_value(value: dict[str, object]) -> None:
            count = _model(value, "ball_lightning", 2)["target_selectors"][0]["count"]
            count["kind"] = "proficiency_bonus"
            count["value"] = 1

        self.assert_rejected(proficiency_bonus_with_value, "unknown")

    def test_timing_owner_and_concentration_lifecycle_are_required(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["components"][0]["duration"].__setitem__(
                "owner", "system"
            ),
            "unsupported value",
        )
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["concentration"]["maximum_duration"].pop("unit"),
            "missing",
        )
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["concentration"]["termination"].pop(),
            "every canonical",
        )

    def test_area_dimensions_and_area_references_are_fail_closed(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["target_selectors"][0]["area"].pop("radius_feet"),
            "incomplete sphere dimensions",
        )
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["components"][0]["duration"].__setitem__(
                "area_id", "missing_area"
            ),
            "unknown area",
        )

    def test_selector_and_resolution_cross_references_are_fail_closed(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["components"][0]["target_selector_ids"].__setitem__(
                0, "missing_selector"
            ),
            "unknown selectors",
        )
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["resolutions"][0]["selector_ids"].append(
                "missing_selector"
            ),
            "unknown selectors",
        )

    def test_resolution_branches_are_complete_and_reference_components(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["resolutions"][0]["resolution"]["branches"].pop(),
            "incomplete saving_throw branches",
        )
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["resolutions"][0]["resolution"]["branches"][0][
                "applies"
            ].append("missing_component"),
            "unknown components",
        )

    def test_inheritance_must_resolve_from_a_lower_tier(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["inheritance"].__setitem__("source_tier", 2),
            "lower canonical tier",
        )

    def test_stacking_replacement_and_dominance_references_are_fail_closed(self) -> None:
        def missing_group(value: dict[str, object]) -> None:
            stacking = _model(value, "ball_lightning", 2)["components"][0]["stacking"]
            stacking["mode"] = "replace"
            stacking["replacement_group"] = "missing_group"

        self.assert_rejected(missing_group, "unknown replacement group")

        def dominance_cycle(value: dict[str, object]) -> None:
            relationships = _model(value, "glacial_spike", 2)["relationships"]
            relationships["dominance"].append({
                "dominant_component_id": "glacial_spike_speed_reduction",
                "suppressed_component_ids": ["glacial_spike_restrained"],
            })

        self.assert_rejected(dominance_cycle, "cycle")

    def test_excluded_profile_and_unsupported_reason_are_not_interchangeable(self) -> None:
        def duplicate_dominant(value: dict[str, object]) -> None:
            relationships = _model(value, "glacial_spike", 2)["relationships"]
            relationships["dominance"].append({
                "dominant_component_id": "glacial_spike_speed_zero",
                "suppressed_component_ids": ["glacial_spike_restrained"],
            })

        self.assert_rejected(duplicate_dominant, "duplicate dominant_component_id")

        excluded = next(row for row in _ledger(self.projection) if row["disposition"] == "excluded_by_profile")
        unsupported = next(row for row in _ledger(self.projection) if row["disposition"] == "unsupported_error")

        def recast_unsupported(value: dict[str, object]) -> None:
            row = _row(value, unsupported["entity_id"], unsupported["tier"])
            row["disposition"] = "excluded_by_profile"
            row["profile_id"] = value["control_authority"]["active_profile"]["id"]
            row["reason"] = "outside_headline_control_value"
            value["coverage"]["excluded_by_profile"] += 1
            value["coverage"]["unsupported_error"] -= 1

        self.assert_rejected(recast_unsupported, "canonical foundation")
        self.assert_rejected(
            lambda value: _row(value, excluded["entity_id"], excluded["tier"]).__setitem__(
                "profile_id", "other_profile"
            ),
            "active profile",
        )
        self.assert_rejected(
            lambda value: _row(value, unsupported["entity_id"], unsupported["tier"]).__setitem__(
                "reason", "excluded_by_profile"
            ),
            "unsupported value",
        )

    def test_tactical_master_choices_reference_exact_mastery_ids(self) -> None:
        self.assert_rejected(
            lambda value: value["control_authority"]["tactical_master"]["choice_mastery_ids"].__setitem__(
                0, "mastery_other"
            ),
            "canonical choices",
        )

    def test_readiness_guard_blocks_current_foundation_and_accepts_mocked_validated_future(self) -> None:
        with self.assertRaisesRegex(AuthorityError, "26 ledger row"):
            ControlAuthorityV2Model(deepcopy(self.projection)).require_benchmark_ready()

        ready = deepcopy(self.projection)
        profile_id = ready["control_authority"]["active_profile"]["id"]
        for row in _ledger(ready):
            if row["disposition"] == "unsupported_error":
                row["disposition"] = "excluded_by_profile"
                row["profile_id"] = profile_id
                row["reason"] = "outside_headline_control_value"
        ready["coverage"].update(modeled=9, excluded_by_profile=40, unsupported_error=0, total=49, benchmark_ready=True)
        with patch("harness.authority.validate_control_projection_v2", return_value=ready):
            future_model = ControlAuthorityV2Model(ready)
        self.assertTrue(future_model.require_benchmark_ready().benchmark_ready)


    def test_resolution_abilities_and_non_save_shape_are_strict(self) -> None:
        wisdom = deepcopy(self.projection)
        _model(wisdom, "forked_lightning", 2)["resolutions"][0]["resolution"]["ability"] = "wisdom"
        self.assertIs(
            validate_control_projection_v2(wisdom),
            wisdom,
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 0)["resolutions"][0]["resolution"].__setitem__(
                "ability", "strength"
            ),
            "unknown",
        )

    def test_attack_scope_numbers_and_movement_modes_fail_closed(self) -> None:
        self.assert_rejected(
            lambda value: value["control_authority"]["masteries"][2]["component"]["magnitude"].pop("scope"),
            "missing",
        )
        for number in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(number=number):
                self.assert_rejected(
                    lambda value, invalid=number: _model(value, "ball_lightning", 2)["components"][0].__setitem__(
                        "magnitude",
                        {"kind": "numerical_modifier", "target": "armor_class", "value": invalid},
                    ),
                    "finite",
                )
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["components"][2]["magnitude"][
                "movement_modes"
            ].__setitem__(0, "all"),
            "unsupported value",
        )

    def test_stacking_modes_and_relationships_are_bidirectionally_consistent(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["components"][0]["stacking"].__setitem__(
                "mode", "replace"
            ),
            "requires replacement_group",
        )
        self.assert_rejected(
            lambda value: _model(value, "ball_lightning", 2)["components"][0]["stacking"].__setitem__(
                "mode", "dominates"
            ),
            "requires explicit edges",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["components"][1]["stacking"].__setitem__(
                "mode", "nonstacking"
            ),
            "edges require replace or dominates",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["relationships"]["replacement_groups"][0][
                "component_ids"
            ].pop(),
            "must match component declarations",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["relationships"]["dominance"][1][
                "suppressed_component_ids"
            ].pop(),
            "must match component declarations",
        )

    def test_branch_transitions_require_matching_component_cadence(self) -> None:
        self.assert_rejected(
            lambda value: _model(value, "forked_lightning", 2)["components"][0]["cadence"].__setitem__(
                "apply", ["hit"]
            ),
            "cadence.apply",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["components"][0]["cadence"].__setitem__(
                "repeat", ["hit"]
            ),
            "cadence.repeat",
        )
        self.assert_rejected(
            lambda value: _model(value, "glacial_spike", 2)["components"][1]["cadence"].__setitem__(
                "end", ["hit"]
            ),
            "cadence.end",
        )

    def test_model_snapshot_cannot_be_mutated_through_public_surfaces(self) -> None:
        source = deepcopy(self.projection)
        model = ControlAuthorityV2Model(source)
        source["coverage"]["benchmark_ready"] = True
        projection_view = model.projection
        projection_view["coverage"]["benchmark_ready"] = True
        contract_view = model.contract
        ledger_view = model.ledger
        next(row for row in contract_view["ledger"] if row["disposition"] == "unsupported_error")[
            "disposition"
        ] = "modeled"

        next(row for row in ledger_view if row["disposition"] == "unsupported_error")["disposition"] = "modeled"

        self.assertFalse(model.benchmark_ready)
        self.assertEqual(len(model.unsupported), 26)
        self.assertFalse(model.projection["coverage"]["benchmark_ready"])
        with self.assertRaisesRegex(AuthorityError, "26 ledger row"):
            model.require_benchmark_ready()

class LegacyAuthorityCompatibilityTests(unittest.TestCase):
    """Keep v1 compatibility evidence separate from the v2 correctness lane."""

    def test_legacy_loader_and_model_remain_on_v1_and_reject_unknown_version(self) -> None:
        legacy = AuthorityModel.load().projection
        self.assertEqual(legacy["projection_version"], "1.0.0")
        self.assertIn("progressions", legacy)
        unknown = deepcopy(legacy)
        unknown["projection_version"] = "9.0.0"
        with patch("harness.authority._run_projector", return_value=unknown):
            with self.assertRaisesRegex(AuthorityError, "Unsupported legacy projection version"):
                load_projection()


if __name__ == "__main__":
    unittest.main()
