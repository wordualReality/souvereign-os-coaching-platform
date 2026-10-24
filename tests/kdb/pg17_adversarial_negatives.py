#!/usr/bin/env python3
"""P2 adversarial negatives on disposable PostgreSQL 17.

(a) New command_id, foreign tenant, same kdb_ingest_runtime login.
(b) Same command_id and claimed request SHA with changed payload/rights.
(c) Direct table, approval, and promotion attempts.
(d) NULL request hash.

Unauthorized DB acceptance is a RED finding, not a security PASS.
PIAC remains fail-closed. No hosted apply.
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg17_disposable_command_path as cmd  # noqa: E402
from piac_fail_closed_probe import assert_piac_fail_closed  # noqa: E402

FINDINGS = []


def finding(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    print(f"{severity} {code} {json.dumps(detail) if not isinstance(detail, str) else detail}")


def rights_blob(status: str = "ADMITTED") -> tuple[str, str]:
    rights = {
        "rights_status": status,
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    raw = json.dumps(rights, separators=(",", ":"), sort_keys=True)
    return raw, cmd.sha256_text(raw)


def ingest_or_fail(**kwargs) -> tuple[bool, str]:
    sql = cmd.ingest_sql(**kwargs)
    proc = cmd.psql(cmd.USER_RUNTIME, sql)
    blob = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, blob


def main() -> None:
    assert_piac_fail_closed()
    cmd.ensure_container()
    cmd.ensure_schema()
    rights_json, rights_sha = rights_blob()
    content_a = cmd.sha256_text("p2-tenant-a-body")
    request_a = cmd.sha256_text("p2-request-a")
    command_a = str(uuid.uuid4())
    submission_a = str(uuid.uuid4())
    run_id = command_a[:8]
    tenant_a = "TENANT_SYNTH_A"
    tenant_b = "TENANT_SYNTH_B"

    ok, first = ingest_or_fail(
        command_id=command_a,
        submission_id=submission_a,
        tenant=tenant_a,
        origin="KDB",
        idem=f"idem-p2-a-{run_id}",
        request_sha=request_a,
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p2/tenant-a-{run_id}",
        content_sha=content_a,
        rights_json=rights_json,
        rights_sha=rights_sha,
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    )
    if ok and '"status":"RECORDED"' in first.replace(" ", ""):
        finding("SETUP_INGEST_STILL_ACCEPTED", "RED", first)
    elif ok:
        finding("SETUP_INGEST_UNEXPECTED_SUCCESS", "RED", first)
    else:
        finding("SETUP_INGEST_DENIED_FAIL_CLOSED", "CLOSED", first[:300])

    print("P2A_FRESH_FOREIGN_TENANT_NEW_COMMAND")
    command_b = str(uuid.uuid4())
    ok_b, body_b = ingest_or_fail(
        command_id=command_b,
        submission_id=str(uuid.uuid4()),
        tenant=tenant_b,
        origin="KDB",
        idem=f"idem-p2-b-{run_id}",
        request_sha=cmd.sha256_text("p2-request-b"),
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p2/tenant-b-{run_id}",
        content_sha=cmd.sha256_text("p2-tenant-b-body"),
        rights_json=rights_json,
        rights_sha=rights_sha,
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    )
    if ok_b and '"status":"RECORDED"' in body_b.replace(" ", ""):
        finding(
            "TENANT_GUC_SPOOF_ACCEPTED_AT_DB",
            "RED",
            "same kdb_ingest_runtime LOGIN wrote a new command_id for a second tenant; session_user is not tenant identity and PIAC is not consulted",
        )
    elif ok_b:
        finding("TENANT_GUC_SPOOF_UNEXPECTED_SUCCESS", "RED", body_b)
    else:
        finding("TENANT_GUC_SPOOF", "CLOSED", body_b)

    print("P2B_SAME_COMMAND_CLAIMED_HASH_CHANGED_PAYLOAD")
    other_rights, other_rights_sha = rights_blob()
    other_rights_obj = json.loads(other_rights)
    other_rights_obj["rights_basis"] = "synthetic-other-license"
    other_raw = json.dumps(other_rights_obj, separators=(",", ":"), sort_keys=True)
    ok_h, body_h = ingest_or_fail(
        command_id=command_a,
        submission_id=str(uuid.uuid4()),
        tenant=tenant_a,
        origin="KDB",
        idem=f"idem-p2-a-changed-{run_id}",
        request_sha=request_a,
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p2/tenant-a-changed-{run_id}",
        content_sha=cmd.sha256_text("p2-changed-payload"),
        rights_json=other_raw,
        rights_sha=cmd.sha256_text(other_raw),
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    )
    if ok_h:
        finding(
            "REQUEST_HASH_NOT_BOUND_TO_PAYLOAD",
            "RED",
            "same command_id and caller-supplied request_sha256 replayed while rights/content bytes changed; SQL trusts the hash string",
        )
    else:
        finding("REQUEST_HASH_PAYLOAD_BINDING", "CLOSED", body_h)

    print("P2C_DIRECT_TABLE_AND_PROMOTION")
    denials = [
        ("SELECT count(*) FROM kdb_canonical.protocol;", "runtime SELECT protocol"),
        (
            "INSERT INTO kdb_canonical.protocol(owning_module_ref, taxonomy_version_ref) "
            "VALUES('P2','TAX_SYNTH');",
            "runtime INSERT protocol",
        ),
        (
            "INSERT INTO kdb_governance.human_review_decision("
            "candidate_revision_id, candidate_content_sha256, reviewer_principal_ref, "
            "access_decision_ref, decision, source_rights_digest, review_evidence_sha256, "
            "signed_decision_ref, decided_at) VALUES ("
            f"'{uuid.uuid4()}', repeat('a',64), 'P2', 'P2', 'APPROVED_FOR_PROMOTION', "
            "repeat('a',64), repeat('a',64), 'P2', now());",
            "runtime INSERT human_review_decision",
        ),
        ("SET ROLE kdb_command_owner;", "runtime SET ROLE command_owner"),
        ("SET ROLE kdb_schema_owner;", "runtime SET ROLE schema_owner"),
    ]
    for sql, label in denials:
        proc = cmd.psql(cmd.USER_RUNTIME, sql)
        if proc.returncode == 0:
            finding("DIRECT_PRIVILEGE_ACCEPTED", "RED", label)
        else:
            finding("DIRECT_PRIVILEGE", "CLOSED", label)

    print("P2D_NULL_REQUEST_HASH")
    null_sql = cmd.ingest_sql(
        command_id=str(uuid.uuid4()),
        submission_id=str(uuid.uuid4()),
        tenant=tenant_a,
        origin="KDB",
        idem=f"idem-p2-null-hash-{run_id}",
        request_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p2/null-hash-{run_id}",
        content_sha=content_a,
        rights_json=rights_json,
        rights_sha=rights_sha,
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    ).replace(
        "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
        "NULL",
        1,
    )
    proc = cmd.psql(cmd.USER_RUNTIME, null_sql)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        finding("NULL_REQUEST_HASH_ACCEPTED", "RED", blob.strip())
    elif "KDB_HASH_INVALID" in blob:
        finding("NULL_REQUEST_HASH", "CLOSED", "KDB_HASH_INVALID")
    elif "permission denied" in blob or "denied" in blob:
        finding("NULL_REQUEST_HASH", "CLOSED", "runtime EXECUTE revoked")
    else:
        finding(
            "NULL_REQUEST_HASH_NOT_NAMED_EXCEPTION",
            "INFO",
            "NULL bypasses the regex IF and fails later on NOT NULL; not an accept",
        )

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    out = Path("/tmp/kdb-p2-adversarial-findings.json")
    payload = {
        "reviewer_blocking_gate": bool(red),
        "hosted_apply": "BLOCKED",
        "piac": "FAIL_CLOSED",
        "findings": FINDINGS,
    }
    raw = json.dumps(payload, indent=2) + "\n"
    out.write_text(raw)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    print("FINDINGS_PATH", out)
    print("FINDINGS_SHA256", digest)
    print("RED_COUNT", len(red))
    direct_red = [row for row in red if row["code"] == "DIRECT_PRIVILEGE_ACCEPTED"]
    if direct_red:
        raise SystemExit("RED_DIRECT_TABLE_OR_PROMOTION")
    if red:
        print("REVIEWER_BLOCKING_NEGATIVE_GATE")
        for row in red:
            print("RED", row["code"])
        print("PASS_P2_ADVERSARIAL_CHARACTERIZATION")
        print("FAIL_CLOSED_UNRESOLVED_SECURITY_CASES")
        print("NOTE_NOT_A_SECURITY_PASS")
        return
    print("PASS_P2_ADVERSARIAL_NEGATIVES")


if __name__ == "__main__":
    main()
