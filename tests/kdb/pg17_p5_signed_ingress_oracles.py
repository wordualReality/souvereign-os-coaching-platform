#!/usr/bin/env python3
"""P5 signed ingress plus DB fail-closed. Disposable PostgreSQL 17.

LOCAL_SIGNED_INGRESS_VERIFIED is not DB_COMMAND_ADMITTED. Runtime EXECUTE
stays revoked after probes. Unexpected SQL errors are RED.
"""
from __future__ import annotations

import json
import secrets
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
import pg17_disposable_command_path as cmd  # noqa: E402
from digest_v2 import local_digest, o1_fields, sql_jsonb_build_array  # noqa: E402
from piac_fail_closed_probe import assert_piac_fail_closed  # noqa: E402
from p5_trust_denial import (  # noqa: E402
    TRUST_PSQL_RC,
    classify_db_fail_closed,
    error_messages,
    evaluate_rb02_matrix,
)
from signed_ingress import (  # noqa: E402
    DB_NOT_ADMITTED,
    LOCAL_VERIFIED,
    SignedIngressError,
    SignedIngressPipeline,
    SignedIngressVerifier,
    mac_hex,
)

INGEST = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,"
    "text,text,text,text,uuid,timestamptz)"
)
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    print(f"{severity} {code} {detail if isinstance(detail, str) else json.dumps(detail)}")


UNEXPECTED = (
    "could not connect",
    "connection refused",
    "does not exist",
    "syntax error",
    "division by zero",
    "invalid input syntax",
    "server closed the connection",
)


def classify_tenant_spoof(body: str) -> str:
    lower = (body or "").lower()
    if any(token in lower for token in UNEXPECTED):
        return "RED"
    if "KDB_HASH_MISMATCH" in body:
        return "CLOSED"
    if "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in body:
        return "RED"
    return "RED"


def set_runtime_execute(grant: bool) -> None:
    verb = "GRANT" if grant else "REVOKE"
    direction = "TO" if grant else "FROM"
    cmd.must(
        cmd.USER_SUPER,
        f"{verb} EXECUTE ON FUNCTION {INGEST} {direction} kdb_ingest_runtime;",
    )


