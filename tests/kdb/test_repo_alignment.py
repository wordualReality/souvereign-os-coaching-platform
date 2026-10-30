"""Repo-path alignment checks. Not a substitute for the original 32 kit tests."""
import json, pathlib, re, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "database" / "migrations" / "kdb"
S1 = (SQL_DIR / "20261023140000__kdb_m01_001__core_foundation.sql").read_text()
S2 = (SQL_DIR / "20261023140100__kdb_m01_002__security_boundary.sql").read_text()
S3 = (SQL_DIR / "20261023140200__kdb_m01_003__api_boundary.sql").read_text()
S4 = (SQL_DIR / "20261023140300__kdb_m01_004__indexes_idempotency.sql").read_text()
FLAGS = json.loads((ROOT / "contracts" / "kdb" / "activation_flags.json").read_text())
class RepoAlignment(unittest.TestCase):
    def test_schemas(self):
        for name in ("kdb_canonical", "kdb_staging", "kdb_governance", "kdb_ops"):
            self.assertIn("CREATE SCHEMA " + name + ";", S1)
        self.assertNotIn("CREATE SCHEMA canonical;", S1)
        self.assertNotIn("CREATE SCHEMA kdb_api;", S1)
        self.assertNotIn("CREATE SCHEMA kdb_audit;", S1)
    def test_no_legacy_ddl(self):
        sql = S1 + "\n" + S2 + "\n" + S3
        self.assertNotRegex(sql, re.compile(r"(?im)^\s*(?:alter|drop|truncate|insert|update|delete)\s+(?:table\s+)?(?:canonical|dev_staging|public)\."))
        self.assertNotRegex(sql, re.compile(r"(?im)^\s*(?:create|alter|drop)\s+schema\s+(?:canonical|dev_staging|public)\b"))
    def test_twelve_tables(self):
        self.assertEqual(12, len(re.findall(r"(?m)^CREATE TABLE\s+", S1)))
    def test_004_dormant(self):
        self.assertIn("NOT_AUTHORIZED_FOR_APPLY", S4)
        self.assertNotIn("CREATE TABLE", S4.upper().replace("NOT_AUTHORIZED_FOR_APPLY",""))
        self.assertNotRegex(S4, re.compile(r"(?im)^\s*create\s+table\b"))
        self.assertNotRegex(S4, re.compile(r"(?im)^\s*create\s+index\b"))
    def test_o4_o5_inactive(self):
        self.assertTrue(FLAGS["o4"].startswith("INACTIVE"))
        self.assertTrue(FLAGS["o5"].startswith("INACTIVE"))
        self.assertEqual(
            FLAGS["disposable_pg17_source_review_readback"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["disposable_pg17_commit_reconnect_replay"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_handoff_preview"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_inbox_readmodel"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_case_detail"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
    def test_no_human_review_writer(self):
        self.assertNotIn("INSERT INTO kdb_governance.human_review_decision", S3)
        self.assertNotIn("INSERT INTO kdb_canonical.protocol_version", S3)
if __name__ == "__main__":
    unittest.main()
