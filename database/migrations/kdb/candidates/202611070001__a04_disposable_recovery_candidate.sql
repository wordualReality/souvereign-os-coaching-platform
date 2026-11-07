-- A04 v1: DISPOSABLE ONLY; HOSTED_NOT_AUTHORIZED; not a deployment migration.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
DO $guard$
DECLARE n text;
BEGIN
 IF current_database() <> 'kdb_a04_disposable' OR current_setting('server_version_num')::integer / 10000 <> 17
    OR to_regclass('pg_temp.kdb_a04_disposable_guard') IS NULL THEN
   RAISE EXCEPTION 'A04_DISPOSABLE_GUARD_REQUIRED';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_extension e JOIN pg_namespace ns ON ns.oid=e.extnamespace WHERE e.extname='pgcrypto' AND ns.nspname='extensions')
    OR to_regprocedure('extensions.digest(bytea,text)') IS NULL THEN
   RAISE EXCEPTION 'A04_PGCRYPTO_NAMESPACE_MISMATCH';
 END IF;
 IF has_function_privilege('public', 'extensions.digest(bytea,text)', 'EXECUTE') THEN
   RAISE EXCEPTION 'A04_PGCRYPTO_PUBLIC_EXECUTE';
 END IF;
 FOREACH n IN ARRAY ARRAY['kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime'] LOOP
   IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=n) THEN
      RAISE EXCEPTION 'A04_EXISTING_ROLE_RECONCILIATION_REQUIRED: %', n;
   END IF;
 END LOOP;
 CREATE ROLE kdb_schema_owner NOLOGIN NOINHERIT NOBYPASSRLS;
 CREATE ROLE kdb_command_owner NOLOGIN NOINHERIT NOBYPASSRLS;
 CREATE ROLE kdb_ingest_runtime NOLOGIN NOINHERIT NOBYPASSRLS;
END $guard$;
-- Creator scope is the disposable runner only, not a claim about future creators.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
-- KDB-M01 / OFFLINE CANDIDATE. DO NOT EXECUTE BEFORE MUTATION-GATE-A.
-- Intended target: isolated approved Supabase/PostgreSQL environment, PostgreSQL >= 17.
-- Exact target, DB owner and grants are subject to preimage admission.
-- Migration identity KDB-M01-001; separate from historical Supabase migration 20261012105203.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';


-- Protected historical schemas canonical/dev_staging/public are NEVER modified here.
CREATE SCHEMA kdb_canonical;
CREATE SCHEMA kdb_staging;
CREATE SCHEMA kdb_governance;
CREATE SCHEMA kdb_ops;
REVOKE ALL ON SCHEMA kdb_canonical, kdb_staging, kdb_governance, kdb_ops FROM PUBLIC;
REVOKE ALL ON SCHEMA kdb_canonical, kdb_staging, kdb_governance, kdb_ops FROM anon, authenticated;


