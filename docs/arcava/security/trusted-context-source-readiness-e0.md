# Q2: trusted ContextSource readiness (E0)

Packet: `ARC36P25-T020-TRUSTED-CONTEXT-SOURCE-READINESS-E0-01`.
Base: `154a5914730eb9d53ced813f000e844c87072652`. Parent: ARC10-T020.
`CL-GATE-CLOSURE-20261105-01` adopted. `BL-ARC-01` remains OPEN for formal
integration/admission only. Local E0 inventory is complete; Q2 remains
`OPEN_UNVERIFIED`. No Java or runtime authority was changed.

## What is physically available

The five schemas are **not missing globally**. Repo B has no CT-SHC physical
producer schema in its tracked contracts tree at this base. Repo A main at
`e7080491b31f64f338e3e4cb39d6b74cb1b0d30f` has no such schema paths either.
The discovered producer branch
`impl/sov-piac-decision-proof-v1-issue14-20261026` at
`9ae5950ed2e556b6d6301f3d19d81a14992d6be7` contains all five schemas and
`contracts/manifest.json`: version `1.0`, producer `PIAC`, **5/5 physical SHA256
values match that manifest**. The five schema blobs and proof-verifier blob are
also identical on observed SOV APB P04 snapshot
`edb40836baf8cec631d1873d60b5b57f7706a820`. This is source discovery, not selection
of an admitted current deployment or cross-owner acceptance.

The [JSON ledger](trusted-context-source-readiness-e0.json) records immutable
GitHub paths, Git blob IDs, SHA256 values, exact schema metadata/field fragments,
local source hashes, and readable Drive excerpts with modification times and
excerpt hashes. Excerpt hashes pin this readable observation; they are not
Google revision IDs or live producer checksums. Schemas remain in their producer
repository; this ledger is not a new consumer contract registry.

## Independent gates and concrete gaps

| Gate | Available declared source | What still prevents a trusted Arcava binding |
| --- | --- | --- |
| SESSION | CT-SHC-001 principal/identity revision; CT-SHC-002 principal/session/state/revision/validity/decision | Authenticated issuer/audience/session correlation and current revocation. Session validity timestamps are not universally required by schema; never fabricate expiry. |
| TENANT_MEMBERSHIP | CT-SHC-003 requested scope and grant ref/revision/state/decision | TenantAccessGrant does not replace Arcava membership/business state; exact current tenant/principal/client correlation remains unadmitted. |
| ACCESS | Producer AccessDecision and composer source; five CT-SHC queries | Query ALLOW is not an execute grant. No admitted SENSITIVE_CLIENT_READ profile or authenticated ContextSource mapping. |
| ASSIGNMENT | ATC-04 AG-ARC-004; local Journal AssignmentView/linkage | Independent ARCAVA gate, not a sixth PIAC contract. Local active IDs do not attest coach principal, role, validity or activation. |
| CONSENT | CT-SHC-004 principal/resource/data-scope/purpose query; optional grant ref/state/scopes/decision result | Current policy/revision/revocation and authenticated subject/resource/purpose correlation. Consent is never ShareGrant or Assignment. |
| SHARE | ATC-04 AG-ARC-113 ActivityShareGrant; local SHARE evidence slot | Independent ARCAVA grant, not supplied by CT-SHC-001..005. Required client/coach-assignment/purpose/consent/validity provenance is not materialized/admitted by a gate enum. |
| ENTITLEMENT | CT-SHC-005 principal/capability/resource query; optional grant ref/state/capability/decision result | Current grant revision, tenant/subject/purpose/expiry/revocation correlation. Enrollment is not entitlement. |

Every gate row in JSON covers issuer, audience, principal, tenant, client/subject,
resource, purpose, operation, revision, effectiveAt, expiresAt, revokedAt,
policy/decision refs, contract version/hash and backend ContextSource availability.
VERIFIED means observed source bytes/manifest only; UNVERIFIED means unadmitted
binding/authority; ABSENT is restricted to the specified inspected source.

The response envelopes require source_refs/as_of/freshness/projection_version,
but resource_ref and valid_until are optional. None of the five result payloads
exposes revokedAt; private producer domain records do have revocation data.
ClientProfile IDs and PIAC principal IDs remain different namespaces. Separate
identity/session/grant revisions cannot be collapsed into the consumer's single
revision without a reviewed rule. Declared producer=PIAC and source_refs strings
are not an authenticated issuer or policy decision. Required consumer proof
fields cannot be filled with request body fields, default timestamps or hashes.

