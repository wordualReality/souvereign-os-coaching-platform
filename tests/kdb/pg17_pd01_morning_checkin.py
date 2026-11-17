#!/usr/bin/env python3
"""Disposable network-isolated PD01 exact-version detail experiment. Never hosted."""
import json
import subprocess
import time
import uuid
from pathlib import Path

from pa05_catalog_reader import read_catalog as read_pa05
from pd01_detail_reader import read_detail, snapshot_schema_ok

ROOT = Path(__file__).resolve().parents[2]
NAME = 'kdb-pd01-' + uuid.uuid4().hex[:12]
PA05_IDS = [f'05000000-0000-4000-8000-{n:012d}' for n in range(1, 14)]
PA05_SRC, PA05_SV, PA05_SUB, PA05_CAND, PA05_REV, PA05_CMD, PA05_ITEM, PA05_DEC, PA05_PROTO, PA05_PV, PA05_AREA, PA05_DOMAIN, PA05_MODULE = PA05_IDS
PA05_TAX = '05000000-0000-4000-8000-000000000014'
PA05_TENANT = 'PA05_TEST_ONLY'
IDS = [f'0d010000-0000-4000-8000-{n:012d}' for n in range(1, 14)]
SRC, SV, SUB, CAND, REV, CMD, ITEM, DEC, PROTO, PV, AREA, DOMAIN, MODULE = IDS
TAX = '0d010000-0000-4000-8000-000000000014'
V2_SUB, V2_CAND, V2_REV, V2_CMD, V2_ITEM, V2_DEC, V2_PV = [
    f'0d010000-0000-4000-8000-{n:012d}' for n in range(21, 28)
]
TENANT = 'PD01_TEST_ONLY'
SUBJECT = 'TEST_ONLY_SUBJECT'
PURPOSE = 'personal-plan-preview'
QUERY = f"SELECT pd01_test.read_detail('{PV}','{TENANT}','{SUBJECT}','{PURPOSE}');"
SRC_TEXT = 'Morgen-Check-in\nNotiere eine Priorität für heute.'
SNAP = (
    '{"instructions":["Notiere eine Priorität für heute."],'
    '"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,'
    '"title":"Morgen-Check-in"}'
)
V2_SNAP = (
    '{"instructions":["Diese Version darf nicht als Ersatz geliefert werden."],'
    '"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,'
    '"title":"Nicht-das-angeforderte-Protokoll"}'
)
PA05_TRACKED = [
    'tests/kdb/fixtures/pa05_catalog_contract.v1.json',
    'tests/kdb/pa05_catalog_fixture.sql',
    'tests/kdb/pg17_pa05_catalog.py',
    'tests/kdb/pa05_catalog_reader.py',
    'docs/kdb/m01/PA05_LOCAL_CATALOG.md',
]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def sql(text, user='postgres', check=True):
    p = subprocess.run(['docker', 'exec', '-i', NAME, 'psql', '-X', '-qAt',
                        '-v', 'ON_ERROR_STOP=1', '-U', user, '-d', 'postgres'],
                       input=text, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError(f'psql rc={p.returncode}: {p.stderr}')
    return p


def git_blob(rev_path):
    return run('git', '-C', str(ROOT), 'rev-parse', rev_path).stdout.strip()


def assert_pa05_byte_exact():
    for rel in PA05_TRACKED:
        current = run('git', '-C', str(ROOT), 'hash-object', rel).stdout.strip()
        committed = git_blob(f'HEAD:{rel}')
        if current != committed:
            raise AssertionError(f'PA05 fixture drifted: {rel} {current} != {committed}')
    contract = json.loads((ROOT / 'tests/kdb/fixtures/pa05_catalog_contract.v1.json').read_text())
    if contract['canonicalSnapshot'] != {'synthetic': True}:
        raise AssertionError('PA05 canonicalSnapshot must remain {"synthetic": true}')
    if contract['protocolVersionId'] != PA05_PV:
        raise AssertionError('PA05 protocolVersionId drifted')
    if contract['contentHash'] != 'f1a8594e8976c89f1e5c028870c3d3764a7a5423473cd8635448d7f6d8cc6574':
        raise AssertionError('PA05 contentHash drifted')


def deny(name, receipt):
    if receipt != {'status': 'DENY', 'candidate': None}:
        raise AssertionError(name + ' leaked detail: ' + json.dumps(receipt, ensure_ascii=False))
    print('PD01_DENY ' + name + ' PASS')


def rebind_snapshot(snapshot_json):
    """Rewrite snapshot, candidate and decision hashes so only schema validity changes."""
    return f"""
WITH snap AS (SELECT $schema${snapshot_json}$schema$::jsonb AS canonical_snapshot)
UPDATE kdb_canonical.protocol_version v
   SET canonical_snapshot = snap.canonical_snapshot,
       content_sha256 = encode(public.digest(convert_to(snap.canonical_snapshot::text,'UTF8'),'sha256'),'hex')
  FROM snap WHERE v.protocol_version_id='{PV}';
UPDATE kdb_staging.candidate_revision c
   SET content_sha256 = v.content_sha256, proposal_payload = v.canonical_snapshot
  FROM kdb_canonical.protocol_version v
 WHERE c.candidate_revision_id='{REV}' AND v.protocol_version_id='{PV}';
UPDATE kdb_governance.human_review_decision d
   SET candidate_content_sha256 = c.content_sha256
  FROM kdb_staging.candidate_revision c
 WHERE d.decision_id='{DEC}' AND c.candidate_revision_id='{REV}';
"""


def main():
    created = False
    try:
        assert_pa05_byte_exact()
        print('PD01_PA05_BYTE_EXACT PASS')
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
        sql((ROOT / 'tests/kdb/pd01_detail_fixture.sql').read_text())
        sql(f"""
INSERT INTO pa05_test.area VALUES ('{PA05_AREA}');
INSERT INTO pa05_test.domain VALUES ('{PA05_DOMAIN}','{PA05_AREA}');
INSERT INTO pa05_test.module VALUES ('{PA05_MODULE}','{PA05_DOMAIN}');
INSERT INTO pa05_test.taxonomy VALUES ('{PA05_TAX}','{PA05_AREA}','{PA05_DOMAIN}','{PA05_MODULE}',1,'TEST_ONLY');
INSERT INTO pa05_test.read_context VALUES ('{PA05_TENANT}','{SUBJECT}','{PURPOSE}',now(),now()+interval '4 minutes');
INSERT INTO kdb_governance.source(source_id,tenant_scope,source_class,external_locator,rights_status,owner_namespace)
 VALUES ('{PA05_SRC}','{PA05_TENANT}','OWNER_AUTHORED','synthetic://pa05','ADMITTED','KDB');
INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at)
 VALUES ('{PA05_SV}','{PA05_SRC}','{PA05_TENANT}',encode(public.digest(convert_to('synthetic source','UTF8'),'sha256'),'hex'),'{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}',encode(public.digest(convert_to('{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}'::jsonb::text,'UTF8'),'sha256'),'hex'),'text/plain',1,now());
INSERT INTO pa05_test.source_bytes VALUES ('{PA05_SV}',convert_to('synthetic source','UTF8'));
INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
 VALUES ('{PA05_SUB}','{PA05_TENANT}','KDB','pa05-fixture',repeat('c',64),'TEST_ONLY:principal','TEST_ONLY:access','KNOWLEDGE_INTAKE','{PA05_SV}');
INSERT INTO kdb_staging.candidate_revision(candidate_revision_id,candidate_id,revision_no,tenant_scope,source_version_id,submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state)
 VALUES ('{PA05_REV}','{PA05_CAND}',1,'{PA05_TENANT}','{PA05_SV}','{PA05_SUB}','{PA05_CMD}',encode(public.digest(convert_to('{{"synthetic": true}}'::jsonb::text,'UTF8'),'sha256'),'hex'),jsonb_build_array(jsonb_build_object('source_version_id','{PA05_SV}','start',0,'end',16)),'{{"synthetic":true}}','STRUCTURE_VALIDATED');
INSERT INTO kdb_staging.review_work_item(review_work_item_id,candidate_revision_id,tenant_scope,correlation_id) VALUES ('{PA05_ITEM}','{PA05_REV}','{PA05_TENANT}','{PA05_CMD}');
INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at)
 SELECT '{PA05_DEC}','{PA05_REV}',c.content_sha256,'TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION',sv.rights_snapshot_sha256,repeat('d',64),'TEST_ONLY:signature',now() FROM kdb_staging.candidate_revision c JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id WHERE c.candidate_revision_id='{PA05_REV}';
INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES ('{PA05_PROTO}','{PA05_MODULE}','{PA05_TAX}');
INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at)
 SELECT '{PA05_PV}','{PA05_PROTO}',1,'{PA05_REV}','{PA05_DEC}',content_sha256,'{{"synthetic":true}}','{PA05_TAX}',now() FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{PA05_REV}';
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES ('{PA05_PV}','PUBLISHED','TEST_ONLY',now(),'{PA05_DEC}');
""")
        sql(f"""
INSERT INTO pd01_test.area VALUES ('{AREA}');
INSERT INTO pd01_test.domain VALUES ('{DOMAIN}','{AREA}');
INSERT INTO pd01_test.module VALUES ('{MODULE}','{DOMAIN}');
INSERT INTO pd01_test.taxonomy VALUES ('{TAX}','{AREA}','{DOMAIN}','{MODULE}',1,'TEST_ONLY');
INSERT INTO pd01_test.read_context VALUES ('{TENANT}','{SUBJECT}','{PURPOSE}',now(),now()+interval '4 minutes');
INSERT INTO kdb_governance.source(source_id,tenant_scope,source_class,external_locator,rights_status,owner_namespace)
 VALUES ('{SRC}','{TENANT}','OWNER_AUTHORED','synthetic://pd01-morning-checkin','ADMITTED','KDB');
INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at)
 VALUES ('{SV}','{SRC}','{TENANT}',encode(public.digest(convert_to($src${SRC_TEXT}$src$,'UTF8'),'sha256'),'hex'),'{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}',encode(public.digest(convert_to('{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"]}}'::jsonb::text,'UTF8'),'sha256'),'hex'),'text/plain',1,now());
INSERT INTO pd01_test.source_bytes VALUES ('{SV}',convert_to($src${SRC_TEXT}$src$,'UTF8'));
INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
 VALUES ('{SUB}','{TENANT}','KDB','pd01-morning-checkin',repeat('c',64),'TEST_ONLY:principal','TEST_ONLY:access','KNOWLEDGE_INTAKE','{SV}');
INSERT INTO kdb_staging.candidate_revision(candidate_revision_id,candidate_id,revision_no,tenant_scope,source_version_id,submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state)
 VALUES ('{REV}','{CAND}',1,'{TENANT}','{SV}','{SUB}','{CMD}',encode(public.digest(convert_to($snap${SNAP}$snap$::jsonb::text,'UTF8'),'sha256'),'hex'),jsonb_build_array(jsonb_build_object('source_version_id','{SV}','start',0,'end',{len(SRC_TEXT.encode())})),$snap${SNAP}$snap$::jsonb,'STRUCTURE_VALIDATED');
INSERT INTO kdb_staging.review_work_item(review_work_item_id,candidate_revision_id,tenant_scope,correlation_id) VALUES ('{ITEM}','{REV}','{TENANT}','{CMD}');
INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at)
 SELECT '{DEC}','{REV}',c.content_sha256,'TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION',sv.rights_snapshot_sha256,repeat('d',64),'TEST_ONLY:signature',now() FROM kdb_staging.candidate_revision c JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id WHERE c.candidate_revision_id='{REV}';
INSERT INTO kdb_canonical.protocol(protocol_id,owning_module_ref,taxonomy_version_ref) VALUES ('{PROTO}','{MODULE}','{TAX}');
INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at)
 SELECT '{PV}','{PROTO}',1,'{REV}','{DEC}',content_sha256,$snap${SNAP}$snap$::jsonb,'{TAX}',now() FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{REV}';
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES ('{PV}','PUBLISHED','TEST_ONLY',now(),'{DEC}');
""")
        receipt = read_detail(NAME, PV, TENANT, SUBJECT, PURPOSE)
        assert receipt['status'] == 'SYNTHETIC_READ'
        positive = receipt['candidate']
        assert positive == read_detail(NAME, PV, TENANT, SUBJECT, PURPOSE)['candidate']
        schema = json.loads((ROOT / 'contracts/kdb/pd01_morning_checkin_detail.v1.schema.json').read_text())
        snapshot = positive['canonicalSnapshot']
        assert snapshot_schema_ok(snapshot)
        assert set(snapshot) == set(schema['required'])
        assert snapshot['schemaVersion'] == schema['properties']['schemaVersion']['const']
        assert snapshot['synthetic'] is True
        assert isinstance(snapshot['title'], str)
        assert all(isinstance(item, str) for item in snapshot['instructions'])
        contract = json.loads((ROOT / 'tests/kdb/fixtures/pd01_morning_checkin_detail_contract.v1.json').read_text())
        for key in ('protocolId', 'protocolVersionId', 'owningModuleId', 'taxonomyVersionId',
                    'relationIds', 'versionNo', 'sourceVersionId', 'candidateRevisionId',
                    'title', 'instruction', 'instructions', 'contentHash', 'canonicalSnapshot',
                    'taxonomyPath', 'lifecycle', 'rights', 'purpose', 'sourceStatus', 'trust'):
            assert positive[key] == contract[key], key
        assert positive['title'] == 'Morgen-Check-in'
        assert positive['instruction'] == 'Notiere eine Priorität für heute.'
        assert positive['provenance']['reviewDecision'] == 'APPROVED_FOR_PROMOTION'
        assert positive['protocolVersionId'] != PA05_PV
        assert positive['contentHash'] != contract['pa05Preservation']['contentHash']
        print('PD01_PG17 NETWORK_NONE / SQL_READ_RECONNECT PASS')
        print('PD01_RECEIPT ' + json.dumps(positive, sort_keys=True, ensure_ascii=False))
        pa05 = read_pa05(NAME.replace('pd01', 'pa05'), PA05_PV, PA05_TENANT, SUBJECT, PURPOSE)
        # PA05 adapter requires kdb-pa05-* container name; read through SQL as postgres then
        # compare the frozen PA05 contract from the same isolated database.
        pa05_row = json.loads(sql(
            f"SELECT pa05_test.read_catalog('{PA05_PV}','{PA05_TENANT}','{SUBJECT}','{PURPOSE}');",
            'pa05_fixture_reader').stdout)
        pa05_contract = json.loads((ROOT / 'tests/kdb/fixtures/pa05_catalog_contract.v1.json').read_text())
        for key in ('protocolId', 'protocolVersionId', 'owningModuleId', 'taxonomyVersionId',
                    'relationIds', 'versionNo', 'sourceVersionId', 'candidateRevisionId',
                    'contentHash', 'canonicalSnapshot', 'taxonomyPath', 'lifecycle', 'rights',
                    'purpose', 'sourceStatus', 'trust'):
            assert pa05_row[key] == pa05_contract[key], 'PA05 ' + key
        assert pa05_row['canonicalSnapshot'] == {'synthetic': True}
        assert pa05 == {'status': 'DENY', 'candidate': None}  # wrong container name on purpose
        print('PD01_PA05_SAME_DB_PRESERVED PASS')
        deny('pa05_version_as_pd01', read_detail(NAME, PA05_PV, TENANT, SUBJECT, PURPOSE))
        deny('literal_latest', read_detail(NAME, 'latest', TENANT, SUBJECT, PURPOSE))
        deny('non_uuid_latest', read_detail(NAME, 'LATEST', TENANT, SUBJECT, PURPOSE))
        negatives = {
            'draft': "DELETE FROM kdb_canonical.lifecycle_event WHERE protocol_version_id='%s';" % PV,
            'withdrawn': f"UPDATE kdb_canonical.lifecycle_event SET kind='WITHDRAWN' WHERE protocol_version_id='{PV}';",
            'unpublished': f"UPDATE kdb_canonical.lifecycle_event SET kind='REVALIDATION_REQUIRED' WHERE protocol_version_id='{PV}';",
            'missing_decision': f"UPDATE kdb_governance.human_review_decision SET decision='REJECTED' WHERE decision_id='{DEC}';",
            'taxonomy': f"UPDATE kdb_canonical.protocol SET owning_module_ref='orphan' WHERE protocol_id='{PROTO}';",
            'revoked': f"UPDATE kdb_governance.source SET rights_status='REVOKED' WHERE source_id='{SRC}';",
            'pending_rights': f"UPDATE kdb_governance.source SET rights_status='PENDING' WHERE source_id='{SRC}';",
            'stale_context': "UPDATE pd01_test.read_context SET observed_at=now()-interval '6 minutes';",
            'future_context': "UPDATE pd01_test.read_context SET observed_at=now()+interval '1 minute';",
            'expired_context': "UPDATE pd01_test.read_context SET valid_until=now()-interval '1 second';",
            'tampered_content': f"""UPDATE kdb_canonical.protocol_version SET canonical_snapshot='{{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"changed","instructions":["changed"]}}' WHERE protocol_version_id='{PV}';""",
            'stale_hash': f"""UPDATE kdb_canonical.protocol_version SET canonical_snapshot = canonical_snapshot || '{{"title":"Andere Überschrift"}}' WHERE protocol_version_id='{PV}';""",
            'tampered_source': f"UPDATE pd01_test.source_bytes SET contents=convert_to('tampered','UTF8') WHERE source_version_id='{SV}';",
            'tampered_rights': f"""UPDATE kdb_governance.source_version SET rights_snapshot='{{"rights_status":"ADMITTED","allowed_purposes":["personal-plan-preview","KNOWLEDGE_INTAKE"],"extra":true}}' WHERE source_version_id='{SV}';""",
            'tampered_evidence': f"""UPDATE kdb_staging.candidate_revision SET evidence_span_refs='[{{"bad":true}}]' WHERE candidate_revision_id='{REV}';""",
            'missing_title': f"""UPDATE kdb_canonical.protocol_version SET canonical_snapshot='{{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"","instructions":["Notiere eine Priorität für heute."]}}' WHERE protocol_version_id='{PV}';""",
            'stale_source': f"""INSERT INTO kdb_governance.source_version(source_version_id,source_id,tenant_scope,content_sha256,rights_snapshot,rights_snapshot_sha256,media_type,source_version_no,acquired_at)
                SELECT gen_random_uuid(),source_id,tenant_scope,repeat('e',64),rights_snapshot,rights_snapshot_sha256,media_type,2,now() FROM kdb_governance.source_version WHERE source_version_id='{SV}';""",
        }
        for name, mutation in negatives.items():
            out = sql('BEGIN; ' + mutation + ' SET LOCAL ROLE pd01_fixture_reader; ' + QUERY + ' ROLLBACK;').stdout.strip()
            if out:
                raise AssertionError(name + ' leaked candidate: ' + out)
            print('PD01_DENY ' + name + ' PASS')
        schema_negatives = {
            'extra_snapshot_key': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"Morgen-Check-in","instructions":["Notiere eine Priorität für heute."],"extra":true}',
            'title_not_string': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":1,"instructions":["Notiere eine Priorität für heute."]}',
            'instruction_not_string': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"Morgen-Check-in","instructions":[true]}',
            'synthetic_not_boolean': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":"true","title":"Morgen-Check-in","instructions":["Notiere eine Priorität für heute."]}',
            'empty_title_rebound': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"","instructions":["Notiere eine Priorität für heute."]}',
            'title_too_long': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"' + ('T' * 129) + '","instructions":["Notiere eine Priorität für heute."]}',
            'instruction_too_long': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"Morgen-Check-in","instructions":["' + ('I' * 257) + '"]}',
            'instructions_empty': '{"schemaVersion":"PD01_DETAIL_TEST_ONLY_V1","synthetic":true,"title":"Morgen-Check-in","instructions":[]}',
        }
        for name, snapshot_json in schema_negatives.items():
            out = sql('BEGIN; ' + rebind_snapshot(snapshot_json) +
                      ' SET LOCAL ROLE pd01_fixture_reader; ' + QUERY + ' ROLLBACK;').stdout.strip()
            if out:
                raise AssertionError(name + ' leaked candidate after hash rebind: ' + out)
            print('PD01_DENY ' + name + ' PASS')
        for name, query in {
            'wrong_tenant': QUERY.replace(TENANT, 'OTHER'),
            'wrong_subject': QUERY.replace(SUBJECT, 'OTHER'),
            'wrong_purpose': QUERY.replace(PURPOSE, 'OTHER'),
            'wrong_version': QUERY.replace(PV, PROTO),
            'pa05_id': QUERY.replace(PV, PA05_PV),
        }.items():
            if sql(query, 'pd01_fixture_reader').stdout.strip():
                raise AssertionError(name + ' leaked candidate')
            print('PD01_DENY ' + name + ' PASS')
        for tenant, subject, purpose in [('OTHER', SUBJECT, PURPOSE), (TENANT, 'OTHER', PURPOSE),
                                         (TENANT, SUBJECT, 'OTHER'), (TENANT, '', PURPOSE)]:
            deny('adapter_' + tenant + '_' + subject + '_' + purpose,
                 read_detail(NAME, PV, tenant, subject, purpose))
        sql(f"""
INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
 VALUES ('{V2_SUB}','{TENANT}','KDB','pd01-morning-checkin-v2',repeat('a',64),'TEST_ONLY:principal','TEST_ONLY:access','KNOWLEDGE_INTAKE','{SV}');
INSERT INTO kdb_staging.candidate_revision(candidate_revision_id,candidate_id,revision_no,tenant_scope,source_version_id,submission_id,proposal_command_id,content_sha256,evidence_span_refs,proposal_payload,validation_state)
 VALUES ('{V2_REV}','{V2_CAND}',1,'{TENANT}','{SV}','{V2_SUB}','{V2_CMD}',encode(public.digest(convert_to($snap${V2_SNAP}$snap$::jsonb::text,'UTF8'),'sha256'),'hex'),jsonb_build_array(jsonb_build_object('source_version_id','{SV}','start',0,'end',{len(SRC_TEXT.encode())})),$snap${V2_SNAP}$snap$::jsonb,'STRUCTURE_VALIDATED');
INSERT INTO kdb_staging.review_work_item(review_work_item_id,candidate_revision_id,tenant_scope,correlation_id) VALUES ('{V2_ITEM}','{V2_REV}','{TENANT}','{V2_CMD}');
INSERT INTO kdb_governance.human_review_decision(decision_id,candidate_revision_id,candidate_content_sha256,reviewer_principal_ref,access_decision_ref,decision,source_rights_digest,review_evidence_sha256,signed_decision_ref,decided_at)
 SELECT '{V2_DEC}','{V2_REV}',c.content_sha256,'TEST_ONLY:reviewer','TEST_ONLY:authority','APPROVED_FOR_PROMOTION',sv.rights_snapshot_sha256,repeat('d',64),'TEST_ONLY:signature',now() FROM kdb_staging.candidate_revision c JOIN kdb_governance.source_version sv ON sv.source_version_id=c.source_version_id WHERE c.candidate_revision_id='{V2_REV}';
INSERT INTO kdb_canonical.protocol_version(protocol_version_id,protocol_id,version_no,source_candidate_revision_id,human_decision_id,content_sha256,canonical_snapshot,taxonomy_version_ref,published_at)
 SELECT '{V2_PV}','{PROTO}',2,'{V2_REV}','{V2_DEC}',content_sha256,$snap${V2_SNAP}$snap$::jsonb,'{TAX}',now() FROM kdb_staging.candidate_revision WHERE candidate_revision_id='{V2_REV}';
INSERT INTO kdb_canonical.lifecycle_event(protocol_version_id,kind,reason_code,occurred_at,decision_ref) VALUES ('{V2_PV}','PUBLISHED','TEST_ONLY',now(),'{V2_DEC}');
""")
        still = read_detail(NAME, PV, TENANT, SUBJECT, PURPOSE)['candidate']
        assert still['protocolVersionId'] == PV
        assert still['title'] == 'Morgen-Check-in'
        assert still['instruction'] == 'Notiere eine Priorität für heute.'
        assert still['contentHash'] == positive['contentHash']
        decoy = read_detail(NAME, V2_PV, TENANT, SUBJECT, PURPOSE)['candidate']
        assert decoy['protocolVersionId'] == V2_PV
        assert decoy['title'] != still['title']
        assert still['title'] != decoy['title']
        print('PD01_EXACT_VERSION_NO_LATEST_SUBSTITUTION PASS')
        duplicate = sql(f"""INSERT INTO kdb_staging.submission(submission_id,tenant_scope,origin_owner,idempotency_key,request_sha256,principal_context_ref,access_decision_ref,purpose,source_version_id)
            SELECT gen_random_uuid(),tenant_scope,origin_owner,idempotency_key,repeat('f',64),principal_context_ref,access_decision_ref,purpose,source_version_id FROM kdb_staging.submission WHERE submission_id='{SUB}';""", check=False)
        assert duplicate.returncode != 0
        assert read_detail(NAME, PV, TENANT, SUBJECT, PURPOSE)['candidate']['canonicalSnapshot'] == positive['canonicalSnapshot']
        assert read_detail(NAME, PROTO, TENANT, SUBJECT, PURPOSE) == {'status': 'DENY', 'candidate': None}
        print('PD01_DENY duplicate_replay_and_stale_reference PASS')
        p = sql('SELECT * FROM kdb_canonical.protocol_version;', 'pd01_fixture_reader', check=False)
        if p.returncode == 0:
            raise AssertionError('reader has direct table access')
        print('PD01_DENY direct_table_access PASS')
        decisions = int(sql("SELECT count(*) FROM kdb_governance.human_review_decision;").stdout.strip())
        assert decisions == 3  # PA05 + PD01 v1 + PD01 v2 fixture rows only; no auto-approval
        print('PD01_NO_AUTO_HUMAN_APPROVAL PASS')
        run('docker', 'stop', NAME)
        deny('reader_unavailable', read_detail(NAME, PV, TENANT, SUBJECT, PURPOSE))
        assert_pa05_byte_exact()
        print('PD01_PA05_BYTE_EXACT_AFTER PASS')
    finally:
        if created:
            run('docker', 'rm', '-f', NAME)
            print('PD01_CONTAINER_REMOVED', NAME)


if __name__ == '__main__':
    main()
