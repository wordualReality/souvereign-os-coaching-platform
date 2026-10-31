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

`offline_review_workbench.py` plus `offline_review_workbench_cli.py` render those inbox rows and case details as standalone UTF-8 HTML. The page is a synthetic preview. It has no server, scripts, or review assignment. FINAL remains NOT_ADMITTED.

`offline_review_snapshot_delta.py` plus `offline_review_snapshot_delta_cli.py` compare two synthetic P14 batches and render current eligible cases plus aggregate counts. Removed or revoked baseline items are count only. Snapshot order is an input, not an attested event sequence. FINAL remains NOT_ADMITTED.

`offline_review_demo_pack.py` plus `offline_review_demo_pack_cli.py` package current workbench HTML, the snapshot-delta view, and the P19 JSON viewmodel into a local file bundle. Default CLI prints a redacted manifest. `--out-dir` writes a new directory under `tests/kdb/demo-artifacts`. Checksums are local file integrity only. FINAL remains NOT_ADMITTED.

`offline_review_viewmodel.py` plus `offline_review_viewmodel_cli.py` emit a versioned JSON preview of current eligible cases plus aggregate counts. The schema is internal and non-normative. Default CLI prints JSON and writes nothing. FINAL remains NOT_ADMITTED.

`offline_source_bytes_proof.py` plus `offline_source_bytes_proof_cli.py` compare exact local synthetic file bytes to a declared SourceVersion SHA-256 after P14/P15 selection. A local match is not source custody, license proof, or admitted ingest. FINAL remains NOT_ADMITTED.

`digest_v2.py` is the KDB-owned SQL-v2 adapter. It does not grant producers database EXECUTE.
`signed_ingress.py` is a test-only synthetic HMAC verifier. A local pass is `LOCAL_SIGNED_INGRESS_VERIFIED`, never `DB_COMMAND_ADMITTED`.
# P21 offline evidence-bound review

`offline_evidence_bound_review.py` composes the full P14 inbox guard, current
P15 selection, P20 exact local-byte proof, and canonical `bytes:first-last`
EvidenceSpan reconciliation. The CLI emits a deterministic, redacted
`LOCAL_BYTES_AND_SPANS_BOUNDED` internal preview or a fail-closed denial:

```sh
python3 services/kdb/offline_evidence_bound_review_cli.py \
  tests/kdb/fixtures/p20_inbox_byte_spans.json \
  --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 \
  --source-file tests/kdb/fixtures/p20_source_a.bin
```

Slice hashes prove only the bounded bytes in the repo-local synthetic file.
They do not attest source custody, rights, semantic correctness, reviewer
assignment, publication, or hosted admission.

# P22 optional portable current-case evidence demo

The P18 six-file output remains the default. Supplying both
`--work-item-id` and `--source-file` explicitly enables the P22 variant. It
recomputes P21, links a redacted `current-case-evidence.json` from the local
index and current-case pages, and records deterministic hashes in the
manifest. It remains `PREVIEW_ONLY`, `SNAPSHOT_UNTRUSTED`, `NOT_ADMITTED`, and
`NON_EXECUTABLE`.

```sh
python3 services/kdb/offline_review_demo_pack_cli.py \
  tests/kdb/fixtures/p20_inbox_byte_spans.json current-copy.json \
  --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 \
  --source-file tests/kdb/fixtures/p20_source_a.bin
```
