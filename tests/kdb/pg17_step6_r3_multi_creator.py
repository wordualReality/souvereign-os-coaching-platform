#!/usr/bin/env python3
"""Disposable PG17 multi-creator default ACL boundary; not hosted authority."""
import json
import pg17_disposable_command_path as db

S = db.USER_SUPER
NS = 'kdb_step6r3_ops'
A, B, C, G = ('kdb_step6r3_creator_a', 'kdb_step6r3_creator_b',
              'kdb_step6r3_creator_c', 'kdb_step6r3_allowed')
ROLES = (A, B, C, G)
UNTRUSTED = ('public', 'anon', 'authenticated', 'service_role')
FUNCTIONS = ('a_old', 'b_old', 'a_after', 'b_unhardened', 'b_after', 'c_uncontrolled', 'a_set_role')


def expect(actual, expected, label):
    if actual != expected:
        raise SystemExit(f'FAIL_CLOSED {label}: expected={expected!r} actual={actual!r}')


def scalar(sql):
    return db.must(S, sql)


def runtime_preimage():
    return scalar("""SELECT jsonb_build_object(
      'role',(SELECT row_to_json(r)::jsonb FROM (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname='kdb_ingest_runtime') r),
      'memberships',(SELECT coalesce(jsonb_agg(jsonb_build_array(roleid,member,admin_option,inherit_option,set_option) ORDER BY roleid,member),'[]'::jsonb) FROM pg_auth_members WHERE member='kdb_ingest_runtime'::regrole OR roleid='kdb_ingest_runtime'::regrole),
      'schema_acls',(SELECT coalesce(jsonb_agg(jsonb_build_array(nspname,nspowner,nspacl::text) ORDER BY nspname),'[]'::jsonb) FROM pg_namespace WHERE nspname IN ('kdb_ops','kdb_staging','kdb_governance','kdb_canonical')),
      'table_acls',(SELECT coalesce(jsonb_agg(jsonb_build_array(n.nspname,c.relname,c.relowner,c.relacl::text) ORDER BY n.nspname,c.relname),'[]'::jsonb) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('kdb_ops','kdb_staging','kdb_governance','kdb_canonical') AND c.relkind IN ('r','p'))
    )::text""")


def inventory():
    return json.loads(scalar(f"""SELECT jsonb_build_object(
      'roles',(SELECT count(*) FROM pg_roles WHERE rolname IN ('{A}','{B}','{C}','{G}')),
      'schema',(SELECT count(*) FROM pg_namespace WHERE nspname='{NS}'),
      'functions',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}'),
      'defaults',(SELECT count(*) FROM pg_default_acl d JOIN pg_roles r ON r.oid=d.defaclrole WHERE r.rolname IN ('{A}','{B}','{C}','{G}')),
      'memberships',(SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member OR r.oid=m.roleid WHERE r.rolname IN ('{A}','{B}','{C}','{G}'))
    )::text"""))


def create_as(role, name):
    guard = f"DO $$ BEGIN IF session_user <> '{role}' OR current_user <> '{role}' THEN RAISE EXCEPTION 'CREATOR_IDENTITY_DRIFT'; END IF; END $$; "
    identity = db.must(role, guard+f"SELECT 'DIRECT|'||session_user||'|'||current_user||'|'||txid_current(); CREATE FUNCTION {NS}.{name}() RETURNS integer LANGUAGE sql AS $$ SELECT 1 $$;")
    if not identity.startswith(f'DIRECT|{role}|{role}|'): raise SystemExit('FAIL_CLOSED DIRECT_IDENTITY '+identity)
    print('CREATOR_TRANSACTION '+identity+' FUNCTION='+name)


def harden(role):
    guard = f"DO $$ BEGIN IF session_user <> '{role}' OR current_user <> '{role}' THEN RAISE EXCEPTION 'CREATOR_IDENTITY_DRIFT'; END IF; END $$; "
    db.must(role, guard+'ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;')
    result = scalar(f"SELECT count(*) FROM pg_default_acl d WHERE d.defaclrole='{role}'::regrole AND d.defaclnamespace=0 AND d.defaclobjtype='f' AND NOT EXISTS (SELECT 1 FROM aclexplode(d.defaclacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')")
    expect(result, '1', 'GLOBAL_DEFAULT_'+role)


