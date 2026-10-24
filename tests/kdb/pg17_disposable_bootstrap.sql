-- Disposable local PostgreSQL 17 fixture only.
-- Creates stub Supabase-named roles so 001-003 REVOKE statements can parse.
-- Never run on zobjpmyccszkabybdmsf or production.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOBYPASSRLS;
  END IF;
END $$;
