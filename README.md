# Project B Repository Cut v0.1

Status: repository cut from `ProjectB_Final_DevHandoff_Bundle_v1_1_2026-06-04.zip`.

This repository is the transition from architecture truth to technical execution. It contains contracts, database migrations, RLS seeds, app/API skeletons, validation scripts, CI wiring, traceability matrices, Cursor prompts and MVP Slice 01 test skeleton.

## Leading truth order

1. Project B Final Dev-Handoff Bundle v1.1
2. Journey Builder & Client Provisioning Hardening v1.1
3. Final Dev-Handoff Bundle v1.0 baseline
4. G1-G14 completion packs

## Validate locally

```bash
python scripts/validate_repo.py
python scripts/validate_openapi.py
python scripts/validate_json_schemas.py
python scripts/validate_sql_static.py
python scripts/validate_rls_static.py
python scripts/validate_mvp_slice_01.py
```

## First Cursor execution

Start with:

`prompts/cursor/PB-CURSOR-JH-001-MANUAL-CLIENT-PROVISIONING.md`

Then continue through the v1.1 hardening prompts before baseline v1.0 implementation prompts.
