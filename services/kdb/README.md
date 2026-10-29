# KDB command facade (not deployed)

This skeleton exists so O1/O2/O3 envelopes have a private owner besides n8n.
It has no database credentials and no deploy path in this packet.

Until an independently admitted PIAC issuer and verifier exist, every request is rejected.
Envelope `tenant_scope` is checked first and must be a nonempty trimmed string of at most 128 characters. A GUC named `kdb.tenant_scope` is not that field. `access_decision_ref` and `principal_context_ref` are not authorization.

`provenance_eligibility.py` is an offline review-handoff eligibility guard for the SourceVersion to ReviewWorkItem chain. A local ELIGIBLE result is not a database write, not C04, and not C05.

`lifecycle_eligibility.py` is an offline read-eligibility guard for ProtocolVersion lifecycle events. Withdrawal and revoked rights win. A local READ_ELIGIBLE result is NON_EXECUTABLE and does not publish.

`offline_diagnostic.py` plus `offline_diagnostic_cli.py` run those checks as one local diagnostic. Exit 0 prints a redacted receipt whose final_authority is always NOT_ADMITTED. Exit 2 means the input was rejected. Example:

```
python3 services/kdb/offline_diagnostic_cli.py tests/kdb/fixtures/p10_stage_coherent.json
```

`tests/kdb/pg17_p11_source_review_readback.py` is a disposable PostgreSQL 17 fixture. It is not a production reader. TEST_FIXTURE_ADMIN DML is rolled back. Mapped rows still finish NOT_ADMITTED. DF-20261029-01 adds a per-object evidence matrix for the twelve SQL001 tables. A frozen 18-object logical inventory is not claimed.

`digest_v2.py` is the KDB-owned SQL-v2 adapter. It does not grant producers database EXECUTE.
`signed_ingress.py` is a test-only synthetic HMAC verifier. A local pass is `LOCAL_SIGNED_INGRESS_VERIFIED`, never `DB_COMMAND_ADMITTED`.
