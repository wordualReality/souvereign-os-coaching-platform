"""Static guardrails for the P25 NON_APPLY creator default-ACL candidate."""
from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANDIDATE = REPO / "tests/kdb/fixtures/p25_creator_default_acl_candidate.sql"
FROZEN = REPO / "database/migrations/kdb/20261023140100__kdb_m01_002__security_boundary.sql"


class P25CreatorDefaultAclCandidate(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = CANDIDATE.read_text()

    def test_candidate_is_explicitly_non_apply_and_direct_login_bound(self) -> None:
        self.assertIn("TEST CANDIDATE ONLY. NEVER AUTO-APPLY", self.sql)
        self.assertIn("session_user <> 'kdb_p25_creator'", self.sql)
        self.assertIn("current_user <> 'kdb_p25_creator'", self.sql)
        self.assertIn("P25_CREATOR_IDENTITY_UNPROVEN", self.sql)

    def test_global_public_revoke_precedes_schema_scoped_authorized_grant(self) -> None:
        revoke = "ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;"
        grant = "ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_p25_target"
        self.assertIn(revoke, self.sql)
        self.assertIn(grant, self.sql)
        self.assertLess(self.sql.index(revoke), self.sql.index(grant))
        self.assertIn("GRANT EXECUTE ON FUNCTIONS TO kdb_p25_authorized", self.sql)

    def test_candidate_never_guesses_hosted_creator_or_mutates_real_roles(self) -> None:
        for forbidden in ("postgres", "service_role;", "zobjpmy", "ujdzah", "ALTER ROLE", "CREATE ROLE"):
            self.assertNotIn(forbidden, self.sql)
        self.assertNotIn("FOR ROLE", self.sql)

    def test_frozen_migration_retains_typed_block(self) -> None:
        frozen = FROZEN.read_text()
        self.assertIn("BLOCK_DEFAULT_ACL_CREATOR", frozen)
        self.assertIn("applying session user is not proven", frozen)
        self.assertIn("ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_ops", frozen)

    def test_candidate_is_outside_auto_applied_migration_root(self) -> None:
        self.assertEqual(CANDIDATE.parent, REPO / "tests/kdb/fixtures")
        self.assertNotIn(CANDIDATE.name, (REPO / ".github/workflows/kdb-m01-pg17.yml").read_text())


if __name__ == "__main__":
    unittest.main()
