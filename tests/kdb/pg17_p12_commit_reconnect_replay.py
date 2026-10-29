#!/usr/bin/env python3
"""P12 disposable PG17 commit, reconnect, replay, and revocation.

TEST_FIXTURE_ADMIN inserts a synthetic Source-to-Review chain, COMMITs it,
closes the backend, and SELECTs the same IDs on a new connection. Exact and
conflicting submission replays stay test-only unique-key proofs. A later
committed rights_status=REVOKED is read back and denied by P08. This is not
authorized runtime ingest. C04/C05 stay empty. FINAL is always NOT_ADMITTED.

Unique docker container (local) or unique database (CI libpq) is created and
dropped by this runner. Shared kdb-m01-pg17-disposable / kdb_m01_disposable
are never teardown targets. A docker restart of the unique container is a
server restart; a new psql backend is only CONNECTION_REOPENED_VERIFIED.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
import pg17_disposable_apply as apply  # noqa: E402
from offline_diagnostic import diagnose  # noqa: E402
from p11_evidence_matrix import build_matrix, verify_contract_mappings  # noqa: E402
from p11_snapshot_map import (  # noqa: E402
    assert_redacted,
    diagnostic_payload,
    id_digest,
    map_candidate_chain,
)
from provenance_eligibility import EligibilityError, evaluate_review_eligibility  # noqa: E402

PACKET = "KDB-M01-P12-DISPOSABLE-PG17-COMMIT-RECONNECT-REPLAY-REVOCATION-01"
FIXTURE_ADMIN = "kdb_test_fixture_admin"
TENANT = "TENANT_SYNTH_A"
CASE_ID = "P12-SYNTH-PG17-COMMIT-RECONNECT"
LIFECYCLE = json.loads(
    (REPO / "tests" / "kdb" / "fixtures" / "p11_synthetic_lifecycle.json").read_text()
)
SHARED_CONTAINER = "kdb-m01-pg17-disposable"
PROTECTED_DBS = frozenset(
    {"postgres", "template0", "template1", "kdb_m01_disposable"}
)
HOSTED_ENV = ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_DB_URL", "SUPABASE_SERVICE_ROLE")
IDENTITY_RE = re.compile(r"^kdb_p12_[0-9a-f]{12}$")
ROLE_LINE = re.compile(r"^CREATE ROLE ([a-z0-9_]+) ([^;]+);$", re.MULTILINE)
COUNT_SQL = """
SELECT jsonb_build_object(
  'source', (SELECT count(*) FROM kdb_governance.source),
  'source_version', (SELECT count(*) FROM kdb_governance.source_version),
  'submission', (SELECT count(*) FROM kdb_staging.submission),
  'candidate_revision', (SELECT count(*) FROM kdb_staging.candidate_revision),
  'review_work_item', (SELECT count(*) FROM kdb_staging.review_work_item),
  'human_review_decision', (SELECT count(*) FROM kdb_governance.human_review_decision),
  'protocol', (SELECT count(*) FROM kdb_canonical.protocol),
  'protocol_version', (SELECT count(*) FROM kdb_canonical.protocol_version),
  'lifecycle_event', (SELECT count(*) FROM kdb_canonical.lifecycle_event),
  'outbox_event', (SELECT count(*) FROM kdb_ops.outbox_event),
  'command_receipt', (SELECT count(*) FROM kdb_ops.command_receipt),
  'audit_event', (SELECT count(*) FROM kdb_ops.audit_event)
);
"""
PROTECTED_ZERO = (
    "human_review_decision",
    "protocol",
    "protocol_version",
    "lifecycle_event",
    "outbox_event",
    "command_receipt",
    "audit_event",
)

SOURCE_ID = "11111111-1111-4111-8111-111111111111"
VERSION_ID = "22222222-2222-4222-8222-222222222222"
VERSION_ID_2 = "22222222-2222-4222-8222-222222222223"
SUBMISSION_ID = "33333333-3333-4333-8333-333333333333"
CANDIDATE_ID = "44444444-4444-4444-8444-444444444444"
REVISION_ID = "55555555-5555-4555-8555-555555555555"
PROPOSAL_ID = "66666666-6666-4666-8666-666666666666"
WORK_ITEM_ID = "77777777-7777-4777-8777-777777777777"
CORR_ID = "88888888-8888-4888-8888-888888888888"
PENDING_SRC = "11111111-1111-4111-8111-aaaaaaaaaaa1"
CONTENT_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CONTENT_SHA_2 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
RIGHTS_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
CAND_SHA = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
REQ_SHA = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
REQ_SHA_CONFLICT = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
RIGHTS_ADMITTED = (
    '{"rights_status":"ADMITTED","rights_basis":"owner-authored-fixture",'
    '"allowed_purposes":["KNOWLEDGE_INTAKE"]}'
)
SPAN = '[{"source_version_id":"' + VERSION_ID + '","locator":"bytes:0-31"}]'
PAYLOAD = '{"title":"synthetic-candidate"}'

USER_SUPER = os.environ.get("PGUSER", "kdb_local_super")
USER_RUNTIME = "kdb_ingest_runtime"
MODE = os.environ.get("KDB_PG17_MODE", "docker")
ADMIN_DB = os.environ.get("PGDATABASE", "kdb_m01_disposable")


def fail(message: str) -> None:
    raise SystemExit(message)


def validate_identity(name: str) -> str:
    if IDENTITY_RE.fullmatch(name) is None:
        fail(f"P12_BAD_IDENTITY {name}")
    return name


def is_protected_name(name: str) -> bool:
    return name in PROTECTED_DBS or name == SHARED_CONTAINER


def refuse_hosted_env(env: dict[str, str] | None = None) -> None:
    blob = env if env is not None else os.environ
    for key in HOSTED_ENV:
        if blob.get(key):
            fail(f"P12_REFUSING_HOSTED_ENV {key}")
    host = blob.get("PGHOST", "127.0.0.1")
    if MODE == "libpq" and host not in {"127.0.0.1", "localhost"}:
        fail(f"P12_REFUSING_PGHOST {host}")


def role_exists_safe(sql: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name, rest = match.group(1), match.group(2)
        return (
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='"
            + name
            + "') THEN CREATE ROLE "
            + name
            + " "
            + rest
            + "; END IF; END $$;"
        )

    return ROLE_LINE.sub(repl, sql)


def reconnect_is_not_restart(reconnect_label: str, restart_label: str) -> None:
    if reconnect_label == "SERVER_RESTART_VERIFIED":
        fail("P12_RECONNECT_LABELLED_AS_RESTART")
    if restart_label == "CONNECTION_REOPENED_VERIFIED":
        fail("P12_RESTART_LABELLED_AS_RECONNECT")


def source_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return "UNPINNED_LOCAL"
    return proc.stdout.strip()


def pin_digest(snapshot: dict) -> str:
    version = snapshot.get("source_version") or {}
    submission = snapshot.get("submission") or {}
    candidate = snapshot.get("candidate_revision") or {}
    payload = json.dumps(
        {
            "content_sha256": str(version.get("content_sha256") or ""),
            "rights_snapshot_sha256": str(version.get("rights_snapshot_sha256") or ""),
            "request_sha256": str(submission.get("request_sha256") or ""),
            "candidate_content_sha256": str(candidate.get("content_sha256") or ""),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Target:
    def __init__(self, identity: str) -> None:
        self.identity = validate_identity(identity)
        self.dbname = self.identity
        self.mode = MODE
        self.container = f"kdb-m01-p12-{self.identity[8:]}"
        self.hostport = ""
        self.restart = "SERVER_RESTART_NOT_TESTED"
        if is_protected_name(self.dbname) or is_protected_name(self.container):
            fail("P12_PROTECTED_TARGET")
        if self.dbname == ADMIN_DB:
            fail("P12_ADMIN_DB_COLLISION")

    def psql(
        self, user: str, sql: str, db: str | None = None, extra=None
    ) -> subprocess.CompletedProcess:
        database = db or self.dbname
        if self.mode == "libpq":
            host = os.environ.get("PGHOST", "127.0.0.1")
            if host not in {"127.0.0.1", "localhost"}:
                fail(f"P12_REFUSING_PGHOST {host}")
            cmd = [
                "psql",
                "-h",
                host,
                "-p",
                os.environ.get("PGPORT", "5432"),
                "-U",
                user,
                "-d",
                database,
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
                self.container,
                "psql",
                "-U",
                user,
                "-d",
                database,
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

    def must(self, user: str, sql: str, db: str | None = None) -> str:
        proc = self.psql(user, sql, db=db)
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            fail(f"psql {user} failed rc={proc.returncode}")
        return proc.stdout.strip()

    def json_row(self, user: str, sql: str) -> dict:
        text = self.must(user, sql)
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            fail("P12_EMPTY_JSON")
        return json.loads(lines[-1])


def free_loopback_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def wait_ready(target: Target) -> None:
    for _ in range(40):
        ready = subprocess.run(
            [
                "docker",
                "exec",
                target.container,
                "pg_isready",
                "-U",
                USER_SUPER,
                "-d",
                target.dbname,
            ],
            capture_output=True,
            text=True,
        )
        if ready.returncode == 0:
            return
        time.sleep(1)
    fail("P12_POSTGRES_NOT_READY")


def guard_unique_container(target: Target) -> None:
    img = subprocess.check_output(
        ["docker", "inspect", "-f", "{{.Config.Image}}", target.container], text=True
    ).strip()
    if not img.startswith("postgres:17"):
        fail(f"P12_REFUSING_IMAGE {img}")
    info = json.loads(subprocess.check_output(["docker", "inspect", target.container], text=True))[0]
    bindings = (info.get("NetworkSettings") or {}).get("Ports", {}).get("5432/tcp") or []
    if not bindings:
        fail("P12_REFUSING_MISSING_PUBLISH")
    for binding in bindings:
        if binding.get("HostIp") != "127.0.0.1":
            fail(f"P12_REFUSING_NON_LOOPBACK {binding}")
        if binding.get("HostPort") == "55432":
            fail("P12_REFUSING_SHARED_PORT")


def start_unique_container(target: Target) -> None:
    existing = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}}"], text=True)
    if target.container in existing.splitlines():
        subprocess.check_call(["docker", "rm", "-f", target.container])
    last_error = ""
    for _ in range(5):
        port = free_loopback_port()
        proc = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                target.container,
                "-e",
                "POSTGRES_USER=" + USER_SUPER,
                "-e",
                "POSTGRES_DB=" + target.dbname,
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-p",
                f"127.0.0.1:{port}:5432",
                "postgres:17",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            target.hostport = str(port)
            wait_ready(target)
            guard_unique_container(target)
            return
        last_error = proc.stderr.strip() or proc.stdout.strip()
        subprocess.run(["docker", "rm", "-f", target.container], capture_output=True)
    fail(f"P12_DOCKER_RUN_FAILED {last_error}")


def apply_stack(target: Target) -> None:
    transform = target.mode == "libpq"
    target.must(USER_SUPER, apply.BOOT.read_text())
    for path in apply.MIGRATIONS:
        if path.name in apply.FORBIDDEN_APPLY:
            fail(f"P12_REFUSING_FORBIDDEN_APPLY {path.name}")
        print("APPLY", path.name)
        sql = path.read_text()
        if transform:
            sql = role_exists_safe(sql)
        proc = target.psql(USER_SUPER, sql, extra=["-q"])
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            fail(f"P12_APPLY_FAILED {path.name}")
    oracle = target.psql(USER_SUPER, apply.ORACLES.read_text(), extra=["-q"])
    if oracle.returncode != 0:
        sys.stderr.write(oracle.stdout)
        sys.stderr.write(oracle.stderr)
        fail("P12_ORACLES_FAILED")


def create_unique_database(target: Target) -> None:
    exists = target.must(
        USER_SUPER,
        f"SELECT count(*) FROM pg_database WHERE datname = '{target.dbname}';",
        db=ADMIN_DB,
    )
    if exists not in {"0", ""}:
        fail(f"P12_DB_ALREADY_EXISTS {target.dbname}")
    target.must(USER_SUPER, f"CREATE DATABASE {target.dbname};", db=ADMIN_DB)


def drop_unique_database(target: Target) -> None:
    target.psql(
        USER_SUPER,
        f"""
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '{target.dbname}' AND pid <> pg_backend_pid();
""",
        db=ADMIN_DB,
    )
    proc = target.psql(
        USER_SUPER, f"DROP DATABASE IF EXISTS {target.dbname} WITH (FORCE);", db=ADMIN_DB
    )
    if proc.returncode != 0:
        target.psql(USER_SUPER, f"DROP DATABASE IF EXISTS {target.dbname};", db=ADMIN_DB)
    left = target.must(
        USER_SUPER,
        f"SELECT count(*) FROM pg_database WHERE datname = '{target.dbname}';",
        db=ADMIN_DB,
    )
    if left not in {"0", ""}:
        fail(f"P12_DB_STILL_PRESENT {target.dbname}")


def teardown(target: Target) -> None:
    if is_protected_name(target.dbname) or is_protected_name(target.container):
        fail("P12_REFUSING_PROTECTED_TEARDOWN")
    if target.mode == "docker":
        subprocess.run(["docker", "rm", "-f", target.container], capture_output=True)
        return
    drop_unique_database(target)


def setup_fixture_admin(target: Target) -> None:
    target.must(
        USER_SUPER,
        f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{FIXTURE_ADMIN}') THEN
    CREATE ROLE {FIXTURE_ADMIN} LOGIN NOINHERIT BYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA kdb_governance, kdb_staging TO {FIXTURE_ADMIN};
GRANT SELECT, INSERT ON kdb_governance.source, kdb_governance.source_version TO {FIXTURE_ADMIN};
GRANT UPDATE (rights_status) ON kdb_governance.source TO {FIXTURE_ADMIN};
GRANT SELECT, INSERT ON kdb_staging.submission, kdb_staging.candidate_revision, kdb_staging.review_work_item TO {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_governance.human_review_decision FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.protocol FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.protocol_version FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.lifecycle_event FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_ops.outbox_event FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_ops.command_receipt FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_ops.audit_event FROM {FIXTURE_ADMIN};
""",
    )


