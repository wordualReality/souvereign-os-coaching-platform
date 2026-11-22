#!/usr/bin/env python3
"""Read-only physical subset verifier. Frozen pins are not runtime admission."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from arcava_local_admission import bind_contracts, EXPECTED_CONTRACTS

PIN_PATH='docs/arcava/admission/synthetic/A09-T04/byte-pins.json'
PIN_SHA='d1b3d4589b68ca9a7315e01be03cea947e7efbb2866c452d41399ee3ddea4b62'

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def physical(root):
    root=root.resolve()
    pins_path=root/PIN_PATH
    if not pins_path.is_file(): raise ValueError('missing_pins')
    if pins_path.is_symlink() or file_hash(pins_path)!=PIN_SHA:
        raise ValueError('frozen_pin_drift')
    pins=json.loads(pins_path.read_text())
    inventory=[]
    for pin in pins['pins']:
        path=root/pin['path']
        try: path.resolve().relative_to(root)
        except ValueError: raise ValueError('path_escape')
        if any(p.is_symlink() for p in [path,*path.parents] if p!=root and root in p.parents):
            raise ValueError('symlink_rejected')
        if not path.is_file(): raise ValueError('missing_physical_file')
        actual=file_hash(path)
        if actual!=pin['sha256']: raise ValueError('physical_byte_drift')
        inventory.append({**pin,'actual_sha256':actual})
    lines,code,reason=bind_contracts(root,pins)
    if code: raise ValueError(reason)
    schemas=[r for r in inventory if r['set']!='manifest']
    ids=sorted({r['contract_id'] for r in schemas if r['set']=='contract'})
    if len(schemas)!=16 or ids!=sorted(EXPECTED_CONTRACTS):
        raise ValueError('physical_inventory')
    return {'status':'PHYSICAL_SUBORACLE_PASS','schema_count':16,'contract_ids':ids,
            'inventory':inventory,'pin_file_sha256':PIN_SHA,
            'registry_48':'NOT_MATERIALIZED','family_16_compatibility':'UNVERIFIED',
            'original_T04':'NOT_EXECUTED','admission':'NOT_ADMITTED'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    try: result=physical(args.root)
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'status':'FAIL','reason':str(error)}))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
