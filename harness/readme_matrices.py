# Synchronize the README balance snapshot from fresh authoritative harness matrices.

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Sequence

from .authority import AuthorityModel, DEFAULT_AUTHORITY, PROJECT_ROOT
from .comparison_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    VALUE_COLUMNS,
    matrix_row,
)
from .control_harness import run as run_control
from .damage_harness import run as run_damage
from .model import (
    DEFAULT_CATALOG,
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_ROSTERS,
    file_sha256,
    load_config,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED BALANCE MATRICES -->"
END_MARKER = "<!-- END GENERATED BALANCE MATRICES -->"
README_PATH = PROJECT_ROOT / "README.md"
BUILD_INPUTS_PATH = PROJECT_ROOT / "build" / "inputs.json"
DAMAGE_SCOPES = ("primary-target DPR", "aggregate cluster DPR")
README_DISCIPLINES = (
    "cryokinesis",
    "pyrokinesis",
    "psychokinesis",
    "electrokinesis",
)
RESULT_FIELDS = tuple(VALUE_COLUMNS)
PROVENANCE_FIELDS = (
    "Provenance Rules Version",
    "Provenance Authority Sha256",
    "Provenance Catalog Sha256",
    "Provenance Roster Sha256",
    "Provenance Target Profile",
    "Provenance Config Sha256",
    "Provenance Comparator Config Sha256",
    "Provenance Trials",
    "Provenance Seed",
    "Provenance Evaluator",
    "Provenance Trial Seed Role",
    "Provenance Aggregation",
    "Provenance Status",
)
MatrixRow = dict[str, str]


class MatrixSyncError(ValueError):
    pass


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
            "Synchronization inputs changed during analytical evaluation: "
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


def _require_fields(rows: Sequence[MatrixRow], fields: Sequence[str], kind: str) -> None:
    expected = set(fields)
    for index, row in enumerate(rows):
        missing = [field for field in fields if field not in row]
        unexpected = [field for field in row if field not in expected]
        if missing or unexpected:
            raise MatrixSyncError(
                f"{kind} row {index} has schema differences; "
                f"missing={missing}, unexpected={unexpected}"
            )


def _uniform(rows: Sequence[MatrixRow], field: str, kind: str) -> str:
    values = {row[field] for row in rows}
    if len(values) != 1:
        raise MatrixSyncError(f"{kind} matrix has inconsistent {field}: {sorted(values)}")
    return next(iter(values))


def _key_difference(actual: set[tuple[str, ...]], expected: set[tuple[str, ...]], kind: str) -> None:
    if actual == expected:
        return
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    raise MatrixSyncError(f"{kind} row identities differ; missing={missing}, extra={extra}")


def validate_authoritative_rows(
    damage_rows: Sequence[MatrixRow], control_rows: Sequence[MatrixRow]
) -> tuple[str, str, str, tuple[int, ...], tuple[str, ...]]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
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
        "damage",
    )
    _require_fields(
        control_rows,
        (
            "Level",
            "Discipline",
            "Metric",
            "Profile",
            *RESULT_FIELDS,
            *PROVENANCE_FIELDS,
            *NOTICE_COLUMNS,
        ),
        "control",
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
    _key_difference(actual_damage, expected_damage, "damage")
    if len(damage_rows) != len(expected_damage):
        raise MatrixSyncError("Damage matrix contains duplicate row identities")

    expected_control = {
        (str(level), discipline) for level in levels for discipline in disciplines
    }
    actual_control = {(row["Level"], row["Discipline"]) for row in control_rows}
    _key_difference(actual_control, expected_control, "control")
    if len(control_rows) != len(expected_control):
        raise MatrixSyncError("Control matrix contains duplicate row identities")

    expected_common = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Catalog Sha256": file_sha256(DEFAULT_CATALOG),
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTERS),
        "Provenance Target Profile": DEFAULT_PROFILE,
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Trial Seed Role": "historical_compatibility_metadata",
        "Provenance Status": status,
        "Profile": profile,
    }

    for kind, rows in (("damage", damage_rows), ("control", control_rows)):
        expected = {
            **expected_common,
            "Provenance Trials": str(config["methodology"][f"{kind}_default_trials"]),
            "Provenance Seed": str(config["methodology"][f"{kind}_seed"]),
            "Provenance Aggregation": (
                "equal-weight roster means; percentages from displayed aggregates"
                if kind == "damage"
                else str(config["control_matrix"]["aggregation"])
            ),
        }
        for index, row in enumerate(rows):
            for field, value in expected.items():
                if row[field] != value:
                    raise MatrixSyncError(
                        f"{kind} row {index} has {field}={row[field]!r}; expected {value!r}"
                    )
            for field, value in NOTICE_COLUMNS.items():
                if row[field] != value:
                    raise MatrixSyncError(f"{kind} row {index} changed notice field {field}")
            recomputed = matrix_row(
                {},
                float(row["KV"]),
                float(row["Eldritch Knight"]),
                float(row["Battle Master"]),
                kind,
            )
            for field in RESULT_FIELDS:
                if row[field] != recomputed[field]:
                    raise MatrixSyncError(
                        f"{kind} row {index} has stale {field}: {row[field]} != {recomputed[field]}"
                    )

    metric = str(config["control_matrix"]["metric"])
    if _uniform(control_rows, "Metric", "control") != metric:
        raise MatrixSyncError("Control matrix metric differs from benchmark configuration")
    if _uniform(damage_rows, "Provenance Rules Version", "damage") != model.rules_version:
        raise MatrixSyncError("Damage matrix rules version differs from canonical authority")
    if _uniform(control_rows, "Provenance Rules Version", "control") != model.rules_version:
        raise MatrixSyncError("Control matrix rules version differs from canonical authority")

    serialized = "\n".join(",".join(row.values()) for row in (*damage_rows, *control_rows))
    if re.search(r"hunter.?ranger|open.?hand.?monk", serialized, re.IGNORECASE):
        raise MatrixSyncError("A retired comparator entered the headline matrices")

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
        raise MatrixSyncError(f"Unsupported public balance result: {band}")
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


