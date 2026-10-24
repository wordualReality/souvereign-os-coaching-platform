# KDB-M01-07 local PostgreSQL 17 recovery

Date: 2026-10-24
Branch: kdb/m01-03-repository-materialization
P06 bytes preserved. 004 not applied. zobjpmyccszkabybdmsf not contacted.
Dedicated dev ujdzahwlximlmndexgmx not applied.

## What ran

Disposable Docker `postgres:17` as `kdb-m01-pg17-disposable` on `127.0.0.1:55432`.
Server: PostgreSQL 17.11.
Harness: `python3 tests/kdb/pg17_disposable_apply.py`

Result: PASS_PG17_LOCAL_APPLY_ROLLBACK_REAPPLY
Fingerprint: `390be49bcda1c33e2bff5f4b0c0361e8f0828f1d8d17cd1265825e258652170a` identical after rollback/reapply.

Catalog oracles: 12 FORCE-RLS tables owned by kdb_schema_owner; three SECURITY DEFINER functions owned by kdb_command_owner; anon/authenticated/service_role EXECUTE denied; runtime has no table DML on protocol_version.

pg_default_acl: empty on this cluster. ALTER DEFAULT PRIVILEGES in 002 did not create a durable defacl row. BLOCK_DEFAULT_ACL_CREATOR remains.

SET ROLE from superuser: session_user stays the superuser. That is not a T07 positive.

Unauthorized SELECT as runtime via SET ROLE: permission denied for schema kdb_canonical.

## Tenant-guard candidate

Offline classifier: baseline 37/37 PASS, tenant negatives 0/26 FAIL.
Candidate: 37/37 plus 26/26 tenant negatives PASS (63/63). Not a live n8n or PIAC proof.

## Not done

No dedicated-dev apply. No zobj apply. No n8n import. No 1Password. No PIAC verifier.
