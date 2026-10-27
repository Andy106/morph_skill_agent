import json

from enum_agent.markdown import render_markdown
from enum_agent.models import AttributeFinding, ComparisonReport, ProposedEnumeration, ValueMapping


def _finding(**overrides) -> AttributeFinding:
    base = dict(
        attribute="environment",
        schema_pointer="/properties/environment",
        schema_values=["dev", "test", "prod"],
        status="same",
        matched_enumeration="environment",
        explanation="Exact match.",
        proposed_schema_fragment=None,
        value_mapping=None,
        proposed_enumeration=None,
    )
    return AttributeFinding(**{**base, **overrides})


REPORT = ComparisonReport(
    schema_path="C:/schemas/db.schema.json",
    summary="1 same, 1 similar, 1 different.",
    findings=[
        _finding(attribute="asset_type", schema_pointer="/properties/asset_type", schema_values=["Database Instance"],
                 matched_enumeration="asset_types", explanation="Value is in asset_types | exact."),
        _finding(status="similar", schema_values=["dev", "uat", "prod"], explanation="uat corresponds to test.",
                 proposed_schema_fragment=json.dumps({"enum": ["dev", "test", "prod"], "x-enumeration": "environment"}),
                 value_mapping=[ValueMapping(schema_value="uat", enumeration_value="test")]),
        _finding(attribute="engine", schema_pointer="/properties/engine", schema_values=["oracle", "db2"],
                 status="different", matched_enumeration=None, explanation="No enumeration for engines.",
                 proposed_enumeration=ProposedEnumeration(name="engine", description="DB engines", values=["oracle", "db2"])),
    ],
)
CONFLICTS = {"/properties/environment": [{"location": "/properties/environment/default", "value": "uat", "suggested_value": "test"}]}
POINTERS = {"/properties/asset_type", "/properties/environment", "/properties/engine", "/properties/status"}


def test_markdown_sections():
    md = render_markdown(REPORT, POINTERS, CONFLICTS)

    assert md.startswith("# Enumeration review: db.schema.json\n")
    assert "| Same | 1 |" in md and "| Similar | 1 |" in md and "| Different | 1 |" in md
    # Table cells escape pipes so the row doesn't break.
    assert "Value is in asset_types \\| exact." in md
    assert "- **Value changes:** `uat` → `test`" in md
    assert '```json\n{\n  "enum": [' in md
    assert "| `/properties/environment/default` | `uat` | change it to `test`; remove it; keep it and add `uat`" in md
    assert '```http\nPOST http://127.0.0.1:8000/api/enumerations\n' in md
    assert "did not report on: `/properties/status`" in md


def test_markdown_empty_sections():
    md = render_markdown(ComparisonReport(schema_path="x.json", summary="Nothing.", findings=[]), set(), {})
    assert md.count("None.") == 3
