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
]
for p in kdb_m01:
    txt=p.read_text().lower()
    assert p.exists(), f'{p}: missing'
    assert 'drop schema canonical' not in txt, f'{p}: refuses dropping canonical'
    assert 'zobjpmyccszkabybdmsf' not in txt, f'{p}: must not target integration project'
    print(f'PASS SQL static kdb-m01 check: {p}')
core=kdb_m01[0].read_text().lower()
assert 'create table' in core and 'canonical.' in core
sec=kdb_m01[1].read_text().lower()
assert 'create policy' in sec and 'row level security' in sec
api=kdb_m01[2].read_text().lower()
assert 'kdb_api.submit_ingestion_candidate' in api
idx=kdb_m01[3].read_text().lower()
assert 'create index' in idx and 'create table' not in idx
print('NOTE: true SQL dry-run requires Postgres/Supabase CLI; this static check is the sandbox fallback.')
