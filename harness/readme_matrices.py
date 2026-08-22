# Synchronize the README balance snapshot from fresh authoritative harness matrices.

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .authority import AuthorityModel, DEFAULT_AUTHORITY, PROJECT_ROOT
from .comparison_report import (
    COMPARATOR_NOTICE,
    NOTICE_COLUMNS,
    VALUE_COLUMNS,
    matrix_row,
)
from .control_harness import run as run_control
from .control_value import (
    DEFAULT_PRIMITIVES,
    DEFAULT_SCORING,
    decompose_label,
    load_scoring_config,
)
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
VALUE_SCENARIO_COLUMNS = (
    "Build",
    "Discipline",
    "Level",
    "Target",
    "Scenario",
    "Eligible",
    "Control Value CU",
    "Whole-package control stick %",
    "Value Disposition",
    "Primitive Rows",
    "Candidate Rows",
    "Context/Unsupported Rows",
    "Retained Candidate Rows",
    "Retained Context/Unsupported Rows",
    "Zero Entirely Fail-Closed Context",
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

PRICED = "priced"
PARTIALLY_PRICED = "partially_priced"
UNPRICED = "unpriced"
NO_MODELED_CONTROL = "no_modeled_control"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ControlCatalogForm:
    discipline_id: str
    title: str
    entity_id: str | None
    tier: int | None
    target_role: str
    minimum_level: int
    feature_minimum_level: int
    tier_minimum_level: int
    modeled_control: bool
    scenario_id: str

    @property
    def identity(self) -> tuple[str, str]:
        return self.discipline_id, self.scenario_id

    @property
    def is_mastery(self) -> bool:
        return self.entity_id is None

    def available(self, level: int) -> bool:
        return level >= self.minimum_level


@dataclass(frozen=True)
class ControlCatalogCell:
    state: str
    mean_cu: float | None = None
    mean_delivery: float | None = None
    eligible_targets: int | None = None
    total_targets: int | None = None


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


def build_kv_control_catalog(
    model: AuthorityModel | None = None,
) -> tuple[ControlCatalogForm, ...]:
    """Project every ordinary KV Mastery/rider form from canonical authority."""
    model = model or AuthorityModel.load(DEFAULT_AUTHORITY)
    tier_minimums = {
        int(row["tier"]): int(row["minimum_level"])
        for row in model.projection["progressions"]["tier_minimum_levels"]
    }
    if len(tier_minimums) != len(
        model.projection["progressions"]["tier_minimum_levels"]
    ):
        raise MatrixSyncError("Canonical tier minimum levels contain duplicates")

    forms: list[ControlCatalogForm] = []
    supported_minimum = int(model.projection["supported_level_range"]["minimum"])
    for discipline_id, discipline in model.disciplines.items():
        mastery = discipline["mastery"]
        kind = str(mastery["kind"])
        forms.append(
            ControlCatalogForm(
                discipline_id=discipline_id,
                title="Kinetic Mastery",
                entity_id=None,
                tier=None,
                target_role="primary",
                minimum_level=supported_minimum,
                feature_minimum_level=supported_minimum,
                tier_minimum_level=supported_minimum,
                modeled_control=bool(mastery["control_outcomes"]),
                scenario_id=f"mastery:{kind}",
            )
        )

    for feature in model.features.values():
        if feature.get("advanced_training"):
            continue
        discipline_ids = tuple(str(item) for item in feature["discipline_ids"])
        if len(discipline_ids) != 1 or discipline_ids[0] not in model.disciplines:
            raise MatrixSyncError(
                f"Ordinary discipline feature {feature['entity_id']} has ambiguous membership"
            )
        discipline_id = discipline_ids[0]
        canonical_tiers = tuple(int(row["tier"]) for row in feature["damage_tiers"])
        if canonical_tiers != tuple(sorted(set(canonical_tiers))):
            raise MatrixSyncError(
                f"Canonical tiers for {feature['entity_id']} are duplicated or out of order"
            )
        control_rows = feature.get("control_tiers", [])
        controls = {int(row["tier"]): row for row in control_rows}
        if len(controls) != len(control_rows) or not set(controls).issubset(canonical_tiers):
            raise MatrixSyncError(
                f"Control tiers for {feature['entity_id']} do not map uniquely to canonical tiers"
            )
        feature_minimum = int(feature["minimum_level"])
        for tier in canonical_tiers:
            if tier not in tier_minimums:
                raise MatrixSyncError(
                    f"Canonical tier T{tier} has no Overload minimum level"
                )
            control = controls.get(tier)
            roles = ("primary",)
            if control is not None:
                declared_roles = {
                    str(effect.get("target_role", "all"))
                    for effect in control["effects"]
                }
                if not declared_roles.issubset({"all", "primary", "secondary"}):
                    raise MatrixSyncError(
                        f"Control tier {feature['entity_id']}:T{tier} has an unknown target role"
                    )
                if declared_roles & {"primary", "secondary"}:
                    roles = ("primary", "secondary")
            for role in roles:
                suffix = f":{role}" if role != "primary" else ""
                forms.append(
                    ControlCatalogForm(
                        discipline_id=discipline_id,
                        title=str(feature["title"]),
                        entity_id=str(feature["entity_id"]),
                        tier=tier,
                        target_role=role,
                        minimum_level=max(feature_minimum, tier_minimums[tier]),
                        feature_minimum_level=feature_minimum,
                        tier_minimum_level=tier_minimums[tier],
                        modeled_control=control is not None,
                        scenario_id=f"{feature['entity_id']}:T{tier}{suffix}",
                    )
                )

    identities = [form.identity for form in forms]
    if len(identities) != len(set(identities)):
        raise MatrixSyncError("Canonical KV control catalog contains duplicate exact forms")
    discipline_order = {value: index for index, value in enumerate(model.disciplines)}
    feature_order = {
        entity_id: index for index, entity_id in enumerate(model.features)
    }
    return tuple(
        sorted(
            forms,
            key=lambda form: (
                discipline_order[form.discipline_id],
                -1 if form.is_mastery else feature_order[form.entity_id or ""],
                -1 if form.tier is None else form.tier,
                0 if form.target_role == "primary" else 1,
            ),
        )
    )


def catalog_rider_scenarios(
    catalog: Sequence[ControlCatalogForm],
) -> tuple[dict[str, object], ...]:
    """Return every rider form whose own authority declares modeled control."""
    return tuple(
        {
            "discipline_id": form.discipline_id,
            "entity_id": form.entity_id,
            "tier": form.tier,
            "target_role": form.target_role,
        }
        for form in catalog
        if form.modeled_control and not form.is_mastery
    )


def classify_catalog_pricing(
    retained_candidates: int, retained_context_or_unsupported: int
) -> str:
    if retained_candidates < 0 or retained_context_or_unsupported < 0:
        raise MatrixSyncError("Control pricing row counts cannot be negative")
    if retained_candidates and retained_context_or_unsupported:
        return PARTIALLY_PRICED
    if retained_candidates:
        return PRICED
    if retained_context_or_unsupported:
        return UNPRICED
    raise MatrixSyncError("Control-bearing form has no retained meaningful consequence")


def validate_control_catalog_scenarios(
    scenario_rows: Sequence[MatrixRow],
    catalog: Sequence[ControlCatalogForm],
    levels: Sequence[int],
) -> dict[tuple[str, str, int], ControlCatalogCell]:
    """Validate exact scenario evidence and aggregate complete-roster catalog cells."""
    _require_fields(scenario_rows, VALUE_SCENARIO_COLUMNS, "Control Value scenario detail")
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
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
    canonical = {form.identity: form for form in catalog}
    parsed: dict[tuple[str, str, str, str], dict[str, object]] = {}
    allowed_dispositions = {
        "ineligible",
        "priced_nonzero",
        "legitimately_priced_zero",
        "entirely_context_required_or_unsupported",
    }
    for index, row in enumerate(scenario_rows):
        _validate_value_source(
            row, index, "Control Value scenario detail", expected_source
        )
        if row["Build"] != "kinetic_vanguard":
            continue
        form = canonical.get((row["Discipline"], row["Scenario"]))
        if form is None:
            raise MatrixSyncError(
                "Control Value scenario detail has unknown exact KV scenario "
                f"{(row['Discipline'], row['Scenario'])}"
            )
        identity = (row["Level"], row["Target"], *form.identity)
        if identity in parsed:
            raise MatrixSyncError(
                f"Control Value scenario detail duplicates exact scenario identity {identity}"
            )
        try:
            level = int(row["Level"])
            cu = float(row["Control Value CU"])
            delivery = float(row["Whole-package control stick %"])
            primitive_rows = int(row["Primitive Rows"])
            candidate_rows = int(row["Candidate Rows"])
            context_rows = int(row["Context/Unsupported Rows"])
            retained_candidates = int(row["Retained Candidate Rows"])
            retained_context = int(row["Retained Context/Unsupported Rows"])
        except (TypeError, ValueError) as error:
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} has non-numeric evidence"
            ) from error
        if (
            level not in levels
            or not math.isfinite(cu)
            or cu < 0
            or not math.isfinite(delivery)
            or not 0 <= delivery <= 100
            or min(
                primitive_rows,
                candidate_rows,
                context_rows,
                retained_candidates,
                retained_context,
            )
            < 0
            or primitive_rows != candidate_rows + context_rows
            or retained_candidates > candidate_rows
            or retained_context > context_rows
        ):
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} has invalid evidence"
            )
        if row["Eligible"] not in {"True", "False"}:
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} has invalid eligibility"
            )
        eligible = row["Eligible"] == "True"
        if row["Value Disposition"] not in allowed_dispositions:
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} has invalid disposition"
            )
        if not eligible and (cu != 0.0 or delivery != 0.0):
            raise MatrixSyncError(
                f"Ineligible exact scenario {identity} must contribute zero"
            )
        parsed[identity] = {
            "cu": cu,
            "delivery": delivery,
            "eligible": eligible,
            "retained_candidates": retained_candidates,
            "retained_context": retained_context,
        }

    targets = load_targets(profile=DEFAULT_PROFILE, levels=set(levels))
    targets_by_level = {
        level: tuple(target for target in targets if target.level == level)
        for level in levels
    }
    expected = {
        (str(level), target.name, *form.identity)
        for form in catalog
        if form.is_mastery or form.modeled_control
        for level in levels
        if form.available(level)
        for target in targets_by_level[level]
    }
    _key_difference(set(parsed), expected, "Control Value exact scenario detail")

    cells: dict[tuple[str, str, int], ControlCatalogCell] = {}
    for form in catalog:
        for level in levels:
            key = (*form.identity, level)
            if not form.available(level):
                cells[key] = ControlCatalogCell(UNAVAILABLE)
                continue
            if not form.modeled_control:
                cells[key] = ControlCatalogCell(NO_MODELED_CONTROL, mean_cu=0.0)
                continue
            rows = [
                parsed[(str(level), target.name, *form.identity)]
                for target in targets_by_level[level]
            ]
            total = len(rows)
            if total != PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][level]:
                raise MatrixSyncError(
                    f"Exact scenario {form.identity} has an incomplete level-{level} roster"
                )
            eligible = sum(bool(row["eligible"]) for row in rows)
            state = classify_catalog_pricing(
                sum(int(row["retained_candidates"]) for row in rows),
                sum(int(row["retained_context"]) for row in rows),
            )
            cells[key] = ControlCatalogCell(
                state=state,
                mean_cu=sum(float(row["cu"]) for row in rows) / total,
                mean_delivery=sum(float(row["delivery"]) for row in rows) / total,
                eligible_targets=eligible,
                total_targets=total,
            )
    return cells


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


