from __future__ import annotations

import stat
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from harness import readme_matrices
from harness.authority import AuthorityModel, DEFAULT_AUTHORITY
from harness.comparison_report import COMPARATOR_NOTICE, NOTICE_COLUMNS, matrix_row
from harness.model import (
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_ROSTER,
    file_sha256,
    load_config,
)
from harness.readme_matrices import (
    BEGIN_MARKER,
    END_MARKER,
    MatrixSyncError,
    _markdown_table,
    atomic_replace_text,
    generated_region_span,
    require_unchanged_inputs,
    release_state_line,
    render_balance_region,
    render_control_table,
    render_damage_scope,
    replace_generated_region,
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
    return matrix_row(
        {
            "Level": level,
            "Discipline": discipline,
            "Cluster Size": cluster,
            "Damage Scope": scope,
        },
        kv,
        eldritch_knight,
        battle_master,
        "damage",
    )


def _control_row(
    level: int,
    discipline: str,
    kv: float,
    eldritch_knight: float,
    battle_master: float,
) -> dict[str, str]:
    return matrix_row(
        {
            "Level": level,
            "Discipline": discipline,
            "Metric": "synthetic control reliability %",
        },
        kv,
        eldritch_knight,
        battle_master,
        "control",
    )


def _full_authoritative_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    methodology = config["methodology"]
    profile = str(config["kv_profile"]["id"])
    common = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTER),
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Trial Seed Role": "historical_compatibility_metadata",
        "Provenance Status": str(methodology["status"]),
    }

    damage_rows: list[dict[str, str]] = []
    for level in methodology["levels"]:
        for discipline in sorted(model.disciplines):
            for cluster in methodology["cluster_sizes"]:
                for scope in readme_matrices.DAMAGE_SCOPES:
                    row = matrix_row(
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
                        "damage",
                    )
                    row.update(
                        {
                            **common,
                            "Provenance Trials": str(
                                methodology["damage_default_trials"]
                            ),
                            "Provenance Seed": str(methodology["damage_seed"]),
                            "Provenance Aggregation": (
                                "equal-weight roster means; percentages from displayed aggregates"
                            ),
                            **NOTICE_COLUMNS,
                        }
                    )
                    damage_rows.append(row)

    control_rows: list[dict[str, str]] = []
    for level in methodology["levels"]:
        for discipline in sorted(model.disciplines):
            row = matrix_row(
                {
                    "Level": level,
                    "Discipline": discipline,
                    "Metric": str(config["control_matrix"]["metric"]),
                    "Profile": profile,
                },
                15,
                20,
                10,
                "control",
            )
            row.update(
                {
                    **common,
                    "Provenance Trials": str(methodology["control_default_trials"]),
                    "Provenance Seed": str(methodology["control_seed"]),
                    "Provenance Aggregation": str(
                        config["control_matrix"]["aggregation"]
                    ),
                    **NOTICE_COLUMNS,
                }
            )
            control_rows.append(row)
    return damage_rows, control_rows


class ReadmeMatrixRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.primary_rows = [
            _damage_row("primary-target DPR", 1, 5, 10, 20),
            _damage_row("primary-target DPR", 3, 15, 10, 20),
            _damage_row("primary-target DPR", 6, 25, 10, 20),
        ]
        self.aggregate_rows = [
            _damage_row("aggregate cluster DPR", 1, 31, 40, 60),
            _damage_row("aggregate cluster DPR", 3, 45, 40, 60),
            _damage_row("aggregate cluster DPR", 6, 70, 40, 60),
        ]
        self.damage_rows = self.primary_rows + self.aggregate_rows
        self.control_rows = [
            _control_row(7, "cold_case", 5, 20, 10),
            _control_row(8, "ideal_case", 15, 20, 10),
            _control_row(9, "hot_case", 25, 20, 10),
            _control_row(10, "order_check_case", 15, 10, 20),
            _control_row(11, "undefined_case", 15, 0, 10),
        ]

    def test_damage_scopes_render_exact_c1_c3_c6_triplets_without_blending(self) -> None:
        primary = render_damage_scope(
            list(reversed(self.damage_rows)), "primary-target DPR", (1, 3, 6)
        )
        expected_primary = "\n".join(
            (
                "#### Primary-target DPR",
                "",
                "| Fighter level | Discipline | KV DPR (C1 / C3 / C6) | Eldritch Knight DPR | Battle Master DPR | KV as % of EK (C1 / C3 / C6) | KV as % of BM (C1 / C3 / C6) | Band (C1 / C3 / C6) |",
                "|---|---|---|---|---|---|---|---|",
                "| 7 | Pyrokinesis | 5.000000 / 15.000000 / 25.000000 | 10.000000 | 20.000000 | 50.00 / 150.00 / 250.00 | 25.00 / 75.00 / 125.00 | COLD / IDEAL / HOT |",
            )
        )
        self.assertEqual(primary, expected_primary)
        self.assertEqual(
            render_damage_scope(self.damage_rows, "primary-target DPR", (1, 3, 6)),
            expected_primary,
        )
        self.assertNotIn("31.000000 / 45.000000 / 70.000000", primary)

        aggregate = render_damage_scope(
            self.damage_rows, "aggregate cluster DPR", (1, 3, 6)
        )
        expected_aggregate = "\n".join(
            (
                "#### Aggregate cluster DPR",
                "",
                "| Fighter level | Discipline | KV DPR (C1 / C3 / C6) | Eldritch Knight DPR | Battle Master DPR | KV as % of EK (C1 / C3 / C6) | KV as % of BM (C1 / C3 / C6) | Band (C1 / C3 / C6) |",
                "|---|---|---|---|---|---|---|---|",
                "| 7 | Pyrokinesis | 31.000000 / 45.000000 / 70.000000 | 40.000000 | 60.000000 | 77.50 / 112.50 / 175.00 | 51.67 / 75.00 / 116.67 | COLD / IDEAL / HOT |",
            )
        )
        self.assertEqual(aggregate, expected_aggregate)
        self.assertNotIn("5.000000 / 15.000000 / 25.000000", aggregate)

    def test_damage_renderer_preserves_order_check_and_na_groups(self) -> None:
        rows = [
            *(
                _damage_row(
                    "primary-target DPR",
                    cluster,
                    15,
                    20,
                    10,
                    discipline="order_check_probe",
                )
                for cluster in (1, 3, 6)
            ),
            *(
                _damage_row(
                    "primary-target DPR",
                    cluster,
                    15,
                    0,
                    10,
                    level=8,
                    discipline="undefined_probe",
                )
                for cluster in (1, 3, 6)
            ),
        ]
        rendered = render_damage_scope(rows, "primary-target DPR", (1, 3, 6))
        self.assertIn(
            "| 7 | Order Check Probe | 15.000000 / 15.000000 / 15.000000 | "
            "20.000000 | 10.000000 | 75.00 / 75.00 / 75.00 | "
            "150.00 / 150.00 / 150.00 | ORDER CHECK / ORDER CHECK / ORDER CHECK |",
            rendered,
        )
        self.assertIn(
            "| 8 | Undefined Probe | 15.000000 / 15.000000 / 15.000000 | "
            "0.000000 | 10.000000 | N/A / N/A / N/A | "
            "150.00 / 150.00 / 150.00 | N/A / N/A / N/A |",
            rendered,
        )

    def test_damage_headers_derive_nonstandard_cluster_dimensions(self) -> None:
        rows = [
            _damage_row("primary-target DPR", cluster, 15, 10, 20)
            for cluster in (1, 2, 4)
        ]
        rendered = render_damage_scope(rows, "primary-target DPR", (1, 2, 4))
        self.assertIn("KV DPR (C1 / C2 / C4)", rendered)
        self.assertIn("Band (C1 / C2 / C4)", rendered)
        self.assertNotIn("C1 / C3 / C6", rendered)

    def test_control_table_renders_all_bands_with_ordinary_kv_ratios(self) -> None:
        rendered = render_control_table(list(reversed(self.control_rows)))
        expected = "\n".join(
            (
                "| Fighter level | Discipline | KV control % | Eldritch Knight control % | Battle Master control % | KV as % of EK | KV as % of BM | Band |",
                "|---|---|---|---|---|---|---|---|",
                "| 7 | Cold Case | 5.000000 | 20.000000 | 10.000000 | 25.00 | 50.00 | COLD |",
                "| 8 | Ideal Case | 15.000000 | 20.000000 | 10.000000 | 75.00 | 150.00 | IDEAL |",
                "| 9 | Hot Case | 25.000000 | 20.000000 | 10.000000 | 125.00 | 250.00 | HOT |",
                "| 10 | Order Check Case | 15.000000 | 10.000000 | 20.000000 | 150.00 | 75.00 | ORDER CHECK |",
                "| 11 | Undefined Case | 15.000000 | 0.000000 | 10.000000 | N/A | 150.00 | N/A |",
            )
        )
        self.assertEqual(rendered, expected)
        self.assertEqual(render_control_table(self.control_rows), expected)
        self.assertNotIn("400.00", rendered)
        self.assertEqual(
            {row["Band"] for row in self.control_rows},
            {"COLD", "IDEAL", "HOT", "ORDER CHECK", "N/A"},
        )

    def test_complete_region_is_deterministic_for_reordered_rows(self) -> None:
        readme = "\n".join(
            (
                "# Project",
                "- Current published release: **v14.0.0**",
                "- Current development line: **v14.1.0**",
            )
        )
        arguments = (
            readme,
            self.damage_rows,
            self.control_rows,
            "14.1.0",
            "SYNTHETIC_REVIEW",
            "synthetic_profile",
            (1, 3, 6),
        )
        rendered = render_balance_region(*arguments)
        reordered = render_balance_region(
            readme,
            list(reversed(self.damage_rows)),
            list(reversed(self.control_rows)),
            "14.1.0",
            "SYNTHETIC_REVIEW",
            "synthetic_profile",
            (1, 3, 6),
        )
        self.assertEqual(rendered, reordered)
        self.assertTrue(rendered.startswith(BEGIN_MARKER))
        self.assertTrue(rendered.endswith(END_MARKER))
        self.assertEqual(rendered.count("#### Primary-target DPR"), 1)
        self.assertEqual(rendered.count("#### Aggregate cluster DPR"), 1)
        self.assertIn("Ratios remain ordinary KV/comparator percentages", rendered)
        self.assertIn(COMPARATOR_NOTICE, rendered)
        self.assertIn("[`LICENSE.md`](LICENSE.md)", rendered)
        self.assertIn("[`NOTICE.md`](NOTICE.md)", rendered)

    def test_markdown_table_has_exact_header_width_and_escaping(self) -> None:
        rendered = _markdown_table(("First", "Second"), (("a|b", "line\nbreak"),))
        self.assertEqual(
            rendered,
            "| First | Second |\n|---|---|\n| a\\|b | line break |",
        )
        with self.assertRaisesRegex(MatrixSyncError, "header width"):
            _markdown_table(("First", "Second"), (("only one cell",),))


