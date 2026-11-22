#!/usr/bin/env python3
"""Read-only E0 source/ledger consistency check. Not runtime or security acceptance.

Default: fetch immutable producer source with the existing gh read credential.
--producer-cache accepts the list of already fetched {path,text} source objects;
all bytes must still match the ledger's SHA256 and Git blob IDs. No secrets needed.
"""
import argparse
import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess


def check():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer-cache', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    ledger_path = Path(__file__).with_name('trusted-context-source-readiness-e0.json')
    ledger = json.loads(ledger_path.read_text())
    base = ledger['base_sha']
    producer = ledger['producer_repository']
    source = ledger['producer_source_sha']

    def git(*argv):
        return subprocess.check_output(['git', '-C', str(root), *argv])

    def api(route):
        return json.loads(subprocess.check_output(['gh', 'api', route]))

    for item in ledger['local_sources']:
        data = git('show', base + ':' + item['path'])
        assert data == (root / item['path']).read_bytes(), item['path'] + ': local source drift'
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path'] + ': hash mismatch'
    inventory = git('ls-tree', '-r', '--name-only', base, 'contracts').decode().splitlines()
    assert inventory == ledger['local_contract_inventory']['tracked_paths']
    assert not any(re.search(r'ct-shc-00[1-5]', p, re.I) for p in inventory)
    manifest_local = json.loads((root / 'contracts/arcava/contract-manifest.json').read_text())
    assert not any(c['contract_id'].startswith('CT-SHC-') for c in manifest_local['contracts'])

    if args.producer_cache:
        sources = {x['path']: x['text'].encode() for x in json.loads(args.producer_cache.read_text())}
    else:
        def fetch(item):
            response = api(f'repos/{producer}/contents/{item["path"]}?ref={source}')
            return item['path'], base64.b64decode(response['content'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            sources = dict(pool.map(fetch, ledger['producer_sources']))
    for item in ledger['producer_sources']:
        data = sources[item['path']]
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path'] + ': producer hash mismatch'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert blob == item['git_blob_sha'], item['path'] + ': producer Git blob mismatch'
    producer_manifest = json.loads(sources['contracts/manifest.json'])
    entries = {e['logical_id']: e for e in producer_manifest['entries']}
    assert {c['contract_id'] for c in ledger['contracts']} == {f'CT-SHC-00{i}' for i in range(1, 6)}
    for contract in ledger['contracts']:
        entry = entries[contract['contract_id']]
        assert entry == contract['manifest_entry']
        data = sources[entry['path']]
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
        schema = json.loads(data)
        assert schema['x-sovereign-contract'] == contract['schema_metadata']
        assert schema['x-sovereign-contract']['logical_id'] == entry['logical_id']
        assert schema['x-sovereign-contract']['schema_version'] == entry['schema_version']
        assert schema['x-sovereign-contract']['producer'] == entry['producer']
        assert schema['$defs']['request']['properties']['payload'] == contract['request_payload']
        response = schema['$defs']['response']
        assert response['properties']['payload'] == contract['response_payload']
        assert response['required'] == contract['response_envelope_required']
        assert sorted(set(response['properties']) - set(response['required'])) == contract['response_envelope_optional']
        assert contract['producer_authority_status'] == 'UNVERIFIED_FOR_ARCAVA'
    proof = 'contracts/piac-decision-proof/v1/proof-envelope.schema.json'
    pin = 'contracts/piac-decision-proof/v1/proof-envelope.schema.sha256'
    assert hashlib.sha256(sources[proof]).hexdigest() == sources[pin].decode().strip() == ledger['proof_boundary']['schema_sha256']
    verifier = sources['services/runtime/src/main/java/io/sovereignos/sharedcore/identity/proof/PiacDecisionProofVerifier.java'].decode()
    assert 'Operation.KDB_SOURCE_INTAKE.name()' in verifier and 'SENSITIVE_CLIENT_READ' not in verifier
    authority = sources['services/runtime/src/main/java/io/sovereignos/sharedcore/identity/proof/UnconfiguredProofAuthority.java'].decode()
    assert 'AUTHORITY_NOT_CONFIGURED' in authority

    trees = {}
    for snapshot in ledger['additional_repo_snapshots']:
        tree = api(f'repos/{producer}/git/trees/{snapshot["sha"]}?recursive=1')
        assert not tree.get('truncated'), 'incomplete producer tree'
        trees[snapshot['branch']] = {e['path']: e['sha'] for e in tree['tree'] if e['type'] == 'blob'}
    assert not any(re.search(r'ct-shc-00[1-5]', p, re.I) for p in trees['main'])
    apb = trees['impl/sov-apb-p04-local-dst-window-20261105']
    for item in ledger['producer_sources']:
        if item['path'].startswith('contracts/shared-core/') or item['path'].endswith('PiacDecisionProofVerifier.java'):
            assert apb[item['path']] == item['git_blob_sha']

    for item in ledger['drive_sources']:
        assert hashlib.sha256('\n'.join(item['excerpts']).encode()).hexdigest() == item['excerpt_utf8_sha256']
    context = (root / 'services/api/src/main/java/com/projectb/api/arcava/security/TrustedRequestContext.java').read_text()
    gates = re.search(r'enum Gate \{([^}]+)\}', context).group(1)
    assert {g.strip() for g in gates.split(',')} == {g['gate'] for g in ledger['gates']}
    evidence = re.search(r'record Evidence\((.*?)\) \{', context, re.S).group(1)
    assert [field.strip().split()[-1] for field in evidence.split(',')] == ledger['local_context_boundary']['evidence_fields']
    required = {'issuer','audience','principal','tenant','client_subject','resource','purpose','operation','revision','effectiveAt','expiresAt','revokedAt','policy_decision_refs','contract_version_checksum','backend_context_source'}
    for gate in ledger['gates']:
        assert set(gate['field_obligations']) == required
        assert all(value['status'] in {'VERIFIED','UNVERIFIED','ABSENT'} for value in gate['field_obligations'].values())
        assert gate['readiness'] == 'UNVERIFIED'
    guard = (root / 'services/api/src/main/java/com/projectb/api/arcava/security/OwnerGuard.java').read_text()
    assert 'public OwnerGuard(Clock clock) { this(clock, request -> null); }' in guard
    assert 'if (context==null) return deny(Reason.PIAC_NOT_CONNECTED);' in guard
    assert 'new TrustedRequestContext(' not in git('grep', '-h', '-F', 'TrustedRequestContext', base, '--', 'services/api/src/main/java').decode()
    assert ledger['gate_record']['STATUS'] == 'OPEN_UNVERIFIED'
    assert ledger['gate_record']['BLOCKER_ID'] == ledger['blocker']['id'] == 'BL-ARC-01'
    assert ledger['adoption']['CL-GATE-CLOSURE-20261105-01'] == 'ACKNOWLEDGED_AND_APPLIED'
    assert ledger['formal_gates_closed'] == []
    assert ledger['test_disposition']['maven_runtime'] == 'NOT_EXECUTED in this packet'
    print(json.dumps({'result':'PASS_SOURCE_CONSISTENCY_ONLY','contracts':5,'manifest_matches':5,'gate_rows':7,
                      'producer_files_hashed':len(ledger['producer_sources']),'local_sources_hashed':len(ledger['local_sources']),
                      'runtime_tests':'NOT_EXECUTED','Q2':'OPEN_UNVERIFIED','BL-ARC-01':'OPEN'}))


if __name__ == '__main__':
    check()
