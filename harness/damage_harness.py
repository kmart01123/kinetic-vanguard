"""Orchestrate the exact nominal replacement damage model and its reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .authority import DamageAuthorityModel, DEFAULT_AUTHORITY
from .creature_catalog import (
    CONSUMER_REQUIREMENTS_VERSION,
    ROSTER_CONTRACT_VERSION,
    RosterEntry,
    load_catalog,
    load_consumer_requirements,
    load_profile,
)
from .creature_damage_projection import (
    DAMAGE_PROJECTION_ID,
    DAMAGE_PROJECTION_VERSION,
    DamageTarget,
    project_damage_target,
)
from .damage_contract import (
    NOMINAL_MODE_ID,
    NUMERIC_REPRESENTATION_ID,
    PROVIDER_IDS,
    TARGET_KNOWLEDGE_CONTRACT_ID,
    DamageSolution,
    TargetKnowledge,
    canonical_sha256,
    cluster_signature,
    reject_unsupported_mode,
    solve_comparator,
    solve_kinetic_vanguard,
)
from .damage_report import (
    NOTICE_COLUMNS,
    damage_matrix_row,
    display_decimal,
    fraction_text,
    provenance_columns,
    write_damage_matrix,
)
from .model import (
    DEFAULT_COMPARATORS,
    DEFAULT_CONFIG,
    file_sha256,
    load_comparators,
    load_config,
)


DAMAGE_RESULT_CONTRACT_VERSION = "3.0.0"
DAMAGE_EVALUATOR_ID = "exact_analytical_enumeration"
RUN_MANIFEST_FILENAME = "run-manifest.json"
HARNESS_ROOT = Path(__file__).resolve().parent
DAMAGE_SENTINEL_CORPUS = HARNESS_ROOT / "data" / "damage-sentinels-v1.json"
DAMAGE_MODEL_CONTRACT = HARNESS_ROOT / "provenance" / "damage-model-contract.json"
DAMAGE_SEMANTIC_IMPLEMENTATION_PATHS = (
    ("harness/authority.py", HARNESS_ROOT / "authority.py"),
    ("harness/damage_contract.py", HARNESS_ROOT / "damage_contract.py"),
)
DAMAGE_ORCHESTRATION_IMPLEMENTATION_PATHS = (
    ("harness/damage_harness.py", Path(__file__)),
    ("harness/model.py", HARNESS_ROOT / "model.py"),
)
DAMAGE_REPORTER_IMPLEMENTATION_PATHS = (
    ("harness/damage_report.py", HARNESS_ROOT / "damage_report.py"),
)


@dataclass(frozen=True)
class DamageInputBundle:
    model: DamageAuthorityModel
    config: dict[str, Any]
    comparators: dict[str, Any]
    entries: tuple[RosterEntry, ...]
    targets: tuple[DamageTarget, ...]
    identity: dict[str, Any]


def _canonical_sha256(value: Any) -> str:
    return canonical_sha256(value)


def implementation_sha256(paths: tuple[tuple[str, Path], ...]) -> str:
    labels = [label for label, _ in paths]
    if labels != sorted(labels) or len(labels) != len(set(labels)):
        raise ValueError("Damage implementation paths must have unique sorted labels")
    return _canonical_sha256(
        [{"path": label, "sha256": file_sha256(path)} for label, path in paths]
    )


def semantic_implementation_sha256() -> str:
    return implementation_sha256(DAMAGE_SEMANTIC_IMPLEMENTATION_PATHS)


def orchestration_implementation_sha256() -> str:
    return implementation_sha256(DAMAGE_ORCHESTRATION_IMPLEMENTATION_PATHS)


def reporter_implementation_sha256() -> str:
    return implementation_sha256(DAMAGE_REPORTER_IMPLEMENTATION_PATHS)


def sentinel_corpus_sha256() -> str:
    """Return the corpus's canonical JSON identity, independent of whitespace."""

    return _canonical_sha256(json.loads(DAMAGE_SENTINEL_CORPUS.read_text(encoding="utf-8")))


