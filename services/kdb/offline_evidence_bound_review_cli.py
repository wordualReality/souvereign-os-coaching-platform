#!/usr/bin/env python3
"""P21 redacted offline evidence-bound review CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_evidence_bound_review import evidence_bound_review_files  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local-only evidence-bound review preview.")
    parser.add_argument("input_json")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--commit", default="UNPINNED_LOCAL")
    args = parser.parse_args()
    try:
        receipt = evidence_bound_review_files(
            args.input_json, args.work_item_id, args.source_file, commit=args.commit
        )
        code = 0
    except PreviewParseError as exc:
        receipt = {
            "packet": "KDB-M01-P21-OFFLINE-EVIDENCE-BOUND-REVIEW-01",
            "review_status": "EVIDENCE_BOUND_REVIEW_DENIED",
            "deny_code": exc.code,
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
        }
        code = 2
    except Exception:
        receipt = {
            "packet": "KDB-M01-P21-OFFLINE-EVIDENCE-BOUND-REVIEW-01",
            "review_status": "EVIDENCE_BOUND_REVIEW_DENIED",
            "deny_code": "INTERNAL_FAIL_CLOSED",
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
        }
        code = 1
    json.dump(receipt, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
