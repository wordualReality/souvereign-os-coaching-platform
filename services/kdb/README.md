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

`tests/kdb/pg17_p12_commit_reconnect_replay.py` COMMITs that fixture on a unique disposable PostgreSQL 17 target, reads it back on a new connection, proves exact and conflicting replays, then revokes source rights. That is still TEST_FIXTURE_ADMIN, not admitted runtime ingest. FINAL remains NOT_ADMITTED.

`review_handoff_preview.py` plus `review_handoff_preview_cli.py` turn an eligible synthetic candidate chain into a redacted `PREVIEW_ONLY` `KDB_HUMAN_REVIEW` queue card. That is not a reviewer assignment, C04 decision, or publication. Revoked rights and stale versions produce no card. Duplicate JSON keys, oversized or deep input, and untrusted commit labels are rejected. The queue card omits `media_type`. FINAL remains NOT_ADMITTED.

`offline_review_inbox.py` plus `offline_review_inbox_cli.py` aggregate those previews into a sorted, filterable inbox. The read model is a non-normative internal preview. It stays `SNAPSHOT_UNTRUSTED` and `NOT_ASSIGNED`. Cross-tenant input and duplicate work items yield no cards. Rights revocation wins for the same SourceID. FINAL remains NOT_ADMITTED.

`offline_review_case_detail.py` plus `offline_review_case_detail_cli.py` open one selected work item after that full inbox re-evaluation. The receipt is `DETAIL_ONLY` and still `NOT_ASSIGNED`. Denied items are not selectable. FINAL remains NOT_ADMITTED.

`digest_v2.py` is the KDB-owned SQL-v2 adapter. It does not grant producers database EXECUTE.
`signed_ingress.py` is a test-only synthetic HMAC verifier. A local pass is `LOCAL_SIGNED_INGRESS_VERIFIED`, never `DB_COMMAND_ADMITTED`.
