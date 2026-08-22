from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from harness import readme_matrices
from harness.authority import AuthorityModel, DEFAULT_AUTHORITY
from harness.comparison_report import COMPARATOR_NOTICE, NOTICE_COLUMNS, matrix_row
from harness.control_value import (
    DEFAULT_PRIMITIVES,
    DEFAULT_SCORING,
    decompose_label,
    load_scoring_config,
)
from harness.model import (
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
from harness.readme_matrices import (
    BEGIN_MARKER,
    END_MARKER,
    NO_MODELED_CONTROL,
    PARTIALLY_PRICED,
    PRICED,
    UNAVAILABLE,
    UNPRICED,
    ControlCatalogCell,
    MatrixSyncError,
    README_DISCIPLINES,
    _markdown_table,
    _public_result,
    atomic_replace_text,
    build_kv_control_catalog,
    catalog_rider_scenarios,
    classify_catalog_pricing,
    extract_damage_section,
    generate_control_publication_rows,
    generated_region_span,
    release_state_line,
    render_balance_region,
    render_benchmark_roster_methodology,
    render_control_value_explanation,
    render_control_table,
    render_damage_section,
    render_kv_control_catalog,
    render_raw_kv_reliability_table,
    render_raw_kv_value_table,
    render_single_target_damage,
    replace_generated_region,
    validate_authoritative_rows,
    validate_control_catalog_scenarios,
    validate_damage_rows,
    validate_reliability_alignment,
    validate_reliability_rows,
    validate_value_rows,
)


def _damage_row(
    scope: str,
    cluster: int,
    kv: float,
    eldritch_knight: float,
    battle_master: float,
    *,
    level: int = 7,
    discipline: str = "pyrokinesis",
) -> dict[str, str]:
    return matrix_row(
        {
            "Level": level,
            "Discipline": discipline,
            "Cluster Size": cluster,
            "Damage Scope": scope,
        },
        kv,
        eldritch_knight,
        battle_master,
        "damage",
    )


def _control_row(
    level: int,
    discipline: str,
    kv: float,
    eldritch_knight: float,
    battle_master: float,
) -> dict[str, str]:
    return matrix_row(
        {
            "Level": level,
            "Discipline": discipline,
            "Metric": "synthetic control reliability %",
        },
        kv,
        eldritch_knight,
        battle_master,
        "control",
    )


def _full_authoritative_rows() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    model = AuthorityModel.load(DEFAULT_AUTHORITY)
    config = load_config()
    methodology = config["methodology"]
    profile = str(config["kv_profile"]["id"])
    common = {
        "Provenance Rules Version": model.rules_version,
        "Provenance Authority Sha256": model.authority_sha256,
        "Provenance Catalog Sha256": file_sha256(DEFAULT_CATALOG),
        "Provenance Roster Sha256": file_sha256(DEFAULT_ROSTERS),
        "Provenance Target Profile": DEFAULT_PROFILE,
        "Provenance Config Sha256": file_sha256(DEFAULT_CONFIG),
        "Provenance Comparator Config Sha256": file_sha256(DEFAULT_COMPARATORS),
        "Provenance Evaluator": "exact_analytical_enumeration",
    }

    damage_rows: list[dict[str, str]] = []
    for level in methodology["levels"]:
        for discipline in sorted(model.disciplines):
            for cluster in methodology["cluster_sizes"]:
                for scope in readme_matrices.DAMAGE_SCOPES:
                    row = matrix_row(
                        {
                            "Level": level,
                            "Discipline": discipline,
                            "Cluster Size": cluster,
                            "Damage Scope": scope,
                            "Profile": profile,
                        },
                        15,
                        10,
                        20,
                        "damage",
                    )
                    row.update(
                        {
                            **common,
                            "Provenance Aggregation": (
                                "equal-weight roster means; percentages from displayed aggregates"
                            ),
                            **NOTICE_COLUMNS,
                        }
                    )
                    damage_rows.append(row)

    control_rows: list[dict[str, str]] = []
    for level in methodology["levels"]:
        for discipline in sorted(model.disciplines):
            row = matrix_row(
                {
                    "Level": level,
                    "Discipline": discipline,
                    "Metric": str(config["control_matrix"]["metric"]),
                    "Profile": profile,
                },
                15,
                20,
                10,
                "control",
            )
            row.update(
                {
                    **common,
                    "Provenance Control Primitive Catalog Sha256": file_sha256(
                        DEFAULT_PRIMITIVES
                    ),
                    "Provenance Control Value Config Sha256": file_sha256(
                        DEFAULT_SCORING
                    ),
                    "Provenance Aggregation": str(
                        config["control_matrix"]["aggregation"]
                    ),
                    **NOTICE_COLUMNS,
                }
            )
            control_rows.append(row)
    raw_common = {
        "Rules Version": model.rules_version,
        "Authority SHA-256": model.authority_sha256,
        "Catalog SHA-256": file_sha256(DEFAULT_CATALOG),
        "Roster SHA-256": file_sha256(DEFAULT_ROSTERS),
        "Target Profile": DEFAULT_PROFILE,
        "Config SHA-256": file_sha256(DEFAULT_CONFIG),
        "Comparator Config SHA-256": file_sha256(DEFAULT_COMPARATORS),
        **NOTICE_COLUMNS,
        "Control Primitive Catalog SHA-256": file_sha256(DEFAULT_PRIMITIVES),
        "Control Value Config SHA-256": file_sha256(DEFAULT_SCORING),
    }
    targets = load_targets(profile=DEFAULT_PROFILE, levels=set(methodology["levels"]))
    value_audit_rows: list[dict[str, str]] = []
    for target in targets:
        for build, discipline, value in (
            ("battle_master", "all", 10.0),
            ("eldritch_knight", "all", 20.0),
            *(
                ("kinetic_vanguard", discipline, 15.0)
                for discipline in README_DISCIPLINES
            ),
        ):
            value_audit_rows.append(
                {
                    "Level": str(target.level),
                    "Target": target.name,
                    "Discipline": discipline,
                    "Build": build,
                    "Selected Scenario": "synthetic_winner",
                    "Eligible": "True",
                    "Selection Basis": "Control Value",
                    "Control Value CU": str(value),
                    "Whole-package control stick %": str(value),
                    "Value Disposition": "priced_nonzero",
                    **raw_common,
                }
            )
    value_rows = [
        {
            "Level": str(level),
            "Discipline": discipline,
            "Kinetic Vanguard Control Value CU": "15.000000000000",
            "Eldritch Knight Control Value CU": "20.000000000000",
            "Battle Master Control Value CU": "10.000000000000",
            "Targets": str(PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][level]),
            **raw_common,
        }
        for level in methodology["levels"]
        for discipline in README_DISCIPLINES
    ]
    catalog = build_kv_control_catalog(model)
    value_scenario_rows: list[dict[str, str]] = []
    for target in targets:
        for form in catalog:
            if not form.available(target.level) or not (
                form.is_mastery or form.modeled_control
            ):
                continue
            modeled = form.modeled_control
            value_scenario_rows.append(
                {
                    "Build": "kinetic_vanguard",
                    "Discipline": form.discipline_id,
                    "Level": str(target.level),
                    "Target": target.name,
                    "Scenario": form.scenario_id,
                    "Eligible": "True",
                    "Control Value CU": "1.0" if modeled else "0.0",
                    "Whole-package control stick %": "50.0" if modeled else "0.0",
                    "Value Disposition": (
                        "priced_nonzero" if modeled else "legitimately_priced_zero"
                    ),
                    "Primitive Rows": "1" if modeled else "0",
                    "Candidate Rows": "1" if modeled else "0",
                    "Context/Unsupported Rows": "0",
                    "Retained Candidate Rows": "1" if modeled else "0",
                    "Retained Context/Unsupported Rows": "0",
                    "Zero Entirely Fail-Closed Context": "False",
                    **raw_common,
                }
            )
    return (
        damage_rows,
        control_rows,
        value_rows,
        value_audit_rows,
        value_scenario_rows,
    )


class ReadmeMatrixRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        primary_values = {
            1: ((5,10,20),(15,10,20),(25,10,20),(15,20,10)),
            3: ((15,10,20),(15,10,20),(15,10,20),(15,20,10)),
            6: ((8,10,20),(24,10,20),(10,10,20),(20,20,10)),
        }
        aggregate_values = {
            1: ((31,40,60),(45,40,60),(70,40,60),(50,60,40)),
            3: ((45,40,60),(45,40,60),(45,40,60),(50,60,40)),
            6: ((35,40,60),(66,40,60),(40,40,60),(60,60,40)),
        }
        self.damage_rows = []
        for scope,values_by_cluster in (
            ("primary-target DPR",primary_values),
            ("aggregate cluster DPR",aggregate_values),
        ):
            for cluster,values in values_by_cluster.items():
                for discipline,(kv,ek,bm) in zip(README_DISCIPLINES,values,strict=True):
                    self.damage_rows.append(
                        _damage_row(scope,cluster,kv,ek,bm,discipline=discipline)
                    )
        control_values = {
            7: ((5,10,20),(15,10,20),(25,10,20),(15,20,10)),
            11: ((15,10,20),(15,10,20),(15,10,20),(15,0,10)),
        }
        self.control_rows = [
            _control_row(level,discipline,kv,ek,bm)
            for level,values in control_values.items()
            for discipline,(kv,ek,bm) in zip(README_DISCIPLINES,values,strict=True)
        ]

    def test_single_target_damage_renders_one_public_heat_matrix(self) -> None:
        rendered=render_single_target_damage(list(reversed(self.damage_rows)))
        header="| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |"
        self.assertEqual(rendered.count(header),1)
        self.assertIn(
            "| 7 | COLD (-50.00%) | IDEAL | HOT (+25.00%) | IDEAL |",
            rendered,
        )
        self.assertNotIn("COLD (-22.50%)",rendered)
        for forbidden in ("KV DPR","KV as %","Eldritch Knight DPR","Battle Master DPR","ORDER CHECK","5.000000"):
            self.assertNotIn(forbidden,rendered)

    def test_single_target_damage_requires_primary_cluster_one(self) -> None:
        rows=[
            _damage_row(
                "primary-target DPR",2,15,10,20,discipline=discipline
            )
            for discipline in README_DISCIPLINES
        ]
        with self.assertRaisesRegex(MatrixSyncError,"cluster size 1"):
            render_single_target_damage(rows)

    def test_control_table_is_level_by_discipline_and_public_only(self) -> None:
        rendered=render_control_table(list(reversed(self.control_rows)))
        expected="\n".join(
            (
                "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |",
                "|---|---|---|---|---|",
                "| 7 | COLD (-50.00%) | IDEAL | HOT (+25.00%) | IDEAL |",
                "| 11 | IDEAL | IDEAL | IDEAL | N/A |",
            )
        )
        self.assertEqual(rendered,expected)
        for forbidden in ("KV control","KV as %","Eldritch Knight","Battle Master","ORDER CHECK"):
            self.assertNotIn(forbidden,rendered)
        self.assertNotIn("IDEAL (",rendered)

    def test_public_result_enforces_band_and_delta_contract(self) -> None:
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,15,10,20)),"IDEAL")
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,5,10,20)),"COLD (-50.00%)")
        self.assertEqual(_public_result(_damage_row("primary-target DPR",1,25,10,20)),"HOT (+25.00%)")
        unavailable=_damage_row("primary-target DPR",1,15,0,20)
        self.assertEqual(_public_result(unavailable),"N/A")
        malformed=_damage_row("primary-target DPR",1,5,10,20);malformed["Boundary Delta %"]="+50.00"
        with self.assertRaisesRegex(MatrixSyncError,"incorrectly signed"):
            _public_result(malformed)
        retired=_damage_row("primary-target DPR",1,15,10,20);retired["Band"]="ORDER CHECK"
        with self.assertRaisesRegex(MatrixSyncError,"Unsupported public"):
            _public_result(retired)

    def test_complete_region_is_deterministic_transposed_and_minimal(self) -> None:
        (
            damage_rows,
            control_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
        ) = _full_authoritative_rows()
        value_public_rows=validate_value_rows(value_rows,value_audit_rows)
        catalog = build_kv_control_catalog()
        catalog_cells = validate_control_catalog_scenarios(
            value_scenario_rows,
            catalog,
            tuple(int(value) for value in load_config()["methodology"]["levels"]),
        )
        damage_section=render_damage_section(damage_rows)
        readme="\n".join(
            (
                "# Project",
                "- Current published release: **v14.0.0**",
                "- Current development line: **v14.1.0**",
            )
        )
        arguments=(
            readme,damage_section,control_rows,value_public_rows,catalog,catalog_cells,
            "14.1.0",DEFAULT_PROFILE,
        )
        rendered=render_balance_region(*arguments)
        reordered=render_balance_region(
            readme,damage_section,list(reversed(control_rows)),
            list(reversed(value_public_rows)),catalog,catalog_cells,
            "14.1.0",DEFAULT_PROFILE,
        )
        self.assertEqual(rendered,reordered)
        self.assertTrue(rendered.startswith(BEGIN_MARKER))
        self.assertTrue(rendered.endswith(END_MARKER))
        self.assertEqual(rendered.count("| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |"),5)
        for heading in (
            "### Single-Target Damage",
            "### Control Value",
            "### Kinetic Vanguard mean Control Value",
            "### Kinetic Vanguard control catalog",
            "### Benchmark roster, eligibility, and coverage",
            "### How Control Value is calculated",
            "#### Worked example: Sap-style next-attack Disadvantage",
            "#### Worked example: Stunned",
            "### Control Reliability — delivery diagnostic",
            "### Kinetic Vanguard mean Reliability",
            "### Why Control Value and Reliability can disagree",
            "### Control methodology",
        ):
            self.assertIn(heading,rendered)
        self.assertNotIn("### Cluster / Aggregate Damage",rendered)
        for required in (
            "**Primary control-balance metric:**",
            "**Secondary diagnostic:**",
            "selects the legal package with the highest Control Value",
            "same CU-selected package",
            "remain in the roster denominator and contribute `0 CU` and `0% delivery`",
            "**Cell format:** `CU · delivery · eligible/roster`",
            "Each Kinetic Mastery row reports only that Mastery's control",
            "each rider/tier/role row reports only control produced by that exact rider form",
            "Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20",
            "[Benchmark roster, eligibility, and coverage](#benchmark-roster-eligibility-and-coverage)",
            "1.0 CU = denial of one target's normal Action + Bonus Action for one scored target-turn window.",
            "0.15 × 0.95 = 0.1425 CU",
            "**2.25 CU**",
            "does **not** mean a 46.97% chance to apply control",
            "soft control that lands consistently",
            "Stunned does **not** gain Speed 0",
            "does **not** mean that a mechanic has no value in actual play",
        ):
            self.assertIn(required,rendered)
        for forbidden in ("ORDER CHECK","KV DPR","KV as % of EK","KV as % of BM","KV control %"):
            self.assertNotIn(forbidden,rendered)
        self.assertIn(COMPARATOR_NOTICE,rendered)
        self.assertIn("LICENSE.md",rendered)
        self.assertIn("NOTICE.md",rendered)
        self.assertEqual(rendered.count("| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |"),4)
        self.assertIn("Forked Lightning — T2 — primary",rendered)
        self.assertIn("Forked Lightning — T2 — secondary",rendered)

    def test_raw_companion_tables_use_validated_common_winner_rows(self) -> None:
        _, reliability_rows, value_rows, value_audit_rows, _ = _full_authoritative_rows()
        value_public_rows = validate_value_rows(value_rows, value_audit_rows)
        reliability_public_rows = validate_reliability_alignment(
            reliability_rows, value_audit_rows
        )
        value_table = render_raw_kv_value_table(value_public_rows)
        reliability_table = render_raw_kv_reliability_table(reliability_public_rows)
        self.assertIn("| 7 | 15.000 CU | 15.000 CU | 15.000 CU | 15.000 CU |", value_table)
        self.assertIn("| 20 | 15.00% | 15.00% | 15.00% | 15.00% |", reliability_table)
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            render_raw_kv_value_table(value_public_rows[1:])

    def test_control_examples_resolve_the_maintained_catalog_and_scoring(self) -> None:
        scoring = load_scoring_config()
        sap = decompose_label("attack_disadvantage", attack_scope="next_attack")
        self.assertEqual(
            [item.primitive_id for item in sap],
            ["offensive_impairment_next_attack"],
        )
        self.assertEqual(
            scoring["rules"]["offensive_impairment_next_attack"]["nominal_weight"],
            0.15,
        )
        stunned = [
            item for item in decompose_label("stunned") if item.pricing_status == "candidate"
        ]
        self.assertEqual(
            [item.primitive_id for item in stunned],
            [
                "active_turn_denial",
                "reaction_denial",
                "save_auto_failure",
                "save_auto_failure",
                "defensive_attack_advantage",
            ],
        )
        total = sum(
            float(scoring["rules"][item.primitive_id]["nominal_weight"])
            for item in stunned
        )
        self.assertEqual(total, 2.25)
        explanation = render_control_value_explanation()
        self.assertIn(scoring["control_unit"], explanation)
        self.assertIn("0.15 × 0.95 = 0.1425 CU", explanation)
        self.assertIn("**2.25 CU**", explanation)
        self.assertIn("Stunned does **not** gain Speed 0", explanation)
        self.assertNotIn("Stunned gains Speed 0", explanation)

    def test_markdown_table_has_exact_header_width_and_escaping(self) -> None:
        rendered=_markdown_table(("First","Second"),(("a|b","line\nbreak"),))
        self.assertEqual(rendered,"| First | Second |\n|---|---|\n| a\\|b | line break |")
        with self.assertRaisesRegex(MatrixSyncError,"header width"):
            _markdown_table(("First","Second"),(("only one cell",),))


class ControlCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            _,
            _,
            _,
            _,
            cls.scenario_rows,
        ) = _full_authoritative_rows()
        cls.catalog = build_kv_control_catalog()
        cls.levels = tuple(
            int(value) for value in load_config()["methodology"]["levels"]
        )

    def test_inventory_is_canonical_complete_and_ordered(self) -> None:
        masteries = [form for form in self.catalog if form.is_mastery]
        self.assertEqual(len(masteries),4)
        self.assertEqual(
            {form.discipline_id for form in masteries}, set(README_DISCIPLINES)
        )
        model = AuthorityModel.load(DEFAULT_AUTHORITY)
        ordinary = [
            feature
            for feature in model.features.values()
            if not feature["advanced_training"]
        ]
        expected = {
            (str(feature["entity_id"]),int(tier["tier"]))
            for feature in ordinary
            for tier in feature["damage_tiers"]
        }
        actual = {
            (str(form.entity_id),int(form.tier))
            for form in self.catalog
            if not form.is_mastery
        }
        self.assertEqual(actual,expected)
        self.assertFalse(
            any(
                form.entity_id and form.entity_id.startswith("advanced_")
                for form in self.catalog
            )
        )
        for feature in ordinary:
            tiers = [
                form.tier
                for form in self.catalog
                if form.entity_id == feature["entity_id"]
                and form.target_role == "primary"
            ]
            self.assertEqual(
                tiers,[int(item["tier"]) for item in feature["damage_tiers"]]
            )

    def test_target_role_variants_remain_exact_forms(self) -> None:
        secondary = {
            form.scenario_id
            for form in self.catalog
            if form.target_role == "secondary"
        }
        self.assertEqual(
            secondary,
            {
                "explosion_implosion:T0:secondary",
                "explosion_implosion:T1:secondary",
                "forked_lightning:T2:secondary",
            },
        )
        for scenario in secondary:
            self.assertTrue(
                any(
                    form.scenario_id == scenario.removesuffix(":secondary")
                    for form in self.catalog
                )
            )

    def test_pricing_states_and_suppressed_rows_are_distinct(self) -> None:
        self.assertEqual(classify_catalog_pricing(1,0),PRICED)
        self.assertEqual(classify_catalog_pricing(1,1),PARTIALLY_PRICED)
        self.assertEqual(classify_catalog_pricing(0,1),UNPRICED)
        with self.assertRaisesRegex(MatrixSyncError,"no retained meaningful"):
            classify_catalog_pricing(0,0)
        cells = validate_control_catalog_scenarios(
            self.scenario_rows,self.catalog,self.levels
        )
        self.assertEqual(
            cells[("pyrokinesis","mastery:graze",7)].state,
            NO_MODELED_CONTROL,
        )
        rows = deepcopy(self.scenario_rows)
        for row in rows:
            if row["Discipline"] == "cryokinesis" and row["Scenario"] == "glacial_spike:T0":
                row["Primitive Rows"] = "2"
                row["Context/Unsupported Rows"] = "1"
                row["Retained Context/Unsupported Rows"] = "0"
        suppressed = validate_control_catalog_scenarios(rows,self.catalog,self.levels)
        self.assertEqual(suppressed[("cryokinesis","glacial_spike:T0",7)].state,PRICED)

    def test_availability_raw_evidence_denominator_and_coverage(self) -> None:
        rows = deepcopy(self.scenario_rows)
        changed = next(
            row for row in rows
            if row["Level"] == "7"
            and row["Discipline"] == "cryokinesis"
            and row["Scenario"] == "glacial_spike:T0"
        )
        changed.update(
            {
                "Eligible":"False",
                "Control Value CU":"0.0",
                "Whole-package control stick %":"0.0",
                "Value Disposition":"ineligible",
                "Primitive Rows":"0",
                "Candidate Rows":"0",
                "Context/Unsupported Rows":"0",
                "Retained Candidate Rows":"0",
                "Retained Context/Unsupported Rows":"0",
            }
        )
        cells = validate_control_catalog_scenarios(rows,self.catalog,self.levels)
        total = PROFILE_LEVEL_COUNTS[DEFAULT_PROFILE][7]
        cell = cells[("cryokinesis","glacial_spike:T0",7)]
        self.assertEqual((cell.eligible_targets,cell.total_targets),(total-1,total))
        self.assertAlmostEqual(cell.mean_cu,(total-1)/total)
        self.assertAlmostEqual(cell.mean_delivery,50*(total-1)/total)
        self.assertEqual(
            cells[("cryokinesis","glacial_spike:T2",7)].state,UNAVAILABLE
        )
        self.assertEqual(
            cells[("pyrokinesis","ember_bolt:T0",7)].state,
            NO_MODELED_CONTROL,
        )

    def test_scenario_schema_provenance_duplicates_and_unknowns_fail_closed(self) -> None:
        missing = deepcopy(self.scenario_rows)
        del missing[0]["Retained Candidate Rows"]
        with self.assertRaisesRegex(MatrixSyncError,"schema differences"):
            validate_control_catalog_scenarios(missing,self.catalog,self.levels)
        stale = deepcopy(self.scenario_rows)
        stale[0]["Authority SHA-256"] = "wrong-authority"
        with self.assertRaisesRegex(MatrixSyncError,"Authority SHA-256"):
            validate_control_catalog_scenarios(stale,self.catalog,self.levels)
        duplicate = deepcopy(self.scenario_rows)
        duplicate.append(deepcopy(duplicate[0]))
        with self.assertRaisesRegex(MatrixSyncError,"duplicates exact scenario identity"):
            validate_control_catalog_scenarios(duplicate,self.catalog,self.levels)
        unknown = deepcopy(self.scenario_rows)
        unknown[0]["Scenario"] = "unknown:T0"
        with self.assertRaisesRegex(MatrixSyncError,"unknown exact KV scenario"):
            validate_control_catalog_scenarios(unknown,self.catalog,self.levels)

    def test_catalog_rider_evidence_inventory_is_independent_of_headline_inventory(self) -> None:
        publication = catalog_rider_scenarios(self.catalog)
        self.assertEqual(len(publication),33)
        published_identities = {
            (
                str(item["discipline_id"]),
                f"{item['entity_id']}:T{item['tier']}"
                + (f":{item['target_role']}" if item["target_role"] != "primary" else ""),
            )
            for item in publication
        }
        self.assertEqual(
            published_identities,
            {
                form.identity
                for form in self.catalog
                if form.modeled_control and not form.is_mastery
            },
        )
        self.assertFalse(
            {
                "explosion_implosion:T2",
                "static_discharge:T0",
                "static_discharge:T1",
                "branching_bolt:T0",
                "branching_bolt:T1",
                "branching_bolt:T2",
                "electron_burst:T0",
                "electron_burst:T1",
            }
            & {identity[1] for identity in published_identities}
        )

    def test_catalog_legend_explains_cells_and_full_roster_denominator(self) -> None:
        cells = validate_control_catalog_scenarios(
            self.scenario_rows,self.catalog,self.levels
        )
        catalog = render_kv_control_catalog(
            self.catalog,cells,self.levels
        )
        for required in (
            "**Cell format:** `CU · delivery · eligible/roster`",
            "`0.143 CU` average Control Value",
            "`95.00%` average initial control-delivery probability",
            "eligible targets / roster targets",
            "`12/12` means all 12 targets satisfy the exact form's structural target restrictions",
            "If a cell says `9/12`, only 9 of 12 targets satisfy the exact form's structural target restrictions",
            "other 3 are not removed",
            "contribute `0 CU` and `0% delivery`",
            "`eligible/roster` reports structural target eligibility",
            "maximum-size and required-creature-type restrictions",
            "not universal susceptibility",
            "Condition immunity or other effect-level ineffectiveness can reduce a target's CU or delivery",
            "target remains structurally eligible in the ratio",
            "Eligibility is not a save result, hit count, successful application count, or probability",
            "`Unpriced` retains measurable delivery and eligibility without reporting zero CU",
            "`No modeled control` means `0.000 CU` and no control delivery (`—`)",
            "`N/A` means the exact form is unavailable",
            "Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20",
            "[Benchmark roster, eligibility, and coverage](#benchmark-roster-eligibility-and-coverage)",
        ):
            self.assertIn(required,catalog)
        for forbidden in (
            "eligible targets only",
            "12/12` is a save result",
            "immunity/effect-eligibility",
            "condition immunity where it makes the package ineffective",
        ):
            self.assertNotIn(forbidden,catalog)

    def test_rider_only_control_classification_is_authority_driven(self) -> None:
        no_rider_control = {
            form.scenario_id
            for form in self.catalog
            if not form.is_mastery and not form.modeled_control
        }
        self.assertEqual(
            {
                "explosion_implosion:T2",
                "static_discharge:T0",
                "static_discharge:T1",
                "branching_bolt:T0",
                "branching_bolt:T1",
                "branching_bolt:T2",
                "electron_burst:T0",
                "electron_burst:T1",
            }.issubset(no_rider_control),
            True,
        )
        self.assertIn("vectored_thrust:T0",no_rider_control)
        self.assertIn("ember_bolt:T0",no_rider_control)
        self.assertNotIn("electron_burst:T2",no_rider_control)
        self.assertNotIn("snow_chains:T2",no_rider_control)
        projection = deepcopy(AuthorityModel.load(DEFAULT_AUTHORITY).projection)
        snow_chains = next(
            feature
            for feature in projection["features"]
            if feature["entity_id"] == "snow_chains"
        )
        snow_chains["control_tiers"] = [
            row for row in snow_chains["control_tiers"] if int(row["tier"]) != 0
        ]
        slow_without_rider_control = next(
            form
            for form in build_kv_control_catalog(AuthorityModel(projection))
            if form.scenario_id == "snow_chains:T0"
        )
        self.assertFalse(slow_without_rider_control.modeled_control)
        self.assertEqual(len(self.catalog),67)
        self.assertEqual(len({form.identity for form in self.catalog}),67)
        self.assertEqual(sum(not form.modeled_control for form in self.catalog),31)

    def test_roster_methodology_is_stable_and_computes_instructional_mean(self) -> None:
        methodology = render_benchmark_roster_methodology()
        self.assertEqual(methodology.count("### Benchmark roster, eligibility, and coverage"),1)
        for required in (
            "structurally eligible targets / total maintained benchmark targets",
            "`target_is_eligible()`",
            "maximum-size and required-creature-type restrictions",
            "`12/12` means all 12 roster targets satisfy those structural restrictions",
            "`9/12` means 9 of 12 satisfy them",
            "universal susceptibility to every control consequence",
            "An ineligible target remains in the aggregate denominator",
            "`CU = 0` and `delivery = 0%`",
            "not automatically coverage exclusions",
            "structurally eligible but immune target",
            "remain in the coverage numerator while contributing `0 CU` or `0% delivery`",
            "Do not divide only by eligible targets",
            "Eligible-only averaging would hide practical restrictions",
            "**Instructional example (not a published scenario):**",
            "(9 × 0.80 + 3 × 0) / 12 = 0.60 = 60%",
            "eligible-only 80% is not the roster-wide result",
            "`Unpriced`, not zero",
            "`No modeled control` is `0.000 CU`",
            "does not participate in that level's aggregate",
        ):
            self.assertIn(required,methodology)
        self.assertNotIn("condition or effect immunity where it makes the package ineffective",methodology)


