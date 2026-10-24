#!/usr/bin/env python3
import json, hashlib, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT=Path(__file__).resolve().parents[2]
CASES=ROOT/'tests/arcava/contracts/arc_p16_cases.json'
MANIFEST=ROOT/'contracts/arcava/contract-manifest.json'
ALLOW=[
'contracts/arcava/types/1.0/QueryEnvelope.schema.json','contracts/arcava/types/1.0/ResponseEnvelope.schema.json','contracts/arcava/types/1.0/EventEnvelope.schema.json',
'contracts/arcava/CT-ARC-002/1.0/request.schema.json','contracts/arcava/CT-ARC-002/1.0/result.schema.json','contracts/arcava/CT-ARC-002/1.0/error.schema.json',
'contracts/arcava/CT-ARC-003/1.0/request.schema.json','contracts/arcava/CT-ARC-003/1.0/result.schema.json','contracts/arcava/CT-ARC-003/1.0/error.schema.json',
'contracts/arcava/CT-ARC-004/1.0/request.schema.json','contracts/arcava/CT-ARC-004/1.0/result.schema.json','contracts/arcava/CT-ARC-004/1.0/error.schema.json',
'contracts/arcava/CT-ARC-R03-REM-001/1.0/request.schema.json','contracts/arcava/CT-ARC-R03-REM-001/1.0/result.schema.json','contracts/arcava/CT-ARC-R03-REM-001/1.0/event.schema.json','contracts/arcava/CT-ARC-R03-REM-001/1.0/error.schema.json',
'contracts/arcava/contract-manifest.json','tests/arcava/contracts/arc_p16_cases.json','scripts/arcava/validate_arc_p16.py','docs/traceability/ARC-P16-sov-priority-producer-contract-physicalization.md','docs/arcava/operations/evidence/ARC-P16/receipt.json','docs/arcava/operations/evidence/ARC-P16/test-results.json','docs/arcava/operations/evidence/ARC-P16/source-extract.txt','docs/arcava/operations/evidence/ARC-P16/toolchain-lock.txt']
SCHEMAS=[p for p in ALLOW if p.endswith('.schema.json')]

def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()

def emit(results, expected_groups, expected_subcases):
    passed=sum(1 for r in results if r['pass'])
    failed=len(results)-passed
    groups=len(set(r['group_id'] for r in results))
    out={'package':'ARC-P16','groups':groups,'subcases':len(results),'pass':passed,'fail':failed,'results':results}
    print(json.dumps(out,separators=(',',':')))
    return 0 if groups==expected_groups and len(results)==expected_subcases and failed==0 else 1

def main():
    plan=json.loads(CASES.read_text())
    expected_groups=plan['frozen_counts']['groups']; expected_subcases=plan['frozen_counts']['subcases']
    docs={p:json.loads((ROOT/p).read_text()) for p in SCHEMAS}
    registry=Registry()
    for p,d in docs.items(): registry=registry.with_resource(d['$id'],Resource.from_contents(d))
    fc=FormatChecker(); results=[]
    def rec(gid,cid,ok,detail=''):
        results.append({'group_id':gid,'case_id':cid,'pass':bool(ok),'detail':detail})
    # G01 schema self-validity
    for i,p in enumerate(SCHEMAS,1):
        try: Draft202012Validator.check_schema(docs[p]); rec('P16-G01',f'P16-C01-{i:02d}',True,p)
        except Exception as e: rec('P16-G01',f'P16-C01-{i:02d}',False,str(e))
    # G02 manifest hashes
    m=json.loads(MANIFEST.read_text()); mapped={}
    for x in m['common_components']: mapped[x['path']]=x['sha256']
    for c in m['contracts']:
        for x in c['physical_schemas']: mapped[x['path']]=x['sha256']
    for i,p in enumerate(SCHEMAS,1): rec('P16-G02',f'P16-C02-{i:02d}',mapped.get(p)==sha(p),p)
    # functional G03-G10
    for group in plan['functional_groups']:
        gid=group['group_id']
        for c in group['cases']:
            schema=docs[c['schema_path']]
            v=Draft202012Validator(schema,registry=registry,format_checker=fc)
            valid=not any(v.iter_errors(c['instance']))
            rec(gid,c['case_id'],valid==c['expected_valid'],f"actual_valid={valid}")
    # G11 abstract direct schemas must reject any direct instance, while defs remain referenced
    for i,p in enumerate(['contracts/arcava/types/1.0/QueryEnvelope.schema.json','contracts/arcava/types/1.0/ResponseEnvelope.schema.json','contracts/arcava/types/1.0/EventEnvelope.schema.json'],1):
        v=Draft202012Validator(docs[p],registry=registry,format_checker=fc)
        rec('P16-G11',f'P16-C11-{i:02d}',not v.is_valid({}),p)
    # G12 manifest semantics
    rec('P16-G12','P16-C12-01',m.get('producer')=='ARCAVA','producer')
    rec('P16-G12','P16-C12-02',all(c.get('profile_version')=='1.0' for c in m['contracts']),'profile-version')
    rec('P16-G12','P16-C12-03',all(c.get('runtime_producer_ready') is False for c in m['contracts']),'runtime-not-ready')
    rec('P16-G12','P16-C12-04',{c['contract_id'] for c in m['contracts']}=={'CT-ARC-002','CT-ARC-003','CT-ARC-004','CT-ARC-R03-REM-001'},'exact-contract-set')
    # G13 source/global invariants from package evidence text
    src=(ROOT/'docs/arcava/operations/evidence/ARC-P16/source-extract.txt').read_text()
    tr=(ROOT/'docs/traceability/ARC-P16-sov-priority-producer-contract-physicalization.md').read_text()
    rec('P16-G13','P16-C13-01','86 = 47 P0 + 39 P1' in src,'baseline')
    rec('P16-G13','P16-C13-02','Food Scan × Dosha AI remains DEFERRED' in src,'food-dosha')
    rec('P16-G13','P16-C13-03','PHYSICAL_SCHEMA_PRESENT_AND_CHECKSUMMED' in tr,'physical-status-boundary')
    rec('P16-G13','P16-C13-04','RUNTIME_PRODUCER_READY' in tr and 'does not establish' in tr,'runtime-nonoverclaim')
    rec('P16-G13','P16-C13-05','CommandEnvelope remains later ARC10-T010 scope' in tr,'command-envelope-deferred')
    # G14 exact file allowlist
    actual=sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file())
    rec('P16-G14','P16-C14-01',actual==sorted(ALLOW),f'actual={len(actual)} expected={len(ALLOW)}')
    return emit(results,expected_groups,expected_subcases)

if __name__=='__main__': sys.exit(main())
