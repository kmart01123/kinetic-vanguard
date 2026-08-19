"""Pure Slice-1 control primitive decomposition, exposure, and normalization.

This module intentionally contains no weights, scenario selection, mutable combat
state, or timeline machinery. Control Reliability remains the delivery layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_PRIMITIVES = Path(__file__).resolve().parent / "data" / "control_primitives.json"
_STATUS_ORDER = {"candidate": 0, "context_required": 1, "unsupported": 2}


@dataclass(frozen=True)
class PrimitiveSpec:
    primitive_id: str
    exposure_basis: str
    magnitude: float | None
    pricing_status: str
    reason: str
    qualifiers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PrimitiveExposure:
    source_effect: str
    source_label: str
    primitive_id: str
    exposure_basis: str
    magnitude: float | None
    application_probability: float
    active_probabilities: tuple[float, ...]
    expected_exposure: float | None
    pricing_status: str
    reason: str
    qualifiers: tuple[tuple[str, str], ...] = ()
    overlapping_attack_impairment_sources: tuple[str, ...] = ()
    disjoint_stage_group: str = ""
    normalization_disposition: str = "retained"
    suppressed_by: str = ""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


@lru_cache(maxsize=None)
def load_primitive_catalog(path: str | Path = DEFAULT_PRIMITIVES) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        data = _object(json.load(stream), "control primitive catalog")
    if data.get("format_version") != 1:
        raise ValueError("Unsupported control primitive catalog format version")
    source = _object(data.get("source"), "control primitive source")
    if set(source) != {"condition_definitions", "analytical_primitives", "comparator_packages", "note"}:
        raise ValueError("Control primitive source scopes are incomplete")
    conditions_source = _object(source["condition_definitions"], "condition definition source")
    if conditions_source != {
        "ruleset": "SRD 5.2.1",
        "pdf_sha256": "8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2.1/SRD_CC_v5.2.1.pdf",
    }:
        raise ValueError("Condition definitions must remain pinned to SRD 5.2.1")
    if source["analytical_primitives"] != "project-authored generic benchmark semantics" or source["comparator_packages"] != "independently expressed mechanical abstractions from sanitized GitHub rulings":
        raise ValueError("Control primitive source scopes are invalid")
    statuses = data.get("pricing_statuses")
    if statuses != ["candidate", "context_required", "unsupported"]:
        raise ValueError("Unsupported control primitive pricing statuses")
    bases = data.get("exposure_bases")
    if not isinstance(bases, list) or len(bases) != len(set(bases)):
        raise ValueError("Control primitive exposure bases must be unique")
    rows = data.get("primitives")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Control primitive catalog must define primitives")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise ValueError("Control primitive IDs must be unique")
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        if row.get("exposure_basis") not in bases or row.get("default_status") not in statuses:
            raise ValueError(f"Invalid primitive contract for {row.get('id')}")
    for group_name in ("conditions", "outcomes"):
        group = _object(data.get(group_name), group_name)
        for label, definition in group.items():
            definition = _object(definition, f"{group_name}.{label}")
            references: list[str] = []
            if group_name == "conditions":
                references.extend(item.get("id") for item in definition.get("primitives", []) if isinstance(item, dict))
            else:
                if "primitive" in definition:
                    references.append(definition["primitive"])
                references.extend(_object(definition.get("primitive_by_attack_scope", {}), f"outcomes.{label}.primitive_by_attack_scope").values())
            unknown = sorted({item for item in references if item not in by_id})
            if unknown:
                raise ValueError(f"{group_name}.{label} references unknown primitives: {', '.join(unknown)}")
            if group_name == "conditions":
                included_unknown = sorted(set(definition.get("includes", [])) - set(group))
                if included_unknown:
                    raise ValueError(f"conditions.{label} includes unknown conditions: {', '.join(included_unknown)}")
    return data


def _qualifiers(value: Mapping[str, Any] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(item)) for key, item in (value or {}).items()))


def _primitive_contract(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["id"]): row for row in catalog["primitives"]}


def decompose_label(
    label: str,
    *,
    magnitude_feet: float | None = None,
    magnitude: float | None = None,
    attack_scope: str | None = None,
    pricing_status: str | None = None,
    qualifiers: Mapping[str, Any] | None = None,
    path: str | Path = DEFAULT_PRIMITIVES,
) -> tuple[PrimitiveSpec, ...]:
    """Expand one canonical condition/outcome label into inspectable primitives."""
    catalog = load_primitive_catalog(path)
    contracts = _primitive_contract(catalog)
    normalized = label.strip().lower().replace(" ", "_")
    normalized = {"speed_0": "speed_zero"}.get(normalized, normalized)
    specs: list[PrimitiveSpec] = []

    if magnitude_feet is not None and magnitude is not None:
        raise ValueError("A control label cannot declare both feet and generic magnitude")

    def add(primitive_id: str, status: str | None, item_qualifiers: Mapping[str, Any] | None, item_magnitude: float | None, reason: str = "") -> None:
        contract = contracts[primitive_id]
        resolved_status = pricing_status or status or str(contract["default_status"])
        if resolved_status not in _STATUS_ORDER:
            raise ValueError(f"Unsupported pricing status: {resolved_status}")
        merged_qualifiers = {**(item_qualifiers or {}), **(qualifiers or {})}
        specs.append(
            PrimitiveSpec(
                primitive_id=primitive_id,
                exposure_basis=str(contract["exposure_basis"]),
                magnitude=item_magnitude,
                pricing_status=resolved_status,
                reason=reason or str(contract["reason"]),
                qualifiers=_qualifiers(merged_qualifiers),
            )
        )

    def condition(condition_id: str, ancestors: tuple[str, ...] = ()) -> None:
        if condition_id in ancestors:
            raise ValueError(f"Condition inclusion cycle: {' -> '.join((*ancestors, condition_id))}")
        definition = catalog["conditions"].get(condition_id)
        if definition is None:
            raise ValueError(f"Unknown control condition: {condition_id}")
        for included in definition.get("includes", []):
            condition(str(included), (*ancestors, condition_id))
        for item in definition.get("primitives", []):
            primitive_id=str(item["id"]);contract=contracts[primitive_id];add(primitive_id,item.get("status"),item.get("qualifiers"),None,f"SRD 5.2.1 p. {definition['source_page']}. {contract['reason']}")

    if normalized in catalog["conditions"]:
        condition(normalized)
    elif normalized in catalog["outcomes"]:
        definition = catalog["outcomes"][normalized]
        if "primitive_by_attack_scope" in definition:
            primitive_id = definition["primitive_by_attack_scope"].get(attack_scope)
            if primitive_id is None:
                primitive_id = definition["primitive_by_attack_scope"]["all_attacks"]
                add(
                    primitive_id,
                    "unsupported",
                    {"attack_scope": attack_scope or "missing"},
                    None,
                    "Attack-disadvantage scope is absent from the maintained source projection.",
                )
            else:
                add(primitive_id, None, {"attack_scope": attack_scope}, None)
        else:
            resolved_magnitude = float(magnitude_feet if magnitude_feet is not None else magnitude) if magnitude_feet is not None or magnitude is not None else None
            status = None
            reason = ""
            if definition.get("requires_magnitude_feet") and magnitude_feet is None:
                status = "unsupported"
                reason = f"{normalized} lacks a trustworthy feet magnitude in the maintained source."
            if definition.get("requires_magnitude") and resolved_magnitude is None:
                status = "unsupported"
                reason = f"{normalized} lacks a trustworthy magnitude in the maintained source."
            add(str(definition["primitive"]), status, definition.get("qualifiers"), resolved_magnitude, reason)
    else:
        raise ValueError(f"Unknown control condition/outcome: {label}")
    deduplicated: list[PrimitiveSpec] = []
    seen: set[tuple[Any, ...]] = set()
    for spec in specs:
        key=(spec.primitive_id,spec.exposure_basis,spec.magnitude,spec.pricing_status,spec.qualifiers)
        if key not in seen:seen.add(key);deduplicated.append(spec)
    unconditional={spec.primitive_id for spec in deduplicated if not spec.qualifiers}
    return tuple(spec for spec in deduplicated if not spec.qualifiers or spec.primitive_id not in unconditional)


def fixed_exposure(application_probability: float, windows: int) -> tuple[float, ...]:
    if not 0.0 <= application_probability <= 1.0 or windows < 0:
        raise ValueError("Fixed exposure requires a probability in [0, 1] and non-negative windows")
    return (application_probability,) * windows


def repeat_save_exposure(
    application_probability: float,
    survival_probability: float,
    windows: int,
    *,
    checkpoint_side: str,
) -> tuple[float, ...]:
    """Expose windows on an explicit side of the repeat-save checkpoint.

    ``before_scored_window`` means the repeat save occurs before each scored
    window, so window 1 is p*q. ``after_scored_window`` means the first scored
    window precedes its repeat save, so window 1 is p.
    """
    if not 0.0 <= application_probability <= 1.0 or not 0.0 <= survival_probability <= 1.0 or windows < 0:
        raise ValueError("Repeat-save exposure requires probabilities in [0, 1] and non-negative windows")
    if checkpoint_side not in {"before_scored_window", "after_scored_window"}:
        raise ValueError(f"Unsupported repeat-save checkpoint side: {checkpoint_side}")
    first_exponent = 1 if checkpoint_side == "before_scored_window" else 0
    return tuple(application_probability * survival_probability ** (index + first_exponent) for index in range(windows))


def instantaneous_exposure(application_probability: float, magnitude: float) -> float:
    if not 0.0 <= application_probability <= 1.0 or magnitude < 0:
        raise ValueError("Instantaneous exposure requires a probability in [0, 1] and non-negative magnitude")
    return application_probability * magnitude


def expose_label(
    source_effect: str,
    label: str,
    application_probability: float,
    duration: str | None,
    *,
    horizon: int = 3,
    repeat_survival_probability: float | None = None,
    repeat_checkpoint: str | None = None,
    magnitude_feet: float | None = None,
    magnitude: float | None = None,
    attack_scope: str | None = None,
    pricing_status: str | None = None,
    qualifiers: Mapping[str, Any] | None = None,
    overlapping_attack_impairment_sources: Sequence[str] = (),
    active_probabilities_by_basis: Mapping[str, Sequence[float]] | None = None,
    suppressed_recovery_options: Sequence[str] = (),
    disjoint_stage_group: str = "",
    source_reason: str = "",
) -> tuple[PrimitiveExposure, ...]:
    if not 0.0 <= application_probability <= 1.0:
        raise ValueError("Application probability must be between zero and one")
    if horizon < 1:
        raise ValueError("Exposure horizon must be positive")
    specs = decompose_label(
        label,
        magnitude_feet=magnitude_feet,
        magnitude=magnitude,
        attack_scope=attack_scope,
        pricing_status=pricing_status,
        qualifiers=qualifiers,
    )
    suppressed_recoveries = frozenset(str(item) for item in suppressed_recovery_options)
    if "end_own_prone" in suppressed_recoveries:
        specs = tuple(spec for spec in specs if spec.primitive_id != "standing_movement_cost")
    attack_overlap_sources = tuple(sorted(set(overlapping_attack_impairment_sources)))
    result: list[PrimitiveExposure] = []
    for spec in specs:
        status = spec.pricing_status
        reason_parts = [part for part in (source_reason, spec.reason) if part]
        active: tuple[float, ...]
        expected: float | None
        if active_probabilities_by_basis is not None:
            staged=active_probabilities_by_basis.get(spec.exposure_basis)
            if staged is None:
                active=()
                expected=None
                status="context_required" if status!="unsupported" else status
                reason_parts.append("This exposure basis has no approved placement in the closed-form staged package.")
            else:
                active=tuple(float(value) for value in staged)
                if len(active)!=horizon or any(value<0.0 or value>1.0 for value in active):raise ValueError("Staged exposure probabilities must cover the horizon with values in [0, 1]")
                expected=sum(active)*(spec.magnitude if spec.magnitude is not None else 1.0) if status!="unsupported" else None
                reason_parts.append("Closed-form staged target-turn exposure; no mutable timeline is used.")
        elif duration is None:
            active = ()
            expected = None
            status = "unsupported"
            reason_parts.append("Exposure timing is absent from the maintained source.")
        elif duration == "while_in_area":
            active = ()
            expected = None
            status = "context_required"
            reason_parts.append("Area occupancy over future windows is not established by the lean analytical model.")
        elif spec.exposure_basis == "instantaneous_occurrence":
            if duration != "instantaneous" and spec.primitive_id == "forced_displacement":
                active = ()
                expected = None
                status = "context_required" if status != "unsupported" else status
                reason_parts.append("The occurrence cadence is not established without additional context.")
            elif spec.magnitude is None:
                active = (application_probability,)
                expected = application_probability
            else:
                active = (application_probability,)
                expected = instantaneous_exposure(application_probability, spec.magnitude)
        else:
            if duration in {"until_end_current_turn", "until_start_next_turn", "until_end_next_turn"}:
                active = fixed_exposure(application_probability, 1)
            elif duration in {"one_minute", "one_minute_concentration", "ten_minutes_concentration", "one_hour", "one_hour_concentration", "eight_hours"}:
                if repeat_survival_probability is None:
                    active = fixed_exposure(application_probability, horizon)
                elif repeat_checkpoint == "start_of_affected_turn" and spec.exposure_basis == "target_turn_window":
                    active = repeat_save_exposure(
                        application_probability,
                        repeat_survival_probability,
                        horizon,
                        checkpoint_side="before_scored_window",
                    )
                    reason_parts.append("The start-of-affected-turn repeat save precedes each scored target-turn window; window 1 is p*q.")
                elif repeat_checkpoint == "start_of_affected_turn":
                    active = ()
                    expected = None
                    status = "context_required" if status != "unsupported" else status
                    reason_parts.append("This exposure basis has no established side of the start-of-affected-turn repeat-save checkpoint.")
                    result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
                    continue
                elif repeat_checkpoint == "end_of_affected_turn" and spec.exposure_basis == "target_turn_window":
                    active = repeat_save_exposure(
                        application_probability,
                        repeat_survival_probability,
                        horizon,
                        checkpoint_side="after_scored_window",
                    )
                    reason_parts.append("The end-of-affected-turn repeat save follows each scored target-turn window; window 1 is p.")
                elif repeat_checkpoint == "end_of_affected_turn":
                    active = ()
                    expected = None
                    status = "context_required" if status != "unsupported" else status
                    reason_parts.append("This exposure basis has no established side of the end-of-affected-turn repeat-save checkpoint.")
                    result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
                    continue
                else:
                    active = ()
                    expected = None
                    status = "context_required" if status != "unsupported" else status
                    reason_parts.append("Repeat-save exposure lacks a supported checkpoint convention.")
                    result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
                    continue
            elif duration == "instantaneous":
                active = ()
                expected = None
                status = "context_required" if status != "unsupported" else status
                reason_parts.append("A persistent condition created instantaneously needs explicit end timing.")
                result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
                continue
            else:
                active = ()
                expected = None
                status = "unsupported"
                reason_parts.append(f"Unsupported exposure duration: {duration}.")
                result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
                continue
            scale = spec.magnitude if spec.magnitude is not None else 1.0
            expected = sum(active) * scale if status != "unsupported" else None
        if status == "unsupported":
            expected = None
        result.append(PrimitiveExposure(source_effect, label, spec.primitive_id, spec.exposure_basis, spec.magnitude, application_probability, active, expected, status, " ".join(reason_parts), spec.qualifiers, attack_overlap_sources, disjoint_stage_group))
    return tuple(result)


def _expected(active: Sequence[float], magnitude: float | None, status: str) -> float | None:
    if status == "unsupported" or not active:
        return None
    return sum(active) * (magnitude if magnitude is not None else 1.0)


def _qualifier(exposure: PrimitiveExposure, name: str) -> str | None:
    return dict(exposure.qualifiers).get(name)


def _subtract(weaker: PrimitiveExposure, stronger: PrimitiveExposure, rule: str) -> PrimitiveExposure:
    if not weaker.active_probabilities or len(weaker.active_probabilities) != len(stronger.active_probabilities):
        return weaker
    residual = tuple(max(0.0, weak - strong) for weak, strong in zip(weaker.active_probabilities, stronger.active_probabilities))
    if residual == weaker.active_probabilities:
        return weaker
    disposition = "suppressed" if not any(residual) else "partially_suppressed"
    return replace(
        weaker,
        active_probabilities=residual,
        expected_exposure=_expected(residual, weaker.magnitude, weaker.pricing_status),
        normalization_disposition=disposition,
        suppressed_by=f"{stronger.source_effect}:{stronger.primitive_id} ({rule})",
    )


def normalize_exposures(exposures: Iterable[PrimitiveExposure]) -> tuple[PrimitiveExposure, ...]:
    """Apply deterministic primitive-level duplicate and dominance rules."""
    ordered = sorted(
        exposures,
        key=lambda item: (
            item.primitive_id,
            item.exposure_basis,
            item.qualifiers,
            item.magnitude if item.magnitude is not None else -1.0,
            _STATUS_ORDER[item.pricing_status],
            tuple(-value for value in item.active_probabilities),
            item.source_effect,
            item.source_label,
        ),
    )
    normalized: list[PrimitiveExposure] = []
    retained_by_key: dict[tuple[Any, ...], PrimitiveExposure] = {}
    retained_index_by_key: dict[tuple[Any, ...], int] = {}
    for item in ordered:
        key = (item.primitive_id, item.exposure_basis, item.qualifiers, item.magnitude)
        if item.primitive_id == "mobility_loss_feet" and _qualifier(item, "mobility_effect") == "flat_reduction":
            key = (*key, item.source_effect)
        retained = retained_by_key.get(key)
        if retained is None:
            retained_by_key[key] = item
            retained_index_by_key[key]=len(normalized)
            normalized.append(item)
        elif item.disjoint_stage_group and item.disjoint_stage_group==retained.disjoint_stage_group and item.active_probabilities and len(item.active_probabilities)==len(retained.active_probabilities):
            combined_active=tuple(left+right for left,right in zip(retained.active_probabilities,item.active_probabilities))
            if any(value>1.0+1e-12 for value in combined_active):raise ValueError("Disjoint staged exposure exceeds probability 1")
            combined=replace(retained,active_probabilities=combined_active,expected_exposure=_expected(combined_active,retained.magnitude,retained.pricing_status),normalization_disposition="combined_disjoint_stages",suppressed_by=f"{item.source_effect}:{item.primitive_id} (disjoint sequential stage)")
            normalized[retained_index_by_key[key]]=combined;retained_by_key[key]=combined
            zeroes=tuple(0.0 for _ in item.active_probabilities);normalized.append(replace(item,active_probabilities=zeroes,expected_exposure=_expected(zeroes,item.magnitude,item.pricing_status),normalization_disposition="combined_into_disjoint_stages",suppressed_by=f"{combined.source_effect}:{combined.primitive_id} (disjoint sequential stage)"))
        else:
            zeroes=tuple(0.0 for _ in item.active_probabilities);normalized.append(replace(item, active_probabilities=zeroes, expected_exposure=_expected(zeroes,item.magnitude,item.pricing_status), normalization_disposition="suppressed", suppressed_by=f"{retained.source_effect}:{retained.primitive_id} (duplicate primitive)"))

    def retained(predicate: Any) -> list[PrimitiveExposure]:
        return [item for item in normalized if item.normalization_disposition != "suppressed" and predicate(item)]

    denials = retained(lambda item: item.primitive_id == "active_turn_denial")
    specified_actions = retained(lambda item: item.primitive_id == "specified_action_requirement")
    effective_specified_actions: list[PrimitiveExposure] = []
    for action in specified_actions:
        effective = action
        for denial in denials:
            if effective.exposure_basis == denial.exposure_basis == "target_turn_window":
                effective = _subtract(effective, denial, "turn denial dominates a specified Action requirement")
        effective_specified_actions.append(effective)
    all_attack_impairments = retained(lambda item: item.primitive_id == "offensive_impairment_all_attacks")
    auto_failures = retained(lambda item: item.primitive_id == "save_auto_failure")
    speed_zeroes = retained(lambda item: item.primitive_id == "mobility_loss_feet" and _qualifier(item, "mobility_effect") == "speed_zero")
    revised: list[PrimitiveExposure] = []
    for item in normalized:
        current = item
        if current.normalization_disposition != "suppressed" and current.primitive_id == "bonus_action_denial":
            for stronger in denials:
                current = _subtract(current, stronger, "turn denial includes and dominates Bonus Action denial")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "specified_action_requirement":
            for stronger in denials:
                if current.exposure_basis == stronger.exposure_basis == "target_turn_window":
                    current = _subtract(current, stronger, "turn denial dominates a specified Action requirement")
        if current.normalization_disposition != "suppressed" and current.primitive_id in {"offensive_impairment_next_attack", "offensive_impairment_all_attacks"}:
            for stronger in denials:
                current = _subtract(current, stronger, "turn denial dominates offensive impairment")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "offensive_impairment_all_attacks":
            for stronger in effective_specified_actions:
                if current.exposure_basis == stronger.exposure_basis == "target_turn_window":
                    current = _subtract(current, stronger, "specified Action requirement consumes the overlapping attack opportunity")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "offensive_impairment_next_attack":
            for stronger in all_attack_impairments:
                if current.source_effect in stronger.overlapping_attack_impairment_sources:
                    current = _subtract(current, stronger, "all-attacks impairment dominates overlapping next-attack impairment")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "save_disadvantage":
            ability = _qualifier(current, "save_ability")
            for stronger in auto_failures:
                if _qualifier(stronger, "save_ability") == ability:
                    current = _subtract(current, stronger, "automatic failure dominates Disadvantage")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "mobility_loss_feet" and _qualifier(current, "mobility_effect") == "flat_reduction":
            for stronger in speed_zeroes:
                current = _subtract(current, stronger, "Speed 0 dominates lesser reduction")
        if current.normalization_disposition != "suppressed" and current.primitive_id == "standing_movement_cost":
            for stronger in speed_zeroes:
                if current.exposure_basis == stronger.exposure_basis == "target_turn_window":
                    current = _subtract(current, stronger, "Speed 0 makes standing recovery unavailable")
        revised.append(current)
    visible = (item for item in revised if item.primitive_id != "standing_movement_cost" or item.normalization_disposition != "suppressed")
    return tuple(sorted(visible, key=lambda item: (item.primitive_id, item.source_effect, item.source_label, item.magnitude or 0.0, item.qualifiers)))


def shadow_rows(metadata: Mapping[str, Any], components: Iterable[Mapping[str, Any]], *, horizon: int = 3) -> list[dict[str, Any]]:
    """Convert delivery-layer components into deterministic normalized shadow rows."""
    exposures: list[PrimitiveExposure] = []
    for component in components:
        labels = component.get("labels", ())
        for kind, label in labels:
            exposures.extend(
                expose_label(
                    str(component["source_effect"]),
                    str(label),
                    float(component["application_probability"]),
                    component.get("duration"),
                    horizon=horizon,
                    repeat_survival_probability=component.get("repeat_survival_probability"),
                    repeat_checkpoint=component.get("repeat_checkpoint"),
                    magnitude_feet=component.get("magnitude_feet"),
                    magnitude=component.get("magnitude"),
                    attack_scope=component.get("attack_scope"),
                    pricing_status=component.get("pricing_status"),
                    qualifiers=component.get("qualifiers"),
                    overlapping_attack_impairment_sources=component.get("overlapping_attack_impairment_sources", ()),
                    active_probabilities_by_basis=component.get("active_probabilities_by_basis"),
                    suppressed_recovery_options=component.get("suppressed_recovery_options", ()),
                    disjoint_stage_group=str(component.get("disjoint_stage_group", "")),
                    source_reason=str(component.get("reason", "")),
                )
            )
    rows: list[dict[str, Any]] = []
    for item in normalize_exposures(exposures):
        probability_label="occurrence" if item.exposure_basis=="instantaneous_occurrence" else "window"
        rows.append(
            {
                **metadata,
                "Source Effect": item.source_effect,
                "Condition/Outcome": item.source_label,
                "Mechanical Primitive": item.primitive_id,
                "Exposure Basis": item.exposure_basis,
                "Magnitude": "" if item.magnitude is None else f"{item.magnitude:g}",
                "Qualifiers": ";".join(f"{key}={value}" for key,value in item.qualifiers),
                "Application Probability": f"{item.application_probability:.12f}",
                "Active Probabilities": ";".join(f"{probability_label}_{index}={value:.12f}" for index,value in enumerate(item.active_probabilities,1)),
                "Expected Exposure": "" if item.expected_exposure is None else f"{item.expected_exposure:.12f}",
                "Normalization": item.normalization_disposition,
                "Suppressed By": item.suppressed_by,
                "Pricing Status": item.pricing_status,
                "Source/Reason": item.reason,
            }
        )
    return rows
