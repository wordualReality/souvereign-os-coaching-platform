# Canonical command digest v2

Client-supplied `request_sha256` is an input. The database recomputes the digest from a versioned JSON array and rejects a mismatch before it returns any prior receipt.

v1 newline `concat_ws` is retired. Calling `kdb_ops.canonical_command_digest(...)` raises `CANONICAL_DIGEST_CONTRACT_UNRESOLVED`.

The contract is PostgreSQL `jsonb_build_array(...)::text` UTF-8 SHA-256 via `kdb_ops.canonical_digest_v2`. Compact `JSON.stringify` is not this contract. The KDB-owned adapter is `services/kdb/digest_v2.py`. It is proven only against SQL golden vectors in `tests/kdb/fixtures/p5_sql_v2_golden.json`. A producer that cannot reproduce those bytes fails closed with `KDB_HASH_MISMATCH` or `CANONICAL_DIGEST_CONTRACT_UNRESOLVED`.

NULL, empty string, embedded newlines, Unicode, numeric vs text, and field count are distinct array positions. JSON object key order is canonicalized by PostgreSQL jsonb, not by caller key order.

## SOURCE_INTAKE

```
jsonb_build_array(
  'v2',
  'SOURCE_INTAKE',
  command_id,
  tenant_scope,
  origin_owner,
  purpose,
  source_class,
  external_locator,
  content_sha256,
  rights_digest,
  principal_context_ref,
  access_decision_ref,
  idempotency_key,
  submission_id
)
```

`rights_digest` is `kdb_ops.jsonb_sha256(rights_snapshot)`.

Tenant and purpose remain command inputs. They are not PIAC proof. O1 stays `BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED`.

## CANDIDATE_PROPOSAL

```
jsonb_build_array(
  'v2',
  'CANDIDATE_PROPOSAL',
  command_id,
  tenant_scope,
  submission_id,
  source_version_id,
  candidate_id,
  revision_no,
  content_sha256,
  payload_digest,
  evidence_spans_digest,
  actor_ref,
  access_decision_ref
)
```

`payload_digest` is `kdb_ops.jsonb_sha256(COALESCE(payload, '{}'::jsonb))`.
`evidence_spans_digest` is `kdb_ops.jsonb_sha256(COALESCE(evidence_spans, '[]'::jsonb))`.

Changed evidence spans under the same `command_id` and claimed hash must raise `KDB_HASH_MISMATCH` or `KDB_IDEMPOTENCY_CONFLICT`.

## REVIEW_HANDOFF

```
jsonb_build_array(
  'v2',
  'REVIEW_HANDOFF',
  command_id,
  tenant_scope,
  candidate_revision_id,
  actor_ref,
  access_decision_ref
)
```

## Trust helper

`kdb_ops.security_context_ready()` is consulted by O1, O2 and O3. It returns false. A true result would still raise `KDB_SECURITY_CONTEXT_NOT_CONFIGURED` until an independently attested trust proof exists.

## Signed local ingress

A valid synthetic MAC is `LOCAL_SIGNED_INGRESS_VERIFIED` only. It is never `DB_COMMAND_ADMITTED`. Runtime O1-O3 EXECUTE stays revoked. `access_decision_ref` is not authorization.

## Arcava producer delta

Contract version: SQL v2. Field order is the arrays above. Bytes are PostgreSQL `jsonb::text`, not JS `JSON.stringify`. Reference encoder: `services/kdb/digest_v2.py`. Golden vectors: `tests/kdb/fixtures/p5_sql_v2_golden.json`. Failure: `KDB_HASH_MISMATCH` or `CANONICAL_DIGEST_CONTRACT_UNRESOLVED`. Ingest stays fail-closed until DB trust is attested. This notice does not change Arcava source in this packet.
