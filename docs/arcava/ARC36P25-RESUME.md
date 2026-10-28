# ARC-36/P25 resume pointer

Current package: ARC36P25-T150-TOOLCHAIN-SOURCE-AND-A09-CASE-BOOTSTRAP-01. Parent `292b7366682287a0e8a93474f47ddf1fb6e17f50`. The pre-build refusal delta is consumed as PASS_WITH_CONDITIONS_DELTA_SCOPE_ONLY for that scope. Earlier frontend, operator, JAR, Spring, ARC-01 and ARC-02 reviews stay closed. This checkout does not accept the new review.

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
- Local operator procedures for the JAR and the Next shell are `EXERCISED_LOCAL`: start, ready, stop, restart, UNKNOWN after a dead pid, and recovery. Hosted operator admission stays open.
- Effective config: `/health/effective` returns the bind, port, role and profile, plus a hash of the journal path. The path itself is not in the response. `scripts/validate_effective_config.py` accepts that object and rejects a non-loopback address, a missing or empty journal, a wrong role, a port outside 0-65535, and an extra `DATABASE_URL`.
- Frontend lock stays `PROPOSAL_EXERCISED_NOT_ADMITTED`. The registry versions are not an ARC-10 source pin.
- The web operator refuses `SUPABASE_SERVICE_ROLE_KEY` and `NEXT_PUBLIC_*` before `npm ci` and `next build`. The build then runs in an allowlisted environment: `PATH`, `HOME`, `TMPDIR`, `NEXT_TELEMETRY_DISABLED=1`.
- E1 authority stays `NOT_ADMITTED`. The running listener reports `LIVE_AUTHORITY_CLOSED` with PIAC and KDB transport not connected. No E1 issuer, engine or owner receipt is in this worktree.
- Registry pins for Node, Next, React and TypeScript stay `PROPOSAL_EXERCISED_NOT_ADMITTED`.
- `scripts/toolchain_receipt.py` checks Java 25, Maven 3.9.16, Spring Boot 4.1.1, Node 20.12.2, Next 16.4.3, React 19.3.1 and TypeScript 7.0.2 against the pom, the lock and the workflows. The current Maven suite is 10 tests. Admission stays `PROPOSAL_EXERCISED_NOT_ADMITTED` because `docs/arcava/admission/toolchain-owner-pin.json` is absent.
- `scripts/a09_case_discovery.py` reports A09-T01, A09-T04, A09-T44 and A09-T48 as `NOT_EXECUTED`. A case file without an owner receipt and an engine does not pass.

## Local evidence

Temurin 25.0.3, Maven 3.9.16. The JAR packet observed 8 tests. The current suite is 10 tests, 0 failures. JAR SHA-256 `07c3e79b6b23c7d4c9be976e914587ad1c3eaa098139a084a818eef451ee9e0c`. JAR smoke exit 0: live 200, ready 503, absent bearer 401, denied 403, journal unchanged, SIGTERM 143, restart closed, non-loopback exit 1 inside 10 seconds.

Web smoke on Node v20.12.2: `apps/web/scripts/renderer-smoke.sh` exit 0. Next.js 16.4.3 served `/`, `/coach/journeys`, `/client/member-home` and `/admin/provisioning` with HTTP 200 on `127.0.0.1`, then SIGTERM 143. The service-role name was absent from the build output.

Operator receipts on 2026-10-27: Maven package 10 tests, 0 failures. `operator-active-dev.sh` exit 0 with live 200, ready 503, effective schema pass, SIGTERM 143, UNKNOWN, crash 137, recovery with the journal unchanged, non-loopback exit 1, blank journal exit 1. `operator-web.sh` exit 0 with four HTTP 200 routes, SIGTERM 143, UNKNOWN, crash 137, recovery HTTP 200, telemetry disabled, and a forbidden env key refused without printing its value.

## Not claimed

This is not full T150 admission, not live PIAC, not a live KDB verification, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. T020 does not start before full T150 admission.

## Next executable step

GPT_BUILDER_ARCAVA consumes this return and decides the next build. Review scope is the toolchain receipt and the A09 discovery only. Do not reopen `292b736`, the operator procedures, the frontend renderer, the JAR packet, the Spring boundary, or ARC-01 and ARC-02. This checkout does not accept that review.