class ReadmeMatrixDelimiterTests(unittest.TestCase):
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

    def test_generated_region_replacement_preserves_surroundings_and_is_idempotent(self) -> None:
        readme = f"prefix\n{BEGIN_MARKER}\nold\n{END_MARKER}\nsuffix"
        region = f"{BEGIN_MARKER}\nnew\n{END_MARKER}"
        expected = f"prefix\n{BEGIN_MARKER}\nnew\n{END_MARKER}\nsuffix"
        replaced = replace_generated_region(readme, region)
        self.assertEqual(replaced, expected)
        self.assertEqual(replace_generated_region(replaced, region), expected)


class ReadmeMatrixReleaseStateTests(unittest.TestCase):
    def test_development_snapshot_names_canonical_and_published_versions(self) -> None:
        readme = "\n".join(
            (
                "- Current published release: **v14.0.0**",
                "- Current development line: **v14.1.0**",
            )
        )
        self.assertEqual(
            release_state_line(readme, "14.1.0"),
            "**Unreleased development snapshot** — canonical rules **v14.1.0**; current published release **v14.0.0**.",
        )

    def test_published_snapshot_uses_the_canonical_published_version(self) -> None:
        readme = "\n".join(
            (
                "- Current published release: **v14.1.0**",
                "- Current development line: **None**",
            )
        )
        self.assertEqual(
            release_state_line(readme, "14.1.0"),
            "**Published snapshot** — canonical rules **v14.1.0**.",
        )

    def test_duplicate_release_status_lines_fail_closed(self) -> None:
        published = "- Current published release: **v14.0.0**"
        development = "- Current development line: **v14.1.0**"
        cases = (
            "\n".join((published, published, development)),
            "\n".join((published, development, development)),
        )
        for readme in cases:
            with self.subTest(readme=readme):
                with self.assertRaisesRegex(MatrixSyncError, "exactly one"):
                    release_state_line(readme, "14.1.0")

    def test_published_canonical_snapshot_rejects_a_live_development_line(self) -> None:
        for development in ("v14.1.0", "v14.2.0"):
            with self.subTest(development=development):
                readme = "\n".join(
                    (
                        "- Current published release: **v14.1.0**",
                        f"- Current development line: **{development}**",
                    )
                )
                with self.assertRaisesRegex(MatrixSyncError, "requires development line None"):
                    release_state_line(readme, "14.1.0")

    def test_missing_or_unrelated_release_state_fails_closed(self) -> None:
        cases = (
            "- Current published release: **v14.0.0**",
            "\n".join(
                (
                    "- Current published release: **v14.0.0**",
                    "- Current development line: **v14.2.0**",
                )
            ),
        )
        for readme in cases:
            with self.subTest(readme=readme):
                with self.assertRaises(MatrixSyncError):
                    release_state_line(readme, "14.1.0")