def main() -> None:
    assert_piac_fail_closed()
    cmd.ensure_container()
    cmd.ensure_schema()
    superuser = cmd.USER_SUPER
    print("P5_00_ORACLE_MUTATION")
    if classify_tenant_spoof("ERROR: KDB_SECURITY_CONTEXT_NOT_CONFIGURED") != "RED":
        note("TENANT_SPOOF_ORACLE_WEAK", "RED", "trust denial must not pass tenant-binding probe")
    else:
        note("TENANT_SPOOF_ORACLE_MUTATION", "CLOSED", "SECURITY_CONTEXT_NOT_CONFIGURED is not CLOSED")
    print("RB02_MATRIX_BEGIN")
    matrix_failed = False
    for label, code, sev, exp_code, exp_sev in evaluate_rb02_matrix():
        print("RB02_MATRIX", label, "got", code, sev, "want", exp_code, exp_sev)
        if (code, sev) != (exp_code, exp_sev):
            matrix_failed = True
            note("RB02_MATRIX_CELL_FAILED", "RED", label)
    print("RB02_MATRIX_END")
    if not matrix_failed:
        note("RB02_MATRIX_PASS", "CLOSED", "all required cells")

    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    rights_json = json.dumps(rights, separators=(",", ":"), sort_keys=True)
    command_id = str(uuid.uuid4())
    submission_id = str(uuid.uuid4())
    tenant_a = "TENANT_SYNTH_A"
    tenant_b = "TENANT_SYNTH_B"
    origin = "KDB"
    purpose = "kdb_knowledge_intake"
    source_class = "LICENSED_DOCUMENT"
    locator = "synthetic://kdb/p5/ingress"
    content_sha = cmd.sha256_text("p5-body")
    principal = "PRINCIPAL_REF_SYNTH_PIPELINE"
    access = "ACCESS_SYNTH_OK"
    idem = "idem-p5-ingress"
    rights_pg = cmd.must(superuser, f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(rights_json)}::jsonb);")
    fields = o1_fields(
        command_id,
        tenant_a,
        origin,
        purpose,
        source_class,
        locator,
        content_sha,
        rights_pg,
        principal,
        access,
        idem,
        submission_id,
    )
    sql_digest = cmd.must(superuser, f"SELECT kdb_ops.canonical_digest_v2({sql_jsonb_build_array(fields)});")
    if local_digest(fields) != sql_digest:
        note("ADAPTER_SQL_MISMATCH", "RED", "local adapter diverged from SQL")
    else:
        note("ADAPTER_SQL_PARITY", "CLOSED", sql_digest[:16])

    omitted = list(fields)
    omitted.pop(3)
    omitted_digest = local_digest(omitted)
    print("P5_00_TENANT_BINDING_LIVE")
    try:
        set_runtime_execute(True)
        spoof = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.ingest_sql(
                command_id=str(uuid.uuid4()),
                submission_id=str(uuid.uuid4()),
                tenant=tenant_b,
                origin=origin,
                idem=idem + "-spoof",
                request_sha=sql_digest,
                source_class=source_class,
                locator=locator + "-b",
                content_sha=content_sha,
                rights_json=rights_json,
                rights_sha=rights_pg,
                principal=principal,
                access=access,
                purpose=purpose,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        body = (spoof.stdout + spoof.stderr).strip()
        if spoof.returncode == 0:
            note("TENANT_GUC_SPOOF_ACCEPTED_AT_DB", "RED", body[:300])
        elif classify_tenant_spoof(body) == "CLOSED":
            note("TENANT_SPOOF_HASH_MISMATCH", "CLOSED", "KDB_HASH_MISMATCH")
        else:
            note("TENANT_SPOOF_NOT_HASH_MISMATCH", "RED", body[:400])

        omitted_call = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.ingest_sql(
                command_id=command_id,
                submission_id=submission_id,
                tenant=tenant_a,
                origin=origin,
                idem=idem,
                request_sha=omitted_digest,
                source_class=source_class,
                locator=locator,
                content_sha=content_sha,
                rights_json=rights_json,
                rights_sha=rights_pg,
                principal=principal,
                access=access,
                purpose=purpose,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        omitted_body = (omitted_call.stdout + omitted_call.stderr).strip()
        if "KDB_HASH_MISMATCH" in omitted_body:
            note("OMITTED_TENANT_DIGEST_REJECTED", "CLOSED", "KDB_HASH_MISMATCH")
        elif "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in omitted_body:
            note("TENANT_NOT_IN_DIGEST", "RED", "omitted tenant reached trust gate")
        else:
            note("OMITTED_TENANT_UNEXPECTED", "RED", omitted_body[:400])

        key = secrets.token_bytes(32)
        replay = set()
        verifier = SignedIngressVerifier(
            keys={"kid-p5": key},
            issuer="kdb-synth-issuer",
            audience="kdb-local-ingress",
            replay_store=replay,
            revocation_store=set(),
            now=lambda: 1_000_000,
        )
        claims = {
            "iss": "kdb-synth-issuer",
            "aud": "kdb-local-ingress",
            "kid": "kid-p5",
            "jti": str(uuid.uuid4()),
            "nbf": 1,
            "exp": 2_000_000,
            "principal": principal,
            "tenant": tenant_a,
            "purpose": purpose,
            "command_id": command_id,
            "request_digest": sql_digest,
            "nonce": str(uuid.uuid4()),
        }
        signed = {"claims": claims, "mac": mac_hex(key, claims)}
        envelope = {
            "tenant": tenant_a,
            "purpose": purpose,
            "command_id": command_id,
            "access_decision_ref": "SYNTHETIC_ALLOW",
        }
        db_state: dict[str, object] = {}

        def ingest_kwargs() -> dict:
            return {
                "command_id": command_id,
                "submission_id": submission_id,
                "tenant": tenant_a,
                "origin": origin,
                "idem": idem,
                "request_sha": sql_digest,
                "source_class": source_class,
                "locator": locator,
                "content_sha": content_sha,
                "rights_json": rights_json,
                "rights_sha": rights_pg,
                "principal": principal,
                "access": access,
                "purpose": purpose,
                "correlation_id": str(uuid.uuid4()),
            }

        def db_attempt() -> str:
            proc = cmd.psql(cmd.USER_RUNTIME, cmd.ingest_sql(**ingest_kwargs()))
            body = (proc.stdout + proc.stderr).strip()
            db_state["rc"] = proc.returncode
            db_state["body"] = body
            print("CLAIM TRUST_FAIL_CLOSED")
            print("PSQL_RC", proc.returncode)
            return body

        missing = cmd.psql(superuser, "SELECT kdb_ops.no_such_ingest_source();")
        miss_code, miss_sev = classify_db_fail_closed(
            psql_rc=missing.returncode, body=(missing.stdout + missing.stderr)
        )
        if miss_sev == "CLOSED":
            note("MISSING_ROUTINE_CLASSIFIED_CLOSED", "RED", miss_code)
        else:
            note("MISSING_ROUTINE_IS_RED", "CLOSED", miss_code)

        wrong_role = cmd.psql(superuser, cmd.ingest_sql(**ingest_kwargs()))
        role_code, role_sev = classify_db_fail_closed(
            psql_rc=wrong_role.returncode, body=(wrong_role.stdout + wrong_role.stderr)
        )
        if role_sev == "CLOSED":
            note("WRONG_ROLE_CLASSIFIED_AS_TRUST", "RED", role_code)
        else:
            note("WRONG_ROLE_NOT_TRUST_CLOSED", "CLOSED", role_code)

        try:
            result = SignedIngressPipeline(verifier).evaluate(
                envelope=envelope,
                signed=signed,
                expected_digest=sql_digest,
                db_attempt=db_attempt,
            )
        except SignedIngressError as exc:
            note("SIGNED_PIPELINE_FAILED", "RED", exc.code)
        else:
            trust_code, trust_sev = classify_db_fail_closed(
                psql_rc=int(db_state.get("rc", 1)),
                body=str(db_state.get("body") or result["db_denial"]),
            )
            print("ORACLE_CODE", trust_code)
            print("ORACLE_SEVERITY", trust_sev)
            live_errors = error_messages(str(db_state.get("body") or ""))
            print("LIVE_ERROR_LINE_COUNT", len(live_errors))
            if len(live_errors) != 1:
                note("LIVE_INGEST_NOT_SINGLE_ERROR", "RED", live_errors)
            if result["local_signed_ingress"] != LOCAL_VERIFIED:
                note("LOCAL_SIGNED_INGRESS_MISSING", "RED", result)
            elif result["db_command"] != DB_NOT_ADMITTED:
                note("DB_COMMAND_ADMITTED", "RED", result)
            elif int(db_state.get("rc", 1)) != TRUST_PSQL_RC:
                note("LIVE_TRUST_WRONG_PSQL_RC", "RED", db_state.get("rc"))
            elif trust_sev != "CLOSED" or trust_code != "TRUST_FAIL_CLOSED":
                note("DB_FAIL_CLOSED_NOT_EXACT", "RED", {"code": trust_code, "body": result["db_denial"]})
            elif len(live_errors) != 1:
                pass
            else:
                note("LOCAL_SIGNED_INGRESS_VERIFIED", "CLOSED", "synthetic MAC recognized")
                note("DB_COMMAND_NOT_ADMITTED", "CLOSED", result["db_denial"][:120])
                print("SIGNATURE_NEGATIVE_PASS")
                print("DB_FAIL_CLOSED_PASS")

        print("P5_GRANT_STRIP_MUTATION")
        set_runtime_execute(False)
        stripped = cmd.psql(cmd.USER_RUNTIME, cmd.ingest_sql(**ingest_kwargs()))
        stripped_body = (stripped.stdout + stripped.stderr).strip()
        strip_code, strip_sev = classify_db_fail_closed(
            psql_rc=stripped.returncode, body=stripped_body
        )
        print("PSQL_RC", stripped.returncode)
        print("ORACLE_CODE", strip_code)
        print("ORACLE_SEVERITY", strip_sev)
        if strip_sev == "CLOSED" or "DB_FAIL_CLOSED_PASS" in strip_code:
            note("PERMISSION_DENIED_MISREPORTED_AS_TRUST", "RED", stripped_body[:300])
        elif strip_code != "PERMISSION_DENIED_NOT_TRUST":
            note("GRANT_STRIP_UNEXPECTED", "RED", {"code": strip_code, "body": stripped_body[:300]})
        else:
            note(
                "GRANT_STRIP_MUTATION_KILLED",
                "CLOSED",
                "permission denied is not DB_FAIL_CLOSED_PASS",
            )
        set_runtime_execute(True)
    finally:
        set_runtime_execute(False)
        leftover = cmd.must(
            superuser,
            f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(INGEST)}, 'EXECUTE');",
        )
        if leftover in {"t", "true"}:
            note("RUNTIME_EXECUTE_NOT_REVOKED_AFTER_PROBE", "RED", leftover)

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    print("RED_COUNT", len(red))
    if red:
        print("RED_SECURITY_FINDINGS")
        for row in red:
            print("RED", row["code"])
        raise SystemExit(1)
    print("PASS_P5_SIGNED_INGRESS_ORACLES")
    print("NOTE_NOT_E2E_BETA_PASS")
    print("NOTE_NOT_A_HOSTED_OR_INDEPENDENT_SECURITY_PASS")


if __name__ == "__main__":
    main()
