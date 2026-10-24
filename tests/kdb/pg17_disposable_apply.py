#!/usr/bin/env python3
"""Apply KDB-M01 001-003, P3 005, and P4 digest integrity to disposable PostgreSQL 17.

Default: docker container kdb-m01-pg17-disposable on 127.0.0.1:55432.
CI: KDB_PG17_MODE=libpq with PGHOST=127.0.0.1 only.
Does not apply 004, 098, or the P2 recovery candidate. Does not connect to Supabase.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTAINER = "kdb-m01-pg17-disposable"
USER = os.environ.get("PGUSER", "kdb_local_super")
DB = os.environ.get("PGDATABASE", "kdb_m01_disposable")
MODE = os.environ.get("KDB_PG17_MODE", "docker")
SQL_DIR = REPO / "database" / "migrations" / "kdb"
BOOT = REPO / "tests" / "kdb" / "pg17_disposable_bootstrap.sql"
ROLL = REPO / "tests" / "kdb" / "pg17_disposable_rollback.sql"
ORACLES = REPO / "tests" / "kdb" / "pg17_disposable_oracles.sql"
MIGRATIONS = [
    SQL_DIR / "20261023140000__kdb_m01_001__core_foundation.sql",
    SQL_DIR / "20261023140100__kdb_m01_002__security_boundary.sql",
    SQL_DIR / "20261023140200__kdb_m01_003__api_boundary.sql",
    SQL_DIR / "20261024190000__kdb_m01_p3__fail_closed_security.sql",
    SQL_DIR / "20261024220000__kdb_m01_p4__digest_oracle_integrity.sql",
]
FORBIDDEN_APPLY = (
    "20261023140300__kdb_m01_004__indexes_idempotency.sql",
    "098_deferred_promotion_not_for_m01.sql",
    "20261024180000__kdb_m01_p2__forward_recovery_candidate.sql",
)


def run(sql: str, argv_extra=None) -> str:
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
            USER,
            "-d",
            DB,
            "-v",
            "ON_ERROR_STOP=1",
            "-X",
            "-q",
        ]
    else:
        cmd = [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            USER,
            "-d",
            DB,
            "-v",
            "ON_ERROR_STOP=1",
            "-X",
            "-q",
        ]
    if argv_extra:
        cmd.extend(argv_extra)
    proc = subprocess.run(cmd, input=sql, text=True, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"psql failed rc={proc.returncode}")
    return proc.stdout


def guard() -> None:
    if MODE == "libpq":
        host = os.environ.get("PGHOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost"}:
            raise SystemExit(f"refusing PGHOST={host}")
        return
    names = subprocess.check_output(
        ["docker", "ps", "--format", "{{.Names}} {{.Image}} {{.Ports}}"], text=True
    )
    if CONTAINER not in names:
        raise SystemExit(f"missing container {CONTAINER}")
    img = subprocess.check_output(
        ["docker", "inspect", "-f", "{{.Config.Image}}", CONTAINER], text=True
    ).strip()
    if not img.startswith("postgres:17"):
        raise SystemExit(f"refusing image {img}")
    info = json.loads(subprocess.check_output(["docker", "inspect", CONTAINER], text=True))[0]
    bindings = (info.get("NetworkSettings") or {}).get("Ports", {}).get("5432/tcp") or []
    if not bindings:
        raise SystemExit("refusing missing 5432 publish")
    for binding in bindings:
        if binding.get("HostIp") != "127.0.0.1" or binding.get("HostPort") != "55432":
            raise SystemExit(f"refusing non-loopback publish: {binding}")


def schema_fingerprint() -> str:
    out = run(
        """
SELECT n.nspname||'.'||c.relname||' '||c.relrowsecurity||' '||c.relforcerowsecurity||' '||pg_get_userbyid(c.relowner)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') AND c.relkind='r'
ORDER BY 1;
SELECT n.nspname||'.'||p.proname||' '||p.prosecdef||' '||pg_get_userbyid(p.proowner)
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='kdb_ops' AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff','security_context_ready','canonical_command_digest','canonical_digest_v2','jsonb_sha256')
ORDER BY 1;
"""
    )
    return hashlib.sha256(out.encode()).hexdigest()


def apply_stack() -> None:
    run(BOOT.read_text())
    for path in MIGRATIONS:
        if path.name in FORBIDDEN_APPLY:
            raise SystemExit(f"refusing forbidden apply {path.name}")
        print(f"APPLY {path.name}")
        run(path.read_text())
    print(run(ORACLES.read_text()).strip())


def main() -> None:
    guard()
    ver = run("SHOW server_version;", argv_extra=["-t", "-A"])
    print("server_version", ver.strip())
    if "17." not in ver:
        raise SystemExit("not PostgreSQL 17")
    print("ROLLBACK_PRE")
    run(ROLL.read_text())
    print("APPLY_1")
    apply_stack()
    fp1 = schema_fingerprint()
    print("FINGERPRINT_1", fp1)
    print("SESSION_USER_CHECK")
    out = run("SELECT session_user, current_user;")
    print("superuser_session", out.strip())
    print("ROLLBACK_REAPPLY")
    run(ROLL.read_text())
    apply_stack()
    fp2 = schema_fingerprint()
    print("FINGERPRINT_2", fp2)
    if fp1 != fp2:
        raise SystemExit("rollback/reapply fingerprint mismatch")
    print("PASS_PG17_LOCAL_APPLY_ROLLBACK_REAPPLY")
    print("NOTE_T07_SET_ROLE_FROM_SUPERUSER_IS_NOT_A_POSITIVE")
    print("NOTE_PG_DEFAULT_ACL_EMPTY_ON_THIS_CLUSTER_BLOCK_DEFAULT_ACL_CREATOR")


if __name__ == "__main__":
    main()
