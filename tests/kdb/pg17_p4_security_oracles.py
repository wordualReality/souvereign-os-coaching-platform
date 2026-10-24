#!/usr/bin/env python3
"""P4 digest and fail-closed oracle integrity. Nonzero exit on weak negatives.

Unexpected SQL errors are RED, not CLOSED. Temporary-grant tests cover O1, O2
and O3. Does not apply 004/098/P2 recovery. Does not connect to Supabase.
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

INGEST = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,"
    "text,text,text,text,uuid,timestamptz)"
)
PROPOSE = "kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid)"
HANDOFF = "kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid)"
UNTRUSTED = ("anon", "authenticated", "service_role", "public")
UNEXPECTED = (
    "could not connect",
    "does not exist",
    "syntax error",
    "division by zero",
    "invalid input syntax",
    "server closed the connection",
    "not PostgreSQL 17",
)
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    payload = json.dumps(detail) if not isinstance(detail, str) else detail
    print(f"{severity} {code} {payload}")


def truthy(value: str) -> bool:
    return value in {"t", "true"}


def blob_of(proc) -> str:
    return (proc.stdout + proc.stderr).strip()


def unexpected(blob: str) -> str | None:
    lower = blob.lower()
    for token in UNEXPECTED:
        if token in lower:
            return token
    return None


def require_denied(blob: str, *needles: str, code: str) -> None:
    hit = unexpected(blob)
    if hit:
        note(code, "RED", {"unexpected": hit, "blob": blob[:400]})
        return
    if not any(needle in blob for needle in needles):
        note(code, "RED", {"expected": needles, "blob": blob[:400]})
        return
    note(code, "CLOSED", needles[0])


def set_runtime_execute(grant: bool) -> None:
    verb = "GRANT" if grant else "REVOKE"
    direction = "TO" if grant else "FROM"
    for fn in (INGEST, PROPOSE, HANDOFF):
        cmd.must(
            cmd.USER_SUPER,
            f"{verb} EXECUTE ON FUNCTION {fn} {direction} kdb_ingest_runtime;",
        )


def rights_blob() -> str:
    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    return json.dumps(rights, separators=(",", ":"), sort_keys=True)


def o1_digest_sql(
    command_id: str,
    tenant: str,
    origin: str,
    purpose: str,
    source_class: str,
    locator: str,
    content_sha: str,
    rights_digest: str,
    principal: str,
    access: str,
    idem: str,
    submission_id: str,
) -> str:
    return (
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array("
        f"'v2','SOURCE_INTAKE','{command_id}'::uuid,{cmd.psql_str(tenant)},"
        f"{cmd.psql_str(origin)},{cmd.psql_str(purpose)},{cmd.psql_str(source_class)},"
        f"{cmd.psql_str(locator)},{cmd.psql_str(content_sha)},{cmd.psql_str(rights_digest)},"
        f"{cmd.psql_str(principal)},{cmd.psql_str(access)},{cmd.psql_str(idem)},"
        f"'{submission_id}'::uuid));"
    )


def main() -> None:
    assert_piac_fail_closed()
    cmd.ensure_container()
    cmd.ensure_schema()
    superuser = cmd.USER_SUPER

    ver = cmd.must(superuser, "SHOW server_version;")
    if "17." not in ver:
        note("WRONG_POSTGRES_VERSION", "RED", ver)
        raise SystemExit(1)
    ingest_exists = cmd.must(
        superuser,
        f"SELECT to_regprocedure({cmd.psql_str(INGEST)}) IS NOT NULL;",
    )
    if not truthy(ingest_exists):
        note("INGEST_FUNCTION_MISSING", "RED", INGEST)
        raise SystemExit(1)

    print("P4_FAULT_INJECTION_CLASSIFIER")
    boom = blob_of(cmd.psql(superuser, "SELECT 1/0;"))
    if "division by zero" not in boom.lower():
        note("FAULT_INJECTION_SETUP", "RED", boom[:300])
    elif unexpected(boom) == "division by zero":
        note("FAULT_INJECTION_NOT_CLOSED", "CLOSED", "division by zero stays RED class")
    else:
        note("FAULT_INJECTION_MISCLASSIFIED", "RED", boom[:300])

    ready = cmd.must(superuser, "SELECT kdb_ops.security_context_ready();")
    if truthy(ready):
        note("SECURITY_CONTEXT_READY_TRUE", "RED", ready)
    else:
        note("SECURITY_CONTEXT_READY_FALSE", "CLOSED", ready)

    src = cmd.must(
        superuser,
        "SELECT string_agg(pg_get_functiondef(p.oid), E'\\n') "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='kdb_ops' AND p.proname IN "
        "('ingest_source','propose_candidate','request_review_handoff');",
    )
    if "concat_ws" in src:
        note("COMMAND_STILL_USES_CONCAT_WS", "RED", "concat_ws remains in command functions")
    else:
        note("COMMAND_DIGEST_V2", "CLOSED", "no concat_ws in O1-O3")
    if "p_evidence_spans" not in src or "v_spans_digest" not in src:
        note("O2_EVIDENCE_SPANS_UNBOUND", "RED", "propose_candidate missing spans digest")
    else:
        note("O2_EVIDENCE_SPANS_BOUND", "CLOSED", "v_spans_digest present")
    if src.count("security_context_ready()") < 3:
        note("TRUST_HELPER_UNUSED", "RED", src.count("security_context_ready()"))
    else:
        note("TRUST_HELPER_CONSULTED", "CLOSED", "all three commands consult the helper")

    print("P4A_RUNTIME_EXECUTE_REVOKED")
    for fn in (INGEST, PROPOSE, HANDOFF):
        exe = cmd.must(
            superuser,
            f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(fn)}, 'EXECUTE');",
        )
        if truthy(exe):
            note("RUNTIME_EXECUTE_STILL_GRANTED", "RED", fn)
        else:
            note("RUNTIME_EXECUTE_REVOKED", "CLOSED", fn)

    rights_json = rights_blob()
    command_a = str(uuid.uuid4())
    submission_a = str(uuid.uuid4())
    run_id = command_a[:8]
    tenant_a = "TENANT_SYNTH_A"
    tenant_b = "TENANT_SYNTH_B"
    content_a = cmd.sha256_text("p4-tenant-a-body")
    origin = "KDB"
    purpose = "kdb_knowledge_intake"
    source_class = "LICENSED_DOCUMENT"
    principal = "PRINCIPAL_REF_SYNTH_PIPELINE"
    access = "ACCESS_SYNTH_OK"

    print("P4A_FOREIGN_TENANT_WITHOUT_EXECUTE")
    proc = cmd.psql(
        cmd.USER_RUNTIME,
        cmd.ingest_sql(
            command_id=str(uuid.uuid4()),
            submission_id=str(uuid.uuid4()),
            tenant=tenant_b,
            origin=origin,
            idem=f"idem-p4-b-{run_id}",
            request_sha=cmd.sha256_text("p4-request-b"),
            source_class=source_class,
            locator=f"synthetic://kdb/p4/tenant-b-{run_id}",
            content_sha=cmd.sha256_text("p4-tenant-b-body"),
            rights_json=rights_json,
            rights_sha=cmd.sha256_text(rights_json),
            principal=principal,
            access=access,
            purpose=purpose,
            correlation_id=str(uuid.uuid4()),
        ),
    )
    if proc.returncode == 0:
        note("TENANT_GUC_SPOOF_ACCEPTED_AT_DB", "RED", blob_of(proc))
    else:
        require_denied(
            blob_of(proc),
            "permission denied for function ingest_source",
            code="TENANT_GUC_SPOOF",
        )

    print("P4B_CHANGED_PAYLOAD_WITHOUT_EXECUTE")
    proc = cmd.psql(
        cmd.USER_RUNTIME,
        cmd.ingest_sql(
            command_id=command_a,
            submission_id=str(uuid.uuid4()),
            tenant=tenant_a,
            origin=origin,
            idem=f"idem-p4-a-changed-{run_id}",
            request_sha=cmd.sha256_text("p4-request-a"),
            source_class=source_class,
            locator=f"synthetic://kdb/p4/tenant-a-changed-{run_id}",
            content_sha=cmd.sha256_text("p4-changed-payload"),
            rights_json=rights_json,
            rights_sha=cmd.sha256_text(rights_json),
            principal=principal,
            access=access,
            purpose=purpose,
            correlation_id=str(uuid.uuid4()),
        ),
    )
    if proc.returncode == 0:
        note("REQUEST_HASH_NOT_BOUND_TO_PAYLOAD", "RED", blob_of(proc))
    else:
        require_denied(
            blob_of(proc),
            "permission denied for function ingest_source",
            code="REQUEST_HASH_PAYLOAD_BINDING",
        )

    print("P4_TEMP_GRANT_O1_O2_O3")
    try:
        set_runtime_execute(True)
        locator = f"synthetic://kdb/p4/digest-{run_id}"
        idem = f"idem-p4-digest-{run_id}"
        rights_pg = cmd.must(
            superuser,
            f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(rights_json)}::jsonb);",
        )
        digest = cmd.must(
            superuser,
            o1_digest_sql(
                command_a,
                tenant_a,
                origin,
                purpose,
                source_class,
                locator,
                content_a,
                rights_pg,
                principal,
                access,
                idem,
                submission_a,
            ),
        )
        proc = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.ingest_sql(
                command_id=command_a,
                submission_id=submission_a,
                tenant=tenant_a,
                origin=origin,
                idem=idem,
                request_sha=digest,
                source_class=source_class,
                locator=locator,
                content_sha=content_a,
                rights_json=rights_json,
                rights_sha=rights_pg,
                principal=principal,
                access=access,
                purpose=purpose,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        if proc.returncode == 0:
            note("POSITIVE_INGEST_WITHOUT_TRUST", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_SECURITY_CONTEXT_NOT_CONFIGURED",
                code="POSITIVE_INGEST_FAIL_CLOSED",
            )

        other_rights = json.loads(rights_json)
        other_rights["rights_basis"] = "synthetic-other-license"
        other_raw = json.dumps(other_rights, separators=(",", ":"), sort_keys=True)
        proc = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.ingest_sql(
                command_id=command_a,
                submission_id=submission_a,
                tenant=tenant_a,
                origin=origin,
                idem=idem,
                request_sha=digest,
                source_class=source_class,
                locator=locator,
                content_sha=cmd.sha256_text("p4-changed-under-same-hash"),
                rights_json=other_raw,
                rights_sha=rights_pg,
                principal=principal,
                access=access,
                purpose=purpose,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        if proc.returncode == 0:
            note("REQUEST_HASH_NOT_BOUND_TO_PAYLOAD", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_HASH_MISMATCH",
                "KDB_IDEMPOTENCY_CONFLICT",
                code="REQUEST_HASH_SERVER_DIGEST",
            )

        cand_id = str(uuid.uuid4())
        source_version_id = str(uuid.uuid4())
        propose_cmd = str(uuid.uuid4())
        spans_a = '[{"span":"a"}]'
        spans_b = '[{"span":"b"}]'
        payload = '{"k":"v"}'
        payload_digest = cmd.must(
            superuser, f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(payload)}::jsonb);"
        )
        spans_a_digest = cmd.must(
            superuser, f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(spans_a)}::jsonb);"
        )
        o2_digest = cmd.must(
            superuser,
            "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array("
            f"'v2','CANDIDATE_PROPOSAL','{propose_cmd}'::uuid,{cmd.psql_str(tenant_a)},"
            f"'{submission_a}'::uuid,'{source_version_id}'::uuid,'{cand_id}'::uuid,1::bigint,"
            f"{cmd.psql_str(content_a)},{cmd.psql_str(payload_digest)},"
            f"{cmd.psql_str(spans_a_digest)},{cmd.psql_str(principal)},{cmd.psql_str(access)}));",
        )
        propose_changed = cmd.propose_sql(
            command_id=propose_cmd,
            tenant=tenant_a,
            submission_id=submission_a,
            source_version_id=source_version_id,
            candidate_id=cand_id,
            revision_no=1,
            request_sha=o2_digest,
            content_sha=content_a,
            evidence_spans=spans_b,
            payload=payload,
            actor=principal,
            access=access,
            correlation_id=str(uuid.uuid4()),
        )
        proc = cmd.psql(cmd.USER_RUNTIME, propose_changed)
        if proc.returncode == 0:
            note("O2_EVIDENCE_SPANS_UNBOUND", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_HASH_MISMATCH",
                "KDB_IDEMPOTENCY_CONFLICT",
                code="O2_EVIDENCE_SPANS_DIGEST",
            )
        propose_match = cmd.propose_sql(
            command_id=propose_cmd,
            tenant=tenant_a,
            submission_id=submission_a,
            source_version_id=source_version_id,
            candidate_id=cand_id,
            revision_no=1,
            request_sha=o2_digest,
            content_sha=content_a,
            evidence_spans=spans_a,
            payload=payload,
            actor=principal,
            access=access,
            correlation_id=str(uuid.uuid4()),
        )
        proc = cmd.psql(cmd.USER_RUNTIME, propose_match)
        if proc.returncode == 0:
            note("O2_POSITIVE_WITHOUT_TRUST", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_SECURITY_CONTEXT_NOT_CONFIGURED",
                code="O2_FAIL_CLOSED",
            )

        handoff_cmd = str(uuid.uuid4())
        revision_id = str(uuid.uuid4())
        o3_digest = cmd.must(
            superuser,
            "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array("
            f"'v2','REVIEW_HANDOFF','{handoff_cmd}'::uuid,{cmd.psql_str(tenant_a)},"
            f"'{revision_id}'::uuid,{cmd.psql_str(principal)},{cmd.psql_str(access)}));",
        )
        proc = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.handoff_sql(
                command_id=handoff_cmd,
                tenant=tenant_a,
                candidate_revision_id=revision_id,
                request_sha=o3_digest,
                actor=principal,
                access=access,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        if proc.returncode == 0:
            note("O3_POSITIVE_WITHOUT_TRUST", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_SECURITY_CONTEXT_NOT_CONFIGURED",
                code="O3_FAIL_CLOSED",
            )
        proc = cmd.psql(
            cmd.USER_RUNTIME,
            cmd.handoff_sql(
                command_id=handoff_cmd,
                tenant=tenant_a,
                candidate_revision_id=revision_id,
                request_sha=o3_digest,
                actor="OTHER_ACTOR",
                access=access,
                correlation_id=str(uuid.uuid4()),
            ),
        )
        if proc.returncode == 0:
            note("O3_ACTOR_UNBOUND", "RED", blob_of(proc))
        else:
            require_denied(
                blob_of(proc),
                "KDB_HASH_MISMATCH",
                "KDB_IDEMPOTENCY_CONFLICT",
                code="O3_DIGEST_BINDING",
            )
    finally:
        set_runtime_execute(False)
        leftover = cmd.must(
            superuser,
            f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(INGEST)}, 'EXECUTE');",
        )
        if truthy(leftover):
            note("RUNTIME_EXECUTE_NOT_REVOKED_AFTER_PROBE", "RED", leftover)

    print("P4C_MIGRATOR_FUTURE_FUNCTION")
    cmd.must(
        superuser,
        "SET ROLE kdb_migrator; "
        "CREATE FUNCTION kdb_ops.p4_acl_probe_future() "
        "RETURNS integer LANGUAGE sql SET search_path = pg_catalog AS $$ SELECT 1 $$; "
        "CREATE FUNCTION kdb_ops.p4_acl_probe_secdef() "
        "RETURNS integer LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$ SELECT 1 $$; "
        "RESET ROLE;",
    )
    public_hits = []
    for fn in ("kdb_ops.p4_acl_probe_future()", "kdb_ops.p4_acl_probe_secdef()"):
        for role in UNTRUSTED:
            exe = cmd.must(
                superuser,
                f"SELECT has_function_privilege({cmd.psql_str(role)}, {cmd.psql_str(fn)}, 'EXECUTE');",
            )
            if truthy(exe):
                public_hits.append({"fn": fn, "role": role})
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p4_acl_probe_future();")
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p4_acl_probe_secdef();")
    if public_hits:
        note("FUTURE_FUNCTION_PUBLIC_EXECUTE", "RED", public_hits)
    else:
        note("FUTURE_FUNCTION_PUBLIC_EXECUTE", "CLOSED", "kdb_migrator probes have no untrusted EXECUTE")

    cmd.must(
        superuser,
        "CREATE OR REPLACE FUNCTION kdb_ops.p4_superuser_acl_probe() "
        "RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$;",
    )
    super_public = cmd.must(
        superuser,
        "SELECT has_function_privilege('public', 'kdb_ops.p4_superuser_acl_probe()', 'EXECUTE');",
    )
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p4_superuser_acl_probe();")
    if truthy(super_public):
        note(
            "BLOCK_DEFAULT_ACL_CREATOR",
            "INFO",
            "superuser-created function still PUBLIC EXECUTE; hosted apply stays blocked",
        )
    else:
        note("SUPERUSER_DEFAULT_ACL", "INFO", "superuser probe had no PUBLIC EXECUTE")

    print("P4D_DIRECT_TABLE_AND_PROMOTION")
    denials = [
        ("SELECT count(*) FROM kdb_canonical.protocol;", "permission denied"),
        (
            "INSERT INTO kdb_canonical.protocol(owning_module_ref, taxonomy_version_ref) VALUES('P4','TAX_SYNTH');",
            "permission denied",
        ),
        ("SET ROLE kdb_command_owner;", "permission denied"),
    ]
    for sql, needle in denials:
        proc = cmd.psql(cmd.USER_RUNTIME, sql)
        if proc.returncode == 0:
            note("DIRECT_PRIVILEGE_ACCEPTED", "RED", sql[:80])
        else:
            require_denied(blob_of(proc), needle, code="DIRECT_PRIVILEGE")

    proto = cmd.must(superuser, "SELECT count(*) FROM kdb_canonical.protocol;")
    proto_v = cmd.must(superuser, "SELECT count(*) FROM kdb_canonical.protocol_version;")
    decisions = cmd.must(superuser, "SELECT count(*) FROM kdb_governance.human_review_decision;")
    if proto != "0" or proto_v != "0" or decisions != "0":
        note("PUBLICATION_WRITTEN", "RED", {"protocol": proto, "protocol_version": proto_v, "decisions": decisions})
    else:
        note("NO_O4_O5", "CLOSED", "protocol and human_review_decision empty")

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    out = Path("/tmp/kdb-p4-security-findings.json")
    payload = {
        "hosted_apply": "BLOCKED",
        "piac": "FAIL_CLOSED",
        "independent_reviewer": "INDEPENDENT_REVIEWER_UNASSIGNED",
        "positive_o1_o3": "BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED",
        "findings": FINDINGS,
    }
    raw = json.dumps(payload, indent=2) + "\n"
    out.write_text(raw)
    print("FINDINGS_PATH", out)
    print("FINDINGS_SHA256", hashlib.sha256(raw.encode()).hexdigest())
    print("RED_COUNT", len(red))
    if red:
        print("RED_SECURITY_FINDINGS")
        for row in red:
            print("RED", row["code"])
        raise SystemExit(1)
    print("NEGATIVE_GATE_PASS")
    print("POSITIVE_INGEST_NOT_ADMITTED")
    print("PASS_P4_DIGEST_ORACLE_INTEGRITY")
    print("NOTE_NOT_A_HOSTED_OR_INDEPENDENT_SECURITY_PASS")
    print("NOTE_BLOCK_DEFAULT_ACL_CREATOR_HOSTED_APPLY_BLOCKED")


if __name__ == "__main__":
    main()
