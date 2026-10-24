#!/usr/bin/env python3
"""Physical catalog assertions for default ACL, role graph, FORCE RLS, and future PUBLIC EXECUTE.

Disposable PostgreSQL 17 only. Does not connect to Supabase.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg17_disposable_command_path as cmd  # noqa: E402

TWELVE = [
    "kdb_governance.source",
    "kdb_governance.source_version",
    "kdb_staging.submission",
    "kdb_staging.candidate_revision",
    "kdb_staging.review_work_item",
    "kdb_governance.human_review_decision",
    "kdb_canonical.protocol",
    "kdb_canonical.protocol_version",
    "kdb_canonical.lifecycle_event",
    "kdb_ops.command_receipt",
    "kdb_ops.outbox_event",
    "kdb_ops.audit_event",
]
FUNCS = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)",
    "kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid)",
    "kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid)",
)
FINDINGS = []


def note(code: str, severity: str, detail) -> None:
    FINDINGS.append({"code": code, "severity": severity, "detail": detail})
    print(f"{severity} {code} {detail}")


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    superuser = cmd.USER_SUPER

    creator = cmd.must(
        superuser,
        "SELECT session_user||'|'||current_user||'|'||current_setting('is_superuser');",
    )
    print("APPLIER", creator)
    session_user, current_user, is_super = creator.split("|")
    if is_super == "on":
        note(
            "BLOCK_DEFAULT_ACL_CREATOR_UNPROVEN_SUPERUSER_APPLIER",
            "INFO",
            {"session_user": session_user, "current_user": current_user},
        )

    defacl = cmd.must(
        superuser,
        "SELECT coalesce(string_agg(pg_get_userbyid(d.defaclrole)||':'||"
        "coalesce(d.defaclnamespace::regnamespace::text,'-')||':'||d.defaclobjtype::text||':'||"
        "coalesce(d.defaclacl::text,''), ';'), '') FROM pg_default_acl d;",
    )
    print("PG_DEFAULT_ACL", defacl if defacl else "(empty)")
    if defacl:
        note("PG_DEFAULT_ACL_ROWS_PRESENT", "INFO", defacl)

    members = cmd.must(
        superuser,
        "SELECT coalesce(string_agg(member::regrole||'>'||roleid::regrole, ','), '') "
        "FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
        "WHERE r.rolname LIKE 'kdb\\_%' ESCAPE '\\';",
    )
    if members:
        note("KDB_ROLE_INHERITED_MEMBERSHIP", "RED", members)
    else:
        note("KDB_ROLE_INHERITED_MEMBERSHIP", "CLOSED", "none")

    for schema in ("kdb_canonical", "kdb_staging", "kdb_governance", "kdb_ops"):
        for role in ("anon", "authenticated", "service_role", "public"):
            usage = cmd.must(
                superuser,
                f"SELECT has_schema_privilege({cmd.psql_str(role)}, {cmd.psql_str(schema)}, 'USAGE');",
            )
            create = cmd.must(
                superuser,
                f"SELECT has_schema_privilege({cmd.psql_str(role)}, {cmd.psql_str(schema)}, 'CREATE');",
            )
            if usage in {"t", "true"} or create in {"t", "true"}:
                note(
                    "SCHEMA_GRANT_TO_UNTRUSTED",
                    "RED",
                    {"role": role, "schema": schema, "usage": usage, "create": create},
                )

    tables = cmd.must(
        superuser,
        "SELECT string_agg(n.nspname||'.'||c.relname||':'||c.relrowsecurity||':'||"
        "c.relforcerowsecurity||':'||pg_get_userbyid(c.relowner), ',') "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') "
        "AND c.relkind='r';",
    )
    seen = set()
    for item in tables.split(","):
        name, rls, force, owner = item.split(":")
        seen.add(name)
        if rls not in {"t", "true"} or force not in {"t", "true"} or owner != "kdb_schema_owner":
            note("FORCE_RLS_OR_OWNER", "RED", item)
    missing = [name for name in TWELVE if name not in seen]
    if missing:
        note("MISSING_TABLES", "RED", missing)

    for fn in FUNCS:
        owner_sec = cmd.must(
            superuser,
            "SELECT pg_get_userbyid(p.proowner)||'|'||p.prosecdef||'|'||"
            "coalesce(array_to_string(p.proconfig, ','), '') "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            f"WHERE n.nspname='kdb_ops' AND p.oid = {cmd.psql_str(fn)}::regprocedure;",
        )
        owner, secdef, config = owner_sec.split("|", 2)
        if owner != "kdb_command_owner" or secdef not in {"t", "true"} or "search_path=pg_catalog" not in config:
            note("FUNCTION_OWNER_OR_SEARCH_PATH", "RED", {fn: owner_sec})
        for role in ("anon", "authenticated", "service_role", "public"):
            exe = cmd.must(
                superuser,
                f"SELECT has_function_privilege({cmd.psql_str(role)}, {cmd.psql_str(fn)}, 'EXECUTE');",
            )
            if exe in {"t", "true"}:
                note("UNTRUSTED_EXECUTE", "RED", {"role": role, "fn": fn})

    cmd.must(
        superuser,
        "CREATE OR REPLACE FUNCTION kdb_ops.p2_acl_probe_future() "
        "RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$;",
    )
    public_exe = cmd.must(
        superuser,
        "SELECT has_function_privilege('public', 'kdb_ops.p2_acl_probe_future()', 'EXECUTE');",
    )
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p2_acl_probe_future();")
    if public_exe in {"t", "true"}:
        note(
            "BLOCK_DEFAULT_ACL_CREATOR",
            "INFO",
            "superuser-created function is PUBLIC EXECUTE; hosted apply stays blocked",
        )
    else:
        note("SUPERUSER_FUTURE_FUNCTION_PUBLIC_EXECUTE", "CLOSED", "PUBLIC EXECUTE denied for superuser probe")

    cmd.must(
        superuser,
        "SET ROLE kdb_migrator; "
        "CREATE FUNCTION kdb_ops.p3_acl_probe_future() "
        "RETURNS integer LANGUAGE sql SET search_path = pg_catalog AS $$ SELECT 1 $$; "
        "RESET ROLE;",
    )
    migrator_hits = []
    for role in ("anon", "authenticated", "service_role", "public"):
        exe = cmd.must(
            superuser,
            f"SELECT has_function_privilege({cmd.psql_str(role)}, "
            "'kdb_ops.p3_acl_probe_future()', 'EXECUTE');",
        )
        if exe in {"t", "true"}:
            migrator_hits.append(role)
    cmd.must(superuser, "DROP FUNCTION kdb_ops.p3_acl_probe_future();")
    if migrator_hits:
        note(
            "FUTURE_FUNCTION_PUBLIC_EXECUTE",
            "RED",
            {"creator": "kdb_migrator", "roles": migrator_hits},
        )
    else:
        note("FUTURE_FUNCTION_PUBLIC_EXECUTE", "CLOSED", "kdb_migrator probe has no untrusted EXECUTE")

    tls = {
        "code": "TLS_1PASSWORD_ISSUER",
        "severity": "NOT_TESTABLE_WITH_CURRENT_DEV_CREDENTIALS",
        "detail": "no issuer, JWKS, CA, or 1Password in this disposable cluster",
    }
    FINDINGS.append(tls)
    print("NOT_TESTABLE_WITH_CURRENT_DEV_CREDENTIALS TLS_1PASSWORD_ISSUER")

    red = [row for row in FINDINGS if row["severity"] == "RED"]
    out = Path("/tmp/kdb-p2-acl-findings.json")
    out.write_text(json.dumps({"findings": FINDINGS}, indent=2) + "\n")
    print("FINDINGS_SHA256", hashlib.sha256(out.read_bytes()).hexdigest())
    if red:
        print("RED_SECURITY_FINDINGS", len(red))
        print("REVIEWER_BLOCKING_NEGATIVE_GATE")
        print("NOTE_NOT_A_SECURITY_PASS")
        return
    print("PASS_PG17_ACL_CATALOG")
    print("NOTE_PIAC_STILL_FAIL_CLOSED")


if __name__ == "__main__":
    main()
