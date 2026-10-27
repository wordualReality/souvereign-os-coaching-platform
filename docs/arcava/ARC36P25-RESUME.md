# ARC-36/P25 resume pointer

Current package: ARC36P25-T150-FRONTEND-RENDERER-RUNNER-LOCK-01. Parent `221ef5422d24b8d24c7d9436f9de3bbdcf7b41da`. The operator and environment delta is consumed as PASS_WITH_CONDITIONS_DELTA_SCOPE_ONLY for that five-file scope. The local JAR packet and ARC-01 and ARC-02 stay closed. This checkout does not accept the frontend review.

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
- Frontend: Next.js 16.4.3, React 19.3.1, lock `package-lock.json`, runner `next start` on `127.0.0.1`. Admission stays `PROPOSAL_EXERCISED_NOT_ADMITTED`. The versions come from the npm registry on 2026-10-27. They are not an ARC-10 source pin.
- The environment schema is still not a proven validator of the effective Spring runtime configuration.
- A09-T01, A09-T04, A09-T44 and A09-T48 stay `NOT_EXECUTED`.

## Local evidence

Temurin 25.0.3, Maven 3.9.16. `mvn -B -f services/api/pom.xml package` exit 0, 8 tests, 0 failures. JAR SHA-256 `07c3e79b6b23c7d4c9be976e914587ad1c3eaa098139a084a818eef451ee9e0c`. JAR smoke exit 0: live 200, ready 503, absent bearer 401, denied 403, journal unchanged, SIGTERM 143, restart closed, non-loopback exit 1 inside 10 seconds.

Web smoke on Node v20.12.2: `apps/web/scripts/renderer-smoke.sh` exit 0. Next.js 16.4.3 served `/`, `/coach/journeys`, `/client/member-home` and `/admin/provisioning` with HTTP 200 on `127.0.0.1`, then SIGTERM 143. The service-role name was absent from the build output.

## Not claimed

This is not full T150 admission, not live PIAC, not a live KDB verification, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. T020 does not start before full T150 admission.

## Next executable step

Independent delta review of the frontend renderer, runner and lock only. Do not reopen `221ef54`, the JAR packet, the Spring boundary, or ARC-01 and ARC-02. This checkout does not accept that review.
