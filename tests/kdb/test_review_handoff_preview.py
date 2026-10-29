"""P13 offline review-handoff preview tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from review_handoff_preview import (  # noqa: E402
    PACKET,
    PreviewParseError,
    preview,
    preview_file,
)

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p13_preview_eligible.json"
CLI = REPO / "services" / "kdb" / "review_handoff_preview_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


class ReviewHandoffPreview(unittest.TestCase):
    def test_eligible_preview_only_still_not_admitted(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = preview(payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["preview_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["review_queue"], "KDB_HUMAN_REVIEW")
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["publication"], "NOT_PUBLISHED")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["execution"], "NON_EXECUTABLE")
        self.assertEqual(receipt["db_write"], "NOT_ADMITTED")
        self.assertEqual(receipt["c04_human_decision"], "NOT_WRITTEN")
        self.assertEqual(receipt["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(receipt["outbox"], "NOT_EMITTED")
        self.assertEqual(receipt["logical_objects_claimed"], "NOT_18_OF_18")
        self.assertEqual(receipt["inventory_source"], "UNCONFIRMED_ATC10_CANDIDATES")
        self.assertEqual(receipt["hosted_verified"], "HOSTED_VERIFIED_NO")
        card = receipt["queue_card"]
        self.assertEqual(card["review_queue"], "KDB_HUMAN_REVIEW")
        self.assertEqual(card["work_item_state"], "REQUESTED")
        self.assertEqual(card["evidence_span_count"], 1)
        self.assertNotIn("external_locator", card)
        self.assertNotIn("proposal_payload", card)
        blob = json.dumps(receipt)
        self.assertNotIn("synthetic://", blob)
        self.assertNotIn("synthetic-candidate", blob)
        self.assertNotIn("KNOWLEDGE_INTAKE", blob)
        self.assertNotIn("ALLOW", blob)
        self.assertNotIn("DB_COMMAND_ADMITTED", blob)
        self.assertNotIn("18/18", blob)

    def test_cli_redacted(self) -> None:
        proc = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["preview_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["source_commit"], "cli-test")
        self.assertNotIn("synthetic://", proc.stdout)
        self.assertNotIn("KNOWLEDGE_INTAKE", proc.stdout)

    def test_revoked_and_pending_deny_preview(self) -> None:
        revoked = _load()
        revoked["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = preview(revoked)
        self.assertEqual(receipt["preview_status"], "PREVIEW_DENIED")
        self.assertEqual(receipt["deny_code"], "REVOKED_SOURCE")
        self.assertIsNone(receipt["queue_card"])
        self.assertEqual(receipt["review_queue"], "NOT_QUEUED")
        pending = _load()
        pending["candidate_chain"]["source"]["rights_status"] = "PENDING"
        receipt = preview(pending)
        self.assertEqual(receipt["deny_code"], "MISSING_RIGHTS")
        self.assertIsNone(receipt["queue_card"])

    def test_stale_version_denies_preview(self) -> None:
        payload = _load()
        extra = deepcopy(payload["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222223"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        payload["candidate_chain"]["source_versions"] = [extra]
        receipt = preview(payload)
        self.assertEqual(receipt["preview_status"], "PREVIEW_DENIED")
        self.assertEqual(receipt["deny_code"], "STALE_SOURCE_VERSION")
        self.assertIsNone(receipt["queue_card"])

    def test_cross_tenant_empty_evidence_and_forged_reviewer(self) -> None:
        cross = _load()
        cross["candidate_chain"]["source_version"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = preview(cross)
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        empty = _load()
        empty["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        receipt = preview(empty)
        self.assertEqual(receipt["deny_code"], "EMPTY_EVIDENCE")
        forged = _load()
        forged["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        receipt = preview(forged)
        self.assertEqual(receipt["deny_code"], "FORGED_REVIEWER_CLAIM")
        self.assertIsNone(receipt["queue_card"])

    def test_network_path_denied(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            preview_file("https://example.invalid/preview.json")
        self.assertEqual(caught.exception.code, "NETWORK_PATH_DENIED")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_handoff_preview"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
