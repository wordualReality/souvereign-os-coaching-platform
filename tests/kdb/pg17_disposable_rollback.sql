-- Disposable local rollback of KDB-M01 schemas/roles only.
-- Does not touch canonical, dev_staging, public, or stub anon roles.
DROP SCHEMA IF EXISTS kdb_canonical CASCADE;
DROP SCHEMA IF EXISTS kdb_staging CASCADE;
DROP SCHEMA IF EXISTS kdb_governance CASCADE;
DROP SCHEMA IF EXISTS kdb_ops CASCADE;
DROP ROLE IF EXISTS kdb_ingest_runtime;
DROP ROLE IF EXISTS kdb_command_owner;
DROP ROLE IF EXISTS kdb_schema_owner;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kdb_test_fixture_admin') THEN
    EXECUTE 'DROP OWNED BY kdb_test_fixture_admin';
  END IF;
END $$;
DROP ROLE IF EXISTS kdb_test_fixture_admin;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kdb_migrator') THEN
    EXECUTE 'DROP OWNED BY kdb_migrator';
  END IF;
END $$;
DROP ROLE IF EXISTS kdb_migrator;
