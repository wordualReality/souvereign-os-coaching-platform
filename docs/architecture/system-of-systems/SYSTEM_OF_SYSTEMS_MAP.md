# Sovereign OS System-of-Systems Map

Status: CURRENT GOVERNANCE BASELINE / EXACT FOUNDER-NOTE TRACEABILITY PENDING

## Whole

Sovereign OS is an interacting system of owner lanes, not a collection of independent applications. The whole exists to convert governed knowledge, human intent and observed state into safe, explainable and useful actions or journeys while preserving ownership, provenance, tenant isolation, privacy, auditability and operational control.

## Constituent systems

| System | Primary purpose | Owns | Receives from | Provides to |
|---|---|---|---|---|
| Project A | Operator/runtime state, routing and execution capabilities | Project-A runtime behavior and projections | approved knowledge/contracts, user state, shared events | operator actions, explanations, runtime events |
| Project B | White-label coaching and journey delivery | tenant/coach/client/journey runtime, assignments, enrollment, delivery, reflection/progress | approved canonical references, effective access, tenant config | commands, runtime projections, audit/outbox events |
| Database/Canonical | governed knowledge and protocol semantics | canonical taxonomy, protocols, programs, sources, provenance, rights, review/publication | approved intake, human review decisions, usage/revalidation signals | validated references, restricted RPCs/events, withdrawal state |
| Shared Database Control | ordered shared persistence controls | migration ordering, shared roles, common RLS/audit/outbox conventions | owner-lane database packets | controlled database baseline and evidence |
| n8n/support plane | bounded automation | approved workflow execution only | APIs, events or restricted RPCs | idempotent support actions and execution evidence |
| Git/CI/agentic tooling | controlled delivery assistance | repository changes and evidence within an authorized packet | versioned rules, source manifest, predecessor gate | proposed code, tests, reviews and returns |

## Interaction rules

- Every cross-system interaction has a producer, consumer, owner, versioned contract and failure owner.
- No constituent system may duplicate another system's authoritative truth.
- Project B and Database/Canonical may share the implementation repository while retaining separate owner authority and one-writer packet control.
- Project A remains a separate repository and owner lane.
- n8n and agentic tooling are support systems, never architecture or gate authorities.
- Direct-table coupling across owner boundaries is prohibited unless an accepted ADR explicitly authorizes it.

## Core end-to-end paths

1. Governed knowledge: source → provenance/rights → review → canonical publication → validated reference → product use → revalidation/withdrawal.
2. Project B journey: admin/coach intent → access checks → draft/version → enrollment → member delivery → completion/reflection → permitted coach projection → audit/outbox.
3. Delivery process: accepted gate → bounded packet → implementation → tests/evidence → independent review → gate → exactly one successor.

## Required evidence

Static diagrams are not sufficient. Each implemented interaction must later be evidenced by contract tests, positive and negative authorization cases, failure propagation, audit/outbox reconstruction and named owner response.
