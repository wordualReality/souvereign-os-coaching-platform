#!/usr/bin/env python3
"""P26: isolated PG17 creator identity and owner-transfer counterexample."""
import json
import pg17_disposable_command_path as db

SUPER = db.USER_SUPER
RUNNER = 'kdb_migration_runner'
OWNER = 'kdb_command_owner'
RUNTIME = 'kdb_ingest_runtime'
GUARD = "DO $$ BEGIN IF session_user <> 'kdb_migration_runner' OR current_user <> 'kdb_migration_runner' THEN RAISE EXCEPTION 'IDENTITY_DRIFT'; END IF; END $$; "


def check(value, expected, label):
    if value != expected:
        raise SystemExit(f'FAIL_CLOSED {label}: expected {expected!r}, got {value!r}')


def deny(user, sql, layer):
    result = db.psql(user, '\\set VERBOSITY verbose\n' + sql)
    if result.returncode == 0 or '42501' not in result.stdout + result.stderr:
        raise SystemExit(f'FAIL_CLOSED {layer}: {result.stdout} {result.stderr}')
    print(f'NEG {layer} SQLSTATE=42501')


def identity():
    check(db.must(RUNNER, 'SELECT session_user || \'|\' || current_user'),
          RUNNER + '|' + RUNNER, 'DIRECT_LOGIN')


