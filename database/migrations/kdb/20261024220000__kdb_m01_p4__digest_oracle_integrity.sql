-- KDB-M01-P4 digest and oracle integrity. Disposable PostgreSQL 17 only.
-- Does not authorize hosted apply. Does not invent a PIAC allow path.
-- v2 digest uses jsonb_build_array so NULL, empty string, and embedded
-- delimiters stay distinct. O2 binds evidence spans. Trust helper is
-- consulted and still cannot admit a command.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE FUNCTION kdb_ops.canonical_digest_v2(p_fields jsonb)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SET search_path = pg_catalog
AS $fn$
BEGIN
  IF p_fields IS NULL OR jsonb_typeof(p_fields) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'CANONICAL_DIGEST_CONTRACT_UNRESOLVED';
  END IF;
  IF jsonb_array_length(p_fields) IS NULL OR jsonb_array_length(p_fields) < 2 THEN
    RAISE EXCEPTION 'CANONICAL_DIGEST_CONTRACT_UNRESOLVED';
  END IF;
  IF (p_fields ->> 0) IS DISTINCT FROM 'v2' THEN
    RAISE EXCEPTION 'CANONICAL_DIGEST_CONTRACT_UNRESOLVED';
  END IF;
  RETURN encode(public.digest(convert_to(p_fields::text, 'UTF8'), 'sha256'), 'hex');
END
$fn$;
ALTER FUNCTION kdb_ops.canonical_digest_v2(jsonb) OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.canonical_digest_v2(jsonb) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.canonical_digest_v2(jsonb) TO kdb_migrator;

CREATE OR REPLACE FUNCTION kdb_ops.canonical_command_digest(
  p_kind text, p_command_id uuid, p_tenant_scope text, p_origin_owner text,
  p_purpose text, p_source_class text, p_external_locator text,
  p_content_sha256 text, p_rights_digest text, p_principal_context_ref text,
  p_access_decision_ref text, p_idempotency_key text, p_submission_id uuid
) RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SET search_path = pg_catalog
AS $fn$
BEGIN
  RAISE EXCEPTION 'CANONICAL_DIGEST_CONTRACT_UNRESOLVED';
END
$fn$;
ALTER FUNCTION kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid) OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.canonical_command_digest(text,uuid,text,text,text,text,text,text,text,text,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;

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
 v_computed := kdb_ops.canonical_digest_v2(jsonb_build_array(
   'v2', 'SOURCE_INTAKE', p_command_id, p_tenant_scope, p_origin_owner, p_purpose,
   p_source_class, p_external_locator, p_content_sha256, v_rights_digest,
   p_principal_context_ref, p_access_decision_ref, p_idempotency_key, p_submission_id));
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256, outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prior.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 IF kdb_ops.security_context_ready() IS NOT TRUE THEN
   RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
 END IF;
 RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
END $fn$;

CREATE OR REPLACE FUNCTION kdb_ops.propose_candidate(
 p_command_id uuid, p_tenant_scope text, p_submission_id uuid, p_source_version_id uuid,
 p_candidate_id uuid, p_revision_no bigint, p_request_sha256 text, p_content_sha256 text,
 p_evidence_spans jsonb, p_payload jsonb, p_actor_ref text, p_access_decision_ref text,
 p_correlation_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE v_prev record; v_computed text; v_payload_digest text; v_spans_digest text;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF p_request_sha256 IS NULL OR p_content_sha256 IS NULL
    OR p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_content_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'KDB_HASH_INVALID'; END IF;
 v_payload_digest := kdb_ops.jsonb_sha256(COALESCE(p_payload, '{}'::jsonb));
 v_spans_digest := kdb_ops.jsonb_sha256(COALESCE(p_evidence_spans, '[]'::jsonb));
 v_computed := kdb_ops.canonical_digest_v2(jsonb_build_array(
   'v2', 'CANDIDATE_PROPOSAL', p_command_id, p_tenant_scope, p_submission_id,
   p_source_version_id, p_candidate_id, p_revision_no, p_content_sha256,
   v_payload_digest, v_spans_digest, p_actor_ref, p_access_decision_ref));
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256,outcome INTO v_prev FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prev.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 IF kdb_ops.security_context_ready() IS NOT TRUE THEN
   RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
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
 v_computed := kdb_ops.canonical_digest_v2(jsonb_build_array(
   'v2', 'REVIEW_HANDOFF', p_command_id, p_tenant_scope, p_candidate_revision_id,
   p_actor_ref, p_access_decision_ref));
 IF p_request_sha256 IS DISTINCT FROM v_computed THEN RAISE EXCEPTION 'KDB_HASH_MISMATCH'; END IF;
 SELECT request_sha256, outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND AND v_prior.request_sha256 IS DISTINCT FROM v_computed THEN
   RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT';
 END IF;
 IF kdb_ops.security_context_ready() IS NOT TRUE THEN
   RAISE EXCEPTION 'KDB_SECURITY_CONTEXT_NOT_CONFIGURED';
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