class ReadmeMatrixAtomicWriteTests(unittest.TestCase):
    def test_atomic_replace_changes_inode_preserves_mode_and_cleans_temporary_file(self) -> None:
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


class ReadmeMatrixInputStabilityTests(unittest.TestCase):
    def test_unchanged_input_comparison_accepts_equal_fingerprints(self) -> None:
        before = {"README.md": "same", "harness/model.py": "also-same"}
        with patch.object(
            readme_matrices,
            "synchronization_input_fingerprints",
            return_value=dict(before),
        ):
            require_unchanged_inputs(before)

    def test_input_comparison_reports_changed_added_and_removed_paths(self) -> None:
        before = {"changed": "old", "removed": "digest"}
        after = {"added": "digest", "changed": "new"}
        with patch.object(
            readme_matrices,
            "synchronization_input_fingerprints",
            return_value=after,
        ):
            with self.assertRaisesRegex(
                MatrixSyncError, "added, changed, removed"
            ):
                require_unchanged_inputs(before)


class AuthoritativeRowValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.damage_rows, cls.control_rows = _full_authoritative_rows()

    def test_full_current_shape_synthetic_rows_pass(self) -> None:
        model = AuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        self.assertEqual(
            validate_authoritative_rows(self.damage_rows, self.control_rows),
            (
                model.rules_version,
                str(config["methodology"]["status"]),
                str(config["kv_profile"]["id"]),
                tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
            ),
        )

    def test_schema_differences_fail_closed(self) -> None:
        damage = deepcopy(self.damage_rows)
        del damage[0]["Profile"]
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(damage, self.control_rows)

        control = deepcopy(self.control_rows)
        control[0]["Unexpected"] = "field"
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(self.damage_rows, control)

    def test_duplicate_and_missing_identities_fail_closed(self) -> None:
        missing_damage = deepcopy(self.damage_rows[1:])
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            validate_authoritative_rows(missing_damage, self.control_rows)

        duplicate_control = deepcopy(self.control_rows)
        duplicate_control.append(deepcopy(duplicate_control[0]))
        with self.assertRaisesRegex(MatrixSyncError, "duplicate row identities"):
            validate_authoritative_rows(self.damage_rows, duplicate_control)

    def test_provenance_and_notice_mismatches_fail_closed(self) -> None:
        damage = deepcopy(self.damage_rows)
        damage[0]["Provenance Seed"] = "wrong-seed"
        with self.assertRaisesRegex(MatrixSyncError, "Provenance Seed"):
            validate_authoritative_rows(damage, self.control_rows)

        control = deepcopy(self.control_rows)
        notice_field = next(iter(NOTICE_COLUMNS))
        control[0][notice_field] = "changed notice"
        with self.assertRaisesRegex(MatrixSyncError, "changed notice field"):
            validate_authoritative_rows(self.damage_rows, control)

    def test_stale_raw_ratio_and_band_values_fail_closed(self) -> None:
        cases = (
            ("KV", "16.000000"),
            ("KV as % of EK", "999.00"),
            ("Band", "HOT"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                damage = deepcopy(self.damage_rows)
                damage[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, f"stale {field}"):
                    validate_authoritative_rows(damage, self.control_rows)

    def test_retired_comparator_names_fail_after_other_validation(self) -> None:
        damage = deepcopy(self.damage_rows)
        control = deepcopy(self.control_rows)
        notice_field = next(
            field for field in NOTICE_COLUMNS if "Unofficial Comparative" in field
        )
        retired_notice = f"{NOTICE_COLUMNS[notice_field]} Hunter Ranger"
        for row in (*damage, *control):
            row[notice_field] = retired_notice
        with patch.dict(NOTICE_COLUMNS, {notice_field: retired_notice}):
            with self.assertRaisesRegex(MatrixSyncError, "retired comparator"):
                validate_authoritative_rows(damage, control)


if __name__ == "__main__":
    unittest.main()
