# Deploy Checklist -- Local Supabase Setup

Date: 2026-07-01

## Prerequisites
- [ ] Docker Desktop / OrbStack running
- [ ] Node.js 20+ (node -v)
- [ ] npm installed
- [ ] Repo cloned: github.com/wordualReality/souvereign-os-coaching-platform
- [ ] git status clean

## Install Supabase CLI
npm install supabase --save-dev
npx supabase --help

## Start Local Stack
npx supabase start
npx supabase status  # record: Studio URL, API URL, local DB URL, keys

## Apply project_b Migrations Locally
npx supabase db push
# OR:
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -f database/migrations/001_project_b_baseline_schema.sql
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -f database/migrations/002_project_b_journey_provisioning_hardening.sql
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -f database/policies/001_project_b_rls_seed.sql

## Validate
python scripts/validate_sql_static.py
python scripts/validate_rls_static.py
npm run validate:all

## NOT Allowed Here
- Do NOT push to remote Supabase
- Do NOT create canonical.* tables
- Do NOT seed unapproved protocol candidates
- Do NOT expose service_role key

## Rollback
npx supabase stop && npx supabase db reset