## Existing proof is not an Arcava authorization shortcut

The pinned producer includes an Ed25519 decision-proof schema with a matching
SHA256 sidecar, issuer/audience/epoch/replay verification source and a trusted
actor-context representation. The inspected verifier explicitly accepts only
`KDB_SOURCE_INTAKE`; it recomputes the KDB command digest. Its producer receipt
explicitly does not adopt the proof for KDB or Arcava. That pinned receipt reports
live custody as `UnconfiguredProofAuthority` (`AUTHORITY_NOT_CONFIGURED`);
this E0 did not probe any current live deployment. Ephemeral synthetic keys are
not live authority. These existing proof fields are observations of a
separate contract, not proposed JWT claims or an Arcava audience/profile.
Calling a factory `verifiedHuman` or supplying issuer/audience/provenance labels
does not itself establish authenticated external identity for Arcava.

In Repo B, ContextSource and its injection constructor remain package-private.
Public `OwnerGuard(Clock)` resolves null and returns `PIAC_NOT_CONNECTED`.
TrustedPiacVerifier.NONE and the deny-by-default active port also remain closed;
neither is a producer-verifying ContextSource. Local synthetic positive context
construction exists only in test fixtures. No live adapter was added.

## Exact next owner requests (not dispatched or assigned by this file)

R01: Existing SOV/PIAC producer owner must review the discovered immutable
source/version/hash bundle and confirm or supersede it for Arcava. Supply the
exact supported sensitive-read operation/profile and identity/client, role,
resource/purpose, independent revision/expiry/revocation correlation. This is
not a request to recreate already existing schemas. Architectural ownership is
identified; the accountable execution assignee remains UNASSIGNED/UNVERIFIED.

R02: Existing PIAC workload/key-custody operator must provide non-secret evidence
of admitted issuer/audience/workload authentication, custody/rotation and current
revocation binding for that reviewed profile. The operational assignee is not
proven. No credential disclosure or hosted action is authorized by this E0 file.

R03: GPT_BUILDER_ARCAVA consumes this E0 once, resolves R01, and selects one bounded
authorized consumer-binding delta with independent Assignment/Share gates. The
live path remains closed until actual implementation, tests and admission.

R04: Required independent security/operational authority later reviews the actual
binding and current/expired/revoked/stale/unbound/cross-scope tests. No new reviewer
is appointed and no assignment is inferred from this request.

The JSON GATE_RECORD supplies status, criteria, evidence, owner, next action and
review trigger. Parent ARC10-T020 stays ACTIVE_LOCAL_WITH_Q2_OPEN; only the live
path is WAITING_EXTERNAL. This single E0 inventory needs no child plan, so no
GATE_PROGRESS or new plan is created. Return to ARC10-T020 via the existing Builder.

## Validation and unchanged admission

No concrete new untested local fail-closed behavior was evidenced after reviewing
the existing source/test suite. Missing, bad, expired, revoked, stale, unbound,
provider-error and default-closure paths already have accepted coverage. No Java
change or duplicate negative suite was added. Maven/runtime tests are
**NOT_EXECUTED in this packet**; prior 75 tests remain unchanged and accepted,
not counted as a new run. CI auto-triggered by docs pushes is not Q2 acceptance.

Mechanical self-check (source/manifest/field consistency only):

```sh
python3 docs/arcava/security/trusted-context-source-readiness-e0-selfcheck.py
```

It reads pinned GitHub sources using existing `gh` access, validates all producer
and local source hashes, manifest entries, schema field observations, additional
snapshot comparisons, seven gate rows, Drive excerpt hashes and default-closed
source markers. No secret values, database, runtime, authority or external writes.
For an already fetched non-secret source cache, `--producer-cache <path>` verifies
the same raw bytes against SHA256/Git blob pins (snapshot tree reads still use gh).

Q1-Q4 OPEN/PROPOSED_NOT_ADMITTED; full T020/T110 NOT_ADMITTED; T150 PARTIAL;
original A09-T01 partial, T04/T44/T48/T07/T08/T09 NOT_EXECUTED; admitted T48 0/86.
G04, producer integration, SQL/RLS, independent Security QS, hosted/release/merge
remain open. Nutrition T050/T090 remains NON_ROUTING. No formal gate is closed.
