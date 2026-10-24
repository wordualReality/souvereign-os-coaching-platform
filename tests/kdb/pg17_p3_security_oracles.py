#!/usr/bin/env python3
"""P3 fail-closed security oracles. Nonzero exit if RED-01/02/03 remain.

P2 characterization scripts may still report superuser PUBLIC EXECUTE as
forensic INFO/RED. This gate is the release oracle: it fails the build when
tenant spoof is accepted, a changed replay returns a prior receipt, or a
kdb_migrator-created function has PUBLIC/anon/authenticated/service_role
EXECUTE. Does not apply 004/098/P2 recovery. Does not connect to Supabase.
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
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    payload = json.dumps(detail) if not isinstance(detail, str) else detail
    print(f"{severity} {code} {payload}")


def truthy(value: str) -> bool:
    return value in {"t", "true"}


def ingest_or_fail(**kwargs) -> tuple[bool, str]:
    proc = cmd.psql(cmd.USER_RUNTIME, cmd.ingest_sql(**kwargs))
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def set_runtime_execute(grant: bool) -> None:
    verb = "GRANT" if grant else "REVOKE"
    direction = "TO" if grant else "FROM"
    for fn in (INGEST, PROPOSE, HANDOFF):
        cmd.must(
            cmd.USER_SUPER,
            f"{verb} EXECUTE ON FUNCTION {fn} {direction} kdb_ingest_runtime;",
        )


def rights_blob() -> tuple[str, str]:
    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    raw = json.dumps(rights, separators=(",", ":"), sort_keys=True)
    return raw, cmd.sha256_text(raw)


def main() -> None:
    assert_piac_fail_closed()
    cmd.ensure_container()
    cmd.ensure_schema()
    superuser = cmd.USER_SUPER

    ready = cmd.must(superuser, "SELECT kdb_ops.security_context_ready();")
    if truthy(ready):
        note("SECURITY_CONTEXT_READY_TRUE", "RED", ready)
    else:
        note("SECURITY_CONTEXT_NOT_CONFIGURED", "CLOSED", ready)

    print("P3A_RUNTIME_EXECUTE_REVOKED")
    for fn in (INGEST, PROPOSE, HANDOFF):
        exe = cmd.must(
            superuser,
            f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(fn)}, 'EXECUTE');",
        )
        if truthy(exe):
            note("RUNTIME_EXECUTE_STILL_GRANTED", "RED", fn)
        else:
            note("RUNTIME_EXECUTE_REVOKED", "CLOSED", fn)

    rights_json, rights_sha = rights_blob()
    command_a = str(uuid.uuid4())
    submission_a = str(uuid.uuid4())
    run_id = command_a[:8]
    tenant_a = "TENANT_SYNTH_A"
    tenant_b = "TENANT_SYNTH_B"
    content_a = cmd.sha256_text("p3-tenant-a-body")
    request_a = cmd.sha256_text("p3-request-a")

    print("P3A_FOREIGN_TENANT_WITHOUT_EXECUTE")
    ok_b, body_b = ingest_or_fail(
        command_id=str(uuid.uuid4()),
        submission_id=str(uuid.uuid4()),
        tenant=tenant_b,
        origin="KDB",
        idem=f"idem-p3-b-{run_id}",
        request_sha=cmd.sha256_text("p3-request-b"),
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p3/tenant-b-{run_id}",
        content_sha=cmd.sha256_text("p3-tenant-b-body"),
        rights_json=rights_json,
        rights_sha=rights_sha,
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    )
    recorded = ok_b and '"status":"RECORDED"' in body_b.replace(" ", "")
    if recorded:
        note("TENANT_GUC_SPOOF_ACCEPTED_AT_DB", "RED", body_b)
    else:
        note("TENANT_GUC_SPOOF", "CLOSED", body_b[:300])

    print("P3B_CHANGED_PAYLOAD_WITHOUT_EXECUTE")
    ok_h, body_h = ingest_or_fail(
        command_id=command_a,
        submission_id=str(uuid.uuid4()),
        tenant=tenant_a,
        origin="KDB",
        idem=f"idem-p3-a-changed-{run_id}",
        request_sha=request_a,
        source_class="LICENSED_DOCUMENT",
        locator=f"synthetic://kdb/p3/tenant-a-changed-{run_id}",
        content_sha=cmd.sha256_text("p3-changed-payload"),
        rights_json=rights_json,
        rights_sha=rights_sha,
        principal="PRINCIPAL_REF_SYNTH_PIPELINE",
        access="ACCESS_SYNTH_OK",
        purpose="kdb_knowledge_intake",
        correlation_id=str(uuid.uuid4()),
    )
    if ok_h:
        note("REQUEST_HASH_NOT_BOUND_TO_PAYLOAD", "RED", body_h)
    else:
        note("REQUEST_HASH_PAYLOAD_BINDING", "CLOSED", body_h[:300])

    print("P3_TEMP_GRANT_PROVES_FAIL_CLOSED_BODY")
    try:
        set_runtime_execute(True)
        locator = f"synthetic://kdb/p3/digest-{run_id}"
        idem = f"idem-p3-digest-{run_id}"
        principal = "PRINCIPAL_REF_SYNTH_PIPELINE"
        access = "ACCESS_SYNTH_OK"
        purpose = "kdb_knowledge_intake"
        origin = "KDB"
        source_class = "LICENSED_DOCUMENT"
        rights_pg = cmd.must(
            superuser,
            f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(rights_json)}::jsonb);",
        )
        digest = cmd.must(
            superuser,
            "SELECT kdb_ops.canonical_command_digest("
            f"'SOURCE_INTAKE', '{command_a}'::uuid, {cmd.psql_str(tenant_a)}, "
            f"{cmd.psql_str(origin)}, {cmd.psql_str(purpose)}, {cmd.psql_str(source_class)}, "
            f"{cmd.psql_str(locator)}, {cmd.psql_str(content_a)}, {cmd.psql_str(rights_pg)}, "
            f"{cmd.psql_str(principal)}, {cmd.psql_str(access)}, {cmd.psql_str(idem)}, "
            f"'{submission_a}'::uuid);",
        )

        ok_match, body_match = ingest_or_fail(
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
        )
        if ok_match:
            note("POSITIVE_INGEST_WITHOUT_TRUST", "RED", body_match)
        elif "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in body_match:
            note("POSITIVE_INGEST_FAIL_CLOSED", "CLOSED", "KDB_SECURITY_CONTEXT_NOT_CONFIGURED")
        else:
            note("POSITIVE_INGEST_UNEXPECTED_DENIAL", "RED", body_match[:400])

        ok_spoof, body_spoof = ingest_or_fail(
            command_id=str(uuid.uuid4()),
            submission_id=str(uuid.uuid4()),
            tenant=tenant_b,
            origin=origin,
            idem=f"idem-p3-spoof-{run_id}",
            request_sha=digest,
            source_class=source_class,
            locator=f"synthetic://kdb/p3/spoof-{run_id}",
            content_sha=content_a,
            rights_json=rights_json,
            rights_sha=rights_pg,
            principal=principal,
            access=access,
            purpose=purpose,
            correlation_id=str(uuid.uuid4()),
        )
        if ok_spoof:
            note("TENANT_GUC_SPOOF_ACCEPTED_AT_DB", "RED", body_spoof)
        else:
            note("TENANT_SPOOF_WITH_EXECUTE_STILL_DENIED", "CLOSED", body_spoof[:300])

        other_rights = json.loads(rights_json)
        other_rights["rights_basis"] = "synthetic-other-license"
        other_raw = json.dumps(other_rights, separators=(",", ":"), sort_keys=True)
        ok_replay, body_replay = ingest_or_fail(
            command_id=command_a,
            submission_id=submission_a,
            tenant=tenant_a,
            origin=origin,
            idem=idem,
            request_sha=digest,
            source_class=source_class,
            locator=locator,
            content_sha=cmd.sha256_text("p3-changed-under-same-hash"),
            rights_json=other_raw,
            rights_sha=rights_pg,
            principal=principal,
            access=access,
            purpose=purpose,
            correlation_id=str(uuid.uuid4()),
        )
        if ok_replay:
            note("REQUEST_HASH_NOT_BOUND_TO_PAYLOAD", "RED", body_replay)
        elif "KDB_HASH_MISMATCH" in body_replay or "KDB_IDEMPOTENCY_CONFLICT" in body_replay:
            note("REQUEST_HASH_SERVER_DIGEST", "CLOSED", body_replay[:300])
        else:
            note("REQUEST_HASH_UNEXPECTED", "RED", body_replay[:400])

        prior_id = str(uuid.uuid4())
        stored_hash = "a" * 64
        cmd.must(
            superuser,
            "INSERT INTO kdb_ops.command_receipt("
            "command_id, tenant_scope, command_kind, request_sha256, outcome) VALUES ("
            f"'{prior_id}'::uuid, {cmd.psql_str(tenant_a)}, 'SOURCE_INTAKE', "
            f"'{stored_hash}', '{{\"status\":\"RECORDED\"}}'::jsonb);",
        )
        prior_sub = str(uuid.uuid4())
        prior_locator = f"synthetic://kdb/p3/prior-{run_id}"
        prior_idem = f"idem-p3-prior-{run_id}"
        prior_digest = cmd.must(
            superuser,
            "SELECT kdb_ops.canonical_command_digest("
            f"'SOURCE_INTAKE', '{prior_id}'::uuid, {cmd.psql_str(tenant_a)}, "
            f"{cmd.psql_str(origin)}, {cmd.psql_str(purpose)}, {cmd.psql_str(source_class)}, "
            f"{cmd.psql_str(prior_locator)}, {cmd.psql_str(content_a)}, {cmd.psql_str(rights_pg)}, "
            f"{cmd.psql_str(principal)}, {cmd.psql_str(access)}, {cmd.psql_str(prior_idem)}, "
            f"'{prior_sub}'::uuid);",
        )
        ok_conflict, body_conflict = ingest_or_fail(
            command_id=prior_id,
            submission_id=prior_sub,
            tenant=tenant_a,
            origin=origin,
            idem=prior_idem,
            request_sha=prior_digest,
            source_class=source_class,
            locator=prior_locator,
            content_sha=content_a,
            rights_json=rights_json,
            rights_sha=rights_pg,
            principal=principal,
            access=access,
            purpose=purpose,
            correlation_id=str(uuid.uuid4()),
        )
        if ok_conflict:
            note("IDEMPOTENCY_RETURNED_PRIOR_RECEIPT", "RED", body_conflict)
        elif "KDB_IDEMPOTENCY_CONFLICT" in body_conflict:
            note("IDEMPOTENCY_CONFLICT_BEFORE_RECEIPT", "CLOSED", "KDB_IDEMPOTENCY_CONFLICT")
        else:
            note("IDEMPOTENCY_UNEXPECTED", "RED", body_conflict[:400])
    finally:
        set_runtime_execute(False)
        leftover = cmd.must(
            superuser,
            f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(INGEST)}, 'EXECUTE');",
        )
        if truthy(leftover):
            note("RUNTIME_EXECUTE_NOT_REVOKED_AFTER_PROBE", "RED", leftover)

    print("P3C_MIGRATOR_FUTURE_FUNCTION")
    cmd.must(
        superuser,
        "SET ROLE kdb_migrator; "
        "CREATE FUNCTION kdb_ops.p3_acl_probe_future() "
        "RETURNS integer LANGUAGE sql SET search_path = pg_catalog AS $$ SELECT 1 $$; "
        "RESET ROLE;",
    )
    public_hits = []
    for role in UNTRUSTED:
        exe = cmd.must(
            superuser,
            f"SELECT has_function_privilege({cmd.psql_str(role)}, "
            "'kdb_ops.p3_acl_probe_future()', 'EXECUTE');",
        )
        if truthy(exe):
            public_hits.append(role)
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p3_acl_probe_future();")
    if public_hits:
        note(
            "FUTURE_FUNCTION_PUBLIC_EXECUTE",
            "RED",
            {"creator": "kdb_migrator", "roles": public_hits},
        )
    else:
        note("FUTURE_FUNCTION_PUBLIC_EXECUTE", "CLOSED", "kdb_migrator probe has no untrusted EXECUTE")

    cmd.must(
        superuser,
        "CREATE OR REPLACE FUNCTION kdb_ops.p3_superuser_acl_probe() "
        "RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$;",
    )
    super_public = cmd.must(
        superuser,
        "SELECT has_function_privilege('public', 'kdb_ops.p3_superuser_acl_probe()', 'EXECUTE');",
    )
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p3_superuser_acl_probe();")
    if truthy(super_public):
        note(
            "BLOCK_DEFAULT_ACL_CREATOR",
            "INFO",
            "superuser-created function still PUBLIC EXECUTE; hosted apply stays blocked",
        )
    else:
        note("SUPERUSER_DEFAULT_ACL", "INFO", "superuser probe had no PUBLIC EXECUTE")

    print("P3D_DIRECT_TABLE_AND_PROMOTION")
    denials = [
        "SELECT count(*) FROM kdb_canonical.protocol;",
        "INSERT INTO kdb_canonical.protocol(owning_module_ref, taxonomy_version_ref) VALUES('P3','TAX_SYNTH');",
        (
            "INSERT INTO kdb_governance.human_review_decision("
            "candidate_revision_id, candidate_content_sha256, reviewer_principal_ref, "
            "access_decision_ref, decision, source_rights_digest, review_evidence_sha256, "
            "signed_decision_ref, decided_at) VALUES ("
            f"'{uuid.uuid4()}', repeat('a',64), 'P3', 'P3', 'APPROVED_FOR_PROMOTION', "
            "repeat('a',64), repeat('a',64), 'P3', now());"
        ),
        "SET ROLE kdb_command_owner;",
        "SET ROLE kdb_schema_owner;",
    ]
    for sql in denials:
        proc = cmd.psql(cmd.USER_RUNTIME, sql)
        if proc.returncode == 0:
            note("DIRECT_PRIVILEGE_ACCEPTED", "RED", sql[:80])
        else:
            note("DIRECT_PRIVILEGE", "CLOSED", sql[:80])

    proto = cmd.must(superuser, "SELECT count(*) FROM kdb_canonical.protocol;")
    proto_v = cmd.must(superuser, "SELECT count(*) FROM kdb_canonical.protocol_version;")
    decisions = cmd.must(superuser, "SELECT count(*) FROM kdb_governance.human_review_decision;")
    if proto != "0" or proto_v != "0" or decisions != "0":
        note("PUBLICATION_WRITTEN", "RED", {"protocol": proto, "protocol_version": proto_v, "decisions": decisions})
    else:
        note("NO_O4_O5", "CLOSED", "protocol and human_review_decision empty")

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    out = Path("/tmp/kdb-p3-security-findings.json")
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
    print("PASS_P3_FAIL_CLOSED_SECURITY_ORACLES")
    print("NOTE_NOT_A_HOSTED_OR_INDEPENDENT_SECURITY_PASS")
    print("NOTE_BLOCK_DEFAULT_ACL_CREATOR_HOSTED_APPLY_BLOCKED")


if __name__ == "__main__":
    main()
