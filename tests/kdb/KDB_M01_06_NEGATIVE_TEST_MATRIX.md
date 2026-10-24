# KDB-M01-06 negative test matrix

Classification: DESIGN + STATIC now. PHYSICAL = NOT_RUN_NOW unless stated.

| ID | Case | Expected | Now |
|---|---|---|---|
| T01 | Preimage drift (HEAD, parent, B03, dirty tree) | Fail closed if unexpected | STATIC_CAPTURED |
| T02 | PG17 grammar of 001/002/003 | Parse or PG17_PARSE_NOT_RUN | see Owner Return |
| T03 | Repeatable 001 then 002 then 003 on throwaway PG17 | 12 objects, rollback/reapply | NOT_RUN_NOW |
| T04 | Catalog FORCE RLS, eight vs four tables, cross-tenant | Deny cross-tenant and protected DML | NOT_RUN_NOW |
| T05 | Effective EXECUTE/default ACL for PUBLIC/anon/authenticated/service_role | DENY | STATIC_SOURCE_ONLY; BLOCK_DEFAULT_ACL_CREATOR |
| T06 | No PIAC signature | Reject before SQL. No receipt | STATIC: fail-closed facade |
| T06 | Synthetic ALLOW ref | Reject before SQL | STATIC: fail-closed facade |
| T06 | Forged issuer, audience, tenant, purpose | Reject | STATIC design; no verifier |
| T06 | Expired / nbf future / replayed jti | Reject | STATIC design; no verifier |
| T06 | Signed-body mismatch / missing rights | Reject | STATIC design; no verifier |
| T06 | Valid PIAC positive | Unverified physically | NOT_RUN_NOW |
| T07 | Call as real LOGIN kdb_ingest_runtime | session_user check can PASS later | NOT_RUN_NOW |
| T07 | SET ROLE from postgres/admin | Not a positive. 003 checks session_user | STATIC_NOTED |
| T08 | Wrong tenant / purpose / source version | Deny | STATIC source predicates in 003; physical NOT_RUN |
| T08 | Duplicate key, changed digest | KDB_IDEMPOTENCY_CONFLICT | STATIC source; physical NOT_RUN |
| T08 | Hidden-row command UUID collision | Fail closed | STATIC source; physical NOT_RUN |
| T09 | Hostile search_path trap schema | SECURITY DEFINER stays on pg_catalog | STATIC source; physical NOT_RUN |
| T10 | Runtime DML on four protected tables | Deny. No review/promote callable | STATIC source |
| T11 | Outbox publish_state | INACTIVE_M01 only. No ProtocolVersion | STATIC / later catalog |
| T12 | Fault injection, rollback/reapply | No leak, no B03/legacy touch | NOT_RUN_NOW |

GUC `kdb.tenant_scope` is never a positive identity oracle.
