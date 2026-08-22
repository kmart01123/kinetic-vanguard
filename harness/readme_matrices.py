# Synchronize the README balance snapshot from fresh authoritative harness matrices.

from __future__ import annotations

import argparse
import csv
import math
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
from .control_value import DEFAULT_PRIMITIVES, DEFAULT_SCORING
from .damage_harness import run as run_damage
from .model import (
    DEFAULT_CATALOG,
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_ROSTERS,
    PROFILE_LEVEL_COUNTS,
    file_sha256,
    load_config,
    load_targets,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED BALANCE MATRICES -->"
END_MARKER = "<!-- END GENERATED BALANCE MATRICES -->"
README_PATH = PROJECT_ROOT / "README.md"
DAMAGE_SECTION_START = "The front-door damage view is the single-target benchmark:"
DAMAGE_SCOPES = ("primary-target DPR", "aggregate cluster DPR")
README_DISCIPLINES = (
    "cryokinesis",
    "pyrokinesis",
    "psychokinesis",
    "electrokinesis",
)
RESULT_FIELDS = tuple(VALUE_COLUMNS)
COMMON_PROVENANCE_FIELDS = (
    "Provenance Rules Version",
    "Provenance Authority Sha256",
    "Provenance Catalog Sha256",
    "Provenance Roster Sha256",
    "Provenance Target Profile",
    "Provenance Config Sha256",
    "Provenance Comparator Config Sha256",
    "Provenance Evaluator",
    "Provenance Aggregation",
)
DAMAGE_PROVENANCE_FIELDS = COMMON_PROVENANCE_FIELDS
RELIABILITY_PROVENANCE_FIELDS = (
    *COMMON_PROVENANCE_FIELDS,
    "Provenance Control Primitive Catalog Sha256",
    "Provenance Control Value Config Sha256",
)
MatrixRow = dict[str, str]
VALUE_COLUMNS_RAW = (
    "Level",
    "Discipline",
    "Kinetic Vanguard Control Value CU",
    "Eldritch Knight Control Value CU",
    "Battle Master Control Value CU",
    "Targets",
    "Rules Version",
    "Authority SHA-256",
    "Catalog SHA-256",
    "Roster SHA-256",
    "Target Profile",
    "Config SHA-256",
    "Comparator Config SHA-256",
    *NOTICE_COLUMNS,
    "Control Primitive Catalog SHA-256",
    "Control Value Config SHA-256",
)
VALUE_AUDIT_COLUMNS = (
    "Level",
    "Target",
    "Discipline",
    "Build",
    "Selected Scenario",
    "Eligible",
    "Selection Basis",
    "Control Value CU",
    "Whole-package control stick %",
    "Value Disposition",
    "Rules Version",
    "Authority SHA-256",
    "Catalog SHA-256",
    "Roster SHA-256",
    "Target Profile",
    "Config SHA-256",
    "Comparator Config SHA-256",
    *NOTICE_COLUMNS,
    "Control Primitive Catalog SHA-256",
    "Control Value Config SHA-256",
)


class MatrixSyncError(ValueError):
    pass


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


def validate_reliability_rows(
    control_rows: Sequence[MatrixRow],
) -> tuple[str, str, tuple[int, ...], tuple[str, ...]]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    disciplines = README_DISCIPLINES
    if set(disciplines) != set(model.disciplines):
        raise MatrixSyncError(
            "README discipline columns differ from the canonical discipline set"
        )

    _require_fields(
        control_rows,
        (
            "Level",
            "Discipline",
            "Metric",
            "Profile",
            *RESULT_FIELDS,
            *RELIABILITY_PROVENANCE_FIELDS,
            *NOTICE_COLUMNS,
        ),
        "control",
    )
    expected_identities = {
        (str(level), discipline) for level in levels for discipline in disciplines
    }
    actual_identities = {
        (row["Level"], row["Discipline"]) for row in control_rows
    }
    _key_difference(actual_identities, expected_identities, "control")
    if len(control_rows) != len(expected_identities):
        raise MatrixSyncError("Control matrix contains duplicate row identities")

    expected = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Catalog Sha256": file_sha256(DEFAULT_CATALOG),
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTERS),
        "Provenance Target Profile": DEFAULT_PROFILE,
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Control Primitive Catalog Sha256": file_sha256(DEFAULT_PRIMITIVES),
        "Provenance Control Value Config Sha256": file_sha256(DEFAULT_SCORING),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Aggregation": str(config["control_matrix"]["aggregation"]),
        "Profile": str(config["kv_profile"]["id"]),
    }
    for index, row in enumerate(control_rows):
        for field, value in expected.items():
            if row[field] != value:
                raise MatrixSyncError(
                    f"control row {index} has {field}={row[field]!r}; expected {value!r}"
                )
        for field, value in NOTICE_COLUMNS.items():
            if row[field] != value:
                raise MatrixSyncError(f"control row {index} changed notice field {field}")
        recomputed = matrix_row(
            {},
            float(row["KV"]),
            float(row["Eldritch Knight"]),
            float(row["Battle Master"]),
            "control",
        )
        for field in RESULT_FIELDS:
            if row[field] != recomputed[field]:
                raise MatrixSyncError(
                    f"control row {index} has stale {field}: "
                    f"{row[field]} != {recomputed[field]}"
                )

    metric = str(config["control_matrix"]["metric"])
    if _uniform(control_rows, "Metric", "control") != metric:
        raise MatrixSyncError("Control matrix metric differs from benchmark configuration")
    return model.rules_version, DEFAULT_PROFILE, levels, disciplines


