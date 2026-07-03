# Build Workflow -- Project B Sovereign OS

This document describes how the automated build workflow operates.
Operators follow this. Aydin approves gates. Nothing else required from Aydin between gates.

## Workflow Model

GATE CHECK -> OPERATOR READS SESSION_START.md -> EXECUTES CURRENT BLOCK
    |                                                    |
    v                                         STOP? -> NEEDS_ALIGNMENT.md
VALIDATION RUNS AUTOMATICALLY
    |
    v
LIVE STATUS UPDATED BY OPERATOR
    |
    v
AYDIN REVIEWS LIVE STATUS (async)
    |
    v
NEXT GATE RELEASED (or blocked)

Aydin's only recurring action: read LIVE STATUS, approve or block next gate.

## Current Active Tracks

Track B -- P01 App Build (ACTIVE NOW)
  [RELEASED] PB-CURSOR-JH-001 Manual Client Provisioning
    -> validate:all PASS + validate_mvp_slice_01.py PASS
    -> [GATE: P01 tester-ready smoke test -- Aydin approves]
    -> [FUTURE] PB-CURSOR-JH-002 and subsequent prompts

Track A -- Canonical Build (BLOCKED)
  [BLOCKED] AYDIN-GATE-01 required:
    Say exactly: AYDIN APPROVES DDL-01 FOR LOCAL MIGRATION DRAFT ONLY
    -> DB Architect drafts local migrations M0-M7
    -> Local Supabase test (Cowork)
    -> [GATE: local evidence] Aydin approves remote push
    -> Gate C (Source Resolution) runs
    -> Gate D (Safety Review) -- ABSOLUTE needs external reviewer
    -> Gate E (Canonical Promotion)
    -> VS-01 verified green
    -> getProtocolDetail() available to Project B

## Who Does What

P01 implementation:         App Builder GPT + Cursor  (released now)
Local Supabase setup:       Cowork                    (after P01 or parallel)
canonical.* migrations:     DB Architect GPT          (after AYDIN-GATE-01)
Gate C/D execution:         Aydin + script            (after DDL local test)
Notion content pipeline:    Claude autonomous         (ongoing)
Gate approvals:             Aydin only                (async, when notified)

## Aydin's Gate Vocabulary

Local canonical migration:  AYDIN APPROVES DDL-01 FOR LOCAL MIGRATION DRAFT ONLY
Remote Supabase push:       AYDIN APPROVES REMOTE SUPABASE PUSH AFTER LOCAL EVIDENCE
Broad UI Build:             AYDIN RELEASES BROAD UI BUILD
VS-01 green:                Automatic after canonical + validation

No other phrases open these gates.

## Validation Is the Gate

Every block ends with validation. Failure = block stays blocked.
npm run validate:all must be exit 0 before any merge.
