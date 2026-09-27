"""
Command-line entry point.

Usage:
    python -m tier0 path/to/document.jpg
    python -m tier0 path/to/document.jpg --watchlist watchlist.json
    python -m tier0 path/to/document.jpg --json

Exit code is 0 on PASS, 1 on FAIL, 2 on a usage/runtime error -- so this
also drops straight into a shell pipeline or a CI check if useful.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from .pipeline import run_tier0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tier0",
        description="Tier 0 — instant document fraud sanity gate (MRZ checksum, "
        "date sanity, watchlist).",
    )
    parser.add_argument("image", help="Path to the document photo (ID/passport photo page)")
    parser.add_argument(
        "--watchlist",
        default=None,
        help="Path to a watchlist JSON file (see tier0/watchlist.py for the expected shape)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the full result as JSON instead of plain text"
    )
    args = parser.parse_args(argv)

    result = run_tier0(args.image, watchlist_path=args.watchlist)

    if args.json:
        payload = dataclasses.asdict(result)
        # enums / nested dataclasses need string-ifying for json.dumps
        if result.failed_at is not None:
            payload["failed_at"] = result.failed_at.value
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(result)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
