#!/usr/bin/env python3
"""Offline KDB review demo-pack CLI. No network, no SQL write, no n8n.

Usage (from repository root):
  python3 services/kdb/offline_review_demo_pack_cli.py \\
    tests/kdb/fixtures/p14_inbox_two_eligible.json \\
    path/to/current-p14-batch.json

Default stdout is a redacted JSON manifest preview. No files are written.
--out-dir tests/kdb/demo-artifacts/<name> creates a new local bundle.
The pack stays NOT_ADMITTED, SNAPSHOT_UNTRUSTED, and NOT_ASSIGNED.
Exit 2: input rejected. Exit 1: unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_review_demo_pack import (  # noqa: E402
    demo_pack_files,
    demo_pack_files_with_evidence,
    write_demo_pack,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Portable offline review demo pack. Never assigns a reviewer, "
            "attests event order, or admits C04."
        )
    )
    parser.add_argument("baseline_json", help="Local baseline P14 JSON batch path.")
    parser.add_argument("current_json", help="Local current P14 JSON batch path. Must differ from baseline.")
    parser.add_argument(
        "--commit",
        default="UNPINNED_LOCAL",
        help="Optional source commit label stored in the pack.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Optional new relative directory under tests/kdb/demo-artifacts. Existing directories are not overwritten.",
    )
    parser.add_argument(
        "--work-item-id",
        default="",
        help="Explicitly opt into P22 evidence mode for this eligible work item.",
    )
    parser.add_argument(
        "--source-file",
        default="",
        help="Repo-local source file for P22 byte/span recomputation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if bool(args.work_item_id) != bool(args.source_file):
            raise PreviewParseError("INCOMPLETE_EVIDENCE_OPT_IN")
        if args.work_item_id:
            receipt = demo_pack_files_with_evidence(
                args.baseline_json,
                args.current_json,
                args.work_item_id,
                args.source_file,
                commit=args.commit,
            )
        else:
            receipt = demo_pack_files(
                args.baseline_json,
                args.current_json,
                commit=args.commit,
            )
        if args.out_dir:
            write_demo_pack(receipt["artifacts"], args.out_dir)
        json.dump(receipt["manifest"], sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    except PreviewParseError as exc:
        error = {
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "pack_status": "DEMO_DENIED",
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
            "pack_status": "DEMO_DENIED",
            "parse_error": "INTERNAL_FAIL_CLOSED",
        }
        json.dump(error, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return EXIT_INTERNAL
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
