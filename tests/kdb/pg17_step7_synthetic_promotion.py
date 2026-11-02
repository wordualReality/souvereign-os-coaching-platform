#!/usr/bin/env python3
"""Test-only C04/C05 relational fixture, never an admitted write path."""
import hashlib
import sys
from pathlib import Path

import pg17_disposable_command_path as db
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/kdb'))
from offline_governance_promotion import validate
from test_offline_governance_promotion import sample

ADMIN = 'kdb_step7_fixture_admin'
S = db.USER_SUPER
IDS = [f'c0400000-0000-4000-8000-{i:012d}' for i in range(1, 11)]
SRC, VER, SUB, CAND, REV, CMD, ITEM, DEC, PROTO, PV = IDS
TENANT = 'STEP7_SYNTHETIC_TEST_ONLY'
H = hashlib.sha256(b'synthetic').hexdigest()


def main():
    db.ensure_container(); db.ensure_schema()
    if db.must(S, f"SELECT count(*) FROM pg_roles WHERE rolname='{ADMIN}'") != '0':
        raise SystemExit('FAIL_CLOSED FIXTURE_ROLE_EXISTS')
    if db.must(S, f"SELECT count(*) FROM kdb_governance.source WHERE source_id='{SRC}'") != '0':
        raise SystemExit('FAIL_CLOSED FIXTURE_SOURCE_EXISTS')
    for role in ('kdb_ingest_runtime', 'anon', 'authenticated', 'service_role'):
        for table in ('kdb_governance.human_review_decision', 'kdb_canonical.protocol_version'):
            # Provider-style NOLOGIN roles are characterized by SET ROLE only
            # as a negative, never as a positive authenticated session.
            user = role if role == 'kdb_ingest_runtime' else S
            prefix = '' if user == role else f'SET ROLE {role}; '
            p = db.psql(user, '\\set VERBOSITY verbose\n' + prefix + f'INSERT INTO {table} DEFAULT VALUES;')
            if p.returncode == 0 or '42501' not in p.stdout + p.stderr:
                raise SystemExit(f'FAIL_CLOSED DIRECT_WRITE {role} {table}: {p.stderr}')
            print(f'NEG DIRECT_WRITE {role} {table} SQLSTATE=42501')
            p = db.psql(user, '\\set VERBOSITY verbose\n' + prefix + f'UPDATE {table} SET created_at=created_at;')
            if p.returncode == 0 or '42501' not in p.stdout + p.stderr:
                raise SystemExit(f'FAIL_CLOSED DIRECT_UPDATE {role} {table}: {p.stderr}')
            print(f'NEG DIRECT_UPDATE {role} {table} SQLSTATE=42501')
    e = sample()
    e.update(tenant=TENANT, candidate_tenant=TENANT, review_tenant=TENANT, source_id=SRC, candidate_revision_id=REV, review_candidate_revision_id=REV, decision_id=DEC, review_item_id=ITEM, command_id=CMD)
    if validate(e, b'synthetic')['admitted']:
        raise SystemExit('FAIL_CLOSED FIXTURE_ADMITTED')
    db.must(S, f"CREATE ROLE {ADMIN} LOGIN NOINHERIT BYPASSRLS; GRANT USAGE ON SCHEMA kdb_governance,kdb_staging,kdb_canonical TO {ADMIN}; GRANT SELECT,INSERT,DELETE ON kdb_governance.source,kdb_governance.source_version,kdb_governance.human_review_decision,kdb_staging.submission,kdb_staging.candidate_revision,kdb_staging.review_work_item,kdb_canonical.protocol,kdb_canonical.protocol_version,kdb_canonical.lifecycle_event TO {ADMIN};")
    try:
        identity = db.must(ADMIN, 'SELECT session_user||\'|\'||current_user')
        if identity != ADMIN+'|'+ADMIN:
            raise SystemExit('FAIL_CLOSED FIXTURE_IDENTITY')
        sql = f"""
BEGIN;
INSERT INTO kdb_governance.source(source_id,tenant_scope,source_class,external_locator,rights_status,owner_namespace) VALUES('{SRC}','{TENANT}','OWNER_AUTHORED','synthetic://step7/test-only','ADMITTED','KDB');
INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at) VALUES('{VER}','{SRC}','{TENANT}','{H}','{{"test_only":true}}','{e['rights_sha256']}','text/plain',1,now());
INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id) VALUES('{SUB}','{TENANT}','KDB','step7-test-only','{'d'*64}','TEST_ONLY','TEST_ONLY','KNOWLEDGE_INTAKE','{VER}');
INSERT INTO kdb_staging.candidate_revision(candidate_revision_id,candidate_id,revision_no,tenant_scope,source_version_id,submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state) VALUES('{REV}','{CAND}',1,'{TENANT}','{VER}','{SUB}','{CMD}','{e['candidate_content_sha256']}','[{{"test_only":true}}]','{{"test_only":true}}','STRUCTURE_VALIDATED');
INSERT INTO kdb_staging.review_work_item(review_work_item_id,candidate_revision_id,tenant_scope,correlation_id) VALUES('{ITEM}','{REV}','{TENANT}','{CMD}');
INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at) VALUES('{DEC}','{REV}','{e['candidate_content_sha256']}','TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION','{e['rights_sha256']}','{e['evidence_sha256']}','TEST_ONLY:signature',now());
INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES('{PROTO}','TEST_ONLY','TEST_ONLY');
INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at) VALUES('{PV}','{PROTO}',1,'{REV}','{DEC}','{e['candidate_content_sha256']}','{{"test_only":true}}','TEST_ONLY',now());
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{PV}','PUBLISHED','TEST_ONLY',now(),'{DEC}');
COMMIT;
"""
        db.must(ADMIN, sql)
        actual = db.must(ADMIN, f"SELECT count(*) FROM kdb_canonical.protocol_version v JOIN kdb_governance.human_review_decision d ON d.decision_id=v.human_decision_id JOIN kdb_staging.review_work_item w ON w.candidate_revision_id=v.source_candidate_revision_id JOIN kdb_staging.candidate_revision c ON c.candidate_revision_id=w.candidate_revision_id JOIN kdb_staging.submission s ON s.submission_id=c.submission_id JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id JOIN kdb_governance.source src ON src.source_id=sv.source_id JOIN kdb_canonical.lifecycle_event l ON l.protocol_version_id=v.protocol_version_id WHERE v.protocol_version_id='{PV}' AND src.source_id='{SRC}' AND src.tenant_scope='{TENANT}' AND s.tenant_scope=c.tenant_scope AND c.tenant_scope=w.tenant_scope AND w.tenant_scope=src.tenant_scope AND sv.content_sha256='{H}' AND d.candidate_revision_id=v.source_candidate_revision_id AND d.candidate_content_sha256=c.content_sha256 AND v.content_sha256=c.content_sha256 AND d.source_rights_digest=sv.rights_snapshot_sha256 AND d.review_evidence_sha256='{e['evidence_sha256']}' AND d.decision='APPROVED_FOR_PROMOTION' AND l.kind='PUBLISHED';")
        if actual != '1': raise SystemExit('FAIL_CLOSED RECONNECT_CHAIN')
        print('STEP7_SYNTHETIC_COMMIT_RECONNECT PASS / NOT_ADMITTED')
    finally:
        db.must(ADMIN, f"BEGIN; DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{PV}'; DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{PV}'; DELETE FROM kdb_canonical.protocol WHERE protocol_id='{PROTO}'; DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{DEC}'; DELETE FROM kdb_staging.review_work_item WHERE review_work_item_id='{ITEM}'; DELETE FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{REV}'; DELETE FROM kdb_staging.submission WHERE submission_id='{SUB}'; DELETE FROM kdb_governance.source_version WHERE source_version_id='{VER}'; DELETE FROM kdb_governance.source WHERE source_id='{SRC}'; COMMIT;")
        db.must(S, f'DROP OWNED BY {ADMIN}; DROP ROLE {ADMIN};')
    if db.must(S, f"SELECT (SELECT count(*) FROM pg_roles WHERE rolname='{ADMIN}')+(SELECT count(*) FROM kdb_governance.source WHERE source_id='{SRC}')+(SELECT count(*) FROM kdb_canonical.protocol_version WHERE protocol_version_id='{PV}')") != '0':
        raise SystemExit('FAIL_CLOSED FIXTURE_RESIDUAL')
    print('STEP7_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