def parse_sqlstate(blob: str, probe: str, expected: str) -> str:
    if "P12_UNEXPECTED_SUCCESS" in blob:
        fail(f"P12_EXPECTED_DENY {probe} succeeded: {blob}")
    marker = "P12_SQLSTATE="
    if marker not in blob:
        fail(f"P12_NO_SQLSTATE {probe}: {blob}")
    state = blob.split(marker, 1)[1].split()[0].strip().rstrip('"').rstrip("'")
    if state != expected:
        fail(f"P12_SQLSTATE_MISMATCH {probe} expected={expected} got={state} blob={blob}")
    print(f"NEG {probe} SQLSTATE={state}")
    return state


def capture_sqlstate(target: Target, user: str, inner_sql: str, expected: str, probe: str) -> str:
    wrapped = f"""
DO $p12$
BEGIN
  BEGIN
    {inner_sql}
    RAISE EXCEPTION 'P12_UNEXPECTED_SUCCESS {probe}';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE 'P12_UNEXPECTED_SUCCESS%' THEN
      RAISE;
    END IF;
    IF SQLSTATE IS DISTINCT FROM '{expected}' THEN
      RAISE EXCEPTION 'P12_WRONG_SQLSTATE probe={probe} expected={expected} got=% err=%', SQLSTATE, SQLERRM;
    END IF;
    RAISE EXCEPTION 'P12_SQLSTATE=%', SQLSTATE;
  END;
END
$p12$;
"""
    proc = target.psql(user, wrapped)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        fail(f"P12_EXPECTED_DENY {probe} succeeded: {blob}")
    return parse_sqlstate(blob, probe, expected)


