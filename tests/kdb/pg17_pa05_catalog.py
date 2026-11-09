#!/usr/bin/env python3
"""Disposable network-isolated PA-05 SQL-read experiment. Never hosted."""
import json
import subprocess
import time
import uuid
from pathlib import Path
from pa05_catalog_reader import read_catalog

ROOT = Path(__file__).resolve().parents[2]
NAME = 'kdb-pa05-' + uuid.uuid4().hex[:12]
IDS = [f'05000000-0000-4000-8000-{n:012d}' for n in range(1, 14)]
SRC, SV, SUB, CAND, REV, CMD, ITEM, DEC, PROTO, PV, AREA, DOMAIN, MODULE = IDS
TAX = '05000000-0000-4000-8000-000000000014'
TENANT = 'PA05_TEST_ONLY'
SUBJECT = 'TEST_ONLY_SUBJECT'
PURPOSE = 'personal-plan-preview'
QUERY = f"SELECT pa05_test.read_catalog('{PV}','{TENANT}','{SUBJECT}','{PURPOSE}');"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def sql(text, user='postgres', check=True):
    p = subprocess.run(['docker', 'exec', '-i', NAME, 'psql', '-X', '-qAt',
                        '-v', 'ON_ERROR_STOP=1', '-U', user, '-d', 'postgres'],
                       input=text, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError(f'psql rc={p.returncode}: {p.stderr}')
    return p


def main():
    created = False
    try:
        run('docker', 'run', '-d', '--network', 'none', '--name', NAME,
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17')
        created = True
        for _ in range(60):
            logs = subprocess.run(['docker', 'logs', NAME], text=True, capture_output=True)
            if 'database system is ready to accept connections' in logs.stdout + logs.stderr and \
                    'PostgreSQL init process complete' in logs.stdout + logs.stderr and \
                    sql('SELECT 1', check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('PG17 startup timed out')
        version = sql("SHOW server_version_num").stdout.strip()
        if not version.startswith('17'):
            raise RuntimeError('PostgreSQL 17 required: ' + version)
        mode = run('docker', 'inspect', '-f', '{{.HostConfig.NetworkMode}}', NAME).stdout.strip()
        if mode != 'none':
            raise RuntimeError('network isolation failed')
        sql((ROOT / 'tests/kdb/pg17_disposable_bootstrap.sql').read_text())
        sql((ROOT / 'database/migrations/kdb/20261023140000__kdb_m01_001__core_foundation.sql').read_text())
        sql((ROOT / 'tests/kdb/pa05_catalog_fixture.sql').read_text())
        sql(f"""
INSERT INTO pa05_test.area VALUES ('{AREA}');
INSERT INTO pa05_test.domain VALUES ('{DOMAIN}','{AREA}');
INSERT INTO pa05_test.module VALUES ('{MODULE}','{DOMAIN}');
INSERT INTO pa05_test.taxonomy VALUES ('{TAX}','{AREA}','{DOMAIN}','{MODULE}',1,'TEST_ONLY');
INSERT INTO pa05_test.read_context VALUES ('{TENANT}','{SUBJECT}','{PURPOSE}',now(),now()+interval '4 minutes');
INSERT INTO kdb_governance.source(source_id,tenant_scope,source_class,external_locator,rights_status,owner_namespace)
 VALUES ('{SRC}','{TENANT}','OWNER_AUTHORED','synthetic://pa05','ADMITTED','KDB');
INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at)
 VALUES ('{SV}','{SRC}','{TENANT}',encode(public.digest(convert_to('synthetic source','UTF8'),'sha256'),'hex'),'{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}',encode(public.digest(convert_to('{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}'::jsonb::text,'UTF8'),'sha256'),'hex'),'text/plain',1,now());
INSERT INTO pa05_test.source_bytes VALUES ('{SV}',convert_to('synthetic source','UTF8'));
INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
 VALUES ('{SUB}','{TENANT}','KDB','pa05-fixture',repeat('c',64),'TEST_ONLY:principal','TEST_ONLY:access','KNOWLEDGE_INTAKE','{SV}');
INSERT INTO kdb_staging.candidate_revision(candidate_revision_id,candidate_id,revision_no,tenant_scope,source_version_id,submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state)
 VALUES ('{REV}','{CAND}',1,'{TENANT}','{SV}','{SUB}','{CMD}',encode(public.digest(convert_to('{{"synthetic": true}}'::jsonb::text,'UTF8'),'sha256'),'hex'),jsonb_build_array(jsonb_build_object('source_version_id','{SV}','start',0,'end',16)),'{{"synthetic":true}}','STRUCTURE_VALIDATED');
INSERT INTO kdb_staging.review_work_item(review_work_item_id,candidate_revision_id,tenant_scope,correlation_id) VALUES ('{ITEM}','{REV}','{TENANT}','{CMD}');
INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at)
 SELECT '{DEC}','{REV}',c.content_sha256,'TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION',sv.rights_snapshot_sha256,repeat('d',64),'TEST_ONLY:signature',now() FROM kdb_staging.candidate_revision c JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id WHERE c.candidate_revision_id='{REV}';
INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES ('{PROTO}','{MODULE}','{TAX}');
INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at)
 SELECT '{PV}','{PROTO}',1,'{REV}','{DEC}',content_sha256,'{{"synthetic":true}}','{TAX}',now() FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{REV}';
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES ('{PV}','PUBLISHED','TEST_ONLY',now(),'{DEC}');
""")
        receipt = read_catalog(NAME, PV, TENANT, SUBJECT, PURPOSE)
        assert receipt['status'] == 'SYNTHETIC_READ'
        positive = receipt['candidate']
        assert positive == read_catalog(NAME, PV, TENANT, SUBJECT, PURPOSE)['candidate']
        assert positive['protocolId'] == PROTO and positive['protocolVersionId'] == PV
        assert positive['owningModuleId'] == MODULE and positive['taxonomyVersionId'] == TAX
        contract = json.loads((ROOT / 'tests/kdb/fixtures/pa05_catalog_contract.v1.json').read_text())
        for key in ('protocolId', 'protocolVersionId', 'owningModuleId', 'taxonomyVersionId',
                    'relationIds', 'versionNo', 'sourceVersionId', 'candidateRevisionId',
                    'contentHash', 'canonicalSnapshot', 'taxonomyPath', 'lifecycle', 'rights',
                    'purpose', 'sourceStatus', 'trust'):
            assert positive[key] == contract[key], key
        print('PA05_PG17 NETWORK_NONE / SQL_READ_RECONNECT PASS')
        print('PA05_RECEIPT ' + json.dumps(positive, sort_keys=True))
        negatives = {
            'draft': "DELETE FROM kdb_canonical.lifecycle_event;",
            'withdrawn': f"UPDATE kdb_canonical.lifecycle_event SET kind='WITHDRAWN' WHERE protocol_version_id='{PV}';",
            'superseded': f"UPDATE kdb_canonical.lifecycle_event SET kind='SUPERSEDED' WHERE protocol_version_id='{PV}';",
            'missing_decision': "UPDATE kdb_governance.human_review_decision SET decision='REJECTED';",
            'taxonomy': "UPDATE kdb_canonical.protocol SET owning_module_ref='orphan';",
            'revoked': "UPDATE kdb_governance.source SET rights_status='REVOKED';",
            'pending_rights': "UPDATE kdb_governance.source SET rights_status='PENDING';",
            'stale_context': "UPDATE pa05_test.read_context SET observed_at=now()-interval '6 minutes';",
            'future_context': "UPDATE pa05_test.read_context SET observed_at=now()+interval '1 minute';",
            'expired_context': "UPDATE pa05_test.read_context SET valid_until=now()-interval '1 second';",
            'tampered_content': """UPDATE kdb_canonical.protocol_version SET canonical_snapshot='{"synthetic":false}';""",
            'tampered_source': "UPDATE pa05_test.source_bytes SET contents=convert_to('tampered','UTF8');",
            'tampered_rights': """UPDATE kdb_governance.source_version SET rights_snapshot='{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"],"extra":true}';""",
            'tampered_evidence': """UPDATE kdb_staging.candidate_revision SET evidence_span_refs='[{"bad":true}]';""",
            'stale_source': f"""INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at)
                SELECT gen_random_uuid(),source_id,tenant_scope,repeat('e',64),rights_snapshot,rights_snapshot_sha256,media_type,2,now() FROM kdb_governance.source_version WHERE source_version_id='{SV}';""",
        }
        for name, mutation in negatives.items():
            out = sql('BEGIN; ' + mutation + ' SET LOCAL ROLE pa05_fixture_reader; ' + QUERY + ' ROLLBACK;').stdout.strip()
            if out:
                raise AssertionError(name + ' leaked candidate: ' + out)
            print('PA05_DENY ' + name + ' PASS')
        for name, query in {
            'wrong_tenant': QUERY.replace(TENANT, 'OTHER'),
            'wrong_subject': QUERY.replace(SUBJECT, 'OTHER'),
            'wrong_purpose': QUERY.replace(PURPOSE, 'OTHER'),
            'wrong_version': QUERY.replace(PV, PROTO),
        }.items():
            if sql(query, 'pa05_fixture_reader').stdout.strip():
                raise AssertionError(name + ' leaked candidate')
            print('PA05_DENY ' + name + ' PASS')
        for tenant, subject, purpose in [('OTHER', SUBJECT, PURPOSE), (TENANT, 'OTHER', PURPOSE),
                                         (TENANT, SUBJECT, 'OTHER'), (TENANT, '', PURPOSE)]:
            assert read_catalog(NAME, PV, tenant, subject, purpose) == {'status': 'DENY', 'candidate': None}
        duplicate = sql(f"""INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
            SELECT gen_random_uuid(),tenant_scope,origin_owner,idempotency_key,repeat('f',64),principal_context_ref,access_decision_ref,purpose,source_version_id FROM kdb_staging.submission WHERE submission_id='{SUB}';""", check=False)
        assert duplicate.returncode != 0
        assert read_catalog(NAME, PV, TENANT, SUBJECT, PURPOSE)['candidate'] == positive
        assert read_catalog(NAME, PROTO, TENANT, SUBJECT, PURPOSE) == {'status': 'DENY', 'candidate': None}
        print('PA05_DENY duplicate_replay_and_stale_reference PASS')
        p = sql('SELECT * FROM kdb_canonical.protocol_version;', 'pa05_fixture_reader', check=False)
        if p.returncode == 0:
            raise AssertionError('reader has direct table access')
        print('PA05_DENY direct_table_access PASS')
        run('docker', 'stop', NAME)
        assert read_catalog(NAME, PV, TENANT, SUBJECT, PURPOSE) == {'status': 'DENY', 'candidate': None}
        print('PA05_DENY reader_unavailable PASS')
    finally:
        if created:
            run('docker', 'rm', '-f', NAME)
            print('PA05_CONTAINER_REMOVED', NAME)


if __name__ == '__main__':
    main()
