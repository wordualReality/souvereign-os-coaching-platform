# Sovereign OS — Project B Coaching Platform

Status: **PRE-IMPLEMENTATION GOVERNANCE**. The repository contains architecture/contract/database/application skeletons and validation assets. It is not evidence of a completed or deployed application.

## Current implementation authority

The current bounded block is FPS-00C: repository governance, Cursor Rules, source precedence, standards, Definition of Ready/Done, evidence and traceability controls.

No feature implementation, SQL/migration, workflow activation, deployment or production access is authorized until the FPS-00C pull request is independently reviewed and accepted.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/control/READ_FIRST.md`.
3. Read `docs/control/CURRENT_SOURCE_MANIFEST.md` and `docs/control/SUPERSESSION_REGISTER.md`.
4. Read `docs/quality/DEFINITION_OF_READY.md` and the packet-specific prompt.
5. Work on one isolated branch or worktree and return evidence under `docs/evidence/EVIDENCE_RETURN_PROTOCOL.md`.

## Source precedence

1. Accepted executed evidence.
2. Accepted owner decisions, ADRs, gates and producer-owned contracts.
3. Exact repository reality at the base SHA.
4. PB-RDH-09 integrated system documentation and current supporting packs.
5. Official current technical documentation.
6. Historical handoffs and community prompt resources.

The earlier v1.0/v1.1 handoff order and direct P01 start instruction are superseded for implementation control.

## Repository ownership

- Project B owns tenant, coach, client, journey, assignment, enrollment, delivery, reflection/progress and application experience.
- Database/Canonical shares this repository for the bounded sprint but remains a separate owner lane and sole writer for KDB-owned migrations/canonical semantics during its packets.
- Shared Database Control governs ordered migrations, shared roles, RLS conventions, audit/outbox conventions and environment baseline.

## Validation

The existing validators perform structural/static checks. Run them as required, but do not treat them as proof of builds, runtime behavior, tenant isolation, migration execution, workflow execution or deployment readiness.

```bash
npm run validate:all
```

## Control sources

- Final sprint workspace: https://drive.google.com/drive/folders/1ikUNh1RGEzWLxC6caunmbRLFjgW3ojjS
- Shared three-lane register: https://docs.google.com/document/d/1AYXt0qswYMgCBKB_VZzKea03OsRrF2jQCG0Ld2tlUrw/edit
- Final production masterprompt: https://docs.google.com/document/d/1Qd2p3qFIZfrJ_dp8w6d3Nhm0ybfdVV_2x6mDrsLUA-Y/edit

Git is implementation truth. Local/CI execution is proof. Drive/Notion are durable documentation and control planes.