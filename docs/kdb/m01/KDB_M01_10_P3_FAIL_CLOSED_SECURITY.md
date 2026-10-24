# KDB-M01-10 P3 fail-closed security patches

Date: 2026-10-24
Issue: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/10
Base: PR #9 frozen at 3692a275deae3a670c2f70d8115a0046dab96fef
Branch: kdb/m01-p3-fail-closed-security
Do not merge. Do not apply to ujdzahwlximlmndexgmx or zobjpmyccszkabybdmsf.
Do not amend P1 or P2. Do not change PR #6 or PR #9.

## What changed

1. RED-01: O1/O2/O3 `EXECUTE` is revoked from `kdb_ingest_runtime`. `session_user` and caller GUCs are not tenant proof. Commands raise `KDB_SECURITY_CONTEXT_NOT_CONFIGURED`. No synthetic ALLOW path.
2. RED-02: the database recomputes a v1 canonical digest and compares it to the stored digest, not to the caller hash as identity. Changed bytes under the same `command_id` raise `KDB_HASH_MISMATCH` or `KDB_IDEMPOTENCY_CONFLICT` before any prior receipt is returned.
3. RED-03: dedicated `kdb_migrator` with creator-global function defaults that revoke PUBLIC EXECUTE. A function created by that role must not be executable by PUBLIC, anon, authenticated, or service_role.

Positive O1-O3 ingest is `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. PIAC stays fail-closed. P2 recovery SQL stays `NOT_AUTHORIZED_FOR_APPLY`. 004 and 098 are not applied.

## Tests

- `tests/kdb/pg17_p3_security_oracles.py` exits nonzero if any of the three attack paths remain open.
- Command path asserts runtime EXECUTE revoked.
- P2 adversarial/ACL scripts remain forensic characterization and must not be treated as a security PASS by themselves.
- Superuser-created functions may still inherit PUBLIC EXECUTE. That is `BLOCK_DEFAULT_ACL_CREATOR`. Hosted apply stays blocked.

## Independent review

Collaborator set is only `wordualReality`. `INDEPENDENT_REVIEWER_UNASSIGNED`. CodeRabbit is supplemental. Hosted apply and merge stay blocked until a human DB/Security reviewer accepts the P3 head.
