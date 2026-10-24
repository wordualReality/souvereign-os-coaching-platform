# KDB-M01-06 security boundary freeze

Packet: KDB-M01-06-CURSOR-LOCAL-SECURITY-HARDENING-001
State: LOCAL UNCOMMITTED SOURCE DRAFT. Not applied. Not committed.

## Owner graph (S01)

- `kdb_schema_owner`: NOLOGIN NOBYPASSRLS. Table and schema owner.
- `kdb_command_owner`: NOLOGIN NOBYPASSRLS. Function owner. SELECT/INSERT only on eight intake/ops tables.
- `kdb_ingest_runtime`: LOGIN NOINHERIT NOBYPASSRLS. EXECUTE on three `kdb_ops` functions only. No table DML.

The applying migration user is not proven. CREATEROLE/grantor proofs remain OPEN.

## Default ACL (T02)

`ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_ops REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` binds the unproven session user only. It is not proof against global PUBLIC EXECUTE defaults or other creator roles. This packet does not run `ALTER DEFAULT PRIVILEGES FOR ROLE postgres`.

Typed residual: BLOCK_DEFAULT_ACL_CREATOR.

Named `REVOKE EXECUTE` on the three O1/O2/O3 functions is the only function ACL this draft treats as inspectable source.

## GUC vs PIAC (T03)

`kdb.tenant_scope` is a transaction-local GUC set inside SECURITY DEFINER functions. It is not authenticated identity. A compromised runtime LOGIN can spoof it. RLS policies using that GUC are defense in depth only.

The private facade remains fail-closed. Synthetic ALLOW refs are rejected. No JWKS, issuer, token, or 1Password identifier is embedded.

## Twelve tables

Mutable with command-owner SELECT/INSERT policies:

- kdb_governance.source
- kdb_governance.source_version
- kdb_staging.submission
- kdb_staging.candidate_revision
- kdb_staging.review_work_item
- kdb_ops.command_receipt
- kdb_ops.audit_event
- kdb_ops.outbox_event

Protected. No O1/O2/O3 DML admission:

- kdb_governance.human_review_decision
- kdb_canonical.protocol
- kdb_canonical.protocol_version
- kdb_canonical.lifecycle_event

002 re-asserts ENABLE and FORCE ROW LEVEL SECURITY on all twelve by name.

## Functions (S04)

Exactly three SECURITY DEFINER functions, `search_path=pg_catalog`, owner `kdb_command_owner`, EXECUTE to `kdb_ingest_runtime` only:

- kdb_ops.ingest_source
- kdb_ops.propose_candidate
- kdb_ops.request_review_handoff

Signatures are unchanged from the P05 repaired 003. `session_user` must be `kdb_ingest_runtime`. SET ROLE from postgres is not a positive later test (T07).

## Out of scope

Legacy `canonical`, `dev_staging`, `public`, B03 SQL, 001, dormant 004, 098, tracked bytecode, n8n, O4/O5, physical TLS/1Password.
