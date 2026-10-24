# KDB-M01-11 P4 digest and oracle integrity

Date: 2026-10-24
Issue: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/14
Base: PR #13 frozen at 51b67fba22fa8e3a991051947d939ba9f7e11c21
Branch: kdb/m01-p4-digest-oracle-integrity
Do not merge. Do not apply to ujdzahwlximlmndexgmx or zobjpmyccszkabybdmsf.
Do not amend P1, P2, or P3. Do not change PR #6, PR #9, or PR #13.

## What changed

1. P4-01: v2 digest is `jsonb_build_array` plus `jsonb::text` SHA-256. NULL, empty string, and embedded newlines stay distinct. v1 `concat_ws` helper raises `CANONICAL_DIGEST_CONTRACT_UNRESOLVED`.
2. P4-02: O2 includes `evidence_spans` digest. Changed spans under the same claimed hash must mismatch.
3. P4-03: P4 oracles require exact denial text. Connection, syntax, missing function, and division-by-zero errors are RED. Temporary-grant tests cover O1, O2 and O3.
4. P4-04: O1/O2/O3 consult `security_context_ready()` and still raise `KDB_SECURITY_CONTEXT_NOT_CONFIGURED` if it were true.
5. P4-05: `kdb_migrator` future functions, including SECURITY DEFINER probes, keep no untrusted EXECUTE. Superuser PUBLIC EXECUTE remains `BLOCK_DEFAULT_ACL_CREATOR`.

Positive O1-O3 ingest stays `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. PIAC stays fail-closed.

## Arcava notice

Producer `request_sha256` must match SQL v2. This packet does not edit Arcava files.

## Independent review

`INDEPENDENT_REVIEWER_UNASSIGNED`. CodeRabbit is supplemental. Hosted apply and merge stay blocked.
