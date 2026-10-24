# KDB-M01-12 P5 producer parity and signed local ingress

Date: 2026-10-24
Issue: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/16
Base: PR #15 frozen at 348f638ff507348ebfa4dbd085245ffaed67381c
Branch: kdb/m01-p5-signed-ingress-digest-parity
Do not merge. Do not apply to ujdzahwlximlmndexgmx or zobjpmyccszkabybdmsf.
Do not amend P1-P4. Do not change PR #6, #9, #13, or #15.

## What changed

1. P5-00: tenant-spoof under temporary EXECUTE is CLOSED only on `KDB_HASH_MISMATCH`. `test_p4_digest_static.py` runs in CI.
2. P5-01: SQL golden vectors for O1/O2/O3 including NULL vs empty, newline, Unicode, evidence-span changes, and wrong version.
3. P5-02: KDB adapter `services/kdb/digest_v2.py` must match PostgreSQL bytes. Compact JSON.stringify is a negative test.
4. P5-03: ephemeral HMAC verifier with issuer, audience, kid, jti, nbf/exp, replay and revocation. No checked-in key. Missing revocation registry is `REVOCATION_PROOF_UNAVAILABLE`.
5. P5-04: valid synthetic MAC is `LOCAL_SIGNED_INGRESS_VERIFIED`. Direct DB ingest stays `DB_COMMAND_NOT_ADMITTED`.
6. P5-06: Arcava notice in the digest contract. No Arcava files edited.

CI labels: `SQL_V2_PARITY_PASS`, `SIGNATURE_NEGATIVE_PASS`, `DB_FAIL_CLOSED_PASS`. Not `E2E_BETA_PASS`.

## Independent review

`INDEPENDENT_REVIEWER_UNASSIGNED`. CodeRabbit is supplemental. Hosted apply and merge stay blocked.
