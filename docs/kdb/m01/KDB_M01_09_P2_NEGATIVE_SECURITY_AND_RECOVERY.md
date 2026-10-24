# KDB-M01-09 P2 negative security and recovery candidate

Date: 2026-10-24
Issue: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/8
Base: PR #6 frozen at bed66883d48dd882294663ce9d1100e6b7adf7b2
Branch: kdb/m01-p2-negative-security-and-recovery
Do not merge. Do not apply to ujdzahwlximlmndexgmx or zobjpmyccszkabybdmsf.

## New tests

1. Fresh foreign-tenant command with the same `kdb_ingest_runtime` LOGIN.
2. Same command_id and caller-supplied request hash with changed rights/content.
3. Direct table, approval, and promotion attempts as runtime.
4. NULL request hash.
5. Catalog: `pg_default_acl`, applier identity, inherited memberships, schema grants, FORCE RLS on 12 tables, function owner/search_path, future-function PUBLIC EXECUTE.
6. Offline parser/diff of the owner-reported ujdz legacy preimage.

PIAC stays fail-closed. Direct table and promotion attempts are denied.

Observed reviewer-blocking RED findings on disposable PostgreSQL 17:

- `TENANT_GUC_SPOOF_ACCEPTED_AT_DB`
- `REQUEST_HASH_NOT_BOUND_TO_PAYLOAD`
- `FUTURE_FUNCTION_PUBLIC_EXECUTE` (BLOCK_DEFAULT_ACL_CREATOR physically open for the superuser applier)

That is not a security PASS. Hosted apply stays blocked.

## Recovery candidate

`database/migrations/kdb/20261024180000__kdb_m01_p2__forward_recovery_candidate.sql` is `NOT_AUTHORIZED_FOR_APPLY`.
It does not delete the unknown `canonical.protocol` row, reset the ledger, or replay foundation.

## Hygiene

Tracked `__pycache__/*.pyc` under `services/kdb` and `tests/kdb` is removed in this forward commit. Nested ignore files prevent re-adding them.

## Independent review

Collaborator set is only `wordualReality`. `INDEPENDENT_REVIEWER_UNASSIGNED`. CodeRabbit is supplemental.
