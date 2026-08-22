# Synchronize the README balance snapshot from fresh authoritative harness matrices.

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import stat
import tempfile
from collections import Counter
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
from .control_harness import (
    BATTLE_MASTER_REFERENCE_SCENARIOS,
    DELIVERY_RECIPE_IDS,
    ELDRITCH_KNIGHT_REFERENCE_FAMILIES,
    EFFECTIVE,
    EFFECTIVENESS_NOT_APPLICABLE,
    INEFFECTIVE_NULLIFIED,
    INEFFECTIVE_STRUCTURAL,
    PARTIALLY_EFFECTIVE,
    _attack_action_retry_probability,
    _kv_retry_resources,
    run as run_control,
)
from .control_value import (
    DEFAULT_PRIMITIVES,
    DEFAULT_SCORING,
    decompose_label,
    load_primitive_catalog,
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
CONTROL_DETAIL_PATH = PROJECT_ROOT / "CONTROL_BENCHMARK_DETAIL.md"
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
CATALOG_EFFECTIVENESS_COLUMNS = (
    "Effectiveness Status",
    "Effective",
    "Declared Consequences",
    "Surviving Consequences",
    "Effectiveness Reasons",
)
CATALOG_DELIVERY_RECIPE_COLUMNS = (
    "Delivery Recipe ID",
    "Delivery Gate",
    "Retry Model",
    "Resolved Save Ability",
    "Additional Control Gate",
)
CATALOG_SCENARIO_COLUMNS = (
    *VALUE_SCENARIO_COLUMNS,
    *CATALOG_EFFECTIVENESS_COLUMNS,
    *CATALOG_DELIVERY_RECIPE_COLUMNS,
)
COMPARATOR_REFERENCE_COLUMNS = (
    "Build",
    "Family ID",
    "Display Name",
    "Spell ID",
    "Level",
    "Target",
    "Scenario",
    "Family Available At Level",
    "Eligible",
    "Control Value CU",
    "Whole-package control stick %",
    "Effective",
    "Effectiveness Status",
    "Declared Consequences",
    "Surviving Consequences",
    "Effectiveness Reasons",
    "Value Disposition",
    "Primitive Rows",
    "Candidate Rows",
    "Context/Unsupported Rows",
    "Retained Candidate Rows",
    "Retained Context/Unsupported Rows",
    "Zero Entirely Fail-Closed Context",
    "Family Candidate Scenarios",
    "Save Primers",
    "Primer Timing",
    "Selection Basis",
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
class ControlCoverageException:
    target: str
    status: str
    reasons: tuple[str, ...]
    surviving_consequences: tuple[str, ...]


@dataclass(frozen=True)
class ControlDeliveryRecipe:
    recipe_id: str
    gate: str
    retry_model: str
    save_ability: str
    additional_control_gate: str = ""


@dataclass(frozen=True)
class ControlCatalogCell:
    state: str
    mean_cu: float | None = None
    mean_delivery: float | None = None
    effective_targets: int | None = None
    total_targets: int | None = None
    exceptions: tuple[ControlCoverageException, ...] = ()
    delivery_recipe: ControlDeliveryRecipe | None = None


@dataclass(frozen=True)
class ComparatorReferenceCell:
    available: bool
    mean_cu: float | None = None
    mean_delivery: float | None = None
    effective_targets: int | None = None
    total_targets: int | None = None
    selections: tuple[tuple[str, str], ...] = ()


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


def atomic_create_text(path: Path, replacement: str) -> None:
    """Create a generated file without overwriting a concurrently created path."""
    if path.exists():
        raise MatrixSyncError(f"Refusing to overwrite concurrently created file: {path}")
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
        temporary_path.chmod(0o644)
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise MatrixSyncError(
                f"Refusing to overwrite concurrently created file: {path}"
            ) from error
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


def _catalog_tokens(value: str, pattern: str, label: str, index: int) -> tuple[str, ...]:
    if value == "":
        return ()
    tokens = tuple(value.split(";"))
    if any(not re.fullmatch(pattern, token) for token in tokens):
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has unknown {label}"
        )
    return tokens


def _validate_effectiveness_evidence(
    row: MatrixRow,
    index: int,
    form: ControlCatalogForm,
    eligible: bool,
    cu: float,
    delivery: float,
) -> dict[str, object]:
    status = row["Effectiveness Status"]
    effective_text = row["Effective"]
    if effective_text not in {"True", "False"}:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has invalid effectiveness"
        )
    effective = effective_text == "True"
    declared = _catalog_tokens(
        row["Declared Consequences"], r"(?:condition|outcome):[a-z0-9_]+", "consequence token", index
    )
    surviving = _catalog_tokens(
        row["Surviving Consequences"], r"(?:condition|outcome):[a-z0-9_]+", "consequence token", index
    )
    reasons = _catalog_tokens(
        row["Effectiveness Reasons"],
        r"(?:exceeds_maximum_size|requires_creature_type|immune_condition|dependency_condition_immune):[a-z0-9_]+",
        "effectiveness reason",
        index,
    )
    declared_counts = Counter(declared)
    surviving_counts = Counter(surviving)
    if surviving_counts - declared_counts:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has undeclared surviving control"
        )
    structural_reasons = tuple(
        reason for reason in reasons if reason.startswith(("exceeds_maximum_size:", "requires_creature_type:"))
    )
    effect_reasons = tuple(
        reason for reason in reasons if reason.startswith(("immune_condition:", "dependency_condition_immune:"))
    )
    if status == EFFECTIVENESS_NOT_APPLICABLE:
        valid = not form.modeled_control and not effective and not declared and not surviving and not reasons
    elif status == EFFECTIVE:
        valid = form.modeled_control and eligible and effective and bool(declared) and declared_counts == surviving_counts and not reasons
    elif status == PARTIALLY_EFFECTIVE:
        valid = form.modeled_control and eligible and effective and bool(surviving) and surviving_counts != declared_counts and bool(effect_reasons) and not structural_reasons
    elif status == INEFFECTIVE_STRUCTURAL:
        valid = form.modeled_control and not eligible and not effective and bool(declared) and not surviving and bool(structural_reasons) and not effect_reasons
    elif status == INEFFECTIVE_NULLIFIED:
        valid = form.modeled_control and eligible and not effective and bool(declared) and not surviving and bool(effect_reasons) and not structural_reasons
    else:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has unknown effectiveness status"
        )
    if not valid:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has inconsistent effectiveness evidence"
        )
    if not effective and form.modeled_control and (cu != 0.0 or delivery != 0.0):
        raise MatrixSyncError(
            f"Ineffective exact scenario {(row['Level'], row['Target'], *form.identity)} must contribute zero"
        )
    return {
        "status": status,
        "effective": effective,
        "declared": declared,
        "surviving": surviving,
        "reasons": reasons,
    }


def _validate_delivery_recipe_evidence(
    row: MatrixRow, index: int, form: ControlCatalogForm
) -> ControlDeliveryRecipe:
    recipe_id = row["Delivery Recipe ID"]
    gate = row["Delivery Gate"]
    retry_model = row["Retry Model"]
    save_ability = row["Resolved Save Ability"]
    additional_control_gate = row["Additional Control Gate"]
    if recipe_id not in DELIVERY_RECIPE_IDS:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has unknown delivery recipe ID"
        )
    contracts = {
        "mastery_attack_action_hit_retry": (
            "hit",
            "ordinary_attack_action_independent_hits",
            False,
        ),
        "no_modeled_control": ("none", "none", False),
        "single_activation_automatic": ("automatic", "single_activation", False),
        "single_activation_failed_save": ("failed_save", "single_activation", True),
        "single_activation_hit": ("hit", "single_activation", False),
        "single_activation_hit_failed_save": (
            "hit_and_failed_save",
            "single_activation",
            True,
        ),
        "kv_attack_action_hit_retry": (
            "hit",
            "kv_attack_action_state_recursion",
            False,
        ),
        "kv_attack_action_hit_failed_save_retry": (
            "hit_and_failed_save",
            "kv_attack_action_state_recursion",
            True,
        ),
    }
    expected_gate, expected_retry, requires_save = contracts[recipe_id]
    if gate != expected_gate or retry_model != expected_retry:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has inconsistent delivery recipe evidence"
        )
    if additional_control_gate not in {"","failed_save"}:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} has unknown additional-control gate"
        )
    if additional_control_gate:
        if requires_save or gate not in {"hit","automatic"}:
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} has inconsistent mixed-gate evidence"
            )
        if not re.fullmatch(r"[a-z]+",save_ability):
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} lacks an additional-control save ability"
            )
    elif requires_save:
        if not re.fullmatch(r"[a-z]+", save_ability):
            raise MatrixSyncError(
                f"Control Value scenario detail row {index} lacks a resolved save ability"
            )
    elif save_ability:
        raise MatrixSyncError(
            f"Control Value scenario detail row {index} invents a save for its delivery recipe"
        )
    if form.is_mastery and recipe_id not in {
        "mastery_attack_action_hit_retry",
        "no_modeled_control",
    }:
        raise MatrixSyncError("Kinetic Mastery has rider delivery recipe evidence")
    if not form.is_mastery and recipe_id == "mastery_attack_action_hit_retry":
        raise MatrixSyncError("Rider delivery recipe inherited Kinetic Mastery")
    if form.modeled_control == (recipe_id == "no_modeled_control"):
        raise MatrixSyncError("Delivery recipe disagrees with modeled-control authority")
    return ControlDeliveryRecipe(
        recipe_id, gate, retry_model, save_ability, additional_control_gate
    )


