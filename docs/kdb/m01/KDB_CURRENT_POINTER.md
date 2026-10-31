# KDB current pointer, 2026-10-31 P22 portable current-case evidence demo

Active grant: THREE_LANE_BUILD_TO_BETA_2026-10-23.md
https://drive.google.com/file/d/1lrV8_CD94ETnrKF-PrCiugWev9kps03g/view
Active packet: KDB-M01-P22-PORTABLE-CURRENT-CASE-EVIDENCE-DEMO-01
DF adoption: DF-20261029-01 evidence matrix. Twelve physical SQL001 tables. ATC-10 named 18 remain UNCONFIRMED. No 18/18 logical claim.

P1 PR #6 `bed66883`, P2 PR #9 `3692a275`, P3 PR #13 `51b67fba`, P4 PR #15 `348f638`, P5 PR #17 `a5f6727`, repair PR #20 `a2b55c2`, PR #21 `2ba7ae44` remain frozen.
PR #22 stays untouched at `0078c03`. This pointer is local branch `kdb/m01-p06-local-worktree-recovery` from accepted PR21.

## Physical stand

- Worktree: isolated `souvereign-os-coaching-platform-kdb-p06`
- Do not merge to main.
- Leave B03 SQL and Arcava paths to their owners.
- Do not apply 004, 098, or the P2 recovery candidate.
- Do not rewrite PR #15, #17, #20, #21, or #22.
- Do not import or activate n8n workflows.

## P07 tenant guard

Version-controlled inactive `n8n/kdb-dev/tenant-guard-candidate` already holds the corrected Fail Closed Classify nodes. P07 adds the same fail-closed `tenant_scope` rule to `services/kdb/tenant_scope.py`, checks it before PIAC, and records 37/37 plus 26/26 plus extra oversize/non-string regressions. Synthetic ALLOW is still rejected. Not a hosted or live ingest admission.

## P08 provenance and review eligibility

`services/kdb/provenance_eligibility.py` checks SourceVersion to Submission to CandidateRevision to ReviewWorkItem against SQL 001 and O1/O2/O3. A pass is eligibility for a review handoff only. It does not write SQL, create a human decision, or publish a ProtocolVersion. Semantic descriptor, taxonomy, and rule version pins are absent from those contracts and are reported as gaps. Synthetic ALLOW is still rejected by the facade.

## P09 lifecycle and withdrawal eligibility

`services/kdb/lifecycle_eligibility.py` checks reserved SQL 001 protocol, protocol_version, and lifecycle_event kinds PUBLISHED, REVALIDATION_REQUIRED, WITHDRAWN, SUPERSEDED. Withdrawal and revoked source rights win. Unclear event order stays NOT_ADMITTED. A local pass is READ_ELIGIBLE_OFFLINE_ONLY and NON_EXECUTABLE. It does not write C04/C05, emit outbox, or recompute opaque content_sha256.

## P10 local diagnostic vertical slice

`services/kdb/offline_diagnostic.py` and `offline_diagnostic_cli.py` compose P07 tenant_scope, P08 provenance, and P09 lifecycle into one local JSON diagnosis. A coherent synthetic run may show STAGE_LOCAL_ELIGIBLE per stage. The receipt stays NOT_ADMITTED and NON_EXECUTABLE because there is no verified C04/C05 transition. No network, SQL, or n8n.

```
python3 services/kdb/offline_diagnostic_cli.py tests/kdb/fixtures/p10_stage_coherent.json
```

## P11 disposable PG17 source-to-review readback

`tests/kdb/pg17_p11_source_review_readback.py` inserts a synthetic Source to ReviewWorkItem chain as `kdb_test_fixture_admin` on disposable PostgreSQL 17, SELECTs it, maps it into P10, and rolls the transaction back. Lifecycle stays a separate synthetic fixture. C04/C05 are not inserted. Runtime LOGIN stays denied. FINAL remains NOT_ADMITTED.