def _validate_value_source(
    row: MatrixRow, index: int, kind: str, expected: dict[str, str]
) -> None:
    for field, value in (*expected.items(), *NOTICE_COLUMNS.items()):
        if row[field] != value:
            raise MatrixSyncError(
                f"{kind} row {index} has {field}={row[field]!r}; expected {value!r}"
            )


def validate_value_rows(
    value_rows: Sequence[MatrixRow], value_audit_rows: Sequence[MatrixRow]
) -> list[MatrixRow]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    disciplines = README_DISCIPLINES
    expected_matrix_identities = {
        (str(level), discipline) for level in levels for discipline in disciplines
    }
    expected_source = {
        "Rules Version": model.rules_version,
        "Authority SHA-256": model.authority_sha256,
        "Catalog SHA-256": file_sha256(DEFAULT_CATALOG),
        "Roster SHA-256": file_sha256(DEFAULT_ROSTERS),
        "Target Profile": DEFAULT_PROFILE,
        "Config SHA-256": file_sha256(DEFAULT_CONFIG),
        "Comparator Config SHA-256": file_sha256(DEFAULT_COMPARATORS),
        "Control Primitive Catalog SHA-256": file_sha256(DEFAULT_PRIMITIVES),
        "Control Value Config SHA-256": file_sha256(DEFAULT_SCORING),
    }

    _require_fields(value_rows, VALUE_COLUMNS_RAW, "Control Value")
    actual_matrix_identities = {
        (row["Level"], row["Discipline"]) for row in value_rows
    }
    _key_difference(
        actual_matrix_identities, expected_matrix_identities, "Control Value"
    )
    if len(value_rows) != len(expected_matrix_identities):
        raise MatrixSyncError("Control Value matrix contains duplicate row identities")

    _require_fields(value_audit_rows, VALUE_AUDIT_COLUMNS, "Control Value audit")
    targets = load_targets(profile=DEFAULT_PROFILE, levels=set(levels))
    expected_audit_identities: set[tuple[str, str, str, str]] = set()
    for target in targets:
        expected_audit_identities.update(
            {
                (str(target.level), target.name, "all", "battle_master"),
                (str(target.level), target.name, "all", "eldritch_knight"),
                *(
                    (
                        str(target.level),
                        target.name,
                        discipline,
                        "kinetic_vanguard",
                    )
                    for discipline in disciplines
                ),
            }
        )
    actual_audit_identities = {
        (row["Level"], row["Target"], row["Discipline"], row["Build"])
        for row in value_audit_rows
    }
    _key_difference(
        actual_audit_identities,
        expected_audit_identities,
        "Control Value audit",
    )
    if len(value_audit_rows) != len(expected_audit_identities):
        raise MatrixSyncError("Control Value audit contains duplicate winner identities")

    audit_values: dict[tuple[str, str, str, str], float] = {}
    allowed_dispositions = {
        "priced_nonzero",
        "legitimately_priced_zero",
        "entirely_context_required_or_unsupported",
    }
    for index, row in enumerate(value_audit_rows):
        _validate_value_source(
            row, index, "Control Value audit", expected_source
        )
        if row["Eligible"] != "True":
            raise MatrixSyncError(
                f"Control Value audit row {index} selected an ineligible winner"
            )
        if not row["Selected Scenario"]:
            raise MatrixSyncError(
                f"Control Value audit row {index} has no selected scenario"
            )
        if row["Selection Basis"] != "Control Value":
            raise MatrixSyncError(
                f"Control Value audit row {index} has a non-CU selection basis"
            )
        if row["Value Disposition"] not in allowed_dispositions:
            raise MatrixSyncError(
                f"Control Value audit row {index} has an invalid disposition"
            )
        try:
            value = float(row["Control Value CU"])
        except ValueError as error:
            raise MatrixSyncError(
                f"Control Value audit row {index} has non-numeric CU"
            ) from error
        if not math.isfinite(value):
            raise MatrixSyncError(
                f"Control Value audit row {index} has non-finite CU"
            )
        try:
            reliability = float(row["Whole-package control stick %"])
        except ValueError as error:
            raise MatrixSyncError(
                f"Control Value audit row {index} has non-numeric Reliability"
            ) from error
        if not math.isfinite(reliability) or not 0.0 <= reliability <= 100.0:
            raise MatrixSyncError(
                f"Control Value audit row {index} has invalid Reliability"
            )
        identity = (row["Level"], row["Target"], row["Discipline"], row["Build"])
        audit_values[identity] = value

    public_rows: list[MatrixRow] = []
    for index, row in enumerate(value_rows):
        _validate_value_source(row, index, "Control Value", expected_source)
        level = int(row["Level"])
        expected_targets = PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][level]
        if row["Targets"] != str(expected_targets):
            raise MatrixSyncError(
                f"Control Value row {index} has Targets={row['Targets']!r}; "
                f"expected {expected_targets}"
            )
        discipline = row["Discipline"]
        level_targets = [target for target in targets if target.level == level]

        def winner_mean(build: str, selected_discipline: str) -> float:
            values = [
                audit_values[
                    (str(level), target.name, selected_discipline, build)
                ]
                for target in level_targets
            ]
            return sum(values) / len(values)

        expected_aggregates = {
            "Kinetic Vanguard Control Value CU": winner_mean(
                "kinetic_vanguard", discipline
            ),
            "Eldritch Knight Control Value CU": winner_mean(
                "eldritch_knight", "all"
            ),
            "Battle Master Control Value CU": winner_mean("battle_master", "all"),
        }
        for field, value in expected_aggregates.items():
            try:
                numeric = float(row[field])
            except ValueError as error:
                raise MatrixSyncError(
                    f"Control Value row {index} has non-numeric {field}"
                ) from error
            if not math.isfinite(numeric):
                raise MatrixSyncError(
                    f"Control Value row {index} has non-finite {field}"
                )
            expected_display = f"{value:.12f}"
            if row[field] != expected_display:
                raise MatrixSyncError(
                    f"Control Value row {index} has stale winner aggregate {field}: "
                    f"{row[field]} != {expected_display}"
                )

        public = matrix_row(
            {"Level": level, "Discipline": discipline},
            expected_aggregates["Kinetic Vanguard Control Value CU"],
            expected_aggregates["Eldritch Knight Control Value CU"],
            expected_aggregates["Battle Master Control Value CU"],
            "control",
        )
        public["Benchmark Type"] = "Control Value"
        public_rows.append(public)

    if set(disciplines) != set(model.disciplines):
        raise MatrixSyncError(
            "README discipline columns differ from the canonical discipline set"
        )
    return public_rows


