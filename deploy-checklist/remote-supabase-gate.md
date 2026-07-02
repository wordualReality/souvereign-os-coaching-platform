# Deploy Checklist -- Remote Supabase Gate

Date: 2026-07-01 | Status: LOCKED

## Required Before Remote Push
- [ ] Local Supabase setup complete
- [ ] All local migrations applied without error
- [ ] npm run validate:all PASS
- [ ] RLS policies reviewed
- [ ] P01 Smoke Test PASS
- [ ] Aydin explicit approval

## Remote Config (when authorized)
SUPABASE_PROJECT_REF=zobjpmyccszkabybdmsf
npx supabase login
npx supabase link --project-ref zobjpmyccszkabybdmsf
npx supabase db push  # review diff before confirming

## Security
- Service role key bypasses RLS -- never expose in browser
- RLS must be enabled on all tables in exposed schemas
- Use anon key for client-facing operations only

## canonical.* on Remote: Additional Gate Required
- [ ] DDL-01 DDL Readiness Review complete
- [ ] FX-01 + AT-05 complete
- [ ] Aydin approval for canonical.* specifically
