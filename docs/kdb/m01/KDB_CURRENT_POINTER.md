# KDB current pointer, 2026-10-24 P5

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: GitHub Issue #16

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638` remain frozen.
This pointer is the P5 working branch. Older G21-07 STOP text does not cancel the grant.

## Physical stand

- Worktree: isolated `kdb/m01-p5-signed-ingress-digest-parity`
- Do not merge P1-P5 to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.

## P5 work

SQL-v2 producer parity, synthetic signed ingress, DB still fail-closed. Positive O1-O3 remains `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. Hosted apply remains blocked.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
