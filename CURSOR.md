# Cursor Operating Entry

Cursor is a bounded repository executor, not an architecture or authorization authority.

## Required context

Before acting, read:

- `AGENTS.md`
- `SESSION_START.md`
- `docs/control/READ_FIRST.md`
- `docs/control/CURRENT_SOURCE_MANIFEST.md`
- `docs/control/AUTHORITY_AND_STOP_CONDITIONS.md`
- `docs/quality/DEFINITION_OF_READY.md`
- the packet-specific prompt and applicable `.cursor/rules/*.mdc`

## Current state

Only FPS-00C governance work is authorized on `chore/fps-00c-preimplementation-governance`. No product feature, SQL/migration, n8n workflow, deployment or production action is authorized.

## Required behavior

- Work on one isolated branch/worktree and one bounded packet.
- State base SHA, allowed paths, forbidden actions, tests and evidence before changes.
- Use current source precedence; do not implement from memory or old handoffs.
- Stop on conflicts, missing owner authority, unexplained worktree changes or out-of-scope paths.
- Run required positive and negative tests and return exact evidence.
- Issue one gate and exactly one successor; never continue automatically.

## Forbidden

- direct changes to `main`;
- inventing capabilities, endpoints, events, schemas or owner decisions;
- moving Core/Canonical truth into Project B;
- cross-tenant exposure or service-role leakage;
- direct n8n table access without an accepted ADR;
- claiming secure, compliant, production-ready or implemented without accepted execution evidence.