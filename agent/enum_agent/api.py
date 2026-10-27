"""Web API for the schema review agent. Run with: uvicorn enum_agent.api:app --port 8001"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import tools
from .service import DEFAULT_OUTPUT_PATH, AnalysisError, analyze, resolve_model

SCHEMAS_DIR = Path(os.getenv("SCHEMAS_DIR") or Path(__file__).resolve().parents[2] / "schemas").resolve()
OUTPUT_PATH = DEFAULT_OUTPUT_PATH

app = FastAPI(title="Schema Review Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SchemaUpload(BaseModel):
    name: str = Field(min_length=6, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._()\-]*\.[jJ][sS][oO][nN]$")
    content: str = Field(min_length=2)


class AnalysisRequest(BaseModel):
    schema_name: str


def _schema_path(name: str) -> Path:
    """Resolve a schema file name inside SCHEMAS_DIR, refusing anything that points elsewhere."""
    path = (SCHEMAS_DIR / name).resolve()
    if Path(name).name != name or path.parent != SCHEMAS_DIR or path.suffix.lower() != ".json":
        raise HTTPException(status_code=400, detail=f"Invalid schema name '{name}'")
    return path


def _describe(path: Path) -> dict:
    info = {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "title": None,
        "description": None,
        "enum_attribute_count": None,
        "error": None,
    }
    try:
        schema = tools.load_schema(path)
        info["title"] = schema.get("title")
        info["description"] = schema.get("description")
        info["enum_attribute_count"] = len(tools.extract_enum_attributes(schema))
    except (ValueError, OSError) as e:
        info["error"] = f"Not a valid JSON Schema: {e}"
    return info


@app.get("/api/status")
def status():
    try:
        tools.fetch_enumerations()
        enum_api_error = None
    except tools.EnumApiError as e:
        enum_api_error = str(e)
    return {
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "model": resolve_model(),
        "enum_api_url": tools.API_URL,
        "enum_api_reachable": enum_api_error is None,
        "enum_api_error": enum_api_error,
        "schemas_dir": str(SCHEMAS_DIR),
    }


@app.get("/api/schemas")
def list_schemas():
    if not SCHEMAS_DIR.is_dir():
        return []
    return [_describe(p) for p in sorted(SCHEMAS_DIR.glob("*.json"), key=lambda p: p.name.lower())]


@app.get("/api/schemas/{name}")
def get_schema(name: str):
    path = _schema_path(name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")
    info = _describe(path)
    info["content"] = path.read_text(encoding="utf-8")
    info["enum_attributes"] = [] if info["error"] else tools.extract_enum_attributes(tools.load_schema(path))
    return info


@app.post("/api/schemas", status_code=201)
def upload_schema(payload: SchemaUpload):
    path = _schema_path(payload.name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"A schema named '{payload.name}' already exists")
    try:
        if not isinstance(json.loads(payload.content), dict):
            raise ValueError("the top level must be a JSON object")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Not a valid JSON Schema: {e}") from e
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.content, encoding="utf-8")
    return _describe(path)


@app.post("/api/analyses")
async def run_analysis(payload: AnalysisRequest):
    path = _schema_path(payload.schema_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Schema '{payload.schema_name}' not found")
    try:
        analysis = await analyze(path)
    except AnalysisError as e:
        # A missing key or unreachable app is a server problem (503); anything else is a bad schema (422).
        unavailable = isinstance(e.__cause__, tools.EnumApiError) or not os.getenv("OPENAI_API_KEY")
        raise HTTPException(status_code=503 if unavailable else 422, detail=str(e)) from e
    except Exception as e:  # model or network failure inside the agent run
        raise HTTPException(status_code=502, detail=f"The agent run failed: {e}") from e
    # Like the command line, each run also saves the report to output.md in the project root.
    try:
        output_path, output_error = str(analysis.write_markdown(OUTPUT_PATH)), None
    except OSError as e:
        output_path, output_error = None, f"Could not write the report to {OUTPUT_PATH}: {e}"
    return {
        **analysis.to_dict(),
        "schema_name": path.name,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "markdown": analysis.markdown(),
        "output_path": output_path,
        "output_error": output_error,
    }