def expect_eligibility_deny(chain: dict, code: str) -> None:
    try:
        evaluate_review_eligibility(chain)
    except EligibilityError as exc:
        if exc.code != code:
            fail(f"P12_P08_CODE expected={code} got={exc.code}")
        print(f"P08_DENY {code}")
        return
    fail(f"P12_P08_EXPECTED_DENY {code}")


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P12_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


INSERT_SQL = f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p12/source', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID}', '{SOURCE_ID}', '{TENANT}', '{CONTENT_SHA}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID_2}', '{SOURCE_ID}', '{TENANT}', '{CONTENT_SHA_2}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 2, '2026-10-28T01:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID}', '{TENANT}', 'KDB', 'p12-replay-001', '{REQ_SHA}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{REVISION_ID}', '{CANDIDATE_ID}', 1, '{TENANT}', '{VERSION_ID}',
  '{SUBMISSION_ID}', '{PROPOSAL_ID}', '{CAND_SHA}', '{SPAN}'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '{WORK_ITEM_ID}', '{REVISION_ID}', '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID}'
);
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{PENDING_SRC}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p12/pending', 'PENDING', 'KDB'
);
COMMIT;
SELECT jsonb_build_object(
  'backend_pid', pg_backend_pid(),
  'postmaster_start_time', pg_postmaster_start_time(),
  'ids', jsonb_build_object(
    'source_id', '{SOURCE_ID}',
    'source_version_id', '{VERSION_ID}',
    'submission_id', '{SUBMISSION_ID}',
    'candidate_revision_id', '{REVISION_ID}',
    'review_work_item_id', '{WORK_ITEM_ID}'
  ),
  'pins', jsonb_build_object(
    'content_sha256', '{CONTENT_SHA}',
    'rights_snapshot_sha256', '{RIGHTS_SHA}',
    'request_sha256', '{REQ_SHA}',
    'candidate_content_sha256', '{CAND_SHA}'
  )
);
"""

SELECT_SQL = f"""
SELECT jsonb_build_object(
  'backend_pid', pg_backend_pid(),
  'postmaster_start_time', pg_postmaster_start_time(),
  'source', (SELECT to_jsonb(s) FROM kdb_governance.source s WHERE source_id = '{SOURCE_ID}'),
  'source_version', (SELECT to_jsonb(v) FROM kdb_governance.source_version v WHERE source_version_id = '{VERSION_ID}'),
  'source_versions', (
    SELECT coalesce(jsonb_agg(to_jsonb(v) ORDER BY source_version_no), '[]'::jsonb)
    FROM kdb_governance.source_version v WHERE source_id = '{SOURCE_ID}'
  ),
  'submission', (SELECT to_jsonb(x) FROM kdb_staging.submission x WHERE submission_id = '{SUBMISSION_ID}'),
  'candidate_revision', (SELECT to_jsonb(c) FROM kdb_staging.candidate_revision c WHERE candidate_revision_id = '{REVISION_ID}'),
  'review_work_item', (SELECT to_jsonb(w) FROM kdb_staging.review_work_item w WHERE review_work_item_id = '{WORK_ITEM_ID}'),
  'pending_source', (SELECT to_jsonb(p) FROM kdb_governance.source p WHERE source_id = '{PENDING_SRC}'),
  'source_version_count', (SELECT count(*) FROM kdb_governance.source_version WHERE source_id = '{SOURCE_ID}'),
  'candidate_count', (SELECT count(*) FROM kdb_staging.candidate_revision WHERE source_version_id = '{VERSION_ID}'),
  'submission_count', (SELECT count(*) FROM kdb_staging.submission WHERE idempotency_key = 'p12-replay-001')
);
"""

FORCE_RLS_SQL = f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  'aaaaaaaa-bbbb-4ccc-8ddd-ffff00000012', '{TENANT}', 'OWNER_AUTHORED',
  'synthetic://kdb/p12/rls', 'ADMITTED', 'KDB'
);
SELECT 'superuser=' || count(*)::text FROM kdb_governance.source
 WHERE external_locator = 'synthetic://kdb/p12/rls';
SET ROLE kdb_command_owner;
SELECT 'command_owner_no_guc=' || count(*)::text FROM kdb_governance.source;
RESET ROLE;
ROLLBACK;
"""


