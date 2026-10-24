-- KDB-M01-BETA / read-only catalog and rollback preimage. PostgreSQL 17.
-- MANUAL TARGET GUARD: execute only on confirmed sovereign-os-kdb-dev (ujdzahwlximlmndexgmx).
-- Never use zobjpmyccszkabybdmsf or SOV dev wixdcaqdwmpccbfmxyea.
-- This is INSPECTION, not a repair or apply. No secrets, row data, or auth/session query text.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';
SELECT current_database() database_name,current_user effective_catalog_principal,
       current_setting('server_version') server_version,
       current_setting('transaction_read_only') read_only_flag;
SELECT n.nspname,pg_get_userbyid(n.nspowner) schema_owner,n.nspacl::text schema_acl
FROM pg_namespace n
WHERE n.nspname IN ('canonical','dev_staging','kdb_canonical','kdb_staging','kdb_governance','kdb_ops','kdb_api','kdb_audit') ORDER BY 1;
SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner) table_owner,
 c.relrowsecurity rls,c.relforcerowsecurity force_rls,c.relacl::text relation_acl
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('canonical','dev_staging','kdb_canonical','kdb_staging','kdb_governance','kdb_ops','kdb_api','kdb_audit')
AND c.relkind IN ('r','p','v') ORDER BY 1,2;
SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) args,
 pg_get_userbyid(p.proowner) function_owner,p.prosecdef security_definer,
 p.proconfig settings,p.proacl::text function_acl
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname IN ('canonical','dev_staging','kdb_canonical','kdb_staging','kdb_governance','kdb_ops','kdb_api','kdb_audit') ORDER BY 1,2;
SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies
WHERE schemaname IN ('canonical','dev_staging','kdb_canonical','kdb_staging','kdb_governance','kdb_ops','kdb_api','kdb_audit') ORDER BY 1,2,3;
SELECT rolname,rolcanlogin,rolbypassrls,rolcreaterole,rolsuper,rolinherit FROM pg_roles
WHERE rolname LIKE 'kdb\_%' ESCAPE '\' ORDER BY 1;
SELECT defaclrole::regrole,defaclnamespace::regnamespace,defaclobjtype,defaclacl::text
FROM pg_default_acl WHERE defaclrole IN (SELECT oid FROM pg_roles WHERE rolname LIKE 'kdb\_%' ESCAPE '\') ORDER BY 1,2;
SELECT version,name FROM supabase_migrations.schema_migrations ORDER BY version;
-- The remaining one-row table has ONLY protocol_id per the live catalog. Its provenance is UNPROVEN.
-- NO delete, update, data export, migration history reset or DROP based on this count.
SELECT count(*) AS legacy_protocol_rows FROM canonical.protocol;
SELECT count(*) AS nonself_active_or_lockwait_sessions FROM pg_stat_activity
WHERE datname=current_database() AND pid<>pg_backend_pid() AND (state='active' OR wait_event_type='Lock');
COMMIT;