CREATE TABLE kdb_governance.source (
  source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_scope text NOT NULL CHECK (length(tenant_scope) BETWEEN 1 AND 128),
  source_class text NOT NULL CHECK (source_class IN ('PUBLIC_LINK','LICENSED_DOCUMENT','AUTHORIZED_UPLOAD','OWNER_AUTHORED','MEDIA_REFERENCE')),
  external_locator text NOT NULL CHECK (length(external_locator) BETWEEN 1 AND 4096),
  rights_status text NOT NULL CHECK (rights_status IN ('PENDING','ADMITTED','BLOCKED','REVOKED')),
  owner_namespace text NOT NULL CHECK (owner_namespace = 'KDB'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (tenant_scope, source_class, external_locator),
  UNIQUE (source_id, tenant_scope)
);


CREATE TABLE kdb_governance.source_version (
  source_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES kdb_governance.source(source_id) ON DELETE RESTRICT,
  tenant_scope text NOT NULL,
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  rights_snapshot jsonb NOT NULL CHECK (jsonb_typeof(rights_snapshot) = 'object'),
  rights_snapshot_sha256 text NOT NULL CHECK (rights_snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  media_type text NOT NULL,
  source_version_no bigint NOT NULL CHECK (source_version_no > 0),
  acquired_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (source_id, source_version_no),
  UNIQUE (source_id, content_sha256, rights_snapshot_sha256),
  UNIQUE (source_version_id, tenant_scope),
  FOREIGN KEY (source_id, tenant_scope) REFERENCES kdb_governance.source(source_id,tenant_scope)
);


CREATE TABLE kdb_staging.submission (
  submission_id uuid PRIMARY KEY,
  tenant_scope text NOT NULL,
  origin_owner text NOT NULL CHECK (origin_owner IN ('ARCAVA','KDB','APPROVED_EXTERNAL')),
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 256),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  principal_context_ref text NOT NULL CHECK (length(principal_context_ref) > 0),
  access_decision_ref text NOT NULL CHECK (length(access_decision_ref) > 0),
  purpose text NOT NULL CHECK (length(purpose) > 0),
  source_version_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED','QUARANTINED')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (source_version_id, tenant_scope) REFERENCES kdb_governance.source_version(source_version_id, tenant_scope),
  UNIQUE (tenant_scope, origin_owner, idempotency_key),
  UNIQUE (submission_id,tenant_scope,source_version_id)
);


CREATE TABLE kdb_staging.candidate_revision (
  candidate_revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL,
  revision_no bigint NOT NULL CHECK (revision_no > 0),
  tenant_scope text NOT NULL,
  source_version_id uuid NOT NULL,
  submission_id uuid NOT NULL REFERENCES kdb_staging.submission(submission_id),
  proposal_command_id uuid NOT NULL UNIQUE,
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_span_refs jsonb NOT NULL CHECK (jsonb_typeof(evidence_span_refs) = 'array' AND jsonb_array_length(evidence_span_refs) > 0),
  proposal_payload jsonb NOT NULL CHECK (jsonb_typeof(proposal_payload) = 'object'),
  validation_state text NOT NULL CHECK (validation_state IN ('STRUCTURE_VALIDATED','PENDING_VALIDATION','QUARANTINED','INSUFFICIENT_EVIDENCE','RIGHTS_BLOCKED','SAFETY_REVIEW_REQUIRED')),
  review_state text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_state = 'PENDING_REVIEW'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (source_version_id, tenant_scope) REFERENCES kdb_governance.source_version(source_version_id, tenant_scope),
  FOREIGN KEY (submission_id, tenant_scope, source_version_id) REFERENCES kdb_staging.submission(submission_id,tenant_scope,source_version_id),
  UNIQUE (candidate_id, revision_no),
  UNIQUE (candidate_revision_id, tenant_scope)
);


CREATE TABLE kdb_staging.review_work_item (
  review_work_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_revision_id uuid NOT NULL UNIQUE,
  tenant_scope text NOT NULL,
  owner_queue text NOT NULL DEFAULT 'KDB_HUMAN_REVIEW',
  state text NOT NULL DEFAULT 'REQUESTED' CHECK (state = 'REQUESTED'),
  correlation_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY (candidate_revision_id, tenant_scope) REFERENCES kdb_staging.candidate_revision(candidate_revision_id, tenant_scope)
);


-- Human review is governance truth, structurally reserved, with NO O1/O2/O3 write API.
CREATE TABLE kdb_governance.human_review_decision (
  decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_revision_id uuid NOT NULL UNIQUE REFERENCES kdb_staging.candidate_revision(candidate_revision_id),
  candidate_content_sha256 text NOT NULL CHECK (candidate_content_sha256 ~ '^[0-9a-f]{64}$'),
  reviewer_principal_ref text NOT NULL,
  access_decision_ref text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('APPROVED_FOR_PROMOTION','CHANGES_REQUESTED','REJECTED')),
  source_rights_digest text NOT NULL CHECK (source_rights_digest ~ '^[0-9a-f]{64}$'),
  review_evidence_sha256 text NOT NULL CHECK (review_evidence_sha256 ~ '^[0-9a-f]{64}$'),
  signed_decision_ref text NOT NULL,
  decided_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);


CREATE TABLE kdb_canonical.protocol (
  protocol_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owning_module_ref text NOT NULL,
  taxonomy_version_ref text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (protocol_id, owning_module_ref)
);


-- A canonical ProtocolVersion can exist only after a separately admitted human promotion transaction.
CREATE TABLE kdb_canonical.protocol_version (
  protocol_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol_id uuid NOT NULL REFERENCES kdb_canonical.protocol(protocol_id) ON DELETE RESTRICT,
  version_no bigint NOT NULL CHECK (version_no > 0),
  source_candidate_revision_id uuid NOT NULL UNIQUE REFERENCES kdb_staging.candidate_revision(candidate_revision_id),
  human_decision_id uuid NOT NULL UNIQUE REFERENCES kdb_governance.human_review_decision(decision_id),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  canonical_snapshot jsonb NOT NULL CHECK (jsonb_typeof(canonical_snapshot)='object'),
  taxonomy_version_ref text NOT NULL,
  published_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (protocol_id, version_no)
);


