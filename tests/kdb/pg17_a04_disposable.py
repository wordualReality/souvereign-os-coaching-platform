"""A04 disposable-only Docker oracle; no remote connection or customer data."""
import json
import hashlib
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
        psql("kdb_a04_disposable", """
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
        print("PASS_DISPOSABLE_PG17_A04_SCOPED: TX_ABORT_SNAPSHOT TABLES_12 FORCE_RLS OWNER RUNTIME_DENIED LEGACY_FIXTURE_POSTCOMMIT DIGEST_VECTOR REAPPLY_DENIED")
        print("POSTCOMMIT_SCOPED_SNAPSHOT_EQUAL=" + str(recovered == baseline).upper())
        print("OPEN: complete raw-ACL parity, verified backup/postcommit restore, other creators, signed PIAC, authoritative target and live grants")
    finally:
        if container:
            invoke("docker", "rm", "-f", container, check=False)

if __name__ == "__main__":
    main()
