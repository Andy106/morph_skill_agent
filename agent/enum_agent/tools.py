"""Plain-Python helpers behind the agent's tools. Kept free of the Agents SDK so they can be unit tested."""

import difflib
import json
import os
import re
from pathlib import Path

import httpx

API_URL = os.getenv("ENUM_API_URL", "http://127.0.0.1:8000").rstrip("/")

# Keywords whose subschemas describe the data itself. Conditional keywords (if/then/else/not)
# are skipped on purpose: a `const` inside an `if` is a test, not an attribute definition.
_NAMED_CHILDREN = ("properties", "patternProperties", "$defs", "definitions")
_SINGLE_CHILDREN = ("items", "additionalProperties", "contains")
_LIST_CHILDREN = ("allOf", "anyOf", "oneOf", "prefixItems")


class EnumApiError(RuntimeError):
    pass


def _as_str(value) -> str:
    # The Enumeration Manager stores values as strings; render numbers/booleans the way JSON writes them.
    return value if isinstance(value, str) else json.dumps(value)


def _escape_pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def load_schema(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    if not isinstance(schema, dict):
        raise ValueError(f"{path} is not a JSON Schema object")
    return schema


def extract_enum_attributes(schema: dict) -> list[dict]:
    """Return every attribute in the schema constrained by `enum` or `const`, with its JSON Pointer."""
    found: list[dict] = []

    def walk(node, pointer: str, name: str) -> None:
        if not isinstance(node, dict):
            return
        if "enum" in node or "const" in node:
            raw = node["enum"] if "enum" in node else [node["const"]]
            found.append(
                {
                    "attribute": name,
                    "pointer": pointer or "/",
                    "kind": "enum" if "enum" in node else "const",
                    "values": [_as_str(v) for v in raw],
                    "description": node.get("description"),
                    "x_enumeration": node.get("x-enumeration"),
                }
            )
        for key in _NAMED_CHILDREN:
            children = node.get(key)
            if isinstance(children, dict):
                for child_name, child in children.items():
                    walk(child, f"{pointer}/{key}/{_escape_pointer(child_name)}", child_name)
        for key in _SINGLE_CHILDREN:
            if isinstance(node.get(key), dict):
                walk(node[key], f"{pointer}/{key}", name)
        for key in _LIST_CHILDREN:
            if isinstance(node.get(key), list):
                for i, child in enumerate(node[key]):
                    walk(child, f"{pointer}/{key}/{i}", name)

    walk(schema, "", schema.get("title") or "root")
    return found


def resolve_pointer(schema: dict, pointer: str):
    """Return the subschema at a JSON Pointer such as /properties/storage/properties/type."""
    node = schema
    for token in pointer.strip("/").split("/") if pointer.strip("/") else []:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def merge_schema_fragment(original: dict, proposed: dict) -> dict:
    """Apply a proposed attribute schema on top of the original, so keywords the model omitted are kept.

    `enum` and `const` are alternatives: if the proposal uses one, the other is dropped from the original.
    """
    merged = dict(original)
    if "enum" in proposed:
        merged.pop("const", None)
    if "const" in proposed:
        merged.pop("enum", None)
    merged.update(proposed)
    return merged


def _instance_steps(schema: dict, pointer: str) -> list[tuple[dict, str, list]]:
    """Walk from the root to the attribute at `pointer`.

    Returns (subschema, its pointer, instance path from the root to it) for the attribute and every enclosing
    subschema whose location in an instance is known. Instance path segments are property names, list indexes,
    or "*" for every array element. Walking through $defs, patternProperties etc. drops the enclosing levels,
    since there is no fixed instance location above those.
    """
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in pointer.strip("/").split("/")] if pointer.strip("/") else []
    node, ptr, path = schema, "", []
    steps = [(node, ptr, path)]
    i = 0
    while i < len(tokens):
        key = tokens[i]
        if key in ("properties", "$defs", "definitions", "patternProperties", "allOf", "anyOf", "oneOf", "prefixItems"):
            child = tokens[i + 1]
            node = node[key][int(child)] if isinstance(node[key], list) else node[key][child]
            ptr += f"/{key}/{_escape_pointer(child)}"
            i += 2
            if key == "properties":
                path = path + [child]
            elif key == "prefixItems":
                path = path + [int(child)]
            elif key not in ("allOf", "anyOf", "oneOf"):
                steps, path = [], []
        else:  # items, additionalProperties, contains
            node = node[key]
            ptr += f"/{key}"
            i += 1
            if key == "items":
                path = path + ["*"]
            else:
                steps, path = [], []
        steps.append((node, ptr, path))
    return steps