class ReadmeMatrixDelimiterTests(unittest.TestCase):
    def test_missing_duplicate_and_reversed_markers_fail_closed(self) -> None:
        malformed = {
            "missing both": "README without generated markers",
            "missing begin": f"content\n{END_MARKER}",
            "missing end": f"{BEGIN_MARKER}\ncontent",
            "duplicate begin": f"{BEGIN_MARKER}\n{BEGIN_MARKER}\n{END_MARKER}",
            "duplicate end": f"{BEGIN_MARKER}\n{END_MARKER}\n{END_MARKER}",
            "reversed": f"{END_MARKER}\ncontent\n{BEGIN_MARKER}",
        }
        for label, readme in malformed.items():
            with self.subTest(label=label):
                with self.assertRaises(MatrixSyncError):
                    generated_region_span(readme)

    def test_generated_region_replacement_preserves_surroundings_and_is_idempotent(self) -> None:
        readme = f"prefix\n{BEGIN_MARKER}\nold\n{END_MARKER}\nsuffix"
        region = f"{BEGIN_MARKER}\nnew\n{END_MARKER}"
        expected = f"prefix\n{BEGIN_MARKER}\nnew\n{END_MARKER}\nsuffix"
        replaced = replace_generated_region(readme, region)
        self.assertEqual(replaced, expected)
        self.assertEqual(replace_generated_region(replaced, region), expected)

    def test_control_render_preserves_damage_subsection_byte_for_byte(self) -> None:
        readme = readme_matrices.README_PATH.read_text(encoding="utf-8")
        original_damage = extract_damage_section(readme)
        (
            _,
            reliability_rows,
            value_rows,
            value_audit_rows,
            value_scenario_rows,
        ) = _full_authoritative_rows()
        catalog = build_kv_control_catalog()
        catalog_cells = validate_control_catalog_scenarios(
            value_scenario_rows,
            catalog,
            tuple(int(value) for value in load_config()["methodology"]["levels"]),
        )
        rules_version, profile, _, disciplines = validate_reliability_rows(
            reliability_rows
        )
        rendered = render_balance_region(
            readme,
            original_damage,
            reliability_rows,
            validate_value_rows(value_rows, value_audit_rows),
            catalog,
            catalog_cells,
            rules_version,
            profile,
            disciplines,
        )
        synchronized = replace_generated_region(readme, rendered)
        self.assertEqual(extract_damage_section(synchronized), original_damage)


