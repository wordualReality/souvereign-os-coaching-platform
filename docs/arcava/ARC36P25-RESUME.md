# ARC-36/P25 resume pointer

Current package: persisted local coach and client journey path. Passed on 2026-10-24.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Commit: `e4cc801fc896bd65548be2688fb624f498ec0ca2`
- Base: `515dc46bab5deb03e61e0a34d3ad0c64d4a3fed5` (PR #5 head, including the JDK 21/25 kernel workflow)
- The KDB checkout `/Users/aydin/Documents/GitHub/souvereign-os-coaching-platform` on `kdb/m01-03-repository-materialization` was not modified.

## What this commit proves

`JourneyPathTest` starts `JourneyHttpServer` on `127.0.0.1`, writes an append-only journal, stops the process, opens the same journal, and checks the restored assignment. It also checks cross-tenant denial, a second client denied on the same assignment, withdrawal, and replay after withdrawal. A request body cannot grant consent. The consent directory and bearer tokens are process fixtures, not PIAC. Canonical pin fields remain untrusted input, not a KDB adapter.

Commands, from the worktree, with Temurin 25:

```sh
classes_dir="$(mktemp -d /tmp/arcava-journey.XXXXXX)"
javac -Xlint:all -Werror --release 25 -d "$classes_dir" \
  services/api/src/main/java/com/projectb/api/domain/JourneyKernel.java \
  services/api/src/main/java/com/projectb/api/domain/JourneyJournal.java \
  services/api/src/main/java/com/projectb/api/json/JsonMini.java \
  services/api/src/main/java/com/projectb/api/http/JourneyHttpServer.java \
  services/api/src/test/java/com/projectb/api/domain/JourneyKernelTest.java \
  services/api/src/test/java/com/projectb/api/http/JourneyPathTest.java
java -cp "$classes_dir" com.projectb.api.domain.JourneyKernelTest
java -cp "$classes_dir" com.projectb.api.http.JourneyPathTest
```

Local result: both commands printed PASS. `JourneyKernelTest` reported 27 checks.

## Not claimed

This is not T150 acceptance, not Spring Boot runtime, not Next.js runtime, not a live PIAC or KDB adapter, and not accepted CT-ARC-002/003/004 producer transport. The local Spring Boot pom and Next.js files remain uncommitted in the KDB checkout. They were not overwritten and were not executed here. Maven is not on PATH, so the existing Spring pom was not built.

## Next executable package

The physical producer schemas are not in this worktree. Start from ARC-27, file `1lnTmPDejSeXRSZExQtj8mjE3nE6M2k2XMW_HAQI8tiU`, and use only the accepted CT-ARC-002, CT-ARC-003 and CT-ARC-004 schema files once they are present. Implement producer backing on this journal and loopback service for fields those schemas define. Keep fixture pins and the consent directory labelled untrusted until a real adapter is connected.

## Setup still required

- GitHub push from this machine. `git push -u origin HEAD:feat/arc36p25-journey-service-integration` stopped with `could not read Username for 'https://github.com': Device not configured`. The commits are local. Do not push this branch onto `feat/arc36p25-journey-kernel-candidate-20261023`.
- Maven 3.9.16 is present, but not on PATH. Binary: `/Users/aydin/Desktop/Tech docs /SouvereignOSProjectKontext/Sovereign OS/03_Arcava/_Lokal_Entpackt_und_Arbeitsordner/ARC36_P25_R8/ARC36P25_R8_RUN_20261010_002721_025017/apache-maven-3.9.16/bin/mvn`. It runs on Temurin 25.0.3. The local cache has `spring-boot-starter-web` 3.5.5 only. Spring Boot 4.1.1 is not cached, so the preserved pom still needs a dependency download before it can host this path.
- A PIAC token and consent source. The current bearer map is a fixture.
- A KDB publication verifier. The current receipt hash is caller input.
- No runner is attached to this session. This file is the resume point. It does not continue execution after the session ends.
