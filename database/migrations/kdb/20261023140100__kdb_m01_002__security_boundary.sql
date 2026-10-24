-- KDB-M01 / READ-REVIEWED CANDIDATE. NO APPLY BEFORE MUTATION-GATE-A.
-- Roles need CREATEROLE/grantor proofs before applying; do NOT fall back to service_role.
-- P06 draft: explicit deny, named FORCE RLS, and BLOCK_DEFAULT_ACL_CREATOR. Not applied.
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
-- BLOCK_DEFAULT_ACL_CREATOR: the applying session user is not proven in this packet.
-- ALTER DEFAULT PRIVILEGES below binds only that unproven user in kdb_ops.
-- It is not proof against GLOBAL PUBLIC EXECUTE defaults or other creator roles.
-- Do not ALTER DEFAULT PRIVILEGES FOR ROLE postgres from this draft.
ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_ops REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE ALL ON SCHEMA kdb_canonical, kdb_staging, kdb_governance, kdb_ops FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL TABLES IN SCHEMA kdb_canonical FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA kdb_staging FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA kdb_governance FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA kdb_ops FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON TABLE kdb_governance.human_review_decision FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime, kdb_command_owner;
REVOKE ALL ON TABLE kdb_canonical.protocol FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime, kdb_command_owner;
REVOKE ALL ON TABLE kdb_canonical.protocol_version FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime, kdb_command_owner;
REVOKE ALL ON TABLE kdb_canonical.lifecycle_event FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime, kdb_command_owner;
-- Named ENABLE+FORCE RLS. Defense in depth. 001 already loops the same four schemas.
ALTER TABLE kdb_governance.source ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_governance.source FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_governance.source_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_governance.source_version FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.submission ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.submission FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.candidate_revision ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.candidate_revision FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.review_work_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_staging.review_work_item FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_governance.human_review_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_governance.human_review_decision FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.protocol ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.protocol FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.protocol_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.protocol_version FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.lifecycle_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_canonical.lifecycle_event FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.command_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.command_receipt FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.outbox_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.outbox_event FORCE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.audit_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE kdb_ops.audit_event FORCE ROW LEVEL SECURITY;
COMMIT;
