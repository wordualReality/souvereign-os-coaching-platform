-- KDB-M01-03 / core foundation
-- Source ZIP SHA-256: 2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518
-- Source kdb_m01_foundation.sql SHA-256: e77e313bb070afd821f660b6c7bdda327be4ed41a3910ec1a4537e20f87f9bae
-- Materialization only. Do not apply from this packet.

begin;

-- KDB-M01 foundation
-- Target: isolated KDB development environment first.
-- Promotion to KDB_INTEGRATION_MAIN requires a separate exact-hash admission.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists canonical;
create schema if not exists dev_staging;
create schema if not exists kdb_api;
create schema if not exists kdb_audit;

revoke all on schema canonical, dev_staging, kdb_api, kdb_audit from public;


create table if not exists canonical.taxonomy_node (
  taxonomy_node_id uuid primary key default gen_random_uuid(),
  stable_key text not null unique,
  node_type text not null check (node_type in ('AREA','DOMAIN','MODULE','TOPIC','TAG')),
  parent_taxonomy_node_id uuid references canonical.taxonomy_node(taxonomy_node_id),
  lifecycle_status text not null default 'ACTIVE'
    check (lifecycle_status in ('DRAFT','ACTIVE','DEPRECATED','WITHDRAWN')),
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  check (parent_taxonomy_node_id is null or parent_taxonomy_node_id <> taxonomy_node_id)
);




create table if not exists canonical.taxonomy_node_version (
  taxonomy_node_version_id uuid primary key default gen_random_uuid(),
  taxonomy_node_id uuid not null references canonical.taxonomy_node(taxonomy_node_id),
  revision integer not null check (revision > 0),
  label text not null,
  description text,
  semantic_payload jsonb not null default '{}'::jsonb,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  unique (taxonomy_node_id, revision),
  unique (taxonomy_node_version_id, taxonomy_node_id),
  check (valid_to is null or valid_to > valid_from)
);



create table if not exists canonical.source (
  source_id uuid primary key default gen_random_uuid(),
  stable_key text not null unique,
  source_type text not null
    check (source_type in ('BOOK','PAPER','GUIDELINE','WEBSITE','VIDEO','AUDIO','TRANSCRIPT','INTERNAL','OTHER')),
  canonical_uri text,
  title text not null,
  publisher_or_author text,
  lifecycle_status text not null default 'ACTIVE'
    check (lifecycle_status in ('ACTIVE','RESTRICTED','WITHDRAWN')),
  created_at timestamptz not null default now(),
  created_by_ref text not null
);

create table if not exists canonical.source_version (
  source_version_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references canonical.source(source_id),
  revision integer not null check (revision > 0),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  acquired_at timestamptz not null,
  published_at timestamptz,
  rights_status text not null
    check (rights_status in ('VERIFIED','RESTRICTED','UNKNOWN','PROHIBITED')),
  permitted_purposes text[] not null default '{}'::text[],
  provenance_payload jsonb not null default '{}'::jsonb,
  storage_locator text,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  unique (source_id, revision),
  unique (source_id, content_sha256)
);




create table if not exists canonical.claim (
  claim_id uuid primary key default gen_random_uuid(),
  stable_key text not null unique,
  claim_type text not null
    check (claim_type in ('EFFECT','MECHANISM','SAFETY','CONTRAINDICATION','APPLICABILITY','DOSHA','OTHER')),
  lifecycle_status text not null default 'ACTIVE'
    check (lifecycle_status in ('DRAFT','ACTIVE','DISPUTED','SUPERSEDED','WITHDRAWN')),
  created_at timestamptz not null default now(),
  created_by_ref text not null
);

create table if not exists canonical.claim_version (
  claim_version_id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references canonical.claim(claim_id),
  revision integer not null check (revision > 0),
  statement text not null,
  risk_classification text not null default 'NORMAL'
    check (risk_classification in ('NORMAL','CAUTION','HIGH_RISK','MEDICAL_REVIEW_REQUIRED')),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  unique (claim_id, revision),
  check (valid_to is null or valid_to > valid_from)
);



