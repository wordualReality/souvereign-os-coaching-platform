# KDB-M01 Step 2 — ADR-M01-01 Physical Schema/Legacy Boundary v1.0


**ADR decision: ACCEPT AS OFFLINE DESIGN / GATE A PHYSICAL APPLY PENDING.** Owner: KDB Principal Data Architect; separate security/IAM approval required for actual use.


## Decision


Build KDB-isolated owner namespaces **`kdb_canonical`**, **`kdb_governance`**, **`kdb_staging`**, **`kdb_ops`** inside a separately admitted PostgreSQL/Supabase *environment*, with `kdb_derived` postponed. `canonical` and `dev_staging` in the observed active Supabase project retain their EXISTING legacy identity, objects, ownership and RPC. **Do not rename/re-own/mutate** those legacy schemas. `KDB-07` describes logical canonical, governance, candidate, derived and ops responsibilities; M01 maps logical canonical to `kdb_canonical` and logical candidate to `kdb_staging` in order to prevent existing-name collisions. This is a physical namespace ADR, not a replacement of the frozen semantic model.


## Physical tables and ownership


| Owner schema | MVP tables | Writes admitted by proposed O1–O3 functions | Future protected writes |
|---|---|---|---|
| `kdb_governance` | source, source_version, human_review_decision | Source and immutable SourceVersion only | Signed HumanReviewDecision via distinct KDB reviewer command |
| `kdb_staging` | submission, candidate_revision, review_work_item | O1/O2/O3 only | corrections are new immutable revisions |
| `kdb_canonical` | protocol, protocol_version, lifecycle_event | **NONE** | independently admitted, signed KDB promotion/lifecycle |
| `kdb_ops` | command_receipt, outbox_event, audit_event | Idempotency/audit and dormant outbox with `INACTIVE_M01` | delivery/ACK only after separate grant |


There are **12 table definitions** in the proposed foundation. New KDB schema and table owner `kdb_schema_owner` NOLOGIN; command function owner `kdb_command_owner` NOLOGIN NOBYPASSRLS, distinct from table owner; execution principal `kdb_ingest_runtime` LOGIN NOBYPASSRLS NOINHERIT with **only** selected EXECUTE grants on three schema-bound functions, never direct table DML. No fallback to postgres/service_role or inherited privileged membership. `FORCE ROW LEVEL SECURITY` on all new relations and default deny until precise grants. RLS policies for the command owner are tenant-scoped via a server-side transaction-local GUC; this is **defense in depth, not independently authenticated tenant identity**. The facade **must cryptographically authenticate signed PIAC tenant/purpose evidence** before calling; `access_decision_ref` is only a trace ID.


## Legacy / compatibility ADR


- Read-only inventory and versioned anti-corruption adapter or approved export/snapshot are the only allowed bridge, not a synonym/direct alias permitting writes; legacy `canonical.protocol` is **not** the new `kdb_canonical.protocol_version`.
- Historical public SECURITY DEFINER functions are NOT reused for KDB-M01 O1/O2/O3; they currently expose `service_role` EXECUTE ACL and require separate B03 treatment. Do not patch them inside KDB-M01.
- No direct `dev_staging.protocol_candidate` upsert or automatic backfill. Any migration of approved legacy content must preserve rights/evidence hash, assign new KDB identities and pass new human review, never infer canonical admission.
- No cross-owner cascading FK. KDB supplies versioned producer API/immutable refs to Arcava and SOV. Arcava owns JourneyVersion/delivery, SOV owns runtime tracking and DecisionTrace.


## Alternatives assessed


1. **Reuse existing `canonical`/`dev_staging`**: REJECT as default; RLS lacks FORCE, ownership remains historical postgres, public RPCs carry legacy service_role permissions. No permission to modify this preimage.
2. **New owner schemas in shared PostgreSQL project**: CONDITIONAL; separate grants and independent versioned migration are possible, but only if the exact environment is named and role/creation rights, pooler, TLS/1Password, RLS tests and blast radius are proven.
3. **Physically isolated KDB service/database**: valid later ADR option; not presupposed or fabricated. Freeze typed contracts now to permit future split without Arcava dependency.
4. **n8n direct PostgreSQL**: REJECT as M01 runtime architecture; even if TLS is conditionally source-supported, n8n may not acquire table rights or canonical authority. Use KDB-owned authenticated service facade for command submission, with TLS+PIAC+1Password gate.


## Hard nonfunctional controls


No client/private Personal Hub or Arcava chat/tracking data in KDB candidate ingestion. Requirements: explicit license/use purpose/retention/source ownership, full pagination and content hash, no untrusted source instruction execution, candidate-only AI, deterministic validation before a human review, immutable signed HumanReviewDecision, separate KDB promotion transaction, exact protocol version, lifecycle-based future eligibility and append-only evidence. Idempotency is command+tenant+origin identity, conflicting payload hash is CONFLICT; time stamps preserve occurred/recorded/emitted/received semantics. Errors fail closed.


## Reversibility and admission


`sql/001...` only proposes new schemas; first physical step must be isolated and reversible, never an automatic legacy replacement. `sql/002...` grants require separately proven CREATEROLE/owner inheritance and negative ACL tests; `sql/003...` is a guarded service-command proof candidate and not safe to expose until PIAC gateway signature validation is implemented and tested. `099_rollback_and_forward_fix.md` separates pre-data compensating reversals from append-only data forward fixes.


**Physical mutation is blocked at Gate A.** No scheme/role/function has been created by this package.
