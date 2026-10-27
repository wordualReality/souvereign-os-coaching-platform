# KDB current pointer, 2026-10-27 P5 SOV proof consumer offline

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-P5-SOV-PROOF-CONSUMER-OFFLINE-01
Binding brief: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/16#issuecomment-6441056187

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2`, PR #21 `2ba7ae44` remain frozen.
This pointer is `kdb/m01-p5-sov-proof-consumer-offline` from accepted PR21 SHA `2ba7ae44`. RB02 is consumed. Do not rewrite PR #21.

## Physical stand

- Worktree: isolated `kdb/m01-p5-sov-proof-consumer-offline`
- Do not merge P1-P5, PR21, or this consumer packet to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.
- Do not rewrite PR #15, #17, #20, or #21.

## Consumer packet

Versioned `PIAC_DECISION_PROOF_V1` consumer, default `DISABLED_CONTRACT_ONLY`.
SOV producer pin `f68760d799831ff260f99eb5b02358a1a3bda979` is CONTRACT ONLY, not
normative adoption. Known producer findings remain. `NEEDS_SOV_SECURITY_QS`
is a named dependency. Synthetic proofs may be `LOCAL_VERIFIED_ONLY`.
They are never `DB_COMMAND_ADMITTED`. Positive O1-O3 remains
`BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`. Hosted apply remains blocked.

## Setup already reported once

S03 to S06 unchanged. INDEPENDENT_REVIEWER_UNASSIGNED.