CREATE TABLE kdb_canonical.lifecycle_event (
  lifecycle_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol_version_id uuid NOT NULL REFERENCES kdb_canonical.protocol_version(protocol_version_id),
  kind text NOT NULL CHECK (kind IN ('PUBLISHED','REVALIDATION_REQUIRED','WITHDRAWN','SUPERSEDED')),
  reason_code text NOT NULL,
  prior_event_id uuid REFERENCES kdb_canonical.lifecycle_event(lifecycle_event_id),
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  decision_ref text NOT NULL,
  UNIQUE (protocol_version_id, kind, decision_ref)
);


CREATE TABLE kdb_ops.command_receipt (
  command_receipt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  command_id uuid NOT NULL UNIQUE,
  tenant_scope text NOT NULL,
  command_kind text NOT NULL CHECK (command_kind IN ('SOURCE_INTAKE','CANDIDATE_PROPOSAL','REVIEW_HANDOFF')),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  outcome jsonb NOT NULL CHECK (jsonb_typeof(outcome)='object'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);


CREATE TABLE kdb_ops.outbox_event (
  event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  tenant_scope text NOT NULL,
  event_schema_version text NOT NULL,
  producer_namespace text NOT NULL DEFAULT 'KDB' CHECK (producer_namespace='KDB'),
  aggregate_id uuid NOT NULL,
  aggregate_version bigint NOT NULL CHECK (aggregate_version > 0),
  correlation_id uuid NOT NULL,
  causation_id uuid,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  publish_state text NOT NULL DEFAULT 'INACTIVE_M01' CHECK (publish_state = 'INACTIVE_M01'),
  UNIQUE(event_type, aggregate_id, aggregate_version)
);


CREATE TABLE kdb_ops.audit_event (
  audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text NOT NULL,
  actor_ref text NOT NULL,
  tenant_scope text NOT NULL,
  object_type text NOT NULL,
  object_id uuid NOT NULL,
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  correlation_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);


CREATE INDEX source_tenant_idx ON kdb_governance.source(tenant_scope, created_at DESC);
CREATE INDEX source_version_source_idx ON kdb_governance.source_version(source_id, source_version_no DESC);
CREATE INDEX candidate_tenant_idx ON kdb_staging.candidate_revision(tenant_scope, validation_state, created_at DESC);
CREATE INDEX outbox_idx ON kdb_ops.outbox_event(event_type, recorded_at);
CREATE INDEX audit_object_idx ON kdb_ops.audit_event(object_type, object_id, recorded_at);


-- Row-level security is FORCEd even against the table owner; no initial grants/policies.
DO $kdb$ DECLARE rec record; BEGIN
  FOR rec IN SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') LOOP
    EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',rec.schemaname,rec.tablename);
    EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY',rec.schemaname,rec.tablename);
    EXECUTE format('REVOKE ALL ON TABLE %I.%I FROM PUBLIC, anon, authenticated',rec.schemaname,rec.tablename);
  END LOOP;
END $kdb$;


-- Zero runtime access at foundation; the gates and role grants belong to a separate reviewed migration.

-- The local superuser performs this disposable-only owner assignment.
DO $owners$
DECLARE rec record;
BEGIN
 FOR rec IN SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops') LOOP
   EXECUTE format('ALTER TABLE %I.%I OWNER TO kdb_schema_owner', rec.schemaname, rec.tablename);
 END LOOP;
END $owners$;
ALTER SCHEMA kdb_canonical OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_staging OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_governance OWNER TO kdb_schema_owner;
ALTER SCHEMA kdb_ops OWNER TO kdb_schema_owner;
-- Least-privilege synthetic owner access; no PUBLIC grant.
GRANT USAGE ON SCHEMA extensions TO kdb_command_owner;
GRANT EXECUTE ON FUNCTION extensions.digest(bytea,text) TO kdb_command_owner;
-- Synthetic deny-by-default v2 digest primitive; never exposes O1/O2/O3.
CREATE FUNCTION kdb_ops.a04_canonical_digest_v2(p_fields jsonb)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $fn$
BEGIN
 IF p_fields IS NULL OR jsonb_typeof(p_fields) IS DISTINCT FROM 'array'
 OR jsonb_array_length(p_fields) < 2 OR p_fields->>0 IS DISTINCT FROM 'v2' THEN
   RAISE EXCEPTION 'CANONICAL_DIGEST_CONTRACT_UNRESOLVED';
 END IF;
 RETURN encode(extensions.digest(convert_to(p_fields::text, 'UTF8'), 'sha256'), 'hex');
END $fn$;
ALTER FUNCTION kdb_ops.a04_canonical_digest_v2(jsonb) OWNER TO kdb_command_owner;
REVOKE ALL ON FUNCTION kdb_ops.a04_canonical_digest_v2(jsonb) FROM PUBLIC, anon, authenticated, service_role, kdb_ingest_runtime;
-- No command functions or grants are installed: PIAC remains unavailable.
COMMIT;
