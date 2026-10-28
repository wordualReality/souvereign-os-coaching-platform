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
        self.assertIn("python3 tests/kdb/test_sov_proof_consumer_offline.py", WF)
        self.assertIn("python3 tests/kdb/pg17_p5_sql_v2_parity.py", WF)
        self.assertIn("python3 tests/kdb/pg17_p5_signed_ingress_oracles.py", WF)
        self.assertIn("python3 tests/kdb/pg17_p5_sov_proof_consumer_negatives.py", WF)

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
        tests = (ROOT / "tests" / "kdb" / "test_signed_ingress.py").read_text()
        oracles = (ROOT / "tests" / "kdb" / "pg17_p5_signed_ingress_oracles.py").read_text()
        self.assertNotIn("BEGIN PRIVATE", ingress)
        self.assertIn("REVOCATION_PROOF_UNAVAILABLE", ingress)
        self.assertNotIn('b"x" * 32', tests)
        self.assertNotIn("p5-ephemeral-hmac-key-32-bytes!!", oracles)
        self.assertIn("secrets.token_bytes(32)", tests)
        self.assertIn("secrets.token_bytes(32)", oracles)

    def test_trust_denial_is_exact(self):
        oracles = (ROOT / "tests" / "kdb" / "pg17_p5_signed_ingress_oracles.py").read_text()
        classifier = (ROOT / "tests" / "kdb" / "p5_trust_denial.py").read_text()
        self.assertIn("classify_db_fail_closed", oracles)
        self.assertNotIn(
            'and "permission denied" not in result["db_denial"]',
            oracles,
        )
        self.assertIn("GRANT_STRIP_MUTATION", oracles)
        self.assertIn("primary_error_message", classifier)
        self.assertIn("error_messages", classifier)
        self.assertIn("MULTIPLE_PRIMARY_ERRORS", classifier)
        self.assertIn("TRUST_PSQL_RC = 3", classifier)
        self.assertIn("TRANSPORT_OR_FATAL", classifier)
        self.assertIn("WRONG_PSQL_RC", classifier)
        self.assertNotIn(
            'if "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in blob:',
            classifier,
        )

    def test_ci_runs_p5_review_delta_tests(self):
        self.assertIn("python3 tests/kdb/test_digest_v2_unproven.py", WF)
        self.assertIn("python3 tests/kdb/test_p5_trust_denial.py", WF)

    def test_consumer_binds_all_source_intake_claims(self):
        consumer = (ROOT / "services" / "kdb" / "sov_proof_consumer.py").read_text()
        self.assertIn("COMMAND_CLAIM_BINDINGS", consumer)
        self.assertIn('"origin_owner"', consumer)
        self.assertIn('"source_class"', consumer)
        self.assertIn('"external_locator"', consumer)
        self.assertIn('"idempotency_key"', consumer)
        self.assertIn('"submission_id"', consumer)
        self.assertIn("_REPLAY_LOCK", consumer)
        self.assertIn("PROCESS_REPLAY_STORE", consumer)
        self.assertIn('COMMAND_NAME = "SOURCE_INTAKE"', consumer)
        self.assertIn("lone surrogate", consumer)


if __name__ == "__main__":
    unittest.main()
