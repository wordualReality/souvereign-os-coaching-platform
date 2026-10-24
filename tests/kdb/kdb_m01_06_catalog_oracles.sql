-- KDB-M01-06 catalog oracles. FUTURE isolated local PostgreSQL 17 only.
-- DO NOT EXECUTE IN P06. No psql. No Docker. No remote Supabase.
-- NOT_RUN_NOW against any database.

-- T01 / T04: twelve tables, owner, FORCE RLS
-- SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity,
--        pg_get_userbyid(c.relowner) AS relowner
-- FROM pg_class c
-- JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
--   AND c.relkind = 'r'
-- ORDER BY 1,2;

-- T05: three routines, SECURITY DEFINER, owner, ACL, search_path
-- SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS args,
--        p.prosecdef, p.proconfig, p.proacl, pg_get_userbyid(p.proowner) AS proowner
-- FROM pg_proc p
-- JOIN pg_namespace n ON n.oid = p.pronamespace
-- WHERE n.nspname = 'kdb_ops'
--   AND p.proname IN ('ingest_source','propose_candidate','request_review_handoff');

-- S01 roles
-- SELECT rolname, rolcanlogin, rolbypassrls, rolsuper, rolcreaterole, rolcreatedb, rolinherit
-- FROM pg_roles
-- WHERE rolname IN ('kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime');

-- T02 / T05 default ACL. Creator identity must be proven before treating this as PASS.
-- SELECT pg_get_userbyid(d.defaclrole) AS defaclrole, n.nspname, d.defaclobjtype, d.defaclacl
-- FROM pg_default_acl d
-- LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace;

-- T04 policies
-- SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check
-- FROM pg_policies
-- WHERE schemaname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops');

-- Effective privileges for intended and unintended roles. Do not execute in P06.
-- SELECT has_schema_privilege('anon','kdb_ops','USAGE');
-- SELECT has_table_privilege('anon','kdb_ops.command_receipt','SELECT');
-- SELECT has_function_privilege('anon','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE');
-- SELECT has_function_privilege('authenticated','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE');
-- SELECT has_function_privilege('service_role','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,uuid,timestamptz)','EXECUTE');
-- SELECT has_function_privilege('kdb_ingest_runtime','kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)','EXECUTE');
-- SELECT has_table_privilege('kdb_ingest_runtime','kdb_canonical.protocol_version','SELECT');
-- SELECT has_table_privilege('kdb_command_owner','kdb_governance.human_review_decision','INSERT');

-- Legacy checksum compare is a later isolated-test concern. Do not touch canonical/dev_staging/public here.
