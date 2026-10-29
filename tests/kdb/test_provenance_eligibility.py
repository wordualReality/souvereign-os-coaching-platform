"""P08 offline provenance and review-eligibility tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from facade import KdbCommandFacade  # noqa: E402
from piac import PiacVerificationError  # noqa: E402
from provenance_eligibility import (  # noqa: E402
    CONTRACT_GAPS,
    EligibilityError,
    evaluate_review_eligibility,
)

SQL_001 = (
    REPO / "database" / "migrations" / "kdb" / "20261023140000__kdb_m01_001__core_foundation.sql"
).read_text()
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())

TENANT = "TENANT_SYNTH_A"
SOURCE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
VERSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-222222222222"
NEWER_VERSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-222222222223"
SUBMISSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-333333333333"
OTHER_SUBMISSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-333333333334"
CANDIDATE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-444444444444"
REVISION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-555555555555"
COMMAND_ID = "aaaaaaaa-bbbb-4ccc-8ddd-666666666666"
WORK_ITEM_ID = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
CORRELATION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-888888888888"
CONTENT_SHA = "a" * 64
RIGHTS_SHA = "b" * 64
CANDIDATE_SHA = "c" * 64
REQUEST_SHA = "d" * 64
OTHER_SHA = "e" * 64


def _chain() -> dict:
    return {
        "source": {
            "source_id": SOURCE_ID,
            "tenant_scope": TENANT,
            "source_class": "OWNER_AUTHORED",
            "external_locator": "synthetic://kdb/p08/source",
            "rights_status": "ADMITTED",
            "owner_namespace": "KDB",
        },
        "source_version": {
            "source_version_id": VERSION_ID,
            "source_id": SOURCE_ID,
            "tenant_scope": TENANT,
            "content_sha256": CONTENT_SHA,
            "rights_snapshot": {
                "rights_status": "ADMITTED",
                "rights_basis": "owner-authored-fixture",
                "allowed_purposes": ["KNOWLEDGE_INTAKE"],
            },
            "rights_snapshot_sha256": RIGHTS_SHA,
            "media_type": "text/plain",
            "source_version_no": 1,
            "acquired_at": "2026-10-28T00:00:00Z",
        },
        "submission": {
            "submission_id": SUBMISSION_ID,
            "tenant_scope": TENANT,
            "origin_owner": "KDB",
            "idempotency_key": "p08-eligibility-001",
            "request_sha256": REQUEST_SHA,
            "principal_context_ref": "piac-ref-untrusted-string",
            "access_decision_ref": "access-ref-untrusted-string",
            "purpose": "KNOWLEDGE_INTAKE",
            "source_version_id": VERSION_ID,
            "status": "RECORDED",
        },
        "candidate_revision": {
            "candidate_revision_id": REVISION_ID,
            "candidate_id": CANDIDATE_ID,
            "revision_no": 1,
            "tenant_scope": TENANT,
            "source_version_id": VERSION_ID,
            "submission_id": SUBMISSION_ID,
            "proposal_command_id": COMMAND_ID,
            "content_sha256": CANDIDATE_SHA,
            "evidence_span_refs": [
                {"source_version_id": VERSION_ID, "locator": "bytes:0-31"}
            ],
            "proposal_payload": {"title": "synthetic-candidate"},
            "validation_state": "STRUCTURE_VALIDATED",
            "review_state": "PENDING_REVIEW",
        },
        "review_work_item": {
            "review_work_item_id": WORK_ITEM_ID,
            "candidate_revision_id": REVISION_ID,
            "tenant_scope": TENANT,
            "owner_queue": "KDB_HUMAN_REVIEW",
            "state": "REQUESTED",
            "correlation_id": CORRELATION_ID,
        },
    }


def _deny_code(mutator) -> str:
    chain = _chain()
    mutator(chain)
    try:
        evaluate_review_eligibility(chain)
    except EligibilityError as exc:
        return exc.code
    raise AssertionError("expected EligibilityError")


class ProvenanceEligibility(unittest.TestCase):
    def test_positive_eligibility_only(self) -> None:
        result = evaluate_review_eligibility(_chain())
        self.assertEqual(result.decision, "ELIGIBLE_FOR_REVIEW_HANDOFF")
        self.assertEqual(result.code, "PENDING_REVIEW_HANDOFF_ELIGIBLE")
        self.assertEqual(result.db_write, "NOT_ADMITTED")
        self.assertEqual(result.c04_human_decision, "NOT_WRITTEN")
        self.assertEqual(result.c05_canonical_admission, "NOT_WRITTEN")
        self.assertEqual(tuple(result.contract_gaps), CONTRACT_GAPS)

    def test_facade_still_rejects_eligible_chain(self) -> None:
        chain = _chain()
        evaluate_review_eligibility(chain)
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(
                {
                    "tenant_scope": TENANT,
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "SYNTHETIC_PIAC",
                    "payload": chain,
                }
            )

    def test_missing_rights(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["source"].update(rights_status="PENDING")),
            "MISSING_RIGHTS",
        )
        self.assertEqual(
            _deny_code(lambda c: c["source_version"]["rights_snapshot"].update(rights_status="PENDING")),
            "MISSING_RIGHTS",
        )
        self.assertEqual(
            _deny_code(lambda c: c["source_version"]["rights_snapshot"].update(allowed_purposes=[])),
            "MISSING_RIGHTS",
        )

    def test_wrong_purpose(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["submission"].update(purpose="MODEL_TRAINING")),
            "WRONG_PURPOSE",
        )

    def test_cross_tenant(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(tenant_scope="TENANT_SYNTH_B")),
            "CROSS_TENANT",
        )

    def test_mismatched_content_digest(self) -> None:
        def mutate(chain: dict) -> None:
            other = deepcopy(chain["source_version"])
            other["content_sha256"] = OTHER_SHA
            chain["source_versions"] = [other]

        self.assertEqual(_deny_code(mutate), "MISMATCHED_CONTENT_DIGEST")

    def test_mismatched_rights_digest(self) -> None:
        def mutate(chain: dict) -> None:
            other = deepcopy(chain["source_version"])
            other["rights_snapshot_sha256"] = OTHER_SHA
            chain["source_versions"] = [other]

        self.assertEqual(_deny_code(mutate), "MISMATCHED_RIGHTS_DIGEST")

    def test_absent_source_version_link(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["submission"].pop("source_version_id")),
            "ABSENT_SOURCE_VERSION_LINK",
        )

    def test_wrong_source_version_link(self) -> None:
        self.assertEqual(
            _deny_code(
                lambda c: c["candidate_revision"].update(source_version_id=NEWER_VERSION_ID)
            ),
            "WRONG_SOURCE_VERSION_LINK",
        )

    def test_malformed_span(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(evidence_span_refs=["not-an-object"])),
            "MALFORMED_EVIDENCE_SPAN",
        )
        self.assertEqual(
            _deny_code(
                lambda c: c["candidate_revision"].update(
                    evidence_span_refs=[{"source_version_id": VERSION_ID, "locator": ""}]
                )
            ),
            "MALFORMED_EVIDENCE_SPAN",
        )

    def test_out_of_range_span(self) -> None:
        self.assertEqual(
            _deny_code(
                lambda c: c["candidate_revision"].update(
                    evidence_span_refs=[
                        {
                            "source_version_id": VERSION_ID,
                            "locator": "bytes:9-1",
                            "start": 9,
                            "end": 1,
                        }
                    ]
                )
            ),
            "OUT_OF_RANGE_EVIDENCE_SPAN",
        )

    def test_empty_evidence(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(evidence_span_refs=[])),
            "EMPTY_EVIDENCE",
        )

    def test_stale_version(self) -> None:
        def mutate(chain: dict) -> None:
            newer = deepcopy(chain["source_version"])
            newer["source_version_id"] = NEWER_VERSION_ID
            newer["source_version_no"] = 2
            newer["content_sha256"] = OTHER_SHA
            chain["source_versions"] = [newer]

        self.assertEqual(_deny_code(mutate), "STALE_SOURCE_VERSION")

    def test_revoked_source(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["source"].update(rights_status="REVOKED")),
            "REVOKED_SOURCE",
        )

    def test_duplicate_submission(self) -> None:
        def mutate(chain: dict) -> None:
            other = deepcopy(chain["submission"])
            other["submission_id"] = OTHER_SUBMISSION_ID
            chain["prior_submissions"] = [other]

        self.assertEqual(_deny_code(mutate), "DUPLICATE_SUBMISSION")

    def test_conflicting_submission(self) -> None:
        def mutate(chain: dict) -> None:
            other = deepcopy(chain["submission"])
            other["submission_id"] = OTHER_SUBMISSION_ID
            other["request_sha256"] = OTHER_SHA
            chain["prior_submissions"] = [other]

        self.assertEqual(_deny_code(mutate), "CONFLICTING_SUBMISSION")

    def test_contradictory_reviewer_flag(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(review_state="APPROVED")),
            "CONTRADICTORY_REVIEWER_FLAG",
        )
        self.assertEqual(
            _deny_code(lambda c: c["review_work_item"].update(state="DECIDED")),
            "CONTRADICTORY_REVIEWER_FLAG",
        )
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(auto_approved=True)),
            "UNTRUSTED_CLAIM",
        )

    def test_malicious_untrusted_claim(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["submission"].update(role="kdb_publisher")),
            "UNTRUSTED_CLAIM",
        )
        self.assertEqual(
            _deny_code(lambda c: c.update({"kdb.tenant_scope": TENANT})),
            "UNTRUSTED_CLAIM",
        )

    def test_schema_alignment_matrix(self) -> None:
        for rel in (
            "kdb_governance.source",
            "kdb_governance.source_version",
            "kdb_staging.submission",
            "kdb_staging.candidate_revision",
            "kdb_staging.review_work_item",
        ):
            self.assertIn(f"CREATE TABLE {rel}", SQL_001)
        self.assertIn("CHECK (review_state = 'PENDING_REVIEW')", SQL_001)
        self.assertIn("CHECK (state = 'REQUESTED')", SQL_001)
        self.assertIn("CHECK (rights_status IN ('PENDING','ADMITTED','BLOCKED','REVOKED'))", SQL_001)
        for name in (
            "o1_source_ingest.schema.json",
            "o2_candidate_proposal.schema.json",
            "o3_review_handoff.schema.json",
        ):
            schema = json.loads((REPO / "contracts" / "kdb" / name).read_text())
            self.assertIn("tenant_scope", schema["required"])
        o1 = json.loads((REPO / "contracts" / "kdb" / "o1_source_ingest.schema.json").read_text())
        self.assertEqual(o1["properties"]["payload"]["properties"]["rights"]["properties"]["rights_status"]["const"], "ADMITTED")
        o2 = json.loads((REPO / "contracts" / "kdb" / "o2_candidate_proposal.schema.json").read_text())
        self.assertIn("evidence_spans", o2["properties"]["payload"]["required"])
        o3 = json.loads((REPO / "contracts" / "kdb" / "o3_review_handoff.schema.json").read_text())
        self.assertEqual(o3["properties"]["payload"]["properties"]["review_queue"]["const"], "KDB_HUMAN_REVIEW")
        self.assertNotIn("SemanticDescriptorVersion", SQL_001)
        self.assertNotIn("INSERT INTO kdb_governance.human_review_decision", SQL_001)
        self.assertEqual(FLAGS["provenance_review_eligibility"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")
        self.assertEqual(FLAGS["human_review_decision"], "NO_AUTOMATED_WRITER")
        self.assertEqual(FLAGS["promotion"], "NO_EXECUTABLE_M01_COMMAND")

    def test_contract_gaps_are_explicit(self) -> None:
        self.assertIn(
            "SEMANTIC_DESCRIPTOR_VERSION_PIN_ABSENT_FROM_O1_O2_O3_AND_SQL_001",
            CONTRACT_GAPS,
        )
        self.assertIn("C04_HUMAN_REVIEW_DECISION_HAS_NO_WRITE_API", CONTRACT_GAPS)
        self.assertIn("C05_CANONICAL_ADMISSION_HAS_NO_WRITE_API", CONTRACT_GAPS)


if __name__ == "__main__":
    unittest.main()
