# KDB current pointer, 2026-10-24 P3

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: GitHub Issue #10

P1 remains accepted and frozen: PR #6 head bed66883d48dd882294663ce9d1100e6b7adf7b2.
P2 remains characterization-only and frozen: PR #9 head 3692a275deae3a670c2f70d8115a0046dab96fef.
This pointer is the P3 working branch. Older G21-07 STOP text does not cancel the grant.

## Physical stand

- Worktree: isolated `kdb/m01-p3-fail-closed-security`
- Do not merge P1, P2, or P3 to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.

## P3 work

Fail-closed tenant, hash-binding, and kdb_migrator default-ACL patches. Positive O1-O3 remains `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. Hosted apply remains blocked.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
