-- P06 draft: kdb.tenant_scope GUC is defense in depth, not authenticated PIAC.
-- A compromised kdb_ingest_runtime LOGIN could spoof the GUC. Facade stays fail-closed.
-- Named REVOKE EXECUTE on the three O1/O2/O3 functions. Signatures unchanged. Not applied.
-- KDB-M01 O1-O3 COMMAND CONTRACT (OFFLINE CANDIDATE; DO NOT APPLY BEFORE GATE A).
-- Public n8n does not call SQL or own the database principal; only the KDB-owned
-- purpose-validated facade may use dedicated kdb_ingest_runtime over approved TLS.
-- PHYSICAL GATE BLOCKER: facade MUST authenticate PIAC decision evidence (signature,
-- tenant, purpose, expiry, replay) BEFORE calling ANY function below. Text refs are
-- audit correlations, not proof. No password in this migration.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';


CREATE FUNCTION kdb_ops.ingest_source(
  p_command_id uuid, p_submission_id uuid, p_tenant_scope text,
  p_origin_owner text, p_idempotency_key text, p_request_sha256 text,
  p_source_class text, p_external_locator text, p_content_sha256 text,
  p_rights_snapshot jsonb, p_rights_snapshot_sha256 text,
  p_principal_context_ref text, p_access_decision_ref text,
  p_purpose text, p_correlation_id uuid, p_acquired_at timestamptz
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $fn$
DECLARE v_source_id uuid; v_version_id uuid; v_outcome jsonb; v_prior record; v_version_no bigint;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF p_tenant_scope IS NULL OR length(p_tenant_scope)<1 OR length(p_principal_context_ref)<1
    OR length(p_access_decision_ref)<1 OR length(p_purpose)<1 THEN RAISE EXCEPTION 'KDB_CONTEXT_REQUIRED'; END IF;
 IF p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_content_sha256 !~ '^[0-9a-f]{64}$'
    OR p_rights_snapshot_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'KDB_HASH_INVALID'; END IF;
 IF COALESCE(p_rights_snapshot->>'rights_status','') <> 'ADMITTED' OR
    COALESCE(p_rights_snapshot->>'rights_basis','')='' OR
    COALESCE(p_rights_snapshot->'allowed_purposes' ? p_purpose, false) IS NOT TRUE
    THEN RAISE EXCEPTION 'KDB_RIGHTS_NOT_ADMITTED'; END IF;
 SELECT request_sha256, outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND THEN
    IF v_prior.request_sha256 <> p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
    RETURN v_prior.outcome;
 END IF;
 -- Conflict on source locator is benign only if tenant + source kind match; rights changes
 -- create a new immutable SourceVersion with independent rights digest.
 INSERT INTO kdb_governance.source(tenant_scope,source_class,external_locator,rights_status,owner_namespace)
 VALUES(p_tenant_scope,p_source_class,p_external_locator,'ADMITTED','KDB')
 ON CONFLICT (tenant_scope,source_class,external_locator) DO NOTHING;
 SELECT source_id INTO v_source_id FROM kdb_governance.source
 WHERE tenant_scope=p_tenant_scope AND source_class=p_source_class AND external_locator=p_external_locator
   AND rights_status='ADMITTED';
 IF v_source_id IS NULL THEN RAISE EXCEPTION 'KDB_SOURCE_RIGHTS_CHANGED'; END IF;
 SELECT source_version_id INTO v_version_id FROM kdb_governance.source_version
 WHERE source_id=v_source_id AND content_sha256=p_content_sha256 AND rights_snapshot_sha256=p_rights_snapshot_sha256;
 IF v_version_id IS NULL THEN
   -- Serialize version number assignment per Source; duplicates resolve to one row.
   PERFORM pg_advisory_xact_lock(hashtextextended(v_source_id::text, 0));
   SELECT source_version_id INTO v_version_id FROM kdb_governance.source_version
   WHERE source_id=v_source_id AND content_sha256=p_content_sha256 AND rights_snapshot_sha256=p_rights_snapshot_sha256;
   IF v_version_id IS NULL THEN
     SELECT COALESCE(max(source_version_no),0)+1 INTO v_version_no FROM kdb_governance.source_version WHERE source_id=v_source_id;
     INSERT INTO kdb_governance.source_version(source_id,tenant_scope,content_sha256,rights_snapshot,
       rights_snapshot_sha256,media_type,source_version_no,acquired_at)
     VALUES(v_source_id,p_tenant_scope,p_content_sha256,p_rights_snapshot,p_rights_snapshot_sha256,
       COALESCE(p_rights_snapshot->>'media_type','application/octet-stream'),v_version_no,p_acquired_at)
     RETURNING source_version_id INTO v_version_id;
   END IF;
 END IF;
 INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,
   principal_context_ref,access_decision_ref,purpose,source_version_id)
 VALUES(p_submission_id,p_tenant_scope,p_origin_owner,p_idempotency_key,p_request_sha256,
   p_principal_context_ref,p_access_decision_ref,p_purpose,v_version_id)
 ON CONFLICT DO NOTHING;
 IF NOT EXISTS(SELECT 1 FROM kdb_staging.submission WHERE submission_id=p_submission_id
      AND tenant_scope=p_tenant_scope AND request_sha256=p_request_sha256 AND source_version_id=v_version_id
      AND idempotency_key=p_idempotency_key AND origin_owner=p_origin_owner) THEN
   RAISE EXCEPTION 'KDB_SUBMISSION_CONFLICT';
 END IF;
 v_outcome := jsonb_build_object('status','RECORDED','submission_id',p_submission_id,'source_version_id',v_version_id);
 INSERT INTO kdb_ops.command_receipt(command_id,tenant_scope,command_kind,request_sha256,outcome)
 VALUES(p_command_id,p_tenant_scope,'SOURCE_INTAKE',p_request_sha256,v_outcome)
 ON CONFLICT(command_id) DO NOTHING;
 SELECT request_sha256,outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'KDB_COMMAND_RECEIPT_CONFLICT'; END IF;
 IF v_prior.request_sha256 <> p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
 INSERT INTO kdb_ops.audit_event(action,actor_ref,tenant_scope,object_type,object_id,request_sha256,correlation_id,occurred_at)
 VALUES('SOURCE_INGESTED',p_principal_context_ref,p_tenant_scope,'SourceVersion',v_version_id,p_request_sha256,p_correlation_id,clock_timestamp());
 RETURN v_prior.outcome;
