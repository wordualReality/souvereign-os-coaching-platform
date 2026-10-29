"""P11 mapper and gate tests. Physical PG17 readback is pg17_p11_source_review_readback.py."""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_diagnostic import diagnose  # noqa: E402
from p11_evidence_matrix import (  # noqa: E402
    NONPHYSICAL_CANDIDATES_NOT_ASSERTED,
    build_matrix,
    verify_contract_mappings,
)
from p11_snapshot_map import (  # noqa: E402
    REDACT_SUBSTRINGS,
    assert_redacted,
    diagnostic_payload,
    id_digest,
    map_candidate_chain,
    map_without_work_item,
)
from provenance_eligibility import EligibilityError, evaluate_review_eligibility  # noqa: E402

SQL_DIR = REPO / "database" / "migrations" / "kdb"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
LIFECYCLE = json.loads(
    (REPO / "tests" / "kdb" / "fixtures" / "p11_synthetic_lifecycle.json").read_text()
)
SNAPSHOT = {
    "source": {
        "source_id": "11111111-1111-4111-8111-111111111111",
        "tenant_scope": "TENANT_SYNTH_A",
        "source_class": "OWNER_AUTHORED",
        "external_locator": "synthetic://kdb/p11/source",
        "rights_status": "ADMITTED",
        "owner_namespace": "KDB",
        "created_at": "2026-10-28T00:00:00+00:00",
    },
    "source_version": {
        "source_version_id": "22222222-2222-4222-8222-222222222222",
        "source_id": "11111111-1111-4111-8111-111111111111",
        "tenant_scope": "TENANT_SYNTH_A",
        "content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "rights_snapshot": {
            "rights_status": "ADMITTED",
            "rights_basis": "owner-authored-fixture",
            "allowed_purposes": ["KNOWLEDGE_INTAKE"],
        },
        "rights_snapshot_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "media_type": "text/plain",
        "source_version_no": 1,
        "acquired_at": "2026-10-28T00:00:00+00:00",
        "created_at": "2026-10-28T00:00:00+00:00",
    },
    "submission": {
        "submission_id": "33333333-3333-4333-8333-333333333333",
        "tenant_scope": "TENANT_SYNTH_A",
        "origin_owner": "KDB",
        "idempotency_key": "p11-readback-001",
        "request_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        "principal_context_ref": "piac-ref-untrusted-string",
        "access_decision_ref": "access-ref-untrusted-string",
        "purpose": "KNOWLEDGE_INTAKE",
        "source_version_id": "22222222-2222-4222-8222-222222222222",
        "status": "RECORDED",
        "created_at": "2026-10-28T00:00:00+00:00",
    },
    "candidate_revision": {
        "candidate_revision_id": "55555555-5555-4555-8555-555555555555",
        "candidate_id": "44444444-4444-4444-8444-444444444444",
        "revision_no": 1,
        "tenant_scope": "TENANT_SYNTH_A",
        "source_version_id": "22222222-2222-4222-8222-222222222222",
        "submission_id": "33333333-3333-4333-8333-333333333333",
        "proposal_command_id": "66666666-6666-4666-8666-666666666666",
        "content_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "evidence_span_refs": [
            {
                "source_version_id": "22222222-2222-4222-8222-222222222222",
                "locator": "bytes:0-31",
            }
        ],
        "proposal_payload": {"title": "synthetic-candidate"},
        "validation_state": "STRUCTURE_VALIDATED",
        "review_state": "PENDING_REVIEW",
        "created_at": "2026-10-28T00:00:00+00:00",
    },
    "review_work_item": {
        "review_work_item_id": "77777777-7777-4777-8777-777777777777",
        "candidate_revision_id": "55555555-5555-4555-8555-555555555555",
        "tenant_scope": "TENANT_SYNTH_A",
        "owner_queue": "KDB_HUMAN_REVIEW",
        "state": "REQUESTED",
        "correlation_id": "88888888-8888-4888-8888-888888888888",
        "created_at": "2026-10-28T00:00:00+00:00",
    },
    "orphan_candidate": {
        "candidate_revision_id": "55555555-5555-4555-8555-555555555556",
        "candidate_id": "44444444-4444-4444-8444-444444444445",
        "revision_no": 1,
        "tenant_scope": "TENANT_SYNTH_A",
        "source_version_id": "22222222-2222-4222-8222-222222222222",
        "submission_id": "33333333-3333-4333-8333-333333333333",
        "proposal_command_id": "66666666-6666-4666-8666-666666666667",
        "content_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "evidence_span_refs": [
            {
                "source_version_id": "22222222-2222-4222-8222-222222222222",
                "locator": "bytes:0-31",
            }
        ],
        "proposal_payload": {"title": "synthetic-candidate"},
        "validation_state": "STRUCTURE_VALIDATED",
        "review_state": "PENDING_REVIEW",
    },
}


