-- Synthetic, non-personal KDB-M01 verification fixture.

insert into canonical.source (
  stable_key, source_type, canonical_uri, title, publisher_or_author,
  lifecycle_status, created_by_ref
) values (
  'fixture:kdb-m01:source-001', 'GUIDELINE',
  'urn:kdb:fixture:source-001', 'KDB-M01 Synthetic Source',
  'KDB Test Fixture', 'ACTIVE', 'kdb-m01-test'
)
on conflict (stable_key) do nothing;

insert into canonical.source_version (
  source_id, revision, content_sha256, acquired_at, published_at,
  rights_status, permitted_purposes, provenance_payload,
  storage_locator, created_by_ref
)
select source_id, 1,
       'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
       now(), now(), 'VERIFIED', array['TEST_ONLY'],
       '{"synthetic":true,"purpose":"KDB-M01 verification"}'::jsonb,
       'urn:kdb:fixture:source-version-001', 'kdb-m01-test'
from canonical.source
where stable_key='fixture:kdb-m01:source-001'
on conflict (source_id, revision) do nothing;

insert into canonical.taxonomy_node (
  stable_key, node_type, lifecycle_status, created_by_ref
) values (
  'fixture:module:breathwork', 'MODULE', 'ACTIVE', 'kdb-m01-test'
)
on conflict (stable_key) do nothing;

insert into canonical.taxonomy_node_version (
  taxonomy_node_id, revision, label, description, semantic_payload,
  content_sha256, created_by_ref
)
select taxonomy_node_id, 1, 'Synthetic Breathwork Module',
       'Non-production test module.', '{"synthetic":true}'::jsonb,
       'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
       'kdb-m01-test'
from canonical.taxonomy_node
where stable_key='fixture:module:breathwork'
on conflict (taxonomy_node_id, revision) do nothing;

insert into canonical.protocol (
  stable_key, owning_module_node_id, lifecycle_status, created_by_ref
)
select 'fixture:protocol:box-breathing', taxonomy_node_id,
       'ACTIVE', 'kdb-m01-test'
from canonical.taxonomy_node
where stable_key='fixture:module:breathwork'
on conflict (stable_key) do nothing;

insert into canonical.protocol_version (
  protocol_id, revision, canonical_name, display_summary,
  protocol_category, steps, contraindications, dosha_relevance,
  evidence_level, review_status, publication_status,
  content_sha256, created_by_ref
)
select protocol_id, 1, 'Synthetic Box Breathing',
       'Test-only protocol version.', 'BREATHWORK',
       '[{"order":1,"instruction":"Synthetic inhale"},{"order":2,"instruction":"Synthetic hold"}]'::jsonb,
       '[{"type":"CAUTION","text":"Synthetic fixture only"}]'::jsonb,
       '{"vata":"test-only","pitta":"test-only","kapha":"test-only"}'::jsonb,
       'UNRATED', 'APPROVED', 'PUBLISHED',
       'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
       'kdb-m01-test'
from canonical.protocol
where stable_key='fixture:protocol:box-breathing'
on conflict (protocol_id, revision) do nothing;

insert into canonical.publication (
  resource_type, resource_id, publication_status, purpose_scope,
  published_by_ref, reason
)
select 'PROTOCOL_VERSION', protocol_version_id, 'PUBLISHED',
       array['TEST_ONLY'], 'kdb-m01-test', 'Synthetic verification publication'
from canonical.protocol_version pv
join canonical.protocol p on p.protocol_id=pv.protocol_id
where p.stable_key='fixture:protocol:box-breathing' and pv.revision=1
on conflict (resource_type, resource_id)
  where publication_status='PUBLISHED'
do nothing;

select kdb_api.submit_ingestion_candidate(
  'fixture:kdb-m01:candidate-001', sv.source_version_id, 'PROTOCOL',
  '{"synthetic":true,"protocol_key":"fixture:box-breathing"}'::jsonb,
  'kdb-m01-test'
)
from canonical.source_version sv
join canonical.source s on s.source_id=sv.source_id
where s.stable_key='fixture:kdb-m01:source-001' and sv.revision=1;
