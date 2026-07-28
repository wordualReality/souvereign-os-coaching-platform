# Current Source Manifest

Version: FPS-00C / 2026-07-29

## Authority tiers

### Tier 1 — Executed and accepted evidence

- Exact repository state and accepted local/CI command evidence.
- Accepted database, workflow and runtime evidence when later gates authorize it.

### Tier 2 — Current decisions and gates

- `THREE-LANE-IMPLEMENTATION-KICKOFF-01` v1.2 or later.
- `SOVEREIGN OS IMPLEMENTATION KICKOFF — Cross-Lane Repository, Tooling and Conflict Alignment` v1.1 or later.
- `PROJECT-B CROSS-LANE-CONFLICT-RESOLUTION-RETURN-01`.
- Accepted owner-lane ADRs, returns and producer-owned contracts.

### Tier 3 — Current implementation control

- `PROJECT-B IMPLEMENTATION CONTROL MASTERPROMPT — Minimal-Input Recursive Delivery` v1.1.
- `PROJECT-B-FINAL-PRODUCTION-SPRINT-01 Recursive Finish and Park` v1.1.
- `SOVEREIGN-OS-PROMPT-ENGINEERING-STANDARD-01` v1.0.
- Repository `AGENTS.md`, `WORKFLOW.md`, `docs/control/**`, `docs/quality/**`, `docs/evidence/**` and `.cursor/rules/**` after FPS-00C acceptance.

### Tier 4 — Current system documentation

- PB-RDH-09 complete integrated Project B system documentation RC1 and release manifest.
- PB-RDH-01 through PB-RDH-08 accepted supporting packs: product/requirements, domain/data/contracts/workflows, security/privacy/safety, web/native/UX, DevSecOps/test/operations, backlog/vertical slices, Cursor packet pack and enterprise delivery method.

### Tier 5 — Repository contracts and code

- `contracts/openapi/**`
- `contracts/asyncapi/**`
- `contracts/events/**`
- `contracts/schemas/**`
- `database/**`
- `apps/**`
- `tests/**`

These files are repository reality but may still be skeleton, incomplete or superseded. Their status must be established by the relevant gate.

### Tier 6 — External references

Use current official documentation for tool and standard behavior. PromptGenius is secondary prompt-method guidance only.

## Frozen cross-lane decisions

- Project A repository: `wordualReality/souvereign-os`.
- Project B and Database/Canonical implementation repository for the bounded sprint: `wordualReality/souvereign-os-coaching-platform`.
- Database/Canonical remains a separate owner lane and sole writer for KDB-owned migrations/canonical semantics during its packets.
- AgentScope is optional and non-authoritative; Project B/KDB defer operational use until governance and one manual packet are proven.

## Conflict rule

Do not resolve contradictory sources by timestamp alone. Record the exact sources, stop the affected path and use the owner lane or shared alignment register.