"""RB02 trust-denial matrix. Exit-code and transport checks are mandatory."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5_trust_denial import (
    CLEAN_PG17,
    CONTEXT_SPOOF,
    DETAIL_SPOOF,
    DUAL_ERROR,
    GRANT_STRIP,
    classify_db_fail_closed,
    error_messages,
    evaluate_rb02_matrix,
    primary_error_message,
)


class TrustDenialClassifier(unittest.TestCase):
    def test_rb02_matrix(self):
        failed = []
        for label, code, sev, exp_code, exp_sev in evaluate_rb02_matrix():
            print("RB02_MATRIX", label, "got", code, sev, "want", exp_code, exp_sev)
            if (code, sev) != (exp_code, exp_sev):
                failed.append((label, (code, sev), (exp_code, exp_sev)))
        self.assertEqual(failed, [])

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
        code, sev = classify_db_fail_closed(psql_rc=3, body=GRANT_STRIP)
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

    def test_second_error_line_is_red(self):
        self.assertEqual(
            error_messages(DUAL_ERROR),
            ["KDB_SECURITY_CONTEXT_NOT_CONFIGURED", "KDB_OTHER_FAILURE"],
        )
        code, sev = classify_db_fail_closed(psql_rc=3, body=DUAL_ERROR)
        self.assertEqual(code, "MULTIPLE_PRIMARY_ERRORS")
        self.assertEqual(sev, "RED")

    def test_clean_pg17_shape_is_one_error_line(self):
        self.assertEqual(error_messages(CLEAN_PG17), ["KDB_SECURITY_CONTEXT_NOT_CONFIGURED"])

    def test_fatal_before_trust_closed(self):
        body = CLEAN_PG17 + "\nFATAL:  terminating connection due to administrator command"
        code, sev = classify_db_fail_closed(psql_rc=3, body=body)
        self.assertEqual(code, "TRANSPORT_OR_FATAL")
        self.assertEqual(sev, "RED")


if __name__ == "__main__":
    unittest.main()
