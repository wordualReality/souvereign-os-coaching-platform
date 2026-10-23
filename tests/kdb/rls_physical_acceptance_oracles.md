# KDB-M01 physical RLS/principal/contract admission oracles — NOT RUN


**These require an isolated, approved target after Gate A.** Never run on the shared legacy project by assumption. The builder only supplies cases; the executing approved actor records query IDs, returned SQLSTATE, and exact principal under independent security review.


1. Enumerate new schemas; all 11 proposed KDB tables have `relrowsecurity=true`, `relforcerowsecurity=true`; legacy `canonical`, `dev_staging`, `public` owners, functions and row counts byte-equivalent/preimage-compatible.
2. Roles: KDB runtime LOGIN / NOINHERIT / NOBYPASSRLS, no membership in service_role/postgres, cannot SET ROLE owner; function owner and table owner separate NOLOGIN roles. Grantor/CREATEROLE capabilities validated before creating roles.
3. `anon`, `authenticated`, `PUBLIC`, `service_role` cannot USAGE / SELECT / INSERT / UPDATE / DELETE new KDB tables nor EXECUTE new KDB commands. Default FUNCTION EXECUTE also revoked.
4. KDB runtime itself has zero table privileges and only three named `kdb_ops` function EXECUTE grants (O1 O2 O3). `UPDATE`, `DELETE`, `TRUNCATE`, direct `SELECT`, or `INSERT` always DENY.
5. RLS tenant crossing denied for O1–O3; both SQL-level constraints and facade PIAC token verification required. Do not accept a caller-supplied principal_context_ref as authentication. Tenant A source version cannot be linked to tenant B candidate/submission/review work item.
6. Failing rights/purpose, stale/withdrawn SourceVersion, unapproved/expired license, missing PIAC actor, invalid schema, unacceptable hash mismatch, prompt-injection-bearing input => no command receipt, no durable candidate, no outbox mutation; deny or quarantine as designed.
7. Same command ID + same request digest => byte-equal response, exactly one durable receipt; same key with different digest => `KDB_IDEMPOTENCY_CONFLICT`. Two concurrent revisions do not both take the same (candidate_id, revision_no).
8. O3 must issue only review work item/outbox request; `human_review_decision` count remains 0 and no `protocol_version` row appears even when n8n retries O3.
9. `kdb_ops.outbox_event.publish_state='INACTIVE_M01'`; no publisher grant, delivery, activation, O4 withdrawal or O5 projection.
10. Pseudotest promotion under **independently authorized isolated test-only role**, with a real signed human review and fresh rights/safety/taxonomy: atomic protocol version + audit + outbox or zero durable changes on injected failure. Merely passing the Python simulated promotion model is insufficient.
11. SQL/pg catalog: zero new SECURITY DEFINER function under `public`, each controlled function fixed `search_path=pg_catalog`, no PUBLIC EXECUTE, no BYPASSRLS, new definer owner cannot update immutable canonical tables. `dev_staging.set_updated_at` legacy Advisor WARN remains separately owned and is not silently patched.
12. TLS: dedicated KDB facade -> database trust anchor CA chain + DNS host/SNI/SAN with negative mismatched certificate; no `rejectUnauthorized=false`, no SSL=disable/allow fallback, custom CA if required; no privilege escalation or plaintext secrets. n8n itself has no DB LOGIN.
13. 1Password Secrets Automation PRODUCT: scoped secret injection, no value in repositories/Drive/logs, revoke and rotate test with bounded failure behavior, no service_role key or generic n8n 1Password Connect substitution.
14. Test order: isolated schema-only migration -> grant/RLS -> contracts -> concurrency/negative tenant -> mock O1/O2/O3 -> human promotion test -> only then propose separate O4/O5 activation; stop and roll back sandbox on any failure. Never claim physical PASS from offline tests.
