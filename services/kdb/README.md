# KDB command facade (not deployed)

This skeleton exists so O1/O2/O3 envelopes have a private owner besides n8n.
It has no database credentials and no deploy path in this packet.

Until an independently admitted PIAC issuer and verifier exist, every request is rejected.
Envelope `tenant_scope` is checked first and must be a nonempty trimmed string of at most 128 characters. A GUC named `kdb.tenant_scope` is not that field. `access_decision_ref` and `principal_context_ref` are not authorization.

`provenance_eligibility.py` is an offline review-handoff eligibility guard for the SourceVersion to ReviewWorkItem chain. A local ELIGIBLE result is not a database write, not C04, and not C05.

`digest_v2.py` is the KDB-owned SQL-v2 adapter. It does not grant producers database EXECUTE.
`signed_ingress.py` is a test-only synthetic HMAC verifier. A local pass is `LOCAL_SIGNED_INGRESS_VERIFIED`, never `DB_COMMAND_ADMITTED`.
