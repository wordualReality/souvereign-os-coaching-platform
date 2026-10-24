"""Static checks for the P4 digest SQL. Not a substitute for PG17 oracles."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "database" / "migrations" / "kdb"
P4 = (SQL_DIR / "20261024220000__kdb_m01_p4__digest_oracle_integrity.sql").read_text()
CONTRACT = (ROOT / "contracts" / "kdb" / "canonical_command_digest.md").read_text()


class P4DigestStatic(unittest.TestCase):
    def test_v2_array_digest(self):
        self.assertIn("canonical_digest_v2", P4)
        self.assertIn("jsonb_build_array", P4)
        self.assertIn("CANONICAL_DIGEST_CONTRACT_UNRESOLVED", P4)

    def test_o2_evidence_spans(self):
        self.assertIn("v_spans_digest", P4)
        self.assertIn("p_evidence_spans", P4)

    def test_trust_helper_consulted_and_unconditional_deny(self):
        self.assertGreaterEqual(P4.count("security_context_ready()"), 3)
        self.assertGreaterEqual(P4.count("KDB_SECURITY_CONTEXT_NOT_CONFIGURED"), 6)

    def test_no_synthetic_allow(self):
        self.assertNotIn("SYNTHETIC_ALLOW", P4)
        self.assertNotIn("BYPASSRLS", P4.replace("NOBYPASSRLS", ""))

    def test_contract_delta(self):
        self.assertIn("v2", CONTRACT)
        self.assertIn("evidence_spans_digest", CONTRACT)
        self.assertIn("Arcava", CONTRACT)

    def test_no_hosted_target(self):
        self.assertNotIn("zobjpmyccszkabybdmsf", P4.lower())
        self.assertNotIn("CREATE SCHEMA canonical", P4)


if __name__ == "__main__":
    unittest.main()
