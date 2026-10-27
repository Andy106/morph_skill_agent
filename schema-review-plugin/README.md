# schema-review: a Claude Code plugin

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

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/getting-started/installation/). It runs the plugin's Python tool server and installs
  its dependencies (and Python itself, if needed) the first time.
- A running Enumeration Manager API (`GET /api/enumerations`). By default the plugin looks for it at
  `http://127.0.0.1:8000`.

## Install

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

## Use

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

## How it works

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

## Development

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
