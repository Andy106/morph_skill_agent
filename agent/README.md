# Schema review agent (`agent`)

An AI agent built on the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/). It reads a JSON Schema,
finds every attribute constrained by `enum` or `const`, and compares each one with the enumerations in the
Enumeration Manager app (`rdaas_app`):

- **Same:** the values match an existing enumeration. The agent confirms it.
- **Similar:** the same concept with different values or spelling (e.g. `dev, uat, prod` vs `dev, test, prod`).
  The agent proposes a replacement block for that attribute. The block keeps the attribute's other keywords
  (description, default, …), uses the enumeration's values, and adds `"x-enumeration": "<name>"`.
- **Different:** no matching enumeration. The agent proposes a new enumeration and prints the
  `POST /api/enumerations` request to create it.

For "similar" attributes, the agent also flags any `default` or `examples` value in the schema that the new values
would make invalid, with options to choose from:

```
! With the new values, these defaults/examples in the schema would become invalid. Decide how to handle each one:
  /properties/environment/default = "uat"
    Options: change it to "test" | remove it | keep it and add "uat" to the 'environment' enumeration instead
```

The agent only proposes changes. It never edits the schema or the app.

You can use it from the command line or a web UI. Both write the report to **`output.md` in the project root**
(the folder that holds `agent/`, `rdaas_app/` and `schemas/`), overwriting the previous one.

```
enum_agent/   the agent: command line (python -m enum_agent) and web API (port 8001)
frontend/     React + Vite web UI (port 5174)
tests/        unit tests (no API key needed)
```

## Setup

The Enumeration Manager backend must be running (see `rdaas_app/README.md`).

```bash
cd agent
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Use the same Python for creating the environment and installing into it. If `pip install` was run with a different
Python, you'll get import errors such as `cannot import name 'ArgsKwargs' from 'pydantic_core'`. Fix it by deleting
`.venv` and creating it again.

Create `agent/.env` (it is git-ignored):

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-luna
# ENUM_API_URL=http://127.0.0.1:8000
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API key (required) | none |
| `OPENAI_MODEL` | Model to use; `--model` overrides it | the SDK's default |
| `ENUM_API_URL` | Where the Enumeration Manager API is running | `http://127.0.0.1:8000` |
| `SCHEMAS_DIR` | Folder the web UI lists schemas from | `schemas/` in the project root |

The `.env` file is loaded wherever you run the agent from. Variables already set in your shell take precedence over it.

## Command line

```bash
cd agent
python -m enum_agent ..\schemas\database-instance.schema-2.json
python -m enum_agent ..\schemas\database-instance.schema-2.json --json          # machine-readable report
python -m enum_agent ..\schemas\database-instance.schema-2.json --model <name>  # override OPENAI_MODEL
python -m enum_agent ..\schemas\database-instance.schema-2.json --output reports\schema-2.md
pytest                                                                          # unit tests
```

The report goes to `output.md` in the project root unless `--output` names another file. A relative `--output` path
is resolved against the current folder.

The agent stops before calling the model if the schema file is missing or invalid, the API key isn't set, or the
Enumeration Manager can't be reached.

## Web UI

The web UI needs three things running: the Enumeration Manager backend (port 8000), the agent API (port 8001) and
the agent UI (port 5174).

```bash
# terminal 1: the Enumeration Manager backend
cd rdaas_app/backend
.venv\Scripts\activate
uvicorn app.main:app

# terminal 2: the agent API
cd agent
.venv\Scripts\activate
uvicorn enum_agent.api:app --port 8001

# terminal 3: the agent UI
cd agent/frontend
npm install
npm run dev
```

Open http://localhost:5174. In the UI you can:
- pick a schema from the `schemas/` folder, or upload one (it is saved into that folder)
- see the attributes that will be compared, and view the schema's JSON
- run the analysis and see the results grouped as same, similar and different, with filters, copy buttons for
  proposed blocks and requests, and the "Decide" tables for defaults/examples that would become invalid
- download the report as `output.md`. Each run also saves it to `output.md` in the project root, and the results
  show where.

The header shows whether the OpenAI key is set, which model is used, and whether the Enumeration Manager is reachable.
Results stay available for each schema until you reload the page.

Agent API endpoints:

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/status` | OpenAI key set, model, and whether the Enumeration Manager is reachable |
| GET | `/api/schemas` | List the `.json` files in the schemas folder |
| GET | `/api/schemas/{name}` | One schema: its content and the attributes that will be compared |
| POST | `/api/schemas` | Upload `{name, content}` into the schemas folder (existing files are never overwritten) |
| POST | `/api/analyses` | Run the agent on `{schema_name}`; returns the report, conflicts and Markdown text, and saves `output.md` |

## How it works

Plain code handles the parsing and checks, so they don't depend on the model:

| Step | Done by |
| --- | --- |
| Extract `enum`/`const` attributes, including nested ones (`read_json_schema` tool) | Python |
| Fetch the app's enumerations over the REST API (`get_defined_enumerations` tool) | Python |
| Compare values: exact matches, values on one side only, near-misses (`compare_values` tool) | Python |
| Decide same / similar / different, map old values to new (e.g. `uat` → `test`), write proposals | the model, as a typed `ComparisonReport` |
| Add back keywords the model left out of a proposed block | Python |
| Flag `default`/`examples` values the new values would make invalid | Python |
| Warn if the report skips an attribute | Python |

The command line and the web API share the same pipeline (`enum_agent/service.py`), so they produce the same report.

Not checked yet: values used in conditions (e.g. `if: {"environment": {"const": "uat"}}`) and attributes reached
through `$ref`.
