# Controlled Status Vocabulary

Use only the following evidence statuses:

- `VERIFIED_REALITY`: observed directly in repository, environment or accepted evidence.
- `APPROVED_DECISION`: accepted owner or cross-lane decision.
- `SPECIFIED`: documented requirement/design not yet implemented.
- `BLUEPRINT_ONLY`: design or workflow definition not imported/executed.
- `PLACEHOLDER_UNFILLED`: deliberate skeleton without completed behavior.
- `IMPLEMENTED`: code/configuration exists at a named SHA; execution may still be pending.
- `IMPORTED_DISABLED`: workflow/configuration imported but inactive.
- `IMPORTED_ACTIVE`: imported and active; execution outcome still separate.
- `DEPLOYED`: delivered to a named environment; verification still separate.
- `EXECUTED_PASS`: executed with accepted evidence and passing result.
- `EXECUTED_FAIL`: executed with accepted evidence and failing result.
- `NOT_EXECUTED`: no accepted execution evidence.
- `ASSUMPTION`: unverified statement requiring confirmation.
- `OPEN_GAP`: missing requirement, decision, artifact or evidence.
- `BLOCKED`: cannot proceed due to named authority/source/environment dependency.
- `SUPERSEDED`: retained historical source that no longer controls implementation.

Do not replace these with vague labels such as `done`, `ready`, `secure`, `compliant` or `production-ready` without a defined gate and evidence.