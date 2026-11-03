# Arcava owner guard / role and RLS binding contract

Decision: `ARC36P25-ARCAVA-RLS-BINDING-CONTRACT-DRAFT-01`

State: `PROPOSED_NOT_ADMITTED`. SQL authority: NONE. This draft implements the
ARC-07 owner-domain foundation only; ARC10-T110 remains incomplete.

Sources:

- [ARC-07 role/service matrix, RLS controls and privacy gates](https://docs.google.com/document/d/1i9NEnvB3Kk9WK4zBNdDzo5eV7xYroW1qJ95ZEQmpZsM/edit)
- [ATC-07 authorization decision matrix and separate controls](https://docs.google.com/document/d/1oNv0gaHdh0skkzana9KmuagggbOXdjwwdsoDW8c_3Ns/edit)
- [ARC09-U11](https://docs.google.com/document/d/1UkD8wxgmH18wa0JNwfY_Iopnsq22idvm72PexrKeoj4/edit)
- [ARC10-T110](https://docs.google.com/document/d/1bwZrdGHeQXZcU2V5kSQeGypNnMVUAp6I3aAgVY8fHKQ/edit)

## First implemented domain scope

`CoachClientAccessService.authorizeSensitiveClientRead` returns a typed decision
and permitted decision references, without resource payload. It supports a coach
assigned to the exact client/resource and a client accessing its own resource.
The same request must bind principal, tenant, subject, resource, operation,
purpose and revision to backend evidence. Session, tenant membership, access,
assignment (coach only), consent, share and entitlement are independent gates.
Every gate requires current state, exact binding, policy/decision reference,
effective time, expiry and applicable revocation. UNKNOWN, missing, stale,
denied, expired, revoked or mismatched evidence denies access.

The domain requires consent/share/entitlement for this sensitive-read operation
also on the client path. This conservative operation scope makes no general
claim about every client self-service contract.

Production `OwnerGuard(Clock)` has no live PIAC adapter and always denies valid
requests with `PIAC_NOT_CONNECTED`. Context constructors and the context-source
injection constructor are package-private. The only positive factory exists in
test sources and is labeled `SYNTHETIC_TEST_ONLY`. No Spring bean, HTTP route,
JWT parser, trusted header, mutable GUC or public trust-registration API is added.
Package access is a code-organization boundary, not a cryptographic attestation;
a future adapter requires separate source/identity review. Current PIAC/KDB NONE
implementations and JAR lifecycle are unchanged.

## Role contract

| Domain role | Grounded scope | This sensitive-read service |
| --- | --- | --- |
| CLIENT | Own admitted resources | Own subject + all applicable gates |
| COACH | Assigned client/resource | Exact assignment + all gates |
| TENANT_ADMIN | Tenant management | Denied; no sensitive-client bypass |
| ARCAVA_APPLICATION_SERVICE | Owner-local operations | Denied; no operation contract here |
| PROVIDER_ADAPTER | Bounded provider operation | Denied |
| COMPOSITION_SERVICE | Arcava draft/review write | Denied |
| AUDIT_READER | Minimized read-only audit | Denied |
| MIGRATION_OWNER | Migration-only | Denied |

These are domain roles, not PostgreSQL identities or grants. Arcava consumes
PIAC CT-SHC-001..005 evidence, KDB verified publication/rights/version and SOV
runtime outcomes through future reviewed contracts. No Arcava role transfers
foreign authority. Provider operations additionally need ProviderPermission;
they are outside the implemented sensitive-read operation.

## Proposed database controls

RLS defaults DENY. PUBLIC/anon privileged mutation is forbidden. Prefer SECURITY
INVOKER. Any justified later SECURITY DEFINER requires a dedicated least-privilege
NOLOGIN/NOSUPERUSER/NOBYPASSRLS owner, fixed minimal search_path, qualified
references and exact tests. No direct cross-owner SQL or FK cascade. The shared
`project_b` baseline and historical RLS seed do not establish Arcava table
ownership or admitted production policy.

## Unresolved decisions

Q1 — Which exact schema/table/migration allocations are Arcava-owned? Proposal:
owner-approve a source-pinned table-by-table manifest before new RLS SQL. No
physical ownership is inferred from existing `project_b` names.

Q2 — Which trusted CT-SHC identity/session/tenant/decision envelope, audience,
expiry and revocation mechanism feeds the backend-only context? Proposal:
reviewed adapter evidence binding. No JWT claim names, caller headers or
caller-set PostgreSQL context are selected by this draft.

Q3 — Which login/scoped-role/invoker/ACL and non-spoofable session boundary is
admitted? Proposal: least-privilege owner-approved runtime identity and independent
authentication-source review, with actual PG17 catalog proof. Exact names and
privileges remain unspecified.

Q4 — Which new policy source and real SQL tests are authorized? Proposal: separate
migration-owner source pin and private disposable PG17 role tests: valid tenant,
assigned coach and client self-read; wrong tenant/subject, unassigned coach,
missing consent/share/entitlement, admin overreach, PUBLIC/default ACL,
self-elevation and foreign-schema denial, with sanitized audit. Resolve Q1–Q3
before generating or executing a new RLS migration.

## Evidence and admission

Tests use fixed UTC time and immutable synthetic identifiers. Denials contain
only typed reasons; no sensitive payload or raw trust-source error is returned.
Allowed synthetic domain decisions expose decision references for audit use;
no durable audit writer or full A09-T44 security acceptance is claimed.
T150 PARTIAL; original T01 PARTIAL_NOT_ADMITTED; T04/T44/T48 NOT_EXECUTED;
T48 admitted evidence 0/86. Hosted, production, Security Acceptance and merge
remain outside this packet.
