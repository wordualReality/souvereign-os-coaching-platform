#!/usr/bin/env python3
from pathlib import Path
text=Path('tests/e2e/mvp-slice-01.spec.md').read_text().lower()
terms=['lead','discovery','offer','agreement','provisioning','coach assignment','journey','core access','delivery plan','member home','reflection','intervention','renewal']
missing=[t for t in terms if t not in text]
if missing: raise SystemExit('MVP Slice 01 skeleton missing: '+', '.join(missing))
print('PASS MVP Slice 01 skeleton coverage')
