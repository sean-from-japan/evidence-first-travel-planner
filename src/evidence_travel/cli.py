"""Command-line interface with stable exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from evidence_travel.model import InputError, load_itinerary
from evidence_travel.report import render_html, render_markdown, summary, write_text
from evidence_travel.validator import validate

EXIT_OK = 0
EXIT_FINDINGS = 2
EXIT_INPUT = 3
EXIT_INTERNAL = 4


def _validate_file(
    path: Path,
    markdown: Optional[Path],
    html: Optional[Path],
    json_path: Optional[Path],
) -> int:
    itinerary = load_itinerary(path)
    issues = validate(itinerary)
    result = summary(issues)
    if markdown:
        write_text(markdown, render_markdown(itinerary, issues))
    if html:
        write_text(html, render_html(itinerary, issues))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if json_path:
        write_text(json_path, rendered)
    print(rendered, end="")
    return EXIT_FINDINGS if issues else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence-travel", description="Validate an evidence-backed itinerary."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser(
        "validate", help="validate an itinerary JSON file"
    )
    validate_parser.add_argument("input", type=Path)
    validate_parser.add_argument("--markdown", type=Path)
    validate_parser.add_argument("--html", type=Path)
    validate_parser.add_argument("--json", dest="json_path", type=Path)
    demo_parser = subparsers.add_parser(
        "demo", help="run the committed fictional example"
    )
    demo_parser.add_argument("--output-dir", type=Path, default=Path("build/demo"))
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _validate_file(args.input, args.markdown, args.html, args.json_path)
        root = Path(__file__).resolve().parents[2]
        output = args.output_dir
        return _validate_file(
            root / "examples" / "fictional_trip.json",
            output / "report.md",
            output / "report.html",
            output / "summary.json",
        )
    except InputError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # pragma: no cover - last-resort stable interface
        print(f"internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
