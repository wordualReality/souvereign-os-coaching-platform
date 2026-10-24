# ARC-36/P25 resume pointer

Current package: ARC36P25-CTARC-JOURNAL-PRODUCER-INTEGRATION-01. Local producer reads passed on 2026-10-24. Live producer admission stays open.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Do not check out `main` or `feat/arc36p25-journey-kernel-candidate-20261023`.
- The KDB checkout was only read. Its uncommitted files were not modified.

## What passed here

- ARC-P16 validator on an isolated 24-file tree, CPython 3.12.14, jsonschema 4.26.0: 14 groups, 96 subcases, 0 fail, exit 0, empty stderr. The full repository is larger than 24 files, so the lock is proven on that isolated copy of the same bytes, not by deleting service files.
- Contract paths match PR #7 commit `86b6a12c4eb04d003eff70262e13c3816708bd39`.
- `JourneyKernelTest`: 27 checks PASS.
- `JourneyPathTest`: PASS.
- `JourneyProducerTest`: PASS. Fifteen captured producer bodies validated against the frozen result and error schemas, 0 fail.
- Maven 3.9.16 with Temurin 25.0.3 resolved Spring Boot 4.1.1 from Maven Central. `mvn -f services/api/pom.xml test` built the non-web bootstrap. Tests run: 1, failures: 0. That Maven run does not replace the HTTP tests.

## Producer boundary

CT-ARC-002, CT-ARC-003 and CT-ARC-004 are read from the append-only journal. A bearer token is a local directory. `principal_context_ref` must match that subject and is not a PIAC call. `consent_decision_ref` does not grant consent. Canonical bindings are stored caller input, with `rights_state` `caller-supplied-not-verified`. CT-ARC-004 returns an empty `runtime_session_refs` array. No KDB or SOV write is performed.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. Independent security review of the auth, tenant and consent boundary is still pending a different reviewer after this branch is published.

## Next executable package

Publish this branch once GitHub HTTPS credentials work, then request the separate security review of the service diff. Do not mark runtime producer ready from this local evidence.

## Setup still required

- `git push -u origin HEAD:feat/arc36p25-journey-service-integration` previously failed with `could not read Username for 'https://github.com': Device not configured`.
- No runner continues this session after it ends.
