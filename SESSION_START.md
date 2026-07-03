# SESSION START -- Project B Sovereign OS Coaching Platform

Read this file FIRST. Every session. Every operator. No exceptions.
This file is the single entry point. It tells you where we are and what to do next.

## Current Control Status

Project B: YELLOW / CONTROLLED
Sprint 0: FROZEN / COMPLETE
P01 (Manual Client Provisioning): RELEASED -- canonical-decoupled
Broad UI Build: NOT AUTHORIZED
canonical.* physical build: BLOCKED -- awaiting AYDIN-GATE-01

## System Architecture

LAYER 1 -- Notion (Content Pipeline)
  27 protocol candidates, Gate A+B PASS
  Operator: Claude + Aydin | n8n: classix.app.n8n.cloud
  NOT Project B runtime. NOT your scope.

LAYER 2 -- Canonical DB (Supabase)
  canonical.* schema, DDL-01 DELIVERED, build BLOCKED
  Operator: DB Architect GPT | Supabase ref: zobjpmyccszkabybdmsf
  BLOCKED until AYDIN-GATE-01 approval phrase

LAYER 3 -- Project B App (this repo) <- YOU ARE HERE
  Next.js | Java 21 Spring Boot 3.5.x | Supabase PG
  Schemas: canonical (blocked) | project_b | core
  P01: tenant/account/client provisioning

## What You May Do Right Now

ALLOWED:
- Implement P01 Manual Client Provisioning via PB-CURSOR-JH-001
- Run validation scripts
- Read all files in repo
- Create documentation
- Local Supabase setup (project_b migrations only)

NOT ALLOWED -- STOP + create NEEDS_ALIGNMENT.md if needed:
- canonical.* access, migrations, or reads
- dev_staging.* from Project B code
- getProtocolDetail() (no approved canonical_ref yet)
- protocol_detail_projection
- PROJECT_B_SEED_ALLOWED / CANONICAL_APPROVED_EXPORT
- project_b.exercise_* tables
- Broad UI Build
- Remote Supabase push (local only until gate)

## Execution Order

Step 1: git status && npm run validate:all
Step 2: cat prompts/cursor/PB-CURSOR-MASTER-RULES.md
Step 3: cat prompts/cursor/PB-CURSOR-JH-001-MANUAL-CLIENT-PROVISIONING.md
Step 4: Report pre-change plan (files, tables, endpoints, no-canonical confirm)
Step 5: Implement P01
Step 6: npm run validate:all && python scripts/validate_mvp_slice_01.py
Step 7: Update LIVE STATUS -- no new Notion pages

## Stop Condition (Master Rule 7)

If any work would require touching the NOT ALLOWED list:
1. Create NEEDS_ALIGNMENT.md in repo root
2. Write: what you needed, why it conflicts, what decision is required
3. Stop. Do not continue.

## LIVE STATUS

https://app.notion.com/p/38be5a7ff397817f9161df25073033bb

## Key Architecture Documents

DB-05 CanonicalRef Model: https://app.notion.com/p/390e5a7ff39781399ff6ec6aedfd647c
DDL-01 Readiness Review:  https://app.notion.com/p/392e5a7ff3978133be82e78502ce7d21
FX-01 Fixture Pack:       https://app.notion.com/p/391e5a7ff39781709c69de7d3fbc9971
AT-05 Acceptance Tests:   https://app.notion.com/p/391e5a7ff3978189994dec151ee21cda
DB-04A Governance:        https://app.notion.com/p/38be5a7ff397816bbdfaecca97ed66df

## Validation Commands

python scripts/validate_repo.py
python scripts/validate_openapi.py
python scripts/validate_json_schemas.py
python scripts/validate_sql_static.py
python scripts/validate_rls_static.py
python scripts/validate_mvp_slice_01.py
npm run validate:all

## After P01 Is Complete

Update LIVE STATUS block with:
  P01 Manual Client Provisioning: COMPLETE
  Files changed: [list]
  Validation: npm run validate:all PASS, validate_mvp_slice_01.py PASS
  Date: [date]

Then wait for next instruction. Do not start Sprint 2 without explicit release.
