# Deploy Checklist -- RLS Readiness

Date: 2026-07-01

## project_b RLS
- [ ] 001_project_b_rls_seed.sql reviewed
- [ ] All tenant-sensitive tables have RLS enabled
- [ ] Tenant isolation enforced (no cross-tenant reads)
- [ ] coach_assignment RLS: coaches see only own clients
- [ ] client RLS: clients see only own data
- [ ] Admin/Ops RLS: scoped to authorized roles

## Validate
python scripts/validate_rls_static.py

## canonical.* RLS (future)
Do NOT create canonical.* tables without explicit RLS spec from DB Architect.

## dev_staging RLS
dev_staging.protocol_candidate: internal/ops roles only.
Never expose to client-facing APIs.
