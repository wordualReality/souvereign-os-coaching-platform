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

Local PG17 counterexample: a function whose raw `proacl` is NULL retains an explicit ACL array after `REVOKE EXECUTE ... FROM PUBLIC` followed by `GRANT EXECUTE ... TO PUBLIC`. Its effective PUBLIC EXECUTE is restored, but raw catalog equality is not. Therefore the inverse shown conceptually above is not a complete raw-preimage rollback. `FAIL_CLOSED RAW_NULL_FUNCTION_ACL_NOT_RESTORED_BY_GRANT_INVERSE`; no direct catalog update or hosted mutation is authorized. A separately reviewed decision is needed on the required parity definition or another proven recovery method. The local test additionally checks a grant-option entry and a separate delegated grantor, but does not claim a general-purpose ACL restoration algorithm.

## Preimage-class decision — NON_APPLY

| Preimage | Current decision |
| --- | --- |
| Existing function with `proacl IS NULL` | No committed ACL mutation under the current raw-parity contract. A same-session rollback before commit preserves NULL locally; it is an abort control, not postcommit recovery. |
| Explicit non-NULL ACL with one authorized grantor | Conditional replay only after recording exact raw ACL and sorted grantor, grantee, privilege and grant-option entries, owner and dependencies, and proving replay on an isolated copy. The limited local examples do not prove general parity. |
| Multiple grantors, delegated grant options, role dependencies or multiple creator sessions | FAIL_CLOSED until the actual identities, dependency chain and postcommit exact restoration are independently proven; no substitution of an administrator as grantor. |
| Newly created disposable role/function | A scoped transaction rollback or controlled removal only when ownership and dependencies are proved and the exact preimage can be compared. This is not authority to remove hosted objects. |

The PG17 test runs BEGIN, REVOKE, observations and ROLLBACK in one authenticated creator session. It observes raw NULL and PUBLIC EXECUTE before, an explicit ACL and denied PUBLIC EXECUTE during, and the original NULL and allowed EXECUTE after rollback and after reconnect. PostgreSQL transactions belong to one database session: separate creator/grantor logins cannot be joined into one ordinary transaction by concatenating their BEGIN and COMMIT commands. `MULTI_SESSION_ATOMIC_RECOVERY_UNPROVEN`; no two-phase commit, prepared transaction or privileged broker is proposed.

Founder decision candidate: retain strict physical raw-catalog parity and prohibit committed mutations of existing NULL-preimage function ACLs, or separately review and authorize a different parity/release strategy with its consequences. The latter is not assumed approved. The existing owner-transfer broker versus runner-ownership decision is a separate decision.

## Founder architecture decision — neither option approved

A: independently design and security-review a fixed-code, auditable privileged broker with a database-enforced allowlist and explicit trust boundary. B: consider runner as final owner, with a documented least-privilege and operational-risk analysis. Either requires a separate Founder decision; the current NOLOGIN command-owner architecture is unchanged.
