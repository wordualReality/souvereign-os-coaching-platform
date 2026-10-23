# ARC-36/P25 — JourneyKernel isolated development slice

Source: published `main` on 2026-10-23, plus the accepted Project B v1.0 OpenAPI journey and client-assignment path. Prepared in a **separate feature branch**, because the Founder-Mac's newer local-only Spring Boot/JDK25 work is unavailable to the connected GitHub session. Do not merge, cherry-pick or wire HTTP controllers until local worktree/source hashes are reconciled.

## Implemented

- In-memory, source-only pure Java `JourneyKernel`: create/update draft with optimistic revisions, immutable published journey-version snapshots, exact string version pins, synthetic coach/client assignment, withdrawal, and idempotent create/publish/assignment intents.
- Fail-closed negative scenarios: cross-tenant coach access, client-subject mismatch, missing consent, stale revision, missing KDB approval/rights fixture, conflicting idempotency key, withdrawn version.
- Offline executable test fixture in `JourneyKernelTest` with no network, DB, secrets, Maven or extra dependency.

## Verification

From repo root, with available JDK >=21:

```sh
mkdir -p /tmp/arcava-kernel-classes
javac -d /tmp/arcava-kernel-classes \
  services/api/src/main/java/com/projectb/api/domain/JourneyKernel.java \
  services/api/src/test/java/com/projectb/api/domain/JourneyKernelTest.java
java -cp /tmp/arcava-kernel-classes com.projectb.api.domain.JourneyKernelTest
```

## Explicit non-acceptance

This is not an Arcava producer, an HTTP service, Spring Boot wiring, a persistent datastore, a published-KDB proof verifier, a PIAC/consent authority, a running UI, or SOV-facing transport. Fixture-supplied actors, consent, KDB-approval flags and receipt hashes are **untrusted inputs**. They do not grant runtime authority. `CT-ARC-002/003/004`, T150, T020/T050/T160, G01/PIAC, security review and browser E2E remain OPEN/NOT_ADMITTED as applicable. All canonical KDB and SOV data remain untouched.

Integrate behind trusted PIAC and KDB adapters only after local Spring Boot source has been reconciled. Persistent transactions, uniqueness constraints, outbox, reliable idempotency and authorization require separate implementation/tests. Later use the native accepted JDK25 toolchain in CI.
