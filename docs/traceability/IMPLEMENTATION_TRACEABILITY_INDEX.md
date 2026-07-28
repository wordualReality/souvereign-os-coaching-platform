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
- T5: completion/reflection and coach progress projection.
- T6: audit/outbox and minimal worker/workflow.
- T7: deterministic demo seed, reset/rebuild, E2E and parking release.

Do not claim coverage because a requirement appears in a document. Coverage requires an implementation and accepted test/evidence link.