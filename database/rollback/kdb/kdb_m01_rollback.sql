-- KDB-M01-03 rollback. Not a forward migration. Do not place in supabase/migrations.
-- Source ZIP SHA-256: 2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518

-- KDB-M01 bounded rollback.
-- Preserves pre-existing canonical.protocol rows and the canonical/dev_staging schemas.

drop function if exists kdb_api.list_published_protocol_versions(uuid);
drop function if exists kdb_api.submit_ingestion_candidate(text, uuid, text, jsonb, text);

drop table if exists kdb_audit.audit_record;
drop table if exists kdb_audit.outbox_event;

drop table if exists dev_staging.ingestion_candidate;

drop table if exists canonical.protocol_version_taxonomy_relation;
drop table if exists canonical.protocol_version_claim;
drop table if exists canonical.protocol_version;
drop table if exists canonical.publication;
drop table if exists canonical.review_decision;
drop table if exists canonical.claim_evidence;
drop table if exists canonical.evidence;
drop table if exists canonical.claim_version;
drop table if exists canonical.claim;
drop table if exists canonical.source_version;
drop table if exists canonical.source;

drop policy if exists kdb_runtime_read_protocol on canonical.protocol;
drop policy if exists kdb_reviewer_read_protocol on canonical.protocol;
revoke all on canonical.protocol from kdb_runtime, kdb_ingest_writer, kdb_reviewer;
alter table if exists canonical.protocol no force row level security;

alter table if exists canonical.protocol
  drop constraint if exists protocol_owning_module_fk,
  drop constraint if exists protocol_lifecycle_status_ck,
  drop column if exists owning_module_node_id,
  drop column if exists stable_key,
  drop column if exists lifecycle_status,
  drop column if exists created_at,
  drop column if exists created_by_ref;

drop table if exists canonical.taxonomy_node_version;
drop table if exists canonical.taxonomy_node;

drop function if exists kdb_audit.reject_immutable_mutation();

revoke all on schema canonical, dev_staging, kdb_api, kdb_audit
  from kdb_runtime, kdb_ingest_writer, kdb_reviewer;

drop schema if exists kdb_api;
drop schema if exists kdb_audit;

drop role if exists kdb_runtime;
drop role if exists kdb_ingest_writer;
drop role if exists kdb_reviewer;
