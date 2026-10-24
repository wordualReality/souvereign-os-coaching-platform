# Canonical command digest v1

Client-supplied `request_sha256` is an input. The database recomputes the digest and rejects a mismatch before it returns any prior receipt.

Python `json.dumps` is not the SQL contract. Rights and payload bytes are digested with PostgreSQL `jsonb::text` via `kdb_ops.jsonb_sha256`. If a caller cannot produce that digest, the command fails closed with `KDB_HASH_MISMATCH`.

## SOURCE_INTAKE

UTF-8 SHA-256 of newline-joined fields:

```
v1
SOURCE_INTAKE
{command_id}
{tenant_scope}
{origin_owner}
{purpose}
{source_class}
{external_locator}
{content_sha256}
{rights_digest}
{principal_context_ref}
{access_decision_ref}
{idempotency_key}
{submission_id}
```

`rights_digest` is `kdb_ops.jsonb_sha256(rights_snapshot)`.

## CANDIDATE_PROPOSAL

```
v1
CANDIDATE_PROPOSAL
{command_id}
{tenant_scope}
{submission_id}
{source_version_id}
{candidate_id}
{revision_no}
{content_sha256}
{payload_digest}
{actor_ref}
{access_decision_ref}
```

## REVIEW_HANDOFF

```
v1
REVIEW_HANDOFF
{command_id}
{tenant_scope}
{candidate_revision_id}
{actor_ref}
{access_decision_ref}
```

Changed semantic bytes under the same `command_id` must raise `KDB_IDEMPOTENCY_CONFLICT` or `KDB_HASH_MISMATCH` before any previous receipt is returned.

O1-O3 remain `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED` while `kdb_ops.security_context_ready()` is false.
