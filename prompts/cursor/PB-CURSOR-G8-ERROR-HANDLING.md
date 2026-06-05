# PB-CURSOR-G8-ERROR-HANDLING — Implement standardized error envelope and mappings

## Context

Use `ProjectB_DevHandoff_Completion_Pack_v0_4_G5_G9_2026-06-03/04_G8_Error_Handling_Matrix` as the controlling source. Also read G1–G4 capability, story and screen-state matrices.

## Allowed source truth

- G1–G4 Completion Pack v0.3
- This G5–G9 Completion Pack v0.4
- Final OpenAPI 3.1 Contract Pack
- Event Schema & Outbox Contract Pack
- Runtime Sequence & State Machine Pack
- repaired Data Model v1.1 from E2E Closure Bundle

## Do not touch

- Do not change product scope.
- Do not move Core entitlement/consent/routing truth into Project B.
- Do not move DB/Canonical taxonomy/protocol/source truth into Project B.
- Do not invent endpoints/events/tables without adding them to reconciliation artifacts.

## Required output

- files changed/created list
- tests added
- contract gap status
- audit/event behavior
- stop condition if architecture contradiction is found

## Definition of Done

The implementation artifact passes the matrix relevant to this prompt and does not create untracked ownership or contract drift.
