# Enumeration Manager and schema review

This project has three parts:

- **[The Enumeration Manager app](rdaas_app/README.md) (`rdaas_app/`)**: a REST API and web UI for creating,
  editing and deleting named enumerations (e.g. `environment` → `dev`, `test`, `prod`).
- **[The schema review agent](agent/README.md) (`agent/`)**: an OpenAI Agents SDK agent that compares the
  enumerations in a JSON Schema with the ones defined in the app and proposes how to bring the two in line.
  It has a command line and a web UI.
- **[The schema-review Claude Code plugin](schema-review-plugin/README.md) (`schema-review-plugin/`)**: the same
  review, with Claude as the model and the terminal as the UI.

```
rdaas_app/
  backend/              FastAPI + SQLAlchemy + SQLite API (port 8000)
  frontend/             React + Vite UI (port 5173)
agent/
  enum_agent/           the agent: command line (python -m enum_agent) and web API (port 8001)
  frontend/             React + Vite UI for the agent (port 5174)
schema-review-plugin/   Claude Code plugin: skill + local Python MCP server
schemas/                JSON Schemas to review
output.md               the latest review report (written by the agent and by the plugin)
```

Both the agent and the plugin write their report to `output.md` in this folder: the agent always, and the plugin
when Claude Code is started here. No authentication or authorization is in place yet.

This file combines the three READMEs linked above. Edit those, then regenerate this one, so they stay in step.

## Quick start

1. Start the Enumeration Manager backend (all reviews need it):
   ```bash
   cd rdaas_app/backend
   .venv\Scripts\activate
   uvicorn app.main:app
   ```
2. Then use any of:
   - **App UI:** `cd rdaas_app/frontend && npm run dev` and open http://localhost:5173.
   - **Agent, command line:** `cd agent`, activate `.venv`, then
     `python -m enum_agent ..\schemas\database-instance.schema-2.json`.
   - **Agent, web UI:** start the agent API and UI (see the agent section) and open http://localhost:5174.
   - **Claude Code plugin:** in Claude Code, `/schema-review:review-schema schemas/database-instance.schema-2.json`.

## Enumeration Manager app (`rdaas_app/`)

_From [rdaas_app/README.md](rdaas_app/README.md)._

A REST API and web UI for creating, editing and deleting named enumerations, e.g. `environment` → `dev`, `test`,
`prod`. The schema review agent and the schema-review Claude Code plugin both check JSON Schemas against the
enumerations defined here.

```
backend/     FastAPI + SQLAlchemy + SQLite API (port 8000; database: backend/enums.db, created on first run)
frontend/    React + Vite UI (port 5173)
```

No authentication or authorization is in place yet.

### Backend (port 8000)

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

### Frontend (port 5173)

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

### Tests

```bash
cd rdaas_app/backend
pytest
```

The tests use a temporary database, so they never touch `enums.db`.

### API

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

#### Example

```bash
curl -X POST http://127.0.0.1:8000/api/enumerations \
  -H "Content-Type: application/json" \
  -d '{"name":"environment","values":["dev","test","prod"]}'

curl "http://127.0.0.1:8000/api/enumerations/environment/validate?value=prod"
# {"enumeration":"environment","value":"prod","valid":true}
```

## Schema review agent (`agent/`)

_From [agent/README.md](agent/README.md)._

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

### Setup

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

### Command line

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

### Web UI

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

### How it works

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

## schema-review Claude Code plugin (`schema-review-plugin/`)

_From [schema-review-plugin/README.md](schema-review-plugin/README.md)._

Reviews a JSON Schema's `enum` and `const` attributes against the enumerations defined in an
**Enumeration Manager** app, right in your Claude Code terminal:

- **Same:** the values match an existing enumeration. Claude confirms it.
- **Similar:** the same concept with different values or spelling (e.g. `dev, uat, prod` vs `dev, test, prod`).
  Claude proposes the replacement schema block and flags any `default` or `examples` values that would become
  invalid, for you to decide.
