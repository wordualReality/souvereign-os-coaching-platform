-- PA-05 synthetic fixture only; never apply to a hosted or persistent database.
CREATE SCHEMA pa05_test;
CREATE TABLE pa05_test.area (area_id uuid PRIMARY KEY);
CREATE TABLE pa05_test.domain (domain_id uuid PRIMARY KEY, area_id uuid NOT NULL REFERENCES pa05_test.area);
CREATE TABLE pa05_test.module (module_id uuid PRIMARY KEY, domain_id uuid NOT NULL REFERENCES pa05_test.domain);
CREATE TABLE pa05_test.taxonomy (
  taxonomy_version_id uuid PRIMARY KEY,
  area_id uuid NOT NULL REFERENCES pa05_test.area,
  domain_id uuid NOT NULL REFERENCES pa05_test.domain,
  module_id uuid NOT NULL REFERENCES pa05_test.module,
  revision integer NOT NULL CHECK (revision > 0),
  fixture_namespace text NOT NULL CHECK (fixture_namespace = 'TEST_ONLY')
);
CREATE TABLE pa05_test.source_bytes (source_version_id uuid PRIMARY KEY REFERENCES kdb_governance.source_version, contents bytea NOT NULL);
CREATE TABLE pa05_test.read_context (
  tenant text NOT NULL,
  subject text NOT NULL,
  purpose text NOT NULL,
  observed_at timestamptz NOT NULL,
  valid_until timestamptz NOT NULL,
  PRIMARY KEY (tenant, subject, purpose)
);

-- Fixture-only role and function. No hosted identity or PIAC claim is made.
CREATE ROLE pa05_fixture_reader LOGIN NOINHERIT NOBYPASSRLS;
REVOKE ALL ON SCHEMA pa05_test FROM PUBLIC;
GRANT USAGE ON SCHEMA pa05_test TO pa05_fixture_reader;
CREATE FUNCTION pa05_test.read_catalog(p_version uuid, p_tenant text, p_subject text, p_purpose text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog AS $function$
SELECT jsonb_build_object(
  'protocolId', p.protocol_id, 'protocolVersionId', v.protocol_version_id,
  'owningModuleId', t.module_id, 'taxonomyVersionId', t.taxonomy_version_id,
  'relationIds', '[]'::jsonb, 'versionNo', v.version_no,
  'sourceVersionId', sv.source_version_id, 'candidateRevisionId', c.candidate_revision_id,
  'provenance', jsonb_build_object('sourceId',src.source_id,'submissionId',s.submission_id,
      'reviewWorkItemId',w.review_work_item_id,'testDecisionId',d.decision_id,
      'sourceHash',sv.content_sha256,'rightsHash',sv.rights_snapshot_sha256,
      'rightsStatus',src.rights_status,'rightsBasis','TEST_ONLY'),
  'contentHash', v.content_sha256, 'canonicalSnapshot', v.canonical_snapshot,
  'taxonomyPath', jsonb_build_object('area', t.area_id, 'domain', t.domain_id,
      'module', t.module_id, 'revision', t.revision, 'namespace', t.fixture_namespace),
  'lifecycle', 'PUBLISHED', 'rights', 'ALLOW', 'safety', 'SAFE_FOR_PREVIEW',
  'purpose', x.purpose, 'observedAt', x.observed_at, 'validUntil', x.valid_until,
  'ruleVersion', 'PA05_TEST_ONLY_V1', 'sourceStatus', 'DATABASE_READ_SYNTHETIC_ONLY',
  'trust', 'TEST_ONLY / PREVIEW_ONLY / NON_EXECUTABLE / NOT_ADMITTED / D06_AUTHORITY_NOT_VERIFIED')
FROM kdb_canonical.protocol_version v
JOIN kdb_canonical.protocol p ON p.protocol_id = v.protocol_id
JOIN kdb_staging.candidate_revision c ON c.candidate_revision_id = v.source_candidate_revision_id
JOIN kdb_staging.submission s ON s.submission_id = c.submission_id AND s.source_version_id = c.source_version_id AND s.tenant_scope = c.tenant_scope
JOIN kdb_staging.review_work_item w ON w.candidate_revision_id = c.candidate_revision_id AND w.tenant_scope = c.tenant_scope
JOIN kdb_governance.source_version sv ON sv.source_version_id = c.source_version_id AND sv.tenant_scope = c.tenant_scope
JOIN kdb_governance.source src ON src.source_id = sv.source_id AND src.tenant_scope = sv.tenant_scope
JOIN kdb_governance.human_review_decision d ON d.decision_id = v.human_decision_id AND d.candidate_revision_id = c.candidate_revision_id
JOIN pa05_test.taxonomy t ON t.taxonomy_version_id::text = p.taxonomy_version_ref
    AND t.taxonomy_version_id::text = v.taxonomy_version_ref AND t.module_id::text = p.owning_module_ref
JOIN pa05_test.module m ON m.module_id = t.module_id AND m.domain_id = t.domain_id
JOIN pa05_test.domain td ON td.domain_id = t.domain_id AND td.area_id = t.area_id
JOIN pa05_test.area a ON a.area_id = t.area_id
JOIN pa05_test.source_bytes sb ON sb.source_version_id = sv.source_version_id
JOIN pa05_test.read_context x ON x.tenant = src.tenant_scope AND x.subject = p_subject AND x.purpose = p_purpose
WHERE v.protocol_version_id = p_version AND p_tenant = x.tenant
  AND p_purpose = 'personal-plan-preview' AND x.subject = 'TEST_ONLY_SUBJECT'
  AND x.observed_at <= statement_timestamp() AND x.observed_at >= statement_timestamp() - interval '5 minutes'
  AND x.valid_until > statement_timestamp()
  AND src.owner_namespace = 'KDB' AND src.rights_status = 'ADMITTED'
  AND sv.rights_snapshot->>'rights_status' = 'ADMITTED'
  AND sv.rights_snapshot->'allowed_purposes' ? p_purpose
  AND sv.rights_snapshot->'allowed_purposes' ? s.purpose
  AND sv.content_sha256 = encode(public.digest(sb.contents, 'sha256'), 'hex')
  AND sv.rights_snapshot_sha256 = encode(public.digest(convert_to(sv.rights_snapshot::text, 'UTF8'), 'sha256'), 'hex')
  AND c.evidence_span_refs = jsonb_build_array(jsonb_build_object('source_version_id',sv.source_version_id::text,'start',0,'end',octet_length(sb.contents)))
  AND s.status = 'RECORDED' AND s.origin_owner = 'KDB' AND s.purpose = 'KNOWLEDGE_INTAKE'
  AND c.validation_state = 'STRUCTURE_VALIDATED' AND c.review_state = 'PENDING_REVIEW'
  AND w.state = 'REQUESTED' AND w.owner_queue = 'KDB_HUMAN_REVIEW'
  AND d.decision = 'APPROVED_FOR_PROMOTION' AND d.reviewer_principal_ref LIKE 'TEST_ONLY:%'
  AND d.access_decision_ref LIKE 'TEST_ONLY:%' AND d.signed_decision_ref LIKE 'TEST_ONLY:%'
  AND d.source_rights_digest = sv.rights_snapshot_sha256 AND d.candidate_content_sha256 = c.content_sha256
  AND v.content_sha256 = c.content_sha256
  AND v.content_sha256 = encode(public.digest(convert_to(v.canonical_snapshot::text, 'UTF8'), 'sha256'), 'hex')
  AND NOT EXISTS (SELECT 1 FROM kdb_governance.source_version newer WHERE newer.source_id = sv.source_id AND newer.source_version_no > sv.source_version_no)
  AND NOT EXISTS (SELECT 1 FROM kdb_staging.candidate_revision newer WHERE newer.candidate_id = c.candidate_id AND newer.revision_no > c.revision_no)
  AND (SELECT count(*) FROM kdb_canonical.lifecycle_event e WHERE e.protocol_version_id = v.protocol_version_id) = 1
  AND EXISTS (SELECT 1 FROM kdb_canonical.lifecycle_event e WHERE e.protocol_version_id = v.protocol_version_id AND e.kind = 'PUBLISHED' AND e.decision_ref = d.decision_id::text);
$function$;
REVOKE ALL ON FUNCTION pa05_test.read_catalog(uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pa05_test.read_catalog(uuid,text,text,text) TO pa05_fixture_reader;
