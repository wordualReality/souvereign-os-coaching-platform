# ARC-36/P25 resume pointer

Current package: ARC36P25-SERVICE-PUBLISH-AND-TRUST-BOUNDARY-01. Implementation commit `771bae3f56e08192b38ce0d2df72795bd03a6590`. Parent `fe3ec2b7708137ab98d3c354cfe725b57041badb` remains the consumed local producer milestone. This file is the pointer on the same branch.

## Checkout

- Worktree: `/Users/aydin/Documents/GitHub/arcava-journey-worktree`
- Branch: `feat/arc36p25-journey-service-integration`
- Push only with `git push -u origin HEAD:refs/heads/feat/arc36p25-journey-service-integration`.
- Do not push `feat/arc36p25-journey-kernel-candidate-20261023`. Do not merge to `main`.
- The KDB checkout was not modified.

## Trust boundary added on top of the local producers

- `Application.main` stays `WebApplicationType.NONE`. It does not start `JourneyHttpServer`. Maven `ApplicationBootstrapTest`: 1 test, 0 failures, Spring Boot 4.1.1.
- `TrustedKdbVerifier.NONE` rejects a caller pin that claims `publication_state` `PUBLISHED` or a `rights_state` other than `caller-supplied-not-verified`. That path returns CT-ARC-002 `REVALIDATION_REQUIRED`. The existing fixture pin stays `DRAFT` and `caller-supplied-not-verified`.
- A request that supplies `runtime_session_refs` is CT-ARC-004 `NOT_FOUND`. The service does not copy a SOV session. The successful fixture response still has `runtime_session_refs` empty.
- After withdrawal, the access decision id differs from the earlier allow and stays the same across restart. A new assignment key returns `WITHDRAWN`.
- `JourneyProducerTest` rerun after this change: PASS. Captured producer bodies remain 15 and match the frozen result and error schemas, 0 fail. Journey path and the isolated ARC-P16 96/96 run were not repeated.

## Not claimed

This is not live PIAC, not a live KDB verification, not T150 acceptance, and not a SOV-ready producer. Issue #11 is open and has no assigned reviewer. It cannot be bound to a remote commit until this branch is published.

## Next executable step

One GitHub HTTPS login on this Mac, then push this branch, read back the remote commit, open or reuse a draft PR from the actual ancestry, and attach that commit and PR to issue #11. A different reviewer performs the security review. Do not mark that review passed from this checkout.

## Setup still required

`gh auth status` reports no GitHub host login. The one-time command is `gh auth login --hostname github.com --git-protocol https --web`, then `gh auth setup-git` and `gh auth status`. No runner continues this session after it ends.