class ReadmeMatrixReleaseStateTests(unittest.TestCase):
    def test_development_snapshot_names_canonical_and_published_versions(self) -> None:
        readme = "\n".join(
            (
                "- Current published release: **v14.0.0**",
                "- Current development line: **v14.1.0**",
            )
        )
        self.assertEqual(
            release_state_line(readme, "14.1.0"),
            "**Unreleased development snapshot** — canonical rules **v14.1.0**; current published release **v14.0.0**.",
        )

    def test_published_snapshot_uses_the_canonical_published_version(self) -> None:
        readme = "\n".join(
            (
                "- Current published release: **v14.1.0**",
                "- Current development line: **None**",
            )
        )
        self.assertEqual(
            release_state_line(readme, "14.1.0"),
            "**Published snapshot** — canonical rules **v14.1.0**.",
        )

    def test_duplicate_release_status_lines_fail_closed(self) -> None:
        published = "- Current published release: **v14.0.0**"
        development = "- Current development line: **v14.1.0**"
        cases = (
            "\n".join((published, published, development)),
            "\n".join((published, development, development)),
        )
        for readme in cases:
            with self.subTest(readme=readme):
                with self.assertRaisesRegex(MatrixSyncError, "exactly one"):
                    release_state_line(readme, "14.1.0")

    def test_published_canonical_snapshot_rejects_a_live_development_line(self) -> None:
        for development in ("v14.1.0", "v14.2.0"):
            with self.subTest(development=development):
                readme = "\n".join(
                    (
                        "- Current published release: **v14.1.0**",
                        f"- Current development line: **{development}**",
                    )
                )
                with self.assertRaisesRegex(MatrixSyncError, "requires development line None"):
                    release_state_line(readme, "14.1.0")

    def test_missing_or_unrelated_release_state_fails_closed(self) -> None:
        cases = (
            "- Current published release: **v14.0.0**",
            "\n".join(
                (
                    "- Current published release: **v14.0.0**",
                    "- Current development line: **v14.2.0**",
                )
            ),
        )
        for readme in cases:
            with self.subTest(readme=readme):
                with self.assertRaises(MatrixSyncError):
                    release_state_line(readme, "14.1.0")


