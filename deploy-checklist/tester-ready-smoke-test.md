# Deploy Checklist -- Tester-Ready Smoke Test

Date: 2026-07-01 | Target: 2026-07-17

## Scope
P01 Manual Client Provisioning ONLY.
No protocol content. No broad UI. No client-facing protocol features.

## Checklist
- [ ] Local Supabase running
- [ ] project_b migrations 001+002 applied
- [ ] RLS policies applied
- [ ] API server running (Spring Boot)
- [ ] Admin/Ops UI accessible (Next.js)
- [ ] Tenant created via Admin/Ops
- [ ] Client manually created via Admin/Ops
- [ ] Client assigned to tenant
- [ ] Coach assigned to client
- [ ] Provisioning status visible
- [ ] Invite sent
- [ ] Audit event recorded for each action
- [ ] No canonical.* access attempted
- [ ] No getProtocolDetail() called

## Validation After Smoke Test
npm run validate:all
python scripts/validate_mvp_slice_01.py
python scripts/validate_rls_static.py

## Known Limitations for Tester Alpha
- No protocol content (canonical not yet approved)
- No journey assignment with content
- No client-facing app features
- No analytics or commerce
