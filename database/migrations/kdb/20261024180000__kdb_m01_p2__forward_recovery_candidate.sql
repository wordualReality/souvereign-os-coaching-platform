-- KDB-M01-P2 / forward recovery CANDIDATE only.
-- STATUS: NOT_AUTHORIZED_FOR_APPLY
-- TARGET IF EVER AUTHORIZED: ujdzahwlximlmndexgmx after independent review
--   and a MATCH on tests/kdb/hosted_recovery_preflight_diff.py against a live
--   read-only preflight transcript.
-- FORBIDDEN: integration main project, SOV runtime dev.
-- FORBIDDEN: DROP SCHEMA, DELETE/UPDATE canonical.protocol, truncate or rewrite
--   supabase_migrations.schema_migrations, unconditional CREATE ROLE, foundation replay.
-- The remaining canonical.protocol row provenance is UNKNOWN. Leave the row.

-- This file is a reviewed-shape candidate. Do not execute it in CI or from Cursor.
-- Live apply waits for independent DB/security review plus verified target/preimage.

-- Intended forward steps after MATCH, each guarded:
-- 1. Confirm current_database is not zobj/SOV and transaction is writable only
--    after an explicit later grant. This packet does not grant that.
-- 2. CREATE SCHEMA kdb_canonical / kdb_staging / kdb_governance / kdb_ops
--    only when those names are absent. Do not rename or drop canonical/dev_staging.
-- 3. CREATE ROLE kdb_schema_owner / kdb_command_owner / kdb_ingest_runtime
--    only when those names are absent. Leave legacy NOLOGIN kdb_runtime,
--    kdb_ingest_writer, kdb_reviewer untouched.
-- 4. Create the twelve kdb_* tables and three commands from 001-003 only inside
--    the new schemas. Never CREATE TABLE canonical.protocol.
-- 5. Stop. Do not copy, delete, or reinterpret the legacy protocol row.
-- 6. Do not mark publication or n8n activation.

SELECT 'NOT_AUTHORIZED_FOR_APPLY' AS kdb_m01_p2_recovery_candidate;
