# Implementation Traceability Index

Every implementation packet must map this chain:

`Source requirement/capability → acceptance criterion → architecture/contract → code path → test → evidence → gate`

## Minimum traceability record

| Field | Required content |
|---|---|
| Requirement | Current requirement/capability ID and source |
| Owner lane | Project B, Database/Canonical or Shared Database Control |
| Acceptance criteria | Observable and testable behavior |
| Architecture | Bounded context, owner and invariant |
| Contract | OpenAPI/AsyncAPI/schema/RPC/event reference |
| Implementation | Exact files and result SHA |
| Tests | Positive, negative and relevant quality/security cases |
| Evidence | Evidence directory and command exit codes |
| Gate | Accepted decision and authorized successor |

## Current MVP traceability groups

- T1: tenant/admin context and effective access.
- T2: manual client provisioning and ownership/assignment.
- T3: journey draft and immutable publication.
- T4: enrollment and member delivery.
- T5: intention policy, pre-session reminder, privacy and progression stage.
- T6: completion/reflection and coach progress projection.
- T7: audit/outbox and minimal worker/workflow.
- T8: deterministic demo seed, reset/rebuild, E2E and parking release.

## Later curated pilot traceability group

- T9: locality/season-aware botanical and supplement evidence projection, human review, safety/legal controls and read-only Project-B discovery.

T9 requires separate Database/Canonical owner evidence for taxonomy, occurrence provenance, legal status, preparation-specific evidence, safety, publication, revalidation and withdrawal. Project B evidence alone cannot close T9.

Do not claim coverage because a requirement appears in a document. Coverage requires an implementation and accepted test/evidence link.
