"""Turn Claude's findings into a checked report: merge proposed blocks, find invalid defaults/examples,
verify each finding against the schema and the app's enumerations, and write the Markdown file."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import schema_tools as st

# The Enumeration Manager's own rule for enumeration names.
ENUM_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")


class ValueMapping(BaseModel):
    schema_value: str
    enumeration_value: str | None = Field(
        default=None, description="The enumeration value it corresponds to, or null if it would be dropped."
    )


class ProposedEnumeration(BaseModel):
    name: str = Field(description="New enumeration name, matching ^[A-Za-z][A-Za-z0-9_-]*$ (snake_case preferred).")
    description: str
    values: list[str]


class Finding(BaseModel):
    attribute: str = Field(description="Attribute name, as read_json_schema returned it.")
    schema_pointer: str = Field(description="JSON Pointer of the attribute, exactly as read_json_schema returned it.")
    status: Literal["same", "similar", "different"]
    matched_enumeration: str | None = Field(default=None, description="The matching app enumeration; null for 'different'.")
    explanation: str = Field(description="One or two sentences on why this status was chosen.")
    proposed_schema_fragment: dict | None = Field(
        default=None,
        description="Only for 'similar': the replacement JSON Schema object for this attribute. "
        "Keywords left out are kept from the original.",
    )
    value_mapping: list[ValueMapping] | None = Field(
        default=None, description="Only for 'similar': one entry per schema value that is not in the enumeration."
    )
    proposed_enumeration: ProposedEnumeration | None = Field(
        default=None, description="Only for 'different': the enumeration to add to the app."
    )


@dataclass
class Row:
    finding: Finding
    schema_values: list[str]
    fragment: dict | None = None  # merged replacement block, for 'similar'
    conflicts: list[dict] = field(default_factory=list)


def require_absolute(path: str, what: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise ValueError(f"The {what} must be an absolute path, got '{path}'. Resolve it against the working directory first.")
    return p


def _check_same(f: Finding, attr: dict, enums: dict, warn) -> None:
    enum = enums.get(f.matched_enumeration or "")
    if enum is None:
        warn(f"`{f.schema_pointer}` is marked same, but there is no enumeration named '{f.matched_enumeration}'.")
        return
    values = attr["values"]
    if set(values) == set(enum["values"]) or (attr["kind"] == "const" and values[0] in enum["values"]):
        return
    d = st.diff_values(values, enum["values"])
    warn(
        f"`{f.schema_pointer}` is marked same, but its values differ from '{enum['name']}' "
        f"(only in schema: {d['only_in_schema']}, only in enumeration: {d['only_in_enumeration']}). It should be similar."
    )


def _check_similar(f: Finding, attr: dict, enums: dict, schema: dict, row: Row, warn) -> None:
    enum = enums.get(f.matched_enumeration or "")
    if enum is None:
        warn(f"`{f.schema_pointer}` is marked similar, but there is no enumeration named '{f.matched_enumeration}'.")
        return
    if set(attr["values"]) == set(enum["values"]):
        warn(f"`{f.schema_pointer}` is marked similar, but its values are exactly those of '{enum['name']}'. It should be same.")
    for m in f.value_mapping or []:
        if m.enumeration_value is not None and m.enumeration_value not in enum["values"]:
            warn(f"`{f.schema_pointer}` maps '{m.schema_value}' to '{m.enumeration_value}', which is not a value of '{enum['name']}'.")
    if not f.proposed_schema_fragment:
        warn(f"`{f.schema_pointer}` is marked similar but has no proposed_schema_fragment.")
        return

    proposed = f.proposed_schema_fragment
    if "enum" in proposed and [st._as_str(v) for v in proposed["enum"]] != enum["values"]:
        warn(
            f"The proposed block for `{f.schema_pointer}` lists {proposed['enum']}, not the values of "
            f"'{enum['name']}' in its order: {enum['values']}."
        )
    if "const" in proposed and st._as_str(proposed["const"]) not in enum["values"]:
        warn(f"The proposed block for `{f.schema_pointer}` sets const {proposed['const']!r}, which is not a value of '{enum['name']}'.")

    original = st.resolve_pointer(schema, f.schema_pointer)
    row.fragment = st.merge_schema_fragment(original, proposed) if isinstance(original, dict) else proposed
    mapping = {m.schema_value: m.enumeration_value for m in f.value_mapping or []}
    for c in st.find_value_conflicts(schema, f.schema_pointer, row.fragment):
        row.conflicts.append({**c, "suggested_value": mapping.get(c["value"])})


def _check_different(f: Finding, attr: dict, enums: dict, warn) -> None:
    p = f.proposed_enumeration
    if p is None:
        warn(f"`{f.schema_pointer}` is marked different but has no proposed_enumeration.")
        return
    if not ENUM_NAME_PATTERN.match(p.name):
        warn(f"The proposed enumeration name '{p.name}' is not allowed by the app (letters, digits, '_' or '-'; must start with a letter).")
    if p.name in enums:
        warn(f"The proposed enumeration '{p.name}' already exists in the app. Should `{f.schema_pointer}` be same or similar instead?")
    if p.values != attr["values"]:
        warn(f"The proposed enumeration '{p.name}' lists {p.values}, not the schema's values {attr['values']}.")


def finalize(
    schema_path: str,
    summary: str,
    findings: list[Finding],
    output_path: str,
    enumerations: list[dict] | None = None,
) -> dict:
    schema_file = require_absolute(schema_path, "schema path")
    output_file = require_absolute(output_path, "output path")
    schema = st.load_schema(schema_file)
    attrs = {a["pointer"]: a for a in st.extract_enum_attributes(schema)}
    enums = {e["name"]: e for e in (enumerations if enumerations is not None else st.fetch_enumerations())}

    warnings: list[str] = []
    rows: list[Row] = []
    seen: set[str] = set()
    for f in findings:
        if f.schema_pointer in seen:
            warnings.append(f"`{f.schema_pointer}` was reported more than once; only the first finding is kept.")
            continue
        seen.add(f.schema_pointer)
        attr = attrs.get(f.schema_pointer)
        if attr is None:
            warnings.append(f"`{f.schema_pointer}` is not an enum/const attribute of this schema; the finding was left out.")
            continue
        row = Row(f, attr["values"])
        warn = warnings.append
        if f.status == "same":
            _check_same(f, attr, enums, warn)
        elif f.status == "similar":
            _check_similar(f, attr, enums, schema, row, warn)
        else:
            _check_different(f, attr, enums, warn)
        rows.append(row)

    for pointer in attrs:
        if pointer not in seen:
            warnings.append(f"`{pointer}` has no finding.")

    markdown = render_markdown(schema_file, summary, rows, warnings)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8")

    counts = {s: sum(r.finding.status == s for r in rows) for s in ("same", "similar", "different")}
    return {
        "output_path": str(output_file),
        "counts": counts,
        "warnings": warnings,
        "similar": [
            {"schema_pointer": r.finding.schema_pointer, "replacement": r.fragment, "value_conflicts": r.conflicts}
            for r in rows
            if r.finding.status == "similar"
        ],
    }


# ---------------------------------------------------------------- Markdown


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _codes(values) -> str:
    return ", ".join(f"`{v}`" for v in values)


def render_markdown(schema_file: Path, summary: str, rows: list[Row], warnings: list[str]) -> str:
    by_status = {s: [r for r in rows if r.finding.status == s] for s in ("same", "similar", "different")}
    out = [
        f"# Enumeration review: {schema_file.name}",
        "",
        f"- **Schema:** `{schema_file}`",
        f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Enumeration Manager:** {st.API_URL}",
        "",
        summary,
        "",
        "| Result | Attributes | Action |",
        "| --- | --- | --- |",
        f"| Same | {len(by_status['same'])} | None needed |",
        f"| Similar | {len(by_status['similar'])} | Change the JSON Schema to match the enumeration |",
        f"| Different | {len(by_status['different'])} | Add a new enumeration to the app |",
        "",
    ]
    if warnings:
        out += ["> **Checks that did not pass:**"] + [f"> - {w}" for w in warnings] + [""]

    out += ["## Same: no change needed", ""]
    if by_status["same"]:
        out += ["| Attribute | Pointer | Enumeration | Notes |", "| --- | --- | --- | --- |"]
        out += [
            f"| `{_cell(r.finding.attribute)}` | `{_cell(r.finding.schema_pointer)}` | "
            f"`{_cell(r.finding.matched_enumeration)}` | {_cell(r.finding.explanation)} |"
            for r in by_status["same"]
        ]
    else:
        out.append("None.")
    out.append("")

    out += ["## Similar: proposed JSON Schema changes", ""]
    if not by_status["similar"]:
        out += ["None.", ""]
    for r in by_status["similar"]:
        f = r.finding
        out += [
            f"### `{f.attribute}` → enumeration `{f.matched_enumeration}`",
            "",
            f"- **Pointer:** `{f.schema_pointer}`",
            f"- **Schema values:** {_codes(r.schema_values)}",
        ]
        if f.value_mapping:
            changes = [f"`{m.schema_value}` → " + (f"`{m.enumeration_value}`" if m.enumeration_value else "dropped") for m in f.value_mapping]
            out.append(f"- **Value changes:** {', '.join(changes)}")
        out += ["", f.explanation, ""]
        if r.fragment:
            out += [f"Replace `{f.schema_pointer}` with:", "", "```json", json.dumps(r.fragment, indent=2), "```", ""]
        if r.conflicts:
            out += [
                "**Decide:** with the new values, these defaults/examples in the schema would become invalid.",
                "",
                "| Location | Value | Options |",
                "| --- | --- | --- |",
            ]
            for c in r.conflicts:
                options = [f"change it to `{c['suggested_value']}`"] if c["suggested_value"] else []
                options += ["remove it", f"keep it and add `{c['value']}` to the `{f.matched_enumeration}` enumeration instead"]
                out.append(f"| `{_cell(c['location'])}` | `{_cell(c['value'])}` | {_cell('; '.join(options))} |")
            out.append("")

    out += ["## Different: proposed new enumerations", ""]
    if not by_status["different"]:
        out += ["None.", ""]
    for r in by_status["different"]:
        f = r.finding
        out += [f"### `{f.attribute}`", "", f"- **Pointer:** `{f.schema_pointer}`", f"- **Schema values:** {_codes(r.schema_values)}", "", f.explanation, ""]
        p = f.proposed_enumeration
        if p:
            payload = json.dumps({"name": p.name, "description": p.description, "values": p.values}, indent=2)
            out += [
                f"Proposed enumeration `{p.name}`. To create it:",
                "",
                "```http",
                f"POST {st.API_URL}/api/enumerations",
                "Content-Type: application/json",
                "",
                payload,
                "```",
                "",
            ]

    return "\n".join(out).rstrip() + "\n"
