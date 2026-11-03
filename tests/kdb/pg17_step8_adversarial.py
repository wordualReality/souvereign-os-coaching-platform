#!/usr/bin/env python3
"""Disposable SQL-only C04/C05 falsification; guard is a test candidate."""
from pathlib import Path
import pg17_disposable_command_path as db
import pg17_p11_source_review_readback as p11

S = db.USER_SUPER
GUARD = Path(__file__).parent / 'fixtures/step8_local_guard_candidate.sql'
D = 'd0800000-0000-4000-8000-000000000001'
P = 'd0800000-0000-4000-8000-000000000002'
V = 'd0800000-0000-4000-8000-000000000003'


def main():
    db.ensure_container(); db.ensure_schema()
    schemas = ('kdb_canonical', 'kdb_governance')
    prior = {s: db.must(S, f"SELECT coalesce(nspacl::text,'<NULL>') FROM pg_namespace WHERE nspname='{s}'") for s in schemas}
    had_usage = {s: db.must(S, f"SELECT has_schema_privilege('kdb_ingest_runtime','{s}','USAGE')") == 't' for s in schemas}
    if not had_usage['kdb_canonical']:
        p = db.psql('kdb_ingest_runtime', '\\set VERBOSITY verbose\nSELECT 1 FROM kdb_canonical.protocol_version;')
        if p.returncode == 0 or '42501' not in p.stderr or 'schema kdb_canonical' not in p.stderr:
            raise SystemExit('FAIL_CLOSED SCHEMA_DENIAL_NOT_ATTRIBUTED ' + p.stderr)
        print('STEP8_SCHEMA_USAGE_DENIED SQLSTATE=42501')
    for schema in schemas:
        if not had_usage[schema]: db.must(S, f'GRANT USAGE ON SCHEMA {schema} TO kdb_ingest_runtime;')
    try:
        for table in ('kdb_governance.human_review_decision', 'kdb_canonical.protocol_version'):
            schema = table.split('.')[0]
            if db.must(S, f"SELECT has_schema_privilege('kdb_ingest_runtime','{schema}','USAGE')") != 't':
                raise SystemExit('FAIL_CLOSED SCHEMA_USAGE_MISSING ' + schema)
            for statement in (f'INSERT INTO {table} DEFAULT VALUES', f'UPDATE {table} SET created_at=created_at', f'DELETE FROM {table}'):
                p = db.psql('kdb_ingest_runtime', '\\set VERBOSITY verbose\n' + statement + ';')
                if p.returncode == 0 or '42501' not in p.stderr or ('permission denied for table ' + table.split('.')[1]) not in p.stderr:
                    raise SystemExit('FAIL_CLOSED TABLE_DENIAL_NOT_ATTRIBUTED ' + p.stderr)
                print('STEP8_RUNTIME_TABLE_DENIED SQLSTATE=42501 ' + statement.split()[0] + ' ' + table)
    finally:
        for schema in schemas:
            if not had_usage[schema]: db.must(S, f'REVOKE USAGE ON SCHEMA {schema} FROM kdb_ingest_runtime;')
            if db.must(S, f"SELECT coalesce(nspacl::text,'<NULL>') FROM pg_namespace WHERE nspname='{schema}'") != prior[schema]:
                raise SystemExit('FAIL_CLOSED SCHEMA_ACL_NOT_RESTORED ' + schema)
    if db.must(S, f"SELECT count(*) FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}'") != '0':
        raise SystemExit('FAIL_CLOSED EXISTING_FIXTURE_SOURCE')
    # P11's original synthetic setup through review item; no historical test
    # function executes and the entire current transaction is rolled back.
    marker = 'INSERT INTO kdb_governance.source ('
    start = p11.FIXTURE_SQL.index(marker)
    end = p11.FIXTURE_SQL.index(marker, start + len(marker))
    fixture = p11.FIXTURE_SQL[:end]
    decision = f"INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at) VALUES('{D}','{p11.REVISION_ID}','{'f'*64}','TEST_ONLY:fake','TEST_ONLY:fake','APPROVED_FOR_PROMOTION','{'e'*64}','{'d'*64}','TEST_ONLY:fake',now())"
    protocol = f"INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES('{P}','TEST_ONLY','TEST_ONLY')"
    version = f"INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at) VALUES('{V}','{P}',1,'{p11.REVISION_ID}','{D}','{'f'*64}','{{}}','TEST_ONLY',now())"
    good = decision.replace('f'*64, p11.CAND_SHA).replace('e'*64, p11.RIGHTS_SHA)
    sql = fixture + f"""
{decision};
{protocol};
{version};
SELECT 'FAIL_CLOSED_DB_GUARD_GAP WRONG_CANDIDATE_HASH_AND_RIGHTS_ACCEPTED';
SELECT 'EXTERNAL_SIGNATURE_REFERENCE_UNVERIFIED';
DO $test$ BEGIN
  BEGIN UPDATE kdb_staging.review_work_item SET tenant_scope='STEP8_WRONG_TENANT' WHERE review_work_item_id='{p11.WORK_ITEM_ID}'; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'STEP8_REVIEW_TENANT_FK_DENIED SQLSTATE=23503'; END;
END $test$;
DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}';
DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}';
{good.replace('TEST_ONLY:fake', '')};
SELECT 'FAIL_CLOSED_DB_GUARD_GAP EMPTY_AUTHORITY_ACCEPTED';
DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}';
UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}';
{good};
SELECT 'FAIL_CLOSED_DB_GUARD_GAP REVOKED_RIGHTS_ACCEPTED';
DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}';
UPDATE kdb_governance.source SET rights_status='ADMITTED' WHERE source_id='{p11.SOURCE_ID}';
""" + GUARD.read_text() + f"""
DO $test$ BEGIN
  BEGIN {decision}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'STEP8_C04_INVALID_DENIED SQLSTATE=23514'; END;
END $test$;
DO $test$ BEGIN
  BEGIN {good.replace('TEST_ONLY:fake', '')}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'STEP8_EMPTY_AUTHORITY_DENIED SQLSTATE=23514'; END;
END $test$;
{good};
DO $test$ BEGIN
  BEGIN {good}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'STEP8_DUPLICATE_DECISION_DENIED SQLSTATE=23505'; END;
END $test$;
DO $test$ BEGIN
  BEGIN {good.replace(D, 'd0800000-0000-4000-8000-000000000004')}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'STEP8_CONFLICTING_DECISION_DENIED SQLSTATE=23505'; END;
END $test$;
SELECT 'STEP8_SAME_DECISION_PERSISTED|'||count(*) FROM kdb_governance.human_review_decision WHERE decision_id='{D}' AND candidate_revision_id='{p11.REVISION_ID}';
DO $test$ BEGIN
  BEGIN {version}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'STEP8_C05_INVALID_DENIED SQLSTATE=23514'; END;
END $test$;
{version.replace('f'*64, p11.CAND_SHA)};
SELECT 'STEP8_VALID_GUARD_INSERT|'||count(*) FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}';
DO $test$ BEGIN
  BEGIN INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','WITHDRAWN','TEST_ONLY',now(),'{D}'); RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'STEP8_LIFECYCLE_ORDER_DENIED SQLSTATE=23514'; END;
END $test$;
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','PUBLISHED','TEST_ONLY',now(),'{D}');
DO $test$ BEGIN
  BEGIN {version.replace('f'*64, p11.CAND_SHA)}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'STEP8_DUPLICATE_VERSION_DENIED SQLSTATE=23505'; END;
END $test$;
DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}';
DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}';
UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}';
DO $test$ BEGIN
  BEGIN {version.replace('f'*64, p11.CAND_SHA)}; RAISE EXCEPTION 'UNEXPECTED_ACCEPT';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'STEP8_REVOKED_DENIED SQLSTATE=23514'; END;
END $test$;
SELECT 'STEP8_LOCAL_GUARD_NEGATIVES_PASS';
ROLLBACK;
"""
    proc = db.psql(S, sql)
    if proc.returncode:
        raise SystemExit('FAIL_CLOSED STEP8_SQL ' + proc.stdout + proc.stderr)
    for token in ('WRONG_CANDIDATE_HASH_AND_RIGHTS_ACCEPTED', 'EMPTY_AUTHORITY_ACCEPTED', 'REVOKED_RIGHTS_ACCEPTED', 'STEP8_LOCAL_GUARD_NEGATIVES_PASS', 'STEP8_C04_INVALID_DENIED', 'STEP8_C05_INVALID_DENIED', 'STEP8_REVOKED_DENIED', 'STEP8_EMPTY_AUTHORITY_DENIED', 'STEP8_LIFECYCLE_ORDER_DENIED', 'STEP8_REVIEW_TENANT_FK_DENIED', 'STEP8_DUPLICATE_DECISION_DENIED', 'STEP8_CONFLICTING_DECISION_DENIED', 'STEP8_DUPLICATE_VERSION_DENIED', 'STEP8_SAME_DECISION_PERSISTED|1', 'STEP8_VALID_GUARD_INSERT|1'):
        if token not in proc.stdout + proc.stderr: raise SystemExit('FAIL_CLOSED MISSING ' + token)
    print(proc.stdout.strip()); print(proc.stderr.strip())
    if db.must(S, f"SELECT (SELECT count(*) FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}')+(SELECT count(*) FROM pg_trigger WHERE tgname IN ('step8_test_c04','step8_test_c05','step8_test_lifecycle'))") != '0':
        raise SystemExit('FAIL_CLOSED STEP8_RESIDUAL')
    print('STEP8_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
