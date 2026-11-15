"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .parser import Catalog, parse_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="errata", description=__doc__)
    parser.add_argument("--version", action="version", version=f"errata {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="parse the error catalog and report problems")
    scan.add_argument("catalog", type=Path, help="path to the catalog, e.g. 06-誤答カタログ.md")
    scan.add_argument("--json", action="store_true", help="print parsed entries as JSON")
    scan.add_argument(
        "--strict", action="store_true", help="exit with status 1 on warnings as well as errors"
    )

    args = parser.parse_args(argv)
    if args.command == "scan":
        return cmd_scan(args.catalog, as_json=args.json, strict=args.strict)
    return 2  # pragma: no cover


def cmd_scan(path: Path, *, as_json: bool, strict: bool) -> int:
    if not path.is_file():
        print(f"errata: file not found: {path}", file=sys.stderr)
        return 2
    catalog = parse_file(path)

    if as_json:
        print(json.dumps(_to_json(catalog), ensure_ascii=False, indent=2, default=str))
    else:
        _print_summary(catalog)

    if catalog.has_errors or (strict and catalog.issues):
        return 1
    return 0


def _print_summary(catalog: Catalog) -> None:
    print(f"{catalog.path}  (created {catalog.created or 'unknown'})")
    print()
    print(f"{'ID':<3} {'entries':>7} {'answered':>8}  title")
    for c in catalog.categories.values():
        answered = sum(1 for e in c.entries if e.answer)
        print(f"{c.id:<3} {len(c.entries):>7} {answered:>8}  {c.title}")
    if catalog.pending:
        print(f"{'-':<3} {len(catalog.pending):>7} {'':>8}  (not checked yet)")
    total = len(catalog.entries)
    print(f"\n{total} entries in {len(catalog.categories)} categories")

    if catalog.issues:
        errors = sum(1 for i in catalog.issues if i.level == "error")
        print(f"\n{errors} error(s), {len(catalog.issues) - errors} warning(s):")
        for i in catalog.issues:
            print(f"  line {i.line:>4}  {i.level:<7} {i.code:<24} {i.message}")
    else:
        print("\nNo problems found.")


def _to_json(catalog: Catalog) -> dict:
    return {
        "path": str(catalog.path),
        "created": catalog.created,
        "categories": [
            {
                "id": c.id,
                "title": c.title,
                "rule": c.rule,
                "entries": [_entry_json(e) for e in c.entries],
            }
            for c in catalog.categories.values()
        ],
        "pending": [_entry_json(e) for e in catalog.pending],
        "issues": [asdict(i) for i in catalog.issues],
    }


def _entry_json(e) -> dict:
    return {
        "id": e.entry_id,
        "label": e.label.raw,
        "source": e.label.kind,
        "unit": e.label.unit,
        "date": e.date,
        "text": e.text,
        "error_parts": e.error_parts,
        "memo": e.memo,
        "repeat": e.repeat,
        "answer": e.answer,
        "line": e.line,
    }


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
