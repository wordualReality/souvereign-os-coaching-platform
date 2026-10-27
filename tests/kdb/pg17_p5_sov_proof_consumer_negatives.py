#!/usr/bin/env python3
"""Isolated PG17 negatives for the SOV proof consumer. No lasting EXECUTE grant.

A synthetic LOCAL_VERIFIED_ONLY proof must not become DB_COMMAND_ADMITTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
import pg17_disposable_command_path as cmd  # noqa: E402
from digest_v2 import local_digest, sql_jsonb_build_array  # noqa: E402
from p5_trust_denial import classify_db_fail_closed  # noqa: E402
from sov_proof_consumer import (  # noqa: E402
    CONSUMER_DISABLED,
    DB_NOT_ADMITTED,
    LOCAL_VERIFIED,
    SovProofConsumer,
    SovProofError,
)
from sov_proof_fixtures import (  # noqa: E402
    ACCESS,
    COMMAND_ID,
    CONTENT,
    NOW,
    PRINCIPAL,
    PURPOSE,
    RIGHTS,
    SUBMISSION_ID,
    TENANT,
    EphemeralAuthority,
    envelope,
    expected_context,
    o1_ascii_fields,
)

INGEST = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,"
    "text,text,text,text,uuid,timestamptz)"
)
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    print(f"{severity} {code} {detail if isinstance(detail, str) else json.dumps(detail)}")


def execute_granted() -> bool:
    value = cmd.must(
        cmd.USER_SUPER,
        f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(INGEST)}, 'EXECUTE');",
    )
    return value in {"t", "true"}


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    if execute_granted():
        cmd.must(cmd.USER_SUPER, f"REVOKE EXECUTE ON FUNCTION {INGEST} FROM kdb_ingest_runtime;")
        note("RUNTIME_EXECUTE_REVOKED_FOR_PROBE", "CLOSED", "start revoked")
    if execute_granted():
        note("RUNTIME_EXECUTE_STILL_GRANTED", "RED", "REVOKE failed")
        raise SystemExit(1)

    fields = o1_ascii_fields()
    sql_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.canonical_digest_v2({sql_jsonb_build_array(fields)});",
    )
    if local_digest(fields) != sql_digest:
        note("ADAPTER_SQL_MISMATCH", "RED", sql_digest)
    else:
        note("ADAPTER_SQL_PARITY", "CLOSED", sql_digest[:16])

    receipts_before = cmd.must(cmd.USER_SUPER, "SELECT count(*) FROM kdb_ops.command_receipt;")

    authority = EphemeralAuthority()
    consumer = SovProofConsumer(
        enabled=True,
        trust={authority.metadata.kid: authority.metadata},
        replay_store=set(),
        now=lambda: NOW,
    )
    try:
        verdict = consumer.evaluate(envelope(authority), expected_context())
    except SovProofError as exc:
        note("SYNTHETIC_PROOF_REJECTED", "RED", exc.code)
        verdict = {}
    else:
        if verdict.get("verdict") != LOCAL_VERIFIED or verdict.get("db_command") != DB_NOT_ADMITTED:
            note("SYNTHETIC_PROOF_ADMITTED_DB", "RED", verdict)
        elif verdict.get("db_command_admitted") is True:
            note("DB_COMMAND_ADMITTED", "RED", verdict)
        else:
            note("LOCAL_VERIFIED_ONLY", "CLOSED", "synthetic proof stays local")

    disabled = SovProofConsumer(
        enabled=False,
        trust={authority.metadata.kid: authority.metadata},
        replay_store=set(),
        now=lambda: NOW,
    )
    try:
        disabled.evaluate(envelope(authority), expected_context())
        note("DISABLED_CONSUMER_ACCEPTED", "RED", "default-off path must fail closed")
    except SovProofError as exc:
        if exc.code == CONSUMER_DISABLED:
            note("DISABLED_CONSUMER_FAIL_CLOSED", "CLOSED", CONSUMER_DISABLED)
        else:
            note("DISABLED_CONSUMER_WRONG_CODE", "RED", exc.code)

    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": [PURPOSE],
        "media_type": "application/octet-stream",
    }
    ingest = cmd.psql(
        cmd.USER_RUNTIME,
        cmd.ingest_sql(
            command_id=COMMAND_ID,
            submission_id=SUBMISSION_ID,
            tenant=TENANT,
            origin="KDB",
            idem="idem-p5",
            request_sha=sql_digest,
            source_class="LICENSED_DOCUMENT",
            locator="synthetic://kdb/p5/a",
            content_sha=CONTENT,
            rights_json=json.dumps(rights, separators=(",", ":"), sort_keys=True),
            rights_sha=RIGHTS,
            principal=PRINCIPAL,
            access=ACCESS,
            purpose=PURPOSE,
            correlation_id="00000000-0000-4000-8000-0000000000aa",
        ),
    )
    body = (ingest.stdout + ingest.stderr).strip()
    trust_code, trust_sev = classify_db_fail_closed(psql_rc=ingest.returncode, body=body)
    print("PSQL_RC", ingest.returncode)
    print("ORACLE_CODE", trust_code)
    print("ORACLE_SEVERITY", trust_sev)
    if ingest.returncode == 0:
        note("INGEST_SUCCEEDED_AFTER_LOCAL_PROOF", "RED", body[:300])
    elif trust_sev == "CLOSED":
        note("PERMISSION_DENIED_MISREPORTED_AS_TRUST", "RED", body[:300])
    elif trust_code == "PERMISSION_DENIED_NOT_TRUST":
        note("PROOF_DID_NOT_ADMIT_DB_COMMAND", "CLOSED", "runtime EXECUTE stays revoked")
    else:
        note("INGEST_UNEXPECTED", "RED", {"code": trust_code, "body": body[:300]})

    if execute_granted():
        note("RUNTIME_EXECUTE_NOT_REVOKED_AFTER_PROBE", "RED", "EXECUTE granted")
    else:
        note("RUNTIME_EXECUTE_STILL_REVOKED", "CLOSED", "no lasting GRANT")

    receipts_after = cmd.must(cmd.USER_SUPER, "SELECT count(*) FROM kdb_ops.command_receipt;")
    if receipts_after != receipts_before:
        note("COMMAND_RECEIPT_MUTATED", "RED", {"before": receipts_before, "after": receipts_after})
    else:
        note("COMMAND_RECEIPT_UNCHANGED", "CLOSED", receipts_after)

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    print("RED_COUNT", len(red))
    if red:
        print("RED_SECURITY_FINDINGS")
        for row in red:
            print("RED", row["code"])
        raise SystemExit(1)
    print("PASS_P5_SOV_PROOF_CONSUMER_NEGATIVES")
    print("NOTE_NEEDS_SOV_SECURITY_QS")
    print("NOTE_NOT_DB_COMMAND_ADMITTED")


if __name__ == "__main__":
    main()
