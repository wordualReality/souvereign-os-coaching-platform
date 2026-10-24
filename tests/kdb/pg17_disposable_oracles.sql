-- Local disposable catalog assertions. PostgreSQL 17 only.
\set ON_ERROR_STOP on
DO $$
DECLARE
  n int;
  rec record;
BEGIN
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') AND c.relkind='r';
  IF n <> 12 THEN RAISE EXCEPTION 'expected 12 tables, got %', n; END IF;

  FOR rec IN
    SELECT ns.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner) AS owner
    FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') AND c.relkind='r'
  LOOP
    IF rec.relrowsecurity IS NOT TRUE OR rec.relforcerowsecurity IS NOT TRUE THEN
      RAISE EXCEPTION 'FORCE RLS missing on %.%', rec.nspname, rec.relname;
    END IF;
    IF rec.owner <> 'kdb_schema_owner' THEN
      RAISE EXCEPTION 'owner mismatch on %.% = %', rec.nspname, rec.relname, rec.owner;
    END IF;
  END LOOP;

  SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
    WHERE ns.nspname='kdb_ops' AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff');
  IF n <> 3 THEN RAISE EXCEPTION 'expected 3 command functions, got %', n; END IF;

  FOR rec IN
    SELECT p.proname, p.prosecdef, pg_get_userbyid(p.proowner) AS owner, p.proconfig
    FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
    WHERE ns.nspname='kdb_ops' AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff')
  LOOP
    IF rec.prosecdef IS NOT TRUE THEN RAISE EXCEPTION '% not SECURITY DEFINER', rec.proname; END IF;
    IF rec.owner <> 'kdb_command_owner' THEN RAISE EXCEPTION '% owner %', rec.proname, rec.owner; END IF;
    IF rec.proconfig IS NULL OR NOT ('search_path=pg_catalog' = ANY(rec.proconfig)) THEN
      RAISE EXCEPTION '% search_path not pg_catalog: %', rec.proname, rec.proconfig;
    END IF;
  END LOOP;

  IF has_function_privilege('anon','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE') THEN
    RAISE EXCEPTION 'anon EXECUTE ingest_source';
  END IF;
  IF has_function_privilege('authenticated','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE') THEN
    RAISE EXCEPTION 'authenticated EXECUTE ingest_source';
  END IF;
  IF has_function_privilege('service_role','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE') THEN
    RAISE EXCEPTION 'service_role EXECUTE ingest_source';
  END IF;
  IF has_function_privilege('kdb_ingest_runtime','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE') THEN
    RAISE EXCEPTION 'runtime still has EXECUTE ingest_source';
  END IF;
  IF has_table_privilege('kdb_ingest_runtime','kdb_canonical.protocol_version','SELECT') THEN
    RAISE EXCEPTION 'runtime SELECT protocol_version';
  END IF;
  IF has_table_privilege('kdb_command_owner','kdb_governance.human_review_decision','INSERT') THEN
    RAISE EXCEPTION 'command_owner INSERT human_review_decision';
  END IF;

  PERFORM 1 FROM pg_roles WHERE rolname='kdb_schema_owner' AND rolcanlogin IS FALSE AND rolbypassrls IS FALSE AND rolsuper IS FALSE;
  IF NOT FOUND THEN RAISE EXCEPTION 'kdb_schema_owner graph'; END IF;
  PERFORM 1 FROM pg_roles WHERE rolname='kdb_command_owner' AND rolcanlogin IS FALSE AND rolbypassrls IS FALSE AND rolsuper IS FALSE;
  IF NOT FOUND THEN RAISE EXCEPTION 'kdb_command_owner graph'; END IF;
  PERFORM 1 FROM pg_roles WHERE rolname='kdb_ingest_runtime' AND rolcanlogin IS TRUE AND rolbypassrls IS FALSE AND rolsuper IS FALSE AND rolcreaterole IS FALSE AND rolcreatedb IS FALSE AND rolinherit IS FALSE;
  IF NOT FOUND THEN RAISE EXCEPTION 'kdb_ingest_runtime graph'; END IF;
  PERFORM 1 FROM pg_roles WHERE rolname='kdb_migrator' AND rolcanlogin IS FALSE AND rolbypassrls IS FALSE AND rolsuper IS FALSE AND rolinherit IS FALSE;
  IF NOT FOUND THEN RAISE EXCEPTION 'kdb_migrator graph'; END IF;
  IF kdb_ops.security_context_ready() IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'security_context_ready must be false';
  END IF;
END $$;

SELECT 'PASS_PG17_ORACLES' AS status;
