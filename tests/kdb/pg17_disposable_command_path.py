#!/usr/bin/env python3
"""Local O1-O3 command path on disposable PostgreSQL 17.

Positive ingest is BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED.
LOGIN as kdb_ingest_runtime. SET ROLE from superuser is not a positive.
Does not apply 004. Does not connect to Supabase. Does not publish.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg17_disposable_apply as apply  # noqa: E402

CONTAINER = apply.CONTAINER
USER_SUPER = os.environ.get("PGUSER", "kdb_local_super")
USER_RUNTIME = "kdb_ingest_runtime"
DB = os.environ.get("PGDATABASE", "kdb_m01_disposable")
MODE = os.environ.get("KDB_PG17_MODE", "docker")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def psql(user: str, sql: str, extra=None) -> subprocess.CompletedProcess:
    if MODE == "libpq":
        host = os.environ.get("PGHOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost"}:
            raise SystemExit(f"refusing PGHOST={host}")
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            os.environ.get("PGPORT", "5432"),
            "-U",
            user,
            "-d",
            DB,
            "-v",
            "ON_ERROR_STOP=1",
            "-X",
            "-q",
            "-t",
            "-A",
        ]
    else:
        cmd = [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            user,
            "-d",
            DB,
            "-v",
            "ON_ERROR_STOP=1",
            "-X",
            "-q",
            "-t",
            "-A",
        ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, input=sql, text=True, capture_output=True)


def must(user: str, sql: str) -> str:
    proc = psql(user, sql)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"psql {user} failed rc={proc.returncode}")
    return proc.stdout.strip()


def must_fail(user: str, sql: str, *tokens: str) -> None:
    proc = psql(user, sql)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        raise SystemExit(f"expected {tokens}, query succeeded: {blob}")
    if not any(token in blob for token in tokens):
        raise SystemExit(f"expected {tokens} in error, got: {blob}")


def ensure_container() -> None:
    if MODE != "docker":
        apply.guard()
        return
    running = subprocess.check_output(
        ["docker", "ps", "--format", "{{.Names}}"], text=True
    )
    if CONTAINER in running.splitlines():
        apply.guard()
        return
    existing = subprocess.check_output(
        ["docker", "ps", "-a", "--format", "{{.Names}}"], text=True
    )
    if CONTAINER in existing.splitlines():
        subprocess.check_call(["docker", "start", CONTAINER])
    else:
        subprocess.check_call(
            [
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER,
                "-e",
                "POSTGRES_USER=" + USER_SUPER,
                "-e",
                "POSTGRES_DB=" + DB,
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-p",
                "127.0.0.1:55432:5432",
                "postgres:17",
            ]
        )
    for _ in range(30):
        ready = subprocess.run(
            ["docker", "exec", CONTAINER, "pg_isready", "-U", USER_SUPER, "-d", DB],
            capture_output=True,
            text=True,
        )
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("postgres not ready")
    apply.guard()


def ensure_schema() -> None:
    exists = must(
        USER_SUPER,
        "SELECT count(*) FROM pg_namespace WHERE nspname='kdb_ops';",
    )
    if exists != "1":
        print("APPLY_FOR_COMMAND_PATH")
        apply.apply_stack()


def ingest_sql(
    command_id: str,
    submission_id: str,
    tenant: str,
    origin: str,
    idem: str,
    request_sha: str,
    source_class: str,
    locator: str,
    content_sha: str,
    rights_json: str,
    rights_sha: str,
    principal: str,
    access: str,
    purpose: str,
    correlation_id: str,
) -> str:
    return f"""
SELECT kdb_ops.ingest_source(
  '{command_id}'::uuid,
  '{submission_id}'::uuid,
  {psql_str(tenant)},
  {psql_str(origin)},
  {psql_str(idem)},
  {psql_str(request_sha)},
  {psql_str(source_class)},
  {psql_str(locator)},
  {psql_str(content_sha)},
  {psql_str(rights_json)}::jsonb,
  {psql_str(rights_sha)},
  {psql_str(principal)},
  {psql_str(access)},
  {psql_str(purpose)},
  '{correlation_id}'::uuid,
  TIMESTAMPTZ '2026-10-24T00:00:00Z'
);
"""


def psql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    ensure_container()
    ver = must(USER_SUPER, "SHOW server_version;")
    print("server_version", ver)
    if "17." not in ver:
        raise SystemExit("not PostgreSQL 17")
    ensure_schema()

    rights = {
        "rights_status": "ADMITTED",
        "rights_basis": "synthetic-test-license",
        "allowed_purposes": ["kdb_knowledge_intake"],
        "media_type": "application/octet-stream",
    }
    rights_json = json.dumps(rights, separators=(",", ":"), sort_keys=True)
    rights_sha = sha256_text(rights_json)
    content_sha = sha256_text("synthetic-kdb-m01-command-path-v1")
    request_sha = sha256_text("o1-request-v1")
    command_id = str(uuid.uuid4())
    submission_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    run_id = command_id[:8]
    tenant_a = "TENANT_SYNTH_A"

    print("T01_SUPERUSER_DENIED")
    must_fail(
        USER_SUPER,
        ingest_sql(
            command_id,
            submission_id,
            tenant_a,
            "KDB",
            f"idem-cmd-{run_id}",
            request_sha,
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/command-path-{run_id}",
            content_sha,
            rights_json,
            rights_sha,
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            correlation_id,
        ),
        "KDB_PRINCIPAL_DENIED",
    )

    print("T02_RUNTIME_EXECUTE_REVOKED")
    exe = must(
        USER_SUPER,
        "SELECT has_function_privilege('kdb_ingest_runtime',"
        "'kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)',"
        "'EXECUTE');",
    )
    if exe in {"t", "true"}:
        raise SystemExit("runtime still has EXECUTE ingest_source")
    must_fail(
        USER_RUNTIME,
        ingest_sql(
            command_id,
            submission_id,
            tenant_a,
            "KDB",
            f"idem-cmd-{run_id}",
            request_sha,
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/command-path-{run_id}",
            content_sha,
            rights_json,
            rights_sha,
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            correlation_id,
        ),
        "permission denied",
        "denied",
        "KDB_SECURITY_CONTEXT_NOT_CONFIGURED",
    )
    print("BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED")
    print("PASS_PG17_COMMAND_PATH_FAIL_CLOSED")
    print("NOTE_PUBLICATION_NOT_EXECUTED")
    print("NOTE_N8N_RUNTIME_NOT_USED")


if __name__ == "__main__":
    main()
