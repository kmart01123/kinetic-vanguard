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
from .comparison_report import COMPARATOR_NOTICE, NOTICE_COLUMNS, matrix_row
from .control_harness import run as run_control
from .damage_harness import run as run_damage
from .model import (
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_ROSTER,
    file_sha256,
    load_config,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED BALANCE MATRICES -->"
END_MARKER = "<!-- END GENERATED BALANCE MATRICES -->"
README_PATH = PROJECT_ROOT / "README.md"
BUILD_INPUTS_PATH = PROJECT_ROOT / "build" / "inputs.json"
DAMAGE_SCOPES = ("primary-target DPR", "aggregate cluster DPR")
DAMAGE_SCOPE_TITLES = {
    "primary-target DPR": "Primary-target DPR",
    "aggregate cluster DPR": "Aggregate cluster DPR",
}
RESULT_FIELDS = (
    "KV",
    "Eldritch Knight",
    "Battle Master",
    "KV as % of EK",
    "KV as % of BM",
    "Band",
    "Boundary Delta %",
)
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
) -> tuple[str, str, str, tuple[int, ...]]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    clusters = tuple(int(value) for value in config["methodology"]["cluster_sizes"])
    disciplines = tuple(sorted(model.disciplines))
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
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTER),
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

    return model.rules_version, status, profile, clusters


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


def _triplet(rows: Sequence[MatrixRow], field: str) -> str:
    return " / ".join(row[field] for row in rows)


def render_damage_scope(
    damage_rows: Sequence[MatrixRow], scope: str, clusters: Sequence[int]
) -> str:
    if scope not in DAMAGE_SCOPE_TITLES:
        raise MatrixSyncError(f"Unsupported damage scope: {scope}")
    grouped: dict[tuple[str, str], list[MatrixRow]] = {}
    for row in damage_rows:
        if row["Damage Scope"] == scope:
            grouped.setdefault((row["Level"], row["Discipline"]), []).append(row)

    table_rows: list[list[str]] = []
    for key in sorted(grouped, key=lambda item: (int(item[0]), item[1])):
        rows = sorted(grouped[key], key=lambda row: int(row["Cluster Size"]))
        actual_clusters = tuple(int(row["Cluster Size"]) for row in rows)
        if actual_clusters != tuple(clusters):
            raise MatrixSyncError(
                f"{scope} {key} clusters are {actual_clusters}; expected {tuple(clusters)}"
            )
        for comparator in ("Eldritch Knight", "Battle Master"):
            if len({row[comparator] for row in rows}) != 1:
                raise MatrixSyncError(f"{scope} {key} has cluster-dependent {comparator} DPR")
        table_rows.append(
            [
                key[0],
                key[1].replace("_", " ").title(),
                _triplet(rows, "KV"),
                rows[0]["Eldritch Knight"],
                rows[0]["Battle Master"],
                _triplet(rows, "KV as % of EK"),
                _triplet(rows, "KV as % of BM"),
                _triplet(rows, "Band"),
            ]
        )

    cluster_columns = " / ".join(f"C{cluster}" for cluster in clusters)
    headers = (
        "Fighter level",
        "Discipline",
        f"KV DPR ({cluster_columns})",
        "Eldritch Knight DPR",
        "Battle Master DPR",
        f"KV as % of EK ({cluster_columns})",
        f"KV as % of BM ({cluster_columns})",
        f"Band ({cluster_columns})",
    )
    return f"#### {DAMAGE_SCOPE_TITLES[scope]}\n\n{_markdown_table(headers, table_rows)}"


def render_control_table(control_rows: Sequence[MatrixRow]) -> str:
    table_rows = [
        [
            row["Level"],
            row["Discipline"].replace("_", " ").title(),
            row["KV"],
            row["Eldritch Knight"],
            row["Battle Master"],
            row["KV as % of EK"],
            row["KV as % of BM"],
            row["Band"],
        ]
        for row in sorted(
            control_rows, key=lambda row: (int(row["Level"]), row["Discipline"])
        )
    ]
    headers = (
        "Fighter level",
        "Discipline",
        "KV control %",
        "Eldritch Knight control %",
        "Battle Master control %",
        "KV as % of EK",
        "KV as % of BM",
        "Band",
    )
    return _markdown_table(headers, table_rows)


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
) -> str:
    release_line = release_state_line(readme, rules_version)
    metric = _uniform(control_rows, "Metric", "control")
    cluster_label = " / ".join(str(value) for value in clusters)
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
            "Battle Master and Eldritch Knight are recognizable Fighter-subclass reference points. "
            "The comparison asks whether Kinetic Vanguard sits inside a useful martial Fighter "
            "balance envelope; it does not predict every table or make unlike control conditions "
            "equally valuable."
        ),
        "",
        "### Damage benchmark",
        "",
        (
            f"Values are damage per round (DPR). Slash-separated entries correspond, in order, "
            f"to cluster sizes **{cluster_label}**. Each entry is a separate equal-weight roster "
            "mean; the cluster-size results are not averaged together. Comparator DPR is "
            "cluster-independent and appears once per row. Primary-target and aggregate-cluster "
            "results remain separate."
        ),
        "",
        "**Damage band legend** — expected comparator order: Eldritch Knight ≤ Battle Master.",
        "",
        "- `COLD`: KV is below Eldritch Knight.",
        "- `IDEAL`: KV is between Eldritch Knight and Battle Master, inclusive.",
        "- `HOT`: KV is above Battle Master.",
        "- `ORDER CHECK`: comparator ordering is reversed for that result.",
        "- `N/A`: a ratio or comparison is not defined.",
        "",
        render_damage_scope(damage_rows, "primary-target DPR", clusters),
        "",
        render_damage_scope(damage_rows, "aggregate cluster DPR", clusters),
        "",
        "### Control benchmark",
        "",
        (
            f"Metric: **{metric}**. This is a best-available reliability envelope, not DPR or a "
            "condition-severity score. Ratios remain ordinary KV/comparator percentages and are "
            "not mathematically inverted."
        ),
        "",
        "**Control band legend** — expected comparator order: Battle Master ≤ Eldritch Knight.",
        "",
        "- `COLD`: KV is below Battle Master.",
        "- `IDEAL`: KV is between Battle Master and Eldritch Knight, inclusive.",
        "- `HOT`: KV is above Eldritch Knight.",
        "- `ORDER CHECK`: comparator ordering is reversed for that result.",
        "- `N/A`: a ratio or comparison is not defined.",
        "",
        render_control_table(control_rows),
        "",
        (
            "This snapshot is a summary, not the full evidence set. Kinetic Vanguard mechanics "
            "come from [`KineticVanguard.yaml`](KineticVanguard.yaml). See the "
            "[maintained harness guide](harness/README.md), "
            "[methodology configuration](harness/config/benchmark.json), "
            "[SRD target roster](harness/data/srd_targets.csv), and "
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
    rules_version, status, profile, clusters = validate_authoritative_rows(
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
