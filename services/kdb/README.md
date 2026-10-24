# KDB command facade (not deployed)

This skeleton exists so O1/O2/O3 envelopes have a private owner besides n8n.
It has no database credentials and no deploy path in this packet.

Until an independently admitted PIAC issuer and verifier exist, every request is rejected.
`access_decision_ref` and `principal_context_ref` are not authorization.

`digest_v2.py` is the KDB-owned SQL-v2 adapter. It does not grant producers database EXECUTE.
`signed_ingress.py` is a test-only synthetic HMAC verifier. A local pass is `LOCAL_SIGNED_INGRESS_VERIFIED`, never `DB_COMMAND_ADMITTED`.
