# P26-R2 DEV permission review — NON_APPLY

Target for a future, separately approved review: `ujdzahwlximlmndexgmx` only. **Do not execute this document.** The present hosted role graph, grants, creator identities and object ACL preimages are unknown; every mutation below is `PRECONDITION_UNSATISFIED` until independently captured and reviewed. No owner transfer, command-owner membership, SET-capable transfer operator or broker is admitted. No secret is specified.

Prerequisites include fixed reviewed source SHA, a direct TLS session using separately provisioned 1Password-held credentials, PIAC, independent security review, exact project confirmation, a transaction and a verified preimage with an independently tested recovery. A schema-level CREATE grant cannot enforce an O1–O3 function allowlist. Privileged provider administrators remain possible creators outside KDB change-control. Existing functions and CREATE OR REPLACE preserve their own ACLs; future creator defaults are not retroactive.

## Proposed scope, NOT executable

1. If and only if preimage proves the runner does not exist, create `kdb_migration_runner LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB`. If it exists, capture and separately review its attributes, dependencies and memberships; do not overwrite them.
2. Record exact `kdb_ops` schema ACL; conditionally grant only `USAGE, CREATE` to the runner for an approved job. Verify runtime has USAGE but not CREATE.
3. Direct runner connection must assert both `session_user` and `current_user` equal `kdb_migration_runner`; capture creator-global function `pg_default_acl` including grantor and grantee. Conditionally apply `ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` as that direct creator. Another creator requires separate proof and is not covered.
4. Capture complete `pg_proc` owner, security-definer flag, search path, ACL and `aclexplode` grantor/grantee for each exact function before any named grant or revoke. The reviewed signatures are:
   * `kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)`
   * `kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid)`
   * `kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid)`
5. Only after separate approval and preimage capture, revoke EXECUTE by those exact signatures from PUBLIC, anon, authenticated and service_role; grant EXECUTE by exact signature to `kdb_ingest_runtime`. Review current owner and grantor privileges first; no ownership transfer is included.

The following is an exact review excerpt, not an authorized deployment script. It is deliberately incomplete until the actual preimage and executing grantor are verified; do not copy or run it against DEV:

```sql
-- NON_APPLY / PRECONDITION_UNSATISFIED
CREATE ROLE kdb_migration_runner LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB;
GRANT USAGE, CREATE ON SCHEMA kdb_ops TO kdb_migration_runner;
-- The next statement requires a separate direct runner connection.
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz) TO kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid) TO kdb_ingest_runtime;
GRANT EXECUTE ON FUNCTION kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid) TO kdb_ingest_runtime;
```

Read-only capture must include `SELECT session_user, current_user`, `pg_roles`, `pg_auth_members` with SET/INHERIT/ADMIN options, `pg_namespace.nspacl`, `pg_default_acl` for each actual creator, and `pg_proc` for all three signatures with `proowner`, `prosecdef`, `proconfig`, `proacl` and `aclexplode`. Persist the actual raw and exploded ACLs, grant options and grantors before any separate authorized change.

## Recovery constraints

Do not blindly drop roles, reset default ACLs or replace a captured ACL with assumed defaults. Recovery needs the exact preimage and grantor-authorized restoration of each ACL entry, including grant options; reverse named function ACL changes, restore creator-global defaults from the captured preimage in a direct creator session, restore only changed schema ACL entries, then remove only roles created by the approved change after confirming no dependencies or memberships. Compare `pg_roles`, `pg_auth_members`, `pg_namespace.nspacl`, `pg_default_acl` and `pg_proc.proacl/proowner` with the preimage. Missing or un-restorable preimage means stop. This section is a recovery requirement, not a complete executable rollback script.

## Founder architecture decision — neither option approved

A: independently design and security-review a fixed-code, auditable privileged broker with a database-enforced allowlist and explicit trust boundary. B: consider runner as final owner, with a documented least-privilege and operational-risk analysis. Either requires a separate Founder decision; the current NOLOGIN command-owner architecture is unchanged.
