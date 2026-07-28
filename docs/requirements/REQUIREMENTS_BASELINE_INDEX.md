# Requirements Baseline Index

## Current baseline

The requirements baseline is the accepted PB-RDH documentation set, especially:

- product definition and target users;
- capability catalogue;
- functional requirements and acceptance criteria;
- non-functional requirements and quality model;
- security/privacy/safety constraints;
- web/native/UX scope;
- backlog, vertical slices and developer handoff.

The integrated PB-RDH-09 RC1 is the entry point; detailed PB-RDH-01 through PB-RDH-08 artifacts remain supporting owner sources.

## Implementation target for the parkable MVP

1. Tenant/Admin/Ops context.
2. Manual client provisioning.
3. Coach/client ownership and assignment.
4. Journey draft and immutable version publication.
5. Enrollment gated by effective access, consent and entitlement.
6. Member journey/step delivery.
7. Completion and bounded reflection.
8. Assigned-coach progress projection.
9. Audit/outbox/evidence.
10. Deterministic synthetic demo seed and restartable parking package.

## Requirements rules

- Every packet identifies the requirement/capability IDs it implements or verifies.
- Acceptance criteria must be testable and mapped to evidence.
- Functional requirements, NFRs and constraints are separate.
- New capability IDs or materially new product behavior require an owner decision and traceability update.
- Native apps, commerce, broad analytics, community/cohorts, full KDB population and production deployment are non-goals of the bounded parking sprint unless a later accepted gate changes scope.