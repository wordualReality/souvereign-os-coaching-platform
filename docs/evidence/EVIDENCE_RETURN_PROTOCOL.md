# Evidence Return Protocol

## Directory

Store packet evidence under:

`evidence/<packet-id>/<UTC-timestamp>/`

Recommended structure:

- `00_manifest.json`
- `01_return.md`
- `02_commands.log`
- `03_git_before.txt`
- `04_git_after.txt`
- `05_diff.patch`
- `06_tests/`
- `07_security_privacy/`
- `08_database_workflow/`
- `09_screenshots_redacted/`
- `10_reviews/`
- `11_gate/`
- `12_successor/`

## Mandatory return fields

- `BLOCK_ID`
- `STATUS`
- `OWNER_LANE`
- `ACTIVE_ROLES`
- `INPUTS_READ`
- `REPOSITORY`
- `BRANCH`
- `BASE_SHA`
- `RESULT_SHA`
- `WORKTREE_START`
- `WORKTREE_END`
- `FILES_CHANGED`
- `COMMANDS_AND_EXIT_CODES`
- `TEST_RESULTS`
- `SECURITY_PRIVACY_RESULTS`
- `DATABASE_WORKFLOW_RESULTS`
- `EVIDENCE_PATH`
- `DECISIONS`
- `DEVIATIONS`
- `OPEN_GAPS`
- `BLOCKERS`
- `LESSONS_LEARNED`
- `GATE`
- `AUTHORIZED_NEXT_ACTION`
- `SUCCESSOR`

## Integrity and privacy

- Preserve raw command output where safe.
- Redact credentials, tokens, personal data and unrestricted production identifiers.
- Record redaction without exposing the secret.
- Hash immutable release artifacts.
- Distinguish local, CI, staging and production evidence.
- A screenshot must show only the necessary state and must be redacted.
- A file, workflow or prompt existing is not execution evidence.

Evidence must be readable by an independent reviewer without this chat.