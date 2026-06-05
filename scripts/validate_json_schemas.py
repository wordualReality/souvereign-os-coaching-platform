#!/usr/bin/env python3
import json
from pathlib import Path
from jsonschema import Draft202012Validator
count=0
for p in list(Path('contracts/events').rglob('*.json')) + list(Path('contracts/json-schema').rglob('*.json')) + [Path('contracts/asyncapi/project-b-events-v1.json')]:
    if not p.exists(): raise SystemExit(f'MISSING {p}')
    data=json.loads(p.read_text())
    if p.name.endswith('.schema.json') or 'schema' in p.name:
        Draft202012Validator.check_schema(data)
    count+=1
print(f'PASS JSON/schema parse + schema-check count={count}')
