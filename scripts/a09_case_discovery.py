#!/usr/bin/env python3
"""Find admitted A09 cases. A missing case, engine or owner receipt stays NOT_EXECUTED."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = ("A09-T01", "A09-T04", "A09-T44", "A09-T48")


def classify(root, case_id):
    folder = root / "docs" / "arcava" / "admission" / "a09" / case_id
    case_file = folder / "case.json"
    owner_file = folder / "owner-receipt.json"
    engine_file = folder / "engine.json"
    case_present = case_file.is_file()
    owner_present = False
    engine_present = engine_file.is_file()
    if owner_file.is_file():
        try:
            owner = json.loads(owner_file.read_text())
        except json.JSONDecodeError:
            owner = {}
        owner_present = owner.get("owner_admitted") is True and owner.get("case_id") == case_id
    if case_present and owner_present and engine_present:
        return "PRESENT_NOT_RUN", case_present, owner_present, engine_present
    return "NOT_EXECUTED", case_present, owner_present, engine_present


def report(root):
    lines = []
    for case_id in IDS:
        status, case_present, owner_present, engine_present = classify(root, case_id)
        marker = "MISSING " if status == "NOT_EXECUTED" else ""
        lines.append(
            "{id} {status} {marker}case={case} owner_receipt={owner} engine={engine}".format(
                id=case_id,
                status=status,
                marker=marker,
                case="present" if case_present else "absent",
                owner="present" if owner_present else "absent",
                engine="present" if engine_present else "absent",
            )
        )
    return lines


def fail_if_proxy_pass(lines):
    for line in lines:
        if " PASS" in line or line.endswith(" PASS"):
            print("FAIL proxy pass")
            return 1
    return 0


def self_check():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        empty = report(root)
        if fail_if_proxy_pass(empty) or any("NOT_EXECUTED" not in line for line in empty):
            print("FAIL empty tree was treated as executed")
            return 1
        partial = root / "docs" / "arcava" / "admission" / "a09" / "A09-T01"
        partial.mkdir(parents=True)
        (partial / "case.json").write_text('{"status":"PASS"}')
        partial_lines = report(root)
        first = partial_lines[0]
        if "A09-T01 NOT_EXECUTED" not in first or "owner_receipt=absent" not in first:
            print("FAIL a case file without an owner receipt was admitted")
            return 1
        if fail_if_proxy_pass(partial_lines):
            return 1
    print("PASS a09_discovery_negative empty=not_executed partial=not_executed proxy_pass=absent")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        return self_check()
    lines = report(ROOT)
    if fail_if_proxy_pass(lines):
        return 1
    for line in lines:
        print(line)
    executed = [line for line in lines if "NOT_EXECUTED" not in line and "PRESENT_NOT_RUN" not in line]
    if executed:
        print("FAIL unclassified a09 result")
        return 1
    print("PASS a09_discovery ids=4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