create table if not exists canonical.evidence (
  evidence_id uuid primary key default gen_random_uuid(),
  source_version_id uuid not null references canonical.source_version(source_version_id),
  evidence_kind text not null
    check (evidence_kind in ('DIRECT_QUOTE','DERIVED_FINDING','DATASET_RESULT','EXPERT_REVIEW','TRADITIONAL_SOURCE','OTHER')),
  locator text,
  excerpt text,
  evidence_quality text not null
    check (evidence_quality in ('A','B','C','D','UNRATED')),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  unique (source_version_id, content_sha256)
);



create table if not exists canonical.claim_evidence (
  claim_version_id uuid not null references canonical.claim_version(claim_version_id),
  evidence_id uuid not null references canonical.evidence(evidence_id),
  support_type text not null
    check (support_type in ('SUPPORTS','CONTRADICTS','QUALIFIES','BACKGROUND')),
  strength numeric(4,3) check (strength is null or (strength >= 0 and strength <= 1)),
  rationale text,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  primary key (claim_version_id, evidence_id, support_type)
);



-- Existing legacy protocol rows can coexist. New columns establish stable identity.
create table if not exists canonical.protocol (
  protocol_id uuid primary key default gen_random_uuid()
);
alter table canonical.protocol add column if not exists stable_key text;
alter table canonical.protocol add column if not exists owning_module_node_id uuid;
alter table canonical.protocol add column if not exists lifecycle_status text;
alter table canonical.protocol add column if not exists created_at timestamptz;
alter table canonical.protocol add column if not exists created_by_ref text;

update canonical.protocol
set stable_key = coalesce(stable_key, 'legacy:' || protocol_id::text),
    lifecycle_status = coalesce(lifecycle_status, 'ACTIVE'),
    created_at = coalesce(created_at, now()),
    created_by_ref = coalesce(created_by_ref, 'legacy-migration')
where stable_key is null
   or lifecycle_status is null
   or created_at is null
   or created_by_ref is null;

alter table canonical.protocol alter column stable_key set not null;
alter table canonical.protocol alter column lifecycle_status set not null;
alter table canonical.protocol alter column lifecycle_status set default 'ACTIVE';
alter table canonical.protocol alter column created_at set not null;
alter table canonical.protocol alter column created_at set default now();
alter table canonical.protocol alter column created_by_ref set not null;




do $constraints$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'protocol_owning_module_fk'
  ) then
    alter table canonical.protocol
      add constraint protocol_owning_module_fk
      foreign key (owning_module_node_id)
      references canonical.taxonomy_node(taxonomy_node_id);
  end if;
  if not exists (
    select 1 from pg_constraint where conname = 'protocol_lifecycle_status_ck'
  ) then
    alter table canonical.protocol
      add constraint protocol_lifecycle_status_ck
      check (lifecycle_status in ('DRAFT','ACTIVE','DEPRECATED','WITHDRAWN'));
  end if;
end
$constraints$;

