# Return Protocol -- Project B

Date: 2026-07-01

## When Returning to This Repo
1. Read README.md
2. Read CLAUDE.md
3. Read MASTER LIVE STATUS: https://app.notion.com/p/38be5a7ff397817f9161df25073033bb
4. Read documentation/project-b/operator-contract.md
5. Run: python scripts/validate_repo.py
6. Read: architecture/p01-decoupling-decision.md before any implementation

## Stop Conditions (Master Rule 7)
If task requires: canonical.*, dev_staging.*, protocol runtime tables,
getProtocolDetail() without approved canonical_ref, or Broad UI:
-> Create NEEDS_ALIGNMENT.md in repo root and stop.

## After Any Change
1. npm run validate:all
2. Record output
3. Update LIVE STATUS block if milestone reached
