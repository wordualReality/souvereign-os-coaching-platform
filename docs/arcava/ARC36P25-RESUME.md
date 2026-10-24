# ARC-36/P25 resume pointer

Current package: ARC36P25-SERVICE-REMOTE-PUBLICATION-AND-CI-01. Published service commit `a267f62e60a07c6e0128dcaaf509a931556f1e05`. This file records that publication on the same branch.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## Published state

- Remote branch `feat/arc36p25-journey-service-integration` at `a267f62e60a07c6e0128dcaaf509a931556f1e05` before this pointer commit.
- Draft pull request: https://github.com/wordualReality/souvereign-os-coaching-platform/pull/12
- Verified base: `feat/arc36p25-journey-kernel-candidate-20261023` at `515dc46bab5deb03e61e0a34d3ad0c64d4a3fed5`. That commit is the merge base. `main` remains `dd0b145e5f429ff3f8f36f79c2709646d77982a3`.
- Issue #11 is linked and remains open. No reviewer is assigned. The review is not accepted from this checkout.

## CI on a267f62e60a07c6e0128dcaaf509a931556f1e05

- `arcava-journey-kernel` push run 40131520209: success. JDK 21 and JDK 25 each ran `JourneyKernelTest` and the persisted loopback path (`JourneyPathTest`, `JourneyProducerTest`). All four jobs success.
- `arcava-journey-kernel` pull request run 40131549713: success. Same four jobs.
- `project-b-contract-validation` pull request run 40131549709: success. One job, `validate-contracts`: repository structure, OpenAPI, JSON schemas and AsyncAPI parse, SQL migration static fallback, RLS static fallback, MVP Slice 01 skeleton.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. T020, T050 and T160 stay not admitted.

## Next executable step

A different reviewer performs the auth, tenant, consent, withdrawal, journal replay, and KDB pin review on pull request #12. Do not mark that review passed from this checkout. Do not connect live PIAC or live KDB without a real verifier.