def privileged(role, name):
    return scalar(f"SELECT has_function_privilege('{role}','{NS}.{name}()','EXECUTE')") == 't'


def observe(name):
    raw = scalar(f"SELECT jsonb_build_object('schema','{NS}','function',p.proname,'owner',pg_get_userbyid(p.proowner),'raw_acl',p.proacl::text,'entries',(SELECT coalesce(jsonb_agg(jsonb_build_object('grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type),'[]'::jsonb) FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a))::text FROM pg_proc p WHERE p.oid='{NS}.{name}()'::regprocedure")
    matrix = {role: privileged(role, name) for role in (*UNTRUSTED,G,A,B,C)}
    print('FUNCTION_ACL '+raw+' EFFECTIVE '+json.dumps(matrix, sort_keys=True))
    return matrix


def main():
    db.ensure_container(); db.ensure_schema()
    before = inventory()
    expect(before, {'roles':0,'schema':0,'functions':0,'defaults':0,'memberships':0}, 'PREIMAGE_OCCUPIED')
    canonical_before = runtime_preimage()
    print('STEP6R3_NAMED_PREIMAGE '+json.dumps(before, sort_keys=True))
    db.must(S, f'CREATE ROLE {A} LOGIN NOINHERIT NOBYPASSRLS; CREATE ROLE {B} LOGIN NOINHERIT NOBYPASSRLS; CREATE ROLE {C} LOGIN NOINHERIT NOBYPASSRLS; CREATE ROLE {G} NOLOGIN NOINHERIT NOBYPASSRLS; CREATE SCHEMA {NS}; REVOKE ALL ON SCHEMA {NS} FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA {NS} TO {A},{B},{C}; GRANT USAGE ON SCHEMA {NS} TO {G};')
    try:
        create_as(A,'a_old'); create_as(B,'b_old')
        for name in ('a_old','b_old'):
            expect(observe(name)['public'], True, 'OLD_PUBLIC_'+name)
        harden(A)
        create_as(A,'a_after'); create_as(B,'b_unhardened')
        expect(observe('a_after')['public'], False, 'A_HARDENED')
        expect(observe('b_unhardened')['public'], True, 'A_DID_NOT_HARDEN_B')
        expect(scalar(f"SELECT count(*) FROM pg_default_acl WHERE defaclrole='{B}'::regrole"), '0', 'B_DEFAULT_UNCHANGED_AFTER_A')
        harden(B)
        create_as(B,'b_after'); create_as(C,'c_uncontrolled')
        db.must(A, f'GRANT EXECUTE ON FUNCTION {NS}.a_after() TO {G};')
        db.must(B, f'GRANT EXECUTE ON FUNCTION {NS}.b_after() TO {G};')
        for name, owner in (('a_after',A),('b_after',B)):
            mat = observe(name)
            if any(mat[r] for r in UNTRUSTED) or not mat[G] or not mat[owner]:
                raise SystemExit('FAIL_CLOSED HARDENED_MATRIX '+name+' '+str(mat))
            expect(scalar(f"SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='{NS}.{name}()'::regprocedure"), owner, 'OWNER_'+name)
        for role, name in ((A,'a_old'),(B,'b_old')):
            db.must(role, f'CREATE OR REPLACE FUNCTION {NS}.{name}() RETURNS integer LANGUAGE sql AS $$ SELECT 2 $$;')
            expect(observe(name)['public'], True, 'REPLACE_NOT_RETROACTIVE_'+name)
        expect(observe('b_unhardened')['public'], True, 'B_EXISTING_NOT_RETROACTIVE')
        expect(observe('c_uncontrolled')['public'], True, 'C_PUBLIC_EXPOSURE')
        expect(scalar(f"SELECT has_schema_privilege('anon','{NS}','USAGE')"), 'f', 'SCHEMA_USAGE_MASK')
        denied = db.psql(S, '\\set VERBOSITY verbose\n'+f'SET ROLE anon; SELECT {NS}.c_uncontrolled();')
        if denied.returncode == 0 or '42501' not in denied.stderr or 'permission denied for schema' not in denied.stderr:
            raise SystemExit('FAIL_CLOSED SCHEMA_DENIAL_NOT_PROVEN '+denied.stderr)
        print('NEG SCHEMA_USAGE_MASK SQLSTATE=42501 / SET_ROLE_NEGATIVE_ONLY')
        db.must(S, f'GRANT USAGE ON SCHEMA {NS} TO anon;')
        try:
            expect(db.must(S, f'SET ROLE anon; SELECT {NS}.c_uncontrolled();'), '1', 'C_CALL_WITH_SCHEMA_USAGE')
            print('C_PUBLIC_CALLABLE_WITH_SCHEMA_USAGE / SET_ROLE_SIMULATION_ONLY')
        finally:
            db.must(S, f'REVOKE USAGE ON SCHEMA {NS} FROM anon;')
        expect(db.must(S, f'SET ROLE {G}; SELECT {NS}.a_after()+{NS}.b_after();'), '2', 'NAMED_GRANTEE_CALL')
        print('NAMED_GRANTEE_CALL PASS / SET_ROLE_SIMULATION_ONLY')
        print('OTHER_CREATORS_UNCONTROLLED PUBLIC_EXECUTE_TRUE / ANON_SCHEMA_USAGE_FALSE / CALLABILITY_MASKED')
        identity = db.must(S, f"SET ROLE {A}; SELECT 'SET_ROLE|'||session_user||'|'||current_user||'|'||txid_current(); CREATE FUNCTION {NS}.a_set_role() RETURNS integer LANGUAGE sql AS $$ SELECT 3 $$;")
        if not identity.startswith(f'SET_ROLE|{S}|{A}|'): raise SystemExit('FAIL_CLOSED SET_ROLE_IDENTITY '+identity)
        expect(observe('a_set_role')['public'], False, 'SET_ROLE_CURRENT_CREATOR_DEFAULT')
        expect(scalar(f"SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='{NS}.a_set_role()'::regprocedure"), A, 'SET_ROLE_OWNER')
        print('SET_ROLE_NOT_DIRECT_LOGIN '+identity)
        rows = scalar(f"SELECT coalesce(jsonb_agg(jsonb_build_object('creator',pg_get_userbyid(d.defaclrole),'schema_oid',d.defaclnamespace,'type',d.defaclobjtype,'raw_acl',d.defaclacl::text,'entries',(SELECT coalesce(jsonb_agg(jsonb_build_object('grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee),'[]'::jsonb) FROM aclexplode(d.defaclacl) a)) ORDER BY d.defaclrole),'[]'::jsonb)::text FROM pg_default_acl d WHERE d.defaclrole IN ('{A}'::regrole,'{B}'::regrole,'{C}'::regrole)")
        print('CREATOR_DEFAULT_ACL '+rows)
        expect(scalar(f"SELECT count(*) FROM pg_default_acl WHERE defaclrole='{C}'::regrole"), '0', 'C_DEFAULT_UNCHANGED')
        expect(db.must(A, "SELECT session_user||'|'||current_user"), A+'|'+A, 'A_RECONNECT')
        expect(db.must(B, "SELECT session_user||'|'||current_user"), B+'|'+B, 'B_RECONNECT')
        print('STEP6R3_TWO_CONFIGURED_CREATORS PASS_SCOPED')
    finally:
        for name in FUNCTIONS:
            db.must(S, f'DROP FUNCTION IF EXISTS {NS}.{name}();')
        for role in (A,B):
            db.must(role, 'ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC;')
        db.must(S, f'DROP SCHEMA {NS}; DROP ROLE {G}; DROP ROLE {C}; DROP ROLE {B}; DROP ROLE {A};')
    expect(inventory(), before, 'BOUNDED_RESIDUAL')
    expect(runtime_preimage(), canonical_before, 'CANONICAL_RUNTIME_PREIMAGE')
    print('STEP6R3_TEARDOWN ZERO_RESIDUAL_BOUNDED / CANONICAL_RUNTIME_PREIMAGE_UNCHANGED')


if __name__ == '__main__': main()
