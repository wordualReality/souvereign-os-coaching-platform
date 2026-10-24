# ARC-36/P25 resume pointer

Current package: persisted local coach and client journey path. Passed on 2026-10-24.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
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

Read the accepted CT-ARC-002, CT-ARC-003 and CT-ARC-004 contract text. Implement producer backing on this journal and loopback service only for fields those contracts actually define. Keep fixture pins and the consent directory labelled untrusted until a real adapter is connected. Do not start from a new kernel.

## Setup still required

- Maven, so the preserved Spring Boot 4.1.1 pom can host this path.
- A PIAC token and consent source. The current bearer map is a fixture.
- A KDB publication verifier. The current receipt hash is caller input.
- The CT-ARC contract documents are not in this worktree.
- No runner is attached to this session. This file is the resume point. It does not continue execution after the session ends.
