#!/usr/bin/env python3
"""Offline KDB source-bytes proof CLI. No network, no SQL write, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_source_bytes_proof_cli.py \\
    tests/kdb/fixtures/p20_inbox_match.json \\
    --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 \\
    --source-file tests/kdb/fixtures/p20_source_a.bin

Default stdout is a redacted proof receipt. No files are written.
A local byte match is not source custody, rights, or live ingest.
Exit 2: input rejected. Exit 1: unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_source_bytes_proof import source_bytes_proof_files  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare local synthetic source bytes to a declared SourceVersion "
            "SHA-256. Never admits rights, origin, or C04."
        )
    )
    parser.add_argument("input_json", help="Local P14 JSON batch path.")
    parser.add_argument(
        "--work-item-id",
        required=True,
        help="Canonical review_work_item_id. Invalid values are not echoed.",
    )
    parser.add_argument(
        "--source-file",
        required=True,
        help="Repo-local synthetic source file. HTTP and escaped paths are denied.",
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
        receipt = source_bytes_proof_files(
            args.input_json,
            args.work_item_id,
            args.source_file,
            commit=args.commit,
        )
        json.dump(receipt, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    except PreviewParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "proof_status": "PROOF_DENIED",
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
            "proof_status": "PROOF_DENIED",
            "parse_error": "INTERNAL_FAIL_CLOSED",
        }
        json.dump(error, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_INTERNAL
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
