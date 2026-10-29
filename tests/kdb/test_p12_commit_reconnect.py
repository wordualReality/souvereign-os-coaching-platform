"""P12 gate tests. Physical PG17 commit/reconnect is pg17_p12_commit_reconnect_replay.py."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p11_evidence_matrix import (  # noqa: E402
    NONPHYSICAL_CANDIDATES_NOT_ASSERTED,
    build_matrix,
)
from pg17_p12_commit_reconnect_replay import (  # noqa: E402
    PACKET,
    is_protected_name,
    reconnect_is_not_restart,
    refuse_hosted_env,
    role_exists_safe,
    validate_identity,
)

FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())


class P12CommitReconnect(unittest.TestCase):
    def test_identity_and_protected_names(self) -> None:
        self.assertEqual(validate_identity("kdb_p12_abcdef012345"), "kdb_p12_abcdef012345")
        with self.assertRaises(SystemExit):
            validate_identity("kdb_m01_disposable")
        self.assertTrue(is_protected_name("kdb_m01_disposable"))
        self.assertTrue(is_protected_name("postgres"))
        self.assertTrue(is_protected_name("kdb-m01-pg17-disposable"))
        self.assertFalse(is_protected_name("kdb_p12_abcdef012345"))

    def test_refuse_hosted_and_non_loopback(self) -> None:
        refuse_hosted_env({"PGHOST": "127.0.0.1"})
        with self.assertRaises(SystemExit):
            refuse_hosted_env({"SUPABASE_URL": "https://example.supabase.co"})
        with self.assertRaises(SystemExit):
            refuse_hosted_env({"DATABASE_URL": "postgres://example"})

    def test_reconnect_label_is_not_restart(self) -> None:
        reconnect_is_not_restart("CONNECTION_REOPENED_VERIFIED", "SERVER_RESTART_NOT_TESTED")
        reconnect_is_not_restart("CONNECTION_REOPENED_VERIFIED", "SERVER_RESTART_VERIFIED")
        with self.assertRaises(SystemExit):
            reconnect_is_not_restart("SERVER_RESTART_VERIFIED", "SERVER_RESTART_VERIFIED")
        with self.assertRaises(SystemExit):
            reconnect_is_not_restart("CONNECTION_REOPENED_VERIFIED", "CONNECTION_REOPENED_VERIFIED")

    def test_role_exists_safe_does_not_rewrite_product_sql_files(self) -> None:
        original = "CREATE ROLE kdb_ingest_runtime LOGIN NOBYPASSRLS NOINHERIT;"
        rewritten = role_exists_safe(original)
        self.assertIn("IF NOT EXISTS", rewritten)
        sql = (
            REPO / "database" / "migrations" / "kdb" / "20261023140100__kdb_m01_002__security_boundary.sql"
        ).read_text()
        self.assertIn("CREATE ROLE kdb_ingest_runtime LOGIN NOBYPASSRLS NOINHERIT;", sql)
        self.assertNotIn("IF NOT EXISTS", sql.split("CREATE ROLE kdb_ingest_runtime")[0][-40:])

    def test_flag_inactive_and_matrix_gap(self) -> None:
        self.assertEqual(
            FLAGS["disposable_pg17_commit_reconnect_replay"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        matrix = build_matrix(
            commit="test-commit",
            environment="unit",
            packet=PACKET,
            restart_replay="SERVER_RESTART_NOT_TESTED",
            restart_replay_next="CI libpq cannot restart the shared GitHub service container",
            run={"slice_pass": True, "denials_pass": True, "zero_ops": True, "tests": ["unit"]},
        )
        self.assertEqual(matrix["packet"], PACKET)
        self.assertEqual(matrix["df_adoption"], "DF-20261029-01")
        self.assertEqual(matrix["physical_sql001_tables"], 12)
        self.assertEqual(matrix["logical_objects_claimed"], "NOT_18_OF_18")
        self.assertEqual(matrix["inventory_source"], "INVENTORY_SOURCE_GAP")
        self.assertEqual(matrix["hosted_verified"], "HOSTED_VERIFIED_NO")
        self.assertEqual(matrix["restart_replay"], "SERVER_RESTART_NOT_TESTED")
        self.assertEqual(matrix["final_authority"], "NOT_ADMITTED")
        self.assertEqual(
            list(NONPHYSICAL_CANDIDATES_NOT_ASSERTED),
            matrix["named_nonphysical_candidates_not_asserted"],
        )
        blob = json.dumps(matrix)
        self.assertNotIn("18/18", blob)
        self.assertNotIn("HOSTED_VERIFIED_YES", blob)
        self.assertNotIn("DB_COMMAND_ADMITTED", blob)


if __name__ == "__main__":
    unittest.main()
