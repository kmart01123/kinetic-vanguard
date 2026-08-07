"""Shared comparison-matrix aggregation, classification, and rendering."""

from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any, Iterable

BANDS = {"COLD", "IDEAL", "HOT", "ORDER CHECK", "N/A"}
VALUE_COLUMNS = ["KV", "Eldritch Knight", "Battle Master", "KV as % of EK", "KV as % of BM", "Band"]


def _display_value(value: float) -> float:
    return round(float(value), 6)


def _percentage(numerator: float, denominator: float) -> str:
    return "N/A" if denominator == 0 else f"{100.0 * numerator / denominator:.2f}"


def classify_damage(kv: float, eldritch_knight: float, battle_master: float) -> str:
    if eldritch_knight == 0 or battle_master == 0:
        return "N/A"
    if eldritch_knight > battle_master:
        return "ORDER CHECK"
    if kv < eldritch_knight:
        return "COLD"
    if kv <= battle_master:
        return "IDEAL"
    return "HOT"


def classify_control(kv: float, eldritch_knight: float, battle_master: float) -> str:
    if eldritch_knight == 0 or battle_master == 0:
        return "N/A"
    if battle_master > eldritch_knight:
        return "ORDER CHECK"
    if kv < battle_master:
        return "COLD"
    if kv <= eldritch_knight:
        return "IDEAL"
    return "HOT"


def matrix_row(metadata: dict[str, Any], kv: float, eldritch_knight: float, battle_master: float, kind: str) -> dict[str, str]:
    displayed = [_display_value(value) for value in (kv, eldritch_knight, battle_master)]
    classifier = classify_damage if kind == "damage" else classify_control
    row = {key: str(value) for key, value in metadata.items()}
    row.update({
        "KV": f"{displayed[0]:.6f}", "Eldritch Knight": f"{displayed[1]:.6f}", "Battle Master": f"{displayed[2]:.6f}",
        "KV as % of EK": _percentage(displayed[0], displayed[1]), "KV as % of BM": _percentage(displayed[0], displayed[2]),
        "Band": classifier(*displayed)
    })
    return row


def _markdown_table(columns: list[str], rows: list[dict[str, str]]) -> str:
    escape = lambda value: value.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines.extend("| " + " | ".join(escape(row.get(column, "")) for column in columns) + " |" for row in rows)
    return "\n".join(lines)


def write_matrix(output_dir: Path, rules_version: str, kind: str, rows: Iterable[dict[str, str]], provenance: dict[str, Any]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        raise ValueError("Comparison matrix cannot be empty")
    if any(row.get("Band") not in BANDS for row in rows):
        raise ValueError("Comparison matrix contains an unsupported band")
    provenance_columns={f"Provenance {str(key).replace('_',' ').title()}":str(value) for key,value in provenance.items()}
    rows=[{**row,**provenance_columns} for row in rows]
    columns = list(rows[0])
    if any(list(row) != columns for row in rows):
        raise ValueError("Comparison matrix rows do not share one column order")
    slug = rules_version.replace(".", "-")
    base = output_dir / f"kv-{slug}-{kind}-comparison-matrix"
    csv_path, md_path, html_path = base.with_suffix(".csv"), base.with_suffix(".md"), base.with_suffix(".html")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns);writer.writeheader();writer.writerows(rows)
    provenance_lines = [f"- {key}: `{value}`" for key, value in provenance.items()]
    limitation = "Control values are a best-available reliability envelope, not a severity-weighted score; different conditions are not treated as equally valuable." if kind == "control" else "Damage percentages are computed from the displayed aggregate raw values, never from averaged target-level percentages."
    md = f"# Kinetic Vanguard {rules_version} {kind.title()} Comparison Matrix\n\n{limitation}\n\n## Provenance\n\n" + "\n".join(provenance_lines) + "\n\n" + _markdown_table(columns, rows) + "\n"
    md_path.write_text(md, encoding="utf-8")
    colors = {"COLD":"#dbeafe","IDEAL":"#dcfce7","HOT":"#ffedd5","ORDER CHECK":"#e5e7eb","N/A":"#e5e7eb"}
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells=[]
        for column in columns:
            value=row.get(column,"");style=f' style="background:{colors[value]}"' if column=="Band" else ""
            cells.append(f"<td{style}>{html.escape(value)}</td>")
        body.append("<tr>"+"".join(cells)+"</tr>")
    prov="".join(f"<li><strong>{html.escape(str(key))}:</strong> {html.escape(str(value))}</li>" for key,value in provenance.items())
    document=f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Kinetic Vanguard {html.escape(rules_version)} {kind.title()} Comparison Matrix</title><style>body{{font:16px system-ui;margin:2rem;color:#111827}}table{{border-collapse:collapse}}th,td{{border:1px solid #9ca3af;padding:.45rem;text-align:right}}th:first-child,td:first-child{{text-align:left}}</style><h1>Kinetic Vanguard {html.escape(rules_version)} {kind.title()} Comparison Matrix</h1><p>{html.escape(limitation)}</p><h2>Provenance</h2><ul>{prov}</ul><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></html>"""
    html_path.write_text(document, encoding="utf-8")
    return {"csv":csv_path,"markdown":md_path,"html":html_path}
