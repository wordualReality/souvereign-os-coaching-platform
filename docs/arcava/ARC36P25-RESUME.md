# ARC-36/P25 resume pointer

Current package: ARC-P25-JOURNAL-AND-AUTHORITY-BOUNDARY-REPAIR-01. Parent `59feaad556ae69fe792c2b4d4505db144142bf22`. This commit is the repair. Independent delta re-QS is not accepted from this checkout.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## ARC-01

Before the repair, a failed append left the draft in memory: the same idempotency key then returned `IDEMPOTENCY_CONFLICT`, while a restart did not see the draft. The journal now commits a complete line before the kernel or projection can see it. A trailing partial line is discarded on open. A complete malformed interior record fails open. Withdrawal is one committed record. A failed withdraw does not revoke. Replay and a new assignment key stay `WITHDRAWN` across restart. HTTP commit failure returns 503 `PERSISTENCE_FAILED`.

## ARC-02

`JourneyHttpServer.start` is `TEST_LOOPBACK_ONLY` with fixture bearer tokens and a local consent directory. `startLive` throws before any listener when PIAC or KDB is not a verified authority. `TrustedKdbVerifier.NONE` and `TrustedPiacVerifier.NONE` do not verify live publication or identity. A request-body consent flag, an unknown bearer, a caller KDB publication claim, and supplied `runtime_session_refs` do not become authority. `Application.main` stays `NON_WEB_INACTIVE_BOOTSTRAP`.

## Local evidence

- JDK 25.0.3: `JourneyKernelTest` 27 checks, `JournalAtomicityTest`, `AuthorityBoundaryTest`, `JourneyPathTest`, `JourneyProducerTest` PASS. Producer bodies 15, schema fail 0.
- `javac --release 21` of the same sources: exit 0. A JDK 21 runtime is not installed on this Mac. GitHub CI runs JDK 21 and JDK 25.
- Maven 3.9.16, Spring Boot 4.1.1: `ApplicationBootstrapTest` 2 tests, 0 failures.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. Issue #11 stays open for a different reviewer.

## Next executable step

Independent delta re-QS of this repair commit by a reviewer who did not write it. Do not mark that review passed from this checkout.
