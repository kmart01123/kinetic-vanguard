"""Synchronize the README damage snapshot from a fresh authoritative matrix."""

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

from .authority import DamageAuthorityModel, DEFAULT_AUTHORITY, PROJECT_ROOT
from .damage_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    VALUE_COLUMNS,
    damage_matrix_row,
)
from .damage_harness import run as run_damage
from .model import (
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_ROSTER,
    file_sha256,
    load_config,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED DAMAGE MATRIX -->"
END_MARKER = "<!-- END GENERATED DAMAGE MATRIX -->"
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
    "Provenance Roster Sha256",
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

    expected = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTER),
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Trials": str(config["methodology"]["damage_default_trials"]),
        "Provenance Seed": str(config["methodology"]["damage_seed"]),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Trial Seed Role": "historical_compatibility_metadata",
        "Provenance Aggregation": (
            "equal-weight roster means; percentages from displayed aggregates"
        ),
        "Provenance Status": status,
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
    serialized = "\n".join(",".join(row.values()) for row in damage_rows)
    if re.search(r"hunter.?ranger|open.?hand.?monk", serialized, re.IGNORECASE):
        raise MatrixSyncError("A retired comparator entered the headline damage matrix")

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


def render_damage_region(
    readme: str,
    damage_rows: Sequence[MatrixRow],
    rules_version: str,
    status: str,
    profile: str,
    clusters: Sequence[int],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    release_line = release_state_line(readme, rules_version)
    if 1 not in clusters:
        raise MatrixSyncError("Single-target README snapshot requires cluster size 1")
    lines = [
        BEGIN_MARKER,
        "## Damage benchmark snapshot",
        "",
        release_line,
        "",
        (
            f"Profile: `{profile}`. Numerical review status: `{status}`. "
            "These are exact analytical full-roster damage results, not Monte Carlo "
            "estimates."
        ),
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
            "cells contain only the public damage result. Detailed release CSV, Markdown, "
            "and HTML reports retain raw aggregates, ratios, boundaries, classifications, "
            "and provenance; all other primary-target and aggregate-cluster results remain "
            "in those reports."
        ),
        "",
        render_single_target_damage(damage_rows, disciplines),
        "",
        (
            "Kinetic Vanguard mechanics come from "
            "[`KineticVanguard.yaml`](KineticVanguard.yaml). See the "
            "[maintained damage harness guide](harness/README.md), "
            "[methodology configuration](harness/config/benchmark.json), "
            "[SRD target roster](harness/data/srd_targets.csv), and "
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


def generate_authoritative_rows(workers: int) -> list[MatrixRow]:
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    methodology = config["methodology"]
    with tempfile.TemporaryDirectory(prefix="kv-readme-damage-") as directory:
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
        return read_matrix_rows(damage["paths"]["csv"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize the README damage matrix with the analytical harness"
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
    damage_rows = generate_authoritative_rows(args.workers)
    rules_version, status, profile, clusters, disciplines = validate_authoritative_rows(
        damage_rows
    )
    region = render_damage_region(
        readme,
        damage_rows,
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
                "README damage benchmark snapshot is stale; run npm run readme:damage"
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