def validate_reliability_alignment(
    control_rows: Sequence[MatrixRow], value_audit_rows: Sequence[MatrixRow]
) -> list[MatrixRow]:
    """Reconstruct public Reliability solely from the common CU winner audit."""
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    targets = load_targets(profile=DEFAULT_PROFILE, levels=set(levels))
    expected_identities = {
        (str(target.level), target.name, discipline, build)
        for target in targets
        for build, discipline in (
            ("battle_master", "all"),
            ("eldritch_knight", "all"),
            *(("kinetic_vanguard", item) for item in README_DISCIPLINES),
        )
    }
    actual_identities = {
        (row["Level"], row["Target"], row["Discipline"], row["Build"])
        for row in value_audit_rows
    }
    _key_difference(actual_identities, expected_identities, "common selection audit")
    if len(value_audit_rows) != len(expected_identities):
        raise MatrixSyncError("Common selection audit contains duplicate winner identities")
    audit_reliability: dict[tuple[str, str, str, str], float] = {}
    for index, row in enumerate(value_audit_rows):
        if row.get("Selection Basis") != "Control Value":
            raise MatrixSyncError(
                f"Common selection audit row {index} has a non-CU selection basis"
            )
        try:
            value = float(row["Whole-package control stick %"])
        except (KeyError, ValueError) as error:
            raise MatrixSyncError(
                f"Common selection audit row {index} has non-numeric Reliability"
            ) from error
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise MatrixSyncError(
                f"Common selection audit row {index} has invalid Reliability"
            )
        identity = (row["Level"], row["Target"], row["Discipline"], row["Build"])
        audit_reliability[identity] = value

    aligned_rows: list[MatrixRow] = []
    for index, row in enumerate(control_rows):
        level = int(row["Level"])
        discipline = row["Discipline"]
        level_targets = [target for target in targets if target.level == level]

        def winner_mean(build: str, selected_discipline: str) -> float:
            values = [
                audit_reliability[
                    (str(level), target.name, selected_discipline, build)
                ]
                for target in level_targets
            ]
            return sum(values) / len(values)

        expected = matrix_row(
            {"Level": level, "Discipline": discipline},
            winner_mean("kinetic_vanguard", discipline),
            winner_mean("eldritch_knight", "all"),
            winner_mean("battle_master", "all"),
            "control",
        )
        for field in RESULT_FIELDS:
            if row[field] != expected[field]:
                raise MatrixSyncError(
                    f"control row {index} does not match common winner {field}: "
                    f"{row[field]} != {expected[field]}"
                )
        aligned_rows.append(dict(row))
    return aligned_rows


