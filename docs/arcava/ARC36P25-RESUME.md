# ARC-36/P25 resume pointer

Current package: ARC36P25-T150-OPERATOR-ENV-EVIDENCE-01. Parent `ab20302a4344207095d6f478b5ce2dfee762dda4`. The local JAR packet and ARC-01 and ARC-02 stay closed. This checkout does not accept the new operator and config review.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## T150 evidence in this slice

- `docs/arcava/admission/toolchain-manifest.json`
- `docs/arcava/config/environment.schema.json`
- Smoke now requires `LIVE_HTTP 200` and `DENIED_HTTP 403`, and rejects a synthetic HTTP 200 that only carries a denial body.
- The non-loopback start waits at most 10 seconds.
- `OPERATOR_START` and `OPERATOR_STOP` stay `REQUIRED_OPEN`.
- Frontend renderer, runner and lock stay `UNVERIFIED`. `apps/web` has route skeletons and no package lock.
- A09-T01, A09-T04, A09-T44 and A09-T48 stay `NOT_EXECUTED`.

## Local evidence

Temurin 25.0.3, Maven 3.9.16. `mvn -B -f services/api/pom.xml package` exit 0, 8 tests, 0 failures. JAR SHA-256 `07c3e79b6b23c7d4c9be976e914587ad1c3eaa098139a084a818eef451ee9e0c`. Smoke exit 0: live 200, ready 503, absent bearer 401, denied 403, journal unchanged, SIGTERM 143, restart closed, non-loopback exit 1 inside 10 seconds. `scripts/validate_repo.py` exit 0.

## Not claimed

This is not full T150 admission, not live PIAC, not a live KDB verification, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. T020 does not start before full T150 admission.

## Next executable step

Independent delta review of this operator, config and HTTP status oracle by a reviewer who did not write it. After that review, the remaining T150 renderer and effective-config work continues in the existing owner order.
