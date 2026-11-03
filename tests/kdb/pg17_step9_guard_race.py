#!/usr/bin/env python3
"""Disposable PG17 guard durability and READ COMMITTED counterexample."""
import os
import json
import select
import subprocess
from pathlib import Path
import pg17_disposable_command_path as db
import pg17_p11_source_review_readback as p11

S = db.USER_SUPER
NS = 'kdb_step9_test'
D = 'd0900000-0000-4000-8000-000000000001'
P = 'd0900000-0000-4000-8000-000000000002'
V = 'd0900000-0000-4000-8000-000000000003'
GUARD = Path(__file__).parent / 'fixtures/step8_local_guard_candidate.sql'


def psql_process():
    args = ['psql', '-U', S, '-d', db.DB, '-v', 'ON_ERROR_STOP=1', '-X', '-q', '-t', '-A']
    if db.MODE == 'libpq':
        args[1:1] = ['-h', os.environ.get('PGHOST', '127.0.0.1'), '-p', os.environ.get('PGPORT', '5432')]
    else:
        args = ['docker', 'exec', '-i', db.CONTAINER] + args
    return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)


def line(proc):
    if not select.select([proc.stdout], [], [], 10)[0]:
        raise SystemExit('FAIL_CLOSED SESSION_TIMEOUT')
    return proc.stdout.readline().strip()


def catalog():
    return db.must(S, f"SELECT coalesce(string_agg(t.oid::text||'|'||pg_get_triggerdef(t.oid)||'|'||pg_get_functiondef(t.tgfoid), E'\\n' ORDER BY t.tgname),'') FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}' AND NOT t.tgisinternal")


def preimage():
    return db.must(S, f"""SELECT jsonb_build_object(
      'schemas',(SELECT count(*) FROM pg_namespace WHERE nspname='{NS}'),
      'functions',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}'),
      'triggers',(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9_test_%'),
      'source',(SELECT count(*) FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}'),
      'versions',(SELECT count(*) FROM kdb_governance.source_version WHERE source_version_id IN ('{p11.VERSION_ID}','{p11.VERSION_ID_2}')),
      'submission',(SELECT count(*) FROM kdb_staging.submission WHERE submission_id='{p11.SUBMISSION_ID}'),
      'candidate',(SELECT count(*) FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{p11.REVISION_ID}'),
      'review',(SELECT count(*) FROM kdb_staging.review_work_item WHERE review_work_item_id='{p11.WORK_ITEM_ID}'),
      'decision',(SELECT count(*) FROM kdb_governance.human_review_decision WHERE decision_id='{D}'),
      'protocol',(SELECT count(*) FROM kdb_canonical.protocol WHERE protocol_id='{P}'),
      'version',(SELECT count(*) FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'),
      'lifecycle',(SELECT count(*) FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}'),
      'outbox',(SELECT count(*) FROM kdb_ops.outbox_event),
      'roles',(SELECT count(*) FROM pg_roles WHERE rolname LIKE 'kdb_step9_%'),
      'memberships',(SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname LIKE 'kdb_step9_%')
    )::text""")


def install():
    fixture = GUARD.read_text().replace('pg_temp.', NS+'.').replace('step8_test_', 'step9_test_')
    fingerprint = f"SELECT md5(coalesce(string_agg(t.oid::text||'|'||pg_get_triggerdef(t.oid)||'|'||pg_get_functiondef(t.tgfoid),E'\\n' ORDER BY t.tgname),'')) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}' AND NOT t.tgisinternal;"
    before_commit = db.must(S, f'BEGIN; CREATE SCHEMA {NS}; REVOKE ALL ON SCHEMA {NS} FROM PUBLIC; ' + fixture + f' REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {NS} FROM PUBLIC; ' + fingerprint + ' COMMIT;')
    if db.must(S, fingerprint) != before_commit: raise SystemExit('FAIL_CLOSED GUARD_COMMIT_DRIFT')
    if len(catalog().split('CREATE TRIGGER')) != 4: raise SystemExit('FAIL_CLOSED GUARD_COUNT')


def uninstall():
    db.must(S, f'DROP TRIGGER IF EXISTS step9_test_c04 ON kdb_governance.human_review_decision; DROP TRIGGER IF EXISTS step9_test_c05 ON kdb_canonical.protocol_version; DROP TRIGGER IF EXISTS step9_test_lifecycle ON kdb_canonical.lifecycle_event; DROP FUNCTION IF EXISTS {NS}.step8_c04_guard(); DROP FUNCTION IF EXISTS {NS}.step8_c05_guard(); DROP FUNCTION IF EXISTS {NS}.step8_lifecycle_guard(); DROP SCHEMA IF EXISTS {NS};')


def denied(sql, state, label):
    result = db.psql(S, '\\set VERBOSITY verbose\n' + sql)
    if result.returncode == 0 or state not in result.stderr:
        raise SystemExit(f'FAIL_CLOSED {label}: {result.stdout} {result.stderr}')
    print(f'STEP9_NEG {label} SQLSTATE={state}')


def main():
    db.ensure_container(); db.ensure_schema()
    pre = preimage()
    if any(value != 0 for key, value in json.loads(pre).items() if key != 'outbox'):
        raise SystemExit('FAIL_CLOSED PREIMAGE_OCCUPIED '+pre)
    marker = 'INSERT INTO kdb_governance.source ('
    start = p11.FIXTURE_SQL.index(marker); end = p11.FIXTURE_SQL.index(marker, start + len(marker))
    fixture = p11.FIXTURE_SQL[:end] + 'COMMIT;'
    decision = f"INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at) VALUES('{D}','{p11.REVISION_ID}','{p11.CAND_SHA}','TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION','{p11.RIGHTS_SHA}','{'d'*64}','TEST_ONLY:signature',now())"
    protocol = f"INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES('{P}','TEST_ONLY','TEST_ONLY')"
    version = f"INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at) VALUES('{V}','{P}',1,'{p11.REVISION_ID}','{D}','{p11.CAND_SHA}','{{}}','TEST_ONLY',now())"
    a = None
    try:
        install(); first = catalog(); second = catalog()
        if first != second: raise SystemExit('FAIL_CLOSED GUARD_RECONNECT_DRIFT')
        if db.must(S, f"SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}' AND (p.prosecdef OR has_function_privilege('public',p.oid,'EXECUTE'))") != '0': raise SystemExit('FAIL_CLOSED FUNCTION_SECURITY')
        print('STEP9_GUARD_COMMIT_RECONNECT DEFINITIONS_OIDS_MATCH')
        db.must(S, fixture)
        denied(decision.replace(p11.CAND_SHA, 'f'*64), '23514', 'WRONG_DIGEST_AFTER_RECONNECT')
        denied(decision.replace('TEST_ONLY:authority', ''), '23514', 'EMPTY_AUTHORITY_AFTER_RECONNECT')
        db.must(S, decision+';'+protocol+';'+version+';')
        denied(f"UPDATE kdb_governance.human_review_decision SET candidate_content_sha256='{'f'*64}' WHERE decision_id='{D}'", '23514', 'C04_UPDATE_DIGEST_ADMITTED_SOURCE')
        denied(f"UPDATE kdb_canonical.protocol_version SET content_sha256='{'f'*64}' WHERE protocol_version_id='{V}'", '23514', 'C05_UPDATE_DIGEST_ADMITTED_SOURCE')
        db.must(S, f"DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol WHERE protocol_id='{P}'; DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}';")
        print('OPEN_BYPASS C04_C05_DELETE_WITHOUT_DEPENDENCIES_NOT_GUARDED')
        # Direct session A changes the source without committing; session B's
        # READ COMMITTED guard sees the previous committed ADMITTED version.
        a = psql_process()
        a.stdin.write(f"SET statement_timeout='5s'; BEGIN; UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}'; SELECT 'A|'||session_user||'|'||current_user||'|'||txid_current()||'|'||pg_backend_pid();\n"); a.stdin.flush()
        ainfo = line(a)
        if not ainfo.startswith('A|'+S+'|'+S+'|'): raise SystemExit('FAIL_CLOSED SESSION_A '+ainfo)
        print('STEP9_SESSION '+ainfo+' UPDATE_UNCOMMITTED')
        pid = int(ainfo.rsplit('|', 1)[1])
        locks = db.must(S, f"SELECT count(*) FROM pg_locks WHERE pid={pid} AND relation='kdb_governance.source'::regclass AND mode='RowExclusiveLock' AND granted")
        if locks != '1': raise SystemExit('FAIL_CLOSED EXPECTED_SOURCE_LOCK')
        print('STEP9_SESSION_A_SOURCE_LOCKS ' + locks)
        b = db.must(S, f"SET statement_timeout='5s'; BEGIN; SELECT 'B|'||session_user||'|'||current_user||'|'||txid_current()||'|'||pg_backend_pid(); {decision}; {protocol}; {version}; INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','PUBLISHED','TEST_ONLY',now(),'{D}'); COMMIT;")
        print('STEP9_SESSION '+b+' PUBLISHED_COMMIT_BEFORE_REVOCATION')
        a.stdin.write("COMMIT; SELECT 'A_COMMIT';\n"); a.stdin.flush()
        if line(a) != 'A_COMMIT': raise SystemExit('FAIL_CLOSED SESSION_A_COMMIT')
        a.stdin.close(); a.wait(timeout=10)
        if a.returncode: raise SystemExit('FAIL_CLOSED SESSION_A_EXIT '+a.stderr.read())
        a = None
        state = db.must(S, f"SELECT s.rights_status||'|'||l.kind FROM kdb_governance.source s JOIN kdb_canonical.lifecycle_event l ON l.protocol_version_id='{V}' WHERE s.source_id='{p11.SOURCE_ID}'")
        if state != 'REVOKED|PUBLISHED': raise SystemExit('FAIL_CLOSED RACE_NOT_REPRODUCED '+state)
        print('FAIL_CLOSED RIGHTS_REVOCATION_RACE_UNCLOSED '+state)
        denied(f"UPDATE kdb_canonical.protocol_version SET content_sha256=content_sha256 WHERE protocol_version_id='{V}'", '23514', 'C05_UPDATE_AFTER_REVOCATION')
        denied(f"INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','WITHDRAWN','TEST_ONLY',now(),'{D}')", '23514', 'LIFECYCLE_ORDER')
        denied(f"DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}'", '23503', 'C04_DELETE_FK')
        denied(f"DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'", '23503', 'C05_DELETE_FK')
        # The candidate did not add DELETE guards; reveal rather than hide it.
        db.must(S, f"DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}';")
        print('OPEN_BYPASS LIFECYCLE_DELETE_NOT_GUARDED')
    finally:
        if a is not None:
            a.stdin.close(); a.wait(timeout=10)
        db.must(S, f"DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol WHERE protocol_id='{P}'; DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}'; DELETE FROM kdb_staging.review_work_item WHERE review_work_item_id='{p11.WORK_ITEM_ID}'; DELETE FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{p11.REVISION_ID}'; DELETE FROM kdb_staging.submission WHERE submission_id='{p11.SUBMISSION_ID}'; DELETE FROM kdb_governance.source_version WHERE source_version_id IN ('{p11.VERSION_ID}','{p11.VERSION_ID_2}'); DELETE FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}';")
        uninstall()
    if preimage() != pre:
        raise SystemExit('FAIL_CLOSED PREIMAGE_NOT_RESTORED')
    install(); uninstall()
    if preimage() != pre: raise SystemExit('FAIL_CLOSED REAPPLY_RESIDUAL')
    print('STEP9_REAPPLY_UNAPPLY PASS')
    print('STEP9_TEARDOWN ZERO_RESIDUAL')


if __name__ == '__main__':
    main()
