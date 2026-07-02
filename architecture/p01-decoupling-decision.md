# P01 Decoupling Decision

Date: 2026-07-01 | Decision: P01 CAN PROCEED IMMEDIATELY

## Decision
ARCH-DECISION-2026-07-01-P01-DECOUPLING
P01 Manual Client Provisioning may proceed in parallel to canonical.* implementation.

## P01 May Include
- Tenant creation/lifecycle
- Manual client creation
- Client-tenant assignment
- Coach/Ops assignment
- Invite/activation/provisioning status
- Role/entitlement binding (project_b/core scope only)
- Audit events
- Admin/Ops provisioning workflow
- Minimal Admin/Ops UI per PB-CURSOR-JH-001

## P01 Must NOT Include
- canonical.* access or migrations
- getProtocolDetail()
- protocol_detail_projection
- dev_staging.protocol_candidate
- PROJECT_B_SEED_ALLOWED / CANONICAL_APPROVED_EXPORT
- video_url implementation
- project_b.exercise_* tables
- Broad UI Build
- Client-facing protocol content

## Gate Instruction for PB-CURSOR-JH-001
Prepend before execution:
"P01 authorized as tenant/account/client provisioning only.
STOP and create NEEDS_ALIGNMENT.md if any of the above Must NOT items become necessary."

## Tables Involved (project_b schema, migrations 001+002)
- project_b.tenants, tenant_memberships, tenant_suspensions
- project_b.external_identity_refs, access_decision_cache
- project_b.tenant_feature_configs, tenant_app_blueprints
- project_b.provisioning_sessions, client_ownerships, support_coach_assignments
