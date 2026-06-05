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
print('NOTE: true SQL dry-run requires Postgres/Supabase CLI; this static check is the sandbox fallback.')
