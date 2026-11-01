#!/usr/bin/env python3
"""P25 creator-specific future function ACL proof on disposable PostgreSQL 17."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg17_disposable_command_path as cmd  # noqa: E402

CANDIDATE = REPO / "tests/kdb/fixtures/p25_creator_default_acl_candidate.sql"
SUPER = cmd.USER_SUPER
CREATOR = "kdb_p25_creator"
OTHER = "kdb_p25_other_creator"
AUTHORIZED = "kdb_p25_authorized"
TARGET = "kdb_p25_target"
WRONG = "kdb_p25_wrong_schema"
UNTRUSTED = ("public", "anon", "authenticated", "service_role")


def truth(value: str) -> bool:
    return value in {"t", "true"}


def fail(message: str) -> None:
    raise SystemExit(message)


def cleanup() -> None:
    cmd.must(
        SUPER,
        f"""
DROP SCHEMA IF EXISTS {TARGET} CASCADE;
DROP SCHEMA IF EXISTS {WRONG} CASCADE;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{CREATOR}') THEN
    EXECUTE 'DROP OWNED BY {CREATOR}';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{OTHER}') THEN
    EXECUTE 'DROP OWNED BY {OTHER}';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{AUTHORIZED}') THEN
    EXECUTE 'DROP OWNED BY {AUTHORIZED}';
  END IF;
END $$;
DROP ROLE IF EXISTS {OTHER};
DROP ROLE IF EXISTS {AUTHORIZED};
DROP ROLE IF EXISTS {CREATOR};
""",
    )


def create_function(user: str, qualified: str) -> None:
    cmd.must(
        user,
        f"CREATE FUNCTION {qualified}() RETURNS integer LANGUAGE sql "
        "SET search_path = pg_catalog AS $$ SELECT 1 $$;",
    )


def privilege(role: str, qualified: str) -> bool:
    return truth(
        cmd.must(
            SUPER,
            f"SELECT has_function_privilege('{role}', '{qualified}()', 'EXECUTE');",
        )
    )


def deny_sqlstate(user: str, sql: str, label: str) -> None:
    proc = cmd.psql(user, "\\set VERBOSITY verbose\n" + sql)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0 or "42501" not in blob:
        fail(f"{label} expected SQLSTATE42501: {blob}")
    print(f"NEG {label} SQLSTATE=42501")


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    cleanup()
    matrix: dict[str, object] = {}
    try:
        cmd.must(
            SUPER,
            f"""
