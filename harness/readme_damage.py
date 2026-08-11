"""Synchronize the README damage snapshot from validated authoritative rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shlex
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .authority import DamageAuthorityModel, DEFAULT_AUTHORITY, PROJECT_ROOT
from .damage_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    VALUE_COLUMNS,
    damage_matrix_row,
)
from .damage_harness import (
    DAMAGE_RESULT_CONTRACT_VERSION,
    load_damage_input_bundle,
)
from .model import (
    file_sha256,
    load_config,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED DAMAGE MATRIX -->"
END_MARKER = "<!-- END GENERATED DAMAGE MATRIX -->"
README_PATH = PROJECT_ROOT / "README.md"
BUILD_INPUTS_PATH = PROJECT_ROOT / "build" / "inputs.json"
DAMAGE_REVIEW_PATH = PROJECT_ROOT / "harness" / "provenance" / "damage-review.json"
DAMAGE_SCOPES = ("primary-target DPR", "aggregate cluster DPR")
README_DISCIPLINES = (
    "cryokinesis",
    "pyrokinesis",
    "psychokinesis",
    "electrokinesis",
)
RESULT_FIELDS = tuple(VALUE_COLUMNS)
PROVENANCE_FIELDS = (
    "Provenance Damage Result Contract Version",
    "Provenance Rules Version",
    "Provenance Authority Sha256",
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
    "Provenance Consumer Requirements Sha256",
    "Provenance Config Sha256",
    "Provenance Comparator Config Sha256",
    "Provenance Evaluator",
    "Provenance Evaluator Implementation Sha256",
    "Provenance Trials",
    "Provenance Seed",
    "Provenance Trial Seed Role",
    "Provenance Aggregation",
    "Provenance Status",
)
MatrixRow = dict[str, str]
CARRIED_FORWARD_REVIEW = "CARRIED_FORWARD_WITHOUT_FRESH_NUMERICAL_REVIEW"
FRESH_EXPANDED_ROSTER_REVIEW = (
    "FRESH_EXPANDED_ROSTER_RUN_WITHOUT_INDEPENDENT_CERTIFICATION"
)


class MatrixSyncError(ValueError):
    pass


@dataclass(frozen=True)
class ExpandedRosterBaselineEvidence:
    rules_version: str
    release_tag: str
    release_commit: str
    source_url: str
    filename: str
    bytes: int
    rows: int
    sha256: str
    evaluator: str


@dataclass(frozen=True)
class DamageOutputSha256:
    detail_csv: str
    matrix_csv: str
    matrix_markdown: str
    matrix_html: str


@dataclass(frozen=True)
class DamageRowCounts:
    detail: int
    matrix: int


@dataclass(frozen=True)
class FreshRunEvidence:
    run_manifest_sha256: str
    baseline_evidence_sha256: str
    damage_result_contract_version: str
    rules_version: str
    authority_sha256: str
    catalog_contract_version: str
    catalog_sha256: str
    roster_contract_version: str
    roster_sha256: str
    target_profile_id: str
    target_profile_version: str
    target_profile_sha256: str
    damage_target_projection_id: str
    damage_target_projection_version: str
    damage_target_projection_sha256: str
    evaluator: str
    evaluator_implementation_sha256: str
    output_sha256: DamageOutputSha256
    row_counts: DamageRowCounts


@dataclass(frozen=True)
class DamageReviewDisposition:
    expanded_roster_baseline_evidence: ExpandedRosterBaselineEvidence
    current_rules_version: str
    review_basis_rules_version: str
    review_status: str
    review_disposition: str
    fresh_full_roster_run: bool
    fresh_numerical_certification: bool
    fresh_monte_carlo_certification: bool
    reason: str
    durable_record: str
    fresh_run_evidence: FreshRunEvidence | None


@dataclass(frozen=True)
class VerifiedDamageRun:
    manifest_path: Path
    manifest_sha256: str
    inputs: dict[str, object]
    target_count: int
    matrix_path: Path
    rows: tuple[MatrixRow, ...]
    output_sha256: DamageOutputSha256
    row_counts: DamageRowCounts


EXPANDED_ROSTER_BASELINE_EVIDENCE = ExpandedRosterBaselineEvidence(
    rules_version="14.1.0",
    release_tag="v14.1.0",
    release_commit="40d0d191e7ef3ba7be7a3ed6f5f4c0e1c6059bef",
    source_url=(
        "https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.1.0"
    ),
    filename="kv-14-1-0-damage-comparison-matrix.csv",
    bytes=265_819,
    rows=96,
    sha256="e0a9aec2d5c8da9409b8158163d44085001c26686385ddacb7108ff48d2326b4",
    evaluator="exact_analytical_enumeration",
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


EXPANDED_ROSTER_BASELINE_EVIDENCE_SHA256 = _canonical_sha256(
    asdict(EXPANDED_ROSTER_BASELINE_EVIDENCE)
)


def _review_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MatrixSyncError(f"{label} must be an object")
    return value


def _review_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MatrixSyncError(f"{label} must be a non-empty string")
    return value


def _review_exact_keys(
    value: dict[str, object], required: set[str], label: str
) -> None:
    if set(value) != required:
        raise MatrixSyncError(
            f"{label} keys are invalid; "
            f"missing={sorted(required - value.keys())}, "
            f"unknown={sorted(value.keys() - required)}"
        )


def _review_sha256(value: object, label: str) -> str:
    result = _review_string(value, label)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise MatrixSyncError(f"{label} must be a lowercase SHA-256")
    return result


def _review_positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MatrixSyncError(f"{label} must be a positive integer")
    return value


def _load_baseline_evidence(value: object) -> ExpandedRosterBaselineEvidence:
    label = "expanded_roster_baseline_evidence"
    raw = _review_object(value, label)
    required = {
        "rules_version",
        "release_tag",
        "release_commit",
        "source_url",
        "filename",
        "bytes",
        "rows",
        "sha256",
        "evaluator",
    }
    _review_exact_keys(raw, required, label)
    release_commit = _review_string(
        raw["release_commit"], f"{label}.release_commit"
    )
    if len(release_commit) != 40 or any(
        character not in "0123456789abcdef" for character in release_commit
    ):
        raise MatrixSyncError(
            f"{label}.release_commit must be a lowercase full Git SHA"
        )
    result = ExpandedRosterBaselineEvidence(
        rules_version=_review_string(raw["rules_version"], f"{label}.rules_version"),
        release_tag=_review_string(raw["release_tag"], f"{label}.release_tag"),
        release_commit=release_commit,
        source_url=_review_string(raw["source_url"], f"{label}.source_url"),
        filename=_review_string(raw["filename"], f"{label}.filename"),
        bytes=_review_positive_integer(raw["bytes"], f"{label}.bytes"),
        rows=_review_positive_integer(raw["rows"], f"{label}.rows"),
        sha256=_review_sha256(raw["sha256"], f"{label}.sha256"),
        evaluator=_review_string(raw["evaluator"], f"{label}.evaluator"),
    )
    if result != EXPANDED_ROSTER_BASELINE_EVIDENCE:
        actual = asdict(result)
        expected = asdict(EXPANDED_ROSTER_BASELINE_EVIDENCE)
        changed = sorted(key for key in expected if actual[key] != expected[key])
        raise MatrixSyncError(
            "Expanded-roster baseline evidence differs from the pinned v14.1 "
            "release asset: " + ", ".join(changed)
        )
    return result


def _load_output_sha256(value: object, label: str) -> DamageOutputSha256:
    raw = _review_object(value, label)
    required = {"detail_csv", "matrix_csv", "matrix_markdown", "matrix_html"}
    _review_exact_keys(raw, required, label)
    return DamageOutputSha256(
        detail_csv=_review_sha256(raw["detail_csv"], f"{label}.detail_csv"),
        matrix_csv=_review_sha256(raw["matrix_csv"], f"{label}.matrix_csv"),
        matrix_markdown=_review_sha256(
            raw["matrix_markdown"], f"{label}.matrix_markdown"
        ),
        matrix_html=_review_sha256(raw["matrix_html"], f"{label}.matrix_html"),
    )


def _load_row_counts(value: object, label: str) -> DamageRowCounts:
    raw = _review_object(value, label)
    required = {"detail", "matrix"}
    _review_exact_keys(raw, required, label)
    return DamageRowCounts(
        detail=_review_positive_integer(raw["detail"], f"{label}.detail"),
        matrix=_review_positive_integer(raw["matrix"], f"{label}.matrix"),
    )


def _load_fresh_run_evidence(value: object) -> FreshRunEvidence:
    label = "current_development_disposition.fresh_run_evidence"
    raw = _review_object(value, label)
    required = {
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
        "evaluator",
        "evaluator_implementation_sha256",
        "output_sha256",
        "row_counts",
    }
    _review_exact_keys(raw, required, label)
    string_fields = (
        "damage_result_contract_version",
        "rules_version",
        "catalog_contract_version",
        "roster_contract_version",
        "target_profile_id",
        "target_profile_version",
        "damage_target_projection_id",
        "damage_target_projection_version",
        "evaluator",
    )
    strings = {
        field: _review_string(raw[field], f"{label}.{field}")
        for field in string_fields
    }
    sha_fields = (
        "run_manifest_sha256",
        "baseline_evidence_sha256",
        "authority_sha256",
        "catalog_sha256",
        "roster_sha256",
        "target_profile_sha256",
        "damage_target_projection_sha256",
        "evaluator_implementation_sha256",
    )
    shas = {
        field: _review_sha256(raw[field], f"{label}.{field}")
        for field in sha_fields
    }
    return FreshRunEvidence(
        run_manifest_sha256=shas["run_manifest_sha256"],
        baseline_evidence_sha256=shas["baseline_evidence_sha256"],
        damage_result_contract_version=strings["damage_result_contract_version"],
        rules_version=strings["rules_version"],
        authority_sha256=shas["authority_sha256"],
        catalog_contract_version=strings["catalog_contract_version"],
        catalog_sha256=shas["catalog_sha256"],
        roster_contract_version=strings["roster_contract_version"],
        roster_sha256=shas["roster_sha256"],
        target_profile_id=strings["target_profile_id"],
        target_profile_version=strings["target_profile_version"],
        target_profile_sha256=shas["target_profile_sha256"],
        damage_target_projection_id=strings["damage_target_projection_id"],
        damage_target_projection_version=strings[
            "damage_target_projection_version"
        ],
        damage_target_projection_sha256=shas["damage_target_projection_sha256"],
        evaluator=strings["evaluator"],
        evaluator_implementation_sha256=shas["evaluator_implementation_sha256"],
        output_sha256=_load_output_sha256(
            raw["output_sha256"], f"{label}.output_sha256"
        ),
        row_counts=_load_row_counts(raw["row_counts"], f"{label}.row_counts"),
    )


def load_damage_review_disposition(
    current_rules_version: str,
    review_status: str,
    path: Path = DAMAGE_REVIEW_PATH,
) -> DamageReviewDisposition:
    try:
        provenance = _review_object(
            json.loads(path.read_text(encoding="utf-8")),
            "Damage-review provenance",
        )
        historical_review = _review_object(
            provenance["current_damage_review"],
            "current_damage_review",
        )
        comparator_review = _review_object(
            provenance["current_comparator_review"],
            "current_comparator_review",
        )
        baseline_evidence = _load_baseline_evidence(
            provenance["expanded_roster_baseline_evidence"]
        )
        raw = _review_object(
            provenance["current_development_disposition"],
            "current_development_disposition",
        )
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise MatrixSyncError("Cannot read damage-review disposition") from error

    required = {
        "current_rules_version",
        "review_basis_rules_version",
        "review_disposition",
        "fresh_full_roster_run",
        "fresh_numerical_certification",
        "fresh_monte_carlo_certification",
        "reason",
        "durable_record",
        "fresh_run_evidence",
    }
    _review_exact_keys(raw, required, "current_development_disposition")

    strings = {
        field: _review_string(raw[field], f"current_development_disposition.{field}")
        for field in (
            "current_rules_version",
            "review_basis_rules_version",
            "review_disposition",
            "reason",
            "durable_record",
        )
    }
    booleans: dict[str, bool] = {}
    for field in (
        "fresh_full_roster_run",
        "fresh_numerical_certification",
        "fresh_monte_carlo_certification",
    ):
        value = raw[field]
        if type(value) is not bool:
            raise MatrixSyncError(
                f"current_development_disposition.{field} must be a boolean"
            )
        booleans[field] = value

    basis_version = _review_string(
        historical_review.get("rules_version"),
        "current_damage_review.rules_version",
    )
    historical_status = _review_string(
        historical_review.get("status"),
        "current_damage_review.status",
    )
    comparator_version = _review_string(
        comparator_review.get("rules_version"),
        "current_comparator_review.rules_version",
    )
    historical_evaluator = _review_string(
        historical_review.get("evaluator"),
        "current_damage_review.evaluator",
    )
    if strings["current_rules_version"] != current_rules_version:
        raise MatrixSyncError(
            "Current damage-review disposition differs from canonical rules version"
        )
    if strings["review_basis_rules_version"] != basis_version:
        raise MatrixSyncError(
            "Damage review-basis version differs from the durable damage review"
        )
    if comparator_version != basis_version:
        raise MatrixSyncError(
            "Damage and comparator review-basis versions must agree"
        )
    if baseline_evidence.rules_version != basis_version:
        raise MatrixSyncError(
            "Expanded-roster baseline evidence differs from the review-basis version"
        )
    if baseline_evidence.evaluator != historical_evaluator:
        raise MatrixSyncError(
            "Expanded-roster baseline evaluator differs from the durable damage review"
        )
    if historical_status != review_status:
        raise MatrixSyncError(
            "Damage matrix review status differs from the durable review basis"
        )
    disposition = strings["review_disposition"]
    fresh_run_evidence: FreshRunEvidence | None
    if disposition == CARRIED_FORWARD_REVIEW:
        if strings["review_basis_rules_version"] == strings["current_rules_version"]:
            raise MatrixSyncError(
                "Carried-forward review basis must differ from current rules version"
            )
        if any(booleans.values()):
            raise MatrixSyncError(
                "Carried-forward damage evidence cannot claim a fresh run or certification"
            )
        if raw["fresh_run_evidence"] is not None:
            raise MatrixSyncError(
                "Carried-forward damage evidence requires null fresh_run_evidence"
            )
        fresh_run_evidence = None
    elif disposition == FRESH_EXPANDED_ROSTER_REVIEW:
        if not booleans["fresh_full_roster_run"]:
            raise MatrixSyncError(
                "Expanded-roster disposition requires a fresh full-roster run"
            )
        if booleans["fresh_numerical_certification"] or booleans[
            "fresh_monte_carlo_certification"
        ]:
            raise MatrixSyncError(
                "Expanded-roster implementation cannot claim independent or "
                "Monte Carlo certification"
            )
        if raw["fresh_run_evidence"] is None:
            raise MatrixSyncError(
                "Expanded-roster disposition requires fresh_run_evidence"
            )
        fresh_run_evidence = _load_fresh_run_evidence(raw["fresh_run_evidence"])
        if (
            fresh_run_evidence.baseline_evidence_sha256
            != _canonical_sha256(asdict(baseline_evidence))
        ):
            raise MatrixSyncError(
                "Fresh-run evidence baseline_evidence_sha256 differs from the "
                "maintained baseline evidence"
            )
        if fresh_run_evidence.rules_version != strings["current_rules_version"]:
            raise MatrixSyncError(
                "Fresh-run evidence rules version differs from current rules version"
            )
    else:
        raise MatrixSyncError("Unsupported current damage-review disposition")

    return DamageReviewDisposition(
        expanded_roster_baseline_evidence=baseline_evidence,
        current_rules_version=strings["current_rules_version"],
        review_basis_rules_version=strings["review_basis_rules_version"],
        review_status=historical_status,
        review_disposition=strings["review_disposition"],
        fresh_full_roster_run=booleans["fresh_full_roster_run"],
        fresh_numerical_certification=booleans["fresh_numerical_certification"],
        fresh_monte_carlo_certification=booleans[
            "fresh_monte_carlo_certification"
        ],
        reason=strings["reason"],
        durable_record=strings["durable_record"],
        fresh_run_evidence=fresh_run_evidence,
    )


def synchronization_input_fingerprints() -> dict[str, str]:
    try:
        manifest = json.loads(BUILD_INPUTS_PATH.read_text(encoding="utf-8"))
        declared = manifest["inputs"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise MatrixSyncError("Cannot read the maintained build-input manifest") from error
    if not isinstance(declared, list):
        raise MatrixSyncError("Build-input manifest inputs must be a list")

    root = PROJECT_ROOT.resolve()
    paths = {README_PATH.resolve(), BUILD_INPUTS_PATH.resolve()}
    for index, entry in enumerate(declared):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise MatrixSyncError(f"Build-input entry {index} has no string path")
        relative = Path(entry["path"])
        if relative.is_absolute():
            raise MatrixSyncError(f"Build-input entry {index} must be repository-relative")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise MatrixSyncError(f"Build-input entry {index} escapes the repository") from error
        if not candidate.is_file():
            raise MatrixSyncError(f"Maintained synchronization input is missing: {relative}")
        paths.add(candidate)

    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(paths, key=lambda candidate: candidate.as_posix())
    }


def require_unchanged_inputs(before: dict[str, str]) -> None:
    after = synchronization_input_fingerprints()
    changed = sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )
    if changed:
        raise MatrixSyncError(
            "Synchronization inputs changed during report validation: "
            + ", ".join(changed)
        )


def atomic_replace_text(path: Path, expected: str, replacement: str) -> None:
    if path.read_text(encoding="utf-8") != expected:
        raise MatrixSyncError(f"Refusing to overwrite concurrently changed file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            dir=path.parent,
            delete=False,
        ) as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        temporary_path.chmod(mode)
        if path.read_text(encoding="utf-8") != expected:
            raise MatrixSyncError(f"Refusing to overwrite concurrently changed file: {path}")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def read_matrix_rows(path: Path) -> list[MatrixRow]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    if not rows:
        raise MatrixSyncError(f"Authoritative matrix is empty: {path}")
    return rows


def load_verified_damage_run(path: Path) -> VerifiedDamageRun:
    path = path.resolve()
    if path.name != "run-manifest.json" or not path.is_file():
        raise MatrixSyncError("--report-input must name an existing run-manifest.json")
    try:
        manifest = _review_object(
            json.loads(path.read_text(encoding="utf-8")),
            "Damage run manifest",
        )
    except (OSError, json.JSONDecodeError) as error:
        raise MatrixSyncError("Cannot read the damage run manifest") from error
    required = {
        "format_version",
        "damage_result_contract_version",
        "inputs",
        "outputs",
        "row_counts",
    }
    if set(manifest) != required:
        raise MatrixSyncError(
            "Damage run manifest keys are invalid; "
            f"missing={sorted(required - manifest.keys())}, "
            f"unknown={sorted(manifest.keys() - required)}"
        )
    if manifest["format_version"] != 1 or manifest[
        "damage_result_contract_version"
    ] != DAMAGE_RESULT_CONTRACT_VERSION:
        raise MatrixSyncError("Unsupported damage run-manifest contract")
    inputs = _review_object(manifest["inputs"], "Damage run inputs")
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    trials = int(config["methodology"]["damage_default_trials"])
    seed = int(config["methodology"]["damage_seed"])
    current = load_damage_input_bundle(DEFAULT_AUTHORITY, levels, trials, seed)
    if inputs != current.identity:
        changed = sorted(
            key
            for key in inputs.keys() | current.identity.keys()
            if inputs.get(key) != current.identity.get(key)
        )
        raise MatrixSyncError(
            "Damage run inputs are stale or foreign: " + ", ".join(changed)
        )
    outputs = _review_object(manifest["outputs"], "Damage run outputs")
    expected_outputs = {
        "detail_csv",
        "matrix_csv",
        "matrix_markdown",
        "matrix_html",
    }
    if set(outputs) != expected_outputs:
        raise MatrixSyncError(
            "Damage run output inventory is incomplete or unsupported"
        )
    resolved: dict[str, Path] = {}
    output_sha256_values: dict[str, str] = {}
    for name in sorted(expected_outputs):
        record = _review_object(outputs[name], f"Damage run output {name}")
        if set(record) != {"file", "sha256"}:
            raise MatrixSyncError(f"Damage run output {name} has invalid keys")
        filename = _review_string(record["file"], f"Damage run output {name}.file")
        expected_sha = _review_sha256(
            record["sha256"], f"Damage run output {name}.sha256"
        )
        if Path(filename).name != filename:
            raise MatrixSyncError(f"Damage run output {name} must be a sibling file")
        candidate = path.parent / filename
        if not candidate.is_file() or file_sha256(candidate) != expected_sha:
            raise MatrixSyncError(f"Damage run output {name} digest does not match")
        resolved[name] = candidate
        output_sha256_values[name] = expected_sha
    output_sha256 = _load_output_sha256(
        output_sha256_values,
        "Damage run output SHA-256 inventory",
    )
    row_counts = _load_row_counts(manifest["row_counts"], "Damage run row counts")
    expected_detail = (
        len(current.entries)
        * len(current.model.disciplines)
        * len(config["methodology"]["cluster_sizes"])
    )
    expected_matrix = (
        len(levels)
        * len(current.model.disciplines)
        * len(config["methodology"]["cluster_sizes"])
        * len(DAMAGE_SCOPES)
    )
    if row_counts != DamageRowCounts(
        detail=expected_detail,
        matrix=expected_matrix,
    ):
        raise MatrixSyncError("Damage run row counts do not match current inputs")
    rows = tuple(read_matrix_rows(resolved["matrix_csv"]))
    if len(rows) != row_counts.matrix:
        raise MatrixSyncError("Damage matrix row count differs from its run manifest")
    return VerifiedDamageRun(
        manifest_path=path,
        manifest_sha256=file_sha256(path),
        inputs=dict(inputs),
        target_count=len(current.entries),
        matrix_path=resolved["matrix_csv"],
        rows=rows,
        output_sha256=output_sha256,
        row_counts=row_counts,
    )


def _verified_input_string(
    verified: VerifiedDamageRun, key: str, *, sha256: bool = False
) -> str:
    label = f"Verified damage run input {key}"
    value = verified.inputs.get(key)
    return _review_sha256(value, label) if sha256 else _review_string(value, label)


def fresh_run_evidence_from_verified(
    review_baseline: ExpandedRosterBaselineEvidence,
    verified: VerifiedDamageRun,
) -> FreshRunEvidence:
    """Build the review evidence record from an already verified run manifest."""

    if review_baseline != EXPANDED_ROSTER_BASELINE_EVIDENCE:
        raise MatrixSyncError(
            "Cannot bind fresh-run evidence to an unsupported baseline evidence record"
        )
    output_sha256 = _load_output_sha256(
        asdict(verified.output_sha256),
        "Verified damage run output SHA-256 inventory",
    )
    row_counts = _load_row_counts(
        asdict(verified.row_counts),
        "Verified damage run row counts",
    )
    return FreshRunEvidence(
        run_manifest_sha256=_review_sha256(
            verified.manifest_sha256,
            "Verified damage run manifest SHA-256",
        ),
        baseline_evidence_sha256=_canonical_sha256(asdict(review_baseline)),
        damage_result_contract_version=_verified_input_string(
            verified, "damage_result_contract_version"
        ),
        rules_version=_verified_input_string(verified, "rules_version"),
        authority_sha256=_verified_input_string(
            verified, "authority_sha256", sha256=True
        ),
        catalog_contract_version=_verified_input_string(
            verified, "catalog_contract_version"
        ),
        catalog_sha256=_verified_input_string(
            verified, "catalog_sha256", sha256=True
        ),
        roster_contract_version=_verified_input_string(
            verified, "roster_contract_version"
        ),
        roster_sha256=_verified_input_string(
            verified, "roster_sha256", sha256=True
        ),
        target_profile_id=_verified_input_string(verified, "target_profile_id"),
        target_profile_version=_verified_input_string(
            verified, "target_profile_version"
        ),
        target_profile_sha256=_verified_input_string(
            verified, "target_profile_sha256", sha256=True
        ),
        damage_target_projection_id=_verified_input_string(
            verified, "damage_target_projection_id"
        ),
        damage_target_projection_version=_verified_input_string(
            verified, "damage_target_projection_version"
        ),
        damage_target_projection_sha256=_verified_input_string(
            verified, "damage_target_projection_sha256", sha256=True
        ),
        evaluator=_verified_input_string(verified, "evaluator"),
        evaluator_implementation_sha256=_verified_input_string(
            verified, "evaluator_implementation_sha256", sha256=True
        ),
        output_sha256=output_sha256,
        row_counts=row_counts,
    )


def _flatten_evidence(value: object, prefix: str = "") -> dict[str, object]:
    if not isinstance(value, dict):
        return {prefix: value}
    flattened: dict[str, object] = {}
    for key, child in value.items():
        label = f"{prefix}.{key}" if prefix else str(key)
        flattened.update(_flatten_evidence(child, label))
    return flattened


def validate_damage_review_run_evidence(
    review: DamageReviewDisposition,
    verified: VerifiedDamageRun,
) -> None:
    baseline = review.expanded_roster_baseline_evidence
    if baseline != EXPANDED_ROSTER_BASELINE_EVIDENCE:
        raise MatrixSyncError(
            "Damage-review baseline evidence differs from the pinned v14.1 release asset"
        )
    if baseline.rules_version != review.review_basis_rules_version:
        raise MatrixSyncError(
            "Damage-review baseline evidence does not match the review-basis version"
        )

    if review.review_disposition == CARRIED_FORWARD_REVIEW:
        if review.review_basis_rules_version == review.current_rules_version or any(
            (
                review.fresh_full_roster_run,
                review.fresh_numerical_certification,
                review.fresh_monte_carlo_certification,
            )
        ):
            raise MatrixSyncError(
                "Carried-forward damage-review flags are inconsistent"
            )
        if review.fresh_run_evidence is not None:
            raise MatrixSyncError(
                "Carried-forward damage review requires null fresh_run_evidence"
            )
        return
    if review.review_disposition != FRESH_EXPANDED_ROSTER_REVIEW:
        raise MatrixSyncError("Unsupported damage-review evidence disposition")
    if review.fresh_run_evidence is None:
        raise MatrixSyncError(
            "Fresh expanded-roster damage review requires fresh_run_evidence"
        )
    if (
        not review.fresh_full_roster_run
        or review.fresh_numerical_certification
        or review.fresh_monte_carlo_certification
    ):
        raise MatrixSyncError(
            "Fresh expanded-roster damage-review flags are inconsistent"
        )

    expected = fresh_run_evidence_from_verified(baseline, verified)
    if expected.rules_version != review.current_rules_version:
        raise MatrixSyncError(
            "Verified fresh-run rules version differs from current review disposition"
        )
    if review.fresh_run_evidence != expected:
        actual_values = _flatten_evidence(asdict(review.fresh_run_evidence))
        expected_values = _flatten_evidence(asdict(expected))
        changed = sorted(
            key
            for key in actual_values.keys() | expected_values.keys()
            if actual_values.get(key) != expected_values.get(key)
        )
        raise MatrixSyncError(
            "Fresh-run evidence differs from the verified run: " + ", ".join(changed)
        )


def _require_fields(rows: Sequence[MatrixRow], fields: Sequence[str]) -> None:
    expected = set(fields)
    for index, row in enumerate(rows):
        missing = [field for field in fields if field not in row]
        unexpected = [field for field in row if field not in expected]
        if missing or unexpected:
            raise MatrixSyncError(
                f"Damage row {index} has schema differences; "
                f"missing={missing}, unexpected={unexpected}"
            )


def _uniform(rows: Sequence[MatrixRow], field: str) -> str:
    values = {row[field] for row in rows}
    if len(values) != 1:
        raise MatrixSyncError(
            f"Damage matrix has inconsistent {field}: {sorted(values)}"
        )
    return next(iter(values))


def _key_difference(actual: set[tuple[str, ...]], expected: set[tuple[str, ...]], kind: str) -> None:
    if actual == expected:
        return
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    raise MatrixSyncError(f"{kind} row identities differ; missing={missing}, extra={extra}")


def validate_authoritative_rows(
    damage_rows: Sequence[MatrixRow],
    expected_inputs: dict[str, object] | None = None,
) -> tuple[str, str, str, tuple[int, ...], tuple[str, ...]]:
    model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    clusters = tuple(int(value) for value in config["methodology"]["cluster_sizes"])
    disciplines = README_DISCIPLINES
    if set(disciplines) != set(model.disciplines):
        raise MatrixSyncError(
            "README discipline columns differ from the canonical discipline set"
        )
    profile = str(config["kv_profile"]["id"])
    status = str(config["methodology"]["status"])

    _require_fields(
        damage_rows,
        (
            "Level",
            "Discipline",
            "Cluster Size",
            "Damage Scope",
            "Profile",
            *RESULT_FIELDS,
            *PROVENANCE_FIELDS,
            *NOTICE_COLUMNS,
        ),
    )

    expected_damage = {
        (str(level), discipline, str(cluster), scope)
        for level in levels
        for discipline in disciplines
        for cluster in clusters
        for scope in DAMAGE_SCOPES
    }
    actual_damage = {
        (row["Level"], row["Discipline"], row["Cluster Size"], row["Damage Scope"])
        for row in damage_rows
    }
    _key_difference(actual_damage, expected_damage, "Damage")
    if len(damage_rows) != len(expected_damage):
        raise MatrixSyncError("Damage matrix contains duplicate row identities")

    if expected_inputs is None:
        bundle = load_damage_input_bundle(
            DEFAULT_AUTHORITY,
            set(levels),
            int(config["methodology"]["damage_default_trials"]),
            int(config["methodology"]["damage_seed"]),
        )
        expected_inputs = bundle.identity
    expected = {
        **{
            f"Provenance {str(key).replace('_', ' ').title()}": str(value)
            for key, value in expected_inputs.items()
        },
        "Profile": profile,
    }
    for index, row in enumerate(damage_rows):
        for field, value in expected.items():
            if row[field] != value:
                raise MatrixSyncError(
                    f"Damage row {index} has {field}={row[field]!r}; expected {value!r}"
                )
        for field, value in NOTICE_COLUMNS.items():
            if row[field] != value:
                raise MatrixSyncError(f"Damage row {index} changed notice field {field}")
        recomputed = damage_matrix_row(
            {},
            float(row["KV"]),
            float(row["Eldritch Knight"]),
            float(row["Battle Master"]),
        )
        for field in RESULT_FIELDS:
            if row[field] != recomputed[field]:
                raise MatrixSyncError(
                    f"Damage row {index} has stale {field}: "
                    f"{row[field]} != {recomputed[field]}"
                )

    if _uniform(damage_rows, "Provenance Rules Version") != model.rules_version:
        raise MatrixSyncError("Damage matrix rules version differs from canonical authority")
    return model.rules_version, status, profile, clusters, disciplines


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if any(len(row) != len(headers) for row in rows):
        raise MatrixSyncError("Markdown table rows do not match the header width")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend(
        "| " + " | ".join(_escape_cell(str(value)) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _public_result(row: MatrixRow) -> str:
    band = row["Band"]
    delta = row["Boundary Delta %"]
    if band == "IDEAL":
        if delta != "0.00":
            raise MatrixSyncError("IDEAL result must have zero Boundary Delta %")
        return band
    if band == "N/A":
        if delta != "N/A":
            raise MatrixSyncError("N/A result must have unavailable Boundary Delta %")
        return band
    expected_sign = {"COLD": "-", "HOT": "+"}.get(band)
    if expected_sign is None:
        raise MatrixSyncError(f"Unsupported public damage result: {band}")
    if not delta.startswith(expected_sign):
        raise MatrixSyncError(f"{band} result has incorrectly signed Boundary Delta %")
    return f"{band} ({delta}%)"


def _heat_table(
    rows: Sequence[MatrixRow], disciplines: Sequence[str]
) -> str:
    if not rows:
        raise MatrixSyncError("README heat matrix cannot be empty")
    grouped: dict[tuple[str, str], MatrixRow] = {}
    for row in rows:
        key = (row["Level"], row["Discipline"])
        if key in grouped:
            raise MatrixSyncError(f"README heat matrix has duplicate row {key}")
        grouped[key] = row
    try:
        levels = tuple(sorted({int(row["Level"]) for row in rows}))
    except ValueError as error:
        raise MatrixSyncError("README heat matrix contains a non-numeric level") from error
    expected = {
        (str(level), discipline) for level in levels for discipline in disciplines
    }
    _key_difference(set(grouped), expected, "README heat matrix")
    table_rows = [
        [
            str(level),
            *[
                _public_result(grouped[(str(level), discipline)])
                for discipline in disciplines
            ],
        ]
        for level in levels
    ]
    headers = ("Level", *(discipline.replace("_", " ").title() for discipline in disciplines))
    return _markdown_table(headers, table_rows)


def render_single_target_damage(
    damage_rows: Sequence[MatrixRow],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    rows = [
        row
        for row in damage_rows
        if row["Damage Scope"] == "primary-target DPR"
        and int(row["Cluster Size"]) == 1
    ]
    if not rows:
        raise MatrixSyncError(
            "Single-target README damage requires primary-target cluster size 1"
        )
    return _heat_table(rows, disciplines)


def render_damage_region(
    damage_rows: Sequence[MatrixRow],
    rules_version: str,
    review: DamageReviewDisposition,
    profile: str,
    target_profile: str,
    target_count: int,
    run_manifest_sha256: str,
    clusters: Sequence[int],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    if 1 not in clusters:
        raise MatrixSyncError("Single-target README snapshot requires cluster size 1")
    if review.current_rules_version != rules_version:
        raise MatrixSyncError(
            "README review disposition differs from canonical rules version"
        )
    if review.review_disposition == CARRIED_FORWARD_REVIEW:
        if review.review_basis_rules_version == review.current_rules_version or any(
            (
                review.fresh_full_roster_run,
                review.fresh_numerical_certification,
                review.fresh_monte_carlo_certification,
            )
        ):
            raise MatrixSyncError("Carried-forward damage-review flags are inconsistent")
        review_text = (
            "Numerical-review basis: reviewed rules "
            f"**v{review.review_basis_rules_version}** evidence "
            f"(`{review.review_status}`). Snapshot values are carried forward from "
            "that reviewed evidence and were not regenerated for "
            f"**v{review.current_rules_version}**. No fresh "
            f"**v{review.current_rules_version}** full-roster run, numerical "
            "certification, or Monte Carlo certification was performed. "
            f"Reason: {review.reason}"
        )
    elif review.review_disposition == FRESH_EXPANDED_ROSTER_REVIEW:
        if not review.fresh_full_roster_run or review.fresh_numerical_certification or review.fresh_monte_carlo_certification:
            raise MatrixSyncError("Fresh expanded-roster review flags are inconsistent")
        review_text = (
            f"A fresh exact analytical run for **v{review.current_rules_version}** "
            f"used all {target_count} targets in `{target_profile}`. It replaces the "
            "carried-forward snapshot, while the independently reviewed rules "
            f"**v{review.review_basis_rules_version}** evidence remains the review "
            f"basis (`{review.review_status}`). No fresh independent numerical or "
            "Monte Carlo certification is claimed. "
            f"Run-manifest SHA-256: `{run_manifest_sha256}`."
        )
    else:
        raise MatrixSyncError("Unsupported README damage-review disposition")
    lines = [
        BEGIN_MARKER,
        "## Damage benchmark snapshot",
        "",
        f"**Current canonical damage authority:** rules **v{rules_version}**.",
        "",
        f"Kinetic Vanguard profile: `{profile}`.",
        "",
        f"Target profile: `{target_profile}` ({target_count} source-ordered targets).",
        "",
        review_text,
        "",
        (
            "Battle Master and Eldritch Knight define the comparison envelope. `IDEAL` "
            "means Kinetic Vanguard falls between the two damage results, inclusive. "
            "`COLD` is below both; `HOT` is above both. The percentage on COLD and HOT "
            "cells is the signed distance outside the nearest envelope boundary. `N/A` "
            "is reserved for a comparison that cannot be evaluated."
        ),
        "",
        (
            "This single-target view is primary-target DPR at cluster size 1. README "
            "cells contain only the public damage result. Generated detailed analytical "
            "CSV, Markdown, and HTML reports retain raw aggregates, ratios, boundaries, "
            "classifications, and provenance; all other primary-target and "
            "aggregate-cluster results remain in those reports."
        ),
        "",
        render_single_target_damage(damage_rows, disciplines),
        "",
        (
            "Kinetic Vanguard mechanics come from "
            "[`KineticVanguard.yaml`](KineticVanguard.yaml). See the "
            "[maintained damage harness guide](harness/README.md), "
            "[methodology configuration](harness/config/benchmark.json), "
            "[SRD creature catalog audit](docs/srd-creature-catalog-audit.md), and "
            "[comparator assumptions](harness/comparators/fighter-subclasses.json)."
        ),
        "",
        (
            COMPARATOR_NOTICE
            + " See [`LICENSE.md`](LICENSE.md) for component boundaries and "
            "[`NOTICE.md`](NOTICE.md) for attribution and notices."
        ),
        END_MARKER,
    ]
    return "\n".join(lines)


def generated_region_span(readme: str) -> tuple[int, int]:
    if readme.count(BEGIN_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise MatrixSyncError(
            "README must contain exactly one generated damage-matrix marker pair"
        )
    start = readme.index(BEGIN_MARKER)
    end_start = readme.find(END_MARKER, start + len(BEGIN_MARKER))
    if end_start < 0:
        raise MatrixSyncError("README damage-matrix markers are reversed")
    return start, end_start + len(END_MARKER)


def replace_generated_region(readme: str, region: str) -> str:
    start, end = generated_region_span(readme)
    return readme[:start] + region + readme[end:]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize the README damage matrix with the analytical harness"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--report-input", type=Path, required=True)
    args = parser.parse_args()

    input_fingerprints = synchronization_input_fingerprints()
    readme = README_PATH.read_text(encoding="utf-8")
    generated_region_span(readme)
    model = DamageAuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    review = load_damage_review_disposition(
        model.rules_version,
        str(config["methodology"]["status"]),
    )
    verified = load_verified_damage_run(args.report_input)
    validate_damage_review_run_evidence(review, verified)
    damage_rows = list(verified.rows)
    rules_version, status, profile, clusters, disciplines = validate_authoritative_rows(
        damage_rows,
        verified.inputs,
    )
    if review.current_rules_version != rules_version or review.review_status != status:
        raise MatrixSyncError(
            "Generated damage matrix differs from preflight review disposition"
        )
    region = render_damage_region(
        damage_rows,
        rules_version,
        review,
        profile,
        str(verified.inputs["target_profile_id"]),
        verified.target_count,
        verified.manifest_sha256,
        clusters,
        disciplines,
    )
    synchronized = replace_generated_region(readme, region)
    require_unchanged_inputs(input_fingerprints)
    if README_PATH.read_text(encoding="utf-8") != readme:
        raise MatrixSyncError("README changed during report synchronization; retry")

    if args.check:
        if synchronized != readme:
            raise SystemExit(
                "README damage benchmark snapshot is stale; run "
                "npm run readme:damage -- --report-input "
                + shlex.quote(str(verified.manifest_path))
            )
        print(f"README damage benchmark snapshot is synchronized for v{rules_version}")
        return

    if synchronized != readme:
        atomic_replace_text(README_PATH, readme, synchronized)
        print(f"Updated README damage benchmark snapshot for v{rules_version}")
    else:
        print(f"README damage benchmark snapshot was already current for v{rules_version}")


if __name__ == "__main__":
    main()
