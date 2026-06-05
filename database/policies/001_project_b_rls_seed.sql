-- Project B RLS policy seed. Adapt JWT claim extraction to final Supabase auth shape.
alter table project_b.tenants enable row level security;
create policy if not exists tenant_select_policy on project_b.tenants for select using (true);

alter table project_b.tenant_memberships enable row level security;
create policy if not exists tenant_isolation_select on project_b.tenant_memberships
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.tenant_memberships
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.tenant_suspensions enable row level security;
create policy if not exists tenant_isolation_select on project_b.tenant_suspensions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.tenant_suspensions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.external_identity_refs enable row level security;
create policy if not exists tenant_isolation_select on project_b.external_identity_refs
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.external_identity_refs
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.access_decision_cache enable row level security;
create policy if not exists tenant_isolation_select on project_b.access_decision_cache
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.access_decision_cache
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.tenant_feature_configs enable row level security;
create policy if not exists tenant_isolation_select on project_b.tenant_feature_configs
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.tenant_feature_configs
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.tenant_app_blueprints enable row level security;
create policy if not exists tenant_isolation_select on project_b.tenant_app_blueprints
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.tenant_app_blueprints
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.branding_themes enable row level security;
create policy if not exists tenant_isolation_select on project_b.branding_themes
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.branding_themes
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.surface_compositions enable row level security;
create policy if not exists tenant_isolation_select on project_b.surface_compositions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.surface_compositions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.program_drafts enable row level security;
create policy if not exists tenant_isolation_select on project_b.program_drafts
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.program_drafts
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.journey_drafts enable row level security;
create policy if not exists tenant_isolation_select on project_b.journey_drafts
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.journey_drafts
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.journey_phases enable row level security;
create policy if not exists tenant_isolation_select on project_b.journey_phases
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.journey_phases
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.journey_steps enable row level security;
create policy if not exists tenant_isolation_select on project_b.journey_steps
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.journey_steps
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.content_spaces enable row level security;
create policy if not exists tenant_isolation_select on project_b.content_spaces
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.content_spaces
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.content_collections enable row level security;
create policy if not exists tenant_isolation_select on project_b.content_collections
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.content_collections
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.content_items enable row level security;
create policy if not exists tenant_isolation_select on project_b.content_items
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.content_items
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.content_assets enable row level security;
create policy if not exists tenant_isolation_select on project_b.content_assets
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.content_assets
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.canonical_ref_bindings enable row level security;
create policy if not exists tenant_isolation_select on project_b.canonical_ref_bindings
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.canonical_ref_bindings
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.canonical_ref_validation_cache enable row level security;
create policy if not exists tenant_isolation_select on project_b.canonical_ref_validation_cache
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.canonical_ref_validation_cache
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.journey_versions enable row level security;
create policy if not exists tenant_isolation_select on project_b.journey_versions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.journey_versions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.publication_requests enable row level security;
create policy if not exists tenant_isolation_select on project_b.publication_requests
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.publication_requests
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.publication_validation_results enable row level security;
create policy if not exists tenant_isolation_select on project_b.publication_validation_results
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.publication_validation_results
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.leads enable row level security;
create policy if not exists tenant_isolation_select on project_b.leads
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.leads
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.prospects enable row level security;
create policy if not exists tenant_isolation_select on project_b.prospects
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.prospects
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.pipeline_stages enable row level security;
create policy if not exists tenant_isolation_select on project_b.pipeline_stages
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.pipeline_stages
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.pipeline_items enable row level security;
create policy if not exists tenant_isolation_select on project_b.pipeline_items
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.pipeline_items
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.booking_requests enable row level security;
create policy if not exists tenant_isolation_select on project_b.booking_requests
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.booking_requests
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.discovery_calls enable row level security;
create policy if not exists tenant_isolation_select on project_b.discovery_calls
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.discovery_calls
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.offers enable row level security;
create policy if not exists tenant_isolation_select on project_b.offers
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.offers
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.offer_items enable row level security;
create policy if not exists tenant_isolation_select on project_b.offer_items
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.offer_items
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.checkout_sessions enable row level security;
create policy if not exists tenant_isolation_select on project_b.checkout_sessions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.checkout_sessions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.payment_records enable row level security;
create policy if not exists tenant_isolation_select on project_b.payment_records
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.payment_records
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.agreement_statuses enable row level security;
create policy if not exists tenant_isolation_select on project_b.agreement_statuses
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.agreement_statuses
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.activation_requests enable row level security;
create policy if not exists tenant_isolation_select on project_b.activation_requests
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.activation_requests
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.client_profiles enable row level security;
create policy if not exists tenant_isolation_select on project_b.client_profiles
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.client_profiles
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.onboarding_flows enable row level security;
create policy if not exists tenant_isolation_select on project_b.onboarding_flows
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.onboarding_flows
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.onboarding_sessions enable row level security;
create policy if not exists tenant_isolation_select on project_b.onboarding_sessions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.onboarding_sessions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.assignments enable row level security;
create policy if not exists tenant_isolation_select on project_b.assignments
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.assignments
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.enrollments enable row level security;
create policy if not exists tenant_isolation_select on project_b.enrollments
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.enrollments
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.delivery_plans enable row level security;
create policy if not exists tenant_isolation_select on project_b.delivery_plans
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.delivery_plans
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.step_availability enable row level security;
create policy if not exists tenant_isolation_select on project_b.step_availability
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.step_availability
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.member_home_projections enable row level security;
create policy if not exists tenant_isolation_select on project_b.member_home_projections
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.member_home_projections
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.next_action_cards enable row level security;
create policy if not exists tenant_isolation_select on project_b.next_action_cards
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.next_action_cards
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.task_completions enable row level security;
create policy if not exists tenant_isolation_select on project_b.task_completions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.task_completions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.step_completions enable row level security;
create policy if not exists tenant_isolation_select on project_b.step_completions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.step_completions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.reflection_entries enable row level security;
create policy if not exists tenant_isolation_select on project_b.reflection_entries
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.reflection_entries
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.practice_logs enable row level security;
create policy if not exists tenant_isolation_select on project_b.practice_logs
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.practice_logs
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.notification_templates enable row level security;
create policy if not exists tenant_isolation_select on project_b.notification_templates
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.notification_templates
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.notification_schedules enable row level security;
create policy if not exists tenant_isolation_select on project_b.notification_schedules
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.notification_schedules
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.notification_delivery_attempts enable row level security;
create policy if not exists tenant_isolation_select on project_b.notification_delivery_attempts
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.notification_delivery_attempts
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.message_threads enable row level security;
create policy if not exists tenant_isolation_select on project_b.message_threads
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.message_threads
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.messages enable row level security;
create policy if not exists tenant_isolation_select on project_b.messages
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.messages
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.intervention_notes enable row level security;
create policy if not exists tenant_isolation_select on project_b.intervention_notes
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.intervention_notes
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.community_spaces enable row level security;
create policy if not exists tenant_isolation_select on project_b.community_spaces
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.community_spaces
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.community_memberships enable row level security;
create policy if not exists tenant_isolation_select on project_b.community_memberships
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.community_memberships
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.community_posts enable row level security;
create policy if not exists tenant_isolation_select on project_b.community_posts
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.community_posts
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.community_comments enable row level security;
create policy if not exists tenant_isolation_select on project_b.community_comments
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.community_comments
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.content_reports enable row level security;
create policy if not exists tenant_isolation_select on project_b.content_reports
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.content_reports
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.moderation_actions enable row level security;
create policy if not exists tenant_isolation_select on project_b.moderation_actions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.moderation_actions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.coach_dashboard_projections enable row level security;
create policy if not exists tenant_isolation_select on project_b.coach_dashboard_projections
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.coach_dashboard_projections
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.progress_metric_projections enable row level security;
create policy if not exists tenant_isolation_select on project_b.progress_metric_projections
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.progress_metric_projections
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.revenue_metric_projections enable row level security;
create policy if not exists tenant_isolation_select on project_b.revenue_metric_projections
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.revenue_metric_projections
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.risk_signals enable row level security;
create policy if not exists tenant_isolation_select on project_b.risk_signals
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.risk_signals
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.audit_events enable row level security;
create policy if not exists tenant_isolation_select on project_b.audit_events
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.audit_events
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.enforcement_decision_logs enable row level security;
create policy if not exists tenant_isolation_select on project_b.enforcement_decision_logs
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.enforcement_decision_logs
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.outbox_events enable row level security;
create policy if not exists tenant_isolation_select on project_b.outbox_events
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.outbox_events
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.inbox_events enable row level security;
create policy if not exists tenant_isolation_select on project_b.inbox_events
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.inbox_events
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.dead_letter_events enable row level security;
create policy if not exists tenant_isolation_select on project_b.dead_letter_events
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.dead_letter_events
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.projection_checkpoints enable row level security;
create policy if not exists tenant_isolation_select on project_b.projection_checkpoints
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.projection_checkpoints
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.support_cases enable row level security;
create policy if not exists tenant_isolation_select on project_b.support_cases
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.support_cases
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.support_case_notes enable row level security;
create policy if not exists tenant_isolation_select on project_b.support_case_notes
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.support_case_notes
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.ops_interventions enable row level security;
create policy if not exists tenant_isolation_select on project_b.ops_interventions
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.ops_interventions
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');

alter table project_b.replay_requests enable row level security;
create policy if not exists tenant_isolation_select on project_b.replay_requests
    for select using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
create policy if not exists tenant_isolation_write on project_b.replay_requests
    for all using (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id')
    with check (tenant_id::text = current_setting('request.jwt.claims', true)::jsonb->>'tenant_id');
