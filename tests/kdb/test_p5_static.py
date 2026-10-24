"""Static checks for P5 producer parity and signed ingress. Not PG17 proof."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = (ROOT / ".github" / "workflows" / "kdb-m01-pg17.yml").read_text()
P3 = (ROOT / "tests" / "kdb" / "pg17_p3_security_oracles.py").read_text()
CONTRACT = (ROOT / "contracts" / "kdb" / "canonical_command_digest.md").read_text()


class P5Static(unittest.TestCase):
    def test_ci_runs_p4_and_p5_static(self):
        self.assertIn("python3 tests/kdb/test_p4_digest_static.py", WF)
        self.assertIn("python3 tests/kdb/test_p5_static.py", WF)
        self.assertIn("python3 tests/kdb/test_signed_ingress.py", WF)
        self.assertIn("python3 tests/kdb/pg17_p5_sql_v2_parity.py", WF)
        self.assertIn("python3 tests/kdb/pg17_p5_signed_ingress_oracles.py", WF)

    def test_tenant_spoof_requires_hash_mismatch(self):
        self.assertIn('elif "KDB_HASH_MISMATCH" in body_spoof:', P3)
        self.assertNotIn(
            'elif "KDB_HASH_MISMATCH" in body_spoof or "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in body_spoof:',
            P3,
        )

    def test_contract_names_adapter(self):
        self.assertIn("digest_v2.py", CONTRACT)
        self.assertIn("LOCAL_SIGNED_INGRESS_VERIFIED", CONTRACT)

    def test_no_checked_in_hmac_secret(self):
        ingress = (ROOT / "services" / "kdb" / "signed_ingress.py").read_text()
        self.assertNotIn("BEGIN PRIVATE", ingress)
        self.assertIn("REVOCATION_PROOF_UNAVAILABLE", ingress)


if __name__ == "__main__":
    unittest.main()
