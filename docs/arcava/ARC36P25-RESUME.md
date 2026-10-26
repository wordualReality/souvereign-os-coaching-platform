# ARC-36/P25 resume pointer

Current package: ARC36P25-SPRING-ACTIVE-RUNTIME-TRUSTED-PORTS-01. Parent `dbe66d1a701397b333e7d25751381b38347e0f17`. ARC-01 and ARC-02 stay closed for that repair. This checkout does not accept the new delta review.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## Active development listener

`Application.ROLE` is `ACTIVE_DEV_HTTP`. It starts Spring Boot 4.1.1 on `127.0.0.1`. `GET /health/live` is 200. `GET /health/ready` is 503 while PIAC and KDB transports are absent. A non-loopback bind fails before the socket opens.

`InactiveBootstrap.ROLE` stays `NON_WEB_INACTIVE_BOOTSTRAP` and does not open a socket. `JourneyHttpServer` stays `TEST_LOOPBACK_ONLY`.

## Trusted ports

`DenyByDefaultPiacConsumer` and `DenyByDefaultKdbPublicationVerifier` admit no live transport. Null, timeout, stale, error, revoked consent, a fixture bearer, and a caller-supplied `PUBLISHED` pin stay denied. A dummy allow still ends at `LIVE_ADAPTER_NOT_ADMITTED`. Fixture credentials do not authorize `/project-b/` routes. Denied requests do not append to the journal.

Repo A `PiacApplicationService.java` is not in this checkout. Live invocation stays not admitted.

## Local evidence

- JDK 25.0.3, Maven 3.9.16: `mvn -B -f services/api/pom.xml test`, 8 tests, 0 failures. The lifecycle test opened a Tomcat listener, read live and ready, denied fixture traffic, stopped, and restarted on the same journal bytes.
- JDK 25.0.3: `JourneyKernelTest` 27 checks, `JourneyPathTest`, `JourneyProducerTest`, `JournalAtomicityTest`, `AuthorityBoundaryTest` PASS.
- `javac --release 21` of the non-Spring sources: exit 0. A JDK 21 runtime is not installed on this Mac. GitHub CI still runs those sources on JDK 21 and JDK 25. The Spring listener job is JDK 25 and Maven 3.9.16.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. Issue #11 stays open for a different reviewer of this new boundary.

## Next executable step

Independent delta review of this Spring and IAM boundary by a reviewer who did not write it. Do not resubmit the unchanged ARC-01 and ARC-02 repair. Do not mark the review passed from this checkout.
