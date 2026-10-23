# Physical KDB command gateway — contract-first / fail closed


n8n has **no SQL credentials and no direct table privileges**. It transports versioned O1/O2/O3 envelopes to a private **KDB-owned command facade** over authenticated TLS. The facade is a physical component to implement at the Gate A execution stage; it is **not present** in this offline package. It alone owns the narrow database connection principal. Facade MUST verify the signed PIAC decision (issuer trust, cryptographic signature, intended tenant/purpose, principal, expiration and replay) before creating the SQL command. References such as `access_decision_ref` and `principal_context_ref` are correlations, **not authorization proofs by themselves**.


The three SQL functions in `003_kdb_command_boundary.sql` check schema, rights/scope and database login role and are only one layer of defense. Without implemented and tested facade PIAC validation, NO external invocation may be admitted. Never expose them through `public`/Supabase REST. A private KDB service route remains subject to endpoint/TLS/1Password verification and independently approved deploy.


External transport envelope contracts: `contracts/o1_source_ingest.schema.json`, `o2_candidate_proposal.schema.json`, `o3_review_handoff.schema.json`; owner receipts `owner_receipt.schema.json` (additional frontend mapper needed; SQL returns narrower JSON and must be mapped into final receipt contract by facade; this mapper is **NOT IMPLEMENTED**). Versioned MAP04-C01/C02/C03 are local mapping identities, not new contract families. O3 **does not** generate HumanReviewDecision, ProtocolVersion or canonical admission; n8n is never promoted to an approver.


Do not enable O1–O3 workflows merely because schema is applied. Physical service unit tests, PIAC proof and credential-safe integration are further execution acceptance requirements after Gate A.