END $fn$;


CREATE FUNCTION kdb_ops.propose_candidate(
 p_command_id uuid, p_tenant_scope text, p_submission_id uuid, p_source_version_id uuid,
 p_candidate_id uuid, p_revision_no bigint, p_request_sha256 text, p_content_sha256 text,
 p_evidence_spans jsonb, p_payload jsonb, p_actor_ref text, p_access_decision_ref text,
 p_correlation_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE v_id uuid; v_outcome jsonb; v_prev record;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF COALESCE(length(p_actor_ref),0)=0 OR COALESCE(length(p_access_decision_ref),0)=0 THEN RAISE EXCEPTION 'KDB_CONTEXT_REQUIRED'; END IF;
 IF p_request_sha256 !~ '^[0-9a-f]{64}$' OR p_content_sha256 !~ '^[0-9a-f]{64}$'
 OR jsonb_typeof(p_evidence_spans)<>'array' OR jsonb_array_length(p_evidence_spans)=0
 OR jsonb_typeof(p_payload)<>'object' THEN RAISE EXCEPTION 'KDB_CANDIDATE_INVALID'; END IF;
 SELECT request_sha256,outcome INTO v_prev FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND THEN
  IF v_prev.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN v_prev.outcome;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM kdb_staging.submission WHERE submission_id=p_submission_id
 AND tenant_scope=p_tenant_scope AND source_version_id=p_source_version_id AND status='RECORDED')
 OR NOT EXISTS (SELECT 1 FROM kdb_governance.source_version v JOIN kdb_governance.source s ON s.source_id=v.source_id
 WHERE v.source_version_id=p_source_version_id AND v.tenant_scope=p_tenant_scope AND s.rights_status='ADMITTED')
 THEN RAISE EXCEPTION 'KDB_SOURCE_RIGHTS_OR_SCOPE_DENIED'; END IF;
 INSERT INTO kdb_staging.candidate_revision(candidate_id,revision_no,tenant_scope,source_version_id,
 submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state)
 VALUES(p_candidate_id,p_revision_no,p_tenant_scope,p_source_version_id,p_submission_id,
 p_command_id,p_content_sha256,p_evidence_spans,p_payload,'STRUCTURE_VALIDATED')
 ON CONFLICT DO NOTHING;
 SELECT candidate_revision_id INTO v_id FROM kdb_staging.candidate_revision
 WHERE proposal_command_id=p_command_id AND tenant_scope=p_tenant_scope AND content_sha256=p_content_sha256
 AND source_version_id=p_source_version_id AND submission_id=p_submission_id AND candidate_id=p_candidate_id
 AND revision_no=p_revision_no;
 IF v_id IS NULL THEN RAISE EXCEPTION 'KDB_CANDIDATE_CONFLICT'; END IF;
 v_outcome:=jsonb_build_object('status','STRUCTURE_VALIDATED_NOT_REVIEWED','candidate_revision_id',v_id);
 INSERT INTO kdb_ops.command_receipt(command_id,tenant_scope,command_kind,request_sha256,outcome)
 VALUES(p_command_id,p_tenant_scope,'CANDIDATE_PROPOSAL',p_request_sha256,v_outcome)
 ON CONFLICT(command_id) DO NOTHING;
 SELECT request_sha256,outcome INTO v_prev FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'KDB_COMMAND_RECEIPT_CONFLICT'; END IF;
 IF v_prev.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
 INSERT INTO kdb_ops.audit_event(action,actor_ref,tenant_scope,object_type,object_id,request_sha256,correlation_id,occurred_at)
 VALUES('CANDIDATE_PROPOSED',p_actor_ref,p_tenant_scope,'CandidateRevision',v_id,p_request_sha256,p_correlation_id,clock_timestamp());
 RETURN v_prev.outcome;