def authority_projection_sha256(model: DamageAuthorityModel) -> str:
    """Bind the canonical projected mechanics without the machine-local source path."""

    return _canonical_sha256(
        {
            key: value
            for key, value in model.projection.items()
            if key != "authority_path"
        }
    )


def _fraction_from_row(row: dict[str, Any], field: str) -> Fraction:
    try:
        return Fraction(str(row[field]))
    except (KeyError, ValueError, ZeroDivisionError) as error:
        raise ValueError(f"Damage row has invalid exact field {field!r}") from error


def _discipline_damage_rows(
    arguments: tuple[
        DamageAuthorityModel,
        dict[str, Any],
        RosterEntry,
        DamageTarget,
        str,
        list[int],
        DamageSolution,
        DamageSolution,
    ]
) -> list[dict[str, Any]]:
    model, config, entry, target, discipline, clusters, ek, bm = arguments
    kv_cache: dict[tuple[tuple[str, int, int], ...], DamageSolution] = {}
    detail: list[dict[str, Any]] = []
    level = entry.benchmark_level
    for cluster in clusters:
        signature = cluster_signature(model, config, discipline, level, int(cluster))
        if signature not in kv_cache:
            kv_cache[signature] = solve_kinetic_vanguard(
                model,
                config,
                target,
                level,
                discipline,
                int(cluster),
            )
        kv = kv_cache[signature]
        detail.append(
            {
                "Level": level,
                "Creature ID": target.creature_id,
                "Target": target.name,
                "Target Profile ID": entry.profile_id,
                "Target Profile SHA-256": entry.profile_sha256,
                "Target Weight Numerator": entry.weight.numerator,
                "Target Weight Denominator": entry.weight.denominator,
                "Discipline": discipline,
                "Cluster Size": cluster,
                "KV Primary DPR": display_decimal(kv.primary_dpr),
                "KV Primary DPR Exact": fraction_text(kv.primary_dpr),
                "KV Aggregate DPR": display_decimal(kv.aggregate_dpr),
                "KV Aggregate DPR Exact": fraction_text(kv.aggregate_dpr),
                "Eldritch Knight DPR": display_decimal(ek.primary_dpr),
                "Eldritch Knight DPR Exact": fraction_text(ek.primary_dpr),
                "Battle Master DPR": display_decimal(bm.primary_dpr),
                "Battle Master DPR Exact": fraction_text(bm.primary_dpr),
                "KV Policy Digest": kv.policy_digest,
                "Eldritch Knight Policy Digest": ek.policy_digest,
                "Battle Master Policy Digest": bm.policy_digest,
                "Selection": kv.selection,
                "Eldritch Knight Trace": ek.selection,
                "Battle Master Trace": bm.selection,
            }
        )
    return detail


