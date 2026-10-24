"""Static checks for the P3 fail-closed SQL. Not a substitute for PG17 oracles."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "database" / "migrations" / "kdb"
P3 = (SQL_DIR / "20261024190000__kdb_m01_p3__fail_closed_security.sql").read_text()
FLAGS = (ROOT / "contracts" / "kdb" / "activation_flags.json").read_text()


class P3FailClosedStatic(unittest.TestCase):
    def test_no_synthetic_allow(self):
        self.assertNotIn("SYNTHETIC_ALLOW", P3)
        self.assertNotIn("BYPASSRLS", P3.replace("NOBYPASSRLS", ""))
        self.assertIn("KDB_SECURITY_CONTEXT_NOT_CONFIGURED", P3)
        self.assertIn("SELECT false", P3)

    def test_runtime_execute_revoked(self):
        self.assertIn("REVOKE ALL ON FUNCTION kdb_ops.ingest_source", P3)
        self.assertIn("kdb_ingest_runtime", P3)
        self.assertNotIn("GRANT EXECUTE ON FUNCTION kdb_ops.ingest_source", P3)

    def test_migrator_defaults(self):
        self.assertIn("CREATE ROLE kdb_migrator NOLOGIN NOBYPASSRLS", P3)
        self.assertIn(
            "ALTER DEFAULT PRIVILEGES FOR ROLE kdb_migrator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC",
            P3,
        )

    def test_hash_binding(self):
        self.assertIn("canonical_command_digest", P3)
        self.assertIn("KDB_HASH_MISMATCH", P3)
        self.assertIn("KDB_IDEMPOTENCY_CONFLICT", P3)

    def test_flags_fail_closed(self):
        self.assertIn("BLOCKED_FAIL_CLOSED_UNTIL_TRUST_ATTESTED", FLAGS)

    def test_no_hosted_target(self):
        self.assertNotIn("zobjpmyccszkabybdmsf", P3.lower())
        self.assertNotIn("CREATE SCHEMA canonical", P3)


if __name__ == "__main__":
    unittest.main()
