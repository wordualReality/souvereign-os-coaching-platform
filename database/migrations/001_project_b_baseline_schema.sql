-- Project B Data Model ERD DDL Pack v1.1 REPAIRED
create schema if not exists project_b;
create extension if not exists pgcrypto;

create or replace function project_b.set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

create table if not exists project_b.tenants (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    display_name text not null,
    lifecycle_state text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_tenants_status on project_b.tenants(status);
create trigger trg_tenants_updated_at before update on project_b.tenants for each row execute function project_b.set_updated_at();

create table if not exists project_b.tenant_memberships (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_tenant_memberships_tenant on project_b.tenant_memberships(tenant_id);
create index if not exists idx_tenant_memberships_status on project_b.tenant_memberships(status);
create trigger trg_tenant_memberships_updated_at before update on project_b.tenant_memberships for each row execute function project_b.set_updated_at();

create table if not exists project_b.tenant_suspensions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_tenant_suspensions_tenant on project_b.tenant_suspensions(tenant_id);
create index if not exists idx_tenant_suspensions_status on project_b.tenant_suspensions(status);
create trigger trg_tenant_suspensions_updated_at before update on project_b.tenant_suspensions for each row execute function project_b.set_updated_at();

create table if not exists project_b.external_identity_refs (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_external_identity_refs_tenant on project_b.external_identity_refs(tenant_id);
create index if not exists idx_external_identity_refs_status on project_b.external_identity_refs(status);
create trigger trg_external_identity_refs_updated_at before update on project_b.external_identity_refs for each row execute function project_b.set_updated_at();

create table if not exists project_b.access_decision_cache (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_access_decision_cache_tenant on project_b.access_decision_cache(tenant_id);
create index if not exists idx_access_decision_cache_status on project_b.access_decision_cache(status);
create trigger trg_access_decision_cache_updated_at before update on project_b.access_decision_cache for each row execute function project_b.set_updated_at();

create table if not exists project_b.tenant_feature_configs (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_tenant_feature_configs_tenant on project_b.tenant_feature_configs(tenant_id);
create index if not exists idx_tenant_feature_configs_status on project_b.tenant_feature_configs(status);
create trigger trg_tenant_feature_configs_updated_at before update on project_b.tenant_feature_configs for each row execute function project_b.set_updated_at();

create table if not exists project_b.tenant_app_blueprints (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_tenant_app_blueprints_tenant on project_b.tenant_app_blueprints(tenant_id);
create index if not exists idx_tenant_app_blueprints_status on project_b.tenant_app_blueprints(status);
create trigger trg_tenant_app_blueprints_updated_at before update on project_b.tenant_app_blueprints for each row execute function project_b.set_updated_at();

create table if not exists project_b.branding_themes (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_branding_themes_tenant on project_b.branding_themes(tenant_id);
create index if not exists idx_branding_themes_status on project_b.branding_themes(status);
create trigger trg_branding_themes_updated_at before update on project_b.branding_themes for each row execute function project_b.set_updated_at();

create table if not exists project_b.surface_compositions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_surface_compositions_tenant on project_b.surface_compositions(tenant_id);
create index if not exists idx_surface_compositions_status on project_b.surface_compositions(status);
create trigger trg_surface_compositions_updated_at before update on project_b.surface_compositions for each row execute function project_b.set_updated_at();

create table if not exists project_b.program_drafts (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_program_drafts_tenant on project_b.program_drafts(tenant_id);
create index if not exists idx_program_drafts_status on project_b.program_drafts(status);
create trigger trg_program_drafts_updated_at before update on project_b.program_drafts for each row execute function project_b.set_updated_at();

create table if not exists project_b.journey_drafts (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_journey_drafts_tenant on project_b.journey_drafts(tenant_id);
create index if not exists idx_journey_drafts_status on project_b.journey_drafts(status);
create trigger trg_journey_drafts_updated_at before update on project_b.journey_drafts for each row execute function project_b.set_updated_at();

create table if not exists project_b.journey_phases (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_journey_phases_tenant on project_b.journey_phases(tenant_id);
create index if not exists idx_journey_phases_status on project_b.journey_phases(status);
create trigger trg_journey_phases_updated_at before update on project_b.journey_phases for each row execute function project_b.set_updated_at();

create table if not exists project_b.journey_steps (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_journey_steps_tenant on project_b.journey_steps(tenant_id);
create index if not exists idx_journey_steps_status on project_b.journey_steps(status);
create trigger trg_journey_steps_updated_at before update on project_b.journey_steps for each row execute function project_b.set_updated_at();

create table if not exists project_b.content_spaces (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_content_spaces_tenant on project_b.content_spaces(tenant_id);
create index if not exists idx_content_spaces_status on project_b.content_spaces(status);
create trigger trg_content_spaces_updated_at before update on project_b.content_spaces for each row execute function project_b.set_updated_at();

create table if not exists project_b.content_collections (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_content_collections_tenant on project_b.content_collections(tenant_id);
create index if not exists idx_content_collections_status on project_b.content_collections(status);
create trigger trg_content_collections_updated_at before update on project_b.content_collections for each row execute function project_b.set_updated_at();

create table if not exists project_b.content_items (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_content_items_tenant on project_b.content_items(tenant_id);
create index if not exists idx_content_items_status on project_b.content_items(status);
create trigger trg_content_items_updated_at before update on project_b.content_items for each row execute function project_b.set_updated_at();

create table if not exists project_b.content_assets (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_content_assets_tenant on project_b.content_assets(tenant_id);
create index if not exists idx_content_assets_status on project_b.content_assets(status);
create trigger trg_content_assets_updated_at before update on project_b.content_assets for each row execute function project_b.set_updated_at();

create table if not exists project_b.canonical_ref_bindings (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_canonical_ref_bindings_tenant on project_b.canonical_ref_bindings(tenant_id);
create index if not exists idx_canonical_ref_bindings_status on project_b.canonical_ref_bindings(status);
create trigger trg_canonical_ref_bindings_updated_at before update on project_b.canonical_ref_bindings for each row execute function project_b.set_updated_at();

create table if not exists project_b.canonical_ref_validation_cache (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_canonical_ref_validation_cache_tenant on project_b.canonical_ref_validation_cache(tenant_id);
create index if not exists idx_canonical_ref_validation_cache_status on project_b.canonical_ref_validation_cache(status);
create trigger trg_canonical_ref_validation_cache_updated_at before update on project_b.canonical_ref_validation_cache for each row execute function project_b.set_updated_at();

create table if not exists project_b.journey_versions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_journey_versions_tenant on project_b.journey_versions(tenant_id);
create index if not exists idx_journey_versions_status on project_b.journey_versions(status);
create trigger trg_journey_versions_updated_at before update on project_b.journey_versions for each row execute function project_b.set_updated_at();

create table if not exists project_b.publication_requests (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_publication_requests_tenant on project_b.publication_requests(tenant_id);
create index if not exists idx_publication_requests_status on project_b.publication_requests(status);
create trigger trg_publication_requests_updated_at before update on project_b.publication_requests for each row execute function project_b.set_updated_at();

create table if not exists project_b.publication_validation_results (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_publication_validation_results_tenant on project_b.publication_validation_results(tenant_id);
create index if not exists idx_publication_validation_results_status on project_b.publication_validation_results(status);
create trigger trg_publication_validation_results_updated_at before update on project_b.publication_validation_results for each row execute function project_b.set_updated_at();

create table if not exists project_b.leads (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_leads_tenant on project_b.leads(tenant_id);
create index if not exists idx_leads_status on project_b.leads(status);
create trigger trg_leads_updated_at before update on project_b.leads for each row execute function project_b.set_updated_at();

create table if not exists project_b.prospects (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_prospects_tenant on project_b.prospects(tenant_id);
create index if not exists idx_prospects_status on project_b.prospects(status);
create trigger trg_prospects_updated_at before update on project_b.prospects for each row execute function project_b.set_updated_at();

create table if not exists project_b.pipeline_stages (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_pipeline_stages_tenant on project_b.pipeline_stages(tenant_id);
create index if not exists idx_pipeline_stages_status on project_b.pipeline_stages(status);
create trigger trg_pipeline_stages_updated_at before update on project_b.pipeline_stages for each row execute function project_b.set_updated_at();

create table if not exists project_b.pipeline_items (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_pipeline_items_tenant on project_b.pipeline_items(tenant_id);
create index if not exists idx_pipeline_items_status on project_b.pipeline_items(status);
create trigger trg_pipeline_items_updated_at before update on project_b.pipeline_items for each row execute function project_b.set_updated_at();

create table if not exists project_b.booking_requests (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_booking_requests_tenant on project_b.booking_requests(tenant_id);
create index if not exists idx_booking_requests_status on project_b.booking_requests(status);
create trigger trg_booking_requests_updated_at before update on project_b.booking_requests for each row execute function project_b.set_updated_at();

create table if not exists project_b.discovery_calls (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_discovery_calls_tenant on project_b.discovery_calls(tenant_id);
create index if not exists idx_discovery_calls_status on project_b.discovery_calls(status);
create trigger trg_discovery_calls_updated_at before update on project_b.discovery_calls for each row execute function project_b.set_updated_at();

create table if not exists project_b.offers (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_offers_tenant on project_b.offers(tenant_id);
create index if not exists idx_offers_status on project_b.offers(status);
create trigger trg_offers_updated_at before update on project_b.offers for each row execute function project_b.set_updated_at();

create table if not exists project_b.offer_items (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_offer_items_tenant on project_b.offer_items(tenant_id);
create index if not exists idx_offer_items_status on project_b.offer_items(status);
create trigger trg_offer_items_updated_at before update on project_b.offer_items for each row execute function project_b.set_updated_at();

create table if not exists project_b.checkout_sessions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_checkout_sessions_tenant on project_b.checkout_sessions(tenant_id);
create index if not exists idx_checkout_sessions_status on project_b.checkout_sessions(status);
create trigger trg_checkout_sessions_updated_at before update on project_b.checkout_sessions for each row execute function project_b.set_updated_at();

create table if not exists project_b.payment_records (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_payment_records_tenant on project_b.payment_records(tenant_id);
create index if not exists idx_payment_records_status on project_b.payment_records(status);
create trigger trg_payment_records_updated_at before update on project_b.payment_records for each row execute function project_b.set_updated_at();

create table if not exists project_b.agreement_statuses (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_agreement_statuses_tenant on project_b.agreement_statuses(tenant_id);
create index if not exists idx_agreement_statuses_status on project_b.agreement_statuses(status);
create trigger trg_agreement_statuses_updated_at before update on project_b.agreement_statuses for each row execute function project_b.set_updated_at();

create table if not exists project_b.activation_requests (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_activation_requests_tenant on project_b.activation_requests(tenant_id);
create index if not exists idx_activation_requests_status on project_b.activation_requests(status);
create trigger trg_activation_requests_updated_at before update on project_b.activation_requests for each row execute function project_b.set_updated_at();

create table if not exists project_b.client_profiles (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_client_profiles_tenant on project_b.client_profiles(tenant_id);
create index if not exists idx_client_profiles_status on project_b.client_profiles(status);
create trigger trg_client_profiles_updated_at before update on project_b.client_profiles for each row execute function project_b.set_updated_at();

create table if not exists project_b.onboarding_flows (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_onboarding_flows_tenant on project_b.onboarding_flows(tenant_id);
create index if not exists idx_onboarding_flows_status on project_b.onboarding_flows(status);
create trigger trg_onboarding_flows_updated_at before update on project_b.onboarding_flows for each row execute function project_b.set_updated_at();

create table if not exists project_b.onboarding_sessions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_onboarding_sessions_tenant on project_b.onboarding_sessions(tenant_id);
create index if not exists idx_onboarding_sessions_status on project_b.onboarding_sessions(status);
create trigger trg_onboarding_sessions_updated_at before update on project_b.onboarding_sessions for each row execute function project_b.set_updated_at();

create table if not exists project_b.assignments (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_assignments_tenant on project_b.assignments(tenant_id);
create index if not exists idx_assignments_status on project_b.assignments(status);
create trigger trg_assignments_updated_at before update on project_b.assignments for each row execute function project_b.set_updated_at();

create table if not exists project_b.enrollments (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_enrollments_tenant on project_b.enrollments(tenant_id);
create index if not exists idx_enrollments_status on project_b.enrollments(status);
create trigger trg_enrollments_updated_at before update on project_b.enrollments for each row execute function project_b.set_updated_at();

create table if not exists project_b.delivery_plans (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_delivery_plans_tenant on project_b.delivery_plans(tenant_id);
create index if not exists idx_delivery_plans_status on project_b.delivery_plans(status);
create trigger trg_delivery_plans_updated_at before update on project_b.delivery_plans for each row execute function project_b.set_updated_at();

create table if not exists project_b.step_availability (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_step_availability_tenant on project_b.step_availability(tenant_id);
create index if not exists idx_step_availability_status on project_b.step_availability(status);
create trigger trg_step_availability_updated_at before update on project_b.step_availability for each row execute function project_b.set_updated_at();

create table if not exists project_b.member_home_projections (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_member_home_projections_tenant on project_b.member_home_projections(tenant_id);
create index if not exists idx_member_home_projections_status on project_b.member_home_projections(status);
create trigger trg_member_home_projections_updated_at before update on project_b.member_home_projections for each row execute function project_b.set_updated_at();

create table if not exists project_b.next_action_cards (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_next_action_cards_tenant on project_b.next_action_cards(tenant_id);
create index if not exists idx_next_action_cards_status on project_b.next_action_cards(status);
create trigger trg_next_action_cards_updated_at before update on project_b.next_action_cards for each row execute function project_b.set_updated_at();

create table if not exists project_b.task_completions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_task_completions_tenant on project_b.task_completions(tenant_id);
create index if not exists idx_task_completions_status on project_b.task_completions(status);
create trigger trg_task_completions_updated_at before update on project_b.task_completions for each row execute function project_b.set_updated_at();

create table if not exists project_b.step_completions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_step_completions_tenant on project_b.step_completions(tenant_id);
create index if not exists idx_step_completions_status on project_b.step_completions(status);
create trigger trg_step_completions_updated_at before update on project_b.step_completions for each row execute function project_b.set_updated_at();

create table if not exists project_b.reflection_entries (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_reflection_entries_tenant on project_b.reflection_entries(tenant_id);
create index if not exists idx_reflection_entries_status on project_b.reflection_entries(status);
create trigger trg_reflection_entries_updated_at before update on project_b.reflection_entries for each row execute function project_b.set_updated_at();

create table if not exists project_b.practice_logs (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_practice_logs_tenant on project_b.practice_logs(tenant_id);
create index if not exists idx_practice_logs_status on project_b.practice_logs(status);
create trigger trg_practice_logs_updated_at before update on project_b.practice_logs for each row execute function project_b.set_updated_at();

create table if not exists project_b.notification_templates (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_notification_templates_tenant on project_b.notification_templates(tenant_id);
create index if not exists idx_notification_templates_status on project_b.notification_templates(status);
create trigger trg_notification_templates_updated_at before update on project_b.notification_templates for each row execute function project_b.set_updated_at();

create table if not exists project_b.notification_schedules (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_notification_schedules_tenant on project_b.notification_schedules(tenant_id);
create index if not exists idx_notification_schedules_status on project_b.notification_schedules(status);
create trigger trg_notification_schedules_updated_at before update on project_b.notification_schedules for each row execute function project_b.set_updated_at();

create table if not exists project_b.notification_delivery_attempts (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_notification_delivery_attempts_tenant on project_b.notification_delivery_attempts(tenant_id);
create index if not exists idx_notification_delivery_attempts_status on project_b.notification_delivery_attempts(status);
create trigger trg_notification_delivery_attempts_updated_at before update on project_b.notification_delivery_attempts for each row execute function project_b.set_updated_at();

create table if not exists project_b.message_threads (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_message_threads_tenant on project_b.message_threads(tenant_id);
create index if not exists idx_message_threads_status on project_b.message_threads(status);
create trigger trg_message_threads_updated_at before update on project_b.message_threads for each row execute function project_b.set_updated_at();

create table if not exists project_b.messages (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_messages_tenant on project_b.messages(tenant_id);
create index if not exists idx_messages_status on project_b.messages(status);
create trigger trg_messages_updated_at before update on project_b.messages for each row execute function project_b.set_updated_at();

create table if not exists project_b.intervention_notes (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_intervention_notes_tenant on project_b.intervention_notes(tenant_id);
create index if not exists idx_intervention_notes_status on project_b.intervention_notes(status);
create trigger trg_intervention_notes_updated_at before update on project_b.intervention_notes for each row execute function project_b.set_updated_at();

create table if not exists project_b.community_spaces (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_community_spaces_tenant on project_b.community_spaces(tenant_id);
create index if not exists idx_community_spaces_status on project_b.community_spaces(status);
create trigger trg_community_spaces_updated_at before update on project_b.community_spaces for each row execute function project_b.set_updated_at();

create table if not exists project_b.community_memberships (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_community_memberships_tenant on project_b.community_memberships(tenant_id);
create index if not exists idx_community_memberships_status on project_b.community_memberships(status);
create trigger trg_community_memberships_updated_at before update on project_b.community_memberships for each row execute function project_b.set_updated_at();

create table if not exists project_b.community_posts (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_community_posts_tenant on project_b.community_posts(tenant_id);
create index if not exists idx_community_posts_status on project_b.community_posts(status);
create trigger trg_community_posts_updated_at before update on project_b.community_posts for each row execute function project_b.set_updated_at();

create table if not exists project_b.community_comments (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_community_comments_tenant on project_b.community_comments(tenant_id);
create index if not exists idx_community_comments_status on project_b.community_comments(status);
create trigger trg_community_comments_updated_at before update on project_b.community_comments for each row execute function project_b.set_updated_at();

create table if not exists project_b.content_reports (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_content_reports_tenant on project_b.content_reports(tenant_id);
create index if not exists idx_content_reports_status on project_b.content_reports(status);
create trigger trg_content_reports_updated_at before update on project_b.content_reports for each row execute function project_b.set_updated_at();

create table if not exists project_b.moderation_actions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_moderation_actions_tenant on project_b.moderation_actions(tenant_id);
create index if not exists idx_moderation_actions_status on project_b.moderation_actions(status);
create trigger trg_moderation_actions_updated_at before update on project_b.moderation_actions for each row execute function project_b.set_updated_at();

create table if not exists project_b.coach_dashboard_projections (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_coach_dashboard_projections_tenant on project_b.coach_dashboard_projections(tenant_id);
create index if not exists idx_coach_dashboard_projections_status on project_b.coach_dashboard_projections(status);
create trigger trg_coach_dashboard_projections_updated_at before update on project_b.coach_dashboard_projections for each row execute function project_b.set_updated_at();

create table if not exists project_b.progress_metric_projections (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_progress_metric_projections_tenant on project_b.progress_metric_projections(tenant_id);
create index if not exists idx_progress_metric_projections_status on project_b.progress_metric_projections(status);
create trigger trg_progress_metric_projections_updated_at before update on project_b.progress_metric_projections for each row execute function project_b.set_updated_at();

create table if not exists project_b.revenue_metric_projections (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_revenue_metric_projections_tenant on project_b.revenue_metric_projections(tenant_id);
create index if not exists idx_revenue_metric_projections_status on project_b.revenue_metric_projections(status);
create trigger trg_revenue_metric_projections_updated_at before update on project_b.revenue_metric_projections for each row execute function project_b.set_updated_at();

create table if not exists project_b.risk_signals (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_risk_signals_tenant on project_b.risk_signals(tenant_id);
create index if not exists idx_risk_signals_status on project_b.risk_signals(status);
create trigger trg_risk_signals_updated_at before update on project_b.risk_signals for each row execute function project_b.set_updated_at();

create table if not exists project_b.audit_events (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_audit_events_tenant on project_b.audit_events(tenant_id);
create index if not exists idx_audit_events_status on project_b.audit_events(status);
create trigger trg_audit_events_updated_at before update on project_b.audit_events for each row execute function project_b.set_updated_at();

create table if not exists project_b.enforcement_decision_logs (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_enforcement_decision_logs_tenant on project_b.enforcement_decision_logs(tenant_id);
create index if not exists idx_enforcement_decision_logs_status on project_b.enforcement_decision_logs(status);
create trigger trg_enforcement_decision_logs_updated_at before update on project_b.enforcement_decision_logs for each row execute function project_b.set_updated_at();

create table if not exists project_b.outbox_events (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid,
    aggregate_type text not null,
    aggregate_id uuid,
    event_type text not null,
    event_version int not null default 1,
    event_id uuid not null unique default gen_random_uuid(),
    event_payload jsonb not null,
    headers jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    retry_count int not null default 0,
    available_at timestamptz not null default now(),
    published_at timestamptz,
    correlation_id uuid not null,
    causation_id uuid,
    created_at timestamptz not null default now()
);
create index if not exists idx_outbox_events_tenant on project_b.outbox_events(tenant_id);
create index if not exists idx_outbox_events_status_available on project_b.outbox_events(status, available_at);

create table if not exists project_b.inbox_events (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid,
    event_id uuid not null unique,
    event_type text not null,
    consumer_name text not null,
    status text not null default 'received',
    processed_at timestamptz,
    correlation_id uuid,
    created_at timestamptz not null default now()
);
create index if not exists idx_inbox_events_tenant on project_b.inbox_events(tenant_id);

create table if not exists project_b.dead_letter_events (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid,
    event_id uuid,
    event_type text not null,
    failure_reason text not null,
    payload jsonb not null,
    retry_count int not null default 0,
    correlation_id uuid,
    created_at timestamptz not null default now()
);
create index if not exists idx_dead_letter_events_tenant on project_b.dead_letter_events(tenant_id);

create table if not exists project_b.projection_checkpoints (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid,
    projection_name text not null,
    checkpoint_value text not null,
    lag_seconds int default 0,
    updated_at timestamptz not null default now(),
    correlation_id uuid,
    unique(tenant_id, projection_name)
);
create index if not exists idx_projection_checkpoints_tenant on project_b.projection_checkpoints(tenant_id);

create table if not exists project_b.support_cases (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_support_cases_tenant on project_b.support_cases(tenant_id);
create index if not exists idx_support_cases_status on project_b.support_cases(status);
create trigger trg_support_cases_updated_at before update on project_b.support_cases for each row execute function project_b.set_updated_at();

create table if not exists project_b.support_case_notes (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_support_case_notes_tenant on project_b.support_case_notes(tenant_id);
create index if not exists idx_support_case_notes_status on project_b.support_case_notes(status);
create trigger trg_support_case_notes_updated_at before update on project_b.support_case_notes for each row execute function project_b.set_updated_at();

create table if not exists project_b.ops_interventions (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_ops_interventions_tenant on project_b.ops_interventions(tenant_id);
create index if not exists idx_ops_interventions_status on project_b.ops_interventions(status);
create trigger trg_ops_interventions_updated_at before update on project_b.ops_interventions for each row execute function project_b.set_updated_at();

create table if not exists project_b.replay_requests (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by_actor_ref text,
    updated_by_actor_ref text,
    correlation_id uuid,
    data jsonb not null default '{}'::jsonb
);
create index if not exists idx_replay_requests_tenant on project_b.replay_requests(tenant_id);
create index if not exists idx_replay_requests_status on project_b.replay_requests(status);
create trigger trg_replay_requests_updated_at before update on project_b.replay_requests for each row execute function project_b.set_updated_at();

alter table project_b.tenant_memberships add constraint fk_tenant_memberships_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.tenant_suspensions add constraint fk_tenant_suspensions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.external_identity_refs add constraint fk_external_identity_refs_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.access_decision_cache add constraint fk_access_decision_cache_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.tenant_feature_configs add constraint fk_tenant_feature_configs_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.tenant_app_blueprints add constraint fk_tenant_app_blueprints_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.branding_themes add constraint fk_branding_themes_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.surface_compositions add constraint fk_surface_compositions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.program_drafts add constraint fk_program_drafts_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.journey_drafts add constraint fk_journey_drafts_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.journey_phases add constraint fk_journey_phases_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.journey_steps add constraint fk_journey_steps_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.content_spaces add constraint fk_content_spaces_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.content_collections add constraint fk_content_collections_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.content_items add constraint fk_content_items_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.content_assets add constraint fk_content_assets_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.canonical_ref_bindings add constraint fk_canonical_ref_bindings_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.canonical_ref_validation_cache add constraint fk_canonical_ref_validation_cache_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.journey_versions add constraint fk_journey_versions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.publication_requests add constraint fk_publication_requests_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.publication_validation_results add constraint fk_publication_validation_results_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.leads add constraint fk_leads_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.prospects add constraint fk_prospects_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.pipeline_stages add constraint fk_pipeline_stages_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.pipeline_items add constraint fk_pipeline_items_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.booking_requests add constraint fk_booking_requests_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.discovery_calls add constraint fk_discovery_calls_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.offers add constraint fk_offers_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.offer_items add constraint fk_offer_items_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.checkout_sessions add constraint fk_checkout_sessions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.payment_records add constraint fk_payment_records_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.agreement_statuses add constraint fk_agreement_statuses_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.activation_requests add constraint fk_activation_requests_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.client_profiles add constraint fk_client_profiles_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.onboarding_flows add constraint fk_onboarding_flows_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.onboarding_sessions add constraint fk_onboarding_sessions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.assignments add constraint fk_assignments_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.enrollments add constraint fk_enrollments_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.delivery_plans add constraint fk_delivery_plans_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.step_availability add constraint fk_step_availability_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.member_home_projections add constraint fk_member_home_projections_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.next_action_cards add constraint fk_next_action_cards_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.task_completions add constraint fk_task_completions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.step_completions add constraint fk_step_completions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.reflection_entries add constraint fk_reflection_entries_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.practice_logs add constraint fk_practice_logs_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.notification_templates add constraint fk_notification_templates_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.notification_schedules add constraint fk_notification_schedules_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.notification_delivery_attempts add constraint fk_notification_delivery_attempts_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.message_threads add constraint fk_message_threads_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.messages add constraint fk_messages_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.intervention_notes add constraint fk_intervention_notes_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.community_spaces add constraint fk_community_spaces_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.community_memberships add constraint fk_community_memberships_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.community_posts add constraint fk_community_posts_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.community_comments add constraint fk_community_comments_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.content_reports add constraint fk_content_reports_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.moderation_actions add constraint fk_moderation_actions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.coach_dashboard_projections add constraint fk_coach_dashboard_projections_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.progress_metric_projections add constraint fk_progress_metric_projections_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.revenue_metric_projections add constraint fk_revenue_metric_projections_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.risk_signals add constraint fk_risk_signals_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.audit_events add constraint fk_audit_events_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.enforcement_decision_logs add constraint fk_enforcement_decision_logs_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.outbox_events add constraint fk_outbox_events_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.inbox_events add constraint fk_inbox_events_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.dead_letter_events add constraint fk_dead_letter_events_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.projection_checkpoints add constraint fk_projection_checkpoints_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.support_cases add constraint fk_support_cases_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.support_case_notes add constraint fk_support_case_notes_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.ops_interventions add constraint fk_ops_interventions_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
alter table project_b.replay_requests add constraint fk_replay_requests_tenant foreign key (tenant_id) references project_b.tenants(id) on delete restrict;
