-- Project B v1.1 Journey Builder & Client Provisioning Patch
-- Applies after Project B Final Dev-Handoff Bundle v1.0 data model.

create table if not exists project_b.provisioning_sessions (
  provisioning_session_id uuid primary key,
  tenant_id uuid not null,
  client_id uuid,
  actor_ref text not null,
  provisioning_mode text not null check (provisioning_mode in ('manual_admin','manual_coach','import','commerce_recovery')),
  lifecycle_state text not null,
  bypass_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_b.client_ownerships (
  client_ownership_id uuid primary key,
  tenant_id uuid not null,
  client_id uuid not null,
  primary_coach_ref text,
  ownership_state text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_b.support_coach_assignments (
  support_assignment_id uuid primary key,
  tenant_id uuid not null,
  client_id uuid not null,
  coach_ref text not null,
  assignment_state text not null,
  created_at timestamptz not null default now()
);

create table if not exists project_b.journey_templates (
  template_id uuid primary key,
  tenant_id uuid,
  owner_scope text not null check (owner_scope in ('platform','tenant','coach')),
  template_type text not null,
  lifecycle_state text not null,
  title text not null,
  canonical_ref_policy text not null,
  created_by_ref text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_b.journey_template_versions (
  template_version_id uuid primary key,
  template_id uuid not null references project_b.journey_templates(template_id),
  semantic_version text not null,
  lifecycle_state text not null,
  published_at timestamptz,
  definition_json jsonb not null
);

create table if not exists project_b.journey_template_clones (
  clone_id uuid primary key,
  template_version_id uuid not null references project_b.journey_template_versions(template_version_id),
  tenant_id uuid not null,
  target_journey_draft_id uuid,
  target_cohort_id uuid,
  clone_mode text not null,
  cloned_by_ref text not null,
  cloned_at timestamptz not null default now()
);

create table if not exists project_b.cohorts (
  cohort_id uuid primary key,
  tenant_id uuid not null,
  title text not null,
  cohort_mode text not null check (cohort_mode in ('fixed_start','rolling','invite_only','tenant_wide','coach_led')),
  lifecycle_state text not null,
  primary_coach_ref text,
  starts_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_b.cohort_memberships (
  cohort_membership_id uuid primary key,
  tenant_id uuid not null,
  cohort_id uuid not null references project_b.cohorts(cohort_id),
  client_id uuid not null,
  enrollment_id uuid,
  membership_state text not null,
  joined_at timestamptz not null default now()
);

create table if not exists project_b.cohort_schedules (
  cohort_schedule_id uuid primary key,
  tenant_id uuid not null,
  cohort_id uuid not null references project_b.cohorts(cohort_id),
  schedule_json jsonb not null,
  timezone text not null default 'UTC',
  created_at timestamptz not null default now()
);

create table if not exists project_b.journey_condition_rules (
  rule_id uuid primary key,
  tenant_id uuid not null,
  journey_version_id uuid,
  cohort_id uuid,
  rule_type text not null,
  input_json jsonb not null,
  operator text not null,
  effect_json jsonb not null,
  priority integer not null default 0,
  lifecycle_state text not null,
  created_at timestamptz not null default now()
);

create table if not exists project_b.journey_rule_evaluation_traces (
  trace_id uuid primary key,
  tenant_id uuid not null,
  client_id uuid not null,
  assignment_id uuid,
  rule_id uuid references project_b.journey_condition_rules(rule_id),
  input_snapshot jsonb not null,
  effect_json jsonb not null,
  evaluated_at timestamptz not null default now()
);

create index if not exists idx_provisioning_sessions_tenant_state on project_b.provisioning_sessions(tenant_id, lifecycle_state);
create index if not exists idx_client_ownerships_tenant_client on project_b.client_ownerships(tenant_id, client_id);
create index if not exists idx_cohort_memberships_tenant_cohort on project_b.cohort_memberships(tenant_id, cohort_id);
create index if not exists idx_condition_rules_tenant_journey on project_b.journey_condition_rules(tenant_id, journey_version_id);
