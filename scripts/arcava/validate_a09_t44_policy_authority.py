#!/usr/bin/env python3
"""Offline denial verifier. No SQL execution or positive authority path."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SEED='database/policies/001_project_b_rls_seed.sql'
CASE='docs/arcava/admission/synthetic/A09-T44/case.json'
ENGINE='docs/arcava/admission/synthetic/A09-T44/engine.json'
PINS={SEED:'1d77f1e932fee3f9b15d9d64e6bb482983b234054b239e6c0d528e975337fe48',CASE:'2bf0272e23f827911bd1db06b45fcf354b4d5824cf772a5b0381aa001e228882',ENGINE:'f3f01c7d950f5b6f80d0b51e7e1969cc41b63cb40a0f3948531cdedc33b9cf69'}

def assess(root):
    root=root.resolve()
    hashes={}
    errors=[]
    contents={}
    for relative,expected in PINS.items():
        path=root/relative
        if not path.resolve().is_relative_to(root):
            errors.append('source_path_escape');continue
        if path.is_symlink() or not path.is_file():
            errors.append('missing_or_symlink_source:'+relative);continue
        payload=path.read_bytes()
        actual=hashlib.sha256(payload).hexdigest()
        hashes[relative]=actual
        contents[relative]=payload
        if actual!=expected: errors.append('source_drift:'+relative)
    reasons=['historical_seed_NOT_ACCEPTED','project_b_source_not_admitted_Arcava_owner_policy','trusted_owner_accepted_manifest_and_hash_absent','JWT_adaptation_incomplete','PUBLIC_default_ACL_and_foreign_denial_runtime_unproven']
    observations={}
    if CASE in contents:
        try:
            case=json.loads(contents[CASE])
            if case.get('historical_seed')!=SEED: errors.append('altered_source_location')
            if case.get('historical_seed_authority')!='NOT_ACCEPTED' or case.get('sql_apply')!='NOT_EXECUTED': errors.append('forged_authority_or_execution')
            if set(case)-{'case_id','units','fixture_class','entrypoint','historical_seed','historical_seed_authority','sql_apply','checks_prepared'}: errors.append('untrusted_case_fields')
        except (ValueError,AttributeError): errors.append('malformed_case')
    if SEED in contents:
        sql=contents[SEED].decode('utf-8',errors='replace').lower()
        observations={'project_b_reference':'project_b.' in sql,'adaptation_marker':'adapt jwt claim extraction' in sql,'using_true':'using (true)' in sql}
    return {'decision':'BLOCK_UNAPPROVED_FOREIGN_SEED','status':'OFFLINE_POLICY_AUTHORITY_DENIAL_VERIFIED' if not errors else 'FAIL_CLOSED_INPUT_REJECTED','reasons':reasons,'input_errors':errors,'source_sha256':hashes,'static_observations_only':observations,'SQL_EXECUTION':'NOT_EXECUTED','original_T44':'NOT_EXECUTED','security_acceptance':'NOT_GRANTED'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    result=assess(args.root)
    print(json.dumps(result,sort_keys=True))
    return 1 if result['input_errors'] else 0

if __name__=='__main__': raise SystemExit(main())