- **Different:** no matching enumeration. Claude proposes a new enumeration for the app.

The full report is written to `output.md` in the folder you started Claude Code in, normally your project's root.
Nothing is changed unless you ask Claude to apply the proposals afterwards.

This plugin does the same review as the OpenAI-based agent in `agent/`, but Claude is the model and the
terminal is the UI. It needs no OpenAI key.

### Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/getting-started/installation/). It runs the plugin's Python tool server and installs
  its dependencies (and Python itself, if needed) the first time.
- A running Enumeration Manager API (`GET /api/enumerations`). By default the plugin looks for it at
  `http://127.0.0.1:8000`.

### Install

In a Claude Code terminal session:

```
/plugin install schema-review --marketplace <owner>/<repo>
```

Answer `y` to add the marketplace, choose a scope (user scope makes it available in every project), and set the
**Enumeration Manager URL** when asked. To change that setting later, use `/plugin` and open the plugin's settings.

To install from a local copy instead, start Claude Code in the folder that contains `schema-review-plugin` and
add it with a relative path. A quoted absolute Windows path such as `"C:\path\to\..."` is rejected with
"Invalid marketplace source format".

```
/plugin marketplace add ./schema-review-plugin
/plugin install schema-review@rdaas-tools
```

Or run the first step from a shell: `claude plugin marketplace add ./schema-review-plugin`. Either way, the
marketplace is saved under its full path, so the plugin keeps working from any folder.

### Use

```
/schema-review:review-schema schemas/database-instance.schema-2.json
/schema-review:review-schema schemas/database-instance.schema-2.json reports/env-review.md
/schema-review:review-schema
```

- The first argument is the schema. The optional second one is where to write the report (default: `output.md`
  in the current folder).
- With no arguments, Claude looks for JSON Schema files in the project and asks which one to review.
- You can also just ask, e.g. "check schemas/foo.json against the Enumeration Manager".

Afterwards you can ask Claude to apply the proposals, e.g. "update the schema for env" or "create the
storage_type and status enumerations". Claude edits the schema file, or calls the app's
`POST /api/enumerations`, only when you ask.

### How it works

| Part | What it does |
| --- | --- |
| `skills/review-schema/SKILL.md` | The review procedure Claude follows, and how it presents the results |
| `.mcp.json` + `server/` | A local Python MCP server (started with `uv run`) with four tools |
| `.claude-plugin/plugin.json` | Plugin manifest, including the Enumeration Manager URL setting |
| `.claude-plugin/marketplace.json` | Makes this repository installable with `/plugin install` |

The tools:
- `read_json_schema`: lists every `enum`/`const` attribute, including nested ones.
- `get_enumerations`: fetches the app's enumerations.
- `compare_values`: exact matches, values only on one side, and near-misses.
- `finalize_review`: takes Claude's findings and checks each one against the schema and the app. For example, it
  confirms that "same" values really match, that proposed blocks use the enumeration's values in order, and that
  proposed names are valid and new. It also restores keywords a proposal left out, finds `default`/`examples`
  values that would become invalid, and writes the Markdown report. Problems come back as warnings, which Claude
  fixes before showing you the results.

Claude makes the judgement calls (which enumeration an attribute corresponds to, how values map). Plain code does
the reading, comparing and checking.

### Development

```
cd server
uv run pytest                       # unit tests
claude plugin validate ..           # check the plugin and marketplace manifests
claude --plugin-dir ..              # try the plugin in a session without installing it
```

To publish, push this folder as the root of a GitHub repository: `.claude-plugin/marketplace.json` must be at the
repository root. Bump `version` in `plugin.json` for each release, so installed copies pick it up with
`claude plugin update`.

Known limits: values used in conditions (`if: {"env": {"const": "uat"}}`) and attributes reached through `$ref`
are not checked yet. The Enumeration Manager API has no authentication.