CREATE ROLE {CREATOR} LOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE {OTHER} LOGIN NOINHERIT NOBYPASSRLS;
CREATE ROLE {AUTHORIZED} NOLOGIN NOINHERIT NOBYPASSRLS;
CREATE SCHEMA {TARGET} AUTHORIZATION {CREATOR};
CREATE SCHEMA {WRONG} AUTHORIZATION {CREATOR};
GRANT USAGE, CREATE ON SCHEMA {TARGET} TO {OTHER};
""",
        )
        direct = cmd.must(CREATOR, "SELECT session_user||'|'||current_user;")
        if direct != f"{CREATOR}|{CREATOR}": fail("direct creator login not proven")
        memberships = cmd.must(
            SUPER,
            f"SELECT count(*) FROM pg_auth_members WHERE member IN ('{CREATOR}'::regrole, '{OTHER}'::regrole, '{AUTHORIZED}'::regrole);",
        )
        if memberships != "0": fail("unexpected creator-role membership")

        before_rows = cmd.must(SUPER, f"SELECT count(*) FROM pg_default_acl WHERE defaclrole='{CREATOR}'::regrole;")
        create_function(CREATOR, f"{TARGET}.before_fix")
        matrix["before_fix"] = {role: privilege(role, f"{TARGET}.before_fix") for role in (*UNTRUSTED, AUTHORIZED, CREATOR)}
        if not matrix["before_fix"]["public"]: fail("cluster preimage unexpectedly denies PUBLIC; record and revise proof")
        cmd.must(SUPER, f"DROP FUNCTION {TARGET}.before_fix();")

        cmd.must(CREATOR, CANDIDATE.read_text())
        global_rows = cmd.must(SUPER, f"SELECT count(*) FROM pg_default_acl WHERE defaclrole='{CREATOR}'::regrole AND defaclnamespace=0 AND defaclobjtype='f';")
        public_entries = cmd.must(SUPER, f"SELECT count(*) FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE d.defaclrole='{CREATOR}'::regrole AND d.defaclobjtype='f' AND a.grantee=0 AND a.privilege_type='EXECUTE';")
        authorized_entries = cmd.must(SUPER, f"SELECT count(*) FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE d.defaclrole='{CREATOR}'::regrole AND d.defaclnamespace='{TARGET}'::regnamespace AND d.defaclobjtype='f' AND a.grantee='{AUTHORIZED}'::regrole AND a.privilege_type='EXECUTE';")
        if (global_rows, public_entries, authorized_entries) != ("1", "0", "1"):
            fail(f"pg_default_acl mismatch {(global_rows, public_entries, authorized_entries)}")

        create_function(CREATOR, f"{TARGET}.after_fix")
        matrix["after_fix_target"] = {role: privilege(role, f"{TARGET}.after_fix") for role in (*UNTRUSTED, AUTHORIZED, CREATOR)}
        if any(matrix["after_fix_target"][role] for role in UNTRUSTED): fail("untrusted target EXECUTE")
        if not matrix["after_fix_target"][AUTHORIZED] or not matrix["after_fix_target"][CREATOR]: fail("intended or owner EXECUTE missing")

        create_function(CREATOR, f"{WRONG}.wrong_schema")
        matrix["wrong_schema"] = {role: privilege(role, f"{WRONG}.wrong_schema") for role in (*UNTRUSTED, AUTHORIZED)}
        if any(matrix["wrong_schema"].values()): fail("wrong schema inherited EXECUTE")

        create_function(OTHER, f"{TARGET}.wrong_creator")
        matrix["wrong_creator"] = {role: privilege(role, f"{TARGET}.wrong_creator") for role in (*UNTRUSTED, AUTHORIZED)}
        if not matrix["wrong_creator"]["public"]: fail("wrong creator unexpectedly covered")
        print("BLOCK WRONG_CREATOR_DEFAULT_ACL_UNPROVEN")

        ambiguous = cmd.must(SUPER, f"SET ROLE {CREATOR}; SELECT session_user||'|'||current_user; RESET ROLE;")
        if ambiguous != f"{SUPER}|{CREATOR}": fail(f"SET ROLE ambiguity missing: {ambiguous}")
        print("BLOCK SET_ROLE_SESSION_USER_AMBIGUITY")

        cmd.must(CREATOR, f"ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC; ALTER DEFAULT PRIVILEGES IN SCHEMA {TARGET} REVOKE EXECUTE ON FUNCTIONS FROM {AUTHORIZED};")
        create_function(CREATOR, f"{TARGET}.rollback_probe")
        if not privilege("public", f"{TARGET}.rollback_probe"): fail("rollback did not restore PUBLIC preimage")
        cmd.must(SUPER, f"DROP FUNCTION {TARGET}.rollback_probe();")
        cmd.must(CREATOR, CANDIDATE.read_text())
        create_function(CREATOR, f"{TARGET}.reapply_reconnect")
        if privilege("public", f"{TARGET}.reapply_reconnect") or not privilege(AUTHORIZED, f"{TARGET}.reapply_reconnect"):
            fail("reapply/reconnect ACL mismatch")

        deny_sqlstate("kdb_ingest_runtime", "SELECT 1 FROM kdb_canonical.protocol;", "runtime_select_denied")
        deny_sqlstate("kdb_ingest_runtime", "INSERT INTO kdb_governance.human_review_decision DEFAULT VALUES;", "c04_insert_denied")

        receipt = {
            "packet": "KDB-M01-P25-PG17-CREATOR-DEFAULT-ACL-LOCAL-HARDENING-01",
            "server": cmd.must(SUPER, "SHOW server_version;"),
            "creator_identity": direct,
            "pg_default_acl_before_rows": int(before_rows),
            "pg_default_acl_after": {"global_rows": 1, "public_execute_entries": 0, "target_authorized_entries": 1},
            "matrix": matrix,
            "wrong_creator": "BLOCKED_UNPROVEN",
            "set_role": "NOT_ACCEPTED_AS_POSITIVE",
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "security_status": "NOT_SECURITY_PASS",
        }
        print(json.dumps(receipt, sort_keys=True))
        print("PASS_P25_CREATOR_DEFAULT_ACL_LOCAL_HARDENING")
    finally:
        cleanup()
    residual = cmd.must(SUPER, "SELECT (SELECT count(*) FROM pg_roles WHERE rolname LIKE 'kdb_p25_%') + (SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'kdb_p25_%') + (SELECT count(*) FROM pg_default_acl d JOIN pg_roles r ON r.oid=d.defaclrole WHERE r.rolname LIKE 'kdb_p25_%');")
    if residual != "0": fail(f"P25 residual objects {residual}")
    print("P25_TEARDOWN ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
