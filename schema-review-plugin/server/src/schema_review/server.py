"""MCP server exposing the schema review tools to Claude Code (stdio transport)."""

from mcp.server.mcpserver import MCPServer

from . import review
from . import schema_tools as st
from .review import Finding

mcp = MCPServer(
    "schema-review",
    version="0.1.0",
    instructions=(
        "Tools for reviewing a JSON Schema's enum/const attributes against the enumerations defined in the "
        "Enumeration Manager app. Follow the review-schema skill: read_json_schema, get_enumerations, "
        "compare_values for each plausible match, then finalize_review with one finding per attribute. "
        "All paths must be absolute."
    ),
)


@mcp.tool()
def get_enumerations() -> list[dict]:
    """List every enumeration defined in the Enumeration Manager app, with its allowed values in order."""
    return st.fetch_enumerations()


@mcp.tool()
def read_json_schema(path: str) -> dict:
    """Read a JSON Schema file and list every attribute constrained by `enum` or `const`, including nested ones.

    Args:
        path: Absolute path to the JSON Schema file.
    """
    schema = st.load_schema(review.require_absolute(path, "schema path"))
    return {
        "title": schema.get("title"),
        "description": schema.get("description"),
        "enum_attributes": st.extract_enum_attributes(schema),
    }


@mcp.tool()
def compare_values(schema_values: list[str], enumeration_name: str) -> dict:
    """Compare a schema attribute's values with one app enumeration: exact match, values on each side only,
    and near-misses (case, separators, prefixes such as dev/development).

    Args:
        schema_values: The attribute's values, as read_json_schema returned them.
        enumeration_name: Name of the app enumeration to compare against.
    """
    enums = {e["name"]: e for e in st.fetch_enumerations()}
    if enumeration_name not in enums:
        raise ValueError(f"No enumeration named '{enumeration_name}'. Available: {sorted(enums)}")
    values = enums[enumeration_name]["values"]
    return {"enumeration": enumeration_name, "enumeration_values": values, **st.diff_values(schema_values, values)}


@mcp.tool()
def finalize_review(schema_path: str, summary: str, findings: list[Finding], output_path: str) -> dict:
    """Check the findings, complete them, and write the Markdown report. Call once all attributes are classified.

    Checks every finding against the schema and the app (e.g. 'same' values really match, proposed blocks use the
    enumeration's values, proposed names are valid and new, no attribute is missing) and returns any problems
    under `warnings`: fix those findings and call again, which overwrites the file. For each 'similar' finding
    it returns the complete replacement block (keywords left out of the proposal are kept) and any `default` or
    `examples` values that the new values would make invalid.

    Args:
        schema_path: Absolute path to the reviewed JSON Schema file.
        summary: One paragraph with the counts of same, similar and different attributes.
        findings: One finding per attribute returned by read_json_schema.
        output_path: Absolute path of the Markdown report to write, normally <working directory>/output.md.
    """
    return review.finalize(schema_path, summary, findings, output_path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
