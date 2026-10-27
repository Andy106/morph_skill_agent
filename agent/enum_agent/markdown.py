"""Render a ComparisonReport as a Markdown document."""

import json
from datetime import datetime
from pathlib import Path

from . import tools
from .models import AttributeFinding, ComparisonReport


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _codes(values: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in values)


def _fragment(f: AttributeFinding) -> tuple[str, str]:
    try:
        return "json", json.dumps(json.loads(f.proposed_schema_fragment), indent=2)
    except json.JSONDecodeError:
        return "", f.proposed_schema_fragment


def render_markdown(report: ComparisonReport, expected_pointers: set[str], conflicts: dict[str, list[dict]]) -> str:
    by_status = {s: [f for f in report.findings if f.status == s] for s in ("same", "similar", "different")}
    out = [
        f"# Enumeration review: {Path(report.schema_path).name}",
        "",
        f"- **Schema:** `{report.schema_path}`",
        f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Enumeration Manager:** {tools.API_URL}",
        "",
        report.summary,
        "",
        "| Result | Attributes | Action |",
        "| --- | --- | --- |",
        f"| Same | {len(by_status['same'])} | None needed |",
        f"| Similar | {len(by_status['similar'])} | Change the JSON Schema to match the enumeration |",
        f"| Different | {len(by_status['different'])} | Add a new enumeration to the app |",
        "",
    ]

    missing = expected_pointers - {f.schema_pointer for f in report.findings}
    if missing:
        out += [f"> **Warning:** the agent did not report on: {_codes(sorted(missing))}", ""]

    out += ["## Same: no change needed", ""]
    if by_status["same"]:
        out += ["| Attribute | Pointer | Enumeration | Notes |", "| --- | --- | --- | --- |"]
        out += [
            f"| `{_cell(f.attribute)}` | `{_cell(f.schema_pointer)}` | `{_cell(f.matched_enumeration)}` | {_cell(f.explanation)} |"
            for f in by_status["same"]
        ]
    else:
        out.append("None.")
    out.append("")

    out += ["## Similar: proposed JSON Schema changes", ""]
    if not by_status["similar"]:
        out += ["None.", ""]
    for f in by_status["similar"]:
        out += [
            f"### `{f.attribute}` → enumeration `{f.matched_enumeration}`",
            "",
            f"- **Pointer:** `{f.schema_pointer}`",
            f"- **Schema values:** {_codes(f.schema_values)}",
        ]
        if f.value_mapping:
            renames = [f"`{m.schema_value}` → " + (f"`{m.enumeration_value}`" if m.enumeration_value else "dropped") for m in f.value_mapping]
            out.append(f"- **Value changes:** {', '.join(renames)}")
        out += ["", f.explanation, ""]
        if f.proposed_schema_fragment:
            lang, body = _fragment(f)
            out += [f"Replace `{f.schema_pointer}` with:", "", f"```{lang}", body, "```", ""]
        if conflicts.get(f.schema_pointer):
            out += [
                "**Decide:** with the new values, these defaults/examples in the schema would become invalid.",
                "",
                "| Location | Value | Options |",
                "| --- | --- | --- |",
            ]
            for c in conflicts[f.schema_pointer]:
                options = [f"change it to `{c['suggested_value']}`"] if c["suggested_value"] else []
                options += ["remove it", f"keep it and add `{c['value']}` to the `{f.matched_enumeration}` enumeration instead"]
                out.append(f"| `{_cell(c['location'])}` | `{_cell(c['value'])}` | {_cell('; '.join(options))} |")
            out.append("")

    out += ["## Different: proposed new enumerations", ""]
    if not by_status["different"]:
        out += ["None.", ""]
    for f in by_status["different"]:
        out += [
            f"### `{f.attribute}`",
            "",
            f"- **Pointer:** `{f.schema_pointer}`",
            f"- **Schema values:** {_codes(f.schema_values)}",
            "",
            f.explanation,
            "",
        ]
        p = f.proposed_enumeration
        if p:
            payload = json.dumps({"name": p.name, "description": p.description, "values": p.values}, indent=2)
            out += [
                f"Proposed enumeration `{p.name}`. To create it:",
                "",
                "```http",
                f"POST {tools.API_URL}/api/enumerations",
                "Content-Type: application/json",
                "",
                payload,
                "```",
                "",
            ]

    return "\n".join(out).rstrip() + "\n"
