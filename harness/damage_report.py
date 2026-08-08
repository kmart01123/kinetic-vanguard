"""Damage comparison-matrix aggregation, classification, and rendering."""

from __future__ import annotations

import csv
import html
import math
from pathlib import Path
from typing import Any, Iterable

BANDS = {"COLD", "IDEAL", "HOT", "N/A"}
VALUE_COLUMNS = [
    "Benchmark Type",
    "KV",
    "Eldritch Knight",
    "Battle Master",
    "KV as % of EK",
    "KV as % of BM",
    "Lower Comparator",
    "Upper Comparator",
    "Lower Boundary",
    "Upper Boundary",
    "Band",
    "Boundary Delta %",
]

PROJECT_ATTRIBUTION_NOTICE = "Original Kinetic Vanguard content is Copyright © 2026 NixNinja. Created by NixNinja in collaboration with artificial intelligence assistants. Special thanks to various muses, great and small. Original Kinetic Vanguard rules, examples, explanatory and editorial prose, documentation, approved interface text, and project-authored benchmark explanation are licensed under CC BY-NC-SA 4.0, available at https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode. The canonical legal code, including its Section 5 disclaimer of warranties and limitation of liability, controls."
COMPONENT_BOUNDARY_NOTICE = "Project-authored benchmark software, report structure, analytical implementation, methodology, and technical configuration structure are Copyright (c) 2026, NixNinja and licensed under BSD-3-Clause. SRD 5.2.1-derived material remains licensed under CC BY 4.0. Third-party names and underlying non-SRD material are not licensed by the project. Each distinguishable component retains its own license. Complete BSD terms are available at https://github.com/kmart01123/kinetic-vanguard/blob/main/LICENSE-CODE. Full boundaries and notices are available at https://github.com/kmart01123/kinetic-vanguard/blob/main/LICENSE.md and https://github.com/kmart01123/kinetic-vanguard/blob/main/NOTICE.md."
SRD_ATTRIBUTION_NOTICE = "This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode."
SRD_MODIFICATION_NOTICE = "Changes have been made to the SRD 5.2.1 material used in this work. Use of SRD material does not imply endorsement."
SRD_SECTION_5_NOTICE = "Section 5 of CC-BY-4.0 includes a Disclaimer of Warranties and Limitation of Liability that limits our liability to you."
COMPARATOR_NOTICE = "Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document."
LEGAL_NOTICES = (
    ("Project Attribution", PROJECT_ATTRIBUTION_NOTICE),
    ("Component Boundary", COMPONENT_BOUNDARY_NOTICE),
    ("SRD 5.2.1 Attribution", SRD_ATTRIBUTION_NOTICE),
    ("SRD Modification", SRD_MODIFICATION_NOTICE),
    ("SRD Section 5 Disclaimer", SRD_SECTION_5_NOTICE),
    ("Unofficial Comparative Benchmarks", COMPARATOR_NOTICE),
)
NOTICE_COLUMNS = {f"Notice {label}": value for label, value in LEGAL_NOTICES}


def _display_value(value: float) -> float:
    return round(float(value), 6)


def _percentage(numerator: float, denominator: float) -> str:
    return "N/A" if denominator == 0 else f"{100.0 * numerator / denominator:.2f}"


def _comparator_envelope(
    eldritch_knight: float, battle_master: float
) -> tuple[float, float, str, str]:
    if eldritch_knight < battle_master:
        return eldritch_knight, battle_master, "Eldritch Knight", "Battle Master"
    if battle_master < eldritch_knight:
        return battle_master, eldritch_knight, "Battle Master", "Eldritch Knight"
    tied = "Eldritch Knight + Battle Master"
    return eldritch_knight, battle_master, tied, tied


def classify_envelope(
    kv: float, eldritch_knight: float, battle_master: float
) -> str:
    values = (kv, eldritch_knight, battle_master)
    if not all(math.isfinite(value) for value in values):
        return "N/A"
    if eldritch_knight == 0 or battle_master == 0:
        return "N/A"
    lower, upper, _, _ = _comparator_envelope(eldritch_knight, battle_master)
    if kv < lower:
        return "COLD"
    if kv > upper:
        return "HOT"
    return "IDEAL"


def _boundary_delta(
    kv: float, eldritch_knight: float, battle_master: float, band: str
) -> str:
    if band == "IDEAL":
        return "0.00"
    if band not in {"COLD", "HOT"}:
        return "N/A"
    lower, upper, _, _ = _comparator_envelope(eldritch_knight, battle_master)
    boundary = upper if band == "HOT" else lower
    return "N/A" if boundary == 0 else f"{100.0 * (kv - boundary) / boundary:+.2f}"


