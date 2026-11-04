# M01 Step 9 readiness — local scoped, not admission

Scope: disposable PostgreSQL 17 and synthetic test actors only. `M01_STEP9_PARTIAL / M01_STEP6_PARTIAL / NOT_ADMITTED / NOT_SECURITY_PASS`. This is not a full M01, 18-of-18, hosted or security decision.

| Original Step 9 area | Evidence and boundary | Status |
| --- | --- | --- |
| Local source and contracts | `docs/kdb/m01/STEP7_SYNTHETIC_GOVERNANCE_CONTRACT.md`; `services/kdb/offline_governance_promotion.py`; Step7 CI 41499625478 at c2a7fa4c4354c7c2b80ebe97558d86d396b66e52 | VERIFIED_LOCAL_SCOPED |
| SQL and tenant invariants | `tests/kdb/pg17_step8_adversarial.py`, `docs/kdb/m01/STEP8_DB_FALSIFICATION.md`; Step8 CI 41605711377 at 673e12cd3669389c5436677c89f0cac4cbc54681. One tenant FK case; full tenant/security semantics not proven | PARTIAL |
| Roles, ACL and creator | `tests/kdb/pg17_p25_creator_default_acl.py`, `tests/kdb/pg17_p26_runner.py`, `docs/kdb/m01/P26_R2_NON_APPLY_REVIEW.md`. Single synthetic creator and local abort proved; other creators and hosted role/ACL restore open | PARTIAL |
| C04/C05 integrity | `tests/kdb/pg17_step8_adversarial.py` reveals SQL-only bypass; `tests/kdb/fixtures/step8_local_guard_candidate.sql` is test-only, not production DDL | PARTIAL |
| Rights and revocation, split transactions | `tests/kdb/pg17_step9r2_split_transactions.py`: committed C04 then committed REVOKED causes C05 23514; separate control publishes before later revoke. Later revocation lifecycle policy is undefined | VERIFIED_LOCAL_SCOPED |
| Concurrent commits | `tests/kdb/pg17_step9_guard_race.py` reproduces uncoordinated race; `tests/kdb/pg17_step9r1_lock_append.py` tests two row-lock schedules; R1 CI 41641254232 at 12cff8be9e74ccff3768ee188a181bbef40310d7 | VERIFIED_LOCAL_SCOPED |
| Append-only | `tests/kdb/pg17_step9r1_lock_append.py`: test-only DELETE trigger 23514 versus existing FK 23503; superuser may disable trigger | VERIFIED_LOCAL_SCOPED |
| Regression and CI | `.github/workflows/kdb-m01-pg17.yml`: exact-head CI on delivered commit is authoritative; prior Step7/8/9 and P25/P26 retained | VERIFIED_LOCAL_SCOPED only when exact-head CI succeeds |
| Rollback/reapply | `tests/kdb/pg17_step9r1_lock_append.py` and `tests/kdb/pg17_step9r2_split_transactions.py`: named fixture unapply/reapply, bounded zero residual; not full catalog/hosted ACL parity | PARTIAL |
| Real reviewer and cryptographic authority | TEST_ONLY strings are not signatures, authenticated identity or authority | UNPROVEN |
| Full 18-of-18 and full schema diff | Not established by this packet | UNPROVEN |
| Hosted deployment and advisors | No hosted query or apply in this packet | BLOCKED_HOSTED |

The split test uses separate direct local superuser sessions for committed synthetic decision, revocation and attempted promotion. A control case uses a fresh fixture, commits C04, commits C05/PUBLISHED while ADMITTED, then commits a later revocation. `REVOKED|PUBLISHED` in that ordered control is historical publication before revocation; withdrawal/revalidation/retention is not decided here. No real rights, external human approval, signature verification or live policy is inferred.