def validate_control_catalog_scenarios(
    scenario_rows: Sequence[MatrixRow],
    catalog: Sequence[ControlCatalogForm],
    levels: Sequence[int],
) -> dict[tuple[str, str, int], ControlCatalogCell]:
    """Validate exact scenario evidence and aggregate complete-roster catalog cells."""
    _require_fields(scenario_rows, CATALOG_SCENARIO_COLUMNS, "Control Value scenario detail")
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
        effectiveness = _validate_effectiveness_evidence(
            row, index, form, eligible, cu, delivery
        )
        recipe = _validate_delivery_recipe_evidence(row, index, form)
        parsed[identity] = {
            "target": row["Target"],
            "cu": cu,
            "delivery": delivery,
            "eligible": eligible,
            "retained_candidates": retained_candidates,
            "retained_context": retained_context,
            "delivery_recipe": recipe,
            **effectiveness,
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
            recipes = {row["delivery_recipe"] for row in rows}
            if len(recipes) != 1:
                raise MatrixSyncError(
                    f"Exact scenario {form.identity} has target-dependent delivery recipes"
                )
            total = len(rows)
            if total != PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][level]:
                raise MatrixSyncError(
                    f"Exact scenario {form.identity} has an incomplete level-{level} roster"
                )
            effective = sum(bool(row["effective"]) for row in rows)
            state = classify_catalog_pricing(
                sum(int(row["retained_candidates"]) for row in rows),
                sum(int(row["retained_context"]) for row in rows),
            )
            cells[key] = ControlCatalogCell(
                state=state,
                mean_cu=sum(float(row["cu"]) for row in rows) / total,
                mean_delivery=sum(float(row["delivery"]) for row in rows) / total,
                effective_targets=effective,
                total_targets=total,
                exceptions=tuple(
                    ControlCoverageException(
                        target=str(row["target"]),
                        status=str(row["status"]),
                        reasons=tuple(str(reason) for reason in row["reasons"]),
                        surviving_consequences=tuple(
                            str(consequence) for consequence in row["surviving"]
                        ),
                    )
                    for row in rows
                    if row["status"]
                    in {
                        PARTIALLY_EFFECTIVE,
                        INEFFECTIVE_STRUCTURAL,
                        INEFFECTIVE_NULLIFIED,
                    }
                ),
                delivery_recipe=next(iter(recipes)),
            )
    return cells