def _raw_kv_table(
    rows: Sequence[MatrixRow],
    disciplines: Sequence[str],
    *,
    decimals: int,
    suffix: str,
) -> str:
    grouped: dict[tuple[str, str], MatrixRow] = {}
    for row in rows:
        key = (row["Level"], row["Discipline"])
        if key in grouped:
            raise MatrixSyncError(f"README raw KV table has duplicate row {key}")
        grouped[key] = row
    levels = tuple(int(value) for value in load_config()["methodology"]["levels"])
    expected = {
        (str(level), discipline) for level in levels for discipline in disciplines
    }
    _key_difference(set(grouped), expected, "README raw KV table")
    table_rows: list[list[str]] = []
    for level in levels:
        rendered = [str(level)]
        for discipline in disciplines:
            try:
                value = float(grouped[(str(level), discipline)]["KV"])
            except (KeyError, ValueError) as error:
                raise MatrixSyncError(
                    f"README raw KV table has non-numeric KV for {(level, discipline)}"
                ) from error
            if not math.isfinite(value):
                raise MatrixSyncError(
                    f"README raw KV table has non-finite KV for {(level, discipline)}"
                )
            rendered.append(f"{value:.{decimals}f}{suffix}")
        table_rows.append(rendered)
    headers = (
        "Level",
        *(discipline.replace("_", " ").title() for discipline in disciplines),
    )
    return _markdown_table(headers, table_rows)


