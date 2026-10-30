#!/usr/bin/env python3
"""Offline KDB review case-detail CLI. No network, no SQL write, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_review_case_detail_cli.py \\
    tests/kdb/fixtures/p14_inbox_two_eligible.json \\
    --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777

Exit 0 prints a redacted DETAIL_ONLY receipt. The result is still NOT_ADMITTED,
SNAPSHOT_UNTRUSTED, and NOT_ASSIGNED. Exit 2: input or selector rejected.
Exit 1: unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_review_case_detail import case_detail_file  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Redacted offline review case detail. Never assigns a reviewer or admits C04."
    )
    parser.add_argument("input_json", help="Local P14 JSON batch path. HTTP paths are denied.")
    parser.add_argument(
        "--work-item-id",
        required=True,
        help="Canonical review_work_item_id. Invalid values are not echoed.",
    )
    parser.add_argument(
        "--commit",
        default="UNPINNED_LOCAL",
        help="Optional source commit label stored on the receipt.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = case_detail_file(args.input_json, args.work_item_id, commit=args.commit)
    except PreviewParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "detail_status": "DETAIL_DENIED",
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
            "detail_status": "DETAIL_DENIED",
            "parse_error": "INTERNAL_FAIL_CLOSED",
        }
        json.dump(error, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_INTERNAL
    json.dump(receipt, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
