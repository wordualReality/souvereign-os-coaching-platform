#!/usr/bin/env python3
"""Local O1-O3 command path on disposable PostgreSQL 17.

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
    request_sha_conflict = sha256_text("o1-request-v1-conflict")

    command_id = str(uuid.uuid4())
    submission_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    run_id = command_id[:8]
    tenant_a = "TENANT_SYNTH_A"
    tenant_b = "TENANT_SYNTH_B"

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

    print("T02_INGEST")
    first = must(
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
    )
    first_obj = json.loads(first)
    if first_obj.get("status") != "RECORDED":
        raise SystemExit(f"unexpected ingest outcome {first}")
    source_version_id = first_obj["source_version_id"]

    print("T03_REPLAY_SAME_BODY")
    replay = must(
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
    )
    if json.loads(replay) != first_obj:
        raise SystemExit("replay did not return existing receipt")
    receipt_count = must(
        USER_SUPER,
        f"SELECT count(*) FROM kdb_ops.command_receipt WHERE command_id='{command_id}'::uuid;",
    )
    if receipt_count != "1":
        raise SystemExit(f"replay created extra receipt: {receipt_count}")

    print("T04_IDEMPOTENCY_CONFLICT")
    must_fail(
        USER_RUNTIME,
        ingest_sql(
            command_id,
            str(uuid.uuid4()),
            tenant_a,
            "KDB",
            f"idem-cmd-{run_id}-conflict",
            request_sha_conflict,
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/command-path-{run_id}",
            content_sha,
            rights_json,
            rights_sha,
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            str(uuid.uuid4()),
        ),
        "KDB_IDEMPOTENCY_CONFLICT",
    )

    print("T05_CONTEXT_REQUIRED")
    must_fail(
        USER_RUNTIME,
        ingest_sql(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            "",
            "KDB",
            f"idem-cmd-{run_id}-empty",
            sha256_text("o1-empty-tenant"),
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/empty-tenant-{run_id}",
            content_sha,
            rights_json,
            rights_sha,
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            str(uuid.uuid4()),
        ),
        "KDB_CONTEXT_REQUIRED",
    )

    print("T06_RIGHTS_NOT_ADMITTED")
    blocked = dict(rights)
    blocked["rights_status"] = "PENDING"
    blocked_json = json.dumps(blocked, separators=(",", ":"), sort_keys=True)
    must_fail(
        USER_RUNTIME,
        ingest_sql(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            tenant_a,
            "KDB",
            f"idem-cmd-{run_id}-pending",
            sha256_text("o1-pending-rights"),
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/pending-rights-{run_id}",
            content_sha,
            blocked_json,
            sha256_text(blocked_json),
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            str(uuid.uuid4()),
        ),
        "KDB_RIGHTS_NOT_ADMITTED",
    )

    print("T07_CROSS_TENANT_COMMAND_ID")
    must_fail(
        USER_RUNTIME,
        ingest_sql(
            command_id,
            str(uuid.uuid4()),
            tenant_b,
            "KDB",
            f"idem-cmd-{run_id}-cross",
            sha256_text("o1-tenant-b"),
            "LICENSED_DOCUMENT",
            f"synthetic://kdb/m01/tenant-b-{run_id}",
            content_sha,
            rights_json,
            rights_sha,
            "PRINCIPAL_REF_SYNTH_PIPELINE",
            "ACCESS_SYNTH_OK",
            "kdb_knowledge_intake",
            str(uuid.uuid4()),
        ),
        "KDB_COMMAND_RECEIPT_CONFLICT",
        "command_receipt_command_id_key",
        "duplicate key",
    )

    print("T08_PROPOSE_CANDIDATE")
    candidate_command = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    candidate_sha = sha256_text("candidate-v1")
    propose_sql = f"""
SELECT kdb_ops.propose_candidate(
  '{candidate_command}'::uuid,
  {psql_str(tenant_a)},
  '{submission_id}'::uuid,
  '{source_version_id}'::uuid,
  '{candidate_id}'::uuid,
  1,
  {psql_str(sha256_text("o2-request-v1"))},
  {psql_str(candidate_sha)},
  '[{{"start":0,"end":1}}]'::jsonb,
  '{{"synthetic":true}}'::jsonb,
  'PRINCIPAL_REF_SYNTH_PIPELINE',
  'ACCESS_SYNTH_OK',
  '{uuid.uuid4()}'::uuid
);
"""
    proposed = json.loads(must(USER_RUNTIME, propose_sql))
    if proposed.get("status") != "STRUCTURE_VALIDATED_NOT_REVIEWED":
        raise SystemExit(f"unexpected propose outcome {proposed}")
    candidate_revision_id = proposed["candidate_revision_id"]
    proposed_again = json.loads(must(USER_RUNTIME, propose_sql))
    if proposed_again != proposed:
        raise SystemExit("candidate replay did not return existing receipt")

    print("T09_REVIEW_HANDOFF")
    review_command = str(uuid.uuid4())
    review_sql = f"""
SELECT kdb_ops.request_review_handoff(
  '{review_command}'::uuid,
  {psql_str(tenant_a)},
  '{candidate_revision_id}'::uuid,
  {psql_str(sha256_text("o3-request-v1"))},
  'PRINCIPAL_REF_SYNTH_PIPELINE',
  'ACCESS_SYNTH_OK',
  '{uuid.uuid4()}'::uuid
);
"""
    handed = json.loads(must(USER_RUNTIME, review_sql))
    if handed.get("status") != "REVIEW_HANDOFF_REQUESTED_NOT_DECIDED":
        raise SystemExit(f"unexpected handoff outcome {handed}")
    handed_again = json.loads(must(USER_RUNTIME, review_sql))
    if handed_again != handed:
        raise SystemExit("handoff replay did not return existing receipt")

    print("T10_NO_PUBLICATION")
    proto = must(USER_SUPER, "SELECT count(*) FROM kdb_canonical.protocol;")
    proto_v = must(USER_SUPER, "SELECT count(*) FROM kdb_canonical.protocol_version;")
    decisions = must(
        USER_SUPER, "SELECT count(*) FROM kdb_governance.human_review_decision;"
    )
    if proto != "0" or proto_v != "0" or decisions != "0":
        raise SystemExit("publication tables were written")
    outbox = must(
        USER_SUPER,
        f"SELECT count(*), min(publish_state) FROM kdb_ops.outbox_event "
        f"WHERE aggregate_id='{candidate_revision_id}'::uuid;",
    )
    if not outbox.startswith("1|INACTIVE_M01"):
        raise SystemExit(f"unexpected outbox {outbox}")

    print("PASS_PG17_LOCAL_COMMAND_PATH_O1_O2_O3")
    print("NOTE_PUBLICATION_NOT_EXECUTED")
    print("NOTE_N8N_RUNTIME_NOT_USED")


if __name__ == "__main__":
    main()
