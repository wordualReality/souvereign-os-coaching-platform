#!/usr/bin/env python3
"""Offline KDB snapshot-delta workbench CLI. No network, no SQL write, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_review_snapshot_delta_cli.py \\
    tests/kdb/fixtures/p14_inbox_two_eligible.json \\
    path/to/current-p14-batch.json

The two paths must be distinct repository files. Exit 0 prints standalone UTF-8
HTML to stdout, or writes it with --output to a new file under the repository.
The page is still NOT_ADMITTED, SNAPSHOT_UNTRUSTED, and NOT_ASSIGNED.
Exit 2: input rejected. Exit 1: unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_review_snapshot_delta import snapshot_delta_files, write_workbench_html  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Static offline snapshot-delta HTML. Never assigns a reviewer, "
            "attests event order, or admits C04."
        )
    )
    parser.add_argument("baseline_json", help="Local baseline P14 JSON batch path.")
    parser.add_argument("current_json", help="Local current P14 JSON batch path. Must differ from baseline.")
    parser.add_argument(
        "--commit",
        default="UNPINNED_LOCAL",
        help="Optional source commit label stored on the page.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional new relative .html path under the repository. Existing files are not overwritten.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = snapshot_delta_files(
            args.baseline_json,
            args.current_json,
            commit=args.commit,
        )
        if args.output:
            write_workbench_html(receipt["html"], args.output)
        else:
            sys.stdout.write(receipt["html"])
            if not receipt["html"].endswith("\n"):
                sys.stdout.write("\n")
    except PreviewParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "delta_status": "DELTA_DENIED",
            "parse_error": exc.code,
        }
        json.dump(error, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_INPUT
    except Exception:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "delta_status": "DELTA_DENIED",
            "parse_error": "INTERNAL_FAIL_CLOSED",
        }
        json.dump(error, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_INTERNAL
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
