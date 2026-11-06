# Q2 R03: sensitive-client-read consumer contract draft

**Status: DRAFT_NON_ADMITTED.** Packet:
`ARC36P25-T020-Q2-R03-LOCAL-SENSITIVE-READ-CONSUMER-SPEC-01`.
Arcava base: `741437272bb864bf29bbb4dc72372c70b42e8de7`.
Parent: ARC-36/P25 / ARC10-T020. Existing child:
`ARC36P25-T020-Q2-CLOSURE-CHILD-01`, C3/R03 SPEC_ONLY.
`CL-GATE-CLOSURE-20261105-01` adopted. Q2 OPEN; BL-ARC-01 OPEN_SCOPED.
RETURN_TO: ARC10-T020. This document neither closes C3 owner review nor Q2.

## Source disposition and classification

Every field/group below uses one of these classifications:

- **VERIFIED_SOURCE_ONLY**: physically declared by the pinned schema/code or
  recorded by the owner decision. It is not an authenticated live fact.
- **UNVERIFIED**: a required authority/configuration/currentness binding has not
  been established. A name, reference, role label or UUID does not prove it.
- **CONTRACT_MISSING**: the applicable operation/export/verifier or field-mapping
  contract is not defined/admitted. This draft states an obligation, not its wire
  implementation, version, issuer, claim name, endpoint or signature format.

