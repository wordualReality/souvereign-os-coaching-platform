# KDB current pointer, 2026-10-27 P5 SOV consumer compat harden 02

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-P5-SOV-CONSUMER-COMPAT-HARDEN-02
Binding brief: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/16#issuecomment-6442277281

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2`, PR #21 `2ba7ae44` remain frozen.
OFFLINE-01 on PR #22 `fb1d76d7` is consumed. Do not rewrite PR #21. One forward commit on PR #22.

## Physical stand

- Worktree: isolated `kdb/m01-p5-sov-proof-consumer-offline`
- Do not merge P1-P5, PR21, or this consumer packet to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.
- Do not rewrite PR #15, #17, #20, or #21.

## Compat harden 02

Claim-to-command bindings for all signed SOURCE_INTAKE fields, trust kid/algorithm/SPKI consistency, lone-surrogate fail-closed, `\b`/`\f` JSONB short-escape proof against PG17, single-process replay check-and-insert. Default remains `DISABLED_CONTRACT_ONLY`. SOV pin stays `f68760d`. Observed producer `0ad4516` is documented, not adopted. `NEEDS_SOV_SECURITY_QS` remains named. Synthetic proofs may be `LOCAL_VERIFIED_ONLY`. They are never `DB_COMMAND_ADMITTED`.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
