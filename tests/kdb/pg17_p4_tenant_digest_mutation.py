#!/usr/bin/env python3
"""Kill a tenant-digest mutant on disposable PostgreSQL 17.

Applies a test-only CREATE OR REPLACE that corrupts O1 tenant binding.
The shipped P4 migration is not modified. Hosted apply stays blocked.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
import pg17_disposable_command_path as cmd  # noqa: E402
from digest_v2 import o1_fields, sql_jsonb_build_array  # noqa: E402
from p4_oracle_classifier import (  # noqa: E402
    classify_runtime_execute,
    classify_tenant_digest_probe,
    classify_trust_fail_closed,
)
from piac_fail_closed_probe import assert_piac_fail_closed  # noqa: E402

INGEST = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,"
    "text,text,text,text,uuid,timestamptz)"
)
REPO = Path(__file__).resolve().parents[2]
P4_SQL = (
    REPO
    / "database"
    / "migrations"
    / "kdb"
    / "20261024220000__kdb_m01_p4__digest_oracle_integrity.sql"
)
DIGEST_NEEDLE = "p_command_id, p_tenant_scope, p_origin_owner"
DIGEST_MUTANT = "p_command_id, 'TENANT_SYNTH_A'::text, p_origin_owner"
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    payload = json.dumps(detail) if not isinstance(detail, str) else detail
    print(f"{severity} {code} {payload}")


def extract_ingest_source(sql: str) -> str:
    start = sql.index("CREATE OR REPLACE FUNCTION kdb_ops.ingest_source(")
    end = sql.index("CREATE OR REPLACE FUNCTION kdb_ops.propose_candidate(")
    return sql[start:end].strip() + "\n"


def function_md5() -> str:
    return cmd.must(
        cmd.USER_SUPER,
        f"SELECT md5(pg_get_functiondef({cmd.psql_str(INGEST)}::regprocedure));",
    )


def apply_ingest_sql(body: str) -> None:
    wrapper = "SET ROLE kdb_command_owner;\n" + body + "\nRESET ROLE;\n"
    cmd.must(cmd.USER_SUPER, wrapper)


def set_runtime_execute(grant: bool) -> None:
    verb = "GRANT" if grant else "REVOKE"
    direction = "TO" if grant else "FROM"
    cmd.must(
        cmd.USER_SUPER,
        f"{verb} EXECUTE ON FUNCTION {INGEST} {direction} kdb_ingest_runtime;",
    )


def execute_granted() -> bool:
    value = cmd.must(
        cmd.USER_SUPER,
        f"SELECT has_function_privilege('kdb_ingest_runtime', {cmd.psql_str(INGEST)}, 'EXECUTE');",
    )
    return value in {"t", "true"}


def probe_ingest(*, tenant: str, request_sha: str, **extra) -> subprocess.CompletedProcess:
    return cmd.psql(
        cmd.USER_RUNTIME,
        cmd.ingest_sql(
            tenant=tenant,
            request_sha=request_sha,
            **extra,
        ),
    )


def blob_of(proc: subprocess.CompletedProcess) -> str:
    return (proc.stdout + proc.stderr).strip()


def report_claim(claim: str, psql_rc: int, oracle_code: str, oracle_sev: str, body: str) -> None:
    print(f"CLAIM {claim}")
    print(f"PSQL_RC {psql_rc}")
    print(f"ORACLE_CODE {oracle_code}")
    print(f"ORACLE_SEVERITY {oracle_sev}")
    note(oracle_code, oracle_sev, {"claim": claim, "psql_rc": psql_rc, "body": body[:400]})


def broken_connection() -> subprocess.CompletedProcess:
    argv = [
        "psql",
        "-h",
        "127.0.0.1",
        "-p",
        "1",
        "-U",
        "kdb_local_super",
        "-d",
        "kdb_m01_disposable",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        "SELECT 1;",
    ]
    if cmd.MODE == "docker":
        argv = ["docker", "exec", "-i", cmd.CONTAINER, *argv]
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=8,
            env={**os.environ, "PGCONNECT_TIMEOUT": "2"},
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(
            args=argv,
            returncode=127,
            stdout="",
            stderr=f"No such file or directory: {exc.filename}",
        )


def fixture_payload() -> dict:
    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    rights_json = json.dumps(rights, separators=(",", ":"), sort_keys=True)
    return {
        "command_id": str(uuid.uuid4()),
        "submission_id": str(uuid.uuid4()),
        "origin": "KDB",
        "purpose": "kdb_knowledge_intake",
        "source_class": "LICENSED_DOCUMENT",
        "locator": "synthetic://kdb/p4/mutation-tenant",
        "content_sha": cmd.sha256_text("p4-mutation-body"),
        "principal": "PRINCIPAL_REF_SYNTH_MUTATION",
        "access": "ACCESS_SYNTH_OK",
        "idem": "idem-p4-tenant-mutation",
        "rights_json": rights_json,
        "tenant_a": "TENANT_SYNTH_A",
        "tenant_b": "TENANT_SYNTH_B",
    }


def digest_for(payload: dict, tenant: str, rights_pg: str) -> str:
    fields = o1_fields(
        payload["command_id"],
        tenant,
        payload["origin"],
        payload["purpose"],
        payload["source_class"],
        payload["locator"],
        payload["content_sha"],
        rights_pg,
        payload["principal"],
        payload["access"],
        payload["idem"],
        payload["submission_id"],
    )
    return cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.canonical_digest_v2({sql_jsonb_build_array(fields)});",
    )


def call_kwargs(payload: dict, *, tenant: str, request_sha: str, rights_pg: str) -> dict:
    # Keep every digest field identical except tenant. Otherwise HASH_MISMATCH
    # is overdetermined and a tenant-only mutant can still look closed.
    return {
        "command_id": payload["command_id"],
        "submission_id": payload["submission_id"],
        "tenant": tenant,
        "origin": payload["origin"],
        "idem": payload["idem"],
        "request_sha": request_sha,
        "source_class": payload["source_class"],
        "locator": payload["locator"],
        "content_sha": payload["content_sha"],
        "rights_json": payload["rights_json"],
        "rights_sha": rights_pg,
        "principal": payload["principal"],
        "access": payload["access"],
        "purpose": payload["purpose"],
        "correlation_id": str(uuid.uuid4()),
    }


def main() -> None:
    assert_piac_fail_closed()
    cmd.ensure_container()
    cmd.ensure_schema()
    superuser = cmd.USER_SUPER
    ver = cmd.must(superuser, "SHOW server_version;")
    print("PG17_VERSION", ver)
    if "17." not in ver:
        note("WRONG_POSTGRES_VERSION", "RED", ver)
        raise SystemExit(1)

    clean_sql = extract_ingest_source(P4_SQL.read_text())
    if DIGEST_NEEDLE not in clean_sql:
        note("MUTANT_SETUP_FAILED", "RED", "tenant digest needle missing in shipped SQL")
        raise SystemExit(1)
    mutant_sql = clean_sql.replace(DIGEST_NEEDLE, DIGEST_MUTANT, 1)
    if mutant_sql == clean_sql or DIGEST_NEEDLE in mutant_sql.split("jsonb_build_array", 1)[-1][:200]:
        note("MUTANT_SETUP_FAILED", "RED", "tenant field was not corrupted")
        raise SystemExit(1)
    before_hash = hashlib.sha256(clean_sql.encode()).hexdigest()
    after_hash = hashlib.sha256(mutant_sql.encode()).hexdigest()
    if before_hash == after_hash:
        note("MUTANT_SETUP_FAILED", "RED", "file hashes identical")
        raise SystemExit(1)
    print("MUTANT_SHA256_BEFORE", before_hash)
    print("MUTANT_SHA256_AFTER", after_hash)
    diff = "".join(
        difflib.unified_diff(
            clean_sql.splitlines(True),
            mutant_sql.splitlines(True),
            fromfile="ingest_source.clean.sql",
            tofile="ingest_source.mutant.sql",
            n=2,
        )
    )
    print("MUTANT_DIFF")
    print(diff)
    with tempfile.TemporaryDirectory(prefix="kdb-p4-o1-mutant-") as tmp:
        Path(tmp, "mutant.sql").write_text(mutant_sql)
        print("MUTANT_SCRATCH_NOT_SHIPPED", tmp)

    print("UNEXPECTED_FAILURE_SENSITIVITY")
    missing = cmd.psql(superuser, "SELECT kdb_ops.no_such_ingest_source();")
    syntax = cmd.psql(superuser, "SELECT * FROM;")
    unrelated = cmd.psql(superuser, "SELECT 1/0;")
    conn = broken_connection()
    fixtures = [
        ("MISSING_FUNCTION", missing),
        ("SQL_SYNTAX", syntax),
        ("UNRELATED_SQL", unrelated),
        ("BROKEN_CONNECTION", conn),
    ]
    for label, proc in fixtures:
        code, sev = classify_tenant_digest_probe(psql_rc=proc.returncode, body=blob_of(proc))
        print(f"CLAIM {label}")
        print(f"PSQL_RC {proc.returncode}")
        print(f"ORACLE_CODE {code}")
        print(f"ORACLE_SEVERITY {sev}")
        if proc.returncode == 0 or sev == "CLOSED":
            note("UNEXPECTED_CLASSIFIED_CLOSED", "RED", {"label": label, "code": code, "body": blob_of(proc)[:400]})
        else:
            note("UNEXPECTED_FAILURE_IS_RED", "CLOSED", {"label": label, "code": code, "psql_rc": proc.returncode})

    payload = fixture_payload()
    rights_pg = cmd.must(
        superuser,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(payload['rights_json'])}::jsonb);",
    )
    digest_a = digest_for(payload, payload["tenant_a"], rights_pg)

    print("RUNTIME_EXECUTE_DENIED")
    if execute_granted():
        set_runtime_execute(False)
    denied = probe_ingest(
        **call_kwargs(
            payload,
            tenant=payload["tenant_b"],
            request_sha=digest_a,
            rights_pg=rights_pg,
        )
    )
    code, sev = classify_runtime_execute(psql_rc=denied.returncode, body=blob_of(denied))
    report_claim("RUNTIME_EXECUTE_DENIED", denied.returncode, code, sev, blob_of(denied))

    clean_md5 = function_md5()
    print("CLEAN_FUNCTION_MD5", clean_md5)
    mutated = False
    try:
        set_runtime_execute(True)
        print("TRUST_FAIL_CLOSED")
        trust = probe_ingest(
            **call_kwargs(
                payload,
                tenant=payload["tenant_a"],
                request_sha=digest_a,
                rights_pg=rights_pg,
            )
        )
        code, sev = classify_trust_fail_closed(psql_rc=trust.returncode, body=blob_of(trust))
        report_claim("TRUST_FAIL_CLOSED", trust.returncode, code, sev, blob_of(trust))

        print("DIGEST_TENANT_BINDING_CLEAN")
        clean_probe = probe_ingest(
            **call_kwargs(
                payload,
                tenant=payload["tenant_b"],
                request_sha=digest_a,
                rights_pg=rights_pg,
            )
        )
        code, sev = classify_tenant_digest_probe(
            psql_rc=clean_probe.returncode, body=blob_of(clean_probe)
        )
        report_claim(
            "DIGEST_TENANT_BINDING_VERIFIED",
            clean_probe.returncode,
            code,
            sev,
            blob_of(clean_probe),
        )
        if sev != "CLOSED" or code != "DIGEST_TENANT_BINDING_VERIFIED":
            note("CLEAN_TENANT_BINDING_NOT_HASH_MISMATCH", "RED", blob_of(clean_probe)[:400])
        else:
            print("CLEAN_TENANT_DIGEST_EXIT_CONTRACT HASH_MISMATCH")

        print("APPLY_TEST_ONLY_O1_MUTANT")
        apply_ingest_sql(mutant_sql)
        mutated = True
        mutant_md5 = function_md5()
        print("MUTANT_FUNCTION_MD5", mutant_md5)
        if mutant_md5 == clean_md5:
            note("MUTANT_FUNCTION_UNCHANGED", "RED", mutant_md5)
            raise SystemExit(1)
        print("MUTANT_FUNCTION_EXPRESSION_CHANGED")

        mutant_probe = probe_ingest(
            **call_kwargs(
                payload,
                tenant=payload["tenant_b"],
                request_sha=digest_a,
                rights_pg=rights_pg,
            )
        )
        code, sev = classify_tenant_digest_probe(
            psql_rc=mutant_probe.returncode, body=blob_of(mutant_probe)
        )
        report_claim(
            "DIGEST_TENANT_BINDING_MUTANT",
            mutant_probe.returncode,
            code,
            sev,
            blob_of(mutant_probe),
        )
        if sev == "CLOSED":
            note("MUTATION_SURVIVED", "RED", "defective tenant digest still classified CLOSED")
        elif code != "DIGEST_TENANT_BINDING_BROKEN":
            note("MUTATION_UNEXPECTED", "RED", {"code": code, "body": blob_of(mutant_probe)[:400]})
        else:
            note(
                "MUTATION_KILLED",
                "CLOSED",
                "defective tenant digest made the security check fail",
            )
            print("MUTANT_TENANT_DIGEST_NONZERO_CONTRACT DIGEST_TENANT_BINDING_BROKEN")
    finally:
        try:
            apply_ingest_sql(clean_sql)
        except Exception as exc:  # noqa: BLE001
            note("MUTANT_RESTORE_FAILED", "RED", str(exc))
        restored = function_md5()
        print("RESTORED_FUNCTION_MD5", restored)
        if restored != clean_md5:
            note("MUTANT_NOT_RESTORED", "RED", {"expected": clean_md5, "got": restored})
        set_runtime_execute(False)
        if execute_granted():
            note("RUNTIME_EXECUTE_NOT_REVOKED_AFTER_PROBE", "RED", "EXECUTE still granted")
        else:
            note("RUNTIME_EXECUTE_REVOKED_AFTER_PROBE", "CLOSED", "EXECUTE revoked")
        mutated = False
        _ = mutated

    leftover = [
        row
        for row in FINDINGS
        if row["severity"] == "RED" and row["code"] != "DIGEST_TENANT_BINDING_BROKEN"
    ]
    kill = [
        row
        for row in FINDINGS
        if row["code"] == "MUTATION_KILLED" and row["severity"] == "CLOSED"
    ]
    broken = [
        row
        for row in FINDINGS
        if row["code"] == "DIGEST_TENANT_BINDING_BROKEN" and row["severity"] == "RED"
    ]
    print("RED_COUNT", len(leftover))
    print("MUTATION_KILL_COUNT", len(kill))
    print("MUTANT_PROBE_BROKEN_COUNT", len(broken))
    if leftover or not kill or not broken:
        print("RED_SECURITY_FINDINGS")
        for row in leftover:
            print("RED", row["code"])
        if not kill:
            print("RED MUTATION_NOT_KILLED")
        raise SystemExit(1)
    print("NEGATIVE_GATE_PASS")
    print("POSITIVE_INGEST_NOT_ADMITTED")
    print("PASS_P4_TENANT_DIGEST_MUTATION")
    print("HOSTED_APPLY_BLOCKED")
    print("NOTE_NOT_A_HOSTED_OR_INDEPENDENT_SECURITY_PASS")


if __name__ == "__main__":
    main()
