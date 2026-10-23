-- KDB-M01-03 / security boundary
-- Source ZIP SHA-256: 2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518
-- Source kdb_m01_foundation.sql SHA-256: e77e313bb070afd821f660b6c7bdda327be4ed41a3910ec1a4537e20f87f9bae
-- Materialization only. Do not apply from this packet.

begin;

do $roles$
begin
  if not exists (select 1 from pg_roles where rolname = 'kdb_runtime') then
    create role kdb_runtime nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'kdb_ingest_writer') then
    create role kdb_ingest_writer nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'kdb_reviewer') then
    create role kdb_reviewer nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end
$roles$;

create or replace function kdb_audit.reject_immutable_mutation()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog
as $fn$
begin
  raise exception using
    errcode = '55000',
    message = format('%I.%I is immutable; create a new version instead', tg_table_schema, tg_table_name);
end
$fn$;

revoke all on function kdb_audit.reject_immutable_mutation() from public;

do $immutability$
declare
  relation_name text;
begin
  foreach relation_name in array array[
    'taxonomy_node_version', 'source_version', 'claim_version', 'evidence',
    'claim_evidence', 'protocol_version', 'protocol_version_claim',
    'protocol_version_taxonomy_relation', 'review_decision', 'publication'
  ] loop
    execute format('drop trigger if exists %I on canonical.%I',
      'trg_' || relation_name || '_immutable', relation_name);
    execute format(
      'create trigger %I before update or delete on canonical.%I for each row execute function kdb_audit.reject_immutable_mutation()',
      'trg_' || relation_name || '_immutable', relation_name
    );
  end loop;
end
$immutability$;

-- RLS is enabled and forced for every KDB table. Roles receive only task-specific policies.
alter table canonical.taxonomy_node enable row level security;
alter table canonical.taxonomy_node force row level security;
alter table canonical.taxonomy_node_version enable row level security;
alter table canonical.taxonomy_node_version force row level security;
alter table canonical.source enable row level security;
alter table canonical.source force row level security;
alter table canonical.source_version enable row level security;
alter table canonical.source_version force row level security;
alter table canonical.claim enable row level security;
alter table canonical.claim force row level security;
alter table canonical.claim_version enable row level security;
alter table canonical.claim_version force row level security;
alter table canonical.evidence enable row level security;
alter table canonical.evidence force row level security;
alter table canonical.claim_evidence enable row level security;
alter table canonical.claim_evidence force row level security;
alter table canonical.protocol enable row level security;
alter table canonical.protocol force row level security;
alter table canonical.protocol_version enable row level security;
alter table canonical.protocol_version force row level security;
alter table canonical.protocol_version_claim enable row level security;
alter table canonical.protocol_version_claim force row level security;
alter table canonical.protocol_version_taxonomy_relation enable row level security;
alter table canonical.protocol_version_taxonomy_relation force row level security;
alter table canonical.review_decision enable row level security;
alter table canonical.review_decision force row level security;
alter table canonical.publication enable row level security;
alter table canonical.publication force row level security;
alter table dev_staging.ingestion_candidate enable row level security;
alter table dev_staging.ingestion_candidate force row level security;
alter table kdb_audit.outbox_event enable row level security;
alter table kdb_audit.outbox_event force row level security;
alter table kdb_audit.audit_record enable row level security;
alter table kdb_audit.audit_record force row level security;

grant usage on schema canonical, kdb_api to kdb_runtime;
grant select on canonical.taxonomy_node, canonical.taxonomy_node_version,
  canonical.claim, canonical.claim_version, canonical.evidence,
  canonical.claim_evidence, canonical.protocol, canonical.protocol_version,
  canonical.protocol_version_claim, canonical.protocol_version_taxonomy_relation,
  canonical.publication to kdb_runtime;

grant usage on schema canonical, dev_staging, kdb_api to kdb_ingest_writer;
grant select on canonical.source, canonical.source_version to kdb_ingest_writer;
grant insert, select on dev_staging.ingestion_candidate to kdb_ingest_writer;