class ReadmeMatrixAtomicWriteTests(unittest.TestCase):
    def test_atomic_replace_refuses_stale_expected_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text("concurrent edit", encoding="utf-8")
            with self.assertRaisesRegex(MatrixSyncError, "concurrently changed"):
                atomic_replace_text(path, "expected old text", "replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "concurrent edit")

    def test_atomic_replace_rechecks_source_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text("before", encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=("before", "changed")):
                with self.assertRaisesRegex(MatrixSyncError, "concurrently changed"):
                    atomic_replace_text(path, "before", "replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "before")
            self.assertEqual([item.name for item in root.iterdir()], ["README.md"])


class AuthoritativeRowValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            cls.damage_rows,
            cls.control_rows,
            cls.value_rows,
            cls.value_audit_rows,
            _,
        ) = _full_authoritative_rows()

    def test_full_current_shape_synthetic_rows_pass(self) -> None:
        model = AuthorityModel.load(DEFAULT_AUTHORITY)
        config = load_config()
        self.assertEqual(
            validate_authoritative_rows(self.damage_rows, self.control_rows),
            (
                model.rules_version,
                DEFAULT_PROFILE,
                tuple(int(value) for value in config["methodology"]["cluster_sizes"]),
                README_DISCIPLINES,
            ),
        )

    def test_schema_differences_fail_closed(self) -> None:
        damage = deepcopy(self.damage_rows)
        del damage[0]["Profile"]
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(damage, self.control_rows)

        control = deepcopy(self.control_rows)
        control[0]["Unexpected"] = "field"
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_authoritative_rows(self.damage_rows, control)

    def test_duplicate_and_missing_identities_fail_closed(self) -> None:
        missing_damage = deepcopy(self.damage_rows[1:])
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            validate_authoritative_rows(missing_damage, self.control_rows)

        duplicate_control = deepcopy(self.control_rows)
        duplicate_control.append(deepcopy(duplicate_control[0]))
        with self.assertRaisesRegex(MatrixSyncError, "duplicate row identities"):
            validate_authoritative_rows(self.damage_rows, duplicate_control)

    def test_provenance_and_notice_mismatches_fail_closed(self) -> None:
        damage = deepcopy(self.damage_rows)
        damage[0]["Provenance Evaluator"] = "wrong-evaluator"
        with self.assertRaisesRegex(MatrixSyncError, "Provenance Evaluator"):
            validate_authoritative_rows(damage, self.control_rows)

        control = deepcopy(self.control_rows)
        notice_field = next(iter(NOTICE_COLUMNS))
        control[0][notice_field] = "changed notice"
        with self.assertRaisesRegex(MatrixSyncError, "changed notice field"):
            validate_authoritative_rows(self.damage_rows, control)

    def test_reliability_cu_selection_provenance_fails_closed(self) -> None:
        expected = {
            "Provenance Control Primitive Catalog Sha256": file_sha256(
                DEFAULT_PRIMITIVES
            ),
            "Provenance Control Value Config Sha256": file_sha256(DEFAULT_SCORING),
        }
        for field, value in expected.items():
            self.assertTrue(all(row[field] == value for row in self.control_rows))
            with self.subTest(field=field):
                stale = deepcopy(self.control_rows)
                stale[0][field] = "wrong-hash"
                with self.assertRaisesRegex(MatrixSyncError, field):
                    validate_reliability_rows(stale)

    def test_damage_provenance_does_not_require_cu_selection_inputs(self) -> None:
        control_only_fields = {
            "Provenance Control Primitive Catalog Sha256",
            "Provenance Control Value Config Sha256",
        }
        self.assertTrue(
            all(control_only_fields.isdisjoint(row) for row in self.damage_rows)
        )
        validate_damage_rows(self.damage_rows)

    def test_catalog_roster_and_target_profile_provenance_fail_closed(self) -> None:
        cases = (
            ("Provenance Catalog Sha256", "wrong-catalog"),
            ("Provenance Roster Sha256", "wrong-roster"),
            ("Provenance Target Profile", "unknown_profile"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                damage = deepcopy(self.damage_rows)
                damage[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, field):
                    validate_authoritative_rows(damage, self.control_rows)

    def test_stale_result_and_boundary_evidence_fails_closed(self) -> None:
        cases = (
            ("Benchmark Type", "Control Reliability"),
            ("KV", "16.000000"),
            ("KV as % of EK", "999.00"),
            ("Lower Comparator", "Battle Master"),
            ("Lower Boundary", "999.000000"),
            ("Upper Comparator", "Eldritch Knight"),
            ("Upper Boundary", "999.000000"),
            ("Band", "HOT"),
            ("Boundary Delta %", "+1.00"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                damage = deepcopy(self.damage_rows)
                damage[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, f"stale {field}"):
                    validate_authoritative_rows(damage, self.control_rows)


class ControlValueRowValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            _,
            cls.reliability_rows,
            cls.value_rows,
            cls.value_audit_rows,
            _,
        ) = _full_authoritative_rows()

    def test_full_winner_derived_value_shape_passes(self) -> None:
        public_rows = validate_value_rows(self.value_rows, self.value_audit_rows)
        self.assertEqual(len(public_rows), 16)
        self.assertEqual({row["Band"] for row in public_rows}, {"IDEAL"})
        self.assertTrue(
            all(row["Benchmark Type"] == "Control Value" for row in public_rows)
        )
        aligned = validate_reliability_alignment(
            self.reliability_rows, self.value_audit_rows
        )
        self.assertEqual(len(aligned), 16)
        self.assertTrue(
            all(row["Benchmark Type"] == "Control Reliability" for row in aligned)
        )
        self.assertTrue(all(row["Metric"] for row in aligned))

    def test_value_schema_duplicates_and_missing_identities_fail_closed(self) -> None:
        missing_field = deepcopy(self.value_rows)
        del missing_field[0]["Targets"]
        with self.assertRaisesRegex(MatrixSyncError, "schema differences"):
            validate_value_rows(missing_field, self.value_audit_rows)

        duplicate = deepcopy(self.value_rows)
        duplicate.append(deepcopy(duplicate[0]))
        with self.assertRaisesRegex(MatrixSyncError, "duplicate row identities"):
            validate_value_rows(duplicate, self.value_audit_rows)

        missing = deepcopy(self.value_rows[1:])
        with self.assertRaisesRegex(MatrixSyncError, "row identities differ"):
            validate_value_rows(missing, self.value_audit_rows)

    def test_value_provenance_target_counts_and_eligibility_fail_closed(self) -> None:
        cases = (
            ("Control Primitive Catalog SHA-256", "wrong-primitives"),
            ("Control Value Config SHA-256", "wrong-scoring"),
            ("Authority SHA-256", "wrong-authority"),
            ("Target Profile", "wrong-profile"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                rows = deepcopy(self.value_rows)
                rows[0][field] = value
                with self.assertRaisesRegex(MatrixSyncError, field):
                    validate_value_rows(rows, self.value_audit_rows)

        wrong_count = deepcopy(self.value_rows)
        wrong_count[0]["Targets"] = "47"
        with self.assertRaisesRegex(MatrixSyncError, "Targets"):
            validate_value_rows(wrong_count, self.value_audit_rows)

        ineligible = deepcopy(self.value_audit_rows)
        ineligible[0]["Eligible"] = "False"
        with self.assertRaisesRegex(MatrixSyncError, "ineligible winner"):
            validate_value_rows(self.value_rows, ineligible)

    def test_value_aggregates_and_public_bands_are_recomputed(self) -> None:
        stale = deepcopy(self.value_rows)
        stale[0]["Kinetic Vanguard Control Value CU"] = "999.000000000000"
        with self.assertRaisesRegex(MatrixSyncError, "stale winner aggregate"):
            validate_value_rows(stale, self.value_audit_rows)

        audit = deepcopy(self.value_audit_rows)
        row = next(
            item
            for item in audit
            if item["Build"] == "kinetic_vanguard"
            and item["Discipline"] == "cryokinesis"
            and item["Level"] == "7"
        )
        row["Control Value CU"] = "25.0"
        with self.assertRaisesRegex(MatrixSyncError, "stale winner aggregate"):
            validate_value_rows(self.value_rows, audit)

    def test_reliability_is_reconstructed_from_common_cu_winners(self) -> None:
        audit = deepcopy(self.value_audit_rows)
        row = next(
            item
            for item in audit
            if item["Build"] == "kinetic_vanguard"
            and item["Discipline"] == "cryokinesis"
            and item["Level"] == "7"
        )
        row["Whole-package control stick %"] = "95.0"
        with self.assertRaisesRegex(MatrixSyncError, "common winner KV"):
            validate_reliability_alignment(self.reliability_rows, audit)

    def test_common_winner_selection_basis_fails_closed(self) -> None:
        audit = deepcopy(self.value_audit_rows)
        audit[0]["Selection Basis"] = "Reliability"
        with self.assertRaisesRegex(MatrixSyncError, "non-CU selection basis"):
            validate_value_rows(self.value_rows, audit)
        with self.assertRaisesRegex(MatrixSyncError, "non-CU selection basis"):
            validate_reliability_alignment(self.reliability_rows, audit)


class ControlOnlyGenerationTests(unittest.TestCase):
    def test_control_only_runs_control_once_and_never_runs_damage(self) -> None:
        paths = {
            "paths": {"csv": Path("reliability.csv")},
            "value_paths": {
                "matrix": Path("value.csv"),
                "selection_audit": Path("audit.csv"),
                "scenario_detail": Path("scenario.csv"),
                "catalog_scenario_detail": Path("catalog-scenario.csv"),
            },
        }
        expected = (
            [{"kind": "reliability"}],
            [{"kind": "value"}],
            [{"kind": "audit"}],
            [{"kind": "scenario"}],
        )
        with (
            patch.object(readme_matrices, "run_control", return_value=paths) as control,
            patch.object(readme_matrices, "run_damage") as damage,
            patch.object(
                readme_matrices,
                "read_matrix_rows",
                side_effect=expected,
            ),
        ):
            self.assertEqual(generate_control_publication_rows(), expected)
        control.assert_called_once()
        self.assertTrue(control.call_args.kwargs["write_shadow"])
        self.assertTrue(control.call_args.kwargs["write_headline"])
        self.assertFalse(control.call_args.kwargs["write_detail"])
        publication = control.call_args.kwargs["publication_scenarios"]
        self.assertEqual(len(publication),33)
        self.assertTrue(all(set(item)=={"discipline_id","entity_id","tier","target_role"} for item in publication))
        damage.assert_not_called()

if __name__ == "__main__":
    unittest.main()
