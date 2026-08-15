from __future__ import annotations

import csv
import json
import re
import stat
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from harness import readme_damage
from harness.authority import DamageAuthorityModel, DEFAULT_AUTHORITY
from harness.damage_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    damage_matrix_row,
)
from harness.model import file_sha256, load_config
from harness.readme_damage import (
    BEGIN_MARKER,
    CARRIED_FORWARD_REVIEW,
    EXPANDED_ROSTER_BASELINE_EVIDENCE,
    EXPANDED_ROSTER_BASELINE_EVIDENCE_SHA256,
    END_MARKER,
    FRESH_EXPANDED_ROSTER_REVIEW,
    INVALIDATED_NUMERICAL_EVIDENCE_ROLE,
    INVALIDATED_PREMERGE_REVIEW,
    PROVENANCE_FIELDS,
    DamageOutputSha256,
    DamageReviewDisposition,
    DamageRowCounts,
    FreshRunEvidence,
    InvalidatedRunEvidence,
    MatrixSyncError,
    README_DISCIPLINES,
    VerifiedDamageRun,
    _markdown_table,
    _public_result,
    atomic_replace_text,
    fresh_run_evidence_from_verified,
    generated_region_span,
    load_damage_review_disposition,
    load_verified_damage_run,
    render_damage_region,
    render_single_target_damage,
    replace_generated_region,
    require_unchanged_inputs,
    validate_authoritative_rows,
    validate_damage_review_run_evidence,
)


EXPECTED_PROVENANCE_FIELDS = (
    "Provenance Damage Result Contract Version",
    "Provenance Damage Model Mode Id",
    "Provenance Target Knowledge Contract Id",
    "Provenance Numeric Representation Id",
    "Provenance Provider Ids",
    "Provenance Rules Version",
    "Provenance Authority Sha256",
    "Provenance Authority Projection Sha256",
    "Provenance Catalog Contract Version",
    "Provenance Catalog Sha256",
    "Provenance Roster Contract Version",
    "Provenance Roster Sha256",
    "Provenance Target Profile Id",
    "Provenance Target Profile Version",
    "Provenance Target Profile Sha256",
    "Provenance Damage Target Projection Id",
    "Provenance Damage Target Projection Version",
    "Provenance Damage Target Projection Sha256",
    "Provenance Consumer Requirements Version",
    "Provenance Damage Consumer Requirements Sha256",
    "Provenance Config Sha256",
    "Provenance Comparator Config Sha256",
    "Provenance Damage Model Contract Sha256",
    "Provenance Sentinel Corpus Sha256",
    "Provenance Sentinel Corpus File Sha256",
    "Provenance Observation Policy Sha256",
    "Provenance Resource Policy Sha256",
    "Provenance Optimization Policy Sha256",
    "Provenance Evaluator",
    "Provenance Evaluator Implementation Sha256",
    "Provenance Semantic Implementation Sha256",
    "Provenance Orchestration Implementation Sha256",
    "Provenance Reporter Implementation Sha256",
    "Provenance Trials",
    "Provenance Seed",
    "Provenance Trial Seed Role",
    "Provenance Aggregation",
    "Provenance Status",
)


@cache
def _current_damage_bundle() -> object:
    config = load_config()
    methodology = config["methodology"]
    return readme_damage.load_damage_input_bundle(
        DEFAULT_AUTHORITY,
        {int(value) for value in methodology["levels"]},
        int(methodology["damage_default_trials"]),
        int(methodology["damage_seed"]),
    )


