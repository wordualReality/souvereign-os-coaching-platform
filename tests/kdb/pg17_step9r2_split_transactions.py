#!/usr/bin/env python3
"""Disposable split C04/revocation/C05 evidence; not a production path."""
import json
import pg17_disposable_command_path as db
import pg17_p11_source_review_readback as p11
import pg17_step9_guard_race as base
import pg17_step9r1_lock_append as r1

S = db.USER_SUPER
D, P, V = base.D, base.P, base.V


def tx(label, statements):
    sql = f"BEGIN; SELECT '{label}|'||session_user||'|'||current_user||'|'||txid_current()||'|'||pg_backend_pid(); {statements}; COMMIT;"
    result = db.must(S, sql)
    if not result.startswith(label+'|'+S+'|'+S+'|'):
        raise SystemExit('FAIL_CLOSED IDENTITY '+result)
    print('STEP9R2_COMMITTED '+result)


def cleanup():
    r1.uninstall()
    db.must(S, f"DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol WHERE protocol_id='{P}'; DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}'; DELETE FROM kdb_staging.review_work_item WHERE review_work_item_id='{p11.WORK_ITEM_ID}'; DELETE FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{p11.REVISION_ID}'; DELETE FROM kdb_staging.submission WHERE submission_id='{p11.SUBMISSION_ID}'; DELETE FROM kdb_governance.source_version WHERE source_version_id IN ('{p11.VERSION_ID}','{p11.VERSION_ID_2}'); DELETE FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}';")


def main():
    db.ensure_container(); db.ensure_schema()
    baseline = json.loads(base.preimage())
    if any(v != 0 for k,v in baseline.items() if k != 'outbox'):
        raise SystemExit('FAIL_CLOSED FIXTURE_OCCUPIED '+str(baseline))
    if db.must(S, f"SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='{r1.NS}')+(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9r1_%')") != '0':
        raise SystemExit('FAIL_CLOSED GUARD_OCCUPIED')
    marker = 'INSERT INTO kdb_governance.source ('
    i = p11.FIXTURE_SQL.index(marker); end = p11.FIXTURE_SQL.index(marker, i+len(marker))
    fixture = p11.FIXTURE_SQL[:end]+'COMMIT;'
    decision = f"INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at) VALUES('{D}','{p11.REVISION_ID}','{p11.CAND_SHA}','TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION','{p11.RIGHTS_SHA}','{'d'*64}','TEST_ONLY:signature',now())"
    protocol = f"INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES('{P}','TEST_ONLY','TEST_ONLY')"
    version = f"INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at) VALUES('{V}','{P}',1,'{p11.REVISION_ID}','{D}','{p11.CAND_SHA}','{{}}','TEST_ONLY',now())"
    lifecycle = f"INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','PUBLISHED','TEST_ONLY',now(),'{D}')"
    for revoked_first in (True, False):
        try:
            r1.install()
            db.must(S, fixture)
            tx('T1_C04', decision+'; '+protocol)
            c04 = db.must(S, f"SELECT (SELECT count(*) FROM kdb_governance.human_review_decision WHERE decision_id='{D}')||'|'||(SELECT count(*) FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}')")
            if c04 != '1|0': raise SystemExit('FAIL_CLOSED C04_RECONNECT '+c04)
            print('STEP9R2_C04_RECONNECT '+c04)
            if revoked_first:
                tx('T2_REVOKE', f"UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}'")
                if db.must(S, f"SELECT rights_status FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}'") != 'REVOKED': raise SystemExit('FAIL_CLOSED REVOCATION_READBACK')
                proc = db.psql(S, '\\set VERBOSITY verbose\n'+f"BEGIN; SELECT 'T3_C05|'||session_user||'|'||current_user||'|'||txid_current()||'|'||pg_backend_pid(); {version}; {lifecycle}; COMMIT;")
                if proc.returncode == 0 or '23514' not in proc.stderr or 'R1_RIGHTS_DENIED' not in proc.stderr: raise SystemExit('FAIL_CLOSED DB_GUARD_GAP '+proc.stdout+proc.stderr)
                print('STEP9R2_T3_DENIED '+proc.stdout.strip()+' SQLSTATE=23514')
                state = db.must(S, f"SELECT (SELECT count(*) FROM kdb_governance.human_review_decision WHERE decision_id='{D}')||'|'||(SELECT count(*) FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}')||'|'||(SELECT count(*) FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}')")
                if state != '1|0|0': raise SystemExit('FAIL_CLOSED POST_DENIAL '+state)
                print('STEP9R2_REVOKED_FIRST C04_RETAINED_C05_ABSENT '+state)
            else:
                tx('T2_C05_PUBLISHED', version+'; '+lifecycle)
                tx('T3_LATER_REVOKE', f"UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}'")
                state = db.must(S, f"SELECT s.rights_status||'|'||l.kind FROM kdb_governance.source s JOIN kdb_canonical.lifecycle_event l ON l.protocol_version_id='{V}' WHERE s.source_id='{p11.SOURCE_ID}'")
                if state != 'REVOKED|PUBLISHED': raise SystemExit('FAIL_CLOSED CONTROL '+state)
                print('STEP9R2_PUBLICATION_BEFORE_LATER_REVOCATION '+state+' POLICY_UNDEFINED')
        finally:
            cleanup()
        if json.loads(base.preimage()) != baseline: raise SystemExit('FAIL_CLOSED PREIMAGE_NOT_RESTORED')
        if db.must(S, f"SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='{r1.NS}')+(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9r1_%')") != '0': raise SystemExit('FAIL_CLOSED GUARD_RESIDUAL')
        print('STEP9R2_CASE_TEARDOWN ZERO_RESIDUAL_BOUNDED')
    print('STEP9R2_SPLIT_TRANSACTIONS PASS_SCOPED / NOT_ADMITTED')


if __name__ == '__main__': main()
