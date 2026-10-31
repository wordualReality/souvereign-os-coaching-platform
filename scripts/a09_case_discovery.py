#!/usr/bin/env python3
"""Find admitted A09 cases. A local file or a boolean is not an owner receipt."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = ("A09-T01", "A09-T04", "A09-T44", "A09-T48")


def load_json(path):
    try:
        return json.loads(path.read_text()), None
    except json.JSONDecodeError:
        return None, "invalid"


def classify(root, case_id, source_revision=None):
    folder = root / "docs" / "arcava" / "admission" / "a09" / case_id
    case_file = folder / "case.json"
    owner_file = folder / "owner-receipt.json"
    engine_file = folder / "engine.json"
    case_state = "absent"
    owner_state = "absent"
    engine_state = "absent"
    if case_file.is_file():
        payload, error = load_json(case_file)
        if error or not isinstance(payload, dict) or payload.get("case_id") != case_id:
            case_state = "invalid"
        elif payload.get("status") == "PASS" and "fixture" not in payload:
            case_state = "invalid"
        else:
            case_state = "present"
    if engine_file.is_file():
        payload, error = load_json(engine_file)
        if error or not isinstance(payload, dict) or not payload.get("entrypoint"):
            engine_state = "invalid"
        elif payload.get("status") == "PASS" and payload.get("entrypoint") in ("", "PASS"):
            engine_state = "invalid"
        else:
            engine_state = "present"
    if owner_file.is_file():
        payload, error = load_json(owner_file)
        if error or not isinstance(payload, dict):
            owner_state = "invalid"
        elif payload.get("case_id") != case_id:
            owner_state = "mismatch"
        elif source_revision is None:
            owner_state = "not_verified"
        elif "source_revision" not in payload or payload.get("source_revision") != source_revision:
            owner_state = "wrong_revision"
        elif payload.get("owner_admitted") is True and not payload.get("authorization"):
            owner_state = "forged"
        elif not payload.get("owner") or not payload.get("authorization"):
            owner_state = "absent_authority"
        else:
            owner_state = "unverified"
    if case_state == "present" and engine_state == "present" and owner_state == "unverified":
        status = "PRESENT_NOT_RUN_WITH_UNVERIFIED_OWNER"
    elif case_state == "present" and engine_state == "present" and owner_state == "absent_authority":
        status = "PRESENT_NOT_RUN_WITH_UNVERIFIED_OWNER"
    else:
        status = "NOT_EXECUTED"
    return status, case_state, owner_state, engine_state


def report(root, source_revision=None):
    lines = []
    for case_id in IDS:
        status, case_state, owner_state, engine_state = classify(root, case_id, source_revision)
        marker = "MISSING " if status == "NOT_EXECUTED" else ""
        lines.append(
            "{id} {status} {marker}case={case} owner_receipt={owner} engine={engine}".format(
                id=case_id,
                status=status,
                marker=marker,
                case=case_state,
                owner=owner_state,
                engine=engine_state,
            )
        )
    return lines


def source_revision(root):
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return None
    return sha


def discover(root):
    revision = source_revision(root)
    marker = revision if revision else "NOT_VERIFIED"
    return revision, ["SOURCE_REVISION " + marker, *report(root, revision)]


def fail_if_proxy_pass(lines):
    for line in lines:
        if " PASS" in line or line.endswith(" PASS"):
            print("FAIL proxy pass")
            return 1
    return 0


def require_line(lines, case_id, status, owner_state):
    match = [line for line in lines if line.startswith(case_id + " ")]
    if len(match) != 1 or status not in match[0] or "owner_receipt=" + owner_state not in match[0]:
        print("FAIL " + case_id + " expected " + status + " owner_receipt=" + owner_state)
        print("\n".join(match))
        return 1
    return fail_if_proxy_pass(match)


def write_case(root, case_id, case_body, engine_body, owner_body):
    folder = root / "docs" / "arcava" / "admission" / "a09" / case_id
    folder.mkdir(parents=True)
    (folder / "case.json").write_text(case_body)
    (folder / "engine.json").write_text(engine_body)
    (folder / "owner-receipt.json").write_text(owner_body)


def self_check():
    revision = "a2dd98dfc3bf86c3c32d1e8638f35d1d294c20f1"
    real_case = '{"case_id":"A09-T01","fixture":"synthetic"}'
    real_engine = '{"entrypoint":"a09.engine.NotPresent"}'
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        empty = report(root, revision)
        if fail_if_proxy_pass(empty) or any("NOT_EXECUTED" not in line for line in empty):
            print("FAIL empty tree was treated as executed")
            return 1
        partial = root / "docs" / "arcava" / "admission" / "a09" / "A09-T01"
        partial.mkdir(parents=True)
        (partial / "case.json").write_text('{"status":"PASS"}')
        partial_lines = report(root, revision)
        if require_line(partial_lines, "A09-T01", "NOT_EXECUTED", "absent"):
            return 1
        if "case=invalid" not in partial_lines[0]:
            print("FAIL a PASS string was treated as a case")
            return 1

        invalid_root = Path(raw) / "invalid-engine"
        write_case(
            invalid_root,
            "A09-T01",
            real_case,
            '{"status":"PASS"}',
            '{"case_id":"A09-T01","source_revision":"%s"}' % revision,
        )
        invalid_lines = report(invalid_root, revision)
        if require_line(invalid_lines, "A09-T01", "NOT_EXECUTED", "absent_authority"):
            return 1
        if "engine=invalid" not in invalid_lines[0]:
            print("FAIL an engine without an entrypoint was accepted")
            return 1

        mismatch_root = Path(raw) / "mismatch"
        write_case(
            mismatch_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T04","source_revision":"%s","owner":"other","authorization":"external"}' % revision,
        )
        if require_line(report(mismatch_root, revision), "A09-T01", "NOT_EXECUTED", "mismatch"):
            return 1

        revision_root = Path(raw) / "revision"
        write_case(
            revision_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T01","source_revision":"wrong","owner":"other","authorization":"external"}',
        )
        if require_line(report(revision_root, revision), "A09-T01", "NOT_EXECUTED", "wrong_revision"):
            return 1

        forged_root = Path(raw) / "forged"
        write_case(
            forged_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T01","source_revision":"%s","owner_admitted":true}' % revision,
        )
        if require_line(report(forged_root, revision), "A09-T01", "NOT_EXECUTED", "forged"):
            return 1

        authority_root = Path(raw) / "authority"
        write_case(
            authority_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T01","source_revision":"%s","owner":"other"}' % revision,
        )
        authority_lines = report(authority_root, revision)
        if require_line(authority_lines, "A09-T01", "PRESENT_NOT_RUN_WITH_UNVERIFIED_OWNER", "absent_authority"):
            return 1

        live_root = Path(raw) / "live-revision"
        live_root.mkdir()
        git_env = os.environ.copy()
        git_env.update(
            {
                "GIT_AUTHOR_NAME": "a09",
                "GIT_AUTHOR_EMAIL": "a09@example.invalid",
                "GIT_COMMITTER_NAME": "a09",
                "GIT_COMMITTER_EMAIL": "a09@example.invalid",
            }
        )
        subprocess.run(["git", "init"], cwd=live_root, check=True, capture_output=True, env=git_env)
        (live_root / "seed").write_text("seed\n")
        subprocess.run(["git", "add", "seed"], cwd=live_root, check=True, capture_output=True, env=git_env)
        subprocess.run(["git", "commit", "-m", "seed"], cwd=live_root, check=True, capture_output=True, env=git_env)
        sha = source_revision(live_root)
        write_case(
            live_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T01","source_revision":"wrong","owner":"other","authorization":"external"}',
        )
        live_revision, live_lines = discover(live_root)
        if live_revision != sha or require_line(live_lines, "A09-T01", "NOT_EXECUTED", "wrong_revision"):
            print("FAIL the default discovery skipped the source revision")
            print("\n".join(live_lines))
            return 1

        unverified_root = Path(raw) / "unverified"
        write_case(
            unverified_root,
            "A09-T01",
            real_case,
            real_engine,
            '{"case_id":"A09-T01","source_revision":"%s","owner":"other","authorization":"external"}' % sha,
        )
        unverified_revision, unverified_lines = discover(unverified_root)
        if unverified_revision is not None or "SOURCE_REVISION NOT_VERIFIED" not in unverified_lines[0]:
            print("FAIL a tree without a source revision was verified")
            return 1
        if require_line(unverified_lines, "A09-T01", "NOT_EXECUTED", "not_verified"):
            return 1
    print(
        "PASS a09_discovery_negative empty=not_executed partial=not_executed "
        "invalid_engine=not_executed case_mismatch=not_executed wrong_revision=not_executed "
        "forged_owner=not_executed absent_authority=unverified_not_run "
        "default_path=revision_checked unverified_tree=not_executed proxy_pass=absent"
    )
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        return self_check()
    revision, lines = discover(ROOT)
    if revision is None:
        print("FAIL source revision is not verified")
        return 1
    if fail_if_proxy_pass(lines):
        return 1
    for line in lines:
        print(line)
    case_lines = [line for line in lines if line.startswith("A09-")]
    if any("NOT_EXECUTED" not in line for line in case_lines):
        print("FAIL live a09 tree is not NOT_EXECUTED")
        return 1
    print(
        "A09_REQUIRED ids=A09-T01,A09-T04,A09-T44,A09-T48 "
        "paths=docs/arcava/admission/a09/<ID>/case.json,engine.json,owner-receipt.json "
        "fields=case_id,source_revision,owner,authorization"
    )
    print("PASS a09_discovery ids=4 result=NOT_EXECUTED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
