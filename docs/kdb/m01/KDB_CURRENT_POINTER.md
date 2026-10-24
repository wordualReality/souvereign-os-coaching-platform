# KDB current pointer, 2026-10-24

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view

This pointer supersedes older G21-07 STOP/NOT_AUTHORIZED routing for development work inside that grant. Historical C2 pause records remain historical. They do not cancel the Build-to-Beta envelope.

## Physical stand

- Repo: wordualReality/souvereign-os-coaching-platform
- Branch: kdb/m01-03-repository-materialization
- Draft PR: https://github.com/wordualReality/souvereign-os-coaching-platform/pull/6
- Do not merge to main.
- Leave B03 SQL untracked. Leave Arcava `apps/web` and `services/api` to ARCAVA_CURSOR.

## Proven

- Four-schema ADR on disposable PostgreSQL 17.11: apply, FORCE RLS, role graph, rollback/reapply.
- GitHub Actions `kdb-m01-pg17-disposable` SUCCESS on this branch.
- Tenant-guard classifier source copy, O4/O5 inactive, 63/63 offline.
- Local O1-O3 command path and offline replay/DLQ policy.

## Not proven

Hosted recovery on ujdzahwlximlmndexgmx. Live n8n-dev import. PIAC verifier. TLS/1Password.

## Next executable package

Independent DB/security review of PR #6, then read-only preflight on ujdzahwlximlmndexgmx.
Until that review exists, continue local contract/pipeline tests only.
Isolated n8n-dev import only after a verified dev URL, least-privilege identity, and TLS probe.

## Setup already reported once

S03 ujdz OAuth plus independent review. S04 PIAC contract. S05 isolated n8n-dev. S06 durable runner.
Do not re-request those grants. Do not apply to zobjpmyccszkabybdmsf.