```
python3 tests/kdb/pg17_p11_source_review_readback.py
```

## P12 disposable PG17 commit reconnect replay revocation

`tests/kdb/pg17_p12_commit_reconnect_replay.py` COMMITs the synthetic Source to ReviewWorkItem chain as `kdb_test_fixture_admin` on a uniquely identified disposable PostgreSQL 17 database or container, closes that backend, and SELECTs the same IDs on a new connection. Exact and conflicting submission replays are unique-key proofs only. A later committed REVOKED rights_status is denied by P08. A docker restart of the unique container is a server restart. A new psql backend is not. C04/C05 stay empty. FINAL remains NOT_ADMITTED. The unique target is dropped at the end.

```
python3 tests/kdb/pg17_p12_commit_reconnect_replay.py
```

## P13 offline review-handoff preview

`services/kdb/review_handoff_preview.py` plus `review_handoff_preview_cli.py` assemble a redacted `KDB_HUMAN_REVIEW` queue card from O1/O2/O3 identities after P07 and P08. A local `PREVIEW_ONLY` result is still `NOT_ADMITTED` and `NON_EXECUTABLE`. Revoked or pending rights, stale versions, cross-tenant links, empty evidence, and forged reviewer claims produce no card. No review assignment, C04, C05, or publication.

```
python3 services/kdb/review_handoff_preview_cli.py tests/kdb/fixtures/p13_preview_eligible.json
python3 tests/kdb/pg17_p13_review_handoff_preview.py
```

P13R keeps that preview path and rejects duplicate JSON keys, oversized or deep input, huge integers, path escape, symlinks, and untrusted commit labels. The queue card omits `media_type`. A local commit label is `LABEL_NOT_ATTESTED`.

## P14 offline review-inbox read model

`offline_review_inbox.py` plus `offline_review_inbox_cli.py` aggregate P13R per-candidate previews into a sorted, filterable, redacted inbox. The receipt is a non-normative internal preview. It stays `SNAPSHOT_UNTRUSTED`, `NOT_ASSIGNED`, and `NOT_ADMITTED`. Cross-tenant input yields no cards. Rights revocation wins for every item that shares a SourceID. Physical PostgreSQL 17 coverage is two linked Source-to-Review chains, not a many-to-many claim.

```
python3 services/kdb/offline_review_inbox_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json
python3 tests/kdb/pg17_p14_review_inbox.py
```

## P15 offline review case detail

`offline_review_case_detail.py` plus `offline_review_case_detail_cli.py` open one selected `review_work_item_id` after the full P14 batch is re-evaluated. The receipt is `DETAIL_ONLY`, `SNAPSHOT_UNTRUSTED`, and `NOT_ASSIGNED`. A denied, stale, or revoked item cannot be selected by paging or filtering. Physical PostgreSQL 17 coverage reuses the two linked Source-to-Review chains.

```
python3 services/kdb/offline_review_case_detail_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777
python3 tests/kdb/pg17_p15_review_case_detail.py
```

## P16 static offline review workbench

`offline_review_workbench.py` plus `offline_review_workbench_cli.py` render a portable UTF-8 HTML5 page from a P14 batch after full inbox re-evaluation and P15 detail for each eligible work item. The page is `SNAPSHOT_UNTRUSTED`, `NOT_ASSIGNED`, and `NOT_ADMITTED`. It has no scripts, forms, remote assets, or server. Physical PostgreSQL 17 coverage reuses the two linked Source-to-Review chains.

```
python3 services/kdb/offline_review_workbench_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json
python3 tests/kdb/pg17_p16_review_workbench.py
```

## P17 offline snapshot-delta workbench

`offline_review_snapshot_delta.py` plus `offline_review_snapshot_delta_cli.py` compare two user-supplied synthetic P14 batches after full inbox re-evaluation. Current eligible cases may appear with P15 detail. Removed or no-longer-eligible baseline items are COUNT ONLY. Snapshot order is not attested. The page is `SNAPSHOT_UNTRUSTED`, `NOT_ASSIGNED`, and `NOT_ADMITTED`. Physical PostgreSQL 17 coverage reuses the two linked Source-to-Review chains.

