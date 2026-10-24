-- KDB-M01-P3 fail-closed security patch. Disposable PostgreSQL 17 only.
-- Does not authorize hosted apply. Does not invent a PIAC allow path.
-- set_config(kdb.tenant_scope) is RLS row visibility only, not tenant authentication.
-- Closes RED-01 (revoke external EXECUTE; security context not configured),
-- RED-02 (server-computed digest vs stored digest, never client hash as identity),
-- RED-03 (dedicated kdb_migrator creator defaults; no PUBLIC EXECUTE on its functions).
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE ROLE kdb_migrator NOLOGIN NOBYPASSRLS NOSUPERUSER NOINHERIT;
GRANT USAGE, CREATE ON SCHEMA kdb_ops TO kdb_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE kdb_migrator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE kdb_migrator IN SCHEMA kdb_ops REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

CREATE FUNCTION kdb_ops.security_context_ready()
RETURNS boolean
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog
AS $fn$ SELECT false $fn$;
ALTER FUNCTION kdb_ops.security_context_ready() OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.security_context_ready() FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;

CREATE FUNCTION kdb_ops.jsonb_sha256(p_doc jsonb)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog
AS $fn$
SELECT CASE WHEN p_doc IS NULL THEN NULL
ELSE encode(public.digest(convert_to(p_doc::text, 'UTF8'), 'sha256'), 'hex') END
$fn$;
ALTER FUNCTION kdb_ops.jsonb_sha256(jsonb) OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.jsonb_sha256(jsonb) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.jsonb_sha256(jsonb) TO kdb_migrator;

CREATE FUNCTION kdb_ops.canonical_command_digest(
  p_kind text, p_command_id uuid, p_tenant_scope text, p_origin_owner text,
  p_purpose text, p_source_class text, p_external_locator text,
  p_content_sha256 text, p_rights_digest text, p_principal_context_ref text,
  p_access_decision_ref text, p_idempotency_key text, p_submission_id uuid
) RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog
AS $fn$
SELECT encode(public.digest(convert_to(
  concat_ws(chr(10),
    'v1', p_kind, p_command_id::text, p_tenant_scope, p_origin_owner, p_purpose,
    p_source_class, p_external_locator, p_content_sha256, p_rights_digest,
    p_principal_context_ref, p_access_decision_ref, p_idempotency_key,
    p_submission_id::text
  ), 'UTF8'), 'sha256'), 'hex')
$fn$;
ALTER FUNCTION kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid) OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid) TO kdb_migrator;

CREATE OR REPLACE FUNCTION kdb_ops.ingest_source(
  p_command_id uuid, p_submission_id uuid, p_tenant_scope text,
  p_origin_owner text, p_idempotency_key text, p_request_sha256 text,
  p_source_class text, p_external_locator text, p_content_sha256 text,
  p_rights_snapshot jsonb, p_rights_snapshot_sha256 text,
  p_principal_context_ref text, p_access_decision_ref text,
  p_purpose text, p_correlation_id uuid, p_acquired_at timestamptz
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $fn$
DECLARE v_prior record; v_rights_digest text; v_computed text;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF p_request_sha256 IS NULL OR p_content_sha256 IS NULL OR p_rights_snapshot_sha256 IS NULL
    OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_content_sha256 !~ '^[0-9a-f]{64}$'
    OR p_rights_snapshot_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'KDB_HASH_INVALID'; END IF;
 v_rights_digest := kdb_ops.jsonb_sha256(p_rights_snapshot);
 IF p_rights_snapshot_sha256 IS DISTINCT FROM v_rights_digest THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 v_computed := kdb_ops.canonical_command_digest(
   'SOURCE_INTAKE', p_command_id, p_tenant_scope, p_origin_owner, p_purpose,
   p_source_class, p_external_locator, p_content_sha256, v_rights_digest,
   p_principal_context_ref, p_access_decision_ref, p_idempotency_key, p_submission_id);
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256, outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prior.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
END $fn$;

CREATE OR REPLACE FUNCTION kdb_ops.propose_candidate(
 p_command_id uuid, p_tenant_scope text, p_submission_id uuid, p_source_version_id uuid,
 p_candidate_id uuid, p_revision_no bigint, p_request_sha256 text, p_content_sha256 text,
 p_evidence_spans jsonb, p_payload jsonb, p_actor_ref text, p_access_decision_ref text,
 p_correlation_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE v_prev record; v_computed text; v_payload_digest text;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF p_request_sha256 IS NULL OR p_content_sha256 IS NULL
    OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_content_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'KDB_HASH_INVALID'; END IF;
 v_payload_digest := kdb_ops.jsonb_sha256(COALESCE(p_payload, '{}'::jsonb));
 v_computed := encode(public.digest(convert_to(concat_ws(chr(10),
   'v1','CANDIDATE_PROPOSAL', p_command_id::text, p_tenant_scope, p_submission_id::text,
   p_source_version_id::text, p_candidate_id::text, p_revision_no::text, p_content_sha256,
   v_payload_digest, p_actor_ref, p_access_decision_ref), 'UTF8'), 'sha256'), 'hex');
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256,outcome INTO v_prev FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prev.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
END $fn$;

CREATE OR REPLACE FUNCTION kdb_ops.request_review_handoff(
 p_command_id uuid, p_tenant_scope text, p_candidate_revision_id uuid, p_request_sha256 text,
 p_actor_ref text, p_access_decision_ref text, p_correlation_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE v_prior record; v_computed text;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF p_request_sha256 IS NULL OR p_request_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'KDB_HASH_INVALID'; END IF;
 v_computed := encode(public.digest(convert_to(concat_ws(chr(10),
   'v1','REVIEW_HANDOFF', p_command_id::text, p_tenant_scope, p_candidate_revision_id::text,
   p_actor_ref, p_access_decision_ref), 'UTF8'), 'sha256'), 'hex');
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256,outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prior.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
END $fn$;

ALTER FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) OWNER TO kdb_command_owner;
ALTER FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) OWNER TO kdb_command_owner;
ALTER FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) OWNER TO kdb_command_owner;

REVOKE ALL ON FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
REVOKE ALL ON FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;

COMMIT;
