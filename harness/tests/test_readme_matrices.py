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
    DEFAULT_CATALOG,
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_ROSTERS,
    file_sha256,
    load_config,
)
from harness.readme_matrices import (
    BEGIN_MARKER,
    END_MARKER,
    MatrixSyncError,
    README_DISCIPLINES,
    _markdown_table,
    _public_result,
    atomic_replace_text,
    generated_region_span,
    release_state_line,
    render_balance_region,
    render_control_table,
    render_single_target_damage,
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
        "Provenance Catalog Sha256": file_sha256(DEFAULT_CATALOG),
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTERS),
        "Provenance Target Profile": DEFAULT_PROFILE,
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
        primary_values = {
            1: ((5,10,20),(15,10,20),(25,10,20),(15,20,10)),
            3: ((15,10,20),(15,10,20),(15,10,20),(15,20,10)),
            6: ((8,10,20),(24,10,20),(10,10,20),(20,20,10)),
        }
        aggregate_values = {
            1: ((31,40,60),(45,40,60),(70,40,60),(50,60,40)),
            3: ((45,40,60),(45,40,60),(45,40,60),(50,60,40)),
            6: ((35,40,60),(66,40,60),(40,40,60),(60,60,40)),
        }
        self.damage_rows = []
        for scope,values_by_cluster in (
            ("primary-target DPR",primary_values),
            ("aggregate cluster DPR",aggregate_values),
        ):
            for cluster,values in values_by_cluster.items():
                for discipline,(kv,ek,bm) in zip(README_DISCIPLINES,values,strict=True):
                    self.damage_rows.append(
                        _damage_row(scope,cluster,kv,ek,bm,discipline=discipline)
                    )
        control_values = {
            7: ((5,10,20),(15,10,20),(25,10,20),(15,20,10)),
            11: ((15,10,20),(15,10,20),(15,10,20),(15,0,10)),
        }
        self.control_rows = [
            _control_row(level,discipline,kv,ek,bm)
            for level,values in control_values.items()
            for discipline,(kv,ek,bm) in zip(README_DISCIPLINES,values,strict=True)
        ]

    def test_single_target_damage_renders_one_public_heat_matrix(self) -> None:
        rendered=render_single_target_damage(list(reversed(self.damage_rows)))
        header="| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |"
        self.assertEqual(rendered.count(header),1)
        self.assertIn(
            "| 7 | COLD (-50.00%) | IDEAL | HOT (+25.00%) | IDEAL |",
            rendered,
        )
        self.assertNotIn("COLD (-22.50%)",rendered)
        for forbidden in ("KV DPR","KV as %","Eldritch Knight DPR","Battle Master DPR","ORDER CHECK","5.000000"):
            self.assertNotIn(forbidden,rendered)

    def test_single_target_damage_requires_primary_cluster_one(self) -> None:
        rows=[
            _damage_row(
                "primary-target DPR",2,15,10,20,discipline=discipline
            )
            for discipline in README_DISCIPLINES
        ]
        with self.assertRaisesRegex(MatrixSyncError,"cluster size 1"):
            render_single_target_damage(rows)

    def test_control_table_is_level_by_discipline_and_public_only(self) -> None:
        rendered=render_control_table(list(reversed(self.control_rows)))
        expected="\n".join(
            (
                "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |",
                "|---|---|---|---|---|",
                "| 7 | COLD (-50.00%) | IDEAL | HOT (+25.00%) | IDEAL |",
                "| 11 | IDEAL | IDEAL | IDEAL | N/A |",
            )
        )
        self.assertEqual(rendered,expected)
        for forbidden in ("KV control","KV as %","Eldritch Knight","Battle Master","ORDER CHECK"):
            self.assertNotIn(forbidden,rendered)
        self.assertNotIn("IDEAL (",rendered)

    def test_public_result_enforces_band_and_delta_contract(self) -> None:
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,15,10,20)),"IDEAL")
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,5,10,20)),"COLD (-50.00%)")
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,25,10,20)),"HOT (+25.00%)")
        unavailable=_damage_row("primary-target DPR",1,15,0,20)
        self.assertEqual(_public_result(unavailable),"N/A")
        malformed=_damage_row("primary-target DPR",1,5,10,20);malformed["Boundary Delta %"]="+50.00"
        with self.assertRaisesRegex(MatrixSyncError,"incorrectly signed"):
            _public_result(malformed)
        retired=_damage_row("primary-target DPR",1,15,10,20);retired["Band"]="ORDER CHECK"
        with self.assertRaisesRegex(MatrixSyncError,"Unsupported public"):
            _public_result(retired)

    def test_complete_region_is_deterministic_transposed_and_minimal(self) -> None:
        damage_rows,control_rows=_full_authoritative_rows()
        readme="\n".join(
            (
                "# Project",
                "- Current published release: **v14.0.0**",
                "- Current development line: **v14.1.0**",
            )
        )
        arguments=(
            readme,damage_rows,control_rows,"14.1.0","SYNTHETIC_REVIEW",
            "synthetic_profile",(1,3,6),
        )
        rendered=render_balance_region(*arguments)
        reordered=render_balance_region(
            readme,list(reversed(damage_rows)),list(reversed(control_rows)),
            "14.1.0","SYNTHETIC_REVIEW","synthetic_profile",(1,3,6),
        )
        self.assertEqual(rendered,reordered)
        self.assertTrue(rendered.startswith(BEGIN_MARKER))
        self.assertTrue(rendered.endswith(END_MARKER))
        self.assertEqual(rendered.count("| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |"),2)
        for heading in ("### Single-Target Damage","### Control Reliability"):
            self.assertIn(heading,rendered)
        self.assertIn("This single-target benchmark evaluates each configured control package",rendered)
        self.assertNotIn("### Cluster / Aggregate Damage",rendered)
        self.assertIn("All other primary-target and aggregate-cluster results remain in the generated detailed release reports",rendered)
        limitation=("Control Reliability measures how often the configured control package takes effect. "
                    "It does not measure the relative severity, duration, area, or strategic value of different control effects. "
                    "A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered.")
        self.assertIn(limitation,rendered)
        for forbidden in ("ORDER CHECK","KV DPR","KV as % of EK","KV as % of BM","KV control %"):
            self.assertNotIn(forbidden,rendered)
        self.assertIn(COMPARATOR_NOTICE,rendered)
        self.assertIn("LICENSE.md",rendered)
        self.assertIn("NOTICE.md",rendered)

    def test_markdown_table_has_exact_header_width_and_escaping(self) -> None:
        rendered=_markdown_table(("First","Second"),(("a|b","line\nbreak"),))
        self.assertEqual(rendered,"| First | Second |\n|---|---|\n| a\\|b | line break |")
        with self.assertRaisesRegex(MatrixSyncError,"header width"):
            _markdown_table(("First","Second"),(("only one cell",),))


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
                DEFAULT_PROFILE,
                tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
                README_DISCIPLINES,
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

    def test_catalog_roster_and_target_profile_provenance_fail_closed(self) -> None:
        cases = (
            ("Provenance Catalog Sha256", "wrong-catalog"),
            ("Provenance Roster Sha256", "wrong-roster"),
            ("Provenance Target Profile", "legacy_v14_1"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                damage = deepcopy(self.damage_rows)
                damage[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, field):
                    validate_authoritative_rows(damage, self.control_rows)

    def test_stale_result_and_boundary_evidence_fails_closed(self) -> None:
        cases = (
            ("Benchmark Type", "Control Reliability"),
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