def validate_damage_rows(
    damage_rows: Sequence[MatrixRow],
) -> tuple[str, str, tuple[int, ...], tuple[str, ...]]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    clusters = tuple(int(value) for value in config["methodology"]["cluster_sizes"])
    disciplines = README_DISCIPLINES
    if set(disciplines) != set(model.disciplines):
        raise MatrixSyncError(
            "README discipline columns differ from the canonical discipline set"
        )

    _require_fields(
        damage_rows,
        (
            "Level",
            "Discipline",
            "Cluster Size",
            "Damage Scope",
            "Profile",
            *RESULT_FIELDS,
            *DAMAGE_PROVENANCE_FIELDS,
            *NOTICE_COLUMNS,
        ),
        "damage",
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

    expected = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Catalog Sha256": file_sha256(DEFAULT_CATALOG),
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTERS),
        "Provenance Target Profile": DEFAULT_PROFILE,
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Evaluator": "exact_analytical_enumeration",
        "Provenance Aggregation": (
            "equal-weight roster means; percentages from displayed aggregates"
        ),
        "Profile": str(config["kv_profile"]["id"]),
    }
    for index, row in enumerate(damage_rows):
        for field, value in expected.items():
            if row[field] != value:
                raise MatrixSyncError(
                    f"damage row {index} has {field}={row[field]!r}; expected {value!r}"
                )
        for field, value in NOTICE_COLUMNS.items():
            if row[field] != value:
                raise MatrixSyncError(f"damage row {index} changed notice field {field}")
        recomputed = matrix_row(
            {},
            float(row["KV"]),
            float(row["Eldritch Knight"]),
            float(row["Battle Master"]),
            "damage",
        )
        for field in RESULT_FIELDS:
            if row[field] != recomputed[field]:
                raise MatrixSyncError(
                    f"damage row {index} has stale {field}: "
                    f"{row[field]} != {recomputed[field]}"
                )
    return model.rules_version, DEFAULT_PROFILE, clusters, disciplines