def _detail_scope_evidence(row: dict[str, Any]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for prefix, value_field in (
        ("Primary Target", "KV Primary DPR Exact"),
        ("Aggregate Cluster", "KV Aggregate DPR Exact"),
    ):
        scope = damage_matrix_row(
            {},
            _fraction_from_row(row, value_field),
            _fraction_from_row(row, "Eldritch Knight DPR Exact"),
            _fraction_from_row(row, "Battle Master DPR Exact"),
        )
        for field in (
            "KV as % of EK",
            "KV as % of BM",
            "Lower Comparator",
            "Upper Comparator",
            "Lower Boundary",
            "Upper Boundary",
            "Band",
            "Boundary Delta %",
        ):
            evidence[f"{prefix} {field}"] = scope[field]
    return evidence


def _projection_digest(entries: list[RosterEntry], targets: list[DamageTarget]) -> str:
    if not entries or len(entries) != len(targets):
        raise ValueError(
            "Damage target projections must cover a non-empty active roster profile exactly"
        )
    for entry, target in zip(entries, targets, strict=True):
        if entry.creature_id != target.creature_id or entry.catalog_sha256 != target.catalog_sha256:
            raise ValueError("Damage target projections do not match active roster identities")
        target.validate_identity()
        TargetKnowledge.from_damage_target(target)
    return _canonical_sha256(
        {
            "projection_id": DAMAGE_PROJECTION_ID,
            "projection_version": DAMAGE_PROJECTION_VERSION,
            "profile_id": entries[0].profile_id,
            "profile_sha256": entries[0].profile_sha256,
            "targets": [
                {
                    "creature_id": entry.creature_id,
                    "target_sha256": target.target_sha256,
                    "target_knowledge_sha256": TargetKnowledge.from_damage_target(target).digest,
                }
                for entry, target in zip(entries, targets, strict=True)
            ],
        }
    )


def load_damage_input_bundle(
    authority: Path,
    levels: set[int],
    trials: int,
    seed: int,
    *,
    mode_id: str = NOMINAL_MODE_ID,
) -> DamageInputBundle:
    reject_unsupported_mode(mode_id)
    if not levels:
        raise ValueError("At least one benchmark level is required")
    model = DamageAuthorityModel.load(authority)
    config = load_config()
    comparators = load_comparators()
    configured_levels = {int(value) for value in config["methodology"]["levels"]}
    if not levels <= configured_levels:
        raise ValueError("Requested levels are outside the frozen nominal benchmark")
    catalog = load_catalog()
    requirements = load_consumer_requirements(catalog=catalog)
    profile_id = str(config["methodology"]["target_profile_id"])
    entries = load_profile(profile_id, levels, catalog=catalog)
    targets = [
        project_damage_target(
            entry.creature_id,
            catalog=catalog,
            requirements=requirements,
        )
        for entry in entries
    ]
    if any(
        entry.profile_id != entries[0].profile_id
        or entry.profile_sha256 != entries[0].profile_sha256
        or entry.roster_sha256 != entries[0].roster_sha256
        for entry in entries
    ):
        raise ValueError("Active target profile identities are inconsistent")
    projection_sha256 = _projection_digest(entries, targets)
    optimization = config["damage_matrix"]["optimization"]
    semantic_sha256 = semantic_implementation_sha256()
    identity = {
        "damage_result_contract_version": DAMAGE_RESULT_CONTRACT_VERSION,
        "damage_model_mode_id": mode_id,
        "target_knowledge_contract_id": TARGET_KNOWLEDGE_CONTRACT_ID,
        "numeric_representation_id": NUMERIC_REPRESENTATION_ID,
        "provider_ids": ",".join(PROVIDER_IDS),
        "rules_version": model.rules_version,
        "authority_sha256": model.authority_sha256,
        "authority_projection_sha256": authority_projection_sha256(model),
        "catalog_contract_version": targets[0].catalog_contract_version,
        "catalog_sha256": targets[0].catalog_sha256,
        "roster_contract_version": ROSTER_CONTRACT_VERSION,
        "roster_sha256": entries[0].roster_sha256,
        "target_profile_id": entries[0].profile_id,
        "target_profile_version": entries[0].profile_version,
        "target_profile_sha256": entries[0].profile_sha256,
        "damage_target_projection_id": DAMAGE_PROJECTION_ID,
        "damage_target_projection_version": DAMAGE_PROJECTION_VERSION,
        "damage_target_projection_sha256": projection_sha256,
        "consumer_requirements_version": CONSUMER_REQUIREMENTS_VERSION,
        "damage_consumer_requirements_sha256": requirements.sha256_for("damage_target"),
        "config_sha256": file_sha256(DEFAULT_CONFIG),
        "comparator_config_sha256": file_sha256(DEFAULT_COMPARATORS),
        "damage_model_contract_sha256": file_sha256(DAMAGE_MODEL_CONTRACT),
        "sentinel_corpus_sha256": sentinel_corpus_sha256(),
        "sentinel_corpus_file_sha256": file_sha256(DAMAGE_SENTINEL_CORPUS),
        "observation_policy_sha256": _canonical_sha256(
            {
                "contract_id": TARGET_KNOWLEDGE_CONTRACT_ID,
                "decision_timing": optimization["decision_timing"],
            }
        ),
        "resource_policy_sha256": _canonical_sha256(
            optimization["resource_cost_classes"]
        ),
        "optimization_policy_sha256": _canonical_sha256(
            {
                "scope": optimization["scope"],
                "objective": optimization["objective"],
            }
        ),
        "evaluator": DAMAGE_EVALUATOR_ID,
        "evaluator_implementation_sha256": semantic_sha256,
        "semantic_implementation_sha256": semantic_sha256,
        "orchestration_implementation_sha256": orchestration_implementation_sha256(),
        "reporter_implementation_sha256": reporter_implementation_sha256(),
        "trials": trials,
        "seed": seed,
        "trial_seed_role": "historical_compatibility_metadata",
        "aggregation": "exact rational target-profile weights; deterministic half-even display boundary",
        "status": config["methodology"]["status"],
    }
    return DamageInputBundle(
        model,
        config,
        comparators,
        tuple(entries),
        tuple(targets),
        identity,
    )


def _write_run_manifest(
    output_dir: Path,
    inputs: dict[str, Any],
    outputs: dict[str, Path],
    detail_rows: int,
    matrix_rows: int,
) -> Path:
    manifest = {
        "format_version": 2,
        "damage_result_contract_version": DAMAGE_RESULT_CONTRACT_VERSION,
        "inputs": inputs,
        "outputs": {
            name: {"file": path.name, "sha256": file_sha256(path)}
            for name, path in sorted(outputs.items())
        },
        "row_counts": {"detail": detail_rows, "matrix": matrix_rows},
    }
    path = output_dir / RUN_MANIFEST_FILENAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run(
    authority: Path,
    output_dir: Path,
    levels: set[int],
    trials: int,
    seed: int,
    write_detail: bool = True,
    write_headline: bool = True,
    workers: int = 1,
    *,
    mode_id: str = NOMINAL_MODE_ID,
) -> dict[str, Any]:
    reject_unsupported_mode(mode_id)
    inputs = load_damage_input_bundle(
        authority,
        levels,
        trials,
        seed,
        mode_id=mode_id,
    )
    model, config, comparators = inputs.model, inputs.config, inputs.comparators
    entries, targets = list(inputs.entries), list(inputs.targets)
    input_identity = inputs.identity
    clusters = [int(value) for value in config["methodology"]["cluster_sizes"]]
    arguments = []
    for entry, target in zip(entries, targets, strict=True):
        level = entry.benchmark_level
        ek = solve_comparator(
            model,
            config,
            comparators,
            target,
            level,
            "eldritch_knight",
        )
        bm = solve_comparator(
            model,
            config,
            comparators,
            target,
            level,
            "battle_master",
        )
        for discipline in model.disciplines:
            arguments.append(
                (model, config, entry, target, discipline, clusters, ek, bm)
            )
    if workers == 1:
        discipline_rows = map(_discipline_damage_rows, arguments)
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            max_tasks_per_child=1,
        ) as executor:
            discipline_rows = executor.map(_discipline_damage_rows, arguments)
    detail = [
        {**row, **_detail_scope_evidence(row)}
        for rows in discipline_rows
        for row in rows
    ]
    slug = model.rules_version.replace(".", "-")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_columns = {**provenance_columns(input_identity), **NOTICE_COLUMNS}
    output_paths: dict[str, Path] = {}
    if write_detail:
        detail_rows = [{**row, **source_columns} for row in detail]
        detail_path = output_dir / f"kv-{slug}-damage-detail.csv"
        with detail_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(detail_rows[0]))
            writer.writeheader()
            writer.writerows(detail_rows)
        output_paths["detail_csv"] = detail_path
    groups: dict[tuple[int, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in detail:
        groups[(int(row["Level"]), str(row["Discipline"]), int(row["Cluster Size"]))].append(row)
    rows: list[dict[str, str]] = []
    for (level, discipline, cluster), values in sorted(groups.items()):
        weights = [
            Fraction(
                int(item["Target Weight Numerator"]),
                int(item["Target Weight Denominator"]),
            )
            for item in values
        ]
        if sum(weights, Fraction()) != 1:
            raise ValueError(
                f"Active target-profile weights for level {level} do not sum to one"
            )

        def weighted(key: str) -> Fraction:
            return sum(
                (
                    weight * _fraction_from_row(item, key)
                    for weight, item in zip(weights, values, strict=True)
                ),
                Fraction(),
            )

        for scope, field in (
            ("primary-target DPR", "KV Primary DPR Exact"),
            ("aggregate cluster DPR", "KV Aggregate DPR Exact"),
        ):
            rows.append(
                damage_matrix_row(
                    {
                        "Level": level,
                        "Discipline": discipline,
                        "Cluster Size": cluster,
                        "Damage Scope": scope,
                        "Profile": config["kv_profile"]["id"],
                    },
                    weighted(field),
                    weighted("Eldritch Knight DPR Exact"),
                    weighted("Battle Master DPR Exact"),
                )
            )
    if write_headline:
        matrix_paths = write_damage_matrix(
            output_dir,
            model.rules_version,
            rows,
            input_identity,
        )
        output_paths.update(
            {f"matrix_{name}": path for name, path in matrix_paths.items()}
        )
    manifest_path = _write_run_manifest(
        output_dir,
        input_identity,
        output_paths,
        len(detail),
        len(rows),
    )
    output_paths["manifest"] = manifest_path
    return {
        "rules_version": model.rules_version,
        "mode_id": mode_id,
        "detail_rows": len(detail),
        "matrix_rows": len(rows),
        "paths": output_paths,
        "inputs": input_identity,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--levels", default="7,11,15,20")
    parser.add_argument("--trials", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--mode", default=NOMINAL_MODE_ID)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--matrix-only", action="store_true")
    parser.add_argument("--no-matrix", action="store_true")
    args = parser.parse_args()
    reject_unsupported_mode(args.mode)
    model = DamageAuthorityModel.load(args.authority)
    config = load_config()
    if args.validate_only:
        load_comparators()
        catalog = load_catalog()
        requirements = load_consumer_requirements(catalog=catalog)
        entries = load_profile(
            str(config["methodology"]["target_profile_id"]),
            catalog=catalog,
        )
        for entry in entries:
            target = project_damage_target(
                entry.creature_id,
                catalog=catalog,
                requirements=requirements,
            )
            TargetKnowledge.from_damage_target(target)
        print(
            f"Validated Kinetic Vanguard {model.rules_version} authority "
            f"{model.authority_sha256}, catalog {catalog.sha256}, and {len(entries)} "
            f"{TARGET_KNOWLEDGE_CONTRACT_ID} projections for {NOMINAL_MODE_ID}"
        )
        return
    trials = (
        args.trials
        if args.trials is not None
        else int(config["methodology"]["damage_default_trials"])
    )
    seed = (
        args.seed
        if args.seed is not None
        else int(config["methodology"]["damage_seed"])
    )
    levels = {int(value) for value in args.levels.split(",")}
    if trials <= 0 or args.workers <= 0:
        parser.error("--trials and --workers must be positive")
    result = run(
        args.authority,
        args.output_dir,
        levels,
        trials,
        seed,
        not args.matrix_only,
        not args.no_matrix,
        args.workers,
        mode_id=args.mode,
    )
    print(
        f"Damage harness wrote {result['detail_rows']} detail rows and "
        f"{result['matrix_rows']} matrix rows for rules {result['rules_version']} "
        f"under {result['mode_id']}"
    )


if __name__ == "__main__":
    main()
