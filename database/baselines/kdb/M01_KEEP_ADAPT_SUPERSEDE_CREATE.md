# M01 historical baseline to accepted ADR mapping

Status: `HISTORICAL_EVIDENCE_ADOPTED / OBJECT_MAPPING_PARTIAL / NO_LEGACY_MUTATION / NOT_SECURITY_PASS`

This compares the dated 2026-10-22 integration observation with the accepted
four-schema, 12-table ADR. It is not a live catalogue, one-to-one migration
plan, deployment authorization, or claim that legacy implements the new model.

## Observed integration relations

| Historical object | Disposition | Accepted candidate relation | Evidence boundary |
|---|---|---|---|
| `canonical.protocol` | `KEEP_LEGACY_NO_MUTATION` | `kdb_canonical.protocol`, `kdb_canonical.protocol_version` are `CREATE_CANDIDATE_ONLY` | Similar names do not prove semantic or identity equivalence; adaptation needs separate owner grant, rights evidence and human review. |
| `canonical.protocol_dependencies` | `KEEP_LEGACY_NO_MUTATION` | `UNRESOLVED_MAPPING` | No corresponding accepted MVP table; do not invent or silently drop the concept. |
| `canonical.topic` | `KEEP_LEGACY_NO_MUTATION` | `UNRESOLVED_MAPPING` | Taxonomy mapping belongs to the unconfirmed wider knowledge model. |
| `dev_staging.protocol_candidate` | `KEEP_LEGACY_NO_MUTATION` | `kdb_staging.submission`, `candidate_revision`, `review_work_item` are `CREATE_CANDIDATE_ONLY` | No direct upsert, alias or backfill; future adaptation requires provenance, rights and new KDB identities. |

## Observed public legacy RPCs

All six are `KEEP_LEGACY_NO_MUTATION` and
`ADAPT_ONLY_AFTER_SEPARATE_OWNER_GRANT`. None is reused by O1–O3, and observed
`service_role EXECUTE` is not an accepted runtime boundary.

| Legacy RPC | Current disposition | Candidate boundary |
|---|---|---|
| `get_project_state` | `KEEP_LEGACY_NO_MUTATION` | no proven one-to-one O1–O3 mapping |
| `get_pending_protocols` | `KEEP_LEGACY_NO_MUTATION` | no proven one-to-one O1–O3 mapping |
| `update_protocol_review` | `KEEP_LEGACY_NO_MUTATION` | must not write `human_review_decision` |
| `get_generation_context` | `KEEP_LEGACY_NO_MUTATION` | no proven one-to-one O1–O3 mapping |
| `get_protocols_by_module` | `KEEP_LEGACY_NO_MUTATION` | no proven one-to-one O1–O3 mapping |
| `insert_protocol_candidate` | `KEEP_LEGACY_NO_MUTATION` | must not substitute for guarded O1/O2 |

## Accepted candidate-only physical foundation

These are `CREATE_CANDIDATE_ONLY_NEW_KDB_12_TABLES` and remain gated:

- `kdb_governance.source`, `kdb_governance.source_version`, `kdb_governance.human_review_decision`
- `kdb_staging.submission`, `kdb_staging.candidate_revision`, `kdb_staging.review_work_item`
- `kdb_canonical.protocol`, `kdb_canonical.protocol_version`, `kdb_canonical.lifecycle_event`
- `kdb_ops.command_receipt`, `kdb_ops.outbox_event`, `kdb_ops.audit_event`

The earlier 17-table handover is
`SUPERSEDE_ARCHIVED_17_TABLE_LAYOUT_NO_DEPLOY`; preserve it as historical
evidence. The dedicated dev snapshot is separate: six migrations and one
estimated legacy row of unknown provenance must not be conflated with the
integration snapshot's 15 migrations.

## Unresolved gates

- exact semantic mapping, source origin, rights/licence and review authority
- creator-specific `pg_default_acl`, function ownership and independent Security QS
- hosted target admission, current catalogue state and positive O1–O3 authority
- full 86-requirement Knowledge/Protocol model
- historical ATC10 18 logical objects: `UNCONFIRMED / NOT_18_OF_18`

No C04/C05, outbox, n8n, hosted apply, PR rewrite or merge is authorized.
