# PIAC proof security contract

Status: CONTRACT ONLY for live admission. No live issuer, JWKS, or deployment.

A versioned `PIAC_DECISION_PROOF_V1` consumer exists at
`services/kdb/sov_proof_consumer.py` and is `DISABLED_CONTRACT_ONLY` by default.
The producer pin is `f68760d799831ff260f99eb5b02358a1a3bda979`. Pinning is not
normative adoption. `NEEDS_SOV_SECURITY_QS` remains named. A synthetic local
pass is `LOCAL_VERIFIED_ONLY` and never `DB_COMMAND_ADMITTED`.

The KDB command facade must reject every envelope until an independently admitted verifier exists. `access_decision_ref`, `principal_context_ref`, and `kdb.tenant_scope` are not proofs.

Required claims, when a verifier is later admitted:

- cryptographic signature over a canonical body hash
- issuer and audience binding
- principal and tenant
- purpose
- expiry and nbf
- nonce/jti replay protection
- rights binding to an immutable SourceVersion

Negative cases (T06) must reject before any SQL call. No receipt, no outbox mutation.

This packet embeds no secret, no 1Password item id, and no test-allow bypass.
