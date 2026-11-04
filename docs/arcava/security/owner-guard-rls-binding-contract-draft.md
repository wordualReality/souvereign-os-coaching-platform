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

## Local T020 enrollment read integration

`ArcavaAccessService.readEnrollment` applies the unchanged OwnerGuard before any
repository lookup. `ClientRelationshipRepository` reads only the existing
`com.projectb.api.domain.JourneyJournal` enrollment, associated projection and
actual internal assignment snapshot.
`ClientRelationshipModel` validates all five existing EnrollmentLink identifiers
as canonical, non-nil UUIDs: tenant, client, version, assignment and enrollment.
Unsupported historical string IDs fail closed; no backfill or SQL schema is added.
After authorization the service independently compares stored tenant/client/
enrollment with request tenant/subject/resource. Missing and mismatched entries
both return NOT_FOUND without payload. Invalid stored values and storage faults
return safe typed statuses with no raw values or exceptions. Successful reads
expose only enrollment and journey-version identifiers in an immutable view.

The storage seam grants no authority. Coach assignment evidence is independently
bound to the exact requested tenant/client/enrollment by OwnerGuard; the existing
context has no separate assignment-ID attestation. This slice neither asserts
that a PIAC decision attests the stored assignmentId nor adds such a claim. The
stored assignment/version IDs are validated and independently linked to the
actual local assignment, not promoted to verified external authority.
EnrollmentLink has no lifecycle/revocation/revision state; associated
publication state is checked below. This is not the full CT-ARC-001/003 or
enrollment lifecycle implementation.

The integration suite actually creates, updates, publishes and assigns through
the existing journal APIs with SYNTHETIC_TEST_ONLY canonical pins and consent.
Principal/tenant/client IDs and trust clock are fixed. The journal generates its
own draft/assignment IDs and publication timestamp; tests preserve those exact
persisted values across reopen instead of inventing an unsupported clock/ID API.
Positive and negative reads are checked after journal replay, including unchanged
bytes and denied-before-lookup counters. Malformed stored links use a storage
fault-injection seam; unsupported client IDs are also persisted/replayed through
the actual source APIs. No caller body, header or bearer is trusted.

Trace: ARC10-T020 TENANT_CLIENT_ACCESS; ARC09-U02/U11; ARC-07 and ATC-07
independent owner guards. T020 and T110 full acceptance remain NOT_ADMITTED;
original A09-T07/T08/T09/T44 remain NOT_EXECUTED. Q1–Q4 below remain OPEN and
PROPOSED_NOT_ADMITTED. No live route, production bean, PIAC/KDB adapter or SQL
has been added by this local developer-integration slice.

### Publication withdrawal fence

After OwnerGuard allows the request, the repository captures the EnrollmentLink
and the Projection selected by its stored version ID, plus the local AssignmentView
selected by its stored assignment ID, inside one `synchronized(journal)` block.
The journal accessors, assign and withdraw use this same monitor. The snapshot
contains immutable source records, not a caller-provided trust boolean. All three
records describe one local
read point; there is no independently cached PUBLISHED result. A concurrent read
may linearize before a withdrawal, but a read beginning after that withdrawal
completes must see the withdrawn state. This is a single-JourneyJournal-instance
consistency boundary, not multi-process file coordination or SQL isolation.

Only exact PUBLISHED allows a view. Missing projection, WITHDRAWN, null/unknown/
lowercase state, projection tenant/version mismatch and malformed projection
identifiers return NOT_FOUND without payload. Projection tenant and version must
exactly match the already validated enrollment UUIDs; journey ID must also be a
canonical non-nil UUID. Raw phases, hashes, timestamps and errors are never
returned. A malformed enrollment still fails closed and storage faults return
READ_UNAVAILABLE. The existing service additionally checks request tenant,
subject and enrollment identity before returning its minimized view.

Regression tests keep the existing 13 integration cases and add four cases:
real journal withdrawal denies coach and client before/after replay, repeated
withdrawal is idempotent and keeps the enrollment, invalid publication snapshots
are denied, revoked/stale/unknown auth and missing live PIAC deny before lookup
even after withdrawal, and a bounded monitor/latch test orders withdrawal before
the blocked reader without sleeps. Reads preserve journal bytes. Projection
fault fixtures are synthetic storage observations, not PIAC/KDB attestations.
The withdrawal implementation did not change Journal/Kernel/OwnerGuard behavior.
The assignment follow-up below adds only read accessors to Journal/Kernel; no
HTTP readiness, production authority or SQL changes are needed.

### Local assignment-link consistency

`JourneyKernel.assignmentSnapshot(UUID)` returns the existing immutable map
entry or null. `JourneyJournal.assignmentSnapshot(UUID)` delegates under its
monitor. These are internal storage APIs, with no HTTP exposure and no new
authority registration or mutation. The repository reads them together with
enrollment and projection under the same journal monitor. No new cache is added.

The referenced record must exist, with assignment ID, tenant, client and journey
version exactly matching the validated EnrollmentLink UUIDs. Only the existing
source status `active` is accepted (lowercase, unlike projection `PUBLISHED`).
Missing, malformed, foreign, swapped, null or unknown assignment fields/status
return NOT_FOUND with null payload, just like an absent record. Storage faults
still fail closed without exception text. No new revoke operation is invented:
withdrawal leaves an assignment locally active, but the separate publication
fence still denies access. The local record does not attest coach identity,
consent, entitlement or a trusted PIAC assignment-ID binding; all existing guard
evidence remains separately required before any storage access.

Three additional integration cases exercise actual assignment creation/readback
and exact replay for coach and client, 26 synthetic missing/mismatched/invalid
assignment snapshots plus a changed enrollment reference for both roles before
and after reopen, and active-assignment/withdrawal/guard/fault interactions.
Unsupported corruptions and inactive/revoked statuses exist only in labeled
SYNTHETIC_TEST_ONLY storage fault fixtures, never as newly supported source
lifecycle operations. Existing denial-before-lookup, no-live-PIAC, revoked/stale
guard, no-byte-mutation and monitor-ordering withdrawal tests are retained.
The original 48 Maven regressions remain alongside these three cases.

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
