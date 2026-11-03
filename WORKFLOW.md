# Recursive Delivery Workflow

## Control loop

For every block:

1. Read predecessor prompt, return, evidence and gate.
2. Read current Drive/Notion control state and cross-lane register.
3. Verify repository, branch, base SHA and worktree.
4. Confirm Definition of Ready.
5. Execute one bounded objective with one writer.
6. Run required positive and negative tests.
7. Store evidence without credentials or personal data.
8. Perform independent review.
9. Issue one gate: `PASS`, `PASS_WITH_BLOCKERS`, `REPAIR_REQUIRED`, `BLOCKED` or `FAILED`.
10. Record lessons learned, deviations and open dependencies.
11. Update durable control artifacts.
12. Generate exactly one successor from the actual result and stop.

## Implementation sequence

- FPS-00C: repository governance, source bridge, standards and evidence controls.
- FPS-01: implementation-authoritative contracts and deterministic packet runner.
- FPS-02: local database baseline under DB-owner authority.
- FPS-03: effective access, manual provisioning and coach assignment.
- FPS-04: journey draft, immutable publication, enrollment and member delivery.
- FPS-05: minimal outbox/worker or approved workflow integration.
- FPS-06: integrated hardening, demo release and parking handover.

The exact successor may reduce scope or insert a repair block. Calendar order never overrides an actual gate.