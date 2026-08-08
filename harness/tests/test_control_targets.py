from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from harness.control_targets import (
    DEFAULT_CONTROL_PROVENANCE,
    DEFAULT_CONTROL_SUPPLEMENT,
    ControlTarget,
    load_control_targets,
)
from harness.model import DEFAULT_ROSTER, file_sha256, load_targets

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ControlTargetSupplementTests(unittest.TestCase):
    def assert_supplement_rejected(self, mutate: object, pattern: str) -> None:
        value = json.loads(DEFAULT_CONTROL_SUPPLEMENT.read_text(encoding="utf-8"))
        mutate(value)  # type: ignore[operator]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "srd_control_targets.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, pattern):
                load_control_targets(supplement_path=path)

    def test_complete_exact_28_row_join_returns_combined_typed_targets(self) -> None:
        base = load_targets()
        combined = load_control_targets()
        self.assertEqual(len(base), 28)
        self.assertEqual([(row.level, row.name) for row in combined], [(row.level, row.name) for row in base])
        self.assertTrue(all(isinstance(row, ControlTarget) for row in combined))
        for source, result in zip(base, combined, strict=True):
            for field in source.__dataclass_fields__:
                self.assertEqual(getattr(result, field), getattr(source, field))

        by_name = {row.name: row for row in combined}
        self.assertEqual(
            {row.name for row in combined if row.movement.hover},
            {"Air Elemental", "Deva", "Solar"},
        )
        self.assertEqual(by_name["Kraken"].movement.walk_ft, 30)
        self.assertEqual(by_name["Kraken"].movement.swim_ft, 120)
        self.assertEqual(by_name["Tarrasque"].movement.burrow_ft, 40)
        self.assertEqual(by_name["Tarrasque"].movement.climb_ft, 60)
        self.assertEqual(
            [(sense.sense, sense.range_ft, sense.limitation) for sense in by_name["Purple Worm"].nonvisual_senses],
            [("blindsight", 30, None), ("tremorsense", 60, None)],
        )
        self.assertEqual(by_name["Air Elemental"].nonvisual_senses, ())
        self.assertNotIn("darkvision", DEFAULT_CONTROL_SUPPLEMENT.read_text(encoding="utf-8").lower())

    def test_provenance_pins_the_verified_official_source_and_every_row_page(self) -> None:
        provenance = json.loads(DEFAULT_CONTROL_PROVENANCE.read_text(encoding="utf-8"))
        damage_review = json.loads((PROJECT_ROOT / "harness/provenance/damage-review.json").read_text(encoding="utf-8"))
        roster = load_targets()
        supplement = json.loads(DEFAULT_CONTROL_SUPPLEMENT.read_text(encoding="utf-8"))
        self.assertEqual(provenance["source"]["official_pdf_sha256"], damage_review["pinned_srd"]["official_pdf_sha256"])
        self.assertEqual({row.source_url for row in roster}, {provenance["source"]["official_pdf_url"]})
        self.assertEqual(provenance["data_sha256"], file_sha256(DEFAULT_CONTROL_SUPPLEMENT))
        self.assertEqual(provenance["roster_sha256"], file_sha256(DEFAULT_ROSTER))
        self.assertEqual(
            [(row["level"], row["target"], str(row["source_page"])) for row in supplement["targets"]],
            [(row.level, row.name, row.source_page) for row in roster],
        )
        self.assertEqual(provenance["join"]["expected_rows"], 28)
        self.assertEqual(provenance["extraction"]["inference"], "none")
        self.assertEqual(provenance["extraction"]["ordinary_darkvision"], "excluded")

    def test_missing_duplicate_and_extra_join_rows_fail_closed(self) -> None:
        self.assert_supplement_rejected(lambda value: value["targets"].pop(), "missing=.*Tarrasque")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"].append(deepcopy(value["targets"][0])), "duplicate level plus target")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][0].__setitem__("target", "Extra Target"), "extra=.*Extra Target")  # type: ignore[index]

    def test_malformed_and_negative_speeds_fail_closed(self) -> None:
        self.assert_supplement_rejected(lambda value: value["targets"][0]["movement"].__setitem__("walk_ft", "10"), "walk_ft must be a positive integer")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][0]["movement"].__setitem__("fly_ft", -1), "fly_ft must be a positive integer")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][0]["movement"].__setitem__("teleport_ft", 30), "movement keys are invalid")  # type: ignore[index]

    def test_inconsistent_hover_and_unknown_sense_fail_closed(self) -> None:
        self.assert_supplement_rejected(lambda value: value["targets"][1]["movement"].__setitem__("hover", True), "hover requires a fly speed")  # type: ignore[index]
        self.assert_supplement_rejected(
            lambda value: value["targets"][0]["nonvisual_senses"].append({"sense": "darkvision", "range_ft": 60, "limitation": None}),  # type: ignore[index]
            "unknown or is not a supported nonvisual sense: darkvision",
        )

    def test_malformed_ranges_limitations_and_source_pages_fail_closed(self) -> None:
        self.assert_supplement_rejected(lambda value: value["targets"][4]["nonvisual_senses"][0].__setitem__("range_ft", -1), "range_ft must be a positive integer")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][4]["nonvisual_senses"][0].__setitem__("range_ft", "30"), "range_ft must be a positive integer")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][4]["nonvisual_senses"][0].__setitem__("limitation", ""), "limitation must be a non-empty trimmed string")  # type: ignore[index]
        self.assert_supplement_rejected(lambda value: value["targets"][0].__setitem__("source_page", 999), "source_page disagrees")  # type: ignore[index]

    def test_provenance_hashes_are_enforced(self) -> None:
        value = json.loads(DEFAULT_CONTROL_PROVENANCE.read_text(encoding="utf-8"))
        value["data_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "srd-control-targets.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "supplement SHA-256"):
                load_control_targets(provenance_path=path)


if __name__ == "__main__":
    unittest.main()
