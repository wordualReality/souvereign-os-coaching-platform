#!/usr/bin/env python3
"""Offline byte-bound candidate validator; hashes confer no approval."""
import argparse
import hashlib
import json

PINS = ('c9fce88492d96aa318da94251bbdf7b2bbb75be7fe5375c240149e343047ce14',
        'be1f8209c39324dbf7c66aa09906f4c463edb5340ebbc619a503e6999c53cfd5')

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def validate(manifest,matrix):
    if manifest.get('status')!='CANDIDATE' or manifest.get('approval')!='NOT_APPROVED' or manifest.get('authority')!='NONE':
        raise ValueError('forged_approval')
    if (manifest.get('clock'),manifest.get('seed'),manifest.get('timezone')) != ('2026-11-02T00:00:00Z',0,'Europe/Berlin'):
        raise ValueError('clock_seed_timezone')
    if matrix.get('admission')!='NOT_ADMITTED' or matrix.get('real_evidence')!='0/86':
        raise ValueError('admission_claim')
    rows=matrix.get('tests',[])
    if [r.get('id') for r in rows]!=['A09-T%02d'%n for n in range(1,49)]:
        raise ValueError('test_inventory_order')
    slots=manifest.get('slots',[])
    ids=[s.get('id') for s in slots]
    if len(ids)!=14 or len(set(ids))!=14:
        raise ValueError('slot_inventory')
    for slot in slots:
        if not slot.get('binding') or not slot.get('source') or slot.get('status') not in ('IMPLEMENTED_SYNTHETIC','NOT_MATERIALIZED','DEPENDS_ON_NONOWNER'):
            raise ValueError('slot_binding')
    for row in rows:
        if not row.get('units') or not row.get('oracle') or not row.get('source') or any(s not in ids for s in row.get('fixture_slots',[])):
            raise ValueError('test_binding')
    hashes=(sha(manifest),sha(matrix))
    if hashes!=PINS:
        raise ValueError('frozen_candidate_content_drift')
    return hashes

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--matrix',required=True)
    args=parser.parse_args()
    try:
        with open(args.manifest) as stream: manifest=json.load(stream)
        with open(args.matrix) as stream: matrix=json.load(stream)
        hashes=validate(manifest,matrix)
    except (ValueError,KeyError,TypeError,OSError) as error:
        print('FAIL',error)
        return 1
    print('PASS CANDIDATE_ONLY manifest_sha256='+hashes[0]+' matrix_sha256='+hashes[1])
    return 0

if __name__=='__main__':
    raise SystemExit(main())
