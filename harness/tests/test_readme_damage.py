from __future__ import annotations

import json
import re
import stat
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from harness import readme_damage
from harness.authority import DamageAuthorityModel, DEFAULT_AUTHORITY
from harness.damage_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    damage_matrix_row,
)
from harness.model import (
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_ROSTER,
    file_sha256,
    load_config,
)
from harness.readme_damage import (
    BEGIN_MARKER,
    END_MARKER,
    MatrixSyncError,
    README_DISCIPLINES,
    _markdown_table,
    _public_result,
    atomic_replace_text,
    generated_region_span,
    load_damage_review_disposition,
    render_damage_region,
    render_single_target_damage,
    replace_generated_region,
    require_unchanged_inputs,
    validate_authoritative_rows,
)


def _damage_row(
    scope: str,
    cluster: int,
    kv: float,
    eldritch_knight: float,
    battle_master: float,
    *,
    level: int = 7,
    discipline: str = "pyrokinesis",
) -> dict[str, str]:
    return damage_matrix_row(
        {
            "Level": level,
            "Discipline": discipline,
            "Cluster Size": cluster,
            "Damage Scope": scope,
        },
        kv,
        eldritch_knight,
        battle_master,
    )


def _full_authoritative_rows() -> list[dict[str, str]]:
    model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    methodology = config["methodology"]
    profile = str(config["kv_profile"]["id"])
    common = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTER),
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Trials": str(methodology["damage_default_trials"]),
        "Provenance Seed": str(methodology["damage_seed"]),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Trial Seed Role": "historical_compatibility_metadata",
        "Provenance Aggregation": (
            "equal-weight roster means; percentages from displayed aggregates"
        ),
        "Provenance Status": str(methodology["status"]),
    }
    rows: list[dict[str, str]] = []
    for level in methodology["levels"]:
        for discipline in sorted(model.disciplines):
            for cluster in methodology["cluster_sizes"]:
                for scope in readme_damage.DAMAGE_SCOPES:
                    row = damage_matrix_row(
                        {
                            "Level": level,
                            "Discipline": discipline,
                            "Cluster Size": cluster,
                            "Damage Scope": scope,
                            "Profile": profile,
                        },
                        15,
                        10,
                        20,
                    )
                    row.update({**common, **NOTICE_COLUMNS})
                    rows.append(row)
    return rows


class ReadmeDamageRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        values = (
            (5, 10, 20),
            (15, 10, 20),
            (25, 10, 20),
            (15, 20, 10),
        )
        self.damage_rows = [
            _damage_row(scope, cluster, kv, ek, bm, discipline=discipline)
            for scope in readme_damage.DAMAGE_SCOPES
            for cluster in (1, 3, 6)
            for discipline, (kv, ek, bm) in zip(
                README_DISCIPLINES, values, strict=True
            )
        ]

    def test_single_target_damage_renders_one_public_heat_table(self) -> None:
        rendered = render_single_target_damage(list(reversed(self.damage_rows)))
        header = (
            "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | "
            "Electrokinesis |"
        )
        self.assertEqual(rendered.count(header), 1)
        self.assertIn(
            "| 7 | COLD (-50.00%) | IDEAL | HOT (+25.00%) | IDEAL |",
            rendered,
        )
        for forbidden in (
            "KV DPR",
            "KV as %",
            "Eldritch Knight DPR",
            "Battle Master DPR",
            "5.000000",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_single_target_damage_requires_primary_cluster_one(self) -> None:
        rows = [
            _damage_row(
                "primary-target DPR", 2, 15, 10, 20, discipline=discipline
            )
            for discipline in README_DISCIPLINES
        ]
        with self.assertRaisesRegex(MatrixSyncError, "cluster size 1"):
            render_single_target_damage(rows)

    def test_public_result_enforces_band_and_delta_contract(self) -> None:
        ideal = _damage_row("primary-target DPR", 1, 15, 10, 20)
        cold = _damage_row("primary-target DPR", 1, 5, 10, 20)
        hot = _damage_row("primary-target DPR", 1, 25, 10, 20)
        unavailable = _damage_row("primary-target DPR", 1, 15, 0, 20)
        self.assertEqual(_public_result(ideal), "IDEAL")
        self.assertEqual(_public_result(cold), "COLD (-50.00%)")
        self.assertEqual(_public_result(hot), "HOT (+25.00%)")
        self.assertEqual(_public_result(unavailable), "N/A")

        malformed = deepcopy(cold)
        malformed["Boundary Delta %"] = "+50.00"
        with self.assertRaisesRegex(MatrixSyncError, "incorrectly signed"):
            _public_result(malformed)
        malformed = deepcopy(ideal)
        malformed["Band"] = "UNKNOWN"
        with self.assertRaisesRegex(MatrixSyncError, "Unsupported public"):
            _public_result(malformed)

    def test_complete_region_is_deterministic_and_has_exactly_one_table(self) -> None:
        rows = _full_authoritative_rows()
        model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        review = load_damage_review_disposition(
            model.rules_version,
            str(config["methodology"]["status"]),
        )
        arguments = (
            rows,
            model.rules_version,
            review,
            "synthetic_profile",
            tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
        )
        rendered = render_damage_region(*arguments)
        reordered = render_damage_region(
            list(reversed(rows)),
            model.rules_version,
            review,
            "synthetic_profile",
            tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
        )
        self.assertEqual(rendered, reordered)
        self.assertTrue(rendered.startswith(BEGIN_MARKER))
        self.assertTrue(rendered.endswith(END_MARKER))
        self.assertIn("## Damage benchmark snapshot", rendered)
        self.assertIn(
            f"**Current canonical damage authority:** rules "
            f"**v{model.rules_version}**.",
            rendered,
        )
        self.assertIn(
            f"Numerical-review basis: reviewed rules "
            f"**v{review.review_basis_rules_version}** evidence "
            f"(`{review.review_status}`).",
            rendered,
        )
        self.assertIn(
            f"Snapshot values are carried forward from that reviewed evidence and "
            f"were not regenerated for **v{model.rules_version}**. No fresh "
            f"**v{model.rules_version}** full-roster run, numerical certification, "
            "or Monte Carlo certification was performed.",
            rendered,
        )
        self.assertIn(
            "Reason: No intentional change to damage-relevant mechanics or "
            "numerical evaluator semantics.",
            rendered,
        )
        self.assertIn("Generated detailed analytical CSV, Markdown, and HTML reports", rendered)
        self.assertNotIn("Numerical review status:", rendered)
        self.assertFalse(review.fresh_full_roster_run)
        plain_rendered = re.sub(r"[*_`]", "", rendered)
        self.assertNotRegex(
            plain_rendered,
            re.compile(
                rf"\bgenerated\s+under\s+rules\s+v"
                rf"{re.escape(review.current_rules_version)}\b",
                re.IGNORECASE,
            ),
        )
        self.assertFalse(review.fresh_numerical_certification)
        self.assertFalse(review.fresh_monte_carlo_certification)
        with self.assertRaisesRegex(MatrixSyncError, "carried-forward evidence"):
            render_damage_region(
                rows,
                model.rules_version,
                replace(review, fresh_numerical_certification=True),
                "synthetic_profile",
                tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
            )
        self.assertEqual(rendered.count("| Level |"), 1)
        self.assertEqual(rendered.count("\n|---|"), 1)
        self.assertIn("primary-target DPR at cluster size 1", rendered)
        self.assertIn("aggregate-cluster results remain", rendered)
        self.assertIn(COMPARATOR_NOTICE, rendered)
        self.assertIn("LICENSE.md", rendered)
        self.assertIn("NOTICE.md", rendered)

    def test_review_disposition_rejects_stale_current_or_basis_versions(self) -> None:
        source = json.loads(
            readme_damage.DAMAGE_REVIEW_PATH.read_text(encoding="utf-8")
        )
        config = load_config()
        cases = (
            ("current", "current_rules_version", "14.3.0", "canonical rules version"),
            ("basis", "review_basis_rules_version", "14.0.0", "review-basis version"),
        )
        for label, field, value, pattern in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                mutated = deepcopy(source)
                mutated["current_development_disposition"][field] = value
                path = Path(directory) / "damage-review.json"
                path.write_text(json.dumps(mutated), encoding="utf-8")
                with self.assertRaisesRegex(MatrixSyncError, pattern):
                    load_damage_review_disposition(
                        "14.2.0",
                        str(config["methodology"]["status"]),
                        path,
                    )

    def test_markdown_table_has_exact_header_width_and_escaping(self) -> None:
        rendered = _markdown_table(
            ("First", "Second"), (("a|b", "line\nbreak"),)
        )
        self.assertEqual(
            rendered,
            "| First | Second |\n|---|---|\n| a\\|b | line break |",
        )
        with self.assertRaisesRegex(MatrixSyncError, "header width"):
            _markdown_table(("First", "Second"), (("only one cell",),))


class ReadmeDamageDelimiterTests(unittest.TestCase):
    def test_missing_duplicate_and_reversed_markers_fail_closed(self) -> None:
        malformed = {
            "missing both": "README without generated markers",
            "missing begin": f"content\n{END_MARKER}",
            "missing end": f"{BEGIN_MARKER}\ncontent",
            "duplicate begin": f"{BEGIN_MARKER}\n{BEGIN_MARKER}\n{END_MARKER}",
            "duplicate end": f"{BEGIN_MARKER}\n{END_MARKER}\n{END_MARKER}",
            "reversed": f"{END_MARKER}\ncontent\n{BEGIN_MARKER}",
        }
        for label, readme in malformed.items():
            with self.subTest(label=label):
                with self.assertRaises(MatrixSyncError):
                    generated_region_span(readme)

    def test_replacement_preserves_surroundings_and_is_idempotent(self) -> None:
        readme = f"prefix\n{BEGIN_MARKER}\nold\n{END_MARKER}\nsuffix"
        region = f"{BEGIN_MARKER}\nnew\n{END_MARKER}"
        expected = f"prefix\n{BEGIN_MARKER}\nnew\n{END_MARKER}\nsuffix"
        replaced = replace_generated_region(readme, region)
        self.assertEqual(replaced, expected)
        self.assertEqual(replace_generated_region(replaced, region), expected)


class ReadmeDamageAtomicWriteTests(unittest.TestCase):
    def test_atomic_replace_changes_inode_preserves_mode_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text("before", encoding="utf-8")
            path.chmod(0o640)
            original_inode = path.stat().st_ino

            atomic_replace_text(path, "before", "after\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "after\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertNotEqual(path.stat().st_ino, original_inode)
            self.assertEqual([item.name for item in root.iterdir()], ["README.md"])

    def test_atomic_replace_refuses_stale_expected_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text("concurrent edit", encoding="utf-8")
            with self.assertRaisesRegex(MatrixSyncError, "concurrently changed"):
                atomic_replace_text(path, "expected old text", "replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "concurrent edit")

    def test_atomic_replace_rechecks_source_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text("before", encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=("before", "changed")):
                with self.assertRaisesRegex(MatrixSyncError, "concurrently changed"):
                    atomic_replace_text(path, "before", "replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "before")
            self.assertEqual([item.name for item in root.iterdir()], ["README.md"])


class ReadmeDamageInputStabilityTests(unittest.TestCase):
    def test_unchanged_inputs_are_accepted(self) -> None:
        before = {"README.md": "same", "harness/model.py": "also-same"}
        with patch.object(
            readme_damage,
            "synchronization_input_fingerprints",
            return_value=dict(before),
        ):
            require_unchanged_inputs(before)

    def test_changed_added_and_removed_inputs_fail_closed(self) -> None:
        before = {"changed": "old", "removed": "digest"}
        after = {"added": "digest", "changed": "new"}
        with patch.object(
            readme_damage,
            "synchronization_input_fingerprints",
            return_value=after,
        ):
            with self.assertRaisesRegex(MatrixSyncError, "added, changed, removed"):
                require_unchanged_inputs(before)


class AuthoritativeDamageRowValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = _full_authoritative_rows()

    def test_full_current_shape_synthetic_rows_pass(self) -> None:
        model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        self.assertEqual(
            validate_authoritative_rows(self.rows),
            (
                model.rules_version,
                str(config["methodology"]["status"]),
                str(config["kv_profile"]["id"]),
                tuple(
                    int(value) for value in config["methodology"]["cluster_sizes"]
                ),
                README_DISCIPLINES,
            ),
        )

    def test_schema_differences_fail_closed(self) -> None:
        rows = deepcopy(self.rows)
        del rows[0]["Profile"]
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(rows)

        rows = deepcopy(self.rows)
        rows[0]["Unexpected"] = "field"
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(rows)

    def test_duplicate_and_missing_identities_fail_closed(self) -> None:
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            validate_authoritative_rows(deepcopy(self.rows[1:]))

        rows = deepcopy(self.rows)
        rows.append(deepcopy(rows[0]))
        with self.assertRaisesRegex(MatrixSyncError, "duplicate row identities"):
            validate_authoritative_rows(rows)

    def test_provenance_and_notice_mismatches_fail_closed(self) -> None:
        rows = deepcopy(self.rows)
        rows[0]["Provenance Seed"] = "wrong-seed"
        with self.assertRaisesRegex(MatrixSyncError, "Provenance Seed"):
            validate_authoritative_rows(rows)

        rows = deepcopy(self.rows)
        notice_field = next(iter(NOTICE_COLUMNS))
        rows[0][notice_field] = "changed notice"
        with self.assertRaisesRegex(MatrixSyncError, "changed notice field"):
            validate_authoritative_rows(rows)

    def test_stale_result_and_boundary_evidence_fails_closed(self) -> None:
        cases = (
            ("Benchmark Type", "Other"),
            ("KV", "16.000000"),
            ("KV as % of EK", "999.00"),
            ("Lower Comparator", "Battle Master"),
            ("Lower Boundary", "999.000000"),
            ("Upper Comparator", "Eldritch Knight"),
            ("Upper Boundary", "999.000000"),
            ("Band", "HOT"),
            ("Boundary Delta %", "+1.00"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                rows = deepcopy(self.rows)
                rows[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, f"stale {field}"):
                    validate_authoritative_rows(rows)

if __name__ == "__main__":
    unittest.main()
