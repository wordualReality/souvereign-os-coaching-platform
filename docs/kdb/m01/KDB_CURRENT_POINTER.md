# KDB current pointer, 2026-10-26 P5 review delta

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-P5-INDEPENDENT-DELTA-QS dual-ERROR classifier uniqueness on PR #21

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2` remain frozen.
This pointer is `kdb/m01-p5-review-delta` from accepted PR20 SHA `a2b55c23`. Older G21-07 STOP text does not cancel the grant.

## Physical stand

- Worktree: isolated `kdb/m01-p5-review-delta`
- Do not merge P1-P5 or this delta to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.
- Do not rewrite PR #15, #17, or #20.

## P5 review delta

Typed fail-closed signed-ingress errors, runtime synthetic HMAC keys, exact
primary `ERROR: KDB_SECURITY_CONTEXT_NOT_CONFIGURED` trust denial (DETAIL/CONTEXT
mentions are RED), and unresolved unproven SQL-v2 adapter types. Positive O1-O3
remains `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. Hosted apply remains blocked.
Accepted KDB-01/KDB-02 is not replayed.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
