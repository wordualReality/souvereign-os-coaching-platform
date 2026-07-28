# Architecture Decision Record Index

## Accepted cross-lane decisions

| Decision | Status | Consequence |
|---|---|---|
| Project A uses `wordualReality/souvereign-os` | Accepted | Separate repository and owner lane |
| Project B and Database/Canonical share `wordualReality/souvereign-os-coaching-platform` for the bounded sprint | Accepted | One ordered implementation repository; owner lanes remain separate |
| KDB/Database is sole writer for KDB-owned migrations and canonical semantics during its packets | Accepted | Project B cannot concurrently modify those paths |
| AgentScope conflict Option (a) | Accepted | Project A may scaffold non-authoritatively; Project B/KDB defer operational use |
| Git + versioned rules + bounded packet + evidence + independent gate is the common control path | Accepted | No agent framework becomes a second source of truth |
| Architecture freeze | Accepted | No silent reopening during implementation |

## Existing domain decisions to retain

- Project B may not consume raw staging rows as client runtime truth.
- `canonical_ref` is a validated reference envelope, not raw intake and not the canonical object itself.
- Canonical promotion remains manual/human-governed.
- Video/media is modeled as an asset relation, not a flat protocol field; detailed implementation remains gated.
- n8n is support plane through restricted interfaces.

## ADR trigger

Create a new ADR and stop the affected packet when a change is required to:

- repository or deployment topology;
- bounded-context or schema ownership;
- shared migration authority;
- identity/effective-access semantics;
- RLS/RPC conventions;
- API/event compatibility;
- canonical promotion or provenance rules;
- security/privacy/safety posture;
- native/web strategy;
- agent or workflow execution authority.

An ADR documents a decision; it does not itself authorize implementation.