"""A04 disposable-only Docker oracle; no remote connection or customer data."""
import json
import hashlib
import copy
import os
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "database/migrations/kdb/candidates/202611070001__a04_disposable_recovery_candidate.sql"
FIXTURE = ROOT / "tests/kdb/fixtures/a04_synthetic_preimage_v1.json"
EXPORT = ROOT / "tests/kdb/fixtures/a04_catalog_export_disposable.v1.sql"

def main():
    manifest = json.loads((ROOT / "docs/kdb/m01/a04_disposable_candidate.v1.json").read_text())
    for pin in [*manifest["sql_steps"], *manifest["derivative_sources"], manifest["derived_from"], manifest["synthetic_fixture"], manifest["catalog_exporter"], manifest["exported_synthetic_fixture"]]:
        path = (ROOT / pin.get("file", pin.get("path", ""))).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise RuntimeError("MANIFEST_SOURCE_HASH_MISMATCH")
    name = "kdb-a04-disposable-" + uuid.uuid4().hex[:12]
    container = None
    def invoke(*args, input=None, check=True):
        return subprocess.run(args, input=input, text=True, capture_output=True, check=check)
    def psql(db, sql, check=True):
        return invoke("docker", "exec", "-i", container, "psql", "-U", "postgres", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", db, input=sql, check=check)
    try:
        container = invoke("docker", "run", "-d", "--network", "none", "--name", name, "-e", "POSTGRES_PASSWORD=kdb_disposable_only", "postgres:17").stdout.strip()
        if len(container) != 64 or not all(c in "0123456789abcdef" for c in container):
            raise RuntimeError("DOCKER_CONTAINER_ID_INVALID")
        network = invoke("docker", "inspect", "-f", "{{.HostConfig.NetworkMode}}", container).stdout.strip()
        if network != "none":
            raise RuntimeError("DISPOSABLE_NETWORK_GUARD_FAILED")
        for _ in range(40):
            ready = invoke("docker", "exec", container, "pg_isready", "-U", "postgres", check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("DISPOSABLE_POSTGRES_NOT_READY")
        for _ in range(20):
            created = invoke("docker","exec",container,"createdb","-U","postgres","kdb_a04_wrong_extension",check=False)
            if created.returncode == 0:
                break
            if "already exists" in created.stderr:
                break
            if not any(s in created.stderr for s in ("starting up", "connection", "Connection", "shutting down")):
                raise RuntimeError("DISPOSABLE_CREATEDB_FAILED: " + created.stderr.strip())
            time.sleep(0.5)
        else:
            raise RuntimeError("DISPOSABLE_CREATEDB_TIMEOUT")
        bad_setup = psql("kdb_a04_wrong_extension", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + SQL.read_text(), check=False)
        if bad_setup.returncode == 0 or "A04_DISPOSABLE_GUARD_REQUIRED" not in bad_setup.stderr:
            raise AssertionError("WRONG_DATABASE_NOT_DENIED")
        invoke("docker","exec",container,"createdb","-U","postgres","kdb_a04_disposable")
        candidate = SQL.read_text()
        for setup_extension in ("", "CREATE EXTENSION pgcrypto WITH SCHEMA public;"):
            if setup_extension:
                psql("kdb_a04_disposable", setup_extension)
            invalid_ext = psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + candidate, check=False)
            if invalid_ext.returncode == 0 or "A04_PGCRYPTO_NAMESPACE_MISMATCH" not in invalid_ext.stderr:
                raise AssertionError("WRONG_EXTENSION_NOT_DENIED")
        psql("kdb_a04_disposable", "DROP EXTENSION pgcrypto;")
        data = json.loads(FIXTURE.read_text())
        ledger = ",".join("('%s','%s',%d,'%s')" % (v["version"],v["name"],v["octets"],v["md5"]) for v in data["ledger"])
        setup = """CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN;
        CREATE ROLE kdb_runtime NOLOGIN NOINHERIT NOBYPASSRLS;
        CREATE ROLE kdb_ingest_writer NOLOGIN NOINHERIT NOBYPASSRLS;
        CREATE ROLE kdb_reviewer NOLOGIN NOINHERIT NOBYPASSRLS;
        GRANT kdb_runtime TO postgres WITH ADMIN TRUE, INHERIT FALSE, SET FALSE;
        GRANT kdb_ingest_writer TO postgres WITH ADMIN TRUE, INHERIT FALSE, SET FALSE;
        GRANT kdb_reviewer TO postgres WITH ADMIN TRUE, INHERIT FALSE, SET FALSE;
        CREATE SCHEMA extensions; CREATE EXTENSION pgcrypto WITH SCHEMA extensions;
        REVOKE EXECUTE ON FUNCTION extensions.digest(bytea,text) FROM PUBLIC;
        CREATE FUNCTION public.digest(bytea,text) RETURNS bytea LANGUAGE sql AS 'SELECT decode(repeat(''00'',32),''hex'')';
        CREATE SCHEMA canonical; CREATE TABLE canonical.protocol(id integer);
        INSERT INTO canonical.protocol VALUES (1); ALTER TABLE canonical.protocol ENABLE ROW LEVEL SECURITY;
        CREATE SCHEMA dev_staging; CREATE SCHEMA kdb_api; CREATE SCHEMA kdb_audit;
        CREATE SCHEMA synthetic_migration_registry;
        CREATE TABLE synthetic_migration_registry.ledger(version text,name text,octets integer,md5 text);
        INSERT INTO synthetic_migration_registry.ledger VALUES """ + ledger + ";"
        psql("kdb_a04_disposable", setup)
        exported = json.loads(psql("kdb_a04_disposable", EXPORT.read_text()).stdout)
        if os.environ.get("KDB_A04_PRINT_SYNTHETIC_EXPORT") == "1":
            print("SYNTHETIC_EXPORT_JSON=" + json.dumps(exported, sort_keys=True, separators=(",",":")))
        expected_export_keys = {"version","binding","ledger","protocol_count","protocol_provenance","schemas","relations","policies","roles","memberships","default_function_acl","functions","pgcrypto","admission"}
        if set(exported) != expected_export_keys or exported["protocol_count"] != 1 or exported["ledger"] != data["ledger"] or exported["admission"] != "NOT_AUTHORIZED":
            raise AssertionError("SYNTHETIC_EXPORT_INVENTORY_MISMATCH")
        if len(exported["roles"]) != 3 or len(exported["memberships"]) != 3 or exported["pgcrypto"]["namespace"] != "extensions":
            raise AssertionError("SYNTHETIC_EXPORT_ROLE_OR_EXTENSION_MISMATCH")
        from hosted_recovery_preflight_diff import analyze
        if analyze(json.dumps(exported))["status"] != "SYNTHETIC_PREIMAGE_MATCH":
            raise AssertionError("SYNTHETIC_RAW_EXPORT_MISMATCH")
        injected_sql = "BEGIN; CREATE TABLE kdb_api.evil(id integer); CREATE FUNCTION kdb_api.evil() RETURNS integer LANGUAGE sql AS 'SELECT 1';\n" + EXPORT.read_text() + "\nROLLBACK;"
        injected = json.loads(psql("kdb_a04_disposable", injected_sql).stdout)
        if not any(r["name"] == "evil" for r in injected["relations"]) or not any("evil()" in f["signature"] for f in injected["functions"]):
            raise AssertionError("SYNTHETIC_EXPORT_MISSED_EXTRA_OBJECT")
        injected_function = next(f for f in injected["functions"] if "evil()" in f["signature"])
        if not any(a["grantee"] == "PUBLIC" and a["privilege"] == "EXECUTE" for a in injected_function["acl"]) or injected_function["effective_visibility"]["PUBLIC"]:
            raise AssertionError("MASKED_PUBLIC_EXECUTE_NOT_CHARACTERIZED")
        if analyze(json.dumps(injected))["status"] != "DRIFT":
            raise AssertionError("SYNTHETIC_EXPORT_DRIFT_NOT_DENIED")
        # Deliberately construct the unsafe synthetic preimage to test rejection.
        psql("kdb_a04_disposable", "GRANT EXECUTE ON FUNCTION extensions.digest(bytea,text) TO PUBLIC;")
        public_digest = psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + candidate, check=False)
        if public_digest.returncode == 0 or "A04_PGCRYPTO_PUBLIC_EXECUTE" not in public_digest.stderr:
            raise AssertionError("PUBLIC_DIGEST_NOT_DENIED")
        psql("kdb_a04_disposable", "REVOKE EXECUTE ON FUNCTION extensions.digest(bytea,text) FROM PUBLIC;")
        snapshot_query = """
        SELECT jsonb_build_object(
          'roles',(SELECT coalesce(jsonb_agg(rolname ORDER BY rolname),'[]'::jsonb) FROM pg_roles WHERE rolname LIKE 'kdb_%'),
          'schemas',(SELECT coalesce(jsonb_agg(nspname ORDER BY nspname),'[]'::jsonb) FROM pg_namespace WHERE nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops')),
          'ledger',(SELECT jsonb_agg(to_jsonb(l) ORDER BY version) FROM synthetic_migration_registry.ledger l),
          'protocol_count',(SELECT count(*) FROM canonical.protocol),
          'default_acl',(SELECT coalesce(jsonb_agg(to_jsonb(d) ORDER BY d.oid),'[]'::jsonb) FROM pg_default_acl d),
          'digest_acl',(SELECT coalesce(proacl::text,'NULL') FROM pg_proc WHERE oid='extensions.digest(bytea,text)'::regprocedure)
        )::text;
        """
        before = psql("kdb_a04_disposable", snapshot_query).stdout.strip()
        if candidate.count("COMMIT;") != 1:
            raise AssertionError("UNEXPECTED_TRANSACTION_BOUNDARY")
        aborted = candidate.replace("COMMIT;", "ROLLBACK;")
        psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + aborted)
        after_abort = psql("kdb_a04_disposable", snapshot_query).stdout.strip()
        if before != after_abort:
            raise AssertionError("TRANSACTIONAL_PREIMAGE_MISMATCH")
        denied = psql("kdb_a04_disposable", candidate, check=False)
        if denied.returncode == 0 or "A04_DISPOSABLE_GUARD_REQUIRED" not in denied.stderr:
            raise AssertionError("MISSING_GUARD_NOT_DENIED")
        psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + candidate)
        for pin in manifest["sql_steps"][1:]:
            derivative = (ROOT / pin["file"]).read_text()
            if "public.digest(" in derivative or "extensions.digest(" not in derivative:
                raise AssertionError("DIGEST_NAMESPACE_DERIVATIVE_MISMATCH")
            psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + derivative)
            exposure = psql("kdb_a04_disposable", """
              SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
              WHERE n.nspname='kdb_ops' AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff')
              AND (has_function_privilege('public',p.oid,'EXECUTE')
                OR has_function_privilege('anon',p.oid,'EXECUTE')
                OR has_function_privilege('authenticated',p.oid,'EXECUTE')
                OR has_function_privilege('service_role',p.oid,'EXECUTE')
                OR has_function_privilege('kdb_ingest_runtime',p.oid,'EXECUTE'));
            """).stdout.strip()
            if exposure != "0":
                raise AssertionError("INTERMEDIATE_COMMAND_EXECUTE_REACHABLE")
        assertions = """
        DO $check$ DECLARE n int; BEGIN
          SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.relowner
          WHERE s.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') AND c.relkind='r'
            AND c.relrowsecurity AND c.relforcerowsecurity AND r.rolname='kdb_schema_owner';
          IF n <> 12 THEN RAISE EXCEPTION 'TABLE_OWNER_RLS_MISMATCH'; END IF;
          IF (SELECT count(*) FROM canonical.protocol) <> 1 OR (SELECT count(*) FROM synthetic_migration_registry.ledger) <> 6 THEN RAISE EXCEPTION 'LEGACY_FIXTURE_CHANGED'; END IF;
          IF has_function_privilege('public','kdb_ops.a04_canonical_digest_v2(jsonb)','EXECUTE') OR has_function_privilege('kdb_ingest_runtime','kdb_ops.a04_canonical_digest_v2(jsonb)','EXECUTE') THEN RAISE EXCEPTION 'RUNTIME_EXECUTE_REACHABLE'; END IF;
          SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
            WHERE ns.nspname='kdb_ops' AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff')
              AND p.prosecdef AND p.proconfig @> ARRAY['search_path=pg_catalog']
              AND NOT has_function_privilege('public',p.oid,'EXECUTE')
              AND NOT has_function_privilege('anon',p.oid,'EXECUTE')
              AND NOT has_function_privilege('authenticated',p.oid,'EXECUTE')
              AND NOT has_function_privilege('service_role',p.oid,'EXECUTE')
              AND NOT has_function_privilege('kdb_ingest_runtime',p.oid,'EXECUTE');
          IF n <> 3 THEN RAISE EXCEPTION 'COMMAND_ACL_OR_SEARCH_PATH_MISMATCH'; END IF;
          IF kdb_ops.security_context_ready() IS DISTINCT FROM false THEN RAISE EXCEPTION 'PIAC_GUARD_NOT_FAIL_CLOSED'; END IF;
          IF kdb_ops.canonical_digest_v2('["v2",null]'::jsonb)=kdb_ops.canonical_digest_v2('["v2",""]'::jsonb)
          OR kdb_ops.canonical_digest_v2('["v2","a|b"]'::jsonb)=kdb_ops.canonical_digest_v2('["v2","a","b"]'::jsonb)
          THEN RAISE EXCEPTION 'P4_DIGEST_AMBIGUOUS'; END IF;
          IF kdb_ops.a04_canonical_digest_v2('["v2",null]'::jsonb)=kdb_ops.a04_canonical_digest_v2('["v2",""]'::jsonb)
          OR kdb_ops.a04_canonical_digest_v2('["v2","a|b"]'::jsonb)=kdb_ops.a04_canonical_digest_v2('["v2","a","b"]'::jsonb) THEN RAISE EXCEPTION 'DIGEST_AMBIGUOUS'; END IF;
          IF kdb_ops.a04_canonical_digest_v2('["v2","café"]'::jsonb) <> encode(extensions.digest(convert_to(('["v2","café"]'::jsonb)::text,'UTF8'),'sha256'),'hex') THEN RAISE EXCEPTION 'DIGEST_SHADOW_OR_UTF8_MISMATCH'; END IF;
          IF encode(extensions.digest(convert_to('abc','UTF8'),'sha256'),'hex') <> 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad' THEN RAISE EXCEPTION 'DIGEST_VECTOR_MISMATCH'; END IF;
          IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid WHERE r.rolname IN ('kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime')) THEN RAISE EXCEPTION 'UNEXPECTED_ROLE_MEMBERSHIP'; END IF;
        END $check$;
        """
        psql("kdb_a04_disposable", assertions)
        after_commit_ledger = psql("kdb_a04_disposable", "SELECT jsonb_agg(to_jsonb(l) ORDER BY version)::text FROM synthetic_migration_registry.ledger l;").stdout.strip()
        if json.loads(after_commit_ledger) != json.loads(before)["ledger"]:
            raise AssertionError("LEGACY_LEDGER_CHANGED")
        duplicate = psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + candidate, check=False)
        if duplicate.returncode == 0 or "A04_EXISTING_ROLE_RECONCILIATION_REQUIRED" not in duplicate.stderr:
            raise AssertionError("EXISTING_ROLE_NOT_DENIED")
        # SET ROLE from postgres alone retains superuser session_user authority.
        # SESSION AUTHORIZATION is a local simulation, not a real login proof.
        role_switch = psql("kdb_a04_disposable", "SET SESSION AUTHORIZATION kdb_ingest_runtime; SET ROLE kdb_schema_owner;", check=False)
        if role_switch.returncode == 0 or "permission denied to set role" not in role_switch.stderr:
            raise AssertionError("UNTRUSTED_ROLE_SWITCH_ALLOWED")
        runtime_call = psql("kdb_a04_disposable", "SET SESSION AUTHORIZATION kdb_ingest_runtime; SELECT kdb_ops.request_review_handoff(NULL::uuid,NULL::text,NULL::uuid,NULL::text,NULL::text,NULL::text,NULL::uuid);", check=False)
        if runtime_call.returncode == 0 or "permission denied" not in runtime_call.stderr:
            raise AssertionError("UNTRUSTED_COMMAND_NOT_DENIED")
        psql("kdb_a04_disposable", """
        CREATE ROLE a04_transfer_runner NOLOGIN NOINHERIT;
        CREATE SCHEMA synthetic_transfer AUTHORIZATION a04_transfer_runner;
        SET ROLE a04_transfer_runner;
        CREATE FUNCTION synthetic_transfer.probe() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        RESET ROLE;
        GRANT kdb_command_owner TO a04_transfer_runner WITH INHERIT FALSE, SET FALSE;
        """)
        blocked_transfer = psql("kdb_a04_disposable", "\\set VERBOSITY verbose\nSET SESSION AUTHORIZATION a04_transfer_runner; ALTER FUNCTION synthetic_transfer.probe() OWNER TO kdb_command_owner;", check=False)
        if blocked_transfer.returncode == 0 or "42501" not in blocked_transfer.stderr:
            raise AssertionError("SET_FALSE_TRANSFER_NOT_DENIED: " + blocked_transfer.stderr.strip())
        psql("kdb_a04_disposable", "GRANT kdb_command_owner TO a04_transfer_runner WITH INHERIT FALSE, SET TRUE;")
        exposed = psql("kdb_a04_disposable", "SET SESSION AUTHORIZATION a04_transfer_runner; SET ROLE kdb_command_owner; SELECT current_user;").stdout.strip()
        if exposed != "kdb_command_owner":
            raise AssertionError("SET_TRUE_ROLE_EXPOSURE_NOT_OBSERVED")
        psql("kdb_a04_disposable", "REVOKE kdb_command_owner FROM a04_transfer_runner; DROP SCHEMA synthetic_transfer CASCADE; DROP OWNED BY a04_transfer_runner; DROP ROLE a04_transfer_runner;")
        psql("kdb_a04_disposable", """
        CREATE ROLE a04_other_creator NOLOGIN;
        CREATE SCHEMA synthetic_other_creator;
        GRANT USAGE,CREATE ON SCHEMA synthetic_other_creator TO a04_other_creator;
        SET ROLE a04_other_creator;
        CREATE FUNCTION synthetic_other_creator.f() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        RESET ROLE;
        DO $check$ BEGIN
          IF NOT has_function_privilege('public','synthetic_other_creator.f()','EXECUTE')
          THEN RAISE EXCEPTION 'OTHER_CREATOR_CHARACTERIZATION_UNEXPECTED'; END IF;
        END $check$;
        """)
        # Defaults belong to the effective creator, not to the eventual owner.
        # Scope grants only to this synthetic laboratory and remove it below.
        psql("kdb_a04_disposable", """
        CREATE ROLE a04_acl_reader NOLOGIN;
        CREATE SCHEMA a04_acl_lab;
        GRANT USAGE,CREATE ON SCHEMA a04_acl_lab TO kdb_migrator,kdb_schema_owner,kdb_command_owner,a04_other_creator;
        CREATE FUNCTION a04_acl_lab.created_by_postgres() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        SET ROLE kdb_migrator;
        CREATE FUNCTION a04_acl_lab.created_by_migrator() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        RESET ROLE;
        SET ROLE kdb_schema_owner;
        CREATE FUNCTION a04_acl_lab.created_by_schema_owner() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        RESET ROLE;
        SET ROLE kdb_command_owner;
        CREATE FUNCTION a04_acl_lab.created_by_command_owner() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        RESET ROLE;
        SET ROLE a04_other_creator;
        CREATE FUNCTION a04_acl_lab.created_by_other() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        CREATE FUNCTION a04_acl_lab.raw_null() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        CREATE FUNCTION a04_acl_lab.named_grant() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        GRANT EXECUTE ON FUNCTION a04_acl_lab.named_grant() TO a04_acl_reader WITH GRANT OPTION;
        CREATE TABLE a04_acl_lab.raw_table(id integer);
        GRANT SELECT ON TABLE a04_acl_lab.raw_table TO a04_acl_reader WITH GRANT OPTION;
        RESET ROLE;
        GRANT a04_acl_reader TO a04_other_creator WITH INHERIT FALSE, SET FALSE;
        """)
        creator_matrix = json.loads(psql("kdb_a04_disposable", """
        SELECT jsonb_object_agg(p.proname,jsonb_build_object(
          'creator',pg_get_userbyid(p.proowner),
          'public_execute',has_function_privilege('public',p.oid,'EXECUTE'),
          'public_visible',has_schema_privilege('public',n.oid,'USAGE') AND has_function_privilege('public',p.oid,'EXECUTE'),
          'raw_acl',p.proacl::text) ORDER BY p.proname)::text
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='a04_acl_lab';
        """).stdout)
        for item in ("created_by_postgres", "created_by_migrator"):
            if creator_matrix[item]["public_execute"]:
                raise AssertionError("CONFIGURED_CREATOR_PUBLIC_EXECUTE: " + item)
        for item in ("created_by_schema_owner", "created_by_command_owner", "created_by_other"):
            if not creator_matrix[item]["public_execute"]:
                raise AssertionError("UNCONFIGURED_CREATOR_EXPOSURE_NOT_OBSERVED: " + item)
            if creator_matrix[item]["public_visible"]:
                raise AssertionError("SYNTHETIC_LAB_SCHEMA_UNEXPECTEDLY_PUBLIC")
        if creator_matrix["raw_null"]["raw_acl"] is not None:
            raise AssertionError("NULL_ACL_PREIMAGE_NOT_OBSERVED")
        raw_snapshot_sql = """
        SELECT jsonb_build_object(
          'functions',(SELECT jsonb_agg(jsonb_build_object(
            'name',p.proname,'owner',pg_get_userbyid(p.proowner),'raw',p.proacl::text,
            'grants',coalesce((SELECT jsonb_agg(jsonb_build_object(
              'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
              'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
              FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a),'[]'::jsonb)
          ) ORDER BY p.proname) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='a04_acl_lab'),
          'tables',(SELECT jsonb_agg(jsonb_build_object(
            'name',c.relname,'owner',pg_get_userbyid(c.relowner),'raw',c.relacl::text,
            'grants',coalesce((SELECT jsonb_agg(jsonb_build_object(
              'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
              'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
              FROM aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a),'[]'::jsonb)
          ) ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='a04_acl_lab' AND c.relkind='r'),
          'schema_acl',(SELECT nspacl::text FROM pg_namespace WHERE nspname='a04_acl_lab'),
          'memberships',(SELECT coalesce(jsonb_agg(jsonb_build_object(
            'role',pg_get_userbyid(m.roleid),'member',pg_get_userbyid(m.member),
            'grantor',pg_get_userbyid(m.grantor),'admin',m.admin_option,'inherit',m.inherit_option,'set',m.set_option)
            ORDER BY m.roleid,m.member),'[]'::jsonb) FROM pg_auth_members m
            WHERE pg_get_userbyid(m.roleid)='a04_acl_reader'),
          'defaults',(SELECT coalesce(jsonb_agg(jsonb_build_object('creator',pg_get_userbyid(d.defaclrole),
            'schema',coalesce(n.nspname,'GLOBAL'),'kind',d.defaclobjtype::text,'raw',d.defaclacl::text)
            ORDER BY d.defaclrole,d.defaclnamespace,d.defaclobjtype),'[]'::jsonb)
            FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
            WHERE pg_get_userbyid(d.defaclrole) IN ('postgres','kdb_migrator','kdb_schema_owner','kdb_command_owner','a04_other_creator'))
        )::text;
        """
        raw_before = psql("kdb_a04_disposable", raw_snapshot_sql).stdout.strip()
        baseline_raw = json.loads(raw_before)
        named = next(row for row in baseline_raw["functions"] if row["name"] == "named_grant")
        if not any(g["grantor"] == "a04_other_creator" and g["grantee"] == "a04_acl_reader" and g["grantable"] and g["privilege"] == "EXECUTE" for g in named["grants"]):
            raise AssertionError("NAMED_GRANTOR_GRANT_OPTION_NOT_ESTABLISHED")
        if not any(g["grantor"] == "a04_other_creator" and g["grantee"] == "a04_acl_reader" and g["grantable"] and g["privilege"] == "SELECT" for g in baseline_raw["tables"][0]["grants"]):
            raise AssertionError("TABLE_GRANTOR_GRANT_OPTION_NOT_ESTABLISHED")
        psql("kdb_a04_disposable", """
        BEGIN;
        REVOKE EXECUTE ON FUNCTION a04_acl_lab.raw_null() FROM PUBLIC;
        REVOKE EXECUTE ON FUNCTION a04_acl_lab.named_grant() FROM a04_acl_reader CASCADE;
        REVOKE SELECT ON TABLE a04_acl_lab.raw_table FROM a04_acl_reader CASCADE;
        ALTER DEFAULT PRIVILEGES FOR ROLE a04_other_creator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
        REVOKE CREATE ON SCHEMA a04_acl_lab FROM kdb_command_owner;
        REVOKE a04_acl_reader FROM a04_other_creator;
        ROLLBACK;
        """)
        raw_after_abort = psql("kdb_a04_disposable", raw_snapshot_sql).stdout.strip()
        if raw_after_abort != raw_before:
            raise AssertionError("RAW_ACL_TRANSACTION_ROLLBACK_MISMATCH")
        psql("kdb_a04_disposable", """
        REVOKE EXECUTE ON FUNCTION a04_acl_lab.raw_null() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION a04_acl_lab.raw_null() TO PUBLIC;
        """)
        restored = json.loads(psql("kdb_a04_disposable", """
        SELECT jsonb_build_object('raw_is_null',proacl IS NULL,
          'public_execute',has_function_privilege('public',oid,'EXECUTE'))::text
        FROM pg_proc WHERE oid='a04_acl_lab.raw_null()'::regprocedure;
        """).stdout)
        if restored != {"raw_is_null": False, "public_execute": True}:
            raise AssertionError("POSTCOMMIT_NULL_ACL_COUNTEREXAMPLE_NOT_OBSERVED")
        print("CREATOR_MATRIX=" + json.dumps(creator_matrix, sort_keys=True))
        print("RAW_ACL_TX_ABORT_EXACT=PASS / POSTCOMMIT_EFFECTIVE_PUBLIC=TRUE / ORIGINAL_NULL_ACL_RESTORED=FALSE")
        psql("kdb_a04_disposable", """
        DROP SCHEMA a04_acl_lab CASCADE;
        REVOKE a04_acl_reader FROM a04_other_creator;
        DROP ROLE a04_acl_reader;
        DROP SCHEMA synthetic_other_creator CASCADE;
        DROP ROLE a04_other_creator;
        DROP SCHEMA kdb_canonical, kdb_staging, kdb_governance, kdb_ops CASCADE;
        DROP OWNED BY kdb_migrator;
        DROP ROLE kdb_migrator;
        DROP OWNED BY kdb_command_owner;
        DROP OWNED BY kdb_schema_owner;
        DROP OWNED BY kdb_ingest_runtime;
        DROP ROLE kdb_command_owner; DROP ROLE kdb_schema_owner; DROP ROLE kdb_ingest_runtime;
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
        """)
        recovered = json.loads(psql("kdb_a04_disposable", snapshot_query).stdout.strip())
        baseline = json.loads(before)
        if recovered["ledger"] != baseline["ledger"] or recovered["protocol_count"] != baseline["protocol_count"]:
            raise AssertionError("LEGACY_FIXTURE_POSTCOMMIT_RECOVERY_MISMATCH")
        # R1: one transaction composes immutable A04 steps and the additive
        # creator patch; no intermediate step is committed independently.
        r1_manifest = json.loads((ROOT / "docs/kdb/m01/a04_r1_creator_admission.v1.json").read_text())
        for pin in (r1_manifest["base_manifest"], r1_manifest["patch"], r1_manifest["catalog_query"], r1_manifest["synthetic_evidence"], r1_manifest["preflight"], r1_manifest["unit_tests"], r1_manifest["p3_precreated_derivative"]):
            path = (ROOT / pin["path"]).resolve()
            if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
                raise AssertionError("R1_MANIFEST_HASH_MISMATCH")
        patch_sql = (ROOT / r1_manifest["patch"]["path"]).read_text()
        query_sql = (ROOT / r1_manifest["catalog_query"]["path"]).read_text()
        if candidate.count("COMMIT;") != 1:
            raise AssertionError("R1_BASE_TRANSACTION_AMBIGUOUS")
        base_transaction = candidate.replace("COMMIT;", "")
        precreate = "CREATE ROLE kdb_migrator NOLOGIN NOBYPASSRLS NOSUPERUSER NOINHERIT;"
        # Independent oracle: fetch *all* pg_auth_members and walk both
        # endpoints in Python. It does not reuse the exporter recursive SQL.
        raw_graph = """SELECT coalesce(jsonb_agg(jsonb_build_object(
          'role',pg_get_userbyid(roleid),'member',pg_get_userbyid(member),
          'grantor',pg_get_userbyid(grantor),'admin',admin_option,
          'inherit',inherit_option,'set',set_option)),'[]'::jsonb)::text FROM pg_auth_members;"""
        seeds = {'postgres','kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime','kdb_migrator'}
        from a04_r1_creator_admission import evaluate
        reference_evidence = json.loads((ROOT / r1_manifest["synthetic_evidence"]["path"]).read_text())
        graph_cases = {
            'baseline': '',
            'roleid_set': 'CREATE ROLE graph_a; GRANT kdb_command_owner TO graph_a WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;',
            'roleid_inherit': 'CREATE ROLE graph_a; GRANT kdb_schema_owner TO graph_a WITH SET FALSE, INHERIT TRUE, ADMIN FALSE;',
            'roleid_admin': 'CREATE ROLE graph_a; GRANT kdb_ingest_runtime TO graph_a WITH SET FALSE, INHERIT FALSE, ADMIN TRUE;',
            'reverse_set': 'CREATE ROLE graph_a; GRANT graph_a TO kdb_command_owner WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;',
            'reverse_inherit': 'CREATE ROLE graph_a; GRANT graph_a TO kdb_schema_owner WITH SET FALSE, INHERIT TRUE, ADMIN FALSE;',
            'reverse_admin': 'CREATE ROLE graph_a; GRANT graph_a TO kdb_ingest_runtime WITH SET FALSE, INHERIT FALSE, ADMIN TRUE;',
            'transitive_parent': 'CREATE ROLE graph_a; CREATE ROLE graph_b; GRANT graph_b TO graph_a WITH SET TRUE, INHERIT TRUE, ADMIN TRUE; GRANT graph_a TO kdb_migrator WITH SET TRUE, INHERIT FALSE;',
            'transitive_inherit': 'CREATE ROLE graph_a; CREATE ROLE graph_b; GRANT graph_b TO graph_a WITH SET FALSE, INHERIT TRUE, ADMIN FALSE; GRANT graph_a TO kdb_migrator WITH SET FALSE, INHERIT TRUE;',
            'transitive_admin': 'CREATE ROLE graph_a; CREATE ROLE graph_b; GRANT graph_b TO graph_a WITH SET FALSE, INHERIT FALSE, ADMIN TRUE; GRANT graph_a TO kdb_migrator WITH SET FALSE, INHERIT FALSE, ADMIN TRUE;',
            'two_hop_descendant': 'CREATE ROLE graph_a; CREATE ROLE graph_b; GRANT kdb_command_owner TO graph_a; GRANT graph_a TO graph_b WITH SET TRUE, INHERIT TRUE, ADMIN TRUE;',
            'mixed_direction': 'CREATE ROLE graph_a; CREATE ROLE graph_b; GRANT graph_a TO kdb_migrator; GRANT graph_a TO graph_b WITH SET FALSE, INHERIT TRUE, ADMIN TRUE;',
        }
        for label, injection in graph_cases.items():
            prefix = "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + base_transaction + "\n" + precreate + "\n" + injection + "\n"
            output = psql("kdb_a04_disposable", prefix + query_sql + "\n" + raw_graph + "\nROLLBACK;").stdout.strip().splitlines()
            exported_graph = json.loads(output[-2])["membership_graph"]
            all_edges = json.loads(output[-1])
            reached = set(seeds)
            while True:
                expanded = reached | {e[k] for e in all_edges if e['role'] in reached or e['member'] in reached for k in ('role','member')}
                if expanded == reached:
                    break
                reached = expanded
            expected = sorted((e for e in all_edges if e['role'] in reached and e['member'] in reached),
                              key=lambda e:(e['role'],e['member'],e['grantor']))
            if exported_graph["edges"] != expected or exported_graph["seeds"] != sorted(seeds):
                raise AssertionError("R1_GRAPH_EXPORT_INCOMPLETE: " + label)
            if label != 'baseline':
                partial = copy.deepcopy(exported_graph)
                partial["edges"] = [edge for edge in partial["edges"] if not edge["role"].startswith("graph_") and not edge["member"].startswith("graph_")]
                if partial["edges"] == expected:
                    raise AssertionError("R1_GRAPH_PARTIAL_ORACLE_FAILED: " + label)
                changed = copy.deepcopy(reference_evidence)
                changed["membership_graph"] = exported_graph
                if evaluate(changed)["status"] != "BLOCKED_CREATOR_AUTHORITY":
                    raise AssertionError("R1_GRAPH_EVALUATOR_ACCEPTED: " + label)
            if label != 'baseline':
                denied = psql("kdb_a04_disposable", prefix + patch_sql + "\nROLLBACK;", check=False)
                if denied.returncode == 0 or 'BLOCKED_CREATOR_AUTHORITY' not in denied.stderr:
                    raise AssertionError("R1_GRAPH_GUARD_NOT_DENIED: " + label + " " + denied.stderr)
            print("R1_GRAPH_CASE " + label + " EXPORT_COMPLETE / " + ("BASELINE" if label == 'baseline' else "GUARD_DENIED"))
        for injection in (
            "CREATE ROLE a04_unknown NOLOGIN; GRANT CREATE ON SCHEMA kdb_ops TO a04_unknown;",
            "CREATE ROLE a04_unknown NOLOGIN; GRANT kdb_command_owner TO a04_unknown WITH SET TRUE, INHERIT FALSE;",
            "ALTER ROLE kdb_migrator SUPERUSER;",
            "DROP ROLE kdb_migrator;",
            "GRANT USAGE ON SCHEMA kdb_ops TO kdb_command_owner WITH GRANT OPTION;",
            "SET ROLE kdb_schema_owner;",
            "CREATE FUNCTION kdb_ops.extra() RETURNS integer LANGUAGE sql AS 'SELECT 1';",
            "DROP FUNCTION kdb_ops.a04_canonical_digest_v2(jsonb); GRANT CREATE ON SCHEMA kdb_ops TO kdb_command_owner; SET ROLE kdb_command_owner; CREATE FUNCTION kdb_ops.a04_canonical_digest_v2(jsonb) RETURNS text LANGUAGE sql AS 'SELECT ''synthetic''::text'; RESET ROLE; REVOKE CREATE ON SCHEMA kdb_ops FROM kdb_command_owner;",
        ):
            attempted = psql("kdb_a04_disposable", "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + base_transaction + "\n" + precreate + "\n" + injection + "\n" + patch_sql + "\nCOMMIT;", check=False)
            if attempted.returncode == 0 or "BLOCKED_CREATOR_AUTHORITY" not in attempted.stderr:
                raise AssertionError("R1_ADMISSION_INJECTION_NOT_DENIED: " + attempted.stderr.strip())
        pieces = []
        for pin in manifest["sql_steps"][1:]:
            source = r1_manifest["p3_precreated_derivative"]["path"] if pin["file"].endswith("202611070002__a04_p3_extensions_disposable.sql") else pin["file"]
            text = (ROOT / source).read_text()
            if text.count("BEGIN;") != 1 or text.count("COMMIT;") != 1:
                raise AssertionError("R1_DERIVATIVE_TRANSACTION_AMBIGUOUS")
            pieces.append(text.replace("BEGIN;", "", 1).replace("COMMIT;", "", 1))
        combined = "CREATE TEMP TABLE kdb_a04_disposable_guard(marker int);\n" + base_transaction + "\n" + precreate + "\n" + patch_sql + "\n" + "\n".join(pieces) + "\nCOMMIT;"
        if combined.count("COMMIT;") != 1:
            raise AssertionError("R1_COMBINED_TRANSACTION_AMBIGUOUS")
        psql("kdb_a04_disposable", combined.replace("COMMIT;", "ROLLBACK;"))
        if psql("kdb_a04_disposable", snapshot_query).stdout.strip() != before:
            raise AssertionError("R1_PRECOMMIT_SNAPSHOT_MISMATCH")
        psql("kdb_a04_disposable", combined)
        from a04_r1_creator_admission import evaluate, parse_and_evaluate
        evidence = json.loads(psql("kdb_a04_disposable", query_sql).stdout)
        if os.environ.get("KDB_A04_PRINT_SYNTHETIC_EXPORT") == "1":
            print("R1_SYNTHETIC_EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",",":")))
        if evidence != json.loads((ROOT / r1_manifest["synthetic_evidence"]["path"]).read_text()):
            raise AssertionError("R1_SYNTHETIC_EVIDENCE_FIXTURE_MISMATCH")
        admission = evaluate(evidence)
        if admission["status"] != "LOCAL_CREATOR_SAFE_FOR_DISPOSABLE" or admission["apply"] != "NOT_AUTHORIZED" or admission["postcommit_restore"] != "POSTCOMMIT_RESTORE_UNVERIFIED":
            raise AssertionError("R1_CREATOR_EVIDENCE_NOT_ADMITTED: " + json.dumps(evidence, sort_keys=True))
        mutations = []
        changed=copy.deepcopy(evidence); changed["schemas"][0]["creators"].append("unknown"); mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["schemas"][0]["acl_safe"]=False; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["schemas"][0]["acl_entries"][0]["grantor"]="forged"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["schemas"][0]["acl_entries"][0]["grantable"]=True; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["schemas"][0]["effective_usage"]["anon"]=True; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["creators"][0]["global_default_raw"]=None; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["creators"][0]["default_safe"]=False; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["session"]["current_user"]="kdb_schema_owner"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["membership_graph"]["edges"].append({"role":"kdb_schema_owner","member":"unknown","grantor":"postgres","admin":False,"inherit":False,"set":True}); mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"][0]["raw_acl"]=None; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"][0]["definition_sha256"]="0"*64; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"][0]["signature"]="forged()"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"][0]["acl_safe"]=False; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"][0]["acl_entries"][0]["grantor"]="forged"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["functions"].append(copy.deepcopy(changed["functions"][0])); mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["restore"]["backup"]="VERIFIED"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["binding"]["attestation"]="PROVIDER_VERIFIED"; mutations.append(changed)
        changed=copy.deepcopy(evidence); changed["source"]["patch_sha256"]="0"*64; mutations.append(changed)
        if any(evaluate(item)["status"] != "BLOCKED_CREATOR_AUTHORITY" for item in mutations):
            raise AssertionError("R1_FORGED_EVIDENCE_ACCEPTED")
        if parse_and_evaluate('{"version":"x","version":"y"}')["status"] != "BLOCKED_CREATOR_AUTHORITY":
            raise AssertionError("R1_DUPLICATE_KEY_ACCEPTED")
        psql("kdb_a04_disposable", "ALTER DEFAULT PRIVILEGES FOR ROLE kdb_command_owner GRANT EXECUTE ON FUNCTIONS TO PUBLIC;")
        if evaluate(json.loads(psql("kdb_a04_disposable", query_sql).stdout))["status"] != "BLOCKED_CREATOR_AUTHORITY":
            raise AssertionError("R1_MISSING_GLOBAL_DEFAULT_NOT_BLOCKED")
        psql("kdb_a04_disposable", "ALTER DEFAULT PRIVILEGES FOR ROLE kdb_command_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;")
        if evaluate(json.loads(psql("kdb_a04_disposable", query_sql).stdout))["status"] != "LOCAL_CREATOR_SAFE_FOR_DISPOSABLE":
            raise AssertionError("R1_RESTORED_GLOBAL_DEFAULT_NOT_RECOGNIZED")
        psql("kdb_a04_disposable", """
        CREATE ROLE a04_r1_unknown NOLOGIN NOINHERIT;
        CREATE SCHEMA a04_r1_lab;
        GRANT USAGE,CREATE ON SCHEMA a04_r1_lab TO kdb_migrator,kdb_schema_owner,kdb_command_owner,a04_r1_unknown;
        CREATE FUNCTION a04_r1_lab.by_postgres() RETURNS integer LANGUAGE sql AS 'SELECT 1';
        SET ROLE kdb_migrator; CREATE FUNCTION a04_r1_lab.by_migrator() RETURNS integer LANGUAGE sql AS 'SELECT 1'; RESET ROLE;
        SET ROLE kdb_schema_owner; CREATE FUNCTION a04_r1_lab.by_schema_owner() RETURNS integer LANGUAGE sql AS 'SELECT 1'; RESET ROLE;
        SET ROLE kdb_command_owner; CREATE FUNCTION a04_r1_lab.by_command_owner() RETURNS integer LANGUAGE sql AS 'SELECT 1'; RESET ROLE;
        SET ROLE a04_r1_unknown; CREATE FUNCTION a04_r1_lab.by_unknown() RETURNS integer LANGUAGE sql AS 'SELECT 1'; RESET ROLE;
        """)
        matrix = json.loads(psql("kdb_a04_disposable", """
        SELECT jsonb_object_agg(p.proname,has_function_privilege('public',p.oid,'EXECUTE'))::text
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='a04_r1_lab';
        """).stdout)
        if matrix != {"by_postgres":False,"by_migrator":False,"by_schema_owner":False,"by_command_owner":False,"by_unknown":True}:
            raise AssertionError("R1_CREATOR_MATRIX_MISMATCH: " + json.dumps(matrix))
        unknown_create = psql("kdb_a04_disposable", "SET SESSION AUTHORIZATION a04_r1_unknown; CREATE FUNCTION kdb_ops.forbidden() RETURNS integer LANGUAGE sql AS 'SELECT 1';", check=False)
        if unknown_create.returncode == 0 or "permission denied" not in unknown_create.stderr:
            raise AssertionError("R1_UNKNOWN_CREATOR_NOT_DENIED")
        psql("kdb_a04_disposable", "GRANT CREATE ON SCHEMA kdb_ops TO a04_r1_unknown;")
        if evaluate(json.loads(psql("kdb_a04_disposable", query_sql).stdout))["status"] != "BLOCKED_CREATOR_AUTHORITY":
            raise AssertionError("R1_ALTERNATE_CREATE_NOT_BLOCKED")
        psql("kdb_a04_disposable", "REVOKE CREATE ON SCHEMA kdb_ops FROM a04_r1_unknown;")
        print("R1_CREATOR_MATRIX=" + json.dumps(matrix, sort_keys=True))
        print("R1_ADMISSION=" + json.dumps(admission, sort_keys=True))
        print("R1_UNKNOWN_CREATE_DENIED / EXTRA_GRANT_DENIED / ROLE_SWITCH_AND_GRANTOR_DENIED")
        psql("kdb_a04_disposable", """
        DROP SCHEMA a04_r1_lab CASCADE; DROP OWNED BY a04_r1_unknown; DROP ROLE a04_r1_unknown;
        DROP SCHEMA kdb_canonical, kdb_staging, kdb_governance, kdb_ops CASCADE;
        DROP OWNED BY kdb_migrator; DROP ROLE kdb_migrator;
        DROP OWNED BY kdb_command_owner; DROP OWNED BY kdb_schema_owner; DROP OWNED BY kdb_ingest_runtime;
        DROP ROLE kdb_command_owner; DROP ROLE kdb_schema_owner; DROP ROLE kdb_ingest_runtime;
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
        """)
        if psql("kdb_a04_disposable", snapshot_query).stdout.strip() != before:
            raise AssertionError("R1_SCOPED_POSTCOMMIT_CLEANUP_MISMATCH")
        print("PASS_DISPOSABLE_PG17_A04_SCOPED: TX_ABORT_SNAPSHOT TABLES_12 FORCE_RLS OWNER RUNTIME_DENIED LEGACY_FIXTURE_POSTCOMMIT DIGEST_VECTOR REAPPLY_DENIED")
        print("POSTCOMMIT_SCOPED_SNAPSHOT_EQUAL=" + str(recovered == baseline).upper())
        print("OPEN: complete raw-ACL parity, verified backup/postcommit restore, other creators, signed PIAC, authoritative target and live grants")
    finally:
        if container:
            invoke("docker", "rm", "-f", container, check=False)

if __name__ == "__main__":
    main()
