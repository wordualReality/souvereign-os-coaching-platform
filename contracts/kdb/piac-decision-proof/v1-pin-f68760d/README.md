# PIAC decision proof v1

Status: SOV producer contract. Synthetic verification only.

This package is the versioned producer surface for `PIAC_DECISION_PROOF_V1`. It does not admit a live issuer, a production trust anchor, or a KDB verifier. KDB `PIAC_PROOF_SECURITY_CONTRACT` stays CONTRACT ONLY. Publishing this package does not adopt it for KDB or Arcava and does not change those lanes.

The signer and verifier live in `io.sovereignos.sharedcore.identity.proof`. A proof is minted only after an operation-specific ALLOW for `KDB_SOURCE_INTAKE`. A CT-SHC read ALLOW is not that authorization. Live key custody returns `AUTHORITY_NOT_CONFIGURED`. Tests use an ephemeral Ed25519 pair that is generated at runtime and is not a trust anchor.

## Envelope

`proof_version` is `PIAC_DECISION_PROOF_V1`. `alg` is `Ed25519`. The signature covers the canonical payload bytes, not a caller-supplied digest. Canonical payload JSON uses sorted keys, UTF-8, and the separators comma and colon with no spaces.

The identity issuer and the proof issuer are different claims (`identity_issuer` and `iss`). A proof that equates them is rejected.

## Command digest

`request_sha256` is SHA-256 of UTF-8 PostgreSQL `jsonb_build_array(...)::text` for SQL v2. The pinned vectors are `kdb-sql-v2-golden.json`. The sibling `kdb-sql-v2-golden.sha256` is the hash of that file and is not part of the hashed bytes. Compact `JSON.stringify` is not this contract.

The verifier recomputes the digest from the presented command fields. A detached hash does not replace those bytes. For `SOURCE_INTAKE` the array order is version, command name, command id, tenant scope, origin owner, purpose, source class, external locator, content sha256, rights digest, principal context ref, access decision ref, idempotency key, submission id.

## Public metadata

Trust metadata is kid, algorithm, proof version, issuer, SPKI public key, and rotation. The shape is `public-metadata.schema.json`. No signing key is in this package.
