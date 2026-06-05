#!/usr/bin/env python3
from pathlib import Path
p=Path('database/policies/001_project_b_rls_seed.sql')
txt=p.read_text().lower()
assert 'row level security' in txt or 'enable row level security' in txt, 'RLS enable statement missing'
assert 'create policy' in txt, 'create policy missing'
assert 'tenant' in txt, 'tenant context missing'
print(f'PASS RLS static check: policies={txt.count("create policy")}')
