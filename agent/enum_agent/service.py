"""The full analysis pipeline, shared by the command line and the web API."""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from agents import Runner
from agents.models import get_default_model

from . import tools
from .agent import build_agent
from .markdown import render_markdown
from .models import ComparisonReport


# The report goes to the project root (the folder holding agent/, rdaas_app/ and schemas/), wherever the agent runs from.
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "output.md"


class AnalysisError(Exception):
    """Inputs are unusable (missing file, invalid schema, no API key, app unreachable). Raised before calling the model."""


@dataclass
class Analysis:
    report: ComparisonReport
    expected_pointers: set[str]
    conflicts: dict[str, list[dict]]
    model: str
    duration_seconds: float

    @property
    def missing_pointers(self) -> list[str]:
        return sorted(self.expected_pointers - {f.schema_pointer for f in self.report.findings})

    def markdown(self) -> str:
        return render_markdown(self.report, self.expected_pointers, self.conflicts)

    def write_markdown(self, path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
        """Write the Markdown report, overwriting any previous one. Raises OSError if it can't be written."""
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.markdown(), encoding="utf-8")
        return path

    def to_dict(self) -> dict:
        data = self.report.model_dump()
        for finding in data["findings"]:
            finding["value_conflicts"] = self.conflicts.get(finding["schema_pointer"], [])
        data["missing_pointers"] = self.missing_pointers
        data["model"] = self.model
        data["duration_seconds"] = round(self.duration_seconds, 1)
        return data


def complete_fragments(report: ComparisonReport, schema: dict) -> dict[str, list[dict]]:
    """Restore any keywords (description, default, ...) the model left out of a proposed replacement,
    then find defaults/examples the replacement would make invalid. Returns conflicts keyed by schema_pointer."""
    conflicts: dict[str, list[dict]] = {}
    for f in report.findings:
        if f.status != "similar" or not f.proposed_schema_fragment:
            continue
        try:
            original = tools.resolve_pointer(schema, f.schema_pointer)
            proposed = json.loads(f.proposed_schema_fragment)
        except (KeyError, IndexError, ValueError):
            continue  # unknown pointer or non-JSON fragment: show the model's text as-is
        if not (isinstance(original, dict) and isinstance(proposed, dict)):
            continue
        merged = tools.merge_schema_fragment(original, proposed)
        f.proposed_schema_fragment = json.dumps(merged)

        mapping = {m.schema_value: m.enumeration_value for m in f.value_mapping or []}
        found = tools.find_value_conflicts(schema, f.schema_pointer, merged)
        for c in found:
            c["suggested_value"] = mapping.get(c["value"])
        if found:
            conflicts[f.schema_pointer] = found
    return conflicts


def resolve_model(model: str | None = None) -> str:
    return model or os.getenv("OPENAI_MODEL") or get_default_model()


async def analyze(schema_path: str | Path, model: str | None = None) -> Analysis:
    schema_path = Path(schema_path).resolve()
    if not schema_path.is_file():
        raise AnalysisError(f"Schema file not found: {schema_path}")
    if not os.getenv("OPENAI_API_KEY"):
        raise AnalysisError("OPENAI_API_KEY is not set (add it to agent/.env).")

    # Fail fast, before spending tokens, if the inputs are unusable.
    try:
        schema = tools.load_schema(schema_path)
        expected = {a["pointer"] for a in tools.extract_enum_attributes(schema)}
        tools.fetch_enumerations()
    except (ValueError, tools.EnumApiError) as e:
        raise AnalysisError(str(e)) from e

    model = resolve_model(model)
    started = time.monotonic()
    if not expected:
        report = ComparisonReport(
            schema_path=str(schema_path),
            summary="The schema has no enum or const attributes, so there is nothing to compare.",
            findings=[],
        )
        return Analysis(report, expected, {}, model, 0.0)

    result = await Runner.run(build_agent(model), f"Review the JSON Schema at: {schema_path}")
    report: ComparisonReport = result.final_output
    conflicts = complete_fragments(report, schema)
    return Analysis(report, expected, conflicts, model, time.monotonic() - started)
