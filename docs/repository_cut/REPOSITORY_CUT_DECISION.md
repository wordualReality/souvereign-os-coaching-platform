# Repository Cut Decision

The architecture is no longer extended in this step. This repo cut tests executable readiness by placing all leading contracts and prompts into a repository shape with CI validation.

## Execution order

1. Validate contracts and repository shape.
2. Execute v1.1 hardening prompts.
3. Implement manual client provisioning.
4. Implement journey template/cohort/branch-rule primitives.
5. Resume baseline v1.0 Cursor execution order.
