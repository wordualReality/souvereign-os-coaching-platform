#!/usr/bin/env python3
"""TEST ONLY: serialize synthetic publication with source rights update."""
import json
import time
from pathlib import Path
import pg17_disposable_command_path as db
import pg17_p11_source_review_readback as p11
import pg17_step9_guard_race as old

S = db.USER_SUPER
NS = 'kdb_step9r1_test'
D, P, V = old.D, old.P, old.V


def send(proc, sql):
    proc.stdin.write(sql + '\n'); proc.stdin.flush()


def stop(proc):
    if proc is None: return
    if proc.poll() is None:
        proc.stdin.close()
    proc.wait(timeout=10)


def blocked(waiter, blocker):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = db.must(S, f"SELECT {blocker} = ANY(pg_blocking_pids({waiter}))")
        if result == 't':
            state = db.must(S, f"SELECT wait_event_type||'|'||wait_event FROM pg_stat_activity WHERE pid={waiter}")
            if not state.startswith('Lock|'): raise SystemExit('FAIL_CLOSED WAIT_NOT_LOCK '+state)
            print(f'R1_BLOCKED waiter={waiter} blocker={blocker} event={state}')
            return
        time.sleep(.05)
    raise SystemExit(f'FAIL_CLOSED EXPECTED_BLOCK waiter={waiter} blocker={blocker}')


def conn(label):
    proc = old.psql_process()
    send(proc, f"\\set VERBOSITY verbose\nSET statement_timeout='8s'; SET lock_timeout='6s'; BEGIN; SELECT '{label}|'||session_user||'|'||current_user||'|'||txid_current()||'|'||pg_backend_pid();")
    info = old.line(proc)
    if not info.startswith(f'{label}|{S}|{S}|'): raise SystemExit('FAIL_CLOSED IDENTITY '+info)
    print('R1_SESSION '+info)
    return proc, int(info.rsplit('|',1)[1])


def guard_sql():
    text = (Path(__file__).parent / 'fixtures/step8_local_guard_candidate.sql').read_text().replace('pg_temp.', NS+'.').replace('step8_test_', 'step9r1_test_')
    c04 = "PERFORM s.source_id FROM kdb_staging.candidate_revision c JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id AND sv.tenant_scope=c.tenant_scope JOIN kdb_governance.source s ON s.source_id=sv.source_id AND s.tenant_scope=sv.tenant_scope WHERE c.candidate_revision_id=NEW.candidate_revision_id AND s.rights_status='ADMITTED' FOR SHARE OF s; IF NOT FOUND THEN RAISE EXCEPTION 'R1_RIGHTS_DENIED' USING ERRCODE='23514'; END IF; "
    c05 = "PERFORM s.source_id FROM kdb_governance.human_review_decision d JOIN kdb_staging.candidate_revision c ON c.candidate_revision_id=d.candidate_revision_id JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id AND sv.tenant_scope=c.tenant_scope JOIN kdb_governance.source s ON s.source_id=sv.source_id AND s.tenant_scope=sv.tenant_scope WHERE d.decision_id=NEW.human_decision_id AND c.candidate_revision_id=NEW.source_candidate_revision_id AND s.rights_status='ADMITTED' FOR SHARE OF s; IF NOT FOUND THEN RAISE EXCEPTION 'R1_RIGHTS_DENIED' USING ERRCODE='23514'; END IF; "
    text = text.replace('BEGIN\n  IF NOT EXISTS (', 'BEGIN\n  '+c04+'\n  IF NOT EXISTS (', 1)
    pos = text.index('CREATE FUNCTION '+NS+'.step8_c05_guard')
    text = text[:pos]+text[pos:].replace('BEGIN\n  IF NOT EXISTS (', 'BEGIN\n  '+c05+'\n  IF NOT EXISTS (', 1)
    text += f"\nCREATE FUNCTION {NS}.deny_delete() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'R1_APPEND_ONLY_TEST' USING ERRCODE='23514'; END $$;"
    for suffix, table in [('c04','kdb_governance.human_review_decision'),('c05','kdb_canonical.protocol_version'),('lifecycle','kdb_canonical.lifecycle_event')]:
        text += f' CREATE TRIGGER step9r1_delete_{suffix} BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {NS}.deny_delete();'
    return text


def catalog():
    return db.must(S, f"SELECT coalesce(string_agg(t.oid::text||'|'||pg_get_triggerdef(t.oid)||'|'||pg_get_functiondef(t.tgfoid), E'\\n' ORDER BY t.tgname),'') FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}' AND NOT t.tgisinternal")


