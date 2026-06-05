#!/usr/bin/env python3
import json, yaml, sys
from pathlib import Path
files=[Path('contracts/openapi/project-b-v1.json'), Path('contracts/openapi/project-b-v1.1-overlay.json'), Path('contracts/openapi/project-b-v1.yaml')]
for p in files:
    if not p.exists(): raise SystemExit(f'MISSING {p}')
    data=json.loads(p.read_text()) if p.suffix=='.json' else yaml.safe_load(p.read_text())
    assert str(data.get('openapi','')).startswith('3.1'), f'{p}: not OpenAPI 3.1'
    assert isinstance(data.get('paths'), dict), f'{p}: missing paths'
    print(f'PASS OpenAPI structural check: {p} paths={len(data["paths"])}')
# overlay must contain hardening endpoints
overlay=json.loads(Path('contracts/openapi/project-b-v1.1-overlay.json').read_text())
required=['/tenants/{tenantId}/clients:provision-draft','/tenants/{tenantId}/journey-templates','/tenants/{tenantId}/cohorts','/tenants/{tenantId}/journeys/{journeyId}/branch-rules']
for e in required:
    assert e in overlay['paths'], f'overlay missing {e}'
print('PASS OpenAPI overlay hardening endpoint check')