END $fn$;


CREATE FUNCTION kdb_ops.request_review_handoff(
 p_command_id uuid, p_tenant_scope text, p_candidate_revision_id uuid, p_request_sha256 text,
 p_actor_ref text, p_access_decision_ref text, p_correlation_id uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE v_work_item_id uuid; v_outcome jsonb; v_prior record;
BEGIN
 IF session_user <> 'kdb_ingest_runtime' THEN RAISE EXCEPTION 'KDB_PRINCIPAL_DENIED'; END IF;
 PERFORM set_config('kdb.tenant_scope', COALESCE(p_tenant_scope, ''), true);
 IF COALESCE(length(p_actor_ref),0)=0 OR COALESCE(length(p_access_decision_ref),0)=0
 OR p_request_sha256 !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'KDB_CONTEXT_REQUIRED'; END IF;
 SELECT request_sha256,outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF FOUND THEN
   IF v_prior.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
   RETURN v_prior.outcome;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM kdb_staging.candidate_revision
 WHERE candidate_revision_id=p_candidate_revision_id AND tenant_scope=p_tenant_scope
 AND validation_state='STRUCTURE_VALIDATED' AND review_state='PENDING_REVIEW') THEN
    RAISE EXCEPTION 'KDB_REVIEW_HANDOFF_NOT_ELIGIBLE'; END IF;
 INSERT INTO kdb_staging.review_work_item(candidate_revision_id,tenant_scope,correlation_id)
 VALUES(p_candidate_revision_id,p_tenant_scope,p_correlation_id)
 ON CONFLICT(candidate_revision_id) DO NOTHING;
 SELECT review_work_item_id INTO v_work_item_id FROM kdb_staging.review_work_item
 WHERE candidate_revision_id=p_candidate_revision_id AND tenant_scope=p_tenant_scope;
 IF v_work_item_id IS NULL THEN RAISE EXCEPTION 'KDB_REVIEW_HANDOFF_CONFLICT'; END IF;
 v_outcome:=jsonb_build_object('status','REVIEW_HANDOFF_REQUESTED_NOT_DECIDED','review_work_item_id',v_work_item_id);
 INSERT INTO kdb_ops.command_receipt(command_id,tenant_scope,command_kind,request_sha256,outcome)
 VALUES(p_command_id,p_tenant_scope,'REVIEW_HANDOFF',p_request_sha256,v_outcome)
 ON CONFLICT(command_id) DO NOTHING;
 SELECT request_sha256,outcome INTO v_prior FROM kdb_ops.command_receipt WHERE command_id=p_command_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'KDB_COMMAND_RECEIPT_CONFLICT'; END IF;
 IF v_prior.request_sha256<>p_request_sha256 THEN RAISE EXCEPTION 'KDB_IDEMPOTENCY_CONFLICT'; END IF;
 INSERT INTO kdb_ops.outbox_event(event_type,tenant_scope,event_schema_version,aggregate_id,aggregate_version,
 correlation_id,causation_id,payload,occurred_at)
 VALUES('kdb.review_work_item_requested',p_tenant_scope,'1.0',p_candidate_revision_id,1,p_correlation_id,p_command_id,
 jsonb_build_object('review_work_item_id',v_work_item_id,'candidate_revision_id',p_candidate_revision_id),clock_timestamp())
 ON CONFLICT(event_type,aggregate_id,aggregate_version) DO NOTHING;
 INSERT INTO kdb_ops.audit_event(action,actor_ref,tenant_scope,object_type,object_id,request_sha256,correlation_id,occurred_at)
 VALUES('REVIEW_HANDOFF_REQUESTED',p_actor_ref,p_tenant_scope,'ReviewWorkItem',v_work_item_id,p_request_sha256,p_correlation_id,clock_timestamp());
 RETURN v_prior.outcome;
END $fn$;


-- Explicit, fully-qualified privileges and immutable controlled command owner.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kdb_ops FROM PUBLIC, anon, authenticated, service_role;
ALTER FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) OWNER TO kdb_command_owner;
ALTER FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) OWNER TO kdb_command_owner;
ALTER FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) OWNER TO kdb_command_owner;
GRANT EXECUTE ON FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) TO kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) TO kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) TO kdb_ingest_runtime;
REVOKE EXECUTE ON FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role;
COMMIT;