```
python3 services/kdb/offline_review_snapshot_delta_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json path/to/current-p14-batch.json
python3 tests/kdb/pg17_p17_review_snapshot_delta.py
```

## P18 portable offline review demo pack

`offline_review_demo_pack.py` plus `offline_review_demo_pack_cli.py` turn the current P16 workbench and P17 snapshot-delta into a local file bundle. `index.html` is the landing page. `current.html` is the current snapshot. `changes.html` keeps removed items as counts only. `review-viewmodel.json` is the P19 machine-readable preview. `manifest.json` hashes those files as `LOCAL_FILE_INTEGRITY_ONLY`. Snapshot order is not attested. Generated bundles stay out of git under `tests/kdb/demo-artifacts`.

```
python3 services/kdb/offline_review_demo_pack_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json path/to/current-p14-batch.json
python3 tests/kdb/pg17_p18_review_demo_pack.py
```

## P19 versioned offline review viewmodel

`offline_review_viewmodel.py` plus `offline_review_viewmodel_cli.py` emit a versioned JSON preview from P14 inbox cards, P15 case detail, and P17 count-only delta. Schema `1.0` is internal and non-normative. Whole-batch deny yields `DEMO_DENIED` with empty cases and zero counts. Removed identities stay out of the document. This is not an admitted consumer contract.

```
python3 services/kdb/offline_review_viewmodel_cli.py tests/kdb/fixtures/p14_inbox_two_eligible.json path/to/current-p14-batch.json
python3 tests/kdb/pg17_p19_review_viewmodel.py
```

## P20 offline source-bytes evidence proof

`offline_source_bytes_proof.py` plus `offline_source_bytes_proof_cli.py` hash one bounded repo-local synthetic file and compare it to the declared `SourceVersion.content_sha256` of a P15-selectable work item. A match is `LOCAL_BYTES_MATCH_DECLARED_SHA` only. It is not rights, origin, or live ingest. Text locators stay `UNVERIFIED_LOCAL_SPAN_SEMANTICS`.

```
python3 services/kdb/offline_source_bytes_proof_cli.py tests/kdb/fixtures/p20_inbox_match.json --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 --source-file tests/kdb/fixtures/p20_source_a.bin
python3 tests/kdb/pg17_p20_source_bytes_proof.py
```

## P21 offline evidence-bound review

`offline_evidence_bound_review.py` plus its CLI compose full P14 batch guards,
P15 current-case selection, P20 local source-byte binding, and canonical
EvidenceSpan reconciliation. Canonical `bytes:first-last` locators are mapped
to zero-based end-exclusive offsets and must agree with optional integer
offsets. Each valid slice receives a local SHA-256 proof without source bytes,
paths, or declared source hash. Unknown locator dialects, mismatches,
duplicates, overlaps, revocation, and tenant conflicts fail closed. The result
is `LOCAL_BYTES_AND_SPANS_BOUNDED`, `SNAPSHOT_UNTRUSTED`, `NOT_ASSIGNED`, and
`NOT_ADMITTED`.

```
python3 services/kdb/offline_evidence_bound_review_cli.py tests/kdb/fixtures/p20_inbox_byte_spans.json --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 --source-file tests/kdb/fixtures/p20_source_a.bin
python3 tests/kdb/pg17_p21_evidence_bound_review.py
```

## P22 portable current-case evidence demo

P22 is an explicit opt-in extension of the existing P18 local bundle. The
default remains the same six files. With both evidence CLI arguments present,
the builder recomputes P21 locally, links a redacted machine-readable receipt
from `index.html` and `current.html`, and hashes the additional artifact in the
manifest. No source bytes, local paths, external locators, rights secrets, or
denied identities enter the bundle. Hosted, security, assignment, admission,
C04/C05, outbox, and production gates remain closed.