class P11SnapshotMap(unittest.TestCase):
    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["disposable_pg17_source_review_readback"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )

    def test_no_new_sql_migration(self) -> None:
        names = sorted(path.name for path in SQL_DIR.glob("*.sql"))
        self.assertIn("20261023140000__kdb_m01_001__core_foundation.sql", names)
        self.assertNotIn("20261029", "".join(names))
        self.assertFalse(any("p11" in name.lower() for name in names))

    def test_mapped_chain_is_p08_eligible_and_p10_not_admitted(self) -> None:
        chain = map_candidate_chain(SNAPSHOT)
        result = evaluate_review_eligibility(chain)
        self.assertEqual(result.code, "PENDING_REVIEW_HANDOFF_ELIGIBLE")
        payload = diagnostic_payload(
            case_id="P11-SYNTH-PG17-READBACK",
            expected_tenant_scope="TENANT_SYNTH_A",
            candidate_chain=chain,
            lifecycle_chain=LIFECYCLE,
        )
        original = deepcopy(payload)
        receipt = diagnose(payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["execution"], "NON_EXECUTABLE")
        self.assertEqual(receipt["c04_human_decision"], "NOT_WRITTEN")
        self.assertEqual(receipt["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(receipt["stages"]["c04_c05_transition"]["status"], "ABSENT")
        self.assertEqual(receipt["stages"]["lifecycle"]["status"], "STAGE_LOCAL_ELIGIBLE")
        blob = json.dumps(receipt)
        for token in REDACT_SUBSTRINGS:
            self.assertNotIn(token, blob)

    def test_missing_review_work_item_denied(self) -> None:
        chain = map_without_work_item(SNAPSHOT)
        with self.assertRaises(EligibilityError) as caught:
            evaluate_review_eligibility(chain)
        self.assertEqual(caught.exception.code, "MISSING_REVIEW_WORK_ITEM")

    def test_revoked_and_pending_denied(self) -> None:
        revoked = map_candidate_chain(SNAPSHOT)
        revoked["source"]["rights_status"] = "REVOKED"
        with self.assertRaises(EligibilityError) as caught:
            evaluate_review_eligibility(revoked)
        self.assertEqual(caught.exception.code, "REVOKED_SOURCE")
        pending = map_candidate_chain(SNAPSHOT)
        pending["source"]["rights_status"] = "PENDING"
        with self.assertRaises(EligibilityError) as caught:
            evaluate_review_eligibility(pending)
        self.assertEqual(caught.exception.code, "MISSING_RIGHTS")

    def test_id_digest_stable_and_redacted(self) -> None:
        digest = id_digest(SNAPSHOT)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, id_digest(SNAPSHOT))
        assert_redacted(digest)
        with self.assertRaises(AssertionError):
            assert_redacted("synthetic://kdb/p11/source")

    def test_lifecycle_fixture_is_not_a_sql_insert(self) -> None:
        sql = (SQL_DIR / "20261023140200__kdb_m01_003__api_boundary.sql").read_text()
        self.assertNotIn("INSERT INTO kdb_canonical.protocol_version", sql)
        self.assertNotIn("INSERT INTO kdb_governance.human_review_decision", sql)
        self.assertEqual(
            LIFECYCLE["protocol_version"]["source_candidate_revision_id"],
            SNAPSHOT["candidate_revision"]["candidate_revision_id"],
        )

    def test_contract_mappings_bound_without_locator_leak(self) -> None:
        mapped = verify_contract_mappings(SNAPSHOT)
        self.assertEqual(len(mapped), 10)
        self.assertTrue(all(item["status"] == "BOUND" for item in mapped))
        blob = json.dumps(mapped)
        self.assertNotIn("synthetic://", blob)

    def test_df_matrix_twelve_physical_not_eighteen(self) -> None:
        matrix = build_matrix(
            commit="test-commit",
            environment="unit",
            run={
                "slice_pass": True,
                "denials_pass": True,
                "zero_ops": True,
                "tests": ["unit"],
                "contract_mappings": verify_contract_mappings(SNAPSHOT),
                "cardinality": {"source_version_per_source": 2, "candidates_per_bound_version": 3},
            },
        )
        self.assertEqual(matrix["df_adoption"], "DF-20261029-01")
        self.assertEqual(matrix["physical_sql001_tables"], 12)
        self.assertEqual(len(matrix["objects"]), 12)
        self.assertEqual(matrix["logical_objects_claimed"], "NOT_18_OF_18")
        self.assertEqual(matrix["inventory_source"], "INVENTORY_SOURCE_GAP")
        self.assertEqual(matrix["hosted_verified"], "HOSTED_VERIFIED_NO")
        self.assertEqual(matrix["restart_replay"], "NOT_TESTED")
        self.assertEqual(matrix["final_authority"], "NOT_ADMITTED")
        self.assertEqual(
            list(NONPHYSICAL_CANDIDATES_NOT_ASSERTED),
            matrix["named_nonphysical_candidates_not_asserted"],
        )
        blob = json.dumps(matrix)
        self.assertNotIn("18/18", blob)
        self.assertNotIn("HOSTED_VERIFIED_YES", blob)
        self.assertNotIn("synthetic://", blob)
        self.assertNotIn("DB_COMMAND_ADMITTED", blob)
        for row in matrix["objects"]:
            self.assertEqual(row["hosted_verified"], "HOSTED_VERIFIED_NO")
            self.assertEqual(row["owner"], "KDB")


if __name__ == "__main__":
    unittest.main()