def validate_comparator_reference_scenarios(
    rows: Sequence[MatrixRow], levels: Sequence[int]
) -> dict[tuple[str, str, int], ComparatorReferenceCell]:
    """Validate target-selected comparator references and aggregate full rosters."""
    _require_fields(rows, COMPARATOR_REFERENCE_COLUMNS, "Comparator reference detail")
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
    inventories = {
        "battle_master": dict(BATTLE_MASTER_REFERENCE_SCENARIOS),
        "eldritch_knight": dict(ELDRITCH_KNIGHT_REFERENCE_FAMILIES),
    }
    targets = load_targets(profile=DEFAULT_PROFILE, levels=set(levels))
    target_identities = {(str(target.level), target.name) for target in targets}
    expected = {
        (str(target.level), target.name, build, family_id)
        for target in targets
        for build, inventory in inventories.items()
        for family_id in inventory
    }
    parsed: dict[tuple[str, str, str, str], dict[str, object]] = {}
    allowed_dispositions = {
        "unavailable",
        "ineligible",
        "priced_nonzero",
        "legitimately_priced_zero",
        "entirely_context_required_or_unsupported",
    }
    selection_basis = "Control Value CU -> Whole-package control stick % -> Scenario ID"
    for index, row in enumerate(rows):
        _validate_value_source(row, index, "Comparator reference detail", expected_source)
        build = row["Build"]
        inventory = inventories.get(build)
        if inventory is None or row["Family ID"] not in inventory:
            raise MatrixSyncError(f"Comparator reference row {index} has unknown inventory identity")
        family_id = row["Family ID"]
        if row["Display Name"] != inventory[family_id]:
            raise MatrixSyncError(f"Comparator reference row {index} has stale display name")
        if (row["Level"], row["Target"]) not in target_identities:
            raise MatrixSyncError(f"Comparator reference row {index} has unknown target identity")
        identity = (row["Level"], row["Target"], build, family_id)
        if identity in parsed:
            raise MatrixSyncError(f"Comparator reference detail duplicates target identity {identity}")
        if row["Selection Basis"] != selection_basis:
            raise MatrixSyncError(f"Comparator reference row {index} has alternate selection ordering")
        if row["Family Available At Level"] not in {"True", "False"} or row["Eligible"] not in {"True", "False"} or row["Effective"] not in {"True", "False"}:
            raise MatrixSyncError(f"Comparator reference row {index} has invalid boolean evidence")
        available = row["Family Available At Level"] == "True"
        eligible = row["Eligible"] == "True"
        effective = row["Effective"] == "True"
        try:
            level = int(row["Level"])
            cu = float(row["Control Value CU"])
            delivery = float(row["Whole-package control stick %"])
            primitive_rows = int(row["Primitive Rows"])
            candidate_rows = int(row["Candidate Rows"])
            context_rows = int(row["Context/Unsupported Rows"])
            retained_candidates = int(row["Retained Candidate Rows"])
            retained_context = int(row["Retained Context/Unsupported Rows"])
            family_candidates = int(row["Family Candidate Scenarios"])
        except (TypeError, ValueError) as error:
            raise MatrixSyncError(f"Comparator reference row {index} has non-numeric evidence") from error
        if (
            level not in levels
            or not math.isfinite(cu)
            or cu < 0
            or not math.isfinite(delivery)
            or not 0 <= delivery <= 100
            or min(primitive_rows,candidate_rows,context_rows,retained_candidates,retained_context,family_candidates) < 0
            or primitive_rows != candidate_rows + context_rows
            or retained_candidates > candidate_rows
            or retained_context > context_rows
        ):
            raise MatrixSyncError(f"Comparator reference row {index} has invalid numeric evidence")
        if row["Value Disposition"] not in allowed_dispositions:
            raise MatrixSyncError(f"Comparator reference row {index} has invalid disposition")
        declared = _catalog_tokens(row["Declared Consequences"],r"(?:condition|outcome):[a-z0-9_]+","consequence token",index)
        surviving = _catalog_tokens(row["Surviving Consequences"],r"(?:condition|outcome):[a-z0-9_]+","consequence token",index)
        reasons = _catalog_tokens(row["Effectiveness Reasons"],r"(?:exceeds_maximum_size|requires_creature_type|immune_condition|dependency_condition_immune|automatic_save_success):[a-z0-9_]+","effectiveness reason",index)
        if Counter(surviving)-Counter(declared):
            raise MatrixSyncError(f"Comparator reference row {index} has undeclared surviving control")
        status = row["Effectiveness Status"]
        structural = any(reason.startswith(("exceeds_maximum_size:","requires_creature_type:")) for reason in reasons)
        effect_loss = any(reason.startswith(("immune_condition:","dependency_condition_immune:","automatic_save_success:")) for reason in reasons)
        if not available:
            valid = not eligible and not effective and cu==0 and delivery==0 and not row["Scenario"] and family_candidates==0 and row["Value Disposition"]=="unavailable" and status==EFFECTIVENESS_NOT_APPLICABLE and not declared and not surviving and not reasons
        elif status==EFFECTIVE:
            valid = eligible and effective and bool(declared) and Counter(declared)==Counter(surviving) and not reasons
        elif status==PARTIALLY_EFFECTIVE:
            valid = eligible and effective and bool(surviving) and Counter(declared)!=Counter(surviving) and effect_loss and not structural
        elif status==INEFFECTIVE_STRUCTURAL:
            valid = not eligible and not effective and bool(declared) and not surviving and structural and not effect_loss and cu==0 and delivery==0
        elif status==INEFFECTIVE_NULLIFIED:
            valid = eligible and not effective and bool(declared) and not surviving and effect_loss and not structural and cu==0 and delivery==0
        else:
            valid = False
        if not valid:
            raise MatrixSyncError(f"Comparator reference row {index} has inconsistent effectiveness or availability evidence")
        if available and (not row["Scenario"] or family_candidates<1 or row["Value Disposition"]=="unavailable"):
            raise MatrixSyncError(f"Comparator reference row {index} lacks an available selected scenario")
        if build=="battle_master":
            if row["Spell ID"] or (available and (row["Scenario"]!=family_id or family_candidates!=1)) or row["Save Primers"] or row["Primer Timing"] not in {"","none"}:
                raise MatrixSyncError(f"Battle Master reference row {index} is not the fixed maintained maneuver")
        else:
            if row["Spell ID"]!=family_id:
                raise MatrixSyncError(f"Eldritch Knight reference row {index} is not grouped by spell_id")
            primers=_catalog_tokens(row["Save Primers"],r"(?:eldritch_strike|mind_sliver)","save primer",index)
            if "mind_sliver" in primers and row["Primer Timing"]!="cross_turn":
                raise MatrixSyncError(f"Eldritch Knight reference row {index} uses Mind Sliver outside the approved cross-turn window")
            if available and row["Primer Timing"] not in {"none","prior_attack_action","cross_turn"}:
                raise MatrixSyncError(f"Eldritch Knight reference row {index} has unknown primer timing")
            if not available and (primers or row["Primer Timing"]):
                raise MatrixSyncError(f"Unavailable Eldritch Knight family row {index} retains primer evidence")
            if family_id=="blindness_deafness" and available and ("condition:blinded" not in declared or "outcome:hearing_option_denial" in declared):
                raise MatrixSyncError("Blindness/Deafness reference is not the maintained Blinded mode")
        parsed[identity]={"available":available,"cu":cu,"delivery":delivery,"effective":effective,"scenario":row["Scenario"]}
    _key_difference(set(parsed),expected,"Comparator reference detail")
    cells={}
    targets_by_level={level:tuple(target for target in targets if target.level==level) for level in levels}
    for build,inventory in inventories.items():
        for family_id in inventory:
            for level in levels:
                family_rows=[parsed[(str(level),target.name,build,family_id)] for target in targets_by_level[level]]
                availability={bool(item["available"]) for item in family_rows}
                if len(availability)!=1:
                    raise MatrixSyncError(f"Comparator family {(build,family_id,level)} has target-dependent level availability")
                if not next(iter(availability)):
                    cells[(build,family_id,level)]=ComparatorReferenceCell(False);continue
                total=len(family_rows)
                if total!=PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][level]:
                    raise MatrixSyncError(f"Comparator family {(build,family_id,level)} has an incomplete roster")
                cells[(build,family_id,level)]=ComparatorReferenceCell(
                    True,
                    sum(float(item["cu"]) for item in family_rows)/total,
                    sum(float(item["delivery"]) for item in family_rows)/total,
                    sum(bool(item["effective"]) for item in family_rows),
                    total,
                    tuple((target.name,str(item["scenario"])) for target,item in zip(targets_by_level[level],family_rows,strict=True)),
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


def _render_comparator_reference_cell(cell: ComparatorReferenceCell) -> str:
    if not cell.available:return "N/A"
    if (
        cell.mean_cu is None
        or cell.mean_delivery is None
        or cell.effective_targets is None
        or cell.total_targets is None
        or not math.isfinite(cell.mean_cu)
        or not math.isfinite(cell.mean_delivery)
        or not 0<=cell.effective_targets<=cell.total_targets
    ):
        raise MatrixSyncError("Comparator reference cell is missing aggregate evidence")
    return f"{cell.mean_cu:.3f} CU · {cell.mean_delivery:.2f}% · {cell.effective_targets}/{cell.total_targets}"


def render_comparator_reference_scale(
    cells: Mapping[tuple[str,str,int],ComparatorReferenceCell],levels: Sequence[int]
) -> str:
    """Render the compact raw BM/EK comparison scale."""
    inventories=(
        ("battle_master","Battle Master reference maneuvers",BATTLE_MASTER_REFERENCE_SCENARIOS,"Maneuver"),
        ("eldritch_knight","Eldritch Knight reference spell families",ELDRITCH_KNIGHT_REFERENCE_FAMILIES,"Spell family"),
    )
    expected={(build,family_id,int(level)) for build,_,inventory,_ in inventories for family_id,_ in inventory for level in levels}
    _key_difference(set(cells),expected,"Comparator reference publication")
    sections=[
        "## Comparator reference scale",
        "",
        (
            "These raw rows provide a familiar Fighter comparison scale beside the exact-form "
            "Kinetic Vanguard catalog. They are reference measurements, not Kinetic Vanguard rules."
        ),
        "",
        "**Cell format:** `CU · initial delivery · effective/roster`",
        "",
        (
            "`CU` is complete-roster mean Control Value. `Initial delivery` is the complete-roster "
            "mean initial establishment probability after maintained legal retries and primer logic. "
            "`Effective/roster` counts targets for which at least one modeled control consequence "
            "survives structural restrictions, maintained immunities, and effect dependencies. "
            "Zero and nullified targets remain in both means; coverage is not derived from CU, "
            "pricing state, or delivery probability."
        ),
        "",
    ]
    for build,heading,inventory,first_column in inventories:
        sections.extend((f"### {heading}",""))
        if build=="eldritch_knight":
            sections.extend((
                "**Best maintained legal setup for each spell family per target.** Candidates are "
                "grouped by stable `spell_id`; the exact selector orders them by highest CU, then "
                "highest initial Reliability on an exact CU tie, then lexicographically ascending "
                "stable Scenario ID on an exact tie. Different targets may select different setups.",
                "",
            ))
        table_rows=[
            [display_name,*(_render_comparator_reference_cell(cells[(build,family_id,int(level))]) for level in levels)]
            for family_id,display_name in inventory
        ]
        sections.extend((_markdown_table((first_column,*(f"Fighter {level}" for level in levels)),table_rows),""))
        if build=="battle_master":
            sections.extend((
                "Goading Attack and Disarming Attack remain maintained context-required diagnostics; "
                "they are not scalar reference rows.",
                "",
            ))
        else:
            sections.extend((
                "`N/A` means the family is not spell-accessible at that Fighter level. When a family "
                "is available, target-specific restrictions such as Hold Person's Humanoid requirement "
                "contribute zero and remain in the complete-roster denominator.",
                "",
            ))
    sections.extend((
        "### How to interpret comparator references",
        "",
        (
            "These rows do not mean Kinetic Vanguard should equal each reference, that every source is "
            "equally severe or broadly applicable, that higher Reliability implies greater severity, "
            "or that higher CU implies higher delivery. Control Value and Reliability retain the "
            "separate meanings documented below."
        ),
        "",
        (
            "Creature and roster facts come from SRD 5.2.1. Battle Master and Eldritch Knight mechanics "
            "come from reviewed, independently expressed current-PHB-derived analytical abstractions in "
            "`harness/comparators/fighter-subclasses.json`. This unofficial comparative scale is not "
            "Wizards-endorsed project content, is not Kinetic Vanguard rules, and does not assert that "
            "the Eldritch Knight control inventory is SRD-only."
        ),
    ))
    return "\n".join(sections)


def _render_catalog_cell(cell: ControlCatalogCell) -> str:
    if cell.state == UNAVAILABLE:
        return "N/A"
    if cell.state == NO_MODELED_CONTROL:
        return "0.000 CU · — · no modeled control"
    if (
        cell.mean_cu is None
        or cell.mean_delivery is None
        or cell.effective_targets is None
        or cell.total_targets is None
        or not math.isfinite(cell.mean_cu)
        or not math.isfinite(cell.mean_delivery)
        or not 0 <= cell.effective_targets <= cell.total_targets
    ):
        raise MatrixSyncError("Control catalog cell is missing aggregate evidence")
    coverage = f"{cell.effective_targets}/{cell.total_targets}"
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


def _render_delivery_recipe(recipe: ControlDeliveryRecipe | None) -> str:
    if recipe is None:
        return "—"
    save = recipe.save_ability.title()
    labels = {
        "mastery_attack_action_hit_retry": (
            "Kinetic Mastery — ordinary Attack-action at least one hit"
        ),
        "no_modeled_control": "—",
        "single_activation_automatic": "Single activation — automatic/no-save modeled control",
        "single_activation_failed_save": f"Single activation — failed {save} save",
        "single_activation_hit": "Single activation — hit",
        "single_activation_hit_failed_save": (
            f"Single activation — hit × failed {save} save"
        ),
        "kv_attack_action_hit_retry": "KV Attack-action retry — hit",
        "kv_attack_action_hit_failed_save_retry": (
            f"KV Attack-action retry — hit × failed {save} save"
        ),
    }
    try:
        label=labels[recipe.recipe_id]
    except KeyError as error:
        raise MatrixSyncError(
            f"Unknown delivery recipe ID: {recipe.recipe_id}"
        ) from error
    if not recipe.additional_control_gate:return label
    if recipe.additional_control_gate!="failed_save" or not recipe.save_ability:
        raise MatrixSyncError("Malformed additional-control delivery gate")
    if recipe.gate=="automatic":label="Single activation — automatic control"
    return f"{label}; failed {recipe.save_ability.title()} save gates additional control"


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
        "**Cell format:** `CU · delivery · effective/roster`",
        "",
        (
            "Example: `0.143 CU · 95.00% · 12/12` means `0.143 CU` average Control "
            "Value and `95.00%` average initial control-delivery probability across the full "
            "benchmark roster at that fighter level. `effective/roster` is **targets against "
            "which at least one modeled control consequence from that exact source survives "
            "maintained structural restrictions, immunities, and effect dependencies / total "
            "roster targets**."
        ),
        "",
        (
            "`12/12 effective` does **not** mean 100% delivery or that every consequence works; "
            "it means every roster target can receive at least one modeled consequence from "
            "that exact source. `10/11 effective` means one of the 11 creatures cannot receive "
            "any modeled control from that source. A target can remain counted in `12/12 "
            "effective` while appearing in a partial-effect exception because another modeled "
            "consequence survives. Coverage is not a save result, hit count, successful "
            "application count, CU threshold, pricing state, or delivery probability."
        ),
        "",
        (
            "`Partial` means retained priced and retained context-required or unsupported "
            "consequences coexist; suppressed duplicate or weaker primitives do not create that "
            "label. `Unpriced` retains measurable delivery and effectiveness coverage without reporting zero "
            "CU. `No modeled control` means `0.000 CU` and no control delivery (`—`). `N/A` means "
            "the exact form is unavailable at that level."
        ),
        "",
        (
            "Full denominator and state methodology: "
            "[Benchmark roster, effectiveness, and coverage]"
            "(#benchmark-roster-effectiveness-and-coverage)"
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
            recipes = {
                cells[(*form.identity, int(level))].delivery_recipe
                for level in levels
                if cells[(*form.identity, int(level))].delivery_recipe is not None
            }
            if len(recipes) > 1:
                raise MatrixSyncError(
                    f"Control catalog form {form.identity} has level-dependent delivery recipes"
                )
            recipe = next(iter(recipes), None)
            rows.append(
                [
                    label,
                    _render_delivery_recipe(recipe),
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
                    (
                        "Rider / form",
                        "Delivery recipe",
                        *(f"Fighter {level}" for level in levels),
                    ),
                    rows,
                ),
            )
        )
    return "\n".join(sections)


def _reader_consequence(token: str) -> str:
    kind, value = token.split(":", 1)
    if kind not in {"condition", "outcome"}:
        raise MatrixSyncError(f"Unknown control consequence kind: {kind}")
    if value == "speed_zero":
        return "Speed 0"
    return value.replace("_", " ").capitalize()


def _reader_exception_reason(exception: ControlCoverageException) -> str:
    phrases: list[str] = []
    for token in exception.reasons:
        kind, value = token.split(":", 1)
        label = value.replace("_", " ").title()
        if kind == "exceeds_maximum_size":
            phrases.append(f"exceeds maximum size {label}")
        elif kind == "requires_creature_type":
            phrases.append(f"requires {label}")
        elif kind == "immune_condition":
            phrases.append(f"immune to {label}")
        elif kind == "dependency_condition_immune":
            phrases.append(
                f"required condition {label} is unavailable because target is immune to {label}"
            )
        else:
            raise MatrixSyncError(f"Unknown control effectiveness reason: {kind}")
    if exception.status == PARTIALLY_EFFECTIVE:
        survivors = tuple(dict.fromkeys(map(_reader_consequence, exception.surviving_consequences)))
        if not survivors:
            raise MatrixSyncError("Partial effectiveness exception lacks surviving control")
        if len(survivors) == 1:
            phrases.append(f"{survivors[0]} remains effective")
        else:
            survivor_text = (
                f"{survivors[0]} and {survivors[1]}"
                if len(survivors) == 2
                else ", ".join(survivors[:-1]) + f", and {survivors[-1]}"
            )
            phrases.append(f"{survivor_text} remain effective")
    return "; ".join(phrases)


def render_control_coverage_exceptions(
    catalog: Sequence[ControlCatalogForm],
    cells: Mapping[tuple[str, str, int], ControlCatalogCell],
    levels: Sequence[int],
) -> str:
    """Render deterministic target-level reductions from structured evidence."""
    labels = {
        "cryokinesis": "Cryokinesis",
        "pyrokinesis": "Pyrokinesis",
        "psychokinesis": "Psychokinesis",
        "electrokinesis": "Electrokinesis",
    }
    variant_counts: dict[tuple[str, str | None, int | None], int] = {}
    for form in catalog:
        key = (form.discipline_id, form.entity_id, form.tier)
        variant_counts[key] = variant_counts.get(key, 0) + 1
    rows: list[tuple[str, str, str, str, str]] = []
    for form in catalog:
        form_label = form.title if form.is_mastery else f"{form.title} — T{form.tier}"
        if not form.is_mastery and variant_counts[(form.discipline_id, form.entity_id, form.tier)] > 1:
            form_label += f" — {form.target_role}"
        for level in levels:
            cell = cells[(*form.identity, int(level))]
            grouped: dict[tuple[str, str], list[str]] = {}
            for exception in cell.exceptions:
                status = "Partial" if exception.status == PARTIALLY_EFFECTIVE else "Ineffective"
                reason = _reader_exception_reason(exception)
                grouped.setdefault((status, reason), []).append(exception.target)
            for (status, reason), targets in grouped.items():
                rows.append(
                    (
                        f"{labels[form.discipline_id]} — {form_label}",
                        f"Fighter {level}",
                        ", ".join(targets),
                        status,
                        reason,
                    )
                )
    return "\n".join(
        (
            "### Control coverage exceptions",
            "",
            (
                "These generated rows expose structural exclusions, complete effect "
                "nullification, and partial losses from the same evidence used by the catalog."
            ),
            "",
            _markdown_table(
                ("Discipline / exact form", "Level", "Affected target(s)", "Status", "Reason"),
                rows,
            ),
        )
    )


def render_benchmark_roster_methodology() -> str:
    """Render the maintained full-roster aggregation and catalog state contract."""
    return "\n".join(
        (
            "### Benchmark roster, effectiveness, and coverage",
            "",
            (
                "Every Fighter level uses the complete maintained headline roster for that "
                "level. Structural legality remains an internal prerequisite evaluated by "
                "`target_is_eligible()` from maintained maximum-size and required-creature-type "
                "restrictions. Public `effective/roster` coverage asks a different question: "
                "for how many roster targets does at least one modeled control consequence from "
                "this exact Mastery or rider survive structural restrictions, maintained "
                "immunities, and effect dependencies?"
            ),
            "",
            (
                "A structural restriction makes a target ineffective for that exact source. "
                "Maintained immunity can instead remove one or more consequences after the "
                "structural check. If another consequence survives, the target is partially "
                "effective and remains in the coverage numerator; if every modeled consequence "
                "is nullified, the target is ineffective. Thus `12/12 effective` does not mean "
                "100% delivery, 12 successful saves or attacks, 12 successful applications, or "
                "that every consequence works against every target."
            ),
            "",
            (
                "Effective coverage is descriptive metadata, not a success roll, CU threshold, "
                "pricing state, delivery probability, or alternate averaging population. An "
                "ineffective target remains in the aggregate denominator at its existing `CU = "
                "0` and `delivery = 0%` contribution. A partially effective target contributes "
                "the CU and delivery of the consequences that survive."
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
                "Do not divide only by effective targets. Effective-only averaging would hide "
                "practical restrictions and could make a narrowly applicable control look "
                "stronger or more reliable than it is across the maintained benchmark roster."
            ),
            "",
            (
                "**Instructional example (not a published scenario):** if a form has 80% "
                "delivery against 9 effective targets and 3 ineffective targets contribute 0%, "
                "its full-roster delivery mean is `(9 × 0.80 + 3 × 0) / 12 = 0.60 = 60%`. "
                "The effective-only 80% is not the roster-wide result."
            ),
            "",
            (
                "`Priced` and `Partial` use the complete-roster denominator above. `Unpriced` "
                "can still be effectively covered and show independently measurable delivery, but its CU "
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


CONTROL_VALUE_TRANSFORM_FORMULAS = {
    "linear_expected_exposure": (
        "CU = nominal weight × expected exposure",
        "Expected exposure is the placed probability/opportunity exposure for the primitive's maintained basis.",
    ),
    "expected_displaced_feet": (
        "CU = nominal weight × expected displaced feet",
        "Displacement uses expected intrinsic feet only; it does not invent terrain or collision value.",
    ),
    "points_times_placed_opportunities": (
        "CU = nominal weight × expected penalty-points/opportunities",
        "The placed exposure already combines the exact penalty magnitude with established attack or save opportunities.",
    ),
    "bounded_fraction_of_benchmark_locomotion": (
        "CU = nominal weight × min(expected lost feet / benchmark locomotion Speed, active-window exposure)",
        "For one fully active window: CU = nominal weight × min(flat feet lost / benchmark locomotion Speed, 1).",
    ),
    "remaining_speed_fraction": (
        "CU = nominal weight × (1 - remaining Speed fraction) × active-window exposure",
        "The magnitude is the exact fraction of Speed that remains.",
    ),
    "diagnostic_zero": (
        "CU = 0 headline CU",
        "This is a deliberate non-scalar/context diagnostic rule, not a claim that the mechanic has zero real-play value.",
    ),
}


def _control_value_publication_contract(
    scoring: Mapping[str, object] | None = None,
    catalog: Mapping[str, object] | None = None,
) -> tuple[Mapping[str, object], tuple[Mapping[str, object], ...]]:
    """Join the frozen scoring rules to catalog authority and fail closed on drift."""
    scoring = load_scoring_config() if scoring is None else scoring
    catalog = load_primitive_catalog() if catalog is None else catalog
    rules = scoring.get("rules")
    primitive_rows = catalog.get("primitives")
    if not isinstance(rules, dict) or not isinstance(primitive_rows, list):
        raise MatrixSyncError("README Control Value publication inputs are malformed")
    if not all(isinstance(row, dict) for row in primitive_rows):
        raise MatrixSyncError("README Control Value primitive catalog rows are malformed")
    by_id = {str(row.get("id")): row for row in primitive_rows}
    unknown = sorted(set(rules) - set(by_id))
    if unknown:
        raise MatrixSyncError(
            "Control Value scoring rules reference unknown primitives: " + ", ".join(unknown)
        )
    missing_candidates = sorted(
        primitive_id
        for primitive_id, row in by_id.items()
        if row.get("default_status") == "candidate" and primitive_id not in rules
    )
    if missing_candidates:
        raise MatrixSyncError(
            "Default-candidate primitives lack scalar scoring rules: "
            + ", ".join(missing_candidates)
        )
    for primitive_id, raw_rule in rules.items():
        if not isinstance(raw_rule, dict):
            raise MatrixSyncError(f"Control Value scoring rule {primitive_id} is malformed")
        transform = raw_rule.get("transform")
        if transform not in CONTROL_VALUE_TRANSFORM_FORMULAS:
            raise MatrixSyncError(
                f"README has no formula for Control Value transform: {transform}"
            )
        weight = raw_rule.get("nominal_weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise MatrixSyncError(f"Control Value scoring rule {primitive_id} has invalid weight")
        row = by_id[primitive_id]
        if not all(
            isinstance(row.get(field), str)
            for field in ("exposure_basis", "default_status", "reason")
        ):
            raise MatrixSyncError(f"Primitive catalog contract is incomplete for {primitive_id}")
    return rules, tuple(primitive_rows)


def render_control_primitive_pricing_rubric(
    scoring: Mapping[str, object] | None = None,
    catalog: Mapping[str, object] | None = None,
) -> str:
    """Publish every maintained scoring rule and every transform it uses."""
    rules, primitive_rows = _control_value_publication_contract(scoring, catalog)
    by_id = {str(row["id"]): row for row in primitive_rows}
    rubric_rows = []
    transforms: list[str] = []
    for primitive_id, raw_rule in rules.items():
        assert isinstance(raw_rule, dict)
        contract = by_id[primitive_id]
        transform = str(raw_rule["transform"])
        if transform not in transforms:
            transforms.append(transform)
        rubric_rows.append(
            (
                f"`{primitive_id}`",
                f"`{contract['exposure_basis']}`",
                f"`{contract['default_status']}`",
                f"{float(raw_rule['nominal_weight']):.2f} CU",
                f"`{transform}`",
            )
        )
    transform_rows = [
        (f"`{transform}`", f"`{CONTROL_VALUE_TRANSFORM_FORMULAS[transform][0]}`", CONTROL_VALUE_TRANSFORM_FORMULAS[transform][1])
        for transform in transforms
    ]
    return "\n".join(
        (
            "### Control Unit primitive pricing rubric",
            "",
            (
                "This is the complete maintained scoring-rule inventory. Primitive basis and "
                "default pricing status come from the primitive catalog; nominal weights and "
                "transform IDs come from the frozen scoring config."
            ),
            "",
            _markdown_table(
                ("Primitive", "Exposure basis", "Default pricing status", "Nominal weight", "Scoring rule"),
                rubric_rows,
            ),
            "",
            "#### Maintained transform definitions",
            "",
            _markdown_table(("Transform", "Formula", "Meaning"), transform_rows),
        )
    )


def render_unpriced_primitive_menu(
    scoring: Mapping[str, object] | None = None,
    catalog: Mapping[str, object] | None = None,
) -> str:
    """Publish every primitive whose catalog default is not scalar-candidate."""
    _, primitive_rows = _control_value_publication_contract(scoring, catalog)
    unpriced_rows = [
        (
            f"`{row['id']}`",
            f"`{row['exposure_basis']}`",
            f"`{row['default_status']}`",
            str(row["reason"]),
        )
        for row in primitive_rows
        if row["default_status"] != "candidate"
    ]
    return "\n".join(
        (
            "### Context-dependent and unpriced control primitives",
            "",
            (
                "Every primitive below defaults to `context_required` or `unsupported`, including "
                "entries with no scalar scoring rule. It contributes 0 headline CU when the "
                "benchmark cannot establish the required context. That fail-closed zero does "
                "**not** mean the mechanic is worthless in actual play."
            ),
            "",
            _markdown_table(
                ("Primitive", "Exposure basis", "Status", "Why it is not assigned headline CU"),
                unpriced_rows,
            ),
            "",
            (
                "`unsupported` can also arise dynamically when a known mechanic lacks a trustworthy "
                "required magnitude, timing, or placement/exposure basis. Maintained examples of "
                "unresolved context include Ball Lightning future area occupancy, Mass Levitation "
                "recurring displacement cadence, and condition-context facts such as sight, "
                "concentration, speech, fall state, or attacker distance. The benchmark does not "
                "manufacture encounter facts to turn these diagnostics into numbers."
            ),
        )
    )


def render_movement_methodology(
    scoring: Mapping[str, object] | None = None,
    catalog: Mapping[str, object] | None = None,
) -> str:
    """Render target-specific movement pricing directly from maintained weights."""
    rules, _ = _control_value_publication_contract(scoring, catalog)
    denial = rules["turn_movement_denial"]
    flat = rules["mobility_loss_feet"]
    assert isinstance(denial, dict) and isinstance(flat, dict)
    denial_weight = float(denial["nominal_weight"])
    flat_weight = float(flat["nominal_weight"])
    examples = (
        ("-10 ft against benchmark Speed 10", f"{flat_weight:.2f} × min(10 / 10, 1)", f"{flat_weight * min(10 / 10, 1):.2f} CU"),
        ("-10 ft against benchmark Speed 30", f"{flat_weight:.2f} × min(10 / 30, 1)", f"{flat_weight * min(10 / 30, 1):.2f} CU"),
        ("-10 ft against benchmark Speed 60", f"{flat_weight:.2f} × min(10 / 60, 1)", f"{flat_weight * min(10 / 60, 1):.2f} CU"),
        ("-30 ft against benchmark Speed 60", f"{flat_weight:.2f} × min(30 / 60, 1)", f"{flat_weight * min(30 / 60, 1):.2f} CU"),
        ("Speed 0 against any ordinary Speed", f"{denial_weight:.2f} × 1.00 active exposure", f"{denial_weight:.2f} CU"),
    )
    return "\n".join(
        (
            "#### How movement control is normalized",
            "",
            "There is **no universal 30-foot target assumption**.",
            "",
            (
                "**Complete movement denial.** `turn_movement_denial` (Speed 0) is valued "
                f"at `{denial_weight:.2f} CU × active exposure`, independent of ordinary Speed. "
                "A creature with 10, 30, 60, or 80 feet of ordinary benchmark locomotion loses "
                "all movement capacity when rooted."
            ),
            "",
            (
                f"**Flat Speed loss.** `mobility_loss_feet` uses `{flat_weight:.2f} CU × "
                "min(expected lost feet / benchmark locomotion Speed, active-window exposure)`. "
                "For one fully active window this is `weight × min(flat feet lost / benchmark "
                "locomotion Speed, 1)`."
            ),
            "",
            "**Illustrative calculations (not current aggregate results):**",
            "",
            _markdown_table(("Illustrative case", "Calculation", "Result"), examples),
            "",
            (
                "**Benchmark locomotion assumption.** `benchmark_locomotion_speed` is the fastest "
                "positive movement mode in the maintained SRD target record that is unconditional, "
                "unqualified, and not choice-dependent. Qualified or choice-dependent modes are "
                "excluded; walking Speed is not privileged. If no trustworthy positive mode exists, "
                "flat `mobility_loss_feet` fails closed to `context_required`."
            ),
            "",
            (
                "Using the fastest unconditionally available listed mode supplies a neutral, "
                "target-specific denominator without inventing encounter geometry. It can "
                "conservatively understate a flat reduction in a fight where that fastest mode "
                "cannot be used. For example, an unconditional Fly Speed remains the maintained "
                "denominator even if a particular room prevents flight; the benchmark does not "
                "silently substitute walking Speed for an unmodeled battlefield."
            ),
            "",
            (
                "**Correlated flat movement cap.** Multiple flat reductions are capped at complete "
                "movement denial only when explicit maintained correlation metadata connects their "
                "sources for the same scored windows. The cap never exceeds the target's benchmark "
                "locomotion Speed. Sharing a package, a primitive, or the fact that both reduce Speed "
                "does not establish correlation; unrelated mobility effects remain independent."
            ),
        )
    )


def render_control_normalization_methodology() -> str:
    """Describe the evaluator's maintained duplicate and dominance contracts."""
    rows = (
        ("Duplicates", "Identical primitive/basis/qualifier/magnitude consequences do not double count. `mobility_loss_feet` and `forced_displacement` remain source-specific so distinct legitimate sources are not automatically collapsed."),
        ("Disjoint sequential stages", "Explicitly declared disjoint stages combine probabilities instead of becoming duplicate overlap; their combined probability may not exceed 1."),
        ("Action-economy dominance", "Overlapping `active_turn_denial` dominates `bonus_action_denial`, `action_bonus_exclusivity`, `specified_action_requirement`, `attack_action_cap`, and offensive impairment. `bonus_action_denial` also dominates overlapping `action_bonus_exclusivity`."),
        ("Specified Action interaction", "`specified_action_requirement` consumes overlapping all-attacks impairment on the same target-turn exposure instead of charging both at full value."),
        ("Attack impairment", "All-attacks impairment dominates next-attack impairment only when maintained source-overlap metadata identifies the same attack share. An unrelated next-attack effect survives."),
        ("Save impairment", "For the same save ability, `save_auto_failure` dominates `save_disadvantage`, `flat_save_roll_penalty`, and `finite_next_save_roll_penalty`. Impairment of a different save ability survives."),
        ("Movement dominance", "`turn_movement_denial` dominates overlapping `mobility_loss_feet`, `speed_multiplier`, and `standing_movement_cost`."),
        ("Correlated flat mobility", "Only explicit same-window correlation metadata invokes the target-specific complete-movement cap; unrelated flat reductions are not implicitly capped or merged."),
        ("Partial overlap", "When a stronger effect covers only part of the weaker effect's active exposure, the residual weaker exposure is preserved."),
        ("Unrelated consequences", "Unrelated surviving primitives add independently."),
    )
    return "\n".join(
        (
            "### Control Value normalization rules",
            "",
            (
                "Normalization prevents double charging while preserving independently established "
                "consequences. These statements describe `normalize_exposures()` and the explicit "
                "correlated-flat-mobility cap; they are not a second scoring engine."
            ),
            "",
            _markdown_table(("Rule", "Maintained behavior"), rows),
        )
    )


def render_reliability_definition() -> str:
    return "\n".join(
        (
            "### What Reliability measures",
            "",
            (
                "`Whole-package control stick %` is the probability that the exact published "
                "control source or package establishes at least one modeled control consequence "
                "in its legal initial delivery window, after all maintained legal retries and "
                "resource constraints are applied. It is initial establishment/delivery "
                "probability: it is not a severity score, Control Value, effective coverage, or "
                "the probability of remaining controlled for all three benchmark rounds."
            ),
            "",
            (
                "The headline discipline benchmark reports the delivery of the same full legal "
                "package selected by Control Value. It does not run a separate Reliability "
                "winner-selection pass. Persistence is a separate diagnostic and contributes to "
                "active exposure and Control Value where the maintained scenario timing calls for it."
            ),
        )
    )


def render_probability_grammar() -> str:
    return "\n".join(
        (
            "### One-attempt probability grammar",
            "",
            "**Hit-gated, no save:** `P(control) = P(hit)`.",
            "",
            (
                "The maintained attack helper enumerates d20 results exactly. A natural 1 "
                "misses, a natural 20 hits as a critical, and every other roll hits when "
                "`natural roll + attack bonus >= AC`. `P(hit)` includes ordinary hits plus "
                "critical hits. Where a source contract actually grants attack Advantage, the "
                "helper enumerates both d20s exactly and keeps the higher result; this publication "
                "does not invent Advantage for a control source."
            ),
            "",
            "**Save-only:** `P(control) = P(failed save) = 1 - P(successful save)`.",
            "",
            (
                "A save succeeds when `d20 + maintained save bonus >= DC`. Saving throws do not "
                "use the attack-roll natural-1/natural-20 automatic miss/critical rules. Magic "
                "Resistance supplies save Advantage only where the maintained comparator/source "
                "contract says it applies. The save helper enumerates Advantage and Disadvantage "
                "exactly and cancels them when both apply. Finite penalties such as `d20 - 1d4` "
                "are enumerated over every die result, never replaced by an average penalty."
            ),
            "",
            (
                "**Hit plus failed save:** for the maintained independent gates, "
                "`P(control) = P(hit) × P(failed save)`."
            ),
            "",
            (
                "**Automatic / no-save modeled control:** application uses the maintained "
                "automatic or reach probability supplied by the evaluator. “Automatic” does not "
                "mean universally effective: size/type restrictions, immunities, and effect "
                "dependencies are evaluated separately."
            ),
        )
    )


def render_attack_action_retry_methodology() -> str:
    return "\n".join(
        (
            "### Attack-action retries",
            "",
            (
                "For `n` identical unconstrained attempts with one-attempt success probability "
                "`p`, `P(at least one success) = 1 - (1 - p)^n`. The maintained generic helper "
                "returns this special case when no state-changing legality function is supplied."
            ),
            "",
            (
                "That closed form is not the general Kinetic Vanguard or Battle Master rule when "
                "resources or legality change. Their recursive shape is "
                "`R(attacks remaining, state) = max over legal next states [p + (1 - p) × "
                "R(attacks remaining - 1, next state)]`, with terminal `0` when no attacks or "
                "legal attempts remain. The exact legal resource state is carried forward."
            ),
            "",
            (
                "Every headline control retry window in this section is one ordinary Attack "
                "action. Action Surge is excluded."
            ),
        )
    )


def render_kv_retry_methodology() -> str:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    levels = tuple(int(value) for value in config["methodology"]["levels"])
    resources = tuple(_kv_retry_resources(model, config, level) for level in levels)
    rows = []
    for row in resources:
        mastery = (
            f"available / {row['overload_mastery_uses']} per rest"
            if row["overload_mastery_uses"]
            else "unavailable / 0"
        )
        taxes = "/".join(str(value) for value in row["blood_tax_by_tier"])
        rows.append(
            (
                row["level"],
                row["attacks_per_action"],
                row["psi_pool"],
                row["benchmark_hp"],
                row["blood_tax_budget"],
                taxes,
                mastery,
                row["tier_two_limit"],
            )
        )
    return "\n".join(
        (
            "### Kinetic Vanguard retry resources",
            "",
            (
                "A repeatable on-hit rider can be declared again on a later Manifested Strike "
                "within the same ordinary Attack action. At each opportunity, the evaluator "
                "carries attacks remaining, Psi spent, Blood Tax spent, Tier-2 declarations, "
                "Overload Mastery uses remaining, and the selected raw/reduced payment mode. A "
                "declaration is legal only if its Psi cost fits the current Psi pool, its "
                "canonical Blood Tax payment fits the benchmark budget, the Tier-2-per-Attack-"
                "action limit is respected, and the current Overload Mastery payment state offers "
                "that option. The recursion then chooses the legal state path with the greatest "
                "at-least-one-establishment probability."
            ),
            "",
            (
                "The canonical payment options preserve the raw Blood Tax path and, while the "
                "maintained Overload Mastery use is available, the exact reduced-tax path. Once "
                "a path establishes its payment mode, later declarations carry that mode and "
                "remaining-use state forward; the renderer does not approximate or rebuild it."
            ),
            "",
            (
                "The table is generated from canonical authority, Fighter progression, and the "
                "benchmark profile used by the evaluator. Benchmark HP and its 25% Blood Tax "
                "budget are analytical inputs, not subclass rules. `T0/T1/T2 tax` lists the "
                "canonical raw Blood Tax before any legal Overload Mastery reduction."
            ),
            "",
            _markdown_table(
                (
                    "Fighter level",
                    "Attacks / Attack action",
                    "Psi pool",
                    "Benchmark HP",
                    "Blood Tax budget",
                    "T0/T1/T2 tax",
                    "Overload Mastery availability/uses",
                    "Tier-2 declaration limit",
                ),
                rows,
            ),
        )
    )


def render_mastery_and_package_methodology() -> str:
    return "\n".join(
        (
            "### Kinetic Mastery retries",
            "",
            (
                "For an eligible current Kinetic Mastery, each qualifying Manifested Strike hit "
                "in one ordinary Attack action is an opportunity and there is no additional "
                "Mastery saving throw. With maintained ordinary attacks/action, "
                "`P(Mastery establishes) = 1 - (1 - P(hit))^attacks`. Action Surge is excluded. "
                "Mastery delivery and rider delivery remain separate catalog recipes."
            ),
            "",
            "### Headline package versus catalog delivery",
            "",
            (
                "The explanatory catalog decomposes each exact source: a Kinetic Mastery row "
                "shows Mastery delivery only, and a rider row shows rider delivery only. Mastery "
                "does not rescue a rider's recipe or target effectiveness. The headline discipline "
                "benchmark instead uses the selected full legal package, and its Reliability is "
                "the initial delivery probability of that same CU-selected package."
            ),
        )
    )


def render_battle_master_retry_methodology() -> str:
    return "\n".join(
        (
            "### Battle Master retry recursion",
            "",
            (
                "For attacks remaining `a`, superiority dice remaining `d`, hit probability `h`, "
                "and failed-save probability `f`, the maintained recursion is:"
            ),
            "",
            "`R(a,d) = (1-h) × R(a-1,d) + h × [f + (1-f) × R(a-1,d-1)]`",
            "",
            (
                "The terminal value is zero when attacks or superiority dice are exhausted. A "
                "miss preserves the die; a hit consumes it; hit plus failed save succeeds; and a "
                "hit followed by a successful save can recurse when both attacks and dice remain. "
                "The headline Control Reliability window excludes Action Surge. This methodology "
                "does not publish the Phase-4 Battle Master reference table."
            ),
        )
    )


def render_eldritch_knight_reliability_methodology() -> str:
    return "\n".join(
        (
            "### Eldritch Knight spell attacks and saves",
            "",
            (
                "A spell attack uses its exact spell-attack hit probability. A save spell uses "
                "its exact failed-save probability. Headline Reliability credits one configured "
                "cast in the spell's delivery window, not repeated casting."
            ),
            "",
            "### Eldritch Strike primer",
            "",
            (
                "A legal prior ordinary Attack action establishes Eldritch Strike with "
                "`P(ES established) = 1 - (1 - P(weapon hit))^ordinary primer attacks`. The "
                "target spell's initial failure probability is the exact mixture "
                "`P(ES) × P(fail with maintained Disadvantage state) + (1 - P(ES)) × "
                "P(ordinary fail)`. The save helper preserves Magic Resistance and cancels "
                "Advantage against Disadvantage when both apply. Eldritch Strike is never "
                "credited below its configured minimum level."
            ),
            "",
            "### Mind Sliver primer",
            "",
            (
                "Only the approved cross-turn composition is modeled. Mind Sliver must first "
                "establish on its Intelligence save; if it does, the next qualifying save "
                "enumerates exact `d20 - 1d4` outcomes, with no average `-2.5` substitution. "
                "The composition is `P(initial target save fails) = P(Mind Sliver establishes) "
                "× P(penalized save fails) + P(Mind Sliver does not establish) × "
                "P(unpenalized composed save fails)`. If Eldritch Strike is also present, the "
                "finite penalty and probabilistic Disadvantage are combined exactly, including "
                "Magic Resistance cancellation. Same-Attack-action Mind Sliver sequencing is not modeled."
            ),
        )
    )


def render_persistence_methodology() -> str:
    return "\n".join(
        (
            "### Persistence is separate from delivery",
            "",
            (
                "Let initial delivery be `p` and the maintained repeat-save failure probability "
                "be `q`. For an effect whose timing supplies repeated survival checkpoints, the "
                "active probabilities can conceptually be `p`, `p × q`, and `p × q²` over the "
                "frozen three-round horizon. Only initial `p` is `Whole-package control stick %`."
            ),
            "",
            (
                "The later terms affect active exposure, Control Value, and the "
                "`Still controlled after configured repeats %` persistence diagnostic; they do "
                "not redefine initial Reliability as `p × q²`. The evaluator uses each "
                "scenario's actual timing metadata rather than applying this pattern universally. "
                "Other maintained end or escape mechanisms can likewise change CU exposure "
                "without becoming part of initial Reliability."
            ),
        )
    )


def render_reliability_worked_examples() -> str:
    hit = 0.70
    failed_save = 0.60
    one_attempt = hit * failed_save
    retries = _attack_action_retry_probability(3, one_attempt)
    repeat_failure = 0.60
    return "\n".join(
        (
            "### Worked Reliability examples",
            "",
            (
                "**Illustrative hit × save (not current target data):** `P(hit) = 0.70` and "
                "`P(failed save) = 0.60`, so `P(one-attempt control) = 0.70 × 0.60 = "
                f"{one_attempt:.2f} = {100 * one_attempt:.0f}%`."
            ),
            "",
            (
                "**Illustrative identical retries (not current target data):** with "
                f"`p = {one_attempt:.2f}` and `n = 3`, `P(at least one) = 1 - (1 - "
                f"{one_attempt:.2f})^3 = {retries:.6f} = {100 * retries:.2f}%`. Actual KV and "
                "Battle Master retries use exact state recursion when resources or legality change."
            ),
            "",
            (
                "**Illustrative persistence (not current target data):** with initial "
                f"`p = {one_attempt:.2f}` and repeat-save failure `q = {repeat_failure:.2f}`, "
                f"the active windows are `p = {one_attempt:.2f} ({100 * one_attempt:.2f}%)`, "
                f"`p × q = {one_attempt * repeat_failure:.3f} "
                f"({100 * one_attempt * repeat_failure:.2f}%)`, and `p × q² = "
                f"{one_attempt * repeat_failure**2:.4f} "
                f"({100 * one_attempt * repeat_failure**2:.2f}%)`. Only the first `p` is "
                "headline Reliability."
            ),
        )
    )


def render_reliability_recipe_legend() -> str:
    samples = (
        ControlDeliveryRecipe("mastery_attack_action_hit_retry", "hit", "ordinary_attack_action_independent_hits", ""),
        ControlDeliveryRecipe("kv_attack_action_hit_retry", "hit", "kv_attack_action_state_recursion", ""),
        ControlDeliveryRecipe("kv_attack_action_hit_retry", "hit", "kv_attack_action_state_recursion", "constitution", "failed_save"),
        ControlDeliveryRecipe("kv_attack_action_hit_failed_save_retry", "hit_and_failed_save", "kv_attack_action_state_recursion", "constitution"),
        ControlDeliveryRecipe("single_activation_hit", "hit", "single_activation", ""),
        ControlDeliveryRecipe("single_activation_hit", "hit", "single_activation", "constitution", "failed_save"),
        ControlDeliveryRecipe("single_activation_failed_save", "failed_save", "single_activation", "constitution"),
        ControlDeliveryRecipe("single_activation_hit_failed_save", "hit_and_failed_save", "single_activation", "constitution"),
        ControlDeliveryRecipe("single_activation_automatic", "automatic", "single_activation", ""),
        ControlDeliveryRecipe("single_activation_automatic", "automatic", "single_activation", "constitution", "failed_save"),
        ControlDeliveryRecipe("no_modeled_control", "none", "none", ""),
    )
    if {sample.recipe_id for sample in samples} != DELIVERY_RECIPE_IDS:
        raise MatrixSyncError("Delivery recipe legend differs from evaluator recipe inventory")
    return "\n".join(
        (
            "### Catalog delivery recipes",
            "",
            (
                "The generated `Delivery recipe` column is diagnostic metadata from each exact "
                "source's evaluator path. Its initial gate comes from the canonical control "
                "effects applicable to that exact target role: any `on_reach` consequence can "
                "establish initial control, while an optional `on_failed_save` gate identifies "
                "additional control. It never changes scoring or selection, contains no "
                "per-target percentages, and remains present for deliverable `Unpriced` forms. "
                "Structural restrictions and effect immunities change target effectiveness, not "
                "the underlying source recipe. Unknown recipe IDs fail publication closed."
            ),
            "",
            _markdown_table(
                ("Recipe family", "Reader-facing format"),
                tuple(
                    (
                        f"`{sample.recipe_id}`"
                        + (
                            " + `additional_control_gate=failed_save`"
                            if sample.additional_control_gate
                            else ""
                        ),
                        _render_delivery_recipe(sample),
                    )
                    for sample in samples
                ),
            ),
        )
    )


def render_control_reliability_methodology() -> str:
    return "\n\n".join(
        (
            render_reliability_definition(),
            render_probability_grammar(),
            render_attack_action_retry_methodology(),
            render_kv_retry_methodology(),
            render_mastery_and_package_methodology(),
            render_battle_master_retry_methodology(),
            render_eldritch_knight_reliability_methodology(),
            render_persistence_methodology(),
            render_reliability_worked_examples(),
        )
    )


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
    stunned_rows: list[tuple[str, str, str, str, str]] = []
    stunned_total = 0.0
    for label, spec in zip(stunned_labels, stunned_specs, strict=True):
        _, weight = _scoring_rule(
            scoring, spec.primitive_id, "linear_expected_exposure"
        )
        stunned_total += weight
        stunned_rows.append(
            (
                label,
                f"`{spec.exposure_basis}`",
                f"{weight:.2f} CU",
                "1.00",
                f"{weight:.2f} CU",
            )
        )

    stunned_table = _markdown_table(
        ("Priced piece", "Exposure basis", "Nominal weight", "Example exposure", "Contribution"),
        (*stunned_rows, ("**Total**", "", "", "", f"**{stunned_total:.2f} CU**")),
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
                "This is an **opportunity-normalized synthetic example**. It assumes 1.00 expected "
                "exposure independently on every displayed priced basis; it does not treat those "
                "different opportunity types as one shared target-turn window."
            ),
            "",
            stunned_table,
            "",
            (
                "Incapacitated supplies the active-turn and reaction pieces; Stunned adds the two "
                "save automatic failures and incoming attack Advantage. Stunned does **not** gain "
                "Speed 0. Concentration, speech, fall, and other context-sensitive consequences "
                "remain diagnostic rather than receiving invented headline CU. Real Stunned "
                "benchmark rows do **not** automatically equal "
                f"{stunned_total:.2f} CU because target-turn, reaction, save, and incoming-attack "
                "opportunity counts and probabilities can differ."
            ),
            "",
            render_control_primitive_pricing_rubric(scoring),
            "",
            render_movement_methodology(scoring),
            "",
            render_unpriced_primitive_menu(scoring),
            "",
            render_control_normalization_methodology(),
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


def render_control_benchmark_detail(
    reliability_rows: Sequence[MatrixRow],
    value_rows: Sequence[MatrixRow],
    catalog: Sequence[ControlCatalogForm],
    catalog_cells: Mapping[tuple[str, str, int], ControlCatalogCell],
    comparator_cells: Mapping[tuple[str, str, int], ComparatorReferenceCell],
    disciplines: Sequence[str] = README_DISCIPLINES,
) -> str:
    """Render the exhaustive control companion from the validated publication run."""
    levels = tuple(int(value) for value in load_config()["methodology"]["levels"])
    return "\n".join(
        (
            "# Kinetic Vanguard Control Benchmark Detail",
            "",
            (
                "This is the exhaustive public companion to the README control benchmark. "
                "Control Value measures the mechanical consequence of the selected package; "
                "Control Reliability measures initial establishment/delivery of that same "
                "CU-selected package. Damage analysis is outside this page's scope."
            ),
            "",
            "## Current Kinetic Vanguard results",
            "",
            "### Kinetic Vanguard mean Control Value",
            "",
            (
                "This table shows the raw Kinetic Vanguard equal-weight roster mean for the "
                "packages selected by Control Value."
            ),
            "",
            render_raw_kv_value_table(value_rows, disciplines),
            "",
            "### Kinetic Vanguard mean Reliability",
            "",
            (
                "This table shows the raw initial whole-package establishment/delivery "
                "probability for those same CU-selected winners."
            ),
            "",
            render_raw_kv_reliability_table(reliability_rows, disciplines),
            "",
            "## Exact-form catalog and effective coverage",
            "",
            render_kv_control_catalog(catalog, catalog_cells, levels, disciplines),
            "",
            render_reliability_recipe_legend(),
            "",
            render_control_coverage_exceptions(catalog, catalog_cells, levels),
            "",
            render_benchmark_roster_methodology(),
            "",
            render_comparator_reference_scale(comparator_cells,levels),
            "",
            "## Control Reliability methodology",
            "",
            render_control_reliability_methodology(),
            "",
            "## Control Value methodology",
            "",
            render_control_value_explanation(),
            "",
            "## Reproducibility and maintained sources",
            "",
            "- [Kinetic Vanguard rules](KineticVanguard.yaml)",
            "- [Harness methodology](harness/README.md)",
            "- [Benchmark configuration](harness/config/benchmark.json)",
            "- [Control Value scoring configuration](harness/config/control-value.json)",
            "- [Control primitive catalog](harness/data/control_primitives.json)",
            "- [Comparator assumptions](harness/comparators/fighter-subclasses.json)",
            "",
            (
                "Creature benchmark data is SRD 5.2.1. Maintained comparator mechanics are "
                "independently expressed analytical abstractions under the reviewed comparator "
                "source policy; they are not Kinetic Vanguard rules. "
                + COMPARATOR_NOTICE
                + " See [LICENSE.md](LICENSE.md) for component boundaries and "
                "[NOTICE.md](NOTICE.md) for attribution and notices."
            ),
            "",
        )
    )


def render_balance_region(
    readme: str,
    damage_section: str,
    rules_version: str,
    profile: str,
) -> str:
    release_line = release_state_line(readme, rules_version)
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
                "Battle Master and Eldritch Knight define the comparison envelope for the "
                "front-door Single-Target Damage result. `IDEAL` means Kinetic Vanguard "
                "falls between the two comparator values, inclusive. `COLD` is below both; "
                "`HOT` is above both. The percentage on COLD and HOT cells shows the signed "
                "distance outside the nearest comparator boundary. `N/A` is reserved for a "
                "comparison that cannot be evaluated. This is a comparator-envelope benchmark, "
                "not a universal real-play balance tolerance, and `IDEAL` is not proof of "
                "balance in every game."
            ),
            "",
            (
                "Front-door damage comparator-table cells contain only the public balance "
                "classification: `IDEAL`, `COLD (-X%)`, `HOT (+X%)`, or `N/A`. "
                "Detailed damage evidence retains raw Kinetic Vanguard and comparator "
                "aggregates, dynamic boundaries, and the comparator identity supplying each "
                "boundary."
            ),
            "",
        )
    )
    control_pointer = "\n".join(
        (
            "### Control benchmark",
            "",
            (
                "Control Value and Control Reliability require more context than the front-door "
                "damage check. The exhaustive exact-form results, effective coverage, Control "
                "Unit methodology, and Reliability analysis are maintained in:"
            ),
            "",
            (
                "[Full control benchmark, catalog, and methodology]"
                "(CONTROL_BENCHMARK_DETAIL.md)"
            ),
            "",
            END_MARKER,
        )
    )
    return common + "\n" + damage_section + control_pointer


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
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
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
        read_matrix_rows(control["value_paths"]["comparator_reference"]),
    )


def generate_control_publication_rows(
) -> tuple[list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow], list[MatrixRow]]:
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
            comparator_reference_rows,
        ) = _control_publication_rows(root / "control", levels)
        return (
            read_matrix_rows(damage["paths"]["csv"]),
            reliability_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
            comparator_reference_rows,
        )


