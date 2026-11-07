# A04-R1 local creator admission and restore boundary

This additive patch and manifest preserve the A04 SQL and manifest byte-for-byte.
The harness composes A04 foundation, the R1 patch and guarded P3/P4 derivatives
inside **one disposable transaction**, then commits or aborts it as a whole.
The R1 patch alone is not a hosted migration or an authenticated admission.
The foundation's postgres-created function has its global creator default
hardened before creation; R1 hardens the owner roles before they create any
functions. P3 hardens the synthetic migrator before its first function. No
independent commits between the guarded steps are claimed safe.

In the isolated fixture, `postgres`, `kdb_schema_owner`,
`kdb_command_owner` and `kdb_migrator` each create a fresh function without
PUBLIC EXECUTE after their respective global defaults are configured. The
unknown test creator retains the PostgreSQL PUBLIC default in a separate lab
schema but is denied CREATE in admitted KDB schemas. The schema owner has
implicit CREATE; it is not hidden by a schema-USAGE check. Injected unknown
CREATE grants, membership with SET TRUE, extra grant option and a superuser
session switched to the owner role are denied by the R1 SQL guard.

The versioned local PREAPPLY_CREATOR_ADMISSION evaluator compares a synthetic
catalog snapshot containing target claim, source/manifest pins, session and
current identity, all scoped schema owners and effective creators, global and
per-schema default-function ACLs, raw ACLs and grantor/grantee/option entries,
memberships and exact function signatures/definition hashes. Unknown or
duplicate creator/function, wrong grantor, grant option, missing global
default, raw NULL function ACL, mismatched source, role switch, or a purported
verified provider/backup is `BLOCKED_CREATOR_AUTHORITY`. Catalog booleans and
labels are untrusted input: even a local match never authenticates its origin.
The evaluator is a read-only post-composition disposable verification in the
harness, not an enforcement gateway for an external SQL session.

The positive result is only `LOCAL_CREATOR_SAFE_FOR_DISPOSABLE` and always
includes `NOT_AUTHORIZED`, `AUTHORITATIVE_TARGET_NOT_VERIFIED`, and
`POSTCOMMIT_RESTORE_UNVERIFIED`. The existing raw-ACL experiment is preserved:
pre-COMMIT abort restores its tested scoped snapshot, while committed
REVOKE+GRANT restores effective PUBLIC execution but not original NULL
`proacl`. R1's combined pre-COMMIT abort and local postcommit cleanup also
restore their separately defined limited snapshots; no general raw-catalog
inverse, actual backup, postcommit recovery or customer-row preservation is
proved.

The actual hosted creator set, real authenticated runner, target binding,
signed PIAC, owner transfer, backup/restore, separate independent P25/security
review and explicit founder mutation authorization remain open. The SQL guard
uses disposable database/temporary markers and a simulated postgres session;
these are not trusted hosted identity. Hosted, production, merge and real
provider execution are not authorized.
