#!/usr/bin/env python3
"""P26-R1: characterize a separate owner-transfer operator on disposable PG17."""
import pg17_disposable_command_path as db

S = db.USER_SUPER
RUNNER = 'kdb_migration_runner'
OP = 'kdb_owner_transfer_operator'


def sql(user, query):
    return db.must(user, query)


def expect(value, expected, label):
    if value != expected:
        raise SystemExit(f'FAIL_CLOSED {label}: {value!r} != {expected!r}')


def denied(user, query, label):
    p = db.psql(user, '\\set VERBOSITY verbose\n' + query)
    if p.returncode == 0 or '42501' not in p.stdout + p.stderr:
        raise SystemExit(f'FAIL_CLOSED {label}: {p.stdout} {p.stderr}')
    print(f'{label} SQLSTATE=42501')


def main():
    db.ensure_container()
    db.ensure_schema()
    expect(sql(S, "SELECT count(*) FROM pg_roles WHERE rolname IN ('kdb_migration_runner','kdb_owner_transfer_operator')"), '0', 'ROLE_PREIMAGE')
    expect(sql(S, "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='kdb_ops' AND p.proname LIKE 'p26r1_%'"), '0', 'FUNCTION_PREIMAGE')
    sql(S, 'CREATE ROLE kdb_migration_runner LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB; CREATE ROLE kdb_owner_transfer_operator LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB; GRANT USAGE, CREATE ON SCHEMA kdb_ops TO kdb_migration_runner;')
    try:
        expect(sql(RUNNER, "SELECT session_user||'|'||current_user"), RUNNER+'|'+RUNNER, 'RUNNER_LOGIN')
        expect(sql(OP, "SELECT session_user||'|'||current_user"), OP+'|'+OP, 'OPERATOR_LOGIN')
        sql(RUNNER, "DO $$ BEGIN IF session_user <> 'kdb_migration_runner' OR current_user <> 'kdb_migration_runner' THEN RAISE EXCEPTION 'IDENTITY_DRIFT'; END IF; END $$; ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC; CREATE FUNCTION kdb_ops.p26r1_o1() RETURNS integer LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT 26 $$; GRANT EXECUTE ON FUNCTION kdb_ops.p26r1_o1() TO kdb_ingest_runtime;")
        denied(RUNNER, 'SET ROLE kdb_command_owner', 'RUNNER_SET_OWNER_DENIED')
        denied(RUNNER, 'ALTER FUNCTION kdb_ops.p26r1_o1() OWNER TO kdb_command_owner', 'RUNNER_TRANSFER_DENIED')
        denied(OP, 'ALTER FUNCTION kdb_ops.p26r1_o1() OWNER TO kdb_command_owner', 'OPERATOR_WITHOUT_MEMBERSHIP_DENIED')
        sql(S, 'GRANT USAGE ON SCHEMA kdb_ops TO kdb_owner_transfer_operator; GRANT kdb_migration_runner TO kdb_owner_transfer_operator WITH INHERIT TRUE, SET FALSE; GRANT kdb_command_owner TO kdb_owner_transfer_operator WITH INHERIT FALSE, SET TRUE;')
        expect(sql(S, "SELECT string_agg(r.rolname||':'||m.set_option||':'||m.inherit_option,',' ORDER BY r.rolname) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid WHERE m.member='kdb_owner_transfer_operator'::regrole"), 'kdb_command_owner:true:false,kdb_migration_runner:false:true', 'OPERATOR_GRAPH')
        sql(OP, "DO $$ BEGIN IF session_user <> 'kdb_owner_transfer_operator' OR current_user <> 'kdb_owner_transfer_operator' THEN RAISE EXCEPTION 'IDENTITY_DRIFT'; END IF; END $$; ALTER FUNCTION kdb_ops.p26r1_o1() OWNER TO kdb_command_owner;")
        expect(sql(S, "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='kdb_ops.p26r1_o1()'::regprocedure"), 'kdb_command_owner', 'TRANSFER')
        expect(sql('kdb_ingest_runtime', 'SELECT kdb_ops.p26r1_o1()'), '26', 'RUNTIME_CALL')
        # Remove runner CREATE first; target-owner SET still provides CREATE.
        sql(S, 'REVOKE CREATE ON SCHEMA kdb_ops FROM kdb_migration_runner;')
        denied(OP, 'CREATE FUNCTION kdb_ops.p26r1_unapproved() RETURNS integer LANGUAGE sql AS $$ SELECT 99 $$', 'OPERATOR_DIRECT_CREATE_DENIED')
        expect(sql(OP, "SET ROLE kdb_command_owner; CREATE FUNCTION kdb_ops.p26r1_unapproved() RETURNS integer LANGUAGE sql AS $$ SELECT 99 $$; SELECT current_user;"), 'kdb_command_owner', 'UNAPPROVED_CREATE')
        print('FAIL_CLOSED OPERATOR_CAN_ASSUME_OWNER_AND_CREATE_UNAPPROVED_FUNCTION')
        print('DESIGN_CANDIDATE_NOT_SECURITY_ADMITTED')
    finally:
        sql(S, 'DROP FUNCTION IF EXISTS kdb_ops.p26r1_o1(); DROP FUNCTION IF EXISTS kdb_ops.p26r1_unapproved(); REVOKE kdb_migration_runner, kdb_command_owner FROM kdb_owner_transfer_operator; DROP OWNED BY kdb_owner_transfer_operator; DROP OWNED BY kdb_migration_runner; DROP ROLE kdb_owner_transfer_operator; DROP ROLE kdb_migration_runner;')
    expect(sql(S, "SELECT (SELECT count(*) FROM pg_roles WHERE rolname IN ('kdb_migration_runner','kdb_owner_transfer_operator'))+(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='kdb_ops' AND p.proname LIKE 'p26r1_%')"), '0', 'RESIDUAL')
    print('P26_R1_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