def stale_control_publication_paths(
    readme: str,
    synchronized_readme: str,
    detail: str | None,
    synchronized_detail: str,
) -> tuple[str, ...]:
    stale = []
    if synchronized_readme != readme:
        stale.append("README.md")
    if synchronized_detail != detail:
        stale.append("CONTROL_BENCHMARK_DETAIL.md")
    return tuple(stale)


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
    detail = (
        CONTROL_DETAIL_PATH.read_text(encoding="utf-8")
        if CONTROL_DETAIL_PATH.exists()
        else None
    )
    generated_region_span(readme)
    if args.control_only:
        damage_section = extract_damage_section(readme)
        reliability_rows, value_rows, value_audit_rows, value_scenario_rows, comparator_reference_rows = (
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
            comparator_reference_rows,
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
    comparator_cells = validate_comparator_reference_scenarios(
        comparator_reference_rows,
        tuple(int(value) for value in load_config()["methodology"]["levels"]),
    )
    region = render_balance_region(
        readme,
        damage_section,
        rules_version,
        profile,
    )
    synchronized = replace_generated_region(readme, region)
    synchronized_detail = render_control_benchmark_detail(
        reliability_public_rows,
        value_public_rows,
        catalog,
        catalog_cells,
        comparator_cells,
        disciplines,
    )
    if README_PATH.read_text(encoding="utf-8") != readme:
        raise MatrixSyncError("README changed during analytical evaluation; retry synchronization")
    current_detail = (
        CONTROL_DETAIL_PATH.read_text(encoding="utf-8")
        if CONTROL_DETAIL_PATH.exists()
        else None
    )
    if current_detail != detail:
        raise MatrixSyncError(
            "CONTROL_BENCHMARK_DETAIL.md changed during analytical evaluation; "
            "retry synchronization"
        )

    if args.check:
        stale = stale_control_publication_paths(
            readme, synchronized, detail, synchronized_detail
        )
        if stale:
            command = (
                "npm run readme:control"
                if args.control_only
                else "npm run readme:benchmarks"
            )
            raise SystemExit(
                f"Control publication is stale ({', '.join(stale)}); run {command}"
            )
        print(f"Control publication is synchronized for v{rules_version}")
        return

    if synchronized_detail != detail:
        if detail is None:
            atomic_create_text(CONTROL_DETAIL_PATH, synchronized_detail)
        else:
            atomic_replace_text(CONTROL_DETAIL_PATH, detail, synchronized_detail)
        print(f"Updated CONTROL_BENCHMARK_DETAIL.md for v{rules_version}")
    else:
        print(f"CONTROL_BENCHMARK_DETAIL.md was already current for v{rules_version}")
    if synchronized != readme:
        atomic_replace_text(README_PATH, readme, synchronized)
        print(f"Updated README balance benchmark snapshot for v{rules_version}")
    else:
        print(f"README balance benchmark snapshot was already current for v{rules_version}")


if __name__ == "__main__":
    main()
