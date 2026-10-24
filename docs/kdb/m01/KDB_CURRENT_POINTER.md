# KDB current pointer, 2026-10-24 P2

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: GitHub Issue #8

P1 remains accepted and frozen: PR #6 head bed66883d48dd882294663ce9d1100e6b7adf7b2.
This pointer is the P2 working branch. Older G21-07 STOP text does not cancel the grant.

## Physical stand

- Worktree: isolated `kdb/m01-p2-negative-security-and-recovery`
- Do not merge P1 or P2 to main.
- Leave B03 SQL and Arcava paths to their owners.

## Proven on P1

Disposable PostgreSQL 17 apply/rollback/reapply and O1-O3 LOGIN command path. CI 40089748909.

## P2 work

Adversarial tenant/hash/direct-privilege tests, ACL catalog, hosted recovery candidate and offline preflight diff. Hosted apply remains blocked.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
