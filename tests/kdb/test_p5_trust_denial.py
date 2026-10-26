"""Exact trust-denial oracle. Secondary-line mentions cannot pass DB_FAIL_CLOSED."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5_trust_denial import classify_db_fail_closed, primary_error_message


CLEAN_PG17 = (
    "ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED\n"
    "CONTEXT:  PL/pgSQL function kdb_ops.ingest_source(uuid,uuid,text,text,text,"
    "text,text,text,text,jsonb,text,text,text,text,uuid,timestamp with time zone) "
    "line 21 at RAISE"
)
DETAIL_SPOOF = (
    "ERROR:  KDB_OTHER_FAILURE\n"
    "DETAIL:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
)
CONTEXT_SPOOF = (
    "ERROR:  KDB_OTHER_FAILURE\n"
    "CONTEXT:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
)


class TrustDenialClassifier(unittest.TestCase):
    def test_exact_pg17_security_context(self):
        self.assertEqual(primary_error_message(CLEAN_PG17), "KDB_SECURITY_CONTEXT_NOT_CONFIGURED")
        code, sev = classify_db_fail_closed(psql_rc=3, body=CLEAN_PG17)
        self.assertEqual(code, "TRUST_FAIL_CLOSED")
        self.assertEqual(sev, "CLOSED")

    def test_detail_only_mention_is_red(self):
        self.assertEqual(primary_error_message(DETAIL_SPOOF), "KDB_OTHER_FAILURE")
        code, sev = classify_db_fail_closed(psql_rc=3, body=DETAIL_SPOOF)
        self.assertEqual(code, "TRUST_DENIAL_UNEXPECTED")
        self.assertEqual(sev, "RED")

    def test_context_only_mention_is_red(self):
        code, sev = classify_db_fail_closed(psql_rc=3, body=CONTEXT_SPOOF)
        self.assertEqual(sev, "RED")
        self.assertNotEqual(code, "TRUST_FAIL_CLOSED")

    def test_unrelated_primary_error_is_red(self):
        code, sev = classify_db_fail_closed(
            psql_rc=3, body="ERROR:  KDB_HASH_MISMATCH\nCONTEXT:  PL/pgSQL function kdb_ops.ingest_source"
        )
        self.assertEqual(sev, "RED")

    def test_permission_denied_is_red(self):
        code, sev = classify_db_fail_closed(
            psql_rc=3, body="ERROR:  permission denied for function ingest_source"
        )
        self.assertEqual(code, "PERMISSION_DENIED_NOT_TRUST")
        self.assertEqual(sev, "RED")

    def test_rc_zero_is_red_even_with_trust_text(self):
        code, sev = classify_db_fail_closed(psql_rc=0, body=CLEAN_PG17)
        self.assertEqual(code, "POSITIVE_INGEST_WITHOUT_TRUST")
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
            _code, sev = classify_db_fail_closed(psql_rc=2, body=body)
            self.assertEqual(sev, "RED", body)

    def test_substring_classifier_would_have_passed_detail_spoof(self):
        self.assertIn("KDB_SECURITY_CONTEXT_NOT_CONFIGURED", DETAIL_SPOOF)
        code, sev = classify_db_fail_closed(psql_rc=3, body=DETAIL_SPOOF)
        self.assertEqual(sev, "RED")
        self.assertNotEqual(code, "TRUST_FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main()
