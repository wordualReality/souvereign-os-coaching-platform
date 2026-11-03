# Controlled Session Start

Use this checklist at the start of every Cursor, Codex, Claude Code or local implementation session.

1. Open the repository root and confirm the expected repository.
2. Run `git status --short --branch` and `git rev-parse HEAD`.
3. Confirm the branch is the packet branch, never `main`.
4. Read `AGENTS.md` and `docs/control/READ_FIRST.md`.
5. Read the accepted predecessor return and gate.
6. Read the exact packet prompt, applicable contracts and owner-lane sources.
7. State the objective, non-goals, allowed paths, forbidden actions and evidence destination.
8. Check `docs/quality/DEFINITION_OF_READY.md` and stop if any mandatory item is missing.
9. Execute only the bounded packet.
10. Run required tests and collect the evidence defined in `docs/evidence/EVIDENCE_RETURN_PROTOCOL.md`.
11. Perform an independent review and issue exactly one allowed gate.
12. Generate exactly one successor and stop.

Never continue because an agent offers to implement additional work.