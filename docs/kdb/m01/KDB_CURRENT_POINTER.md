# KDB current pointer, 2026-10-28 P07 tenant guard

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-M01-P07-BOUND-TENANT-GUARD-AND-SOURCE-FOUNDATION-01

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2`, PR #21 `2ba7ae44` remain frozen.
PR #22 stays untouched at `0078c03`. This pointer is local branch `kdb/m01-p06-local-worktree-recovery` from accepted PR21.

## Physical stand

- Worktree: isolated `souvereign-os-coaching-platform-kdb-p06`
- Do not merge to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.
- Do not rewrite PR #15, #17, #20, #21, or #22.
- Do not import or activate n8n workflows.

## P07 tenant guard

Version-controlled inactive `n8n/kdb-dev/tenant-guard-candidate` already holds the corrected Fail Closed Classify nodes. P07 adds the same fail-closed `tenant_scope` rule to `services/kdb/tenant_scope.py`, checks it before PIAC, and records 37/37 plus 26/26 plus extra oversize/non-string regressions. Synthetic ALLOW is still rejected. Not a hosted or live ingest admission.
