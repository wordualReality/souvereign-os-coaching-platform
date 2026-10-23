-- KDB-M01-03 / API boundary
-- Source ZIP SHA-256: 2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518
-- Source kdb_m01_foundation.sql SHA-256: e77e313bb070afd821f660b6c7bdda327be4ed41a3910ec1a4537e20f87f9bae
-- Materialization only. Do not apply from this packet.

begin;

create or replace function kdb_api.submit_ingestion_candidate(
  p_idempotency_key text,
  p_source_version_id uuid,
  p_candidate_kind text,
  p_candidate_payload jsonb,
  p_created_by_ref text
)
returns uuid
language plpgsql
security invoker
set search_path = pg_catalog, dev_staging
as $fn$
declare
  candidate_id uuid;
begin
  insert into dev_staging.ingestion_candidate (
    idempotency_key, source_version_id, candidate_kind,
    candidate_payload, created_by_ref
  ) values (
    p_idempotency_key, p_source_version_id, p_candidate_kind,
    p_candidate_payload, p_created_by_ref
  )
  on conflict (idempotency_key) do nothing
  returning ingestion_candidate_id into candidate_id;

  if candidate_id is null then
    select ingestion_candidate_id
      into candidate_id
      from dev_staging.ingestion_candidate
     where idempotency_key = p_idempotency_key;
  end if;

  return candidate_id;
end
$fn$;

create or replace function kdb_api.list_published_protocol_versions(
  p_owning_module_node_id uuid default null
)
returns table (
  protocol_id uuid,
  protocol_version_id uuid,
  stable_key text,
  revision integer,
  canonical_name text,
  display_summary text,
  protocol_category text,
  content_sha256 text
)
language sql
stable
security invoker
set search_path = pg_catalog, canonical
as $fn$
  select p.protocol_id, pv.protocol_version_id, p.stable_key, pv.revision,
         pv.canonical_name, pv.display_summary, pv.protocol_category,
         pv.content_sha256
  from canonical.protocol p
  join canonical.protocol_version pv on pv.protocol_id = p.protocol_id
  where p.lifecycle_status = 'ACTIVE'
    and pv.publication_status = 'PUBLISHED'
    and (p_owning_module_node_id is null
         or p.owning_module_node_id = p_owning_module_node_id)
  order by p.stable_key, pv.revision desc
$fn$;

revoke all on all functions in schema kdb_api from public, anon, authenticated, service_role;
grant execute on function kdb_api.submit_ingestion_candidate(text, uuid, text, jsonb, text)
  to kdb_ingest_writer;
grant execute on function kdb_api.list_published_protocol_versions(uuid)
  to kdb_runtime;

commit;