grant usage on schema canonical, dev_staging, kdb_audit, kdb_api to kdb_reviewer;
grant select on all tables in schema canonical, dev_staging to kdb_reviewer;
grant insert on canonical.review_decision, canonical.publication,
  kdb_audit.outbox_event, kdb_audit.audit_record to kdb_reviewer;
grant update (validation_status, review_status, validation_report, reviewed_at, reviewed_by_ref)
  on dev_staging.ingestion_candidate to kdb_reviewer;

create policy kdb_runtime_read_taxonomy_node on canonical.taxonomy_node
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_taxonomy_node_version on canonical.taxonomy_node_version
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_claim on canonical.claim
  for select to kdb_runtime using (lifecycle_status = 'ACTIVE');
create policy kdb_runtime_read_claim_version on canonical.claim_version
  for select to kdb_runtime using (valid_to is null);
create policy kdb_runtime_read_evidence on canonical.evidence
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_claim_evidence on canonical.claim_evidence
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_protocol on canonical.protocol
  for select to kdb_runtime using (lifecycle_status = 'ACTIVE');
create policy kdb_runtime_read_protocol_version on canonical.protocol_version
  for select to kdb_runtime using (publication_status = 'PUBLISHED');
create policy kdb_runtime_read_protocol_version_claim on canonical.protocol_version_claim
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_protocol_version_taxonomy on canonical.protocol_version_taxonomy_relation
  for select to kdb_runtime using (true);
create policy kdb_runtime_read_publication on canonical.publication
  for select to kdb_runtime using (publication_status = 'PUBLISHED');

create policy kdb_ingest_read_source on canonical.source
  for select to kdb_ingest_writer using (lifecycle_status <> 'WITHDRAWN');
create policy kdb_ingest_read_source_version on canonical.source_version
  for select to kdb_ingest_writer using (rights_status <> 'PROHIBITED');
create policy kdb_ingest_insert_candidate on dev_staging.ingestion_candidate
  for insert to kdb_ingest_writer with check (
    validation_status = 'PENDING' and review_status = 'PENDING_REVIEW'
  );
create policy kdb_ingest_read_own_candidate on dev_staging.ingestion_candidate
  for select to kdb_ingest_writer using (true);

create policy kdb_reviewer_read_taxonomy_node on canonical.taxonomy_node
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_taxonomy_node_version on canonical.taxonomy_node_version
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_source on canonical.source
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_source_version on canonical.source_version
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_claim on canonical.claim
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_claim_version on canonical.claim_version
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_evidence on canonical.evidence
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_claim_evidence on canonical.claim_evidence
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_protocol on canonical.protocol
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_protocol_version on canonical.protocol_version
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_protocol_version_claim on canonical.protocol_version_claim
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_protocol_version_taxonomy on canonical.protocol_version_taxonomy_relation
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_read_review_decision on canonical.review_decision
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_insert_review_decision on canonical.review_decision
  for insert to kdb_reviewer with check (reviewer_ref <> '');
create policy kdb_reviewer_read_publication on canonical.publication
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_insert_publication on canonical.publication
  for insert to kdb_reviewer with check (published_by_ref <> '');
create policy kdb_reviewer_read_candidate on dev_staging.ingestion_candidate
  for select to kdb_reviewer using (true);
create policy kdb_reviewer_update_candidate on dev_staging.ingestion_candidate
  for update to kdb_reviewer using (true) with check (true);
create policy kdb_reviewer_insert_outbox on kdb_audit.outbox_event
  for insert to kdb_reviewer with check (true);
create policy kdb_reviewer_insert_audit on kdb_audit.audit_record
  for insert to kdb_reviewer with check (actor_ref <> '');
alter default privileges for role postgres in schema canonical
  revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema dev_staging
  revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema kdb_audit
  revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema kdb_api
  revoke execute on functions from public, anon, authenticated, service_role;

commit;