def render_control_table(
    control_rows: Sequence[MatrixRow],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    return _heat_table(control_rows, disciplines)


def release_state_line(readme: str, rules_version: str) -> str:
    published_lines = re.findall(r"^- Current published release:.*$", readme, re.MULTILINE)
    development_lines = re.findall(r"^- Current development line:.*$", readme, re.MULTILINE)
    published_matches = re.findall(
        r"^- Current published release: \*\*v(\d+\.\d+\.\d+)\*\*$",
        readme,
        re.MULTILINE,
    )
    development_matches = re.findall(
        r"^- Current development line: \*\*(v\d+\.\d+\.\d+|None)\*\*$",
        readme,
        re.MULTILINE,
    )
    if (
        len(published_lines) != 1
        or len(development_lines) != 1
        or len(published_matches) != 1
        or len(development_matches) != 1
    ):
        raise MatrixSyncError(
            "README must contain exactly one published and one development release-status line"
        )
    published = published_matches[0]
    development = development_matches[0]
    if published == rules_version:
        if development != "None":
            raise MatrixSyncError(
                "A published canonical snapshot requires development line None"
            )
        return f"**Published snapshot** — canonical rules **v{rules_version}**."
    if development == f"v{rules_version}":
        return (
            f"**Unreleased development snapshot** — canonical rules **v{rules_version}**; "
            f"current published release **v{published}**."
        )
    raise MatrixSyncError(
        f"Rules v{rules_version} is neither README published v{published} nor development {development}"
    )


def render_balance_region(
    readme: str,
    damage_rows: Sequence[MatrixRow],
    control_rows: Sequence[MatrixRow],
    rules_version: str,
    status: str,
    profile: str,
    clusters: Sequence[int],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    release_line = release_state_line(readme, rules_version)
    metric = _uniform(control_rows, "Metric", "control")
    if 1 not in clusters:
        raise MatrixSyncError("Single-target README snapshot requires cluster size 1")
    lines = [
        BEGIN_MARKER,
        "## Balance benchmark snapshot",
        "",
        release_line,
        "",
        (
            f"Profile: `{profile}`. Numerical review status: `{status}`. "
            "These are exact analytical full-roster results, not Monte Carlo estimates."
        ),
        "",
        (
            "Battle Master and Eldritch Knight define the comparison envelope for each "
            "benchmark result. `IDEAL` means Kinetic Vanguard falls between the two "
            "comparator results, inclusive. `COLD` is below both; `HOT` is above both. "
            "The percentage on COLD and HOT cells shows the signed distance outside the nearest "
            "envelope boundary. `N/A` is reserved for a comparison that cannot be evaluated."
        ),
        "",
        (
            "README cells intentionally contain only the public balance result: `IDEAL`, "
            "`COLD (-X%)`, `HOT (+X%)`, or `N/A`. Detailed release CSV, Markdown, "
            "and HTML reports retain raw Kinetic Vanguard and comparator aggregates, ordinary "
            "KV/comparator ratios, dynamic lower and upper boundaries, and the comparator "
            "identity supplying each boundary."
        ),
        "",
        (
            "The front-door damage view is the single-target benchmark: primary-target DPR "
            "at cluster size 1. All other primary-target and aggregate-cluster results remain "
            "in the generated detailed release reports and are not collapsed into this table."
        ),
        "",
        "### Single-Target Damage",
        "",
        render_single_target_damage(damage_rows, disciplines),
        "",
        "### Control Reliability",
        "",
        (
            "This single-target benchmark evaluates each configured control package against "
            "one roster target at a time before taking the equal-weight roster mean."
        ),
        "",
        f"Configured headline metric: **{metric}**.",
        "",
        (
            "This v14.2 snapshot evaluates legal repeated attack-delivered opportunities within "
            "one ordinary Attack action when the configured package permits them. Kinetic Vanguard "
            "Signature Riders were already 0-Psi and repeatable before issue #58; issue #58 newly "
            "extends that repeatability to paid on-hit riders. Battle Master maneuvers receive legal "
            "hit-gated retries, while Eldritch Knight keeps one Blindness/Deafness cast and uses all "
            "ordinary primer attacks for Eldritch Strike. Published v14.1 used simpler one-shot "
            "approximations, so control deltas can combine the paid-rider rule with historical KV, "
            "Battle Master, and Eldritch Knight evaluator corrections. Those effects interact and "
            "are not assumed to be additively separable."
        ),
        "",
        (
            "Control Reliability measures how often the configured control package takes effect. "
            "It does not measure the relative severity, duration, area, or strategic value of "
            "different control effects. A HOT result is a balance-review signal, not an automatic "
            "finding that the feature is overpowered."
        ),
        "",
        render_control_table(control_rows, disciplines),
        "",
        (
            "This snapshot is a summary, not the full evidence set. Kinetic Vanguard mechanics "
            "come from [`KineticVanguard.yaml`](KineticVanguard.yaml). See the "
            "[maintained harness guide](harness/README.md), "
            "[methodology configuration](harness/config/benchmark.json), "
            "[SRD creature profiles](harness/data/srd_creature_rosters.json), and "
            "[comparator assumptions](harness/comparators/fighter-subclasses.json) for the "
            "complete methodology, provenance, regeneration commands, and report paths."
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
        raise MatrixSyncError("README must contain exactly one generated balance-matrix marker pair")
    start = readme.index(BEGIN_MARKER)
    end_start = readme.find(END_MARKER, start + len(BEGIN_MARKER))
    if end_start < 0:
        raise MatrixSyncError("README balance-matrix markers are reversed")
    return start, end_start + len(END_MARKER)


def replace_generated_region(readme: str, region: str) -> str:
    start, end = generated_region_span(readme)
    return readme[:start] + region + readme[end:]


def generate_authoritative_rows(workers: int) -> tuple[list[MatrixRow], list[MatrixRow]]:
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    methodology = config["methodology"]
    with tempfile.TemporaryDirectory(prefix="kv-readme-matrices-") as directory:
        root = Path(directory)
        damage = run_damage(
            DEFAULT_AUTHORITY,
            root / "damage",
            levels,
            None,
            int(methodology["damage_default_trials"]),
            int(methodology["damage_seed"]),
            False,
            True,
            workers,
        )
        control = run_control(
            DEFAULT_AUTHORITY,
            root / "control",
            levels,
            None,
            int(methodology["control_default_trials"]),
            int(methodology["control_seed"]),
            False,
            True,
        )
        return (
            read_matrix_rows(damage["paths"]["csv"]),
            read_matrix_rows(control["paths"]["csv"]),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize README balance matrices with the exact analytical harness"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("--workers must be positive")

    input_fingerprints = synchronization_input_fingerprints()
    readme = README_PATH.read_text(encoding="utf-8")
    generated_region_span(readme)
    damage_rows, control_rows = generate_authoritative_rows(args.workers)
    rules_version, status, profile, clusters, disciplines = validate_authoritative_rows(
        damage_rows, control_rows
    )
    region = render_balance_region(
        readme,
        damage_rows,
        control_rows,
        rules_version,
        status,
        profile,
        clusters,
        disciplines,
    )
    synchronized = replace_generated_region(readme, region)
    require_unchanged_inputs(input_fingerprints)
    if README_PATH.read_text(encoding="utf-8") != readme:
        raise MatrixSyncError("README changed during analytical evaluation; retry synchronization")

    if args.check:
        if synchronized != readme:
            raise SystemExit(
                "README balance benchmark snapshot is stale; run npm run readme:benchmarks"
            )
        print(f"README balance benchmark snapshot is synchronized for v{rules_version}")
        return

    if synchronized != readme:
        atomic_replace_text(README_PATH, readme, synchronized)
        print(f"Updated README balance benchmark snapshot for v{rules_version}")
    else:
        print(f"README balance benchmark snapshot was already current for v{rules_version}")


if __name__ == "__main__":
    main()