def _values_at(instance, path: list, location: str):
    """Yield (JSON Pointer, value) for each value found at `path` inside an example or default instance."""
    if not path:
        yield location, instance
        return
    seg, rest = path[0], path[1:]
    if seg == "*" and isinstance(instance, list):
        for k, item in enumerate(instance):
            yield from _values_at(item, rest, f"{location}/{k}")
    elif isinstance(seg, int) and isinstance(instance, list) and seg < len(instance):
        yield from _values_at(instance[seg], rest, f"{location}/{seg}")
    elif isinstance(seg, str) and seg != "*" and isinstance(instance, dict) and seg in instance:
        yield from _values_at(instance[seg], rest, f"{location}/{_escape_pointer(seg)}")


def find_value_conflicts(schema: dict, pointer: str, fragment: dict) -> list[dict]:
    """Find `default` and `examples` values that the proposed attribute `fragment` would no longer allow.

    Checks the fragment itself and every enclosing subschema, including the root `examples`.
    """
    allowed = fragment["enum"] if "enum" in fragment else [fragment["const"]] if "const" in fragment else None
    if allowed is None:
        return []
    allowed = {_as_str(v) for v in allowed}

    steps = _instance_steps(schema, pointer)
    target_path = steps[-1][2]
    steps[-1] = (fragment, steps[-1][1], target_path)  # judge the attribute's own keywords as proposed

    conflicts = []
    for node, node_ptr, node_path in steps:
        rest = target_path[len(node_path):]
        sources = []
        if "default" in node:
            sources.append((node["default"], f"{node_ptr}/default"))
        if isinstance(node.get("examples"), list):
            sources += [(ex, f"{node_ptr}/examples/{j}") for j, ex in enumerate(node["examples"])]
        for instance, location in sources:
            for value_ptr, value in _values_at(instance, rest, location):
                if _as_str(value) not in allowed:
                    conflicts.append({"location": value_ptr or "/", "value": _as_str(value)})
    return conflicts


def fetch_enumerations() -> list[dict]:
    try:
        resp = httpx.get(f"{API_URL}/api/enumerations", timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise EnumApiError(
            f"Could not reach the Enumeration Manager API at {API_URL} ({e}). "
            "Start it with: cd rdaas_app/backend && uvicorn app.main:app"
        ) from e
    return [{"name": e["name"], "description": e["description"], "values": e["values"]} for e in resp.json()]


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-.]+", "", value.lower())


def diff_values(schema_values: list[str], enum_values: list[str]) -> dict:
    """Compare a schema attribute's values with an enumeration's values."""
    schema_set, enum_set = set(schema_values), set(enum_values)
    only_schema = [v for v in schema_values if v not in enum_set]
    only_enum = [v for v in enum_values if v not in schema_set]

    by_norm = {_normalize(v): v for v in only_enum}
    close = []
    for v in only_schema:
        n = _normalize(v)
        hits = difflib.get_close_matches(n, list(by_norm), n=3, cutoff=0.6)
        hits += [k for k in by_norm if k not in hits and n and k and (k.startswith(n) or n.startswith(k))]
        if hits:
            close.append({"schema_value": v, "enumeration_values": [by_norm[h] for h in hits]})

    return {
        "identical": schema_set == enum_set,
        "identical_ignoring_case_and_separators": {_normalize(v) for v in schema_set} == {_normalize(v) for v in enum_set},
        "schema_values_are_subset": schema_set <= enum_set,
        "in_both": [v for v in schema_values if v in enum_set],
        "only_in_schema": only_schema,
        "only_in_enumeration": only_enum,
        "close_matches": close,
    }
