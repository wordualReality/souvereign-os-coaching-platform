# Definition of Done

A packet is done only when the bounded objective is implemented or documented within its authority and independently reviewable.

## Required completion evidence

- [ ] Base and result SHA are recorded.
- [ ] Changed files are within the allowlist and no forbidden path changed.
- [ ] Commands and exit codes are captured.
- [ ] Required positive, negative, security, tenant, database and workflow tests pass or failures are explicitly gated.
- [ ] Diff is reviewed for scope, contracts, architecture, privacy and status accuracy.
- [ ] No credentials, raw personal data or unrestricted production identifiers are stored.
- [ ] Documentation, traceability and status vocabulary are updated where required.
- [ ] Deviations, assumptions, open gaps and blockers are recorded.
- [ ] Independent review is complete.
- [ ] Exactly one allowed gate is issued.
- [ ] Exactly one successor is generated from the actual result.

## Non-completion

The following do not constitute Done:

- code generation without tests;
- static parse checks presented as runtime proof;
- a prompt or agent claiming success;
- files existing without execution evidence;
- deployment without authorization and rollback evidence;
- a partially executed workflow classified as production-ready;
- unreviewed direct changes to `main`.