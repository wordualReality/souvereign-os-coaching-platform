#!/usr/bin/env python3
"""Diff a read-only ujdz preflight transcript against the frozen owner-reported legacy state.

Does not connect to Supabase. Does not apply SQL. zobj and SOV-dev are forbidden targets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PREIMAGE = json.loads((FIXTURES / "ujdz_legacy_preimage.json").read_text())
FORBIDDEN = set(PREIMAGE["forbidden_refs"])
TARGET = PREIMAGE["target_ref"]


def analyze(text: str) -> dict:
    lowered = text.lower()
    hits = sorted(ref for ref in FORBIDDEN if ref.lower() in lowered)
    has_rollback = PREIMAGE["required_migration_substring"] in text
    protocol_rows = None
    for line in text.splitlines():
        if line.startswith("legacy_protocol_rows|"):
            protocol_rows = int(line.split("|", 1)[1])
    role_hits = [role for role in PREIMAGE["legacy_nologin_roles"] if role in text]
    ledger = [
        line
        for line in text.splitlines()
        if len(line) >= 9 and line[0:8].isdigit() and "|" in line
    ]
    drifts = []
    if hits:
        drifts.append({"code": "FORBIDDEN_TARGET_REF", "detail": hits})
    if protocol_rows is None:
        drifts.append({"code": "MISSING_PROTOCOL_COUNT"})
    elif protocol_rows != PREIMAGE["legacy_protocol_rows"]:
        drifts.append(
            {
                "code": "PROTOCOL_ROW_COUNT_DRIFT",
                "expected": PREIMAGE["legacy_protocol_rows"],
                "actual": protocol_rows,
            }
        )
    if not has_rollback:
        drifts.append({"code": "MISSING_ROLLBACK_OBJECTS_TEST_V2"})
    if len(ledger) != PREIMAGE["migration_receipt_count"]:
        drifts.append(
            {
                "code": "MIGRATION_RECEIPT_COUNT_DRIFT",
                "expected": PREIMAGE["migration_receipt_count"],
                "actual": len(ledger),
            }
        )
    missing_roles = [role for role in PREIMAGE["legacy_nologin_roles"] if role not in role_hits]
    if missing_roles:
        drifts.append({"code": "MISSING_LEGACY_NOLOGIN_ROLES", "detail": missing_roles})
    status = "MATCH" if not drifts else "DRIFT"
    return {
        "target_ref": TARGET,
        "protocol_provenance": PREIMAGE["protocol_provenance"],
        "protocol_rows": protocol_rows,
        "status": status,
        "drifts": drifts,
        "do_not": PREIMAGE["do_not"],
        "apply": "NOT_AUTHORIZED",
    }


def main() -> None:
    if len(sys.argv) < 2:
        match = analyze((FIXTURES / "ujdz_preflight_sample_match.txt").read_text())
        drift = analyze((FIXTURES / "ujdz_preflight_sample_drift.txt").read_text())
        if match["status"] != "MATCH":
            raise SystemExit(f"expected MATCH fixture, got {match}")
        if drift["status"] != "DRIFT":
            raise SystemExit(f"expected DRIFT fixture, got {drift}")
        print("PASS_HOSTED_RECOVERY_PREFLIGHT_DIFF_OFFLINE")
        print("NOTE_NO_LIVE_UJDZ_READ")
        print("NOTE_APPLY_NOT_AUTHORIZED")
        return
    path = Path(sys.argv[1])
    report = analyze(path.read_text())
    print(json.dumps(report, indent=2))
    if report["status"] != "MATCH":
        raise SystemExit("DRIFT")


if __name__ == "__main__":
    main()
