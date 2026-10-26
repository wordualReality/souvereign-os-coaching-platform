"""Exact trust-denial oracle. permission denied cannot pass DB_FAIL_CLOSED."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5_trust_denial import classify_db_fail_closed


class TrustDenialClassifier(unittest.TestCase):
    def test_exact_security_context(self):
        code, sev = classify_db_fail_closed(
            psql_rc=3, body="ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
        )
        self.assertEqual(code, "TRUST_FAIL_CLOSED")
        self.assertEqual(sev, "CLOSED")

    def test_permission_denied_is_red(self):
        code, sev = classify_db_fail_closed(
            psql_rc=3, body="ERROR:  permission denied for function ingest_source"
        )
        self.assertEqual(code, "PERMISSION_DENIED_NOT_TRUST")
        self.assertEqual(sev, "RED")

    def test_rc_zero_is_red(self):
        code, sev = classify_db_fail_closed(psql_rc=0, body='{"recorded":true}')
        self.assertEqual(sev, "RED")

    def test_missing_routine_is_red(self):
        code, sev = classify_db_fail_closed(
            psql_rc=3, body="ERROR:  function kdb_ops.ingest_source(...) does not exist"
        )
        self.assertEqual(code, "UNEXPECTED_SQL_OR_CONNECTION")
        self.assertEqual(sev, "RED")

    def test_syntax_and_transport_are_red(self):
        for body in (
            "ERROR:  syntax error at or near \";\"",
            'psql: error: connection to server failed: Connection refused',
        ):
            code, sev = classify_db_fail_closed(psql_rc=2, body=body)
            self.assertEqual(sev, "RED", body)


if __name__ == "__main__":
    unittest.main()
