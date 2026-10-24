# PIAC proof security contract

Status: CONTRACT ONLY. No working verifier, issuer, key, JWKS, or deployment.

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
