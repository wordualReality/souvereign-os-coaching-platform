"""Static classifier tests. Unexpected failures must not count as CLOSED."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p4_oracle_classifier import (
    classify_runtime_execute,
    classify_tenant_digest_probe,
    classify_trust_fail_closed,
)


class TenantDigestClassifier(unittest.TestCase):
    def test_hash_mismatch_is_closed(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=1, body="ERROR:  KDB_HASH_MISMATCH"
        )
        self.assertEqual(code, "DIGEST_TENANT_BINDING_VERIFIED")
        self.assertEqual(sev, "CLOSED")

    def test_trust_reject_is_red_for_tenant_probe(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=1, body="ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
        )
        self.assertEqual(code, "DIGEST_TENANT_BINDING_BROKEN")
        self.assertEqual(sev, "RED")

    def test_success_is_red(self):
        code, sev = classify_tenant_digest_probe(psql_rc=0, body='{"ok":true}')
        self.assertEqual(sev, "RED")

    def test_missing_function_is_red(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=1, body='ERROR:  function kdb_ops.ingest_source(...) does not exist'
        )
        self.assertEqual(code, "UNEXPECTED_SQL_OR_CONNECTION")
        self.assertEqual(sev, "RED")

    def test_connection_refused_is_red(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=2,
            body='psql: error: connection to server at "127.0.0.1", port 1 failed: Connection refused',
        )
        self.assertEqual(code, "UNEXPECTED_SQL_OR_CONNECTION")
        self.assertEqual(sev, "RED")

    def test_syntax_error_is_red(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=1, body="ERROR:  syntax error at or near \";\""
        )
        self.assertEqual(code, "UNEXPECTED_SQL_OR_CONNECTION")
        self.assertEqual(sev, "RED")

    def test_unrelated_sql_error_is_red(self):
        code, sev = classify_tenant_digest_probe(
            psql_rc=1, body="ERROR:  division by zero"
        )
        self.assertEqual(code, "UNEXPECTED_SQL_OR_CONNECTION")
        self.assertEqual(sev, "RED")

    def test_trust_claim_separate_from_tenant_claim(self):
        code, sev = classify_trust_fail_closed(
            psql_rc=1, body="ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
        )
        self.assertEqual(code, "TRUST_FAIL_CLOSED")
        self.assertEqual(sev, "CLOSED")
        tenant_code, tenant_sev = classify_tenant_digest_probe(
            psql_rc=1, body="ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
        )
        self.assertEqual(tenant_sev, "RED")
        self.assertNotEqual(tenant_code, code)

    def test_runtime_execute_denied(self):
        code, sev = classify_runtime_execute(
            psql_rc=1, body="ERROR:  permission denied for function ingest_source"
        )
        self.assertEqual(code, "RUNTIME_EXECUTE_DENIED")
        self.assertEqual(sev, "CLOSED")

    def test_runtime_connection_error_is_red(self):
        code, sev = classify_runtime_execute(
            psql_rc=2, body="could not connect to server"
        )
        self.assertEqual(sev, "RED")


if __name__ == "__main__":
    unittest.main()
