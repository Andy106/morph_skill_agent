# Enumeration Manager app (`rdaas_app`)

A REST API and web UI for creating, editing and deleting named enumerations, e.g. `environment` → `dev`, `test`,
`prod`. The schema review agent and the schema-review Claude Code plugin both check JSON Schemas against the
enumerations defined here.

```
backend/     FastAPI + SQLAlchemy + SQLite API (port 8000; database: backend/enums.db, created on first run)
frontend/    React + Vite UI (port 5173)
```

No authentication or authorization is in place yet.

## Backend (port 8000)

```bash
cd rdaas_app/backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

Set `ENUM_DB_URL` to use a different database file, e.g. `sqlite:///./other.db`.

A virtual environment only works where it was created. If you move or rename the folder, delete `.venv` and create
it again with the steps above.

## Frontend (port 5173)

```bash
cd rdaas_app/frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server forwards `/api` requests to the backend, so start the backend first.

In the UI you can:
- filter the list of enumerations
- create, rename, describe and delete enumerations
- add, remove and reorder values
- test whether a value is valid for an enumeration

## Tests

```bash
cd rdaas_app/backend
pytest
```

The tests use a temporary database, so they never touch `enums.db`.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/enumerations` | List all enumerations |
| POST | `/api/enumerations` | Create `{name, description?, values[]}` |
| GET | `/api/enumerations/{name}` | Get one enumeration |
| PUT | `/api/enumerations/{name}` | Update any of `name`, `description`, `values` (values replaces the full list; fields left out are unchanged) |
| DELETE | `/api/enumerations/{name}` | Delete an enumeration |
| POST | `/api/enumerations/{name}/values` | Add one value `{value}` |
| DELETE | `/api/enumerations/{name}/values/{value}` | Remove one value |
| GET | `/api/enumerations/{name}/validate?value=x` | Check whether `x` is an allowed value |

Rules:
- Names start with a letter, contain only letters, digits, `_` or `-`, and are unique.
- Each enumeration has at least one value.
- Values are trimmed, non-blank and unique within the enumeration, and they keep their order.

Breaking a rule returns `422`, except removing an enumeration's last value, which returns `400`.
A duplicate name or value returns `409`. An unknown enumeration or value returns `404`.

### Example

```bash
curl -X POST http://127.0.0.1:8000/api/enumerations \
  -H "Content-Type: application/json" \
  -d '{"name":"environment","values":["dev","test","prod"]}'

curl "http://127.0.0.1:8000/api/enumerations/environment/validate?value=prod"
# {"enumeration":"environment","value":"prod","valid":true}
```
