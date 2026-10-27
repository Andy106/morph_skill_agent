from typing import Literal

from pydantic import BaseModel, Field

# No field defaults: the Agents SDK uses strict structured output, where every field must be required.


class ProposedEnumeration(BaseModel):
    name: str = Field(description="New enumeration name, matching ^[A-Za-z][A-Za-z0-9_-]*$ (snake_case preferred).")
    description: str
    values: list[str]


class ValueMapping(BaseModel):
    schema_value: str
    enumeration_value: str | None = Field(description="The enumeration value it corresponds to, or null if it would be dropped.")


class AttributeFinding(BaseModel):
    attribute: str = Field(description="Attribute name as it appears in the schema.")
    schema_pointer: str = Field(description="JSON Pointer to the attribute, exactly as returned by read_json_schema.")
    schema_values: list[str]
    status: Literal["same", "similar", "different"]
    matched_enumeration: str | None = Field(description="Name of the matching app enumeration; null when 'different'.")
    explanation: str = Field(description="One or two sentences on why this status was chosen.")
    proposed_schema_fragment: str | None = Field(
        description="Only for 'similar': the full replacement JSON for this attribute's schema, as JSON text. Otherwise null."
    )
    value_mapping: list[ValueMapping] | None = Field(
        description="Only for 'similar': one entry per schema value that is not already in the enumeration. Otherwise null."
    )
    proposed_enumeration: ProposedEnumeration | None = Field(
        description="Only for 'different': the enumeration to add to the app. Otherwise null."
    )


class ComparisonReport(BaseModel):
    schema_path: str
    summary: str
    findings: list[AttributeFinding]
