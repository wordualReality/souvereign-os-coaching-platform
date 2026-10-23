-- KDB-M01-03 / indexes and idempotency
-- Source ZIP SHA-256: 2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518
-- Source kdb_m01_foundation.sql SHA-256: e77e313bb070afd821f660b6c7bdda327be4ed41a3910ec1a4537e20f87f9bae
-- Materialization only. Do not apply from this packet.

begin;

create index if not exists taxonomy_node_parent_idx
  on canonical.taxonomy_node(parent_taxonomy_node_id);
create index if not exists taxonomy_node_type_status_idx
  on canonical.taxonomy_node(node_type, lifecycle_status);
create index if not exists taxonomy_node_version_node_idx
  on canonical.taxonomy_node_version(taxonomy_node_id, revision desc);
create index if not exists source_version_source_idx
  on canonical.source_version(source_id, revision desc);
create index if not exists source_version_rights_idx
  on canonical.source_version(rights_status);
create index if not exists claim_version_claim_idx
  on canonical.claim_version(claim_id, revision desc);
create index if not exists evidence_source_version_idx
  on canonical.evidence(source_version_id);
create index if not exists claim_evidence_evidence_idx
  on canonical.claim_evidence(evidence_id);
create unique index if not exists protocol_stable_key_uq
  on canonical.protocol(stable_key);
create index if not exists protocol_owning_module_idx
  on canonical.protocol(owning_module_node_id);
create index if not exists protocol_version_protocol_idx
  on canonical.protocol_version(protocol_id, revision desc);
create index if not exists protocol_version_publication_idx
  on canonical.protocol_version(publication_status, protocol_id);
create index if not exists protocol_version_claim_claim_idx
  on canonical.protocol_version_claim(claim_version_id);
create index if not exists protocol_version_taxonomy_node_idx
  on canonical.protocol_version_taxonomy_relation(taxonomy_node_version_id);
create index if not exists review_decision_resource_idx
  on canonical.review_decision(resource_type, resource_id, decided_at desc);
create index if not exists publication_resource_idx
  on canonical.publication(resource_type, resource_id, published_at desc);
create index if not exists publication_supersedes_idx
  on canonical.publication(supersedes_publication_id)
  where supersedes_publication_id is not null;
create unique index if not exists publication_one_active_per_resource_uq
  on canonical.publication(resource_type, resource_id)
  where publication_status = 'PUBLISHED';
create index if not exists ingestion_candidate_status_idx
  on dev_staging.ingestion_candidate(validation_status, review_status, created_at);
create index if not exists ingestion_candidate_source_idx
  on dev_staging.ingestion_candidate(source_version_id);
create index if not exists outbox_event_unpublished_idx
  on kdb_audit.outbox_event(occurred_at)
  where published_at is null;
create index if not exists audit_record_resource_idx
  on kdb_audit.audit_record(resource_type, resource_id, occurred_at desc);
create index if not exists audit_record_correlation_idx
  on kdb_audit.audit_record(correlation_id)
  where correlation_id is not null;

commit;
