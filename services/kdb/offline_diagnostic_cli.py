#!/usr/bin/env python3
"""Offline KDB diagnostic CLI. No network, no SQL, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_diagnostic_cli.py tests/kdb/fixtures/p10_stage_coherent.json

Exit 0: a redacted diagnostic receipt was printed. final_authority is always
NOT_ADMITTED. Exit 2: input rejected. Exit 1: unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_diagnostic import DiagnosticParseError, diagnose_file  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only offline KDB diagnostic. Never admits a database command."
    )
    parser.add_argument("input_json", help="Local JSON fixture path. HTTP paths are denied.")
    parser.add_argument(
        "--commit",
        default="UNPINNED_LOCAL",
        help="Optional source commit label stored on the receipt.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = diagnose_file(args.input_json, commit=args.commit)
    except DiagnosticParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
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