def main():
    db.ensure_container()
    db.ensure_schema()
    # Refuse to overwrite a pre-existing runner, function, or role membership.
    check(db.must(SUPER, "SELECT count(*) FROM pg_roles WHERE rolname='kdb_migration_runner'"), '0', 'RUNNER_PREEXISTS')
    check(db.must(SUPER, "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='kdb_ops' AND p.proname LIKE 'p26_%'"), '0', 'FUNCTION_PREEXISTS')
    db.must(SUPER, 'CREATE ROLE kdb_migration_runner LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB; GRANT USAGE, CREATE ON SCHEMA kdb_ops TO kdb_migration_runner;')
    try:
        identity()
        db.must(RUNNER, GUARD + 'CREATE FUNCTION kdb_ops.p26_before() RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$;')
        check(db.must(SUPER, "SELECT has_function_privilege('public','kdb_ops.p26_before()','EXECUTE')"), 't', 'PUBLIC_PREIMAGE')
        db.must(RUNNER, GUARD + 'ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;')
        # The pre-existing function is not retroactively changed; OR REPLACE
        # also preserves its original ACL instead of applying new defaults.
        check(db.must(SUPER, "SELECT has_function_privilege('public','kdb_ops.p26_before()','EXECUTE')"), 't', 'EXISTING_ACL')
        db.must(RUNNER, 'CREATE OR REPLACE FUNCTION kdb_ops.p26_before() RETURNS integer LANGUAGE sql AS $$ SELECT 2 $$;')
        check(db.must(SUPER, "SELECT has_function_privilege('public','kdb_ops.p26_before()','EXECUTE')"), 't', 'REPLACE_ACL')
        db.must(RUNNER, 'BEGIN; ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC; ROLLBACK; ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;')
        check(db.must(SUPER, "SELECT count(*) FROM pg_default_acl d WHERE d.defaclrole='kdb_migration_runner'::regrole AND d.defaclnamespace=0 AND d.defaclobjtype='f' AND NOT EXISTS (SELECT 1 FROM aclexplode(d.defaclacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')"), '1', 'DEFAULT_ACL')
        identity()
        db.must(RUNNER, GUARD + "CREATE FUNCTION kdb_ops.p26_o1() RETURNS integer LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT 26 $$; REVOKE ALL ON FUNCTION kdb_ops.p26_o1() FROM PUBLIC, anon, authenticated, service_role; GRANT EXECUTE ON FUNCTION kdb_ops.p26_o1() TO kdb_ingest_runtime;")
        for role in ('public', 'anon', 'authenticated', 'service_role'):
            check(db.must(SUPER, f"SELECT has_function_privilege('{role}','kdb_ops.p26_o1()','EXECUTE')"), 'f', role)
        check(db.must(SUPER, "SELECT has_schema_privilege('kdb_ingest_runtime','kdb_ops','USAGE') AND NOT has_schema_privilege('kdb_ingest_runtime','kdb_ops','CREATE')"), 't', 'RUNTIME_SCHEMA')
        deny(RUNNER, 'CREATE FUNCTION public.p26_forbidden() RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$', 'WRONG_SCHEMA_CREATE')
        check(db.must(RUNTIME, 'SELECT kdb_ops.p26_o1()'), '26', 'RUNTIME_EXECUTE')
        deny(RUNTIME, 'SELECT 1 FROM kdb_canonical.protocol', 'RUNTIME_SELECT')
        deny(RUNTIME, 'INSERT INTO kdb_governance.human_review_decision DEFAULT VALUES', 'C04_INSERT')
        print('ACL_BEFORE_TRANSFER ' + db.must(SUPER, "SELECT coalesce(string_agg(pg_get_userbyid(a.grantor)||':'||coalesce(pg_get_userbyid(a.grantee),'PUBLIC')||':'||a.privilege_type,',' ORDER BY a.grantee),'') FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.oid='kdb_ops.p26_o1()'::regprocedure"))
        check(db.must(SUPER, "SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.oid='kdb_ops.p26_o1()'::regprocedure AND a.grantor <> 'kdb_migration_runner'::regrole"), '0', 'GRANTOR_BEFORE')
        check(db.must(SUPER, "SELECT pg_get_userbyid(proowner)||'|'||prosecdef||'|'||array_to_string(proconfig,',') FROM pg_proc WHERE oid='kdb_ops.p26_o1()'::regprocedure"), 'kdb_migration_runner|true|search_path=pg_catalog', 'FUNCTION_METADATA')
        # A membership with neither inheritance nor SET must not allow either
        # role switching or ownership transfer; do not infer this from NOINHERIT.
        db.must(SUPER, 'GRANT kdb_command_owner TO kdb_migration_runner WITH INHERIT FALSE, SET FALSE;')
        check(db.must(SUPER, "SELECT set_option||'|'||inherit_option FROM pg_auth_members WHERE roleid='kdb_command_owner'::regrole AND member='kdb_migration_runner'::regrole"), 'false|false', 'RESTRICTED_MEMBERSHIP')
        deny(RUNNER, 'SET ROLE kdb_command_owner', 'SET_FALSE_ROLE_SWITCH')
        deny(RUNNER, 'ALTER FUNCTION kdb_ops.p26_o1() OWNER TO kdb_command_owner', 'SET_FALSE_OWNER_TRANSFER')
        check(db.must(SUPER, "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='kdb_ops.p26_o1()'::regprocedure"), RUNNER, 'OWNER_UNCHANGED')
        print('RESTRICTED_MEMBERSHIP TRANSFER_DENIED')
        db.must(SUPER, 'GRANT kdb_command_owner TO kdb_migration_runner WITH INHERIT TRUE, SET FALSE;')
        check(db.must(SUPER, "SELECT set_option||'|'||inherit_option FROM pg_auth_members WHERE roleid='kdb_command_owner'::regrole AND member='kdb_migration_runner'::regrole"), 'false|true', 'INHERITED_MEMBERSHIP')
        deny(RUNNER, 'SET ROLE kdb_command_owner', 'INHERIT_ONLY_ROLE_SWITCH')
        deny(RUNNER, 'ALTER FUNCTION kdb_ops.p26_o1() OWNER TO kdb_command_owner', 'INHERIT_ONLY_OWNER_TRANSFER')
        # PG17's SET membership authorizes the transfer but exposes the owner role.
        db.must(SUPER, 'GRANT kdb_command_owner TO kdb_migration_runner WITH INHERIT FALSE, SET TRUE;')
        check(db.must(SUPER, "SELECT set_option||'|'||inherit_option FROM pg_auth_members WHERE roleid='kdb_command_owner'::regrole AND member='kdb_migration_runner'::regrole"), 'true|false', 'MEMBERSHIP')
        identity()
        check(db.must(RUNNER, 'SET ROLE kdb_command_owner; SELECT session_user||\'|\'||current_user'), 'kdb_migration_runner|kdb_command_owner', 'SET_ROLE_RISK')
        identity()
        db.must(RUNNER, GUARD + 'ALTER FUNCTION kdb_ops.p26_o1() OWNER TO kdb_command_owner;')
        check(db.must(SUPER, "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='kdb_ops.p26_o1()'::regprocedure"), OWNER, 'OWNER_TRANSFER')
        print('ACL_AFTER_TRANSFER ' + db.must(SUPER, "SELECT coalesce(string_agg(pg_get_userbyid(a.grantor)||':'||coalesce(pg_get_userbyid(a.grantee),'PUBLIC')||':'||a.privilege_type,',' ORDER BY a.grantee),'') FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.oid='kdb_ops.p26_o1()'::regprocedure"))
        check(db.must(SUPER, "SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.oid='kdb_ops.p26_o1()'::regprocedure AND a.grantor <> 'kdb_command_owner'::regrole"), '0', 'GRANTOR_AFTER')
        check(db.must(RUNTIME, 'SELECT kdb_ops.p26_o1()'), '26', 'POST_TRANSFER_EXECUTE')
        print('FAIL_CLOSED OWNER_TRANSFER_MEMBERSHIP_RISK')
        print(json.dumps({'creator': RUNNER, 'owner': OWNER, 'hosted': 'NOT_VERIFIED', 'security': 'NOT_PASS'}))
    finally:
        db.must(SUPER, 'DROP FUNCTION IF EXISTS kdb_ops.p26_o1(); DROP FUNCTION IF EXISTS kdb_ops.p26_before(); REVOKE kdb_command_owner FROM kdb_migration_runner; DROP OWNED BY kdb_migration_runner; DROP ROLE kdb_migration_runner;')
    check(db.must(SUPER, "SELECT (SELECT count(*) FROM pg_roles WHERE rolname='kdb_migration_runner')+(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='kdb_ops' AND p.proname LIKE 'p26_%')"), '0', 'TEARDOWN')
    print('P26_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
