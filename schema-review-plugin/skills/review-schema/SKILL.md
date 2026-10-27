---
name: review-schema
description: Review a JSON Schema's enum/const attributes against the enumerations defined in the Enumeration Manager app. Confirms attributes that match, proposes JSON Schema changes for similar ones, proposes new enumerations for the rest, and writes the report to output.md. Use when the user asks to review, check or compare a JSON Schema (or its enums) against the Enumeration Manager or its enumerations.
argument-hint: <schema.json> [output.md]
allowed-tools:
  - mcp__plugin_schema-review_schema-review__read_json_schema
  - mcp__plugin_schema-review_schema-review__get_enumerations
  - mcp__plugin_schema-review_schema-review__compare_values
  - mcp__plugin_schema-review_schema-review__finalize_review
  - Glob
---

# Review a JSON Schema against the Enumeration Manager

Arguments: `$ARGUMENTS`

The schema-review MCP tools do the reading, comparing and checking. You make the judgement calls: which app
enumeration, if any, each attribute corresponds to. The Enumeration Manager is at `${user_config.enum_api_url}`.

## 1. Work out the paths

- The first argument is the schema file and the optional second one is the report file. Resolve both against the
  current working directory into **absolute** paths; the tools refuse relative ones.
- No schema given: Glob for `**/*.json` (skip `node_modules`, `.venv`, `dist`, lock files and `package*.json`).
  If exactly one file looks like a JSON Schema, use it. Otherwise list the candidates and ask which one to review.
- No report path given: use `<working directory>/output.md`.

## 2. Gather the facts

1. Call `read_json_schema` with the schema path. It lists every attribute constrained by `enum` or `const`. If
   there are none, say so and stop.
2. Call `get_enumerations` to get the app's enumerations. If it fails, show its error (the app is probably not
   running, or the plugin's Enumeration Manager URL setting is wrong) and stop.
3. For each attribute, look for an app enumeration that represents the same concept. Signals: an `x_enumeration`
   hint, a similar name (env ~ environment, asset_type ~ asset_types), or overlapping or synonymous values. Call
   `compare_values` for every plausible candidate before deciding. A similar name alone is not enough if the
   values describe a different concept.

## 3. Classify every attribute exactly once

- **same**: the attribute's values are exactly the enumeration's values (order does not matter), or the attribute
  is a `const` whose value is exactly one of the enumeration's values for the same concept. Just confirm it.
- **similar**: an enumeration represents the same concept but the values or spelling differ (case or separators,
  abbreviations such as dev/development, synonyms such as uat/test, missing or extra values).
  - `proposed_schema_fragment`: the replacement JSON object for the attribute, using the enumeration's values
    verbatim and in its order, plus `"x-enumeration": "<enumeration name>"`. Keywords you leave out are kept
    from the original.
  - `value_mapping`: for each schema value not in the enumeration, the enumeration value it corresponds to
    (uat -> test), or null if it has no counterpart and would be dropped.
  - In the explanation, say which values would be renamed or dropped, so the user can decide whether to extend
    the enumeration instead.
- **different**: no enumeration represents the concept. Set `proposed_enumeration`: a snake_case name derived
  from the attribute (prefix generic nested names with their parent: storage/type -> storage_type), a short
  description, and the schema's values verbatim.

Never invent enumeration names or values: use only what the tools return. Copy `attribute` and `schema_pointer`
exactly as `read_json_schema` returned them.

## 4. Finalize

Call `finalize_review` with the schema path, a one-paragraph summary with the counts, every finding, and the
report path. It checks each finding against the schema and the app, writes the report, and returns `warnings`.
If there are warnings, fix the findings they point at and call it again (it overwrites the file). After two
retries, stop and pass any remaining warnings on to the user.

## 5. Show the results in the terminal

Keep it scannable. The full detail is in the report file.

1. One line: the schema name and the counts, e.g. **database-instance.schema-2.json**: 0 same · 1 similar · 6 different.
2. **Same**: one bullet per attribute: `attribute` matches `enumeration`.
3. **Similar**: for each attribute, the value changes (`uat` → `test`) and the `replacement` block that
   `finalize_review` returned, in a ```json block. If it returned `value_conflicts`, add a table
   (Location | Value | Options), the options being: change it to the suggested value (when there is one), remove
   it, or keep it and add the value to the enumeration instead. Say plainly that these are the user's call.
4. **Different**: a table with Attribute | Proposed enumeration | Values.
5. Any warnings that remain after finalizing.
6. The report path, then one line offering the next steps: update the schema file, or create the proposed
   enumerations in the app.

This review only proposes changes. Do not edit the schema or create enumerations unless the user then asks for it.
If they do: edit the schema file with your editing tools, and create an enumeration by sending
`POST ${user_config.enum_api_url}/api/enumerations` with JSON `{"name", "description", "values"}`. Confirm each
one that was created, and show the error for any that failed.