def diagnose_not_admitted(snapshot: dict, commit: str) -> dict:
    chain = map_candidate_chain(snapshot)
    payload = diagnostic_payload(
        case_id=CASE_ID,
        expected_tenant_scope=TENANT,
        candidate_chain=chain,
        lifecycle_chain=LIFECYCLE,
    )
    original = deepcopy(payload)
    receipt = diagnose(payload, commit=commit)
    if payload != original:
        fail("P12_INPUT_MUTATED")
    if receipt["final_authority"] != "NOT_ADMITTED":
        fail("P12_FALSE_ADMIT")
    if receipt["execution"] != "NON_EXECUTABLE":
        fail("P12_FALSE_EXECUTABLE")
    if receipt["c04_human_decision"] != "NOT_WRITTEN":
        fail("P12_FALSE_C04")
    if receipt["c05_canonical_admission"] != "NOT_WRITTEN":
        fail("P12_FALSE_C05")
    return receipt


def main() -> None:
    refuse_hosted_env()
    identity = "kdb_p12_" + uuid.uuid4().hex[:12]
    target = Target(identity)
    print("P12_IDENTITY", target.identity)
    print("P12_MODE", target.mode)
    print("SOURCE_COMMIT", source_commit())
    created = False
    try:
        if target.mode == "docker":
            start_unique_container(target)
        else:
            create_unique_database(target)
        created = True
        ver = target.must(USER_SUPER, "SHOW server_version;")
        print("server_version", ver)
        if "17." not in ver:
            fail("P12_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")
        print("ROW_COUNTS_BEFORE", json.dumps(before, sort_keys=True))

        commit_proc = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_proc.returncode != 0:
            fail("P12_COMMIT_FAILED " + commit_proc.stdout + commit_proc.stderr)
        commit_lines = [line for line in commit_proc.stdout.splitlines() if line.strip()]
        commit_meta = json.loads(commit_lines[-1])
        commit_pid = int(commit_meta["backend_pid"])
        print("COMMIT_PID", commit_pid)

        snapshot = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        reconnect_pid = int(snapshot["backend_pid"])
        if reconnect_pid == commit_pid:
            fail("P12_SAME_BACKEND_PID")
        if snapshot.get("source") is None or snapshot.get("review_work_item") is None:
            fail("P12_INCOMPLETE_SNAPSHOT")
        if snapshot["source"]["rights_status"] != "ADMITTED":
            fail("P12_SOURCE_NOT_COMMITTED")
        if snapshot["pending_source"]["rights_status"] != "PENDING":
            fail("P12_PENDING_NOT_COMMITTED")
        if int(snapshot.get("source_version_count") or 0) < 2:
            fail("P12_SOURCE_VERSION_NOT_ONE_TO_N")
        if snapshot["submission"]["request_sha256"] != REQ_SHA:
            fail("P12_REQUEST_PIN_MISMATCH")
        digest_commit = hashlib.sha256(
            json.dumps(commit_meta["ids"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        digest_reconnect = id_digest(snapshot)
        if digest_commit != digest_reconnect:
            fail("P12_ID_DIGEST_MISMATCH")
        if pin_digest(snapshot) != hashlib.sha256(
            json.dumps(commit_meta["pins"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest():
            fail("P12_PIN_DIGEST_MISMATCH")
        mappings = verify_contract_mappings(snapshot)
        commit_sha = source_commit()
        admitted_receipt = diagnose_not_admitted(snapshot, commit_sha)
        if admitted_receipt["stages"]["provenance"]["status"] != "STAGE_LOCAL_ELIGIBLE":
            fail("P12_PROVENANCE_STAGE " + admitted_receipt["stages"]["provenance"]["code"])

        restart_meta = {
            "status": "SERVER_RESTART_NOT_TESTED",
            "note": "GitHub service container restart is not a uniquely identified disposable instance",
        }
        if target.mode == "docker":
            before_start = snapshot["postmaster_start_time"]
            subprocess.check_call(["docker", "restart", target.container])
            wait_ready(target)
            restarted = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
            if restarted["postmaster_start_time"] == before_start:
                fail("P12_POSTMASTER_UNCHANGED")
            if id_digest(restarted) != digest_reconnect:
                fail("P12_RESTART_DIGEST_MISMATCH")
            if pin_digest(restarted) != pin_digest(snapshot):
                fail("P12_RESTART_PIN_MISMATCH")
            snapshot = restarted
            target.restart = "SERVER_RESTART_VERIFIED"
            restart_meta = {
                "status": "SERVER_RESTART_VERIFIED",
                "postmaster_start_time": restarted["postmaster_start_time"],
                "backend_pid": int(restarted["backend_pid"]),
            }
            print("SERVER_RESTART_VERIFIED")
        reconnect_is_not_restart("CONNECTION_REOPENED_VERIFIED", target.restart)

        exact_state = capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '33333333-3333-4333-8333-333333333334', '{TENANT}', 'KDB', 'p12-replay-001', '{REQ_SHA}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
""",
            "23505",
            "exact_replay",
        )
        conflict_state = capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '33333333-3333-4333-8333-333333333335', '{TENANT}', 'KDB', 'p12-replay-001', '{REQ_SHA_CONFLICT}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
""",
            "23505",
            "conflicting_replay",
        )
        cross_state = capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '22222222-2222-4222-8222-222222222229', '{SOURCE_ID}', 'TENANT_SYNTH_B',
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab',
  '{RIGHTS_ADMITTED}'::jsonb, '{RIGHTS_SHA}', 'text/plain', 3, '2026-10-28T02:00:00Z'
);
""",
            "23503",
            "cross_tenant_fk",
        )
        immutable_state = capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
UPDATE kdb_governance.source_version
SET content_sha256 = '{CONTENT_SHA_2}'
WHERE source_version_id = '{VERSION_ID}';
""",
            "42501",
            "immutable_source_version",
        )
        after_replay = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        if int(after_replay.get("submission_count") or 0) != 1:
            fail("P12_DUPLICATE_SUBMISSION_WRITE")
        if after_replay["submission"]["request_sha256"] != REQ_SHA:
            fail("P12_CONFLICT_OVERWROTE_DIGEST")
        if pin_digest(after_replay) != pin_digest(snapshot):
            fail("P12_REPLAY_MUTATED_PINS")

        revoke_proc = target.psql(
            FIXTURE_ADMIN,
            f"""
BEGIN;
UPDATE kdb_governance.source
SET rights_status = 'REVOKED'
WHERE source_id = '{SOURCE_ID}';
COMMIT;
SELECT rights_status FROM kdb_governance.source WHERE source_id = '{SOURCE_ID}';
""",
        )
        if revoke_proc.returncode != 0:
            fail("P12_REVOKE_FAILED " + revoke_proc.stdout + revoke_proc.stderr)
        revoked_snapshot = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        if revoked_snapshot["source"]["rights_status"] != "REVOKED":
            fail("P12_REVOKE_NOT_COMMITTED")
        chain = map_candidate_chain(revoked_snapshot)
        expect_eligibility_deny(chain, "REVOKED_SOURCE")
        if revoked_snapshot["pending_source"]["rights_status"] != "PENDING":
            fail("P12_PENDING_ROW_MISSING")
        pending = map_candidate_chain(revoked_snapshot)
        pending["source"]["rights_status"] = "PENDING"
        expect_eligibility_deny(pending, "MISSING_RIGHTS")
        stale = map_candidate_chain(revoked_snapshot)
        stale["source"]["rights_status"] = "ADMITTED"
        stale["source_versions"] = revoked_snapshot["source_versions"]
        expect_eligibility_deny(stale, "STALE_SOURCE_VERSION")
        revoked_receipt = diagnose_not_admitted(revoked_snapshot, commit_sha)
        if revoked_receipt["stages"]["provenance"]["status"] == "STAGE_LOCAL_ELIGIBLE":
            fail("P12_REVOKED_STILL_ELIGIBLE")

        c04_state = capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_governance.human_review_decision (
  candidate_revision_id, candidate_content_sha256, reviewer_principal_ref,
  access_decision_ref, decision, source_rights_digest, review_evidence_sha256
) VALUES (
  '{REVISION_ID}', '{CAND_SHA}', 'reviewer-untrusted',
  'access-ref-untrusted-string', 'APPROVED_FOR_PROMOTION', '{RIGHTS_SHA}', '{CAND_SHA}'
);
""",
            "42501",
            "c04_insert_denied",
        )
        runtime = []
        for probe, sql in (
            ("runtime_select_denied", "PERFORM 1 FROM kdb_governance.source;"),
            (
                "runtime_insert_denied",
                f"""
INSERT INTO kdb_governance.source (
  tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p12/runtime', 'ADMITTED', 'KDB'
);
""",
            ),
            ("runtime_security_context_execute_denied", "PERFORM kdb_ops.security_context_ready();"),
            (
                "runtime_o1_execute_denied",
                "PERFORM kdb_ops.ingest_source("
                " '11111111-1111-4111-8111-999999999999'::uuid,"
                f" '{SUBMISSION_ID}'::uuid, '{TENANT}', 'KDB', 'p12-runtime-001',"
                f" '{REQ_SHA}', 'OWNER_AUTHORED', 'synthetic://kdb/p12/runtime',"
                f" '{CONTENT_SHA}', '{RIGHTS_ADMITTED}'::jsonb, '{RIGHTS_SHA}',"
                " 'piac-ref-untrusted-string', 'access-ref-untrusted-string',"
                f" 'KNOWLEDGE_INTAKE', '{CORR_ID}'::uuid, '2026-10-28T00:00:00Z'::timestamptz"
                ");",
            ),
        ):
            state = capture_sqlstate(target, USER_RUNTIME, sql, "42501", probe)
            runtime.append(
                {
                    "probe": probe,
                    "sqlstate": state,
                    "role": USER_RUNTIME,
                    "enforced_by": "ACL",
                }
            )
        rls = target.psql(USER_SUPER, FORCE_RLS_SQL)
        if rls.returncode != 0:
            fail("P12_FORCE_RLS_FAILED " + rls.stdout + rls.stderr)
        rls_out = rls.stdout + rls.stderr
        if "superuser=1" not in rls_out:
            fail("P12_FORCE_RLS_SUPERUSER_MISSING " + rls_out)
        if "command_owner_no_guc=0" not in rls_out:
            fail("P12_FORCE_RLS_LEAK " + rls_out)
        print("FORCE_RLS command_owner_no_guc=0 SET_ROLE_FROM_SUPERUSER_IS_NOT_A_POSITIVE")

        after = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(after, "AFTER")
        print("ROW_COUNTS_AFTER", json.dumps(after, sort_keys=True))

        matrix = build_matrix(
            commit=commit_sha,
            environment="disposable-postgres-17",
            packet=PACKET,
            restart_replay=target.restart,
            restart_replay_next=(
                "unique docker container restarted"
                if target.restart == "SERVER_RESTART_VERIFIED"
                else "CI libpq cannot restart the shared GitHub service container"
            ),
            run={
                "slice_pass": True,
                "denials_pass": True,
                "zero_ops": True,
                "tests": [
                    "pg17_p12_commit_reconnect_replay",
                    "test_p12_commit_reconnect",
                    "test_p11_source_review_readback",
                    "test_offline_diagnostic",
                ],
                "contract_mappings": mappings,
                "cardinality": {
                    "source_version_per_source": int(revoked_snapshot.get("source_version_count") or 0),
                    "candidates_per_bound_version": int(revoked_snapshot.get("candidate_count") or 0),
                },
            },
        )
        if matrix["logical_objects_claimed"] == "18/18":
            fail("P12_FALSE_18_OF_18")
        if matrix["inventory_source"] != "INVENTORY_SOURCE_GAP":
            fail("P12_INVENTORY_MUST_STAY_GAP")
        if matrix["hosted_verified"] != "HOSTED_VERIFIED_NO":
            fail("P12_FALSE_HOSTED")

        wrapper = {
            "packet": PACKET,
            "df_adoption": "DF-20261029-01",
            "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "fixture_admin": FIXTURE_ADMIN,
            "fixture_admin_is_runtime_principal": False,
            "persistence": "TEST_ADMIN_COMMITTED",
            "lifecycle_source": "SYNTHETIC_FIXTURE_NOT_DB",
            "c04_human_decision": "NOT_WRITTEN",
            "c05_canonical_admission": "NOT_WRITTEN",
            "outbox": "NOT_EMITTED",
            "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
            "event_watermark": "UNTRUSTED",
            "environment": {
                "identity": target.identity,
                "mode": target.mode,
                "image": "postgres:17",
                "loopback": True,
            },
            "phases": {
                "commit": {
                    "status": "TEST_ADMIN_COMMITTED",
                    "backend_pid": commit_pid,
                },
                "reconnect": {
                    "status": "CONNECTION_REOPENED_VERIFIED",
                    "backend_pid": reconnect_pid,
                    "id_digest": digest_reconnect,
                    "note": "new psql backend is not a database restart",
                },
                "server_restart": restart_meta,
                "replay_exact": {
                    "label": "EXACT_TEST_ONLY_REPLAY",
                    "sqlstate": exact_state,
                    "duplicate_write": False,
                    "runtime_o1_idempotency": "NOT_CLAIMED",
                },
                "replay_conflict": {
                    "label": "CONFLICT_SQL23505",
                    "sqlstate": conflict_state,
                    "original_digest_preserved": True,
                },
                "cross_tenant": {"sqlstate": cross_state, "enforced_by": "DB_CONSTRAINT"},
                "immutable_source_version": {
                    "sqlstate": immutable_state,
                    "enforced_by": "ACL",
                },
                "revocation": {
                    "rights_status": "REVOKED",
                    "p08": "REVOKED_SOURCE",
                    "p10_final": "NOT_ADMITTED",
                },
                "pending": {"p08": "MISSING_RIGHTS"},
                "stale": {"p08": "STALE_SOURCE_VERSION"},
            },
            "snapshot_id_digest": digest_reconnect,
            "row_counts_before": before,
            "row_counts_after": after,
            "negatives": [
                {"probe": "exact_replay", "sqlstate": exact_state, "enforced_by": "DB_CONSTRAINT"},
                {
                    "probe": "conflicting_replay",
                    "sqlstate": conflict_state,
                    "enforced_by": "DB_CONSTRAINT",
                },
                {"probe": "cross_tenant_fk", "sqlstate": cross_state, "enforced_by": "DB_CONSTRAINT"},
                {
                    "probe": "immutable_source_version",
                    "sqlstate": immutable_state,
                    "enforced_by": "ACL",
                },
                {"probe": "c04_insert_denied", "sqlstate": c04_state, "enforced_by": "ACL"},
            ],
            "runtime_denials": runtime,
            "force_rls": {
                "role": "kdb_command_owner",
                "missing_tenant_guc_count": 0,
                "note": "SET_ROLE_FROM_SUPERUSER_IS_NOT_A_POSITIVE",
            },
            "evidence_matrix": matrix,
            "diagnostic_after_revoke": revoked_receipt,
            "source_commit": commit_sha,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P12_FORBIDDEN_TOKEN")
        print(text)
        print("PASS_P12_DISPOSABLE_PG17_COMMIT_RECONNECT_REPLAY_REVOCATION")
    finally:
        if created:
            teardown(target)
            print("P12_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
