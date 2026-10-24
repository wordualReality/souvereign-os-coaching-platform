#!/usr/bin/env python3
from pathlib import Path
import re
files=[Path('database/migrations/001_project_b_baseline_schema.sql'), Path('database/migrations/002_project_b_journey_provisioning_hardening.sql')]
for p in files:
    txt=p.read_text().lower()
    assert 'create table' in txt, f'{p}: no create table'
    assert 'project_b.' in txt, f'{p}: no project_b schema/table references'
    assert 'drop schema' not in txt, f'{p}: destructive drop schema found'
    print(f'PASS SQL static migration check: {p} create_table_count={txt.count("create table")}')
kdb_m01=[
    Path('database/migrations/kdb/20261023140000__kdb_m01_001__core_foundation.sql'),
    Path('database/migrations/kdb/20261023140100__kdb_m01_002__security_boundary.sql'),
    Path('database/migrations/kdb/20261023140200__kdb_m01_003__api_boundary.sql'),
    Path('database/migrations/kdb/20261023140300__kdb_m01_004__indexes_idempotency.sql'),
    Path('database/migrations/kdb/20261024180000__kdb_m01_p2__forward_recovery_candidate.sql'),
]
legacy_ddl=re.compile(r'(?im)^\s*(?:create|alter|drop)\s+(?:table|schema)\s+(?:canonical|dev_staging|public)\b')
for pth in kdb_m01:
    txt=pth.read_text()
    assert 'zobjpmyccszkabybdmsf' not in txt.lower(), f'{pth}: must not target integration project'
    assert not legacy_ddl.search(txt), f'{pth}: legacy schema DDL forbidden'
    print(f'PASS SQL static kdb-m01 check: {pth}')
core=kdb_m01[0].read_text()
assert 'CREATE SCHEMA kdb_canonical;' in core
assert 'CREATE SCHEMA kdb_staging;' in core
assert 'CREATE SCHEMA kdb_governance;' in core
assert 'CREATE SCHEMA kdb_ops;' in core
assert 'CREATE SCHEMA canonical;' not in core
assert 'kdb_api' not in core
assert 'NOBYPASSRLS' in kdb_m01[1].read_text()
assert 'kdb_ops.ingest_source' in kdb_m01[2].read_text()
assert 'kdb_api.submit_ingestion_candidate' not in kdb_m01[2].read_text()
assert 'NOT_AUTHORIZED_FOR_APPLY' in kdb_m01[3].read_text()
assert 'NOT_AUTHORIZED_FOR_APPLY' in kdb_m01[4].read_text()
assert 'canonical.protocol' in kdb_m01[4].read_text()
assert 'CREATE SCHEMA canonical' not in kdb_m01[4].read_text()
assert 'NOT_AUTHORIZED_FOR_APPLY' in kdb_m01[4].read_text()
print('NOTE: true SQL dry-run requires Postgres/Supabase CLI; this static check is the sandbox fallback.')