VERIFIED_SOURCE_ONLY: [R01 owner decision](https://github.com/wordualReality/souvereign-os/issues/14#issuecomment-6662999628)
accepts the five CT-SHC schemas as a source baseline. Its
[routing clarification](https://github.com/wordualReality/souvereign-os/issues/14#issuecomment-6663022174)
explicitly removes the pre-decision OWNER_ADOPTION_REQUIRED interpretation.
No repeat R01 approval or E0 inventory is requested.

UNVERIFIED: [R02 request](https://github.com/wordualReality/souvereign-os/issues/14#issuecomment-6667433808)
is pending in the inspected issue comments. Accountable operational issuer,
Arcava workload and key-custody assignees remain UNASSIGNED_UNVERIFIED. Requests
and architectural ownership do not appoint an operator or admit runtime access.
SOV P06 retains its sole writer; no SOV change or message is made by this draft.

VERIFIED_SOURCE_ONLY: accepted source repository `wordualReality/souvereign-os`,
immutable SHA `9ae5950ed2e556b6d6301f3d19d81a14992d6be7`,
[`contracts/manifest.json`](https://github.com/wordualReality/souvereign-os/blob/9ae5950ed2e556b6d6301f3d19d81a14992d6be7/contracts/manifest.json).
All five schemas declare version `1.0`, producer PIAC and QUERY_READ_MODEL.
Paths below are under `contracts/shared-core/` at that SHA.

| Contract | Physical filename | Accepted SHA256 | Status |
| --- | --- | --- | --- |
| CT-SHC-001 | `ct-shc-001.actor-identity-context.v1.schema.json` | `4b77feee91d7cb86013fd3a6f59e7178be3e744ab6d76d6b58844b9a7b03783f` | VERIFIED_SOURCE_ONLY |
| CT-SHC-002 | `ct-shc-002.auth-session-context.v1.schema.json` | `7ec82462615fb1b071018d755279c62f9f4c4d6c4c7f974a7f9157a6da665d35` | VERIFIED_SOURCE_ONLY |
| CT-SHC-003 | `ct-shc-003.tenant-access-context.v1.schema.json` | `0e55b200c975bbf49432c08d627215c6696351ae52292bfab21ef3c28f0db0af` | VERIFIED_SOURCE_ONLY |
| CT-SHC-004 | `ct-shc-004.consent-decision.v1.schema.json` | `e3c21f00a8f0dc62f7aa09ad8474163df6ab512ace4064f2d9ab8375531a40b8` | VERIFIED_SOURCE_ONLY |
| CT-SHC-005 | `ct-shc-005.entitlement-access-decision.v1.schema.json` | `8ffd258108bf1f92ef457130c6144b98850becccbaa5e28de86d0fe1ac0f47a4` | VERIFIED_SOURCE_ONLY |

VERIFIED_SOURCE_ONLY: this draft reads, but does not modify or rerun, the existing
[E0 ledger](trusted-context-source-readiness-e0.json),
[E0 explanation](trusted-context-source-readiness-e0.md), control-manifest.json,
OwnerGuard.java, TrustedRequestContext.java, RoleScopePolicy.java and
ArcavaAccessService.java at the Arcava base. The prior 75-test return remains
accepted at source `b2f28610d879d8dac4adc7a171053ee981df0f04`; it is provenance,
not a new R03 execution or security admission.

## Request and identity binding requirements

The following describes logical binding obligations, **not a new wire schema**.
Future resolution must happen on the backend before the repository lookup.
Untrusted selectors cannot create their own authenticated counterpart.

| Logical field/group | Current source fact | Future binding obligation | Status |
| --- | --- | --- | --- |
| `claimedPrincipal` | Existing Request UUID selector | Compare to authenticated actor principal; handle delegated subject separately, never trust a caller claim | VERIFIED_SOURCE_ONLY for selector; UNVERIFIED for authentication |
| `tenant` | Existing Request UUID | Bind PIAC tenant scope and independent Arcava membership/resource tenant | VERIFIED_SOURCE_ONLY for selector; CONTRACT_MISSING for authenticated composition |
| `subject` / client | Existing Request subject UUID; local self-client policy compares principal and subject UUIDs | Keep Arcava ClientProfile ID and PIAC subject-principal ID distinct; require explicit tenant-bound mapping. Existing synthetic equality is not that mapping | VERIFIED_SOURCE_ONLY for local shape; CONTRACT_MISSING for namespace mapping |
| `resource` | Existing Request resource UUID selects an enrollment; service returns enrollment/version UUIDs only | Explicitly bind target enrollment, ClientProfile, permitted data scope and resource revision. Whether the future proof addresses the profile, enrollment or both requires an exact owner agreement; never silently reinterpret the IDs | VERIFIED_SOURCE_ONLY for current enrollment selector; CONTRACT_MISSING for producer target normalization |
| `purpose` | Local COACHING_SUPPORT / SELF_ACCESS / UNKNOWN enum | An admitted operation profile must select exact purpose and capability semantics; do not invent a producer translation | VERIFIED_SOURCE_ONLY for local enum; CONTRACT_MISSING for producer mapping |
| `operation` | Local SENSITIVE_CLIENT_READ; UNKNOWN denied | SOV operation-specific signed decision/export/verifier contract **REQUIRES_NEW_CONTRACT** | VERIFIED_SOURCE_ONLY for local enum/R01 disposition; CONTRACT_MISSING for producer implementation |
| `revision` | Existing single Request long; requires value at least 1 and exact local-context equality | Cannot represent all independently current identity/session/grant/policy/decision/resource revisions | VERIFIED_SOURCE_ONLY for synthetic field; CONTRACT_MISSING for revision model |
| AuthSession | Backend context has separate `authSession`; it is not a Request body field | Authenticate and bind the current PIAC session to actor/subject and workload; distinguish it from JourneySession and Enrollment | VERIFIED_SOURCE_ONLY for local context field; UNVERIFIED for current producer binding |
| Role / assignment / share | Current local policy allows coach support or client self scope; other roles denied | Independent Arcava role/client/assignment/share provenance plus admitted PIAC operation profile; admin/workload label is no blanket sensitive-read grant | VERIFIED_SOURCE_ONLY for local policy; UNVERIFIED for real authority |

CONTRACT_MISSING: a source-bound relationship between this logical request and a
new signed operation decision. No request body, header, fixture bearer, GUC,
producer string, source_refs, plain ALLOW or caller hash can substitute for it.
No new producer contract ID, version, JWT claim, audience literal or endpoint is
defined here. Package-private ContextSource injection is not a cryptographic
trust boundary or an authority registrar.

## Seven independent gates: physical field crosswalk

Notation `CT-SHC-NNN:request.payload.x` or `:response.x` points to a property
under the corresponding pinned schema `$defs`. Source presence does not imply
the property is required or authenticated. Each gate still needs an independently
current, exact actor/subject/tenant/resource/purpose/operation binding.

| Gate | Physical source fields / independent owner control | Missing consumer obligation | Status |
| --- | --- | --- | --- |
| SESSION | `CT-SHC-001:response.payload.principal_id`, `CT-SHC-001:response.payload.identity_revision`; `CT-SHC-002:request.payload.auth_session_id`, `CT-SHC-002:response.payload.principal_id`, `CT-SHC-002:response.payload.session_state`, `CT-SHC-002:response.payload.session_revision`, `CT-SHC-002:response.payload.validity` | Authenticated current session tied to actor/delegated subject/workload and revocation; a session ref or state label is insufficient | VERIFIED_SOURCE_ONLY fields; UNVERIFIED authority |
| TENANT_MEMBERSHIP | `CT-SHC-003:request.payload.principal_id`, `CT-SHC-003:request.payload.requested_scope`; `CT-SHC-003:response.payload.grant_ref`, `CT-SHC-003:response.payload.grant_revision`, `CT-SHC-003:response.payload.grant_state`; separate Arcava TenantMembership | Correlate PIAC grant and Arcava membership with exact tenant/client and current validity; neither replaces the other | VERIFIED_SOURCE_ONLY fields/owner boundary; CONTRACT_MISSING composition |
| ACCESS | CT-SHC read decisions, e.g. `CT-SHC-001:response.payload.decision`; producer composer source in E0 | An operation-specific authenticated SENSITIVE_CLIENT_READ decision is missing. Five read-ALLOWs cannot be combined into an invented execute grant | VERIFIED_SOURCE_ONLY query fields; CONTRACT_MISSING operation/export/verifier |
| ASSIGNMENT | Arcava AG-ARC-004; existing local AssignmentView and exact journal linkage; local ASSIGNMENT evidence slot | Verify coach/client/tenant/resource relationship, role, validity, revision and activation provenance independently. This is not another CT-SHC schema | VERIFIED_SOURCE_ONLY local structure; UNVERIFIED admitted business authority |
| CONSENT | `CT-SHC-004:request.payload.principal_id`, `CT-SHC-004:request.payload.resource_ref`, `CT-SHC-004:request.payload.data_scope`, `CT-SHC-004:request.payload.processing_purpose`; `CT-SHC-004:response.payload.consent_grant_ref`, `CT-SHC-004:response.payload.grant_state`, `CT-SHC-004:response.payload.data_scope`, `CT-SHC-004:response.payload.decision` | Bind exact subject/resource/recipient/purpose/data scope and independently current grant/policy/revocation. DENY may omit grant ref. Never infer Share or Assignment | VERIFIED_SOURCE_ONLY fields; CONTRACT_MISSING current binding |
| SHARE | Arcava AG-ARC-113 ActivityShareGrant: client, coach assignment, purpose, data scope, consent reference and validity; local SHARE evidence slot | Independently admitted current Arcava grant, not provider permission, consent or coach role alone. No CT-SHC Share producer is assumed | VERIFIED_SOURCE_ONLY owner-local source requirement; UNVERIFIED materialization/authority |
| ENTITLEMENT | `CT-SHC-005:request.payload.principal_id`, `CT-SHC-005:request.payload.capability_code`, `CT-SHC-005:request.payload.resource_ref`; `CT-SHC-005:response.payload.entitlement_ref`, `CT-SHC-005:response.payload.grant_state`, `CT-SHC-005:response.payload.capability_code`, `CT-SHC-005:response.payload.decision` | Bind capability, tenant, subject, purpose and resource with separate grant revision/currentness. DENY may omit grant ref; Enrollment is not entitlement | VERIFIED_SOURCE_ONLY fields; CONTRACT_MISSING current binding |

VERIFIED_SOURCE_ONLY: current synthetic OwnerGuard requires seven gate slots for
coach support; its client path skips ASSIGNMENT while requiring the other six.
That applicability rule is not a general live-role waiver: UNVERIFIED until the
new operation profile and namespace-safe self-client mapping are admitted.
Assignment/Share remain Arcava-owned even when PIAC supplies all five reads.

## Independent revision and time domains

| Domain | Actual source observation | Consumer rule still needed | Status |
| --- | --- | --- | --- |
| Identity | CT-SHC-001 identity_revision | Independently current principal version, not a resource or session revision | VERIFIED_SOURCE_ONLY field; UNVERIFIED currentness |
| Session | CT-SHC-002 session_revision; `CT-SHC-002:response.payload.validity.effective_from` and `CT-SHC-002:response.payload.validity.effective_until` optional within validity | Session revision/currentness/revocation must be checked independently; optional dates cannot become invented proof times | VERIFIED_SOURCE_ONLY fields/optionality; CONTRACT_MISSING authenticated rule |
| Tenant grant | CT-SHC-003 grant_revision | Exact tenant-grant revision and revocation separate from business membership revision | VERIFIED_SOURCE_ONLY field; UNVERIFIED consumer binding |
| Consent grant | CT-SHC-004 payload has no grant revision; E0 records producer private-domain revision data | Export and correlate current consent revision rather than substituting projection_version or tenant grant revision | VERIFIED_SOURCE_ONLY wire absence; CONTRACT_MISSING export |
| Entitlement grant | CT-SHC-005 payload has no grant revision; E0 records producer private-domain revision data | Independent current entitlement revision; never copy consent/session/resource revision | VERIFIED_SOURCE_ONLY wire absence; CONTRACT_MISSING export |
| Policy / decision / revocation epochs | Generic read fields are not the new signed decision; KDB-specific proof epochs belong to another operation | Exact policy/decision versions and revocation/currentness contract for Arcava | CONTRACT_MISSING |
| Resource / assignment / share | Local Request/Evidence each use a single synthetic revision; persisted linkage validates IDs/status, not complete aggregate lifecycle | Independently identify current resource and owner-grant revisions and their race/refresh semantics | VERIFIED_SOURCE_ONLY local shape; CONTRACT_MISSING admitted mapping |

VERIFIED_SOURCE_ONLY: response envelopes require as_of/freshness/projection_version
and source_refs, but `CT-SHC-001:response.valid_until` and
`CT-SHC-001:response.resource_ref` are optional (same envelope shape across five
schemas). `as_of` is not automatically effectiveAt; projection_version is not a
grant revision. No inspected read payload carries revokedAt. Existing consumer
Evidence requires nonnull effectiveAt/expiresAt, CURRENT state, applicable
revokedAt and exact binding of its single revision; those synthetic fields do
not settle producer time/revision contracts.

UNVERIFIED: actual session-currentness, issuer, Arcava audience, authenticated
workload, key custody/rotation and trusted current revocation observations.
CONTRACT_MISSING: exact signed-decision/export/verifier rules for these facts,
expiry/freshness limits, decision-time and read-time checks, races, replay and
safe retries. Missing expiry cannot be filled from requested_at/as_of or an
arbitrary duration. A cached historical ALLOW must not retain revoked rights.

## Trust boundary and future fail-closed sequence (not implemented)

CONTRACT_MISSING: SOV must supply a new operation-specific contract; the existing
KDB_SOURCE_INTAKE proof, KDB SQL-v2 hash and its synthetic issuer cannot authorize
this operation or be widened in place. No signature/proof is issued by R03.

Subject to that future contract and verified R02, the proposed consumer must:

1. Reject missing/malformed selectors and unsupported operation/purpose without
   touching resource storage. Resolve identity exclusively through the admitted
   backend verifier; client references are selectors only.
2. Authenticate issuer and workload for the exact Arcava audience and operation.
   Reject unknown trust/version/key, invalid signature and unapproved delegation.
   Do not copy the KDB trust store or invent an Arcava trust root.
3. Bind actor, delegated subject, PIAC session and Arcava client/tenant mapping,
   target resource, data scope, purpose and all independent revisions. Reject any
   ambiguity; equality of UUID bytes does not bridge namespaces.
4. Apply the admitted currentness/expiry/revocation and replay policy. Reject
   missing, future, expired, revoked, stale, replayed or unavailable proof.
   Single-use/reusable-read semantics, durable replay handling and legitimate
   retries require the new contract; KDB jti behavior is not adopted by default.
5. Compose seven applicable independent gates, including owner Assignment/Share.
   Consent or entitlement cannot override a denied/missing business gate. No
   tenant-admin or service-wide sensitive-read bypass.
6. Only then read the consistent local journal snapshot and enforce its existing
   exact tenant/client/enrollment/version/assignment linkage and PUBLISHED fence.
   No payload is returned when binding or lifecycle checks fail. Concurrency and
   revocation-at-read behavior must satisfy the future admitted contract.
7. Return minimized view/reasons and evidence references under an admitted audit
   policy. Do not log proof tokens, keys, private profile bodies or raw provider
   errors. Producer outage, timeout or inability to establish currentness denies.

VERIFIED_SOURCE_ONLY: today's public OwnerGuard(Clock) resolves null and denies
valid requests with PIAC_NOT_CONNECTED. ArcavaAccessService calls it before any
repository lookup and returns a typed denial with no view. R03 does not change
that behavior, the HTTP surface, journal locking, wire response or test fixtures.

## Future test matrix — PLANNED_NOT_EXECUTED

All rows are CONTRACT_MISSING as executable integration evidence. Preconditions
are the new SOV contract, verified R02 and separately authorized implementation.
These are future oracles, **not test results or an original A09 PASS**.

| Future scenario | Required result / evidence |
| --- | --- |
| Valid assigned coach, exact tenant/client/resource, current independent gates | Minimal admitted read only after authenticated binding and all local checks |
| Valid own-client path | Exact namespace-safe identity mapping and admitted applicability policy; no equality-only shortcut |
| Wrong actor or delegated subject / unsupported delegation | Deny before storage; no view |
| Wrong tenant, ClientProfile or principal-to-client mapping | Deny before storage; no cross-tenant existence leak |
| Wrong resource, resource kind, assignment, enrollment, version or data scope | Deny; no interchangeable profile/enrollment/version identities |
| Wrong purpose, capability or operation; CT-SHC read-ALLOW only | Deny; no constructed execute grant |
| Missing, ended, revoked, invalid or mismatched assignment | Deny independently of consent/share/entitlement |
| Missing/revoked share; consent-only or share-only | Deny; gates cannot stand in for each other |
| Missing or stale identity/session/tenant/consent/entitlement revision | Deny; no synthetic combined revision or projection-version fallback |
| Missing proof, wrong issuer/audience/workload, unknown key/version, invalid signature | Deny before storage; no fallback to KDB proof or caller labels |
| Expired, revoked, not-yet-valid, missing expiry or unavailable current session | Deny; no inferred dates or historic-ALLOW cache |
| Proof replay, retry and concurrent replay | Enforce the agreed replay policy; no second unauthorized disclosure; legitimate retry semantics explicit |
| Producer timeout, error or currentness/revocation channel unavailable | Fail closed, sanitized reason, zero resource payload |
| Revocation or withdrawal after earlier allowed read and after journal replay | Reject subsequent access under the admitted race/currentness rule; retain existing local publication fence |
| Tenant-admin/service overreach; untrusted body/header/context ref | Deny; no role label or caller-provided material confers authority |
| Diagnostics/audit privacy and denied lookup counter | No private body/credential/raw error leak; guard failures make zero storage lookups |

## Validation, handoff and residual gates

VERIFIED_SOURCE_ONLY: R03 validation is source-reference/Markdown/single-file
diff/SHA256 checking. No Java implementation, new producer schema, signature,
SQL/RLS, credentials, HTTP/provider/hosted call, merge or deployment. No E0
self-check rerun or fresh acceptance of the previous 75 Maven tests. Automatic
CI caused by a docs push, if observed, is informational and cannot close Q2.

UNVERIFIED: R02 operational evidence remains pending; C4/R04 independent security
admission remains pending. CONTRACT_MISSING: new SOV operation/export/verifier
and reviewed consumer mapping. This draft supplies only C3/R03 specification
evidence for bounded Owner-QS by GPT_BUILDER_ARCAVA.

GATE_PROGRESS: TARGET_GATE_ID Q2; PARENT_PLAN_ID ARC-36/P25 (ARC10);
PARENT_STEP ARC10-T020; CHILD_PLAN_ID ARC36P25-T020-Q2-CLOSURE-CHILD-01;
CHILD_STEP C3/R03 SPEC_ONLY, draft delivered pending Owner-QS. CLOSURE_EVIDENCE:
this source-bound draft only, not a signed decision or gate closure. RETURN_TO
ARC10-T020; RESUME_CONDITION: scoped Q2 closure evidence after required producer,
R02, consumer and security proof, or a documented externally blocked live path
with independent authorized local work allowed. Next: existing Builder reviews
R03 once and continues this existing child; no repeat R01 request or parallel
SOV/PIAC executor. No new plan or reviewer lane.

UNVERIFIED/open: Q1-Q4, full T020/T110, T150 completion, G04, real producer
integration, SQL/RLS and independent security/hosted/release admission. Original
A09 gates retain their previous status and admitted T48 evidence stays 0/86.
BL-ARC-01 remains OPEN_SCOPED for dependent formal/live paths only. Nutrition
T050/T090 remains NON_ROUTING. No production or security gate is closed.