def validate_authoritative_rows(
    damage_rows: Sequence[MatrixRow], control_rows: Sequence[MatrixRow]
) -> tuple[str, str, tuple[int, ...], tuple[str, ...]]:
    damage_contract = validate_damage_rows(damage_rows)
    rules_version, profile, _, disciplines = validate_reliability_rows(control_rows)
    if (
        rules_version,
        profile,
        disciplines,
    ) != (
        damage_contract[0],
        damage_contract[1],
        damage_contract[3],
    ):
        raise MatrixSyncError("Damage and control publication contracts differ")
    return damage_contract


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


def render_damage_section(
    damage_rows: Sequence[MatrixRow],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    return "\n".join(
        (
            (
                "The front-door damage view is the single-target benchmark: "
                "primary-target DPR at cluster size 1. All other primary-target and "
                "aggregate-cluster results remain in the generated detailed release "
                "reports and are not collapsed into this table."
            ),
            "",
            "### Single-Target Damage",
            "",
            render_single_target_damage(damage_rows, disciplines),
            "",
            "",
        )
    )


def extract_damage_section(readme: str) -> str:
    start, end = generated_region_span(readme)
    region = readme[start:end]
    if region.count(DAMAGE_SECTION_START) != 1:
        raise MatrixSyncError(
            "README must contain exactly one preserved Single-Target Damage introduction"
        )
    section_start = region.index(DAMAGE_SECTION_START)
    headings = list(re.finditer(r"^### .+$", region[section_start:], re.MULTILINE))
    if not headings or headings[0].group(0) != "### Single-Target Damage":
        raise MatrixSyncError("README Single-Target Damage heading is missing or misplaced")
    if len(headings) < 2:
        raise MatrixSyncError("README damage subsection has no following control section")
    section_end = section_start + headings[1].start()
    return region[section_start:section_end]


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
    damage_section: str,
    reliability_rows: Sequence[MatrixRow],
    value_rows: Sequence[MatrixRow],
    rules_version: str,
    profile: str,
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    release_line = release_state_line(readme, rules_version)
    metric = _uniform(reliability_rows, "Metric", "control")
    common = "\n".join(
        (
            BEGIN_MARKER,
            "## Balance benchmark snapshot",
            "",
            release_line,
            "",
            (
                f"Target profile: `{profile}`. The maintained headline benchmark uses "
                f"{sum(PROFILE_LEVEL_COUNTS[profile].values())} creature profiles from "
                "SRD 5.2.1 at levels 7, 11, 15, and 20. These are exact analytical "
                "full-roster results, with creatures weighted equally within their level."
            ),
            "",
            (
                "Battle Master and Eldritch Knight define the comparison envelope for each "
                "benchmark result. `IDEAL` means Kinetic Vanguard falls between the two "
                "comparator values, inclusive. `COLD` is below both; `HOT` is above both. "
                "The percentage on COLD and HOT cells shows the signed distance outside the "
                "nearest comparator boundary. `N/A` is reserved for a comparison that cannot "
                "be evaluated. This is a comparator-envelope benchmark, not a universal "
                "real-play balance tolerance, and `IDEAL` is not proof of balance in every game."
            ),
            "",
            (
                "README cells intentionally contain only the public balance result: `IDEAL`, "
                "`COLD (-X%)`, `HOT (+X%)`, or `N/A`. Detailed evidence retains raw Kinetic "
                "Vanguard and comparator aggregates, dynamic boundaries, and the comparator "
                "identity supplying each boundary."
            ),
            "",
        )
    )
    control = "\n".join(
        (
            "### Control Value",
            "",
            (
                "**Primary control-balance metric:** how much useful control the configured "
                "package delivers. Control Value asks: “How much useful control does the "
                "configured package deliver?”"
            ),
            "",
            (
                "Control Value combines delivery probability, persistence or active windows, "
                "established attack/save/reaction opportunities, mechanical consequences, and "
                "legal repeatable accumulating instantaneous effects. `1.0 CU` is denial of "
                "one target's normal Action + Bonus Action for one scored target-turn window. "
                "A Control Unit is a project analytical benchmark unit, **not a D&D rules "
                "quantity**."
            ),
            "",
            (
                "For each target, build, and discipline, the benchmark filters out ineligible "
                "packages and selects the legal package with the highest Control Value. An exact "
                "CU tie is resolved by higher whole-package Control Reliability, then by ascending "
                "stable scenario ID. Control Value reports what that selected package delivers "
                "mechanically; CU is the common package-selection methodology for both readouts."
            ),
            "",
            render_control_table(value_rows, disciplines),
            "",
            "### Control Reliability — delivery diagnostic",
            "",
            (
                "**Secondary diagnostic:** how reliably the Value-selected control package lands "
                "and, where applicable, persists. Control Reliability asks: “How reliably is "
                "that selected package delivered?”"
            ),
            "",
            f"Configured Reliability metric: **{metric}**.",
            "",
            (
                "Control Reliability measures delivery probability for the same CU-selected "
                "package, not effect severity. It "
                "includes legal repeatable attack-delivered opportunities within one ordinary "
                "Attack action when the rules permit them, excludes Action Surge from the "
                "headline control comparison, and applies the maintained repeat-save and "
                "persistence treatment where relevant. A Reliability `HOT` result means "
                "unusually high delivery relative to the Reliability comparator envelope; it "
                "does not by itself mean that the control's mechanical severity is excessive."
            ),
            "",
            render_control_table(reliability_rows, disciplines),
            "",
            "### Control methodology",
            "",
            (
                "Control Value follows a transparent pipeline: canonical condition or outcome "
                "→ mechanical consequences → expected exposure or opportunities → overlap "
                "normalization → weighted Control Units. It prices what an effect mechanically "
                "does rather than assigning value only from its name."
            ),
            "",
            (
                "For example, Stunned decomposes into active-turn denial through Incapacitated, "
                "reaction denial, automatic failure of Strength and Dexterity saves, and "
                "Advantage on incoming attacks. Stunned does **not** gain Speed 0. Restrained "
                "includes complete movement denial plus its separately scored consequences. "
                "Forced movement is valued from expected displaced feet, and repeatable legal "
                "displacement can accrue multiple successful occurrences."
            ),
            "",
            (
                "Value and Reliability can still receive different public bands because they "
                "measure different properties of the same selected package. A consequence-aware "
                "Value readout can differ from delivery: "
                "a soft effect such as Sap can land very reliably without carrying the same "
                "mechanical consequence as Stunned or Restrained. Equal stick probabilities "
                "do not imply equal control power."
            ),
            "",
            (
                "Normalization prevents double counting. Identical boolean consequences do not "
                "stack. Complete turn denial suppresses overlapping lesser action or offensive "
                "effects; automatic save failure supersedes weaker impairment to the same save; "
                "and complete movement denial supersedes overlapping lesser mobility loss. "
                "All-attacks Disadvantage suppresses only an explicitly overlapping next-attack "
                "Disadvantage share. Correlated flat movement reductions are capped at complete "
                "movement denial, while unrelated mechanical consequences remain independently "
                "valued."
            ),
            "",
            (
                "Some mechanics require battlefield or opportunity facts that this benchmark "
                "cannot neutrally establish, such as geometry-dependent restrictions, sight or "
                "sense interactions, cliffs or hazards, unspecified ally opportunities, and "
                "open-ended behavioral effects. They remain visible in detailed diagnostics but "
                "contribute zero CU unless the required context is explicitly established. Zero "
                "Control Value from missing context does **not** mean that a mechanic has no value "
                "in actual play."
            ),
            "",
            (
                "Speed 0 is complete turn movement denial. Flat Speed reductions normalize "
                "against the target's maintained unconditional locomotion Speed; conditional or "
                "choice movement modes are not assumed, and missing trustworthy movement data "
                "fails closed. Forced displacement uses expected feet moved."
            ),
            "",
            (
                "Kinetic Vanguard mechanics come from [`KineticVanguard.yaml`](KineticVanguard.yaml). "
                "Full methodology and reproducibility details are in the "
                "[maintained harness guide](harness/README.md), "
                "[benchmark configuration](harness/config/benchmark.json), "
                "[frozen Control Value configuration](harness/config/control-value.json), "
                "[control primitive catalog](harness/data/control_primitives.json), and "
                "[comparator assumptions](harness/comparators/fighter-subclasses.json)."
            ),
            "",
            (
                "Creature benchmark data is SRD 5.2.1. Maintained comparator mechanics are "
                "independently expressed analytical abstractions under the reviewed comparator "
                "source policy; they are not Kinetic Vanguard rules. "
                + COMPARATOR_NOTICE
                + " See [`LICENSE.md`](LICENSE.md) for component boundaries and "
                "[`NOTICE.md`](NOTICE.md) for attribution and notices."
            ),
            END_MARKER,
        )
    )
    return common + "\n" + damage_section + control


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


def _control_publication_rows(
    root: Path, levels: set[int]
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
    control = run_control(
        DEFAULT_AUTHORITY,
        root,
        levels,
        None,
        write_detail=False,
        write_headline=True,
        profile=DEFAULT_PROFILE,
        write_shadow=True,
    )
    return (
        read_matrix_rows(control["paths"]["csv"]),
        read_matrix_rows(control["value_paths"]["matrix"]),
        read_matrix_rows(control["value_paths"]["selection_audit"]),
    )


def generate_control_publication_rows(
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    with tempfile.TemporaryDirectory(prefix="kv-readme-control-") as directory:
        return _control_publication_rows(Path(directory), levels)


def generate_authoritative_rows(
    workers: int,
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    with tempfile.TemporaryDirectory(prefix="kv-readme-matrices-") as directory:
        root = Path(directory)
        damage = run_damage(
            DEFAULT_AUTHORITY,
            root / "damage",
            levels,
            None,
            False,
            True,
            workers,
        )
        reliability_rows, value_rows, value_audit_rows = _control_publication_rows(
            root / "control", levels
        )
        return (
            read_matrix_rows(damage["paths"]["csv"]),
            reliability_rows,
            value_rows,
            value_audit_rows,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize README balance matrices with the exact analytical harness"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--control-only",
        action="store_true",
        help="refresh control publication while preserving the current damage subsection",
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("--workers must be positive")

    readme = README_PATH.read_text(encoding="utf-8")
    generated_region_span(readme)
    if args.control_only:
        damage_section = extract_damage_section(readme)
        reliability_rows, value_rows, value_audit_rows = (
            generate_control_publication_rows()
        )
        rules_version, profile, _, disciplines = validate_reliability_rows(
            reliability_rows
        )
    else:
        damage_rows, reliability_rows, value_rows, value_audit_rows = (
            generate_authoritative_rows(args.workers)
        )
        rules_version, profile, _, disciplines = validate_authoritative_rows(
            damage_rows, reliability_rows
        )
        damage_section = render_damage_section(damage_rows, disciplines)
    value_public_rows = validate_value_rows(value_rows, value_audit_rows)
    reliability_public_rows = validate_reliability_alignment(
        reliability_rows, value_audit_rows
    )
    region = render_balance_region(
        readme,
        damage_section,
        reliability_public_rows,
        value_public_rows,
        rules_version,
        profile,
        disciplines,
    )
    synchronized = replace_generated_region(readme, region)
    if README_PATH.read_text(encoding="utf-8") != readme:
        raise MatrixSyncError("README changed during analytical evaluation; retry synchronization")

    if args.check:
        if synchronized != readme:
            command = (
                "npm run readme:control"
                if args.control_only
                else "npm run readme:benchmarks"
            )
            raise SystemExit(
                f"README balance benchmark snapshot is stale; run {command}"
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
