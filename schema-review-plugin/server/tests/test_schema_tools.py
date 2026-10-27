from schema_review.schema_tools import (
    diff_values,
    extract_enum_attributes,
    find_value_conflicts,
    merge_schema_fragment,
    resolve_pointer,
)

SCHEMA = {
    "title": "Database Instance",
    "properties": {
        "asset_type": {"const": "Database Instance", "x-enumeration": "asset_types"},
        "environment": {"type": "string", "enum": ["dev", "test", "prod"], "x-enumeration": "environment"},
        "storage": {"properties": {"type": {"enum": ["ASM", "filesystem"]}}},
        "ha": {"properties": {"rac_enabled": {"type": "boolean"}}},
    },
    "allOf": [{"if": {"properties": {"ha": {"properties": {"rac_enabled": {"const": True}}}}}, "then": {}}],
}


def test_extracts_enum_and_const_attributes():
    attrs = {a["pointer"]: a for a in extract_enum_attributes(SCHEMA)}

    assert attrs["/properties/environment"]["values"] == ["dev", "test", "prod"]
    assert attrs["/properties/environment"]["x_enumeration"] == "environment"
    assert attrs["/properties/asset_type"]["kind"] == "const"
    assert attrs["/properties/storage/properties/type"]["attribute"] == "type"
    # The `const: true` inside the allOf/if condition is a test, not an attribute.
    assert not any("/if" in p for p in attrs)


def test_non_string_values_are_rendered_as_json():
    attrs = extract_enum_attributes({"properties": {"level": {"enum": [1, 2, True, None]}}})
    assert attrs[0]["values"] == ["1", "2", "true", "null"]


def test_diff_identical_ignores_order():
    d = diff_values(["prod", "dev", "test"], ["dev", "test", "prod"])
    assert d["identical"] and not d["only_in_schema"]


def test_diff_similar_values():
    d = diff_values(["dev", "uat", "prod"], ["dev", "test", "prod"])
    assert not d["identical"]
    assert d["only_in_schema"] == ["uat"]
    assert d["only_in_enumeration"] == ["test"]

    d = diff_values(["Development", "PROD"], ["dev", "prod"])
    assert {m["schema_value"] for m in d["close_matches"]} == {"Development", "PROD"}


def test_diff_ignoring_case_and_separators():
    assert diff_values(["Database-Instance"], ["database_instance"])["identical_ignoring_case_and_separators"]


def test_resolve_pointer():
    assert resolve_pointer(SCHEMA, "/properties/storage/properties/type") == {"enum": ["ASM", "filesystem"]}
    assert resolve_pointer({"properties": {"a/b": {"const": 1}}}, "/properties/a~1b") == {"const": 1}
    assert resolve_pointer(SCHEMA, "/") is SCHEMA


def test_merge_keeps_omitted_keywords():
    original = {"description": "Deployment environment.", "type": "string", "enum": ["dev", "uat", "prod"], "default": "dev"}
    proposed = {"type": "string", "enum": ["dev", "test", "prod"], "x-enumeration": "environment"}
    assert merge_schema_fragment(original, proposed) == {
        "description": "Deployment environment.",
        "type": "string",
        "enum": ["dev", "test", "prod"],
        "default": "dev",
        "x-enumeration": "environment",
    }


def test_merge_switching_const_to_enum_drops_const():
    merged = merge_schema_fragment({"const": "DB Instance", "description": "d"}, {"enum": ["Database Instance"]})
    assert merged == {"description": "d", "enum": ["Database Instance"]}


def test_value_conflicts_in_defaults_and_examples():
    schema = {
        "properties": {
            "environment": {"enum": ["dev", "uat", "prod"], "default": "uat", "examples": ["dev", "uat"]},
            "deployments": {
                "type": "array",
                "default": [{"env": "uat"}, {"env": "prod"}],
                "items": {"properties": {"env": {"enum": ["dev", "uat", "prod"]}}},
            },
        },
        "examples": [{"environment": "uat", "deployments": [{"env": "dev"}, {"env": "uat"}]}, {"environment": "prod"}],
    }
    fragment = {"enum": ["dev", "test", "prod"]}
    merged = merge_schema_fragment(schema["properties"]["environment"], fragment)

    # The kept default and examples are judged against the new values, as are the root examples.
    assert find_value_conflicts(schema, "/properties/environment", merged) == [
        {"location": "/examples/0/environment", "value": "uat"},
        {"location": "/properties/environment/default", "value": "uat"},
        {"location": "/properties/environment/examples/1", "value": "uat"},
    ]
    # If the proposal itself fixes the default, only the examples remain.
    assert len(find_value_conflicts(schema, "/properties/environment", {**merged, "default": "dev"})) == 2

    assert find_value_conflicts(schema, "/properties/deployments/items/properties/env", fragment) == [
        {"location": "/examples/0/deployments/1/env", "value": "uat"},
        {"location": "/properties/deployments/default/0/env", "value": "uat"},
    ]


def test_no_conflicts_when_values_still_allowed():
    schema = {"properties": {"environment": {"enum": ["dev", "prod"], "default": "dev"}}, "examples": [{"environment": "prod"}]}
    assert find_value_conflicts(schema, "/properties/environment", {"enum": ["dev", "test", "prod"], "default": "dev"}) == []


def test_conflicts_under_defs_ignore_root_examples():
    schema = {"$defs": {"env": {"enum": ["uat"], "default": "uat"}}, "examples": [{"env": "uat"}]}
    assert find_value_conflicts(schema, "/$defs/env", {"enum": ["test"], "default": "uat"}) == [
        {"location": "/$defs/env/default", "value": "uat"}
    ]
