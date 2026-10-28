# KDB current pointer, 2026-10-28 consumer security delta 03

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-CONSUMER-SECURITY-DELTA-03
Binding brief: https://github.com/wordualReality/souvereign-os-coaching-platform/issues/16#issuecomment-6466498190
Independent return: https://docs.google.com/document/d/16DGW83X6vHTjM42BSQjF_ethPI-iuCxmn7h6nkb45Mw/edit

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2`, PR #21 `2ba7ae44` remain frozen.
OFFLINE-01 and COMPAT-HARDEN-02 on PR #22 are consumed. Do not rewrite PR #21. One forward commit on PR #22 from `24ba4d9`.

## Physical stand

- Worktree: isolated `kdb/m01-p5-sov-proof-consumer-offline`
- Do not merge P1-P5, PR21, or this consumer packet to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.

## Delta 03

K01 small-order Ed25519 reject. K02 process-wide default replay store. K03 SOURCE_INTAKE command[1] bind. K04 default Unix clock. K05 typed JSON ValueError/RecursionError. Default remains `DISABLED_CONTRACT_ONLY`. Pin stays `f68760d`. `NEEDS_SOV_SECURITY_QS`. `CRYPTO_VALIDATION_NOT_LIVE`. `DURABLE_REPLAY_NOT_CONFIGURED`. Never `DB_COMMAND_ADMITTED`.

## Setup already reported once

S03 to S06 unchanged.
