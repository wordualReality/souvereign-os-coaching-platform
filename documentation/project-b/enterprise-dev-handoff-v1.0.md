# Enterprise Dev Handoff -- Project B v1.0

Date: 2026-07-01 | Status: YELLOW / CONTROLLED
Source: ProjectB_Final_DevHandoff_Bundle_v1_1_2026-06-04.zip

## Leading Truth Order
1. Project B Final Dev-Handoff Bundle v1.1
2. Journey Builder & Client Provisioning Hardening v1.1
3. Final Dev-Handoff Bundle v1.0 baseline
4. G1-G14 completion packs

## Control Status
- Sprint 0: FROZEN
- Broad UI Build: NOT AUTHORIZED
- P01: Manual Client Provisioning Controlled Slice ONLY
- DB-05: DELIVERED 2026-07-01
- VS-01: NOT VERIFIED

## Repo Contents
- database/migrations/001_project_b_baseline_schema.sql
- database/migrations/002_project_b_journey_provisioning_hardening.sql
- database/policies/001_project_b_rls_seed.sql
- prompts/cursor/ -- 40 Cursor prompts
- scripts/ -- validation suite
- contracts/ -- asyncapi, events, json-schema, openapi

## NOT in Repo (by design)
- canonical.* schema (DB Architect domain)
- Notion pipeline DBs (Ebene 1)
- n8n workflows (Ebene 1)
- protocol/exercise runtime tables

## Validation
bash: python scripts/validate_repo.py && npm run validate:all

## First Cursor Execution
prompts/cursor/PB-CURSOR-JH-001-MANUAL-CLIENT-PROVISIONING.md
See: architecture/p01-decoupling-decision.md for gate instruction.
