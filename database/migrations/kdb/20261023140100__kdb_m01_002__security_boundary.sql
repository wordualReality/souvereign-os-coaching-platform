-- KDB-M01 / READ-REVIEWED CANDIDATE. NO APPLY BEFORE MUTATION-GATE-A.
-- Roles need CREATEROLE/grantor proofs before applying; do NOT fall back to service_role.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE ROLE kdb_schema_owner NOLOGIN NOBYPASSRLS;
CREATE ROLE kdb_command_owner NOLOGIN NOBYPASSRLS;
CREATE ROLE kdb_ingest_runtime LOGIN NOBYPASSRLS NOINHERIT;
-- No password assigned by SQL: 1Password C3/provisioner gate required before external use.
GRANT USAGE, CREATE ON SCHEMA kdb_canonical, kdb_governance, kdb_staging, kdb_ops TO kdb_schema_owner;
GRANT USAGE ON SCHEMA kdb_governance, kdb_staging, kdb_ops TO kdb_command_owner;
GRANT CREATE ON SCHEMA kdb_ops TO kdb_command_owner; -- NOLOGIN function owner only
GRANT USAGE ON SCHEMA kdb_ops TO kdb_ingest_runtime;
GRANT SELECT, INSERT ON kdb_governance.source, kdb_governance.source_version TO kdb_command_owner;
GRANT SELECT, INSERT ON kdb_staging.submission, kdb_staging.candidate_revision, kdb_staging.review_work_item TO kdb_command_owner;
GRANT SELECT, INSERT ON kdb_ops.command_receipt, kdb_ops.audit_event, kdb_ops.outbox_event TO kdb_command_owner;
-- These are deliberately absent for ALL KDB-M01 operational roles:
-- NO GRANTS on kdb_canonical.protocol, protocol_version, lifecycle_event.
-- NO grants on human_review_decision to n8n or kdb_command_owner.
-- No grants at all to anon, authenticated, service_role, PUBLIC.
-- The command owner is NOT the table owner and has NOBYPASSRLS.
DO $kdb$ DECLARE rec record; BEGIN
  FOR rec IN SELECT schemaname,tablename FROM pg_tables WHERE (schemaname='kdb_governance' AND tablename IN ('source','source_version')) OR (schemaname='kdb_staging' AND tablename IN ('submission','candidate_revision','review_work_item')) OR (schemaname='kdb_ops' AND tablename IN ('command_receipt','audit_event','outbox_event')) LOOP
    EXECUTE format('CREATE POLICY command_owner_select ON %I.%I AS PERMISSIVE FOR SELECT TO kdb_command_owner USING (tenant_scope = current_setting(''kdb.tenant_scope'', true))',rec.schemaname,rec.tablename);
    EXECUTE format('CREATE POLICY command_owner_insert ON %I.%I AS PERMISSIVE FOR INSERT TO kdb_command_owner WITH CHECK (tenant_scope = current_setting(''kdb.tenant_scope'', true))',rec.schemaname,rec.tablename);
  END LOOP;
END $kdb$;
-- Dedicated NOLOGIN schema owner; FORCE-RLS remains enabled even for table owner.
DO $own$ DECLARE rec record; BEGIN
  FOR rec IN SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') LOOP
    EXECUTE format('ALTER TABLE %I.%I OWNER TO kdb_schema_owner', rec.schemaname, rec.tablename);
  END LOOP;
END $own$;
ALTER SCHEMA kdb_canonical OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_staging OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_governance OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_ops OWNER TO kdb_schema_owner;
-- No default EXECUTE privilege: functions require explicit name-specific grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_ops REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
COMMIT;