create table if not exists canonical.protocol_version (
  protocol_version_id uuid primary key default gen_random_uuid(),
  protocol_id uuid not null references canonical.protocol(protocol_id),
  revision integer not null check (revision > 0),
  canonical_name text not null,
  display_summary text,
  protocol_category text not null,
  steps jsonb not null default '[]'::jsonb check (jsonb_typeof(steps) = 'array'),
  contraindications jsonb not null default '[]'::jsonb
    check (jsonb_typeof(contraindications) = 'array'),
  dosha_relevance jsonb not null default '{}'::jsonb
    check (jsonb_typeof(dosha_relevance) = 'object'),
  evidence_level text,
  review_status text not null default 'DRAFT'
    check (review_status in ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','CHANGES_REQUIRED')),
  publication_status text not null default 'UNPUBLISHED'
    check (publication_status in ('UNPUBLISHED','PUBLISHED','SUPERSEDED','WITHDRAWN')),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  unique (protocol_id, revision),
  unique (protocol_version_id, protocol_id),
  check (valid_to is null or valid_to > valid_from)
);




create table if not exists canonical.protocol_version_claim (
  protocol_version_id uuid not null references canonical.protocol_version(protocol_version_id),
  claim_version_id uuid not null references canonical.claim_version(claim_version_id),
  applicability text not null default 'GENERAL'
    check (applicability in ('GENERAL','STEP','SAFETY','CONTRAINDICATION','DOSHA')),
  created_at timestamptz not null default now(),
  primary key (protocol_version_id, claim_version_id, applicability)
);



create table if not exists canonical.protocol_version_taxonomy_relation (
  protocol_version_id uuid not null references canonical.protocol_version(protocol_version_id),
  taxonomy_node_version_id uuid not null references canonical.taxonomy_node_version(taxonomy_node_version_id),
  relation_type text not null
    check (relation_type in ('OWNS','APPLIES_TO','RELATED_TO','CONTRAINDICATED_FOR','SUPPORTS')),
  created_at timestamptz not null default now(),
  primary key (protocol_version_id, taxonomy_node_version_id, relation_type)
);



create table if not exists canonical.review_decision (
  review_decision_id uuid primary key default gen_random_uuid(),
  resource_type text not null
    check (resource_type in ('SOURCE_VERSION','CLAIM_VERSION','PROTOCOL_VERSION','TAXONOMY_NODE_VERSION','INGESTION_CANDIDATE')),
  resource_id uuid not null,
  decision text not null
    check (decision in ('APPROVE','REJECT','REQUEST_CHANGES','ABSTAIN')),
  reviewer_ref text not null,
  reason text,
  evidence_snapshot jsonb not null default '{}'::jsonb,
  decided_at timestamptz not null default now()
);



create table if not exists canonical.publication (
  publication_id uuid primary key default gen_random_uuid(),
  resource_type text not null
    check (resource_type in ('PROTOCOL_VERSION','CLAIM_VERSION','TAXONOMY_NODE_VERSION')),
  resource_id uuid not null,
  publication_status text not null
    check (publication_status in ('PUBLISHED','SUPERSEDED','WITHDRAWN')),
  purpose_scope text[] not null default '{}'::text[],
  published_at timestamptz not null default now(),
  published_by_ref text not null,
  supersedes_publication_id uuid references canonical.publication(publication_id),
  reason text
);





create table if not exists dev_staging.ingestion_candidate (
  ingestion_candidate_id uuid primary key default gen_random_uuid(),
  idempotency_key text not null unique,
  source_version_id uuid not null references canonical.source_version(source_version_id),
  candidate_kind text not null
    check (candidate_kind in ('PROTOCOL','CLAIM','TAXONOMY','RELATION')),
  candidate_payload jsonb not null check (jsonb_typeof(candidate_payload) = 'object'),
  validation_status text not null default 'PENDING'
    check (validation_status in ('PENDING','VALID','INVALID','CONFLICT','INSUFFICIENT_EVIDENCE')),
  review_status text not null default 'PENDING_REVIEW'
    check (review_status in ('PENDING_REVIEW','APPROVED','REJECTED','CHANGES_REQUIRED')),
  validation_report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  created_by_ref text not null,
  reviewed_at timestamptz,
  reviewed_by_ref text
);




create table if not exists kdb_audit.outbox_event (
  outbox_event_id uuid primary key default gen_random_uuid(),
  aggregate_type text not null,
  aggregate_id uuid not null,
  event_type text not null,
  event_version integer not null default 1 check (event_version > 0),
  payload jsonb not null,
  occurred_at timestamptz not null default now(),
  published_at timestamptz,
  attempts integer not null default 0 check (attempts >= 0),
  last_error text
);



create table if not exists kdb_audit.audit_record (
  audit_record_id uuid primary key default gen_random_uuid(),
  actor_ref text not null,
  action text not null,
  resource_type text not null,
  resource_id uuid,
  correlation_id uuid,
  decision_trace_id uuid,
  details jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

commit;
