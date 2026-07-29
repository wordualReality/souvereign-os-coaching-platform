# Paved Paths and Guardrails

Status: CURRENT GOVERNANCE CONTROL

Paved paths provide the shortest approved route through the system. Teams and agents receive context and autonomy inside these paths; deviations require an owner decision or ADR.

## Approved paths

### Repository delivery

accepted gate → isolated branch/worktree → scoped rules and packet → bounded change → required tests → evidence → independent review → gate → exactly one successor.

### Project-B application write

authenticated actor → effective-access check → application service/command → validated state transition → transaction → audit/outbox → approved projection/API response.

### Canonical consumption

Project B or Project A → producer-owned read contract / validated reference envelope → published and permitted canonical object/version. Raw intake, staging or candidate rows are not consumption paths.

### Workflow support

versioned outbox/event or approved scheduler → claim/lease/restricted API or RPC → idempotent action → ACK/NACK/retry/DLQ → audit and execution evidence.

### Database change

DB-owner packet → ordered local migration → reset/rebuild from zero → RLS/grant/RPC positive and negative tests → evidence → environment gate. Remote mutation is not implied.

### Feedback and adaptation

observed interaction → classified/minimized signal → owner-approved interpretation → bounded decision or recommendation → user/human control where required → outcome measurement → review.

## Guardrails

- No direct changes to `main`.
- No direct cross-lane table access or duplicated source of truth.
- No unconditional tenant read policy or service-role exposure.
- No endpoint, event, RPC or schema invented outside an authorized contract packet.
- No autonomous canonical promotion, safety decision or high-impact adaptation.
- No n8n or agentic tool as architecture, owner or gate authority.
- No broad context crawl when an exact source manifest or packet context exists.
- No `PASS` based only on file presence, static parsing, screenshots or model self-assessment.
- No hidden continuation beyond the one authorized packet.

## Deviation process

A deviation must state the blocked paved path, evidence, affected lanes, options, risk and proposed ADR/owner return. Until accepted, the executor stops the affected path.
