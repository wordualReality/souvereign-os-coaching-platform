-- TEST ONLY / NON_APPLY. No hosted migration, no authority or signature proof.
CREATE FUNCTION pg_temp.step8_c04_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM kdb_staging.candidate_revision c
    JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id AND sv.tenant_scope=c.tenant_scope
    JOIN kdb_governance.source s ON s.source_id=sv.source_id AND s.tenant_scope=sv.tenant_scope
    JOIN kdb_staging.review_work_item w ON w.candidate_revision_id=c.candidate_revision_id AND w.tenant_scope=c.tenant_scope
    WHERE c.candidate_revision_id=NEW.candidate_revision_id AND c.content_sha256=NEW.candidate_content_sha256
      AND sv.rights_snapshot_sha256=NEW.source_rights_digest AND s.rights_status='ADMITTED'
      AND length(trim(NEW.reviewer_principal_ref))>0 AND length(trim(NEW.access_decision_ref))>0
      AND length(trim(NEW.signed_decision_ref))>0
  ) THEN RAISE EXCEPTION 'STEP8_C04_GUARD' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION pg_temp.step8_c05_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM kdb_governance.human_review_decision d
    JOIN kdb_staging.candidate_revision c ON c.candidate_revision_id=d.candidate_revision_id
    JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id AND sv.tenant_scope=c.tenant_scope
    JOIN kdb_governance.source s ON s.source_id=sv.source_id AND s.tenant_scope=sv.tenant_scope
    WHERE d.decision_id=NEW.human_decision_id AND d.candidate_revision_id=NEW.source_candidate_revision_id
      AND d.decision='APPROVED_FOR_PROMOTION' AND NEW.content_sha256=c.content_sha256
      AND d.candidate_content_sha256=c.content_sha256 AND d.source_rights_digest=sv.rights_snapshot_sha256
      AND s.rights_status='ADMITTED'
  ) THEN RAISE EXCEPTION 'STEP8_C05_GUARD' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER step8_test_c04 BEFORE INSERT OR UPDATE ON kdb_governance.human_review_decision FOR EACH ROW EXECUTE FUNCTION pg_temp.step8_c04_guard();
CREATE TRIGGER step8_test_c05 BEFORE INSERT OR UPDATE ON kdb_canonical.protocol_version FOR EACH ROW EXECUTE FUNCTION pg_temp.step8_c05_guard();
CREATE FUNCTION pg_temp.step8_lifecycle_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.kind <> 'PUBLISHED' OR NEW.prior_event_id IS NOT NULL OR EXISTS
    (SELECT 1 FROM kdb_canonical.lifecycle_event WHERE protocol_version_id=NEW.protocol_version_id)
  THEN RAISE EXCEPTION 'STEP8_LIFECYCLE_GUARD' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER step8_test_lifecycle BEFORE INSERT ON kdb_canonical.lifecycle_event FOR EACH ROW EXECUTE FUNCTION pg_temp.step8_lifecycle_guard();
