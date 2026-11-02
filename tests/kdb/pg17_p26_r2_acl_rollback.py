#!/usr/bin/env python3
"""Disposable P26-R2 ACL preimage, rollback and wrong-creator proof."""
import json
import pg17_disposable_command_path as db

S = db.USER_SUPER
R = 'kdb_p26r2_runner'
W = 'kdb_p26r2_other'
SCHEMA = 'kdb_p26r2_ops'


def check(value, expected, label):
    if value != expected:
        raise SystemExit(f'FAIL_CLOSED {label}: expected {expected!r}, got {value!r}')


def denied(user, query, layer):
    p = db.psql(user, '\\set VERBOSITY verbose\n' + query)
    if p.returncode == 0 or '42501' not in p.stdout + p.stderr:
        raise SystemExit(f'FAIL_CLOSED {layer}: {p.stdout} {p.stderr}')
    print(f'NEG {layer} SQLSTATE=42501')


def snapshot():
    return db.must(S, """SELECT jsonb_build_object(
      'roles', (SELECT count(*) FROM pg_roles WHERE rolname LIKE 'kdb_p26r2_%'),
      'schemas', (SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'kdb_p26r2_%'),
      'functions', (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname LIKE 'kdb_p26r2_%'),
      'defaults', (SELECT count(*) FROM pg_default_acl d JOIN pg_roles r ON r.oid=d.defaclrole WHERE r.rolname LIKE 'kdb_p26r2_%'),
      'memberships', (SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname LIKE 'kdb_p26r2_%'))::text""")


def main():
    db.ensure_container()
    db.ensure_schema()
    pre = snapshot()
    check(json.loads(pre), {'roles': 0, 'schemas': 0, 'functions': 0, 'defaults': 0, 'memberships': 0}, 'PREIMAGE_OCCUPIED')
    db.must(S, f'CREATE ROLE {R} LOGIN NOINHERIT NOBYPASSRLS; CREATE ROLE {W} LOGIN NOINHERIT NOBYPASSRLS; CREATE SCHEMA {SCHEMA}; GRANT USAGE, CREATE ON SCHEMA {SCHEMA} TO {R}, {W};')
    try:
        check(db.must(R, "SELECT session_user||'|'||current_user"), R+'|'+R, 'DIRECT_LOGIN')
        db.must(R, f"CREATE FUNCTION {SCHEMA}.old() RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$; ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;")
        check(db.must(S, f"SELECT count(*) FROM pg_default_acl d WHERE d.defaclrole='{R}'::regrole AND d.defaclnamespace=0 AND d.defaclobjtype='f' AND NOT EXISTS (SELECT 1 FROM aclexplode(d.defaclacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')"), '1', 'GLOBAL_DEFAULT')
        db.must(R, f"CREATE FUNCTION {SCHEMA}.new() RETURNS integer LANGUAGE sql AS $$ SELECT 2 $$; CREATE OR REPLACE FUNCTION {SCHEMA}.old() RETURNS integer LANGUAGE sql AS $$ SELECT 3 $$;")
        db.must(W, f"CREATE FUNCTION {SCHEMA}.other() RETURNS integer LANGUAGE sql AS $$ SELECT 4 $$;")
        for name, expected in [('old','t'),('new','f'),('other','t')]:
            check(db.must(S, f"SELECT has_function_privilege('public','{SCHEMA}.{name}()','EXECUTE')"), expected, name)
        print('WRONG_CREATOR_PUBLIC_EXPOSURE TRUE')
        denied('kdb_ingest_runtime', f'SELECT {SCHEMA}.new()', 'SCHEMA_USAGE')
        db.must(S, f'GRANT USAGE ON SCHEMA {SCHEMA} TO kdb_ingest_runtime;')
        denied('kdb_ingest_runtime', f'SELECT {SCHEMA}.new()', 'FUNCTION_EXECUTE')
        db.must(R, f'GRANT EXECUTE ON FUNCTION {SCHEMA}.new() TO kdb_ingest_runtime;')
        check(db.must('kdb_ingest_runtime', f'SELECT {SCHEMA}.new()'), '2', 'RUNTIME_POSITIVE')
        denied('kdb_ingest_runtime', 'SELECT * FROM kdb_canonical.protocol', 'TABLE_SELECT')
        denied('kdb_ingest_runtime', 'INSERT INTO kdb_governance.human_review_decision DEFAULT VALUES', 'C04_INSERT')
        print('CATALOG ' + db.must(S, f"SELECT jsonb_build_object('schema_acl',(SELECT nspacl::text FROM pg_namespace WHERE nspname='{SCHEMA}'),'functions',(SELECT jsonb_agg(jsonb_build_object('name',p.proname,'owner',pg_get_userbyid(p.proowner),'acl',p.proacl::text) ORDER BY p.proname) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{SCHEMA}'),'default',(SELECT defaclacl::text FROM pg_default_acl WHERE defaclrole='{R}'::regrole AND defaclnamespace=0 AND defaclobjtype='f'))::text"))
        db.must(R, 'BEGIN; ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC; ROLLBACK;')
        check(db.must(S, f"SELECT has_function_privilege('public','{SCHEMA}.new()','EXECUTE')"), 'f', 'ROLLBACK_EXISTING')
        # Scoped inverse for this known synthetic preimage, not a generic
        # hosted undo: restore the absent runtime grant and implicit defaults.
        db.must(R, f'REVOKE EXECUTE ON FUNCTION {SCHEMA}.new() FROM kdb_ingest_runtime; ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC;')
        db.must(S, f'REVOKE USAGE ON SCHEMA {SCHEMA} FROM kdb_ingest_runtime;')
        check(db.must(S, f"SELECT count(*) FROM pg_default_acl WHERE defaclrole='{R}'::regrole"), '0', 'DEFAULT_PREIMAGE_RESTORED')
        check(db.must(S, f"SELECT has_schema_privilege('kdb_ingest_runtime','{SCHEMA}','USAGE') OR has_function_privilege('kdb_ingest_runtime','{SCHEMA}.new()','EXECUTE')"), 'f', 'ACL_PREIMAGE_RESTORED')
        print('SAFE_SYNTHETIC_UNWIND PREIMAGE_RESTORED')
        db.must(R, 'ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC; ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;')
        db.must(R, f'CREATE FUNCTION {SCHEMA}.reapply() RETURNS integer LANGUAGE sql AS $$ SELECT 5 $$;')
        check(db.must(S, f"SELECT has_function_privilege('public','{SCHEMA}.reapply()','EXECUTE')"), 'f', 'REAPPLY_RECONNECT')
    finally:
        db.must(S, f'DROP SCHEMA {SCHEMA} CASCADE; DROP OWNED BY {R}; DROP OWNED BY {W}; DROP ROLE {R}; DROP ROLE {W};')
    check(snapshot(), pre, 'ROLLBACK_PARITY')
    print('P26_R2_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
