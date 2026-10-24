# KDB-M01-08 local command path and replay policy

Date: 2026-10-24
Branch: kdb/m01-03-repository-materialization
Parent capability: local PostgreSQL 17 apply of 001-003.

## What this packet proves

LOGIN as `kdb_ingest_runtime` on disposable PostgreSQL 17:

1. O1 `ingest_source` records a synthetic submission.
2. Same command_id and request hash returns the existing receipt.
3. Same command_id with a different hash raises `KDB_IDEMPOTENCY_CONFLICT`.
4. Superuser call raises `KDB_PRINCIPAL_DENIED`. Empty tenant raises `KDB_CONTEXT_REQUIRED`.
5. Pending rights raise `KDB_RIGHTS_NOT_ADMITTED`.
6. Foreign tenant reuse of the command_id fails closed.
7. O2 `propose_candidate` and O3 `request_review_handoff` replay the same receipts.
8. Canonical publication tables stay empty. Outbox stays `INACTIVE_M01`.

Offline n8n fixture policy:

- Never retry DENIED, REVOKED, RIGHTS_RESTRICTED, CONFLICT, INJECTION, POISON, UNKNOWN_COMMIT.
- Transient UNAVAILABLE, RATE_LIMIT, TIMEOUT may retry only until an owner-selected budget. This packet does not invent a number.
- In-memory receipt store: same idempotency key and body digest replays. A different digest is CONFLICT.

## What this packet does not prove

No n8n import. No hosted apply on ujdzahwlximlmndexgmx. No zobj write.
No 1Password. No PIAC signature. No publication. No production scheduler.
