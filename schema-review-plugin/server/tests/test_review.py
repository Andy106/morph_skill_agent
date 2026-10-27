import asyncio
import json

import pytest

from schema_review import review
from schema_review.review import Finding, ProposedEnumeration, ValueMapping

ENUMS = [
    {"name": "environment", "description": "Envs", "values": ["dev", "test", "prod"]},
    {"name": "asset_types", "description": "Assets", "values": ["Database Instance", "Web Server Instance"]},
]

SCHEMA = {
    "title": "DB",
    "properties": {
        "asset_type": {"const": "Database Instance"},
        "env": {"description": "Deployment environment.", "type": "string", "enum": ["dev", "uat", "prod"], "default": "uat"},
        "engine": {"enum": ["oracle", "db2"]},
    },
    "examples": [{"env": "uat"}],
}


@pytest.fixture
def schema_file(tmp_path):
    path = tmp_path / "db.schema.json"
    path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    return path


def good_findings():
    return [
        Finding(attribute="asset_type", schema_pointer="/properties/asset_type", status="same",
                matched_enumeration="asset_types", explanation="Const value is in asset_types."),
        Finding(attribute="env", schema_pointer="/properties/env", status="similar", matched_enumeration="environment",
                explanation="uat corresponds to test.",
                proposed_schema_fragment={"enum": ["dev", "test", "prod"], "x-enumeration": "environment"},
                value_mapping=[ValueMapping(schema_value="uat", enumeration_value="test")]),
        Finding(attribute="engine", schema_pointer="/properties/engine", status="different", explanation="No engines enum.",
                proposed_enumeration=ProposedEnumeration(name="engine", description="DB engines", values=["oracle", "db2"])),
    ]


def run(schema_file, findings, tmp_path):
    return review.finalize(str(schema_file), "1 same, 1 similar, 1 different.", findings, str(tmp_path / "out" / "output.md"), ENUMS)


def test_clean_review_writes_report(schema_file, tmp_path):
    result = run(schema_file, good_findings(), tmp_path)

    assert result["warnings"] == []
    assert result["counts"] == {"same": 1, "similar": 1, "different": 1}
    similar = result["similar"][0]
    # Keywords the proposal left out are kept, and the invalid default/example are flagged with the mapped value.
    assert similar["replacement"] == {
        "description": "Deployment environment.", "type": "string", "enum": ["dev", "test", "prod"],
        "default": "uat", "x-enumeration": "environment",
    }
    assert {(c["location"], c["suggested_value"]) for c in similar["value_conflicts"]} == {
        ("/examples/0/env", "test"), ("/properties/env/default", "test"),
    }

    md = (tmp_path / "out" / "output.md").read_text(encoding="utf-8")
    assert md.startswith("# Enumeration review: db.schema.json")
    assert "| `/properties/env/default` | `uat` | change it to `test`; remove it;" in md
    assert "Checks that did not pass" not in md


def test_wrong_claims_are_flagged(schema_file, tmp_path):
    findings = good_findings()
    findings[0] = Finding(attribute="env", schema_pointer="/properties/env", status="same",
                          matched_enumeration="environment", explanation="wrong")
    findings[1] = Finding(attribute="engine", schema_pointer="/properties/engine", status="different", explanation="dup")
    findings[2] = Finding(attribute="x", schema_pointer="/properties/nope", status="different", explanation="bogus",
                          proposed_enumeration=ProposedEnumeration(name="environment", description="", values=["a"]))

    warnings = run(schema_file, findings, tmp_path)["warnings"]
    text = "\n".join(warnings)
    assert "marked same, but its values differ" in text
    assert "/properties/engine` is marked different but has no proposed_enumeration" in text
    assert "/properties/nope` is not an enum/const attribute" in text
    assert "/properties/asset_type` has no finding" in text
    # The report still gets written, with the failed checks at the top.
    assert "Checks that did not pass" in (tmp_path / "out" / "output.md").read_text(encoding="utf-8")


def test_similar_checks(schema_file, tmp_path):
    findings = good_findings()
    findings[1] = findings[1].model_copy(update={
        "proposed_schema_fragment": {"enum": ["prod", "dev", "test"]},
        "value_mapping": [ValueMapping(schema_value="uat", enumeration_value="staging")],
    })
    findings[2] = findings[2].model_copy(update={
        "proposed_enumeration": ProposedEnumeration(name="1engine", description="", values=["oracle"]),
    })
    text = "\n".join(run(schema_file, findings, tmp_path)["warnings"])
    assert "not the values of 'environment' in its order" in text
    assert "maps 'uat' to 'staging'" in text
    assert "'1engine' is not allowed" in text
    assert "lists ['oracle'], not the schema's values" in text


def test_relative_paths_are_refused(schema_file, tmp_path):
    with pytest.raises(ValueError, match="absolute path"):
        review.finalize("db.schema.json", "", [], str(tmp_path / "o.md"), ENUMS)
    with pytest.raises(ValueError, match="absolute path"):
        review.finalize(str(schema_file), "", [], "output.md", ENUMS)


def test_server_exposes_the_tools():
    from schema_review.server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert set(tools) == {"get_enumerations", "read_json_schema", "compare_values", "finalize_review"}
    params = tools["finalize_review"].input_schema
    assert set(params["required"]) == {"schema_path", "summary", "findings", "output_path"}