def damage_matrix_row(
    metadata: dict[str, Any],
    kv: float,
    eldritch_knight: float,
    battle_master: float,
) -> dict[str, str]:
    raw = [float(value) for value in (kv, eldritch_knight, battle_master)]
    if not all(math.isfinite(value) for value in raw):
        raise ValueError("Comparison matrix values must be finite")
    displayed = [_display_value(value) for value in raw]
    lower, upper, lower_name, upper_name = _comparator_envelope(
        displayed[1], displayed[2]
    )
    band = classify_envelope(*displayed)
    row = {key: str(value) for key, value in metadata.items()}
    row.update({
        "Benchmark Type": "Damage",
        "KV": f"{displayed[0]:.6f}", "Eldritch Knight": f"{displayed[1]:.6f}", "Battle Master": f"{displayed[2]:.6f}",
        "KV as % of EK": _percentage(displayed[0], displayed[1]), "KV as % of BM": _percentage(displayed[0], displayed[2]),
        "Lower Comparator": lower_name, "Upper Comparator": upper_name,
        "Lower Boundary": f"{lower:.6f}", "Upper Boundary": f"{upper:.6f}",
        "Band": band, "Boundary Delta %": _boundary_delta(*displayed, band)
    })
    return row


def _markdown_table(columns: list[str], rows: list[dict[str, str]]) -> str:
    escape = lambda value: value.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines.extend("| " + " | ".join(escape(row.get(column, "")) for column in columns) + " |" for row in rows)
    return "\n".join(lines)


def _validate_release_rows(rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows):
        missing = [field for field in VALUE_COLUMNS if field not in row]
        if missing:
            raise ValueError(f"Comparison matrix row {index} is missing evidence: {missing}")
        try:
            expected = damage_matrix_row(
                {},
                float(row["KV"]),
                float(row["Eldritch Knight"]),
                float(row["Battle Master"]),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Comparison matrix row {index} has invalid raw values"
            ) from error
        for field in VALUE_COLUMNS:
            if row[field] != expected[field]:
                raise ValueError(
                    f"Comparison matrix row {index} has stale {field}: "
                    f"{row[field]!r} != {expected[field]!r}"
                )


def write_damage_matrix(
    output_dir: Path,
    rules_version: str,
    rows: Iterable[dict[str, str]],
    provenance: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        raise ValueError("Damage comparison matrix cannot be empty")
    if any(row.get("Band") not in BANDS for row in rows):
        raise ValueError("Damage comparison matrix contains an unsupported band")
    _validate_release_rows(rows)
    provenance_columns={f"Provenance {str(key).replace('_',' ').title()}":str(value) for key,value in provenance.items()}
    rows=[{**row,**provenance_columns} for row in rows]
    columns = list(rows[0])
    if any(list(row) != columns for row in rows):
        raise ValueError("Damage comparison matrix rows do not share one column order")
    csv_rows=[{**row,**NOTICE_COLUMNS} for row in rows]
    csv_columns=list(csv_rows[0])
    slug = rules_version.replace(".", "-")
    report_title = "Damage"
    base = output_dir / f"kv-{slug}-damage-comparison-matrix"
    csv_path, md_path, html_path = base.with_suffix(".csv"), base.with_suffix(".md"), base.with_suffix(".html")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_columns);writer.writeheader();writer.writerows(csv_rows)
    provenance_lines = [f"- {key}: `{value}`" for key, value in provenance.items()]
    notice_lines = [f"- **{label}:** {value}" for label, value in LEGAL_NOTICES]
    limitation = "Damage percentages are computed from the displayed aggregate raw values, never from averaged target-level percentages."
    distance_note = "Battle Master and Eldritch Knight define a dynamic comparison envelope for every result. Boundary Delta % is negative below the lower comparator, positive above the upper comparator, and 0.00 inside the inclusive envelope."
    md = f"# Kinetic Vanguard {rules_version} {report_title} Comparison Matrix\n\n{limitation}\n\n{distance_note}\n\n## Licensing and notices\n\n" + "\n".join(notice_lines) + "\n\n## Provenance\n\n" + "\n".join(provenance_lines) + "\n\n" + _markdown_table(columns, rows) + "\n"
    md_path.write_text(md, encoding="utf-8")
    colors = {"COLD":"#dbeafe","IDEAL":"#dcfce7","HOT":"#ffedd5","N/A":"#e5e7eb"}
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells=[]
        for column in columns:
            value=row.get(column,"");style=f' style="background:{colors[value]}"' if column=="Band" else ""
            cells.append(f"<td{style}>{html.escape(value)}</td>")
        body.append("<tr>"+"".join(cells)+"</tr>")
    prov="".join(f"<li><strong>{html.escape(str(key))}:</strong> {html.escape(str(value))}</li>" for key,value in provenance.items())
    notices="".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label,value in LEGAL_NOTICES)
    document=f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Kinetic Vanguard {html.escape(rules_version)} {report_title} Comparison Matrix</title><style>body{{font:16px system-ui;margin:2rem;color:#111827}}table{{border-collapse:collapse}}th,td{{border:1px solid #9ca3af;padding:.45rem;text-align:right}}th:first-child,td:first-child{{text-align:left}}dt{{font-weight:700;margin-top:.75rem}}dd{{margin-left:0}}</style><h1>Kinetic Vanguard {html.escape(rules_version)} {report_title} Comparison Matrix</h1><p>{html.escape(limitation)}</p><p>{html.escape(distance_note)}</p><h2>Licensing and notices</h2><dl>{notices}</dl><h2>Provenance</h2><ul>{prov}</ul><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></html>"""
    html_path.write_text(document, encoding="utf-8")
    return {"csv":csv_path,"markdown":md_path,"html":html_path}
