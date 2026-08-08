"""Typed, fail-closed control-target inputs joined to the frozen SRD roster."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.model import DEFAULT_ROSTER, Target, file_sha256, load_targets

HARNESS_ROOT = Path(__file__).resolve().parent
DEFAULT_CONTROL_SUPPLEMENT = HARNESS_ROOT / "data" / "srd_control_targets.json"
DEFAULT_CONTROL_PROVENANCE = HARNESS_ROOT / "provenance" / "srd-control-targets.json"
SUPPORTED_NONVISUAL_SENSES = ("blindsight", "tremorsense", "truesight")
EXPECTED_SOURCE = {
    "ruleset": "D&D SRD 5.2.1",
    "official_pdf_url": "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",
    "official_pdf_sha256": "8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",
    "pages": 364,
}
EXPECTED_EXTRACTION = {
    "source_location": "Each monster stat block's Speed and Senses lines on the row's source_page",
    "fields": ["walking_speed", "fly_speed", "swim_speed", "climb_speed", "burrow_speed", "hover", "nonvisual_senses"],
    "ordinary_darkvision": "excluded",
    "absence": "explicit_null_movement_modes_and_empty_nonvisual_sense_arrays",
    "inference": "none",
    "sense_limitations": "preserve_official_material_limitation_when_present",
    "modifications": "Selected control-relevant facts, normalized feet to integer fields, lower-cased nonvisual sense names, and represented absence explicitly.",
}


@dataclass(frozen=True)
class ControlMovement:
    walk_ft: int
    fly_ft: int | None
    swim_ft: int | None
    climb_ft: int | None
    burrow_ft: int | None
    hover: bool


@dataclass(frozen=True)
class NonvisualSense:
    sense: str
    range_ft: int
    limitation: str | None


@dataclass(frozen=True)
class ControlTarget(Target):
    movement: ControlMovement
    nonvisual_senses: tuple[NonvisualSense, ...]


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing or unknown:
        raise ValueError(f"{label} keys are invalid; missing={missing}, unknown={unknown}")


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _optional_speed(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _positive_integer(value, label)


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{label} must be a non-empty trimmed string")
    return value


def _movement(value: Any, label: str) -> ControlMovement:
    row = _object(value, label)
    _exact_keys(row, {"walk_ft", "fly_ft", "swim_ft", "climb_ft", "burrow_ft", "hover"}, label)
    walk = _positive_integer(row["walk_ft"], f"{label}.walk_ft")
    fly = _optional_speed(row["fly_ft"], f"{label}.fly_ft")
    swim = _optional_speed(row["swim_ft"], f"{label}.swim_ft")
    climb = _optional_speed(row["climb_ft"], f"{label}.climb_ft")
    burrow = _optional_speed(row["burrow_ft"], f"{label}.burrow_ft")
    hover = row["hover"]
    if not isinstance(hover, bool):
        raise ValueError(f"{label}.hover must be a boolean")
    if hover and fly is None:
        raise ValueError(f"{label}.hover requires a fly speed")
    return ControlMovement(walk, fly, swim, climb, burrow, hover)


def _senses(value: Any, label: str) -> tuple[NonvisualSense, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    senses: list[NonvisualSense] = []
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        row = _object(item, item_label)
        _exact_keys(row, {"sense", "range_ft", "limitation"}, item_label)
        sense = _nonempty_string(row["sense"], f"{item_label}.sense")
        if sense not in SUPPORTED_NONVISUAL_SENSES:
            raise ValueError(f"{item_label}.sense is unknown or is not a supported nonvisual sense: {sense}")
        range_ft = _positive_integer(row["range_ft"], f"{item_label}.range_ft")
        limitation = row["limitation"]
        if limitation is not None:
            limitation = _nonempty_string(limitation, f"{item_label}.limitation")
        senses.append(NonvisualSense(sense, range_ft, limitation))
    names = [item.sense for item in senses]
    if len(names) != len(set(names)):
        raise ValueError(f"{label} contains a duplicate sense")
    canonical = sorted(names, key=SUPPORTED_NONVISUAL_SENSES.index)
    if names != canonical:
        raise ValueError(f"{label} must use canonical sense ordering")
    return tuple(senses)


def _supplement_rows(path: Path) -> list[tuple[int, str, ControlMovement, tuple[NonvisualSense, ...], int]]:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    data = _object(data, "control-target supplement")
    _exact_keys(data, {"format_version", "join_key", "targets"}, "control-target supplement")
    if isinstance(data["format_version"], bool) or data["format_version"] != 1:
        raise ValueError("Unsupported control-target supplement format version")
    if data["join_key"] != ["level", "target"]:
        raise ValueError("Control-target supplement join_key must be exact level plus target")
    raw_targets = data["targets"]
    if not isinstance(raw_targets, list):
        raise ValueError("control-target supplement.targets must be an array")
    rows: list[tuple[int, str, ControlMovement, tuple[NonvisualSense, ...], int]] = []
    for index, item in enumerate(raw_targets):
        label = f"control-target supplement.targets[{index}]"
        row = _object(item, label)
        _exact_keys(row, {"level", "target", "movement", "nonvisual_senses", "source_page"}, label)
        level = _positive_integer(row["level"], f"{label}.level")
        target = _nonempty_string(row["target"], f"{label}.target")
        movement = _movement(row["movement"], f"{label}.movement")
        senses = _senses(row["nonvisual_senses"], f"{label}.nonvisual_senses")
        source_page = _positive_integer(row["source_page"], f"{label}.source_page")
        rows.append((level, target, movement, senses, source_page))
    return rows


def _validate_provenance(path: Path, roster_path: Path, supplement_path: Path) -> None:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    data = _object(data, "control-target provenance")
    _exact_keys(
        data,
        {"format_version", "source", "data_file", "data_sha256", "roster_file", "roster_sha256", "join", "extraction"},
        "control-target provenance",
    )
    if isinstance(data["format_version"], bool) or data["format_version"] != 1:
        raise ValueError("Unsupported control-target provenance format version")
    source = _object(data["source"], "control-target provenance.source")
    _exact_keys(source, set(EXPECTED_SOURCE), "control-target provenance.source")
    if source != EXPECTED_SOURCE:
        raise ValueError("Control-target provenance does not identify the pinned official SRD 5.2.1 PDF")
    if data["data_file"] != "harness/data/srd_control_targets.json" or data["roster_file"] != "harness/data/srd_targets.csv":
        raise ValueError("Control-target provenance file identities are unsupported")
    if data["data_sha256"] != file_sha256(supplement_path):
        raise ValueError("Control-target supplement SHA-256 does not match provenance")
    if data["roster_sha256"] != file_sha256(roster_path):
        raise ValueError("SRD target roster SHA-256 does not match control-target provenance")
    join = _object(data["join"], "control-target provenance.join")
    expected_join = {
        "base_fields": ["Level", "Target"],
        "supplement_fields": ["level", "target"],
        "match": "exact_case_sensitive",
        "expected_rows": 28,
    }
    _exact_keys(join, set(expected_join), "control-target provenance.join")
    if join != expected_join:
        raise ValueError("Control-target provenance join contract is unsupported")
    extraction = _object(data["extraction"], "control-target provenance.extraction")
    _exact_keys(extraction, set(EXPECTED_EXTRACTION), "control-target provenance.extraction")
    if extraction != EXPECTED_EXTRACTION:
        raise ValueError("Control-target provenance extraction policy is unsupported")


def load_control_targets(
    roster_path: Path = DEFAULT_ROSTER,
    supplement_path: Path = DEFAULT_CONTROL_SUPPLEMENT,
    provenance_path: Path = DEFAULT_CONTROL_PROVENANCE,
) -> list[ControlTarget]:
    """Load the complete base roster plus control-only facts, rejecting any drift."""

    base_targets = load_targets(roster_path)
    base_keys = [(target.level, target.name) for target in base_targets]
    if len(base_keys) != len(set(base_keys)):
        raise ValueError("Pinned SRD target roster contains a duplicate Level plus Target key")

    supplements = _supplement_rows(supplement_path)
    supplement_keys = [(level, target) for level, target, _, _, _ in supplements]
    if len(supplement_keys) != len(set(supplement_keys)):
        raise ValueError("Control-target supplement contains a duplicate level plus target key")
    missing = sorted(set(base_keys) - set(supplement_keys))
    extra = sorted(set(supplement_keys) - set(base_keys))
    if missing or extra:
        raise ValueError(f"Control-target supplement join is incomplete; missing={missing}, extra={extra}")
    if supplement_keys != base_keys:
        raise ValueError("Control-target supplement rows must follow the exact pinned roster order")

    combined: list[ControlTarget] = []
    target_fields = tuple(Target.__dataclass_fields__)
    for base, (_, _, movement, senses, source_page) in zip(base_targets, supplements, strict=True):
        if str(source_page) != base.source_page:
            raise ValueError(f"Control-target source_page disagrees with the roster for {(base.level, base.name)}")
        inherited = {name: getattr(base, name) for name in target_fields}
        combined.append(ControlTarget(**inherited, movement=movement, nonvisual_senses=senses))

    _validate_provenance(provenance_path, roster_path, supplement_path)
    return combined


if __name__ == "__main__":
    targets = load_control_targets()
    print(f"Validated {len(targets)} exact SRD control-target joins.")
