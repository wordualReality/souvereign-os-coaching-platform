# Architecture Baseline Index

## Architecture status

Project B architecture is `PASS / FROZEN / NO REOPEN` for the bounded implementation sprint. Implementation may expose defects or missing contracts, but it may not silently redesign accepted boundaries.

## Runtime target

- Web: Next.js App Router.
- Backend: Java 21 / Spring Boot 3.5.x target architecture.
- Data: Supabase PostgreSQL with ordered migrations and mandatory RLS for exposed tenant data.
- Schemas: `project_b`, `canonical` and shared/core boundaries as defined by owner contracts.
- Integration: versioned HTTP APIs, events and restricted RPCs.

## Ownership boundaries

- Project B owns tenant, coach, client, journey, assignment, enrollment, delivery, reflection/progress and Project-B runtime projections.
- Database/Canonical owns canonical knowledge, provenance, rights, claims/evidence, review/publication and KDB-specific RPC/migration semantics.
- Shared Database Control owns migration ordering, shared roles, common RLS conventions, audit/outbox conventions and environment baseline.
- Project A remains a separate repository and owner lane.

## Architectural invariants

- Fail closed on missing or ambiguous effective access.
- Tenant isolation is enforced at database and application boundaries.
- Published journey versions are immutable.
- Raw staging/candidate content is never client runtime truth.
- Canonical promotion is human-governed and not autonomous.
- Operational writes occur through application services or approved restricted interfaces.
- Audit/outbox records allow reconstruction of material state changes.
- n8n is support plane, not architecture authority.
- AgentScope/OpenClaw are optional orchestration/operation layers, not project truth.

## Required escalation

Create an ADR/owner-return and stop when implementation requires a change to bounded contexts, schema ownership, canonical truth, cross-lane contracts, security model or deployment topology.