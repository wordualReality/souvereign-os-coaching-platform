#!/usr/bin/env python3
from pathlib import Path
required=[
 'README.md','CURSOR.md','CLAUDE.md','.github/workflows/ci.yml',
 'contracts/openapi/project-b-v1.json','contracts/openapi/project-b-v1.1-overlay.json',
 'contracts/asyncapi/project-b-events-v1.json','database/migrations/001_project_b_baseline_schema.sql',
 'database/migrations/002_project_b_journey_provisioning_hardening.sql',
 'database/policies/001_project_b_rls_seed.sql','apps/web/app/admin/provisioning/page.tsx',
 'apps/web/app/coach/journeys/page.tsx','apps/web/app/client/member-home/page.tsx',
 'tests/e2e/mvp-slice-01.spec.md','prompts/cursor/PB-CURSOR-JH-001-MANUAL-CLIENT-PROVISIONING.md'
]
missing=[x for x in required if not Path(x).exists()]
if missing: raise SystemExit('MISSING required repo files: '+', '.join(missing))
print(f'PASS repo required-file check count={len(required)}')
