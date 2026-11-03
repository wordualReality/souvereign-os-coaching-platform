# Minimal Operator Handoff

Status: CURRENT GOVERNANCE CONTROL

## Objective

The operator must not copy large terminal, test or agent outputs into chat. Cursor or the local executor stores the complete return in the repository and pushes it to the packet branch. The implementation controller reviews it through GitHub.

## Mandatory output location

For every executed packet:

`evidence/<packet-id>/<UTC-timestamp>/`

The packet must create:

- `00_manifest.json`
- `01_return.md`
- `02_commands.log`
- `03_git_before.txt`
- `04_git_after.txt`
- `05_diff.patch`
- applicable test/review/gate files
- `OPERATOR_RETURN.md`

## OPERATOR_RETURN.md

Keep this file short and use exactly these fields:

```text
PACKET_ID:
STATUS:
BRANCH:
RESULT_SHA:
EVIDENCE_PATH:
PR_NUMBER_OR_URL:
OPERATOR_ACTION:
```

`OPERATOR_ACTION` must be one small instruction such as:

- `Ask Implementation Control to review PR #<n>.`
- `No action; packet is blocked and evidence is stored.`
- `Founder approval required for <specific reserved action>.`

## Git handoff

Unless the packet explicitly forbids repository writes:

1. Store the complete evidence under the packet path.
2. Redact secrets, personal data and unrestricted production identifiers.
3. Commit code and evidence to the packet branch.
4. Push the packet branch.
5. Create or update the packet pull request.
6. Put the evidence path and result SHA in the PR body or a PR comment.
7. Stop.

Do not merge, start a later packet or request that the operator paste logs into chat.

## Size controls

Do not commit:

- `node_modules`, build caches or dependency directories;
- raw database dumps containing real data;
- credentials, `.env` files or tokens;
- large generated binaries that are not needed for review;
- repetitive logs without diagnostic value.

For large CI output, store the workflow run/job reference and a concise relevant excerpt. For necessary binary evidence, use an approved GitHub artifact or controlled Drive release location and record its URL and hash.

## Operator interaction

After execution, the operator should only need to write:

`Prüfe <PACKET_ID> in PR #<number>.`

The implementation controller then reads the branch, PR, evidence directory and CI status through GitHub and issues the gate and successor.

## Drive and Notion

Git/GitHub is the operational implementation and evidence channel. After review, the implementation controller mirrors accepted gates, decisions and durable release artifacts to Google Drive and Notion. Cursor does not need direct Drive write access for the normal packet loop.
