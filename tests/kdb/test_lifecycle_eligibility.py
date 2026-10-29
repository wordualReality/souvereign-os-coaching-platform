"""P09 offline lifecycle/withdrawal eligibility tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from facade import KdbCommandFacade  # noqa: E402
from lifecycle_eligibility import (  # noqa: E402
    CONTRACT_GAPS,
    DIGEST_PROOF,
    LifecycleError,
    evaluate_lifecycle_read_eligibility,
)
from piac import PiacVerificationError  # noqa: E402
from provenance_eligibility import evaluate_review_eligibility  # noqa: E402

SQL_001 = (
    REPO / "database" / "migrations" / "kdb" / "20261023140000__kdb_m01_001__core_foundation.sql"
).read_text()
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())

TENANT = "TENANT_SYNTH_A"
PROTOCOL_ID = "aaaaaaaa-bbbb-4ccc-8ddd-aaaaaaaaaaa1"
VERSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-aaaaaaaaaaa2"
CANDIDATE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-555555555555"
DECISION_PIN = "aaaaaaaa-bbbb-4ccc-8ddd-aaaaaaaaaaa3"
SOURCE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
SOURCE_VERSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-222222222222"
EVENT_PUB = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb1"
EVENT_WD = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb2"
EVENT_RV = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb3"
EVENT_SS = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb4"
EVENT_PUB2 = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb5"
CONTENT_SHA = "c" * 64
SUBMISSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-333333333333"
COMMAND_ID = "aaaaaaaa-bbbb-4ccc-8ddd-666666666666"
WORK_ITEM_ID = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
CORRELATION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-888888888888"
RIGHTS_SHA = "b" * 64
REQUEST_SHA = "d" * 64


def _event(event_id: str, kind: str, occurred: str, *, prior=None, decision: str | None = None) -> dict:
    return {
        "lifecycle_event_id": event_id,
        "protocol_version_id": VERSION_ID,
        "kind": kind,
        "reason_code": "synthetic-" + kind.lower(),
        "prior_event_id": prior,
        "occurred_at": occurred,
        "recorded_at": occurred,
        "decision_ref": decision or ("decision-" + kind.lower()),
    }


def _chain() -> dict:
    return {
        "protocol": {
            "protocol_id": PROTOCOL_ID,
            "owning_module_ref": "module-synth-a",
            "taxonomy_version_ref": "taxo-v1",
        },
        "protocol_version": {
            "protocol_version_id": VERSION_ID,
            "protocol_id": PROTOCOL_ID,
            "version_no": 1,
            "source_candidate_revision_id": CANDIDATE_ID,
            "human_decision_id": DECISION_PIN,
            "content_sha256": CONTENT_SHA,
            "canonical_snapshot": {"title": "synthetic-protocol"},
            "taxonomy_version_ref": "taxo-v1",
            "published_at": "2026-10-29T10:00:00Z",
        },
        "lifecycle_events": [
            _event(EVENT_PUB, "PUBLISHED", "2026-10-29T10:00:00Z"),
        ],
        "source": {
            "source_id": SOURCE_ID,
            "tenant_scope": TENANT,
            "source_class": "OWNER_AUTHORED",
            "external_locator": "synthetic://kdb/p09/source",
            "rights_status": "ADMITTED",
            "owner_namespace": "KDB",
        },
        "source_version": {
            "source_version_id": SOURCE_VERSION_ID,
            "source_id": SOURCE_ID,
            "tenant_scope": TENANT,
            "content_sha256": "a" * 64,
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
        "candidate_revision": {
            "candidate_revision_id": CANDIDATE_ID,
            "candidate_id": "aaaaaaaa-bbbb-4ccc-8ddd-444444444444",
            "revision_no": 1,
            "tenant_scope": TENANT,
            "source_version_id": SOURCE_VERSION_ID,
            "submission_id": SUBMISSION_ID,
            "proposal_command_id": COMMAND_ID,
            "content_sha256": CONTENT_SHA,
            "evidence_span_refs": [{"source_version_id": SOURCE_VERSION_ID, "locator": "bytes:0-31"}],
            "proposal_payload": {"title": "synthetic-candidate"},
            "validation_state": "STRUCTURE_VALIDATED",
            "review_state": "PENDING_REVIEW",
        },
    }


def _deny_code(mutator) -> str:
    chain = _chain()
    mutator(chain)
    try:
        evaluate_lifecycle_read_eligibility(chain)
    except LifecycleError as exc:
        return exc.code
    raise AssertionError("expected LifecycleError")


class LifecycleEligibility(unittest.TestCase):
    def test_published_only_is_offline_non_executable(self) -> None:
        result = evaluate_lifecycle_read_eligibility(_chain())
        self.assertEqual(result.decision, "READ_ELIGIBLE_OFFLINE_ONLY")
        self.assertFalse(result.executable)
        self.assertEqual(result.execution, "NON_EXECUTABLE")
        self.assertEqual(result.db_write, "NOT_ADMITTED")
        self.assertEqual(result.c04_human_decision, "NOT_WRITTEN")
        self.assertEqual(result.c05_canonical_admission, "NOT_WRITTEN")
        self.assertEqual(result.outbox, "NOT_EMITTED")
        self.assertEqual(result.content_digest_proof, DIGEST_PROOF)
        self.assertEqual(DIGEST_PROOF, "OPAQUE_SHA_UNPROVEN")
        self.assertEqual(tuple(result.contract_gaps), CONTRACT_GAPS)

    def test_facade_still_rejects_read_eligible_chain(self) -> None:
        chain = _chain()
        evaluate_lifecycle_read_eligibility(chain)
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(
                {
                    "tenant_scope": TENANT,
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "SYNTHETIC_PIAC",
                    "payload": chain,
                }
            )

    def test_withdrawal_after_publish(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(EVENT_WD, "WITHDRAWN", "2026-10-29T11:00:00Z", prior=EVENT_PUB)
            )

        self.assertEqual(_deny_code(mutate), "WITHDRAWN")

    def test_withdrawal_before_publish_still_wins(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"] = [
                _event(EVENT_WD, "WITHDRAWN", "2026-10-29T09:00:00Z"),
                _event(EVENT_PUB, "PUBLISHED", "2026-10-29T10:00:00Z", prior=EVENT_WD),
            ]

        self.assertEqual(_deny_code(mutate), "WITHDRAWN")

    def test_conflicting_published(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(
                    EVENT_PUB2,
                    "PUBLISHED",
                    "2026-10-29T11:00:00Z",
                    prior=EVENT_PUB,
                    decision="decision-published-2",
                )
            )

        self.assertEqual(_deny_code(mutate), "CONFLICTING_PUBLISHED")

    def test_revalidation_required(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(EVENT_RV, "REVALIDATION_REQUIRED", "2026-10-29T11:00:00Z", prior=EVENT_PUB)
            )

        self.assertEqual(_deny_code(mutate), "REVALIDATION_REQUIRED")

    def test_superseded(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(EVENT_SS, "SUPERSEDED", "2026-10-29T11:00:00Z", prior=EVENT_PUB)
            )

        self.assertEqual(_deny_code(mutate), "SUPERSEDED")

    def test_revoked_source_wins(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["source"].update(rights_status="REVOKED")),
            "REVOKED_SOURCE",
        )

    def test_unknown_source(self) -> None:
        self.assertEqual(_deny_code(lambda c: c.pop("source")), "UNKNOWN_SOURCE")

    def test_source_rights_not_admitted(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["source"].update(rights_status="PENDING")),
            "SOURCE_RIGHTS_NOT_ADMITTED",
        )

    def test_missing_prior_event(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(
                    EVENT_WD,
                    "WITHDRAWN",
                    "2026-10-29T11:00:00Z",
                    prior="aaaaaaaa-bbbb-4ccc-8ddd-ffffffffffff",
                )
            )

        self.assertEqual(_deny_code(mutate), "MISSING_PRIOR_EVENT")

    def test_ambiguous_clock_order(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(EVENT_WD, "WITHDRAWN", "2026-10-29T10:00:00Z", prior=EVENT_PUB)
            )

        self.assertEqual(_deny_code(mutate), "INDETERMINATE_EVENT_ORDER")

    def test_concurrent_published_roots(self) -> None:
        def mutate(chain: dict) -> None:
            chain["lifecycle_events"].append(
                _event(
                    EVENT_PUB2,
                    "PUBLISHED",
                    "2026-10-29T10:01:00Z",
                    decision="decision-published-2",
                )
            )

        self.assertEqual(_deny_code(mutate), "INDETERMINATE_EVENT_ORDER")

    def test_cross_tenant(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["candidate_revision"].update(tenant_scope="TENANT_SYNTH_B")),
            "CROSS_TENANT",
        )

    def test_wrong_protocol_version(self) -> None:
        self.assertEqual(
            _deny_code(
                lambda c: c["lifecycle_events"][0].update(
                    protocol_version_id="aaaaaaaa-bbbb-4ccc-8ddd-aaaaaaaaaaa9"
                )
            ),
            "WRONG_PROTOCOL_VERSION",
        )

    def test_duplicate_event(self) -> None:
        def mutate(chain: dict) -> None:
            dup = deepcopy(chain["lifecycle_events"][0])
            chain["lifecycle_events"].append(dup)

        self.assertEqual(_deny_code(mutate), "DUPLICATE_EVENT")

    def test_missing_provenance(self) -> None:
        self.assertEqual(_deny_code(lambda c: c.pop("candidate_revision")), "MISSING_PROVENANCE")

    def test_malicious_publisher_allow(self) -> None:
        self.assertEqual(
            _deny_code(lambda c: c["protocol_version"].update(auto_publish=True)),
            "UNTRUSTED_CLAIM",
        )
        self.assertEqual(
            _deny_code(lambda c: c.update(publisher="kdb_publisher")),
            "UNTRUSTED_CLAIM",
        )

    def test_tampered_snapshot_opaque_sha_is_not_independent_proof(self) -> None:
        chain = _chain()
        chain["protocol_version"]["canonical_snapshot"] = {"title": "tampered"}
        result = evaluate_lifecycle_read_eligibility(chain)
        self.assertEqual(result.content_digest_proof, "OPAQUE_SHA_UNPROVEN")
        self.assertFalse(result.executable)
        p08 = {
            "source": chain["source"],
            "source_version": chain["source_version"],
            "submission": {
                "submission_id": SUBMISSION_ID,
                "tenant_scope": TENANT,
                "origin_owner": "KDB",
                "idempotency_key": "p09-digest-limit-001",
                "request_sha256": REQUEST_SHA,
                "principal_context_ref": "piac-ref-untrusted-string",
                "access_decision_ref": "access-ref-untrusted-string",
                "purpose": "KNOWLEDGE_INTAKE",
                "source_version_id": SOURCE_VERSION_ID,
                "status": "RECORDED",
            },
            "candidate_revision": chain["candidate_revision"],
            "review_work_item": {
                "review_work_item_id": WORK_ITEM_ID,
                "candidate_revision_id": CANDIDATE_ID,
                "tenant_scope": TENANT,
                "owner_queue": "KDB_HUMAN_REVIEW",
                "state": "REQUESTED",
                "correlation_id": CORRELATION_ID,
            },
        }
        other = deepcopy(p08["source_version"])
        other["rights_snapshot"] = {"rights_status": "ADMITTED", "rights_basis": "tampered", "allowed_purposes": ["KNOWLEDGE_INTAKE"]}
        p08["source_versions"] = [other]
        eligible = evaluate_review_eligibility(p08)
        self.assertEqual(eligible.decision, "ELIGIBLE_FOR_REVIEW_HANDOFF")
        self.assertEqual(eligible.db_write, "NOT_ADMITTED")

    def test_schema_alignment_and_flags(self) -> None:
        self.assertIn("kind text NOT NULL CHECK (kind IN ('PUBLISHED','REVALIDATION_REQUIRED','WITHDRAWN','SUPERSEDED'))", SQL_001)
        self.assertIn("CREATE TABLE kdb_canonical.lifecycle_event", SQL_001)
        self.assertIn("CREATE TABLE kdb_canonical.protocol_version", SQL_001)
        self.assertIn("publish_state text NOT NULL DEFAULT 'INACTIVE_M01' CHECK (publish_state = 'INACTIVE_M01')", SQL_001)
        self.assertNotIn("tenant_scope", SQL_001.split("CREATE TABLE kdb_canonical.lifecycle_event", 1)[1].split("CREATE TABLE", 1)[0])
        self.assertEqual(FLAGS["lifecycle_read_eligibility"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")
        self.assertTrue(FLAGS["o4"].startswith("INACTIVE"))
        self.assertTrue(FLAGS["o5"].startswith("INACTIVE"))
        self.assertEqual(FLAGS["outbox_dispatch"], "INACTIVE_M01")
        self.assertIn("TRUSTED_EVENT_WATERMARK_ABSENT", CONTRACT_GAPS)
        self.assertIn("CONTENT_SHA_OPAQUE_NOT_RECOMPUTED", CONTRACT_GAPS)


if __name__ == "__main__":
    unittest.main()
