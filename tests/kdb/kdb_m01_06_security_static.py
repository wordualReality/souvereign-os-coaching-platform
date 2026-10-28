"""P06 static security checks. Not physical RLS, GRANT, TLS, or PIAC proof."""
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "database" / "migrations" / "kdb"
S1 = (SQL_DIR / "20261023140000__kdb_m01_001__core_foundation.sql").read_text()
S2 = (SQL_DIR / "20261023140100__kdb_m01_002__security_boundary.sql").read_text()
S3 = (SQL_DIR / "20261023140200__kdb_m01_003__api_boundary.sql").read_text()
FLAGS = json.loads((ROOT / "contracts" / "kdb" / "activation_flags.json").read_text())
sys.path.insert(0, str(ROOT / "services" / "kdb"))
from facade import KdbCommandFacade
from piac import PiacVerificationError

TWELVE = [
    "kdb_governance.source",
    "kdb_governance.source_version",
    "kdb_staging.submission",
    "kdb_staging.candidate_revision",
    "kdb_staging.review_work_item",
    "kdb_governance.human_review_decision",
    "kdb_canonical.protocol",
    "kdb_canonical.protocol_version",
    "kdb_canonical.lifecycle_event",
    "kdb_ops.command_receipt",
    "kdb_ops.outbox_event",
    "kdb_ops.audit_event",
]
PROTECTED = [
    "kdb_governance.human_review_decision",
    "kdb_canonical.protocol",
    "kdb_canonical.protocol_version",
    "kdb_canonical.lifecycle_event",
]
FUNCS = (
    "kdb_ops.ingest_source(uuid,uuid,text,text,text,text,text,text,text,jsonb,text,text,text,text,uuid,timestamptz)",
    "kdb_ops.propose_candidate(uuid,text,uuid,uuid,uuid,bigint,text,text,jsonb,jsonb,text,text,uuid)",
    "kdb_ops.request_review_handoff(uuid,text,uuid,text,text,text,uuid)",
)

class P06SecurityStatic(unittest.TestCase):
    def test_s01_roles(self):
        self.assertIn("CREATE ROLE kdb_schema_owner NOLOGIN NOBYPASSRLS;", S2)
        self.assertIn("CREATE ROLE kdb_command_owner NOLOGIN NOBYPASSRLS;", S2)
        self.assertIn("CREATE ROLE kdb_ingest_runtime LOGIN NOBYPASSRLS NOINHERIT;", S2)
        self.assertNotIn("BYPASSRLS;", S2.replace("NOBYPASSRLS", ""))

    def test_s02_private_schema_only(self):
        self.assertNotIn("CREATE SCHEMA canonical;", S1)
        self.assertNotIn("CREATE SCHEMA kdb_api;", S1)
        self.assertNotIn("kdb_audit", S1 + S2 + S3)

    def test_s03_named_force_rls(self):
        for rel in TWELVE:
            self.assertIn(f"ALTER TABLE {rel} ENABLE ROW LEVEL SECURITY;", S2)
            self.assertIn(f"ALTER TABLE {rel} FORCE ROW LEVEL SECURITY;", S2)
        self.assertEqual(12, S2.count("FORCE ROW LEVEL SECURITY;"))

    def test_s03_protected_no_command_owner_grant(self):
        for rel in PROTECTED:
            self.assertNotRegex(
                S2,
                re.compile(rf"(?im)^\s*GRANT\s+.*\bON\s+(TABLE\s+)?{re.escape(rel)}\b.*\bkdb_command_owner\b"),
            )
            self.assertIn(f"REVOKE ALL ON TABLE {rel} FROM", S2)

    def test_s04_three_security_definer(self):
        self.assertEqual(3, len(re.findall(r"(?m)^CREATE FUNCTION kdb_ops\.", S3)))
        self.assertIn("SECURITY DEFINER SET search_path = pg_catalog", S3)
        self.assertIn("SECURITY DEFINER SET search_path=pg_catalog", S3)
        self.assertEqual(3, S3.count("IF session_user <> 'kdb_ingest_runtime'"))
        for fn in FUNCS:
            self.assertIn(f"ALTER FUNCTION {fn} OWNER TO kdb_command_owner;", S3)
            self.assertIn(f"GRANT EXECUTE ON FUNCTION {fn} TO kdb_ingest_runtime;", S3)
            self.assertIn(
                f"REVOKE EXECUTE ON FUNCTION {fn} FROM PUBLIC, anon, authenticated, service_role;",
                S3,
            )

    def test_s04_no_public_or_service_role_grant(self):
        joined = S2 + "\n" + S3
        code = re.sub(r"(?m)^\s*--.*$", "", joined)
        self.assertNotRegex(code, re.compile(r"(?im)^\s*GRANT.*?\bTO\s+(?:anon|authenticated|service_role|PUBLIC)\b"))
        self.assertNotRegex(code, re.compile(r"(?im)^\s*ALTER DEFAULT PRIVILEGES FOR ROLE postgres\b"))

    def test_s05_piac_fail_closed_and_guc_not_auth(self):
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle({})
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(
                {
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "tenant_scope=forged",
                    "kdb.tenant_scope": "tenant-a",
                }
            )
        self.assertIn("not authenticated PIAC", S3)
        self.assertIn("BLOCK_DEFAULT_ACL_CREATOR", S2)

    def test_s10_o4_o5_and_protected_writers(self):
        self.assertTrue(FLAGS["o4"].startswith("INACTIVE"))
        self.assertTrue(FLAGS["o5"].startswith("INACTIVE"))
        self.assertEqual(FLAGS["sov_piac_proof_consumer_v1"], "DISABLED_CONTRACT_ONLY")
        self.assertNotIn("INSERT INTO kdb_governance.human_review_decision", S3)
        self.assertNotIn("INSERT INTO kdb_canonical.protocol_version", S3)
        self.assertNotIn("INSERT INTO kdb_canonical.protocol", S3)
        self.assertNotIn("INSERT INTO kdb_canonical.lifecycle_event", S3)

    def test_signatures_unchanged(self):
        self.assertIn(
            "CREATE FUNCTION kdb_ops.ingest_source(\n  p_command_id uuid, p_submission_id uuid, p_tenant_scope text,",
            S3,
        )
        self.assertIn("CREATE FUNCTION kdb_ops.propose_candidate(", S3)
        self.assertIn("CREATE FUNCTION kdb_ops.request_review_handoff(", S3)

if __name__ == "__main__":
    unittest.main()
