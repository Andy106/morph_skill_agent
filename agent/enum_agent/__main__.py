"""Usage: python -m enum_agent <schema.json> [--json] [--model MODEL] [--output PATH]

The Markdown report goes to output.md in the project root unless --output says otherwise."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import tools
from .service import DEFAULT_OUTPUT_PATH, Analysis, AnalysisError, analyze


def _print_conflicts(conflicts: list[dict], enumeration: str | None) -> None:
    print("      ! With the new values, these defaults/examples in the schema would become invalid. Decide how to handle each one:")
    for c in conflicts:
        options = []
        if c["suggested_value"]:
            options.append(f"change it to \"{c['suggested_value']}\"")
        options.append("remove it")
        options.append(f"keep it and add \"{c['value']}\" to the '{enumeration}' enumeration instead")
        print(f"        {c['location']} = \"{c['value']}\"")
        print(f"          Options: {' | '.join(options)}")


def _print_report(analysis: Analysis) -> None:
    report, conflicts = analysis.report, analysis.conflicts
    by_status = {s: [f for f in report.findings if f.status == s] for s in ("same", "similar", "different")}

    print(f"\nSchema: {report.schema_path}\n")
    print(report.summary)

    print(f"\n== SAME ({len(by_status['same'])}) - no change needed ==")
    for f in by_status["same"]:
        print(f"  [OK] {f.attribute}  ({f.schema_pointer}) matches enumeration '{f.matched_enumeration}'")
        print(f"       {f.explanation}")

    print(f"\n== SIMILAR ({len(by_status['similar'])}) - proposed JSON Schema changes ==")
    for f in by_status["similar"]:
        print(f"  [~] {f.attribute}  ({f.schema_pointer}) is similar to enumeration '{f.matched_enumeration}'")
        print(f"      Schema values: {', '.join(f.schema_values)}")
        print(f"      {f.explanation}")
        if f.proposed_schema_fragment:
            print(f"      Replace {f.schema_pointer} with:")
            try:
                fragment = json.dumps(json.loads(f.proposed_schema_fragment), indent=2)
            except json.JSONDecodeError:
                fragment = f.proposed_schema_fragment
            print("\n".join("        " + line for line in fragment.splitlines()))
        if f.schema_pointer in conflicts:
            _print_conflicts(conflicts[f.schema_pointer], f.matched_enumeration)

    print(f"\n== DIFFERENT ({len(by_status['different'])}) - proposed new enumerations ==")
    for f in by_status["different"]:
        p = f.proposed_enumeration
        print(f"  [+] {f.attribute}  ({f.schema_pointer})")
        print(f"      {f.explanation}")
        if p:
            payload = json.dumps({"name": p.name, "description": p.description, "values": p.values})
            print(f"      POST {tools.API_URL}/api/enumerations")
            print(f"      {payload}")

    if analysis.missing_pointers:
        print("\nWARNING: the agent did not report on these attributes:", ", ".join(analysis.missing_pointers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a JSON Schema's enumerations with the Enumeration Manager.")
    parser.add_argument("schema", help="Path to the JSON Schema file")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--model", help="OpenAI model (default: $OPENAI_MODEL or the SDK default)")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Markdown report file to write (default: {DEFAULT_OUTPUT_PATH}). A relative path is resolved against the current folder.",
    )
    args = parser.parse_args()

    try:
        analysis = asyncio.run(analyze(args.schema, args.model))
    except AnalysisError as e:
        print(e, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(analysis.to_dict(), indent=2))
    else:
        _print_report(analysis)

    try:
        output_path = analysis.write_markdown(args.output)
    except OSError as e:
        print(f"Could not write the report to {Path(args.output).resolve()}: {e}", file=sys.stderr)
        return 1
    print(f"\nReport written to {output_path}", file=sys.stderr if args.json else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
