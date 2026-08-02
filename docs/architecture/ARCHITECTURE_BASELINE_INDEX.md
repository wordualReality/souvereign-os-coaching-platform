# Architecture Baseline Index

## Architecture status

Project B architecture is `PASS / FROZEN / NO REOPEN` for the bounded implementation sprint. Implementation may expose defects or missing contracts, but it may not silently redesign accepted boundaries.

The 2026-08-02 intention and botanical scope is classified as `EXTENSION_WITHIN_EXISTING_BOUNDARIES / NO REOPEN` and is documented in:

- `docs/requirements/INTENTION_AND_BOTANICAL_SCOPE_ADDENDUM.md`;
- `docs/architecture/INTENTION_AND_BOTANICAL_THREE_TIER_ARCHITECTURE.md`;
- `docs/security/BOTANICAL_SAFETY_AND_LOCATION_PRIVACY_RULES.md`;
- `docs/decisions/ADR-SCOPE-INT-BOT-001.md`.

## Runtime target

- Web: Next.js App Router.
- Backend: Java 21 / Spring Boot 3.5.x target architecture.
- Data: Supabase PostgreSQL with ordered migrations and mandatory RLS for exposed tenant data.
- Schemas: `project_b`, `canonical` and shared/core boundaries as defined by owner contracts.
- Integration: versioned HTTP APIs, events and restricted RPCs.

## Ownership boundaries

- Project B owns tenant, coach, client, journey, assignment, enrollment, delivery, intention policy/runtime, reflection/progress, local discovery presentation and Project-B runtime projections.
- Database/Canonical owns canonical knowledge, botanical taxonomy, occurrence provenance, legal status, preparation-specific evidence, safety, rights, claims/evidence, review/publication and KDB-specific RPC/migration semantics.
- Shared Database Control owns migration ordering, shared roles, common RLS conventions, audit/outbox conventions and environment baseline.
- Project A remains a separate repository and owner lane.

## Architectural invariants

- Fail closed on missing or ambiguous effective access.
- Tenant isolation is enforced at database and application boundaries.
- Published journey versions are immutable.
- Intention text is private by default and excluded from general logs/outbox payloads.
- Raw staging/candidate content is never client runtime truth.
- Canonical and botanical promotion is human-governed and not autonomous.
- Local occurrence does not imply edibility, efficacy, legal collection or safety.
- Preparation and dosage evidence cannot be transferred across plant parts, extracts or concentrations.
- Operational writes occur through application services or approved restricted interfaces.
- Audit/outbox records allow reconstruction of material state changes without sensitive-text leakage.
- n8n is support plane, not architecture authority.
- AgentScope/OpenClaw are optional orchestration/operation layers, not project truth.

## Required escalation

Create an ADR/owner-return and stop when implementation requires a change to bounded contexts, schema ownership, canonical truth, botanical publication/safety semantics, cross-lane contracts, security model or deployment topology.