def install():
    db.must(S, f'BEGIN; CREATE SCHEMA {NS}; REVOKE ALL ON SCHEMA {NS} FROM PUBLIC; '+guard_sql()+f' REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {NS} FROM PUBLIC; COMMIT;')
    definitions = catalog()
    if len(definitions.split('CREATE TRIGGER')) != 7 or definitions != catalog(): raise SystemExit('FAIL_CLOSED GUARD_CATALOG')
    if db.must(S, f"SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{NS}' AND (p.prosecdef OR has_function_privilege('public',p.oid,'EXECUTE'))") != '0': raise SystemExit('FAIL_CLOSED GUARD_PRIVILEGES')
    print('R1_GUARD_CATALOG ' + db.must(S, f"SELECT jsonb_build_object('schema_owner',pg_get_userbyid(n.nspowner),'schema_acl',n.nspacl::text,'functions',(SELECT jsonb_agg(jsonb_build_object('name',p.proname,'owner',pg_get_userbyid(p.proowner),'acl',p.proacl::text,'secdef',p.prosecdef,'config',p.proconfig) ORDER BY p.proname) FROM pg_proc p WHERE p.pronamespace=n.oid))::text FROM pg_namespace n WHERE n.nspname='{NS}'"))


def uninstall():
    for suffix, table in [('c04','kdb_governance.human_review_decision'),('c05','kdb_canonical.protocol_version'),('lifecycle','kdb_canonical.lifecycle_event')]:
        db.must(S, f'DROP TRIGGER IF EXISTS step9r1_delete_{suffix} ON {table}; DROP TRIGGER IF EXISTS step9r1_test_{suffix} ON {table};')
    db.must(S, f'DROP FUNCTION IF EXISTS {NS}.deny_delete(); DROP FUNCTION IF EXISTS {NS}.step8_c04_guard(); DROP FUNCTION IF EXISTS {NS}.step8_c05_guard(); DROP FUNCTION IF EXISTS {NS}.step8_lifecycle_guard(); DROP SCHEMA IF EXISTS {NS};')


def denied(sql, state, label):
    result = db.psql(S, '\\set VERBOSITY verbose\n' + sql)
    if result.returncode == 0 or state not in result.stderr: raise SystemExit('FAIL_CLOSED '+label+' '+result.stderr)
    print(f'R1_NEG {label} SQLSTATE={state}')


def main():
    db.ensure_container(); db.ensure_schema()
    baseline = json.loads(old.preimage())
    if any(v != 0 for k,v in baseline.items() if k != 'outbox'): raise SystemExit('FAIL_CLOSED FIXTURE_OCCUPIED')
    if db.must(S, f"SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='{NS}')+(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9r1_%')") != '0': raise SystemExit('FAIL_CLOSED GUARD_OCCUPIED')
    for table in ('kdb_governance.human_review_decision', 'kdb_canonical.protocol_version'):
        for privilege in ('INSERT', 'UPDATE', 'DELETE'):
            if db.must(S, f"SELECT has_table_privilege('kdb_ingest_runtime','{table}','{privilege}')") != 'f':
                raise SystemExit(f'FAIL_CLOSED RUNTIME_TABLE_PRIVILEGE {table} {privilege}')
    print('R1_RUNTIME_C04_C05_DML_PRIVILEGES FALSE')
    marker = 'INSERT INTO kdb_governance.source ('; i = p11.FIXTURE_SQL.index(marker); end = p11.FIXTURE_SQL.index(marker, i+len(marker))
    fixture = p11.FIXTURE_SQL[:end]+'COMMIT;'
    decision = f"INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at) VALUES('{D}','{p11.REVISION_ID}','{p11.CAND_SHA}','TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION','{p11.RIGHTS_SHA}','{'d'*64}','TEST_ONLY:signature',now())"
    protocol = f"INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES('{P}','TEST_ONLY','TEST_ONLY')"
    version = f"INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at) VALUES('{V}','{P}',1,'{p11.REVISION_ID}','{D}','{p11.CAND_SHA}','{{}}','TEST_ONLY',now())"
    lifecycle = f"INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES('{V}','PUBLISHED','TEST_ONLY',now(),'{D}')"
    a = b = None
    try:
        install()
        db.must(S, fixture)
        # A updates first; B's source FOR SHARE must wait for A's commit.
        a, apid = conn('A_REVOKE_FIRST'); send(a, f"UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}'; SELECT 'A_LOCKED';")
        if old.line(a) != 'A_LOCKED': raise SystemExit('FAIL_CLOSED A_LOCK')
        b, bpid = conn('B_PUBLISH_SECOND'); send(b, decision+';')
        blocked(bpid, apid)
        send(a, "COMMIT; SELECT 'A_COMMIT';")
        if old.line(a) != 'A_COMMIT': raise SystemExit('FAIL_CLOSED A_COMMIT')
        stop(a); a = None
        stop(b); err = b.stderr.read(); rc = b.returncode; b = None
        if rc == 0 or '23514' not in err or 'R1_RIGHTS_DENIED' not in err: raise SystemExit('FAIL_CLOSED B_NOT_DENIED '+err)
        if db.must(S, f"SELECT count(*) FROM kdb_governance.human_review_decision WHERE decision_id='{D}'") != '0': raise SystemExit('FAIL_CLOSED REVOKE_FIRST_WROTE')
        print('R1_REVOKE_FIRST BLOCK_THEN_DENY SQLSTATE=23514')
        db.must(S, f"UPDATE kdb_governance.source SET rights_status='ADMITTED' WHERE source_id='{p11.SOURCE_ID}'")
        # B publishes first and keeps source row share lock; A must wait.
        b, bpid = conn('B_PUBLISH_FIRST'); send(b, decision+';'+protocol+';'+version+';'+lifecycle+"; SELECT 'B_LOCKED';")
        if old.line(b) != 'B_LOCKED': raise SystemExit('FAIL_CLOSED B_LOCK')
        a, apid = conn('A_REVOKE_SECOND'); send(a, f"UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{p11.SOURCE_ID}'; SELECT 'A_UPDATED';")
        blocked(apid, bpid)
        send(b, "COMMIT; SELECT 'B_COMMIT';")
        if old.line(b) != 'B_COMMIT': raise SystemExit('FAIL_CLOSED B_COMMIT')
        stop(b); b = None
        if old.line(a) != 'A_UPDATED': raise SystemExit('FAIL_CLOSED A_UPDATE')
        send(a, "COMMIT; SELECT 'A_COMMIT';")
        if old.line(a) != 'A_COMMIT': raise SystemExit('FAIL_CLOSED A_COMMIT2')
        stop(a); a = None
        if db.must(S, f"SELECT s.rights_status||'|'||l.kind FROM kdb_governance.source s JOIN kdb_canonical.lifecycle_event l ON l.protocol_version_id='{V}' WHERE s.source_id='{p11.SOURCE_ID}'") != 'REVOKED|PUBLISHED': raise SystemExit('FAIL_CLOSED FINAL_STATE')
        print('R1_PUBLICATION_LINEARIZED_BEFORE_REVOCATION REVOKED|PUBLISHED / LATER_POLICY_UNDEFINED')
        for table, where in [('kdb_governance.human_review_decision',f"decision_id='{D}'"),('kdb_canonical.protocol_version',f"protocol_version_id='{V}'"),('kdb_canonical.lifecycle_event',f"protocol_version_id='{V}'")]: denied(f'DELETE FROM {table} WHERE {where}', '23514', 'APPEND_ONLY_'+table)
        # Disable ONLY disposable test triggers to characterize the existing
        # FK layer; immediately re-enable before the no-dependent checks.
        for suffix, table, where in [('c04','kdb_governance.human_review_decision',f"decision_id='{D}'"),('c05','kdb_canonical.protocol_version',f"protocol_version_id='{V}'")]:
            db.must(S, f'ALTER TABLE {table} DISABLE TRIGGER step9r1_delete_{suffix};')
            try: denied(f'DELETE FROM {table} WHERE {where}', '23503', 'EXISTING_FK_'+suffix)
            finally: db.must(S, f'ALTER TABLE {table} ENABLE TRIGGER step9r1_delete_{suffix};')
        db.must(S, 'ALTER TABLE kdb_canonical.lifecycle_event DISABLE TRIGGER step9r1_delete_lifecycle;')
        try: db.must(S, f"DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}';")
        finally: db.must(S, 'ALTER TABLE kdb_canonical.lifecycle_event ENABLE TRIGGER step9r1_delete_lifecycle;')
        denied(f"DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'", '23514', 'C05_NO_DEPENDENTS')
        db.must(S, 'ALTER TABLE kdb_canonical.protocol_version DISABLE TRIGGER step9r1_delete_c05;')
        try: db.must(S, f"DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}';")
        finally: db.must(S, 'ALTER TABLE kdb_canonical.protocol_version ENABLE TRIGGER step9r1_delete_c05;')
        denied(f"DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}'", '23514', 'C04_NO_DEPENDENTS')
        print('R1_GUARD_RECONNECT PASS / TEST_ONLY / NOT_ADMITTED')
    finally:
        stop(a); stop(b)
        uninstall()
        db.must(S, f"DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol_version WHERE protocol_version_id='{V}'; DELETE FROM kdb_canonical.protocol WHERE protocol_id='{P}'; DELETE FROM kdb_governance.human_review_decision WHERE decision_id='{D}'; DELETE FROM kdb_staging.review_work_item WHERE review_work_item_id='{p11.WORK_ITEM_ID}'; DELETE FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{p11.REVISION_ID}'; DELETE FROM kdb_staging.submission WHERE submission_id='{p11.SUBMISSION_ID}'; DELETE FROM kdb_governance.source_version WHERE source_version_id IN ('{p11.VERSION_ID}','{p11.VERSION_ID_2}'); DELETE FROM kdb_governance.source WHERE source_id='{p11.SOURCE_ID}';")
    if json.loads(old.preimage()) != baseline or db.must(S, f"SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='{NS}')+(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9r1_%')") != '0': raise SystemExit('FAIL_CLOSED PREIMAGE_NOT_RESTORED')
    install(); uninstall()
    if json.loads(old.preimage()) != baseline or db.must(S, f"SELECT (SELECT count(*) FROM pg_namespace WHERE nspname='{NS}')+(SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'step9r1_%')") != '0': raise SystemExit('FAIL_CLOSED REAPPLY_RESIDUAL')
    print('R1_REAPPLY_UNAPPLY PASS')
    print('R1_TEARDOWN ZERO_RESIDUAL_BOUNDED')


if __name__ == '__main__': main()