def _synthetic_verified_run(
    manifest_sha256: str = "c" * 64,
    *,
    inputs: dict[str, object] | None = None,
    rows: tuple[dict[str, str], ...] = ({"sentinel": "reused"},),
) -> VerifiedDamageRun:
    identity = (
        dict(_current_damage_bundle().identity) if inputs is None else dict(inputs)
    )
    return VerifiedDamageRun(
        manifest_path=Path("run-manifest.json"),
        manifest_sha256=manifest_sha256,
        inputs=identity,
        target_count=47,
        matrix_path=Path("matrix.csv"),
        rows=rows,
        output_sha256=DamageOutputSha256(
            detail_csv="1" * 64,
            matrix_csv="2" * 64,
            matrix_markdown="3" * 64,
            matrix_html="4" * 64,
        ),
        row_counts=DamageRowCounts(detail=564, matrix=96),
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


def _full_authoritative_rows(
    expected_inputs: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    methodology = config["methodology"]
    profile = str(config["kv_profile"]["id"])
    identity = (
        dict(_current_damage_bundle().identity)
        if expected_inputs is None
        else expected_inputs
    )
    common = {
        f"Provenance {str(key).replace('_', ' ').title()}": str(value)
        for key, value in identity.items()
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


def _synthetic_review(
    disposition: str,
    verified: VerifiedDamageRun | None = None,
) -> DamageReviewDisposition:
    current = DamageAuthorityModel.load(DEFAULT_AUTHORITY).rules_version
    fresh = disposition == FRESH_EXPANDED_ROSTER_REVIEW
    verified = _synthetic_verified_run() if fresh and verified is None else verified
    preserve_invalidated = disposition in {
        INVALIDATED_PREMERGE_REVIEW,
        FRESH_EXPANDED_ROSTER_REVIEW,
    }
    current_review = (
        load_damage_review_disposition(
            current,
            str(load_config()["methodology"]["status"]),
        )
        if preserve_invalidated
        else None
    )
    return DamageReviewDisposition(
        expanded_roster_baseline_evidence=EXPANDED_ROSTER_BASELINE_EVIDENCE,
        current_rules_version=current,
        review_basis_rules_version="14.1.0",
        review_status=str(load_config()["methodology"]["status"]),
        review_disposition=disposition,
        fresh_full_roster_run=fresh,
        fresh_numerical_certification=False,
        fresh_monte_carlo_certification=False,
        reason="Synthetic disposition reason.",
        durable_record="Synthetic test record.",
        invalidated_run_evidence=(
            current_review.invalidated_run_evidence
            if current_review is not None
            else None
        ),
        fresh_run_evidence=(
            fresh_run_evidence_from_verified(
                EXPANDED_ROSTER_BASELINE_EVIDENCE,
                verified,
            )
            if fresh and verified is not None
            else None
        ),
    )


def _write_verified_run_fixture(
    root: Path,
) -> tuple[Path, list[dict[str, str]], dict[str, object]]:
    bundle = _current_damage_bundle()
    identity = dict(bundle.identity)
    rows = _full_authoritative_rows(identity)
    outputs = {
        "detail_csv": root / "detail.csv",
        "matrix_csv": root / "matrix.csv",
        "matrix_markdown": root / "matrix.md",
        "matrix_html": root / "matrix.html",
    }
    outputs["detail_csv"].write_text("synthetic detail\n", encoding="utf-8")
    with outputs["matrix_csv"].open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    outputs["matrix_markdown"].write_text("synthetic markdown\n", encoding="utf-8")
    outputs["matrix_html"].write_text("synthetic html\n", encoding="utf-8")

    config = load_config()
    manifest = {
        "format_version": 2,
        "damage_result_contract_version": identity[
            "damage_result_contract_version"
        ],
        "inputs": identity,
        "outputs": {
            name: {"file": path.name, "sha256": file_sha256(path)}
            for name, path in sorted(outputs.items())
        },
        "row_counts": {
            "detail": (
                len(bundle.entries)
                * len(bundle.model.disciplines)
                * len(config["methodology"]["cluster_sizes"])
            ),
            "matrix": len(rows),
        },
    }
    manifest_path = root / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path, rows, manifest


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
        review = _synthetic_review(CARRIED_FORWARD_REVIEW)
        bundle = _current_damage_bundle()
        arguments = (
            rows,
            model.rules_version,
            review,
            "synthetic_profile",
            str(bundle.identity["target_profile_id"]),
            len(bundle.entries),
            "a" * 64,
            tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
        )
        rendered = render_damage_region(*arguments)
        reordered = render_damage_region(list(reversed(rows)), *arguments[1:])
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
            "Target profile: `srd521_headline_source_diversity_v1` "
            "(47 source-ordered targets).",
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
            "Reason: Synthetic disposition reason.",
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
        with self.assertRaisesRegex(MatrixSyncError, "Carried-forward.*inconsistent"):
            render_damage_region(
                rows,
                model.rules_version,
                replace(review, fresh_numerical_certification=True),
                "synthetic_profile",
                str(bundle.identity["target_profile_id"]),
                len(bundle.entries),
                "a" * 64,
                tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
            )
        self.assertEqual(rendered.count("| Level |"), 1)
        self.assertEqual(rendered.count("\n|---|"), 1)
        self.assertIn("primary-target DPR at cluster size 1", rendered)
        self.assertIn("aggregate-cluster results remain", rendered)
        self.assertIn(COMPARATOR_NOTICE, rendered)
        self.assertIn("LICENSE.md", rendered)
        self.assertIn("NOTICE.md", rendered)

    def test_fresh_expanded_roster_disposition_is_rendered_without_certification(self) -> None:
        model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        bundle = _current_damage_bundle()
        manifest_sha256 = "b" * 64
        verified = _synthetic_verified_run(manifest_sha256)
        review = _synthetic_review(FRESH_EXPANDED_ROSTER_REVIEW, verified)
        invalidated = review.invalidated_run_evidence
        self.assertIsNotNone(invalidated)
        rendered = render_damage_region(
            _full_authoritative_rows(),
            model.rules_version,
            review,
            "synthetic_profile",
            str(bundle.identity["target_profile_id"]),
            len(bundle.entries),
            manifest_sha256,
            tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
        )
        self.assertIn(
            "A corrected-contract replacement exact analytical run for "
            f"**v{model.rules_version}** used all "
            "47 targets in `srd521_headline_source_diversity_v1`.",
            rendered,
        )
        self.assertIn(f"`{INVALIDATED_PREMERGE_REVIEW}`", rendered)
        self.assertIn(
            "prior manifest SHA-256 "
            f"`{invalidated.run_manifest_sha256}`",
            rendered,
        )
        self.assertIn(
            "No fresh independent numerical or Monte Carlo certification", rendered
        )
        self.assertIn(f"Run-manifest SHA-256: `{manifest_sha256}`.", rendered)
        self.assertNotIn("were not regenerated", rendered)

    def test_invalidated_premerge_disposition_is_rendered_as_comparison_only(
        self,
    ) -> None:
        model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        bundle = _current_damage_bundle()
        review = _synthetic_review(INVALIDATED_PREMERGE_REVIEW)
        invalidated = review.invalidated_run_evidence
        self.assertIsNotNone(invalidated)
        rendered = render_damage_region(
            _full_authoritative_rows(),
            model.rules_version,
            review,
            "synthetic_profile",
            str(bundle.identity["target_profile_id"]),
            len(bundle.entries),
            "b" * 64,
            tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
        )
        self.assertIn(f"`{INVALIDATED_PREMERGE_REVIEW}`", rendered)
        self.assertIn(
            f"Its manifest SHA-256 is `{invalidated.run_manifest_sha256}`.",
            rendered,
        )
        self.assertIn("retained only as comparison evidence", rendered)
        self.assertIn("no numerical defect has been demonstrated", rendered)
        self.assertIn(
            f"No corrected-contract replacement **v{model.rules_version}** "
            "full-roster run has been performed.",
            rendered,
        )
        self.assertNotIn("replacement exact analytical run", rendered)
        self.assertNotIn("`" + "b" * 64 + "`", rendered)

    def test_review_disposition_rejects_stale_current_or_basis_versions(self) -> None:
        source = json.loads(
            readme_damage.DAMAGE_REVIEW_PATH.read_text(encoding="utf-8")
        )
        config = load_config()
        current_rules_version = DamageAuthorityModel.load(
            DEFAULT_AUTHORITY
        ).rules_version
        cases = (
            ("current", "current_rules_version", "0.0.0", "canonical rules version"),
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
                        current_rules_version,
                        str(config["methodology"]["status"]),
                        path,
                    )

    def test_review_loader_accepts_only_coherent_review_timeline_dispositions(
        self,
    ) -> None:
        source = json.loads(
            readme_damage.DAMAGE_REVIEW_PATH.read_text(encoding="utf-8")
        )
        current_rules_version = DamageAuthorityModel.load(
            DEFAULT_AUTHORITY
        ).rules_version
        status = str(load_config()["methodology"]["status"])

        def load(mutated: dict[str, object]) -> DamageReviewDisposition:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "damage-review.json"
                path.write_text(json.dumps(mutated), encoding="utf-8")
                return load_damage_review_disposition(
                    current_rules_version,
                    status,
                    path,
                )

        carried = deepcopy(source)
        carried_row = carried["current_development_disposition"]
        carried_row.update(
            {
                "current_rules_version": current_rules_version,
                "review_disposition": CARRIED_FORWARD_REVIEW,
                "fresh_full_roster_run": False,
                "fresh_numerical_certification": False,
                "fresh_monte_carlo_certification": False,
                "invalidated_run_evidence": None,
                "fresh_run_evidence": None,
            }
        )
        loaded_carried = load(carried)
        self.assertEqual(loaded_carried.review_disposition, CARRIED_FORWARD_REVIEW)
        self.assertEqual(
            loaded_carried.expanded_roster_baseline_evidence,
            EXPANDED_ROSTER_BASELINE_EVIDENCE,
        )
        self.assertIsNone(loaded_carried.fresh_run_evidence)

        fresh = deepcopy(carried)
        fresh_row = fresh["current_development_disposition"]
        fresh_row["review_disposition"] = FRESH_EXPANDED_ROSTER_REVIEW
        fresh_row["fresh_full_roster_run"] = True
        fresh_row["invalidated_run_evidence"] = deepcopy(
            source["current_development_disposition"][
                "invalidated_run_evidence"
            ]
        )
        fresh_row["fresh_run_evidence"] = asdict(
            fresh_run_evidence_from_verified(
                EXPANDED_ROSTER_BASELINE_EVIDENCE,
                _synthetic_verified_run(),
            )
        )
        loaded_fresh = load(fresh)
        self.assertEqual(
            loaded_fresh.review_disposition, FRESH_EXPANDED_ROSTER_REVIEW
        )
        self.assertTrue(loaded_fresh.fresh_full_roster_run)
        self.assertFalse(loaded_fresh.fresh_numerical_certification)
        self.assertFalse(loaded_fresh.fresh_monte_carlo_certification)
        self.assertIsInstance(loaded_fresh.fresh_run_evidence, FreshRunEvidence)
        self.assertIsInstance(
            loaded_fresh.invalidated_run_evidence,
            InvalidatedRunEvidence,
        )

        invalidated = deepcopy(source)
        invalidated_row = invalidated["current_development_disposition"]
        invalidated_row["review_disposition"] = INVALIDATED_PREMERGE_REVIEW
        invalidated_row["fresh_full_roster_run"] = False
        invalidated_row["fresh_run_evidence"] = None
        loaded_invalidated = load(invalidated)
        self.assertEqual(
            loaded_invalidated.review_disposition,
            INVALIDATED_PREMERGE_REVIEW,
        )
        self.assertFalse(loaded_invalidated.fresh_full_roster_run)
        self.assertIsNone(loaded_invalidated.fresh_run_evidence)
        self.assertIsInstance(
            loaded_invalidated.invalidated_run_evidence,
            InvalidatedRunEvidence,
        )

        invalid_cases = (
            (carried, "fresh_full_roster_run", True, "cannot claim a fresh run"),
            (fresh, "fresh_full_roster_run", False, "requires a fresh full-roster run"),
            (
                fresh,
                "fresh_numerical_certification",
                True,
                "cannot claim independent or Monte Carlo certification",
            ),
            (
                fresh,
                "fresh_monte_carlo_certification",
                True,
                "cannot claim independent or Monte Carlo certification",
            ),
            (
                carried,
                "fresh_run_evidence",
                fresh_row["fresh_run_evidence"],
                "requires null fresh_run_evidence",
            ),
            (
                fresh,
                "fresh_run_evidence",
                None,
                "requires fresh_run_evidence",
            ),
            (
                invalidated,
                "fresh_full_roster_run",
                True,
                "cannot claim a fresh run",
            ),
            (
                invalidated,
                "invalidated_run_evidence",
                None,
                "requires invalidated_run_evidence",
            ),
            (
                fresh,
                "invalidated_run_evidence",
                None,
                "must preserve invalidated_run_evidence",
            ),
        )
        for base, field, value, pattern in invalid_cases:
            with self.subTest(field=field):
                mutated = deepcopy(base)
                mutated["current_development_disposition"][field] = value
                with self.assertRaisesRegex(MatrixSyncError, pattern):
                    load(mutated)

        unknown_fresh_key = deepcopy(fresh)
        unknown_fresh_key["current_development_disposition"][
            "fresh_run_evidence"
        ]["unexpected"] = True
        with self.assertRaisesRegex(MatrixSyncError, "fresh_run_evidence keys"):
            load(unknown_fresh_key)

        unknown_invalidated_key = deepcopy(invalidated)
        unknown_invalidated_key["current_development_disposition"][
            "invalidated_run_evidence"
        ]["unexpected"] = True
        with self.assertRaisesRegex(MatrixSyncError, "invalidated_run_evidence keys"):
            load(unknown_invalidated_key)

        rewritten_invalidated = deepcopy(invalidated)
        rewritten_invalidated["current_development_disposition"][
            "invalidated_run_evidence"
        ]["run_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(MatrixSyncError, "preserved pre-correction record"):
            load(rewritten_invalidated)

    def test_current_fresh_evidence_preserves_original_run_as_comparison(
        self,
    ) -> None:
        source = json.loads(
            readme_damage.DAMAGE_REVIEW_PATH.read_text(encoding="utf-8")
        )
        pinned = source["pinned_srd"]
        current = source["current_development_disposition"]
        invalidated = current["invalidated_run_evidence"]
        fresh = current["fresh_run_evidence"]
        self.assertEqual(
            current["review_disposition"], FRESH_EXPANDED_ROSTER_REVIEW
        )
        self.assertTrue(current["fresh_full_roster_run"])
        self.assertFalse(current["fresh_numerical_certification"])
        self.assertFalse(current["fresh_monte_carlo_certification"])
        self.assertIsNotNone(fresh)
        self.assertEqual(
            invalidated["invalidation_disposition"],
            INVALIDATED_PREMERGE_REVIEW,
        )
        self.assertEqual(
            invalidated["numerical_evidence_role"],
            INVALIDATED_NUMERICAL_EVIDENCE_ROLE,
        )
        self.assertFalse(invalidated["numerical_defect_demonstrated"])
        self.assertEqual(
            invalidated["run_manifest_sha256"],
            "a6ad2a6ca1b56c08ce95668f0825d2959d7b8f3ea8dd2f10b498d3536a25e1b8",
        )
        self.assertEqual(
            invalidated["consumer_requirements_sha256"],
            "b3aebbf3e6a9ec6dcf26b2427bfa607a0b8ee9bd31b288c1372ed489820d971d",
        )
        self.assertEqual(
            invalidated["output_sha256"],
            {
                "detail_csv": "6147aca22e5881741628dcdc5527175facd1107b98e66eff4660db852103b1b9",
                "matrix_csv": "aaa5883bf18ac1ccde6cbb1af21290e5add47c36ec3babba36d95e5101cd1263",
                "matrix_markdown": "7d8cd1e4316ee28f589b2ad47a1de1418d0c9b80389f0fb2bac9a82467c3c87c",
                "matrix_html": "963cceba16ac9a1db894e02407d1fa22333215c279425083458af14a92e27639",
            },
        )
        self.assertEqual(
            fresh["run_manifest_sha256"],
            "3986173ebb182c809e0d977ae4f24124b5fa9ffba37b2332492e496b54cf1b98",
        )
        self.assertEqual(
            fresh["damage_consumer_requirements_sha256"],
            "a394e60b24aa2901369b12877adb6fad5e2b1be8180c416c3441361be6dd1ac1",
        )
        self.assertEqual(
            fresh["damage_target_projection_sha256"],
            "42d733f68b6e706801bb3dc470717ac4841bf48ee8c88fde9530b717b355a4b1",
        )
        self.assertEqual(
            fresh["evaluator_implementation_sha256"],
            "7907904abe5cdcf0a46d8888101a8e8cd4888202a34ba3577870dcb1a11a1f7e",
        )
        self.assertEqual(
            fresh["output_sha256"],
            {
                "detail_csv": "b8840c398dbb11e6225270cffb7312cb096a9711095d14208393107190652c0b",
                "matrix_csv": "109f17a20c9a86b6e55a831ac7292eb4079dc0d5c2cd194d3a1bd5d8c09a6866",
                "matrix_markdown": "6ba68dc1dae86d2f534caa5e17c6402c0064dfafd156f2e174c7743b65209340",
                "matrix_html": "2115627df7ec259e5fd5bb40e609d26627fd524f696e06d5abd2e937ce92c94d",
            },
        )
        self.assertEqual(fresh["row_counts"], {"detail": 564, "matrix": 96})
        self.assertEqual(
            pinned["damage_consumer_requirements_sha256"],
            _current_damage_bundle().identity[
                "damage_consumer_requirements_sha256"
            ],
        )
        self.assertEqual(
            pinned["consumer_requirements_registry_sha256"],
            file_sha256(
                readme_damage.PROJECT_ROOT
                / "harness"
                / "config"
                / "creature-consumers.json"
            ),
        )
        self.assertNotIn("consumer_requirements_sha256", pinned)

    def test_review_loader_pins_exact_v14_1_release_baseline_evidence(self) -> None:
        source = json.loads(
            readme_damage.DAMAGE_REVIEW_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(
            source["expanded_roster_baseline_evidence"],
            asdict(EXPANDED_ROSTER_BASELINE_EVIDENCE),
        )
        self.assertEqual(
            EXPANDED_ROSTER_BASELINE_EVIDENCE_SHA256,
            "61b82443b9bd8e05b9b9cbcf51e1650d9da2da13eb9c880bae3f9fc67cfea814",
        )
        current_rules_version = DamageAuthorityModel.load(
            DEFAULT_AUTHORITY
        ).rules_version
        status = str(load_config()["methodology"]["status"])
        cases = (
            ("asset digest", "sha256", "0" * 64, "pinned v14.1 release asset"),
            ("release commit", "release_commit", "0" * 40, "pinned v14.1 release asset"),
            ("row count", "rows", 95, "pinned v14.1 release asset"),
            ("unknown key", "unexpected", True, "baseline_evidence keys"),
        )
        for label, field, value, pattern in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                mutated = deepcopy(source)
                mutated["expanded_roster_baseline_evidence"][field] = value
                path = Path(directory) / "damage-review.json"
                path.write_text(json.dumps(mutated), encoding="utf-8")
                with self.assertRaisesRegex(MatrixSyncError, pattern):
                    load_damage_review_disposition(
                        current_rules_version,
                        status,
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


class VerifiedDamageRunTests(unittest.TestCase):
    def test_verified_manifest_reuses_current_47_target_run_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, rows, manifest = _write_verified_run_fixture(root)
            with patch.object(
                readme_damage,
                "load_damage_input_bundle",
                return_value=_current_damage_bundle(),
            ):
                verified = load_verified_damage_run(manifest_path)

            self.assertEqual(verified.manifest_path, manifest_path.resolve())
            self.assertEqual(verified.manifest_sha256, file_sha256(manifest_path))
            self.assertEqual(verified.target_count, 47)
            self.assertEqual(verified.inputs, _current_damage_bundle().identity)
            self.assertEqual(list(verified.rows), rows)
            self.assertEqual(
                asdict(verified.output_sha256),
                {
                    name: record["sha256"]
                    for name, record in manifest["outputs"].items()
                },
            )
            self.assertEqual(asdict(verified.row_counts), manifest["row_counts"])

    def test_manifest_input_identity_and_output_digests_fail_closed(self) -> None:
        for field in (
            "damage_model_mode_id",
            "target_knowledge_contract_id",
            "numeric_representation_id",
            "provider_ids",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest_path, _, manifest = _write_verified_run_fixture(root)
                manifest["inputs"][field] = "stale_identity"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with patch.object(
                    readme_damage,
                    "load_damage_input_bundle",
                    return_value=_current_damage_bundle(),
                ):
                    with self.assertRaisesRegex(
                        MatrixSyncError, f"stale or foreign: {field}"
                    ):
                        load_verified_damage_run(manifest_path)

        for field in (
            "catalog_sha256",
            "damage_consumer_requirements_sha256",
            "damage_model_contract_sha256",
            "sentinel_corpus_sha256",
            "sentinel_corpus_file_sha256",
            "observation_policy_sha256",
            "resource_policy_sha256",
            "optimization_policy_sha256",
            "evaluator_implementation_sha256",
            "semantic_implementation_sha256",
            "orchestration_implementation_sha256",
            "reporter_implementation_sha256",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest_path, _, manifest = _write_verified_run_fixture(root)
                manifest["inputs"][field] = "0" * 64
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with patch.object(
                    readme_damage,
                    "load_damage_input_bundle",
                    return_value=_current_damage_bundle(),
                ):
                    with self.assertRaisesRegex(
                        MatrixSyncError, f"stale or foreign: {field}"
                    ):
                        load_verified_damage_run(manifest_path)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, _, manifest = _write_verified_run_fixture(root)
            manifest["inputs"]["consumer_requirements_sha256"] = manifest[
                "inputs"
            ].pop("damage_consumer_requirements_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(
                readme_damage,
                "load_damage_input_bundle",
                return_value=_current_damage_bundle(),
            ):
                with self.assertRaisesRegex(
                    MatrixSyncError,
                    "consumer_requirements_sha256.*damage_consumer_requirements_sha256",
                ):
                    load_verified_damage_run(manifest_path)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, _, _ = _write_verified_run_fixture(root)
            (root / "detail.csv").write_text(
                "tampered after manifest\n", encoding="utf-8"
            )
            with patch.object(
                readme_damage,
                "load_damage_input_bundle",
                return_value=_current_damage_bundle(),
            ):
                with self.assertRaisesRegex(
                    MatrixSyncError, "output detail_csv digest does not match"
                ):
                    load_verified_damage_run(manifest_path)

    def test_manifest_contract_inventory_and_row_counts_fail_closed(self) -> None:
        cases = (
            ("unknown key", lambda data: data.update({"unexpected": True}), "keys"),
            (
                "legacy manifest version",
                lambda data: data.update({"format_version": 1}),
                "run-manifest contract",
            ),
            (
                "missing output",
                lambda data: data["outputs"].pop("matrix_html"),
                "output inventory",
            ),
            (
                "wrong row count",
                lambda data: data["row_counts"].update({"matrix": 95}),
                "row counts",
            ),
        )
        for label, mutate, pattern in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest_path, _, manifest = _write_verified_run_fixture(root)
                mutate(manifest)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with patch.object(
                    readme_damage,
                    "load_damage_input_bundle",
                    return_value=_current_damage_bundle(),
                ):
                    with self.assertRaisesRegex(MatrixSyncError, pattern):
                        load_verified_damage_run(manifest_path)


class DamageReviewRunEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verified = _synthetic_verified_run()
        self.review = _synthetic_review(
            FRESH_EXPANDED_ROSTER_REVIEW,
            self.verified,
        )

    def test_pure_builder_and_coherent_fresh_evidence_match_exactly(self) -> None:
        evidence = fresh_run_evidence_from_verified(
            EXPANDED_ROSTER_BASELINE_EVIDENCE,
            self.verified,
        )
        self.assertEqual(
            evidence.baseline_evidence_sha256,
            EXPANDED_ROSTER_BASELINE_EVIDENCE_SHA256,
        )
        self.assertEqual(self.review.fresh_run_evidence, evidence)
        self.assertEqual(
            set(asdict(evidence)),
            {
                "run_manifest_sha256",
                "baseline_evidence_sha256",
                "damage_result_contract_version",
                "rules_version",
                "authority_sha256",
                "catalog_contract_version",
                "catalog_sha256",
                "roster_contract_version",
                "roster_sha256",
                "target_profile_id",
                "target_profile_version",
                "target_profile_sha256",
                "damage_target_projection_id",
                "damage_target_projection_version",
                "damage_target_projection_sha256",
                "consumer_requirements_version",
                "damage_consumer_requirements_sha256",
                "evaluator",
                "evaluator_implementation_sha256",
                "output_sha256",
                "row_counts",
            },
        )
        validate_damage_review_run_evidence(self.review, self.verified)

    def test_stale_fresh_evidence_identities_and_outputs_fail_closed(self) -> None:
        evidence = self.review.fresh_run_evidence
        self.assertIsNotNone(evidence)
        cases = (
            (
                "manifest",
                replace(evidence, run_manifest_sha256="0" * 64),
                "run_manifest_sha256",
            ),
            (
                "baseline binding",
                replace(evidence, baseline_evidence_sha256="0" * 64),
                "baseline_evidence_sha256",
            ),
            (
                "output",
                replace(
                    evidence,
                    output_sha256=replace(
                        evidence.output_sha256,
                        detail_csv="0" * 64,
                    ),
                ),
                "output_sha256.detail_csv",
            ),
            (
                "evaluator",
                replace(evidence, evaluator="stale_evaluator"),
                "evaluator",
            ),
            (
                "profile",
                replace(evidence, target_profile_id="stale_profile"),
                "target_profile_id",
            ),
            (
                "damage requirements",
                replace(
                    evidence,
                    damage_consumer_requirements_sha256="0" * 64,
                ),
                "damage_consumer_requirements_sha256",
            ),
            (
                "damage requirements version",
                replace(evidence, consumer_requirements_version="stale_version"),
                "consumer_requirements_version",
            ),
        )
        for label, mutated_evidence, pattern in cases:
            with self.subTest(label=label):
                mutated_review = replace(
                    self.review,
                    fresh_run_evidence=mutated_evidence,
                )
                with self.assertRaisesRegex(MatrixSyncError, pattern):
                    validate_damage_review_run_evidence(
                        mutated_review,
                        self.verified,
                    )

    def test_carried_null_and_baseline_basis_contract_fail_closed(self) -> None:
        carried = _synthetic_review(CARRIED_FORWARD_REVIEW)
        validate_damage_review_run_evidence(carried, self.verified)

        with self.assertRaisesRegex(MatrixSyncError, "requires null"):
            validate_damage_review_run_evidence(
                replace(
                    carried,
                    fresh_run_evidence=self.review.fresh_run_evidence,
                ),
                self.verified,
            )

        stale_baseline = replace(EXPANDED_ROSTER_BASELINE_EVIDENCE, rows=95)
        with self.assertRaisesRegex(MatrixSyncError, "baseline evidence"):
            validate_damage_review_run_evidence(
                replace(
                    self.review,
                    expanded_roster_baseline_evidence=stale_baseline,
                ),
                self.verified,
            )
        with self.assertRaisesRegex(MatrixSyncError, "review-basis version"):
            validate_damage_review_run_evidence(
                replace(self.review, review_basis_rules_version="14.0.0"),
                self.verified,
            )

    def test_invalidated_disposition_cannot_accept_a_report_input(self) -> None:
        invalidated = _synthetic_review(INVALIDATED_PREMERGE_REVIEW)
        with self.assertRaisesRegex(
            MatrixSyncError,
            "cannot accept report input; a corrected-contract replacement run is required",
        ):
            validate_damage_review_run_evidence(invalidated, self.verified)


class ReadmeDamageCliTests(unittest.TestCase):
    def test_check_reuses_report_input_without_running_damage_benchmark(self) -> None:
        verified = _synthetic_verified_run()
        review = _synthetic_review(FRESH_EXPANDED_ROSTER_REVIEW, verified)
        rules_version = review.current_rules_version
        status = review.review_status
        region = f"{BEGIN_MARKER}\nsynthetic current region\n{END_MARKER}"
        readme = f"prefix\n{region}\nsuffix\n"
        validated = (
            rules_version,
            status,
            "synthetic_profile",
            (1, 3, 6),
            README_DISCIPLINES,
        )
        report_input = Path("/tmp/synthetic-damage-run/run-manifest.json")
        with tempfile.TemporaryDirectory() as directory:
            readme_path = Path(directory) / "README.md"
            readme_path.write_text(readme, encoding="utf-8")
            with (
                patch.object(sys, "argv", [
                    "readme_damage",
                    "--check",
                    "--report-input",
                    str(report_input),
                ]),
                patch.object(readme_damage, "README_PATH", readme_path),
                patch.object(
                    readme_damage,
                    "synchronization_input_fingerprints",
                    return_value={"README.md": "stable"},
                ),
                patch.object(
                    readme_damage.DamageAuthorityModel,
                    "load",
                    return_value=SimpleNamespace(rules_version=rules_version),
                ),
                patch.object(
                    readme_damage,
                    "load_config",
                    return_value={"methodology": {"status": status}},
                ),
                patch.object(
                    readme_damage,
                    "load_damage_review_disposition",
                    return_value=review,
                ),
                patch.object(
                    readme_damage,
                    "load_verified_damage_run",
                    return_value=verified,
                ) as load_run,
                patch.object(
                    readme_damage,
                    "validate_damage_review_run_evidence",
                    wraps=validate_damage_review_run_evidence,
                ) as validate_review,
                patch.object(
                    readme_damage,
                    "validate_authoritative_rows",
                    return_value=validated,
                ) as validate,
                patch.object(
                    readme_damage,
                    "render_damage_region",
                    return_value=region,
                ) as render,
                patch("harness.damage_harness.run") as benchmark,
                patch("builtins.print"),
            ):
                readme_damage.main()

        load_run.assert_called_once_with(report_input)
        validate_review.assert_called_once_with(review, verified)
        validate.assert_called_once_with(
            list(verified.rows),
            verified.inputs,
        )
        render.assert_called_once_with(
            list(verified.rows),
            rules_version,
            review,
            "synthetic_profile",
            "srd521_headline_source_diversity_v1",
            47,
            verified.manifest_sha256,
            (1, 3, 6),
            README_DISCIPLINES,
        )
        benchmark.assert_not_called()

    def test_stale_check_names_the_verified_report_input(self) -> None:
        report_input = Path("/tmp/synthetic damage run/run-manifest.json")
        verified = replace(
            _synthetic_verified_run(),
            manifest_path=report_input,
            matrix_path=report_input.with_name("matrix.csv"),
        )
        review = _synthetic_review(FRESH_EXPANDED_ROSTER_REVIEW, verified)
        with tempfile.TemporaryDirectory() as directory:
            readme_path = Path(directory) / "README.md"
            readme_path.write_text(
                f"prefix\n{BEGIN_MARKER}\nstale\n{END_MARKER}\nsuffix\n",
                encoding="utf-8",
            )
            with (
                patch.object(sys, "argv", ["readme_damage", "--check", "--report-input", str(report_input)]),
                patch.object(readme_damage, "README_PATH", readme_path),
                patch.object(readme_damage, "synchronization_input_fingerprints", return_value={"README.md": "stable"}),
                patch.object(readme_damage.DamageAuthorityModel, "load", return_value=SimpleNamespace(rules_version=review.current_rules_version)),
                patch.object(readme_damage, "load_config", return_value={"methodology": {"status": review.review_status}}),
                patch.object(readme_damage, "load_damage_review_disposition", return_value=review),
                patch.object(readme_damage, "load_verified_damage_run", return_value=verified),
                patch.object(readme_damage, "validate_authoritative_rows", return_value=(review.current_rules_version, review.review_status, "profile", (1, 3, 6), README_DISCIPLINES)),
                patch.object(readme_damage, "render_damage_region", return_value=f"{BEGIN_MARKER}\nfresh\n{END_MARKER}"),
                patch("harness.damage_harness.run") as benchmark,
            ):
                with self.assertRaisesRegex(
                    SystemExit,
                    r"npm run readme:damage -- --report-input '/tmp/synthetic damage run/run-manifest\.json'",
                ):
                    readme_damage.main()
        benchmark.assert_not_called()


class AuthoritativeDamageRowValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.identity = dict(_current_damage_bundle().identity)
        cls.rows = _full_authoritative_rows(cls.identity)

    def test_full_current_shape_synthetic_rows_pass(self) -> None:
        model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        damage_model_contract = json.loads(
            (Path(__file__).resolve().parents[1] / "provenance" / "damage-model-contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(PROVENANCE_FIELDS, EXPECTED_PROVENANCE_FIELDS)
        self.assertEqual(
            damage_model_contract["result_and_provenance"]["required_input_identity_fields"],
            list(self.identity),
        )
        self.assertEqual(len(_current_damage_bundle().entries), 47)
        self.assertEqual(
            self.identity["target_profile_id"],
            "srd521_headline_source_diversity_v1",
        )
        self.assertEqual(
            validate_authoritative_rows(self.rows, self.identity),
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
            validate_authoritative_rows(rows, self.identity)

        rows = deepcopy(self.rows)
        rows[0]["Unexpected"] = "field"
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(rows, self.identity)

    def test_duplicate_and_missing_identities_fail_closed(self) -> None:
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            validate_authoritative_rows(deepcopy(self.rows[1:]), self.identity)

        rows = deepcopy(self.rows)
        rows.append(deepcopy(rows[0]))
        with self.assertRaisesRegex(MatrixSyncError, "duplicate row identities"):
            validate_authoritative_rows(rows, self.identity)

    def test_provenance_and_notice_mismatches_fail_closed(self) -> None:
        rows = deepcopy(self.rows)
        rows[0]["Provenance Seed"] = "wrong-seed"
        with self.assertRaisesRegex(MatrixSyncError, "Provenance Seed"):
            validate_authoritative_rows(rows, self.identity)

        rows = deepcopy(self.rows)
        notice_field = next(iter(NOTICE_COLUMNS))
        rows[0][notice_field] = "changed notice"
        with self.assertRaisesRegex(MatrixSyncError, "changed notice field"):
            validate_authoritative_rows(rows, self.identity)

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
                    validate_authoritative_rows(rows, self.identity)

if __name__ == "__main__":
    unittest.main()
