# Sovereign OS Project B — Agent Authority

Status: CURRENT for FPS-00C governance branch.

## Mission

Work only on the single bounded packet explicitly authorized by the accepted predecessor gate. This repository contains Project B application/runtime concerns and the Database/Canonical lane in one ordered implementation repository, but ownership remains separate.

## Source order

1. Executed evidence accepted by a gate.
2. Accepted owner decisions, ADRs, producer-owned contracts and cross-lane resolutions.
3. Repository reality at the exact base SHA.
4. Current Project B system documentation and source manifests.
5. Official current technical documentation.
6. Historical handoffs and community prompting resources.

Lower-precedence material cannot override higher-precedence material.

## Mandatory start

Before any work, read:

- `docs/control/READ_FIRST.md`
- `docs/control/CURRENT_SOURCE_MANIFEST.md`
- `docs/control/AUTHORITY_AND_STOP_CONDITIONS.md`
- `docs/quality/DEFINITION_OF_READY.md`
- the packet-specific prompt and applicable `.cursor/rules/*.mdc`

Record repository, branch, base SHA, worktree state, allowed paths, forbidden actions, tests and evidence destination.

## Owner lanes

- **Project B:** application domain, APIs, web experience, tenant/coach/client/journey runtime.
- **Database/Canonical:** canonical/KDB schemas, migrations, RLS/RPC semantics, provenance, rights and publication controls.
- **Shared Database Control:** migration ordering, shared roles, common RLS conventions, audit/outbox conventions and environment baseline.

One packet has one writer. Project B must not change KDB-owned migration or canonical paths during a Database/Canonical packet, and the DB lane must not redesign Project B product behavior.

## Non-negotiable controls

- No direct work on `main`.
- No feature, SQL, workflow, deployment or production action without an accepted gate naming it.
- No silent architecture reopening.
- No cross-tenant exposure, service-role leakage or client access to raw staging/canonical candidates.
- No autonomous canonical promotion.
- n8n may use only approved APIs, events or restricted RPCs; direct table access is forbidden unless an accepted ADR explicitly changes this.
- A prompt, agent or passing static validator cannot self-declare production readiness.

## Return and successor

Every packet returns commands, exit codes, changed files, base/result SHA, tests, evidence, deviations, blockers and an allowed gate value. Generate exactly one successor from the accepted return, evidence, review, blockers and lessons learned. Stop after the gate.