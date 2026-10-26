# ARC-36/P25 resume pointer

Current package: ARC36P25-EXECUTABLE-JAR-PACKAGE-LIFECYCLE-01. Parent `45e001fce81c4d8f969acf934a2ecea76bd62110`. The local Spring delta QS is consumed for that commit only. ARC-01 and ARC-02 stay closed. This checkout does not accept the new JAR review.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## Executable JAR

Without an explicit main class, `spring-boot-maven-plugin:4.1.1:repackage` failed: `Unable to find a single main class from the following candidates [com.projectb.api.Application, com.projectb.api.inactive.InactiveBootstrap]`. The plugin now sets `mainClass` to `com.projectb.api.Application`. `InactiveBootstrap` remains the non-web fixture.

The repackaged file is `services/api/target/projectb-api-0.1.0-SNAPSHOT.jar`. Manifest: `Main-Class: org.springframework.boot.loader.launch.JarLauncher`, `Start-Class: com.projectb.api.Application`, `Spring-Boot-Version: 4.1.1`.

## Local java -jar evidence

Temurin 25.0.3, Maven 3.9.16. `mvn -B -f services/api/pom.xml package` exit 0, 8 tests, 0 failures. `services/api/scripts/jar-lifecycle-smoke.sh` exit 0 on that JAR. SHA-256 `07c3e79b6b23c7d4c9be976e914587ad1c3eaa098139a084a818eef451ee9e0c`. Live 200 with `ACTIVE_DEV_HTTP` and closed authority. Ready 503. Absent bearer 401. Fixture bearer 403 `LIVE_AUTHORITY_CLOSED`. Journal bytes unchanged. SIGTERM exit 143, then the port refused connections. Restart repeated the closed checks. `--server.address=0.0.0.0` exit 1.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. T020, T050 and T160 stay not admitted. A CI rebuild can hash differently because the archive carries build timestamps. CI must rerun the same smoke on its own JAR.

## Next executable step

Independent delta review of this packaged JAR boundary by a reviewer who did not write it. Do not resubmit the unchanged Spring listener review or ARC-01 and ARC-02. Do not mark the review passed from this checkout.
