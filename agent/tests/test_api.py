import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from enum_agent import api
from enum_agent.models import ComparisonReport
from enum_agent.service import Analysis, AnalysisError

SCHEMA = {"title": "Thing", "properties": {"environment": {"enum": ["dev", "prod"]}}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "SCHEMAS_DIR", tmp_path.resolve())
    monkeypatch.setattr(api, "OUTPUT_PATH", tmp_path / "out" / "output.md")
    (tmp_path / "thing.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    return TestClient(api.app)


def test_list_schemas(client):
    schemas = {s["name"]: s for s in client.get("/api/schemas").json()}
    assert schemas["thing.json"]["enum_attribute_count"] == 1
    assert schemas["thing.json"]["title"] == "Thing"
    assert schemas["broken.json"]["error"].startswith("Not a valid JSON Schema")


def test_get_schema(client):
    body = client.get("/api/schemas/thing.json").json()
    assert body["enum_attributes"][0]["pointer"] == "/properties/environment"
    assert json.loads(body["content"]) == SCHEMA
    assert client.get("/api/schemas/missing.json").status_code == 404


@pytest.mark.parametrize("name", ["../secret.json", "..%2Fsecret.json", "notes.txt"])
def test_rejects_names_outside_the_folder(client, name):
    assert client.get(f"/api/schemas/{name}").status_code in (400, 404)
    assert client.post("/api/schemas", json={"name": name, "content": "{}"}).status_code in (400, 422)


def test_upload(client):
    r = client.post("/api/schemas", json={"name": "new.json", "content": json.dumps(SCHEMA)})
    assert r.status_code == 201 and r.json()["enum_attribute_count"] == 1
    assert client.post("/api/schemas", json={"name": "new.json", "content": "{}"}).status_code == 409
    assert client.post("/api/schemas", json={"name": "bad.json", "content": "[1, 2]"}).status_code == 422


def test_analysis_returns_report_and_markdown(client, monkeypatch):
    async def fake_analyze(path):
        report = ComparisonReport(schema_path=str(path), summary="All good.", findings=[])
        return Analysis(report, set(), {}, "test-model", 1.23)

    monkeypatch.setattr(api, "analyze", fake_analyze)
    body = client.post("/api/analyses", json={"schema_name": "thing.json"}).json()
    assert body["summary"] == "All good."
    assert body["model"] == "test-model"
    assert body["markdown"].startswith("# Enumeration review: thing.json")
    assert body["output_error"] is None
    assert Path(body["output_path"]).read_text(encoding="utf-8") == body["markdown"]


def test_report_defaults_to_project_root():
    from enum_agent.service import DEFAULT_OUTPUT_PATH

    project_root = Path(__file__).resolve().parents[2]
    assert DEFAULT_OUTPUT_PATH == project_root / "output.md"
    assert (project_root / "rdaas_app").is_dir() and (project_root / "agent").is_dir()


def test_analysis_errors(client, monkeypatch):
    async def failing(path):
        raise AnalysisError("bad schema")

    monkeypatch.setattr(api, "analyze", failing)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert client.post("/api/analyses", json={"schema_name": "thing.json"}).status_code == 422
    assert client.post("/api/analyses", json={"schema_name": "missing.json"}).status_code == 404
