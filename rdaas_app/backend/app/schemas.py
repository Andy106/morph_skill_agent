from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_\-]*$"


def _clean_values(values: list[str]) -> list[str]:
    cleaned = [v.strip() for v in values]
    if any(not v for v in cleaned):
        raise ValueError("values must not be blank")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("values must be unique")
    return cleaned


class EnumerationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=NAME_PATTERN)
    description: str | None = Field(default=None, max_length=500)
    values: list[str] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _validate_values(cls, values: list[str]) -> list[str]:
        return _clean_values(values)


class EnumerationUpdate(BaseModel):
    """Partial update: any field left out is kept as-is. `values` replaces the full list."""

    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=NAME_PATTERN)
    description: str | None = Field(default=None, max_length=500)
    values: list[str] | None = Field(default=None, min_length=1)

    @field_validator("values")
    @classmethod
    def _validate_values(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_values(values)


class ValueIn(BaseModel):
    value: str = Field(min_length=1, max_length=200)

    @field_validator("value")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("value must not be blank")
        return v


class ValidationResult(BaseModel):
    enumeration: str
    value: str
    valid: bool


class EnumerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    values: list[str]
    created_at: datetime
    updated_at: datetime

    @field_validator("values", mode="before")
    @classmethod
    def _flatten(cls, values):
        return [v if isinstance(v, str) else v.value for v in values]
