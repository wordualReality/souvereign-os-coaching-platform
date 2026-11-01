-- KDB P25 DISPOSABLE-PG17 TEST CANDIDATE ONLY. NEVER AUTO-APPLY.
-- Preconditions: a direct LOGIN session as kdb_p25_creator, not SET ROLE;
-- kdb_p25_target exists and kdb_p25_authorized is the intended test principal.
\set ON_ERROR_STOP on
DO $$
BEGIN
  IF session_user <> 'kdb_p25_creator' OR current_user <> 'kdb_p25_creator' THEN
    RAISE EXCEPTION 'P25_CREATOR_IDENTITY_UNPROVEN';
  END IF;
END $$;

-- Function defaults grant PUBLIC EXECUTE globally. A schema-only REVOKE cannot
-- negate that global default, so the creator must close PUBLIC globally.
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Authorization remains schema-scoped: the intended principal receives future
-- EXECUTE only for functions this proven creator makes in the bounded schema.
ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_p25_target
  GRANT EXECUTE ON FUNCTIONS TO kdb_p25_authorized;
