import os
import tempfile

# Point the app at a throwaway database before it is imported.
_tmpdir = tempfile.mkdtemp()
os.environ["ENUM_DB_URL"] = f"sqlite:///{os.path.join(_tmpdir, 'test.db')}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _create_env():
    return client.post(
        "/api/enumerations",
        json={"name": "environment", "description": "Deploy targets", "values": ["dev", "test", "prod"]},
    )


def test_create_and_get():
    r = _create_env()
    assert r.status_code == 201
    assert r.json()["values"] == ["dev", "test", "prod"]

    r = client.get("/api/enumerations/environment")
    assert r.status_code == 200
    assert r.json()["description"] == "Deploy targets"


def test_duplicate_name_rejected():
    _create_env()
    assert _create_env().status_code == 409


def test_invalid_payloads():
    assert client.post("/api/enumerations", json={"name": "x", "values": []}).status_code == 422
    assert client.post("/api/enumerations", json={"name": "x", "values": ["a", "a"]}).status_code == 422
    assert client.post("/api/enumerations", json={"name": "1bad", "values": ["a"]}).status_code == 422


def test_update_rename_and_replace_values():
    _create_env()
    r = client.put("/api/enumerations/environment", json={"name": "env", "values": ["prod", "dev", "staging"]})
    assert r.status_code == 200
    assert r.json()["name"] == "env"
    assert r.json()["values"] == ["prod", "dev", "staging"]
    assert r.json()["description"] == "Deploy targets"
    assert client.get("/api/enumerations/environment").status_code == 404


def test_update_clears_description():
    _create_env()
    r = client.put("/api/enumerations/environment", json={"description": None})
    assert r.json()["description"] is None


def test_add_and_remove_value():
    _create_env()
    r = client.post("/api/enumerations/environment/values", json={"value": "staging"})
    assert r.status_code == 201
    assert r.json()["values"] == ["dev", "test", "prod", "staging"]
    assert client.post("/api/enumerations/environment/values", json={"value": "dev"}).status_code == 409

    r = client.delete("/api/enumerations/environment/values/test")
    assert r.json()["values"] == ["dev", "prod", "staging"]


def test_validate():
    _create_env()
    assert client.get("/api/enumerations/environment/validate", params={"value": "prod"}).json()["valid"] is True
    assert client.get("/api/enumerations/environment/validate", params={"value": "qa"}).json()["valid"] is False


def test_delete():
    _create_env()
    assert client.delete("/api/enumerations/environment").status_code == 204
    assert client.get("/api/enumerations").json() == []