def render_raw_kv_value_table(
    value_rows: Sequence[MatrixRow],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    """Render raw KV CU from validated public Value rows."""
    return _raw_kv_table(value_rows, disciplines, decimals=3, suffix=" CU")


def render_raw_kv_reliability_table(
    reliability_rows: Sequence[MatrixRow],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    """Render raw KV stick probability from CU-winner-aligned Reliability rows."""
    return _raw_kv_table(reliability_rows, disciplines, decimals=2, suffix="%")


def _render_catalog_cell(cell: ControlCatalogCell) -> str:
    if cell.state == UNAVAILABLE:
        return "N/A"
    if cell.state == NO_MODELED_CONTROL:
        return "0.000 CU · — · no modeled control"
    if (
        cell.mean_cu is None
        or cell.mean_delivery is None
        or cell.eligible_targets is None
        or cell.total_targets is None
        or not math.isfinite(cell.mean_cu)
        or not math.isfinite(cell.mean_delivery)
        or not 0 <= cell.eligible_targets <= cell.total_targets
    ):
        raise MatrixSyncError("Control catalog cell is missing aggregate evidence")
    coverage = f"{cell.eligible_targets}/{cell.total_targets}"
    if cell.state == PRICED:
        return f"{cell.mean_cu:.3f} CU · {cell.mean_delivery:.2f}% · {coverage}"
    if cell.state == PARTIALLY_PRICED:
        return (
            f"{cell.mean_cu:.3f} CU (partial) · "
            f"{cell.mean_delivery:.2f}% · {coverage}"
        )
    if cell.state == UNPRICED:
        return f"Unpriced · {cell.mean_delivery:.2f}% delivery · {coverage}"
    raise MatrixSyncError(f"Unknown control catalog pricing state: {cell.state}")


def render_kv_control_catalog(
    catalog: Sequence[ControlCatalogForm],
    cells: Mapping[tuple[str, str, int], ControlCatalogCell],
    levels: Sequence[int],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    expected_keys = {
        (*form.identity, int(level)) for form in catalog for level in levels
    }
    _key_difference(set(cells), expected_keys, "README KV control catalog")
    if {form.discipline_id for form in catalog} != set(disciplines):
        raise MatrixSyncError("KV control catalog disciplines differ from README columns")
    variant_counts: dict[tuple[str, str | None, int | None], int] = {}
    for form in catalog:
        key = (form.discipline_id, form.entity_id, form.tier)
        variant_counts[key] = variant_counts.get(key, 0) + 1

    sections = [
        "### Kinetic Vanguard control catalog",
        "",
        (
            "This authority-driven catalog is a decomposition view: Kinetic Mastery and every "
            "exact rider tier are separate control sources. Each Kinetic Mastery row reports "
            "only that Mastery's control; each rider/tier/role row reports only control produced "
            "by that exact rider form. Mastery that may legally coexist during actual play is "
            "excluded from rider CU and delivery. The headline discipline benchmark above "
            "remains a separate whole-legal-package view."
        ),
        "",
        (
            "Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20. Each "
            "column uses the complete maintained roster for that level."
        ),
        "",
        "**Cell format:** `CU · delivery · eligible/roster`",
        "",
        (
            "Example: `0.143 CU · 95.00% · 12/12` means `0.143 CU` average Control "
            "Value and `95.00%` average initial control-delivery probability across the full "
            "benchmark roster at that fighter level; `12/12` means all 12 targets satisfy the "
            "exact form's structural target restrictions. The ratio is **eligible targets / "
            "roster targets**."
        ),
        "",
        (
            "If a cell says `9/12`, only 9 of 12 targets satisfy the exact form's structural "
            "target restrictions. The other 3 are not removed: they remain in the roster "
            "denominator and contribute `0 CU` and `0% delivery`. `eligible/roster` reports "
            "structural target eligibility—currently maintained maximum-size and required-"
            "creature-type restrictions—not universal susceptibility. Condition immunity or "
            "other effect-level ineffectiveness can reduce a target's CU or delivery while that "
            "target remains structurally eligible in the ratio. Eligibility is not a save "
            "result, hit count, successful application count, or probability."
        ),
        "",
        (
            "`Partial` means retained priced and retained context-required or unsupported "
            "consequences coexist; suppressed duplicate or weaker primitives do not create that "
            "label. `Unpriced` retains measurable delivery and eligibility without reporting zero "
            "CU. `No modeled control` means `0.000 CU` and no control delivery (`—`). `N/A` means "
            "the exact form is unavailable at that level."
        ),
        "",
        (
            "Full denominator and state methodology: "
            "[Benchmark roster, eligibility, and coverage]"
            "(#benchmark-roster-eligibility-and-coverage)"
        ),
    ]
    labels = {
        "cryokinesis": "Cryokinesis",
        "pyrokinesis": "Pyrokinesis",
        "psychokinesis": "Psychokinesis",
        "electrokinesis": "Electrokinesis",
    }
    for discipline_id in disciplines:
        rows: list[list[str]] = []
        for form in catalog:
            if form.discipline_id != discipline_id:
                continue
            if form.is_mastery:
                label = form.title
            else:
                label = f"{form.title} — T{form.tier}"
                if variant_counts[(form.discipline_id, form.entity_id, form.tier)] > 1:
                    label += f" — {form.target_role}"
            rows.append(
                [
                    label,
                    *[
                        _render_catalog_cell(cells[(*form.identity, int(level))])
                        for level in levels
                    ],
                ]
            )
        sections.extend(
            (
                "",
                f"#### {labels[discipline_id]}",
                "",
                _markdown_table(
                    ("Rider / form", *(f"Fighter {level}" for level in levels)), rows
                ),
            )
        )
    return "\n".join(sections)


def render_benchmark_roster_methodology() -> str:
    """Render the maintained full-roster aggregation and catalog state contract."""
    return "\n".join(
        (
            "### Benchmark roster, eligibility, and coverage",
            "",
            (
                "Every Fighter level uses the complete maintained headline roster for that "
                "level. `eligible/roster` means **structurally eligible targets / total "
                "maintained benchmark targets**. Structural eligibility currently comes from "
                "`target_is_eligible()`: the exact form's maintained maximum-size and required-"
                "creature-type restrictions."
            ),
            "",
            (
                "`12/12` means all 12 roster targets satisfy those structural restrictions. "
                "`9/12` means 9 of 12 satisfy them. Eligibility is not a success roll, delivery "
                "probability, or guarantee of susceptibility. In particular, `12/12` does not "
                "mean 12 successful saves, 12 successful attacks, 100% delivery, 12 successful "
                "applications, or universal susceptibility to every control consequence."
            ),
            "",
            (
                "An ineligible target remains in the aggregate denominator. For a priced or "
                "partially priced form, that target contributes `CU = 0` and `delivery = 0%`."
            ),
            "",
            "`mean CU = sum(per-target CU across the complete roster) / total roster targets`",
            "",
            (
                "`mean delivery = sum(per-target initial-delivery probability across the "
                "complete roster) / total roster targets`"
            ),
            "",
            (
                "Do not divide only by eligible targets. Eligible-only averaging would hide "
                "practical restrictions and could make a narrowly applicable control look "
                "stronger or more reliable than it is across the maintained benchmark roster."
            ),
            "",
            (
                "Condition immunity and other effect-level ineffectiveness are resolved "
                "separately when effective control components are filtered; they are not "
                "automatically coverage exclusions. A structurally eligible but immune target "
                "can remain in the coverage numerator while contributing `0 CU` or `0% "
                "delivery` for the ineffective consequence."
            ),
            "",
            (
                "**Instructional example (not a published scenario):** if a form has 80% "
                "delivery against 9 structurally eligible targets and 3 targets are structurally "
                "ineligible, its full-roster delivery mean is `(9 × 0.80 + 3 × 0) / 12 = 0.60 "
                "= 60%`. The eligible-only 80% is not the roster-wide result."
            ),
            "",
            (
                "`Priced` and `Partial` use the complete-roster denominator above. `Unpriced` "
                "can still show coverage and independently measurable delivery, but its CU "
                "field remains `Unpriced`, not zero. `No modeled control` is `0.000 CU` because "
                "that catalog source declares no modeled control, with delivery `—` because no "
                "control establishment is measured. `N/A` means the exact form is unavailable "
                "at that Fighter level and does not participate in that level's aggregate."
            ),
        )
    )


def _scoring_rule(
    scoring: dict[str, object], primitive_id: str, transform: str
) -> tuple[str, float]:
    rules = scoring["rules"]
    if not isinstance(rules, dict) or primitive_id not in rules:
        raise MatrixSyncError(
            f"README Control Value explanation has no scoring rule for {primitive_id}"
        )
    rule = rules[primitive_id]
    if not isinstance(rule, dict) or rule.get("transform") != transform:
        raise MatrixSyncError(
            f"README Control Value explanation has stale transform for {primitive_id}"
        )
    weight = rule.get("nominal_weight")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise MatrixSyncError(
            f"README Control Value explanation has invalid weight for {primitive_id}"
        )
    return transform, float(weight)


def render_control_value_explanation() -> str:
    """Render reader-facing CU arithmetic from the maintained scoring contracts."""
    scoring = load_scoring_config()
    definition = scoring["control_unit"]
    if not isinstance(definition, str):
        raise MatrixSyncError("README Control Unit definition is not text")

    sap_specs = decompose_label("attack_disadvantage", attack_scope="next_attack")
    if (
        len(sap_specs) != 1
        or sap_specs[0].primitive_id != "offensive_impairment_next_attack"
        or sap_specs[0].pricing_status != "candidate"
    ):
        raise MatrixSyncError("README Sap example no longer matches the primitive catalog")
    _, sap_weight = _scoring_rule(
        scoring, sap_specs[0].primitive_id, "linear_expected_exposure"
    )
    sap_exposure = 0.95
    sap_total = sap_weight * sap_exposure

    stunned_specs = tuple(
        spec for spec in decompose_label("stunned") if spec.pricing_status == "candidate"
    )
    expected_stunned = (
        (
            "active_turn_denial",
            (("denied_turn_options", "action_and_bonus_action"),),
        ),
        ("reaction_denial", ()),
        ("save_auto_failure", (("save_ability", "strength"),)),
        ("save_auto_failure", (("save_ability", "dexterity"),)),
        ("defensive_attack_advantage", ()),
    )
    actual_stunned = tuple(
        (spec.primitive_id, spec.qualifiers) for spec in stunned_specs
    )
    if actual_stunned != expected_stunned:
        raise MatrixSyncError(
            "README Stunned example no longer matches the priced candidate catalog"
        )
    stunned_labels = (
        "active-turn denial",
        "reaction denial",
        "Strength save automatic failure",
        "Dexterity save automatic failure",
        "incoming attack Advantage",
    )
    stunned_rows: list[tuple[str, str, str]] = []
    stunned_total = 0.0
    for label, spec in zip(stunned_labels, stunned_specs, strict=True):
        _, weight = _scoring_rule(
            scoring, spec.primitive_id, "linear_expected_exposure"
        )
        stunned_total += weight
        stunned_rows.append((label, f"{weight:.2f} × 1.00", f"{weight:.2f} CU"))

    _scoring_rule(
        scoring, "mobility_loss_feet", "bounded_fraction_of_benchmark_locomotion"
    )
    _scoring_rule(scoring, "speed_multiplier", "remaining_speed_fraction")
    _, displacement_weight = _scoring_rule(
        scoring, "forced_displacement", "expected_displaced_feet"
    )
    _scoring_rule(
        scoring, "flat_armor_class_penalty", "points_times_placed_opportunities"
    )
    _scoring_rule(
        scoring, "flat_save_roll_penalty", "points_times_placed_opportunities"
    )

    stunned_table = _markdown_table(
        ("Priced piece", "Arithmetic", "Contribution"),
        (*stunned_rows, ("**Total**", "", f"**{stunned_total:.2f} CU**")),
    )
    return "\n".join(
        (
            "### How Control Value is calculated",
            "",
            definition,
            "",
            (
                "The calculation pipeline is: condition/outcome → mechanical primitives → "
                "expected delivery/persistence/opportunities → overlap normalization → "
                "primitive CU contributions → total Control Value."
            ),
            "",
            "General arithmetic: `primitive contribution = frozen weight × expected exposure`.",
            "",
            (
                "Expected exposure is where delivery probability, persistence, placed attack, "
                "save, and reaction opportunities, and repeatable instantaneous occurrences "
                "enter the calculation. Overlap normalization then prevents the same mechanical "
                "consequence from being counted twice."
            ),
            "",
            (
                "Special transforms keep their maintained meanings. A flat Speed reduction is "
                "normalized against the target's benchmark locomotion Speed and capped at "
                "complete movement denial; a Speed multiplier prices the lost fraction of Speed. "
                f"Forced movement contributes {displacement_weight:.2f} CU × expected displaced "
                "feet. Flat Armor Class and save penalties price penalty points multiplied by "
                "established attack or save opportunities. `context_required` and `unsupported` "
                "primitives remain visible but contribute 0 CU when the benchmark cannot establish "
                "the needed battlefield fact."
            ),
            "",
            "#### Worked example: Sap-style next-attack Disadvantage",
            "",
            (
                "The maintained next-attack Disadvantage outcome resolves to "
                f"`{sap_specs[0].primitive_id}`, weighted at {sap_weight:.2f} CU per expected "
                "placed attack opportunity."
            ),
            "",
            f"Illustrative arithmetic: `{sap_weight:.2f} × {sap_exposure:.2f} = {sap_total:.4f} CU`.",
            "",
            (
                "The 95% expected exposure is an instructional example, not a published target "
                "or roster result. Even at very high delivery, the effect remains low-Control-Value "
                "because it impairs only one attack. Repeated legal attack attempts can make this "
                "kind of rider highly reliable without making its consequence more severe; Sap is "
                "not assumed to be the selected package in every Electrokinesis matrix cell."
            ),
            "",
            "#### Worked example: Stunned",
            "",
            (
                "For one synthetic, fully active scored window, the maintained condition catalog "
                "and frozen scoring config produce these candidate priced pieces:"
            ),
            "",
            stunned_table,
            "",
            (
                "Incapacitated supplies the active-turn and reaction pieces; Stunned adds the two "
                "save automatic failures and incoming attack Advantage. Stunned does **not** gain "
                "Speed 0. Concentration, speech, fall, and other context-sensitive consequences "
                "remain diagnostic rather than receiving invented headline CU. This synthetic "
                "one-window decomposition teaches the weighting model; it does not claim that "
                f"every real Stunned benchmark row equals {stunned_total:.2f} CU."
            ),
        )
    )


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
    catalog: Sequence[ControlCatalogForm],
    catalog_cells: Mapping[tuple[str, str, int], ControlCatalogCell],
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
                "**Primary control-balance metric:** how much mechanically useful control the "
                "selected package delivers. A Control Unit is a project analytical benchmark "
                "unit, **not a D&D rules quantity**."
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
            (
                "The band table compares Kinetic Vanguard against the Battle Master / Eldritch "
                "Knight Control Value envelope."
            ),
            "",
            render_control_table(value_rows, disciplines),
            "",
            "### Kinetic Vanguard mean Control Value",
            "",
            (
                "This companion table shows the raw Kinetic Vanguard equal-weight roster mean for "
                "the same CU-selected packages represented by the band table."
            ),
            "",
            render_raw_kv_value_table(value_rows, disciplines),
            "",
            render_kv_control_catalog(
                catalog,
                catalog_cells,
                tuple(int(value) for value in load_config()["methodology"]["levels"]),
                disciplines,
            ),
            "",
            render_benchmark_roster_methodology(),
            "",
            render_control_value_explanation(),
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
                "persistence treatment where relevant."
            ),
            "",
            (
                "A cell such as `HOT (+46.97%)` does **not** mean a 46.97% chance to apply "
                "control. The percentage is the signed distance outside the nearest Battle "
                "Master / Eldritch Knight Reliability comparator boundary. `IDEAL` means the "
                "raw value falls within that comparator envelope. `COLD` and `HOT` describe "
                "relative comparator position, not an absolute real-play balance verdict."
            ),
            "",
            render_control_table(reliability_rows, disciplines),
            "",
            "### Kinetic Vanguard mean Reliability",
            "",
            (
                "This companion table shows the raw Kinetic Vanguard whole-package stick "
                "probability reconstructed from the same common CU-selected winner audit. The "
                "band percentage above is comparator distance, not this raw application "
                "probability."
            ),
            "",
            render_raw_kv_reliability_table(reliability_rows, disciplines),
            "",
            "### Why Control Value and Reliability can disagree",
            "",
            (
                "Control Value asks: “How much mechanically useful control does the selected "
                "package deliver?” Reliability asks: “How often does that same selected package "
                "land and persist?” Both readouts use the same CU-selected package."
            ),
            "",
            (
                "Sap can be very reliable because legal repeated attack opportunities can give "
                "a next-attack Disadvantage rider multiple chances to land. Its priced consequence "
                "is still only one impaired attack, so its Control Value remains small. "
                "Restrained- and Stunned-style control affects much more of a target's turn, "
                "movement, attacks, defenses, saves, or reactions, so one successful application "
                "can carry substantially more Control Value even when it is less reliable."
            ),
            "",
            (
                "**High Reliability + low Value** means soft control that lands consistently. "
                "**Lower Reliability + high Value** means harder control that is less dependable "
                "but more consequential when it lands. High Reliability alone is not evidence "
                "that a feature is too strong, and low Value alone is not evidence that delivery "
                "is poor."
            ),
            "",
            "### Control methodology",
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
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
    catalog = build_kv_control_catalog()
    publication_scenarios = catalog_rider_scenarios(catalog)
    control = run_control(
        DEFAULT_AUTHORITY,
        root,
        levels,
        None,
        write_detail=False,
        write_headline=True,
        profile=DEFAULT_PROFILE,
        write_shadow=True,
        publication_scenarios=publication_scenarios,
    )
    return (
        read_matrix_rows(control["paths"]["csv"]),
        read_matrix_rows(control["value_paths"]["matrix"]),
        read_matrix_rows(control["value_paths"]["selection_audit"]),
        read_matrix_rows(control["value_paths"]["catalog_scenario_detail"]),
    )


def generate_control_publication_rows(
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
    config = load_config()
    levels = {int(value) for value in config["methodology"]["levels"]}
    with tempfile.TemporaryDirectory(prefix="kv-readme-control-") as directory:
        return _control_publication_rows(Path(directory), levels)


def generate_authoritative_rows(
    workers: int,
) -> tuple[
    list[MatrixRow],
    list[MatrixRow],
    list[MatrixRow],
    list[MatrixRow],
    list[MatrixRow],
]:
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
        (
            reliability_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
        ) = _control_publication_rows(root / "control", levels)
        return (
            read_matrix_rows(damage["paths"]["csv"]),
            reliability_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
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
        reliability_rows, value_rows, value_audit_rows, value_scenario_rows = (
            generate_control_publication_rows()
        )
        rules_version, profile, _, disciplines = validate_reliability_rows(
            reliability_rows
        )
    else:
        (
            damage_rows,
            reliability_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
        ) = (
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
    catalog = build_kv_control_catalog()
    catalog_cells = validate_control_catalog_scenarios(
        value_scenario_rows,
        catalog,
        tuple(int(value) for value in load_config()["methodology"]["levels"]),
    )
    region = render_balance_region(
        readme,
        damage_section,
        reliability_public_rows,
        value_public_rows,
        catalog,
        catalog_cells,
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
