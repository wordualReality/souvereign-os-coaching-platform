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
- `OPERATOR_RETURN.md`

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

## Operational handoff

Follow `docs/evidence/MINIMAL_OPERATOR_HANDOFF.md`.

When repository writes are authorized, the executor must:

1. write the complete evidence under the packet directory;
2. create the short `OPERATOR_RETURN.md`;
3. commit and push code plus evidence on the packet branch;
4. create or update the pull request with result SHA and evidence path;
5. stop without merging or starting the successor.

The operator must not be asked to paste long logs into chat. The normal operator message is only:

`Prüfe <PACKET_ID> in PR #<number>.`

## Integrity and privacy

- Preserve raw command output where safe.
- Redact credentials, tokens, personal data and unrestricted production identifiers.
- Record redaction without exposing the secret.
- Hash immutable release artifacts.
- Distinguish local, CI, staging and production evidence.
- A screenshot must show only the necessary state and must be redacted.
- A file, workflow or prompt existing is not execution evidence.
- Do not commit dependencies, caches, raw real-data dumps or unnecessary large binaries.

Evidence must be readable by an independent reviewer without this chat.
