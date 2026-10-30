#!/usr/bin/env python3
"""Offline KDB review-inbox read-model CLI. No network, no SQL write, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_review_inbox_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json

Exit 0 prints a redacted inbox receipt. PREVIEW_ONLY is still NOT_ADMITTED,
SNAPSHOT_UNTRUSTED, and NOT_ASSIGNED. Exit 2: input rejected. Exit 1: unexpected
failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_review_inbox import MAX_ENTRIES, inbox_file  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Redacted offline review-inbox read model. Never assigns a reviewer or admits C04."
    )
    parser.add_argument("input_json", help="Local JSON batch path. HTTP paths are denied.")
    parser.add_argument(
        "--commit",
        default="UNPINNED_LOCAL",
        help="Optional source commit label stored on the receipt.",
    )
    parser.add_argument(
        "--status",
        default="",
        help="Non-authoritative local filter: PREVIEW_ONLY, PREVIEW_DENIED, or REQUESTED.",
    )
    parser.add_argument("--page", default=1, type=int, help="1-based local page. Not an authorization cursor.")
    parser.add_argument(
        "--page-size",
        default=MAX_ENTRIES,
        type=int,
        help="Local page size, at most 32. Not a server cursor.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = inbox_file(
            args.input_json,
            commit=args.commit,
            status_filter=args.status or None,
            page=args.page,
            page_size=args.page_size,
        )
    except PreviewParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "inbox_status": "INBOX_DENIED",
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
            "inbox_status": "INBOX_DENIED",
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
