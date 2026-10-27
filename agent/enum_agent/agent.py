import json
import os

from agents import Agent, function_tool

from . import tools
from .models import ComparisonReport

INSTRUCTIONS = """\
You review JSON Schemas against the enumerations defined in the Enumeration Manager application.

Steps:
1. Call read_json_schema with the path you are given. It lists every attribute constrained by `enum` or `const`.
2. Call get_defined_enumerations to get the application's enumerations.
3. For each schema attribute, look for an application enumeration that represents the same concept. Signals:
   an `x_enumeration` hint, a similar name (e.g. env ~ environment, asset_type ~ asset_types), or overlapping
   or synonymous values. Call compare_values for every plausible candidate before deciding. A similar name alone
   is not enough if the values describe a different concept.
4. Classify every attribute returned by read_json_schema exactly once:
   - "same": the attribute's values are exactly the enumeration's values (order does not matter), or the attribute
     is a `const` whose value is exactly one of the values of an enumeration for the same concept.
     Just confirm it; both proposal fields are null.
   - "similar": an enumeration represents the same concept but the values or spelling differ (case or separators,
     abbreviations such as dev/development, synonyms such as uat/test, missing or extra values).
     Propose changing the schema to match the enumeration: set proposed_schema_fragment to the complete
     replacement JSON for that attribute, keeping its other keywords, using the enumeration's values verbatim
     and in its order, and adding "x-enumeration": "<enumeration name>". In the explanation, say which schema
     values would be renamed or dropped, so the user can decide whether to extend the enumeration instead.
     Also fill value_mapping: for each schema value not in the enumeration, the enumeration value it
     corresponds to (e.g. uat -> test), or null if it has no counterpart and would be dropped.
   - "different": no enumeration represents the concept. Propose adding one: a snake_case name derived from the
     attribute (prefix generic nested names with their parent, e.g. storage/type -> storage_type), a short
     description, and the schema's values verbatim.
5. Never invent enumeration names or values; use only what the tools return. Copy schema_pointer exactly.
6. Write a one-paragraph summary with the counts of same, similar and different attributes.
"""


@function_tool
def read_json_schema(path: str) -> str:
    """Read a JSON Schema file and list every attribute constrained by `enum` or `const`.

    Args:
        path: Path to the JSON Schema file.
    """
    schema = tools.load_schema(path)
    return json.dumps(
        {"title": schema.get("title"), "enum_attributes": tools.extract_enum_attributes(schema)}, indent=2
    )


@function_tool
def get_defined_enumerations() -> str:
    """List all enumerations defined in the Enumeration Manager application, with their allowed values."""
    return json.dumps(tools.fetch_enumerations(), indent=2)


@function_tool
def compare_values(schema_values: list[str], enumeration_name: str) -> str:
    """Compare a schema attribute's values with one application enumeration's values.

    Args:
        schema_values: The attribute's values from the JSON Schema.
        enumeration_name: Name of the application enumeration to compare against.
    """
    enums = {e["name"]: e for e in tools.fetch_enumerations()}
    if enumeration_name not in enums:
        return json.dumps({"error": f"No enumeration named '{enumeration_name}'", "available": sorted(enums)})
    enum_values = enums[enumeration_name]["values"]
    return json.dumps(
        {"enumeration": enumeration_name, "enumeration_values": enum_values, **tools.diff_values(schema_values, enum_values)},
        indent=2,
    )


def build_agent(model: str | None = None) -> Agent:
    return Agent(
        name="Enumeration Schema Reviewer",
        instructions=INSTRUCTIONS,
        tools=[read_json_schema, get_defined_enumerations, compare_values],
        output_type=ComparisonReport,
        model=model or os.getenv("OPENAI_MODEL") or None,
    )
