"""P22 optional current-case evidence demo tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_demo_pack import (  # noqa: E402
    EVIDENCE_FILE,
    EVIDENCE_FILES,
    EVIDENCE_PACKET,
    FIXED_FILES,
    demo_pack,
    demo_pack_with_evidence,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests/kdb/fixtures/p20_inbox_byte_spans.json"
SOURCE_A = REPO / "tests/kdb/fixtures/p20_source_a.bin"
SOURCE_B = REPO / "tests/kdb/fixtures/p20_source_b.bin"
CLI = REPO / "services/kdb/offline_review_demo_pack_cli.py"
FLAGS = json.loads((REPO / "contracts/kdb/activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"


def load() -> dict:
    return json.loads(FIXTURE.read_text())


class OfflineCurrentCaseEvidenceDemo(unittest.TestCase):
    def test_opt_in_adds_redacted_linked_deterministic_evidence(self) -> None:
        payload = load()
        standard = demo_pack(payload, deepcopy(payload), commit="p22-test")
        enriched = demo_pack_with_evidence(
            payload, deepcopy(payload), WORK_A, SOURCE_A.read_bytes(), commit="p22-test"
        )
        self.assertEqual(set(standard["artifacts"]), set(FIXED_FILES))
        self.assertEqual(set(enriched["artifacts"]), set(EVIDENCE_FILES))
        self.assertEqual(enriched["packet"], EVIDENCE_PACKET)
        self.assertEqual(enriched["manifest"]["evidence_mode"], "EXPLICIT_OPT_IN")
        self.assertIn(f'href="{EVIDENCE_FILE}"', enriched["artifacts"]["index.html"])
        self.assertIn(f'href="{EVIDENCE_FILE}"', enriched["artifacts"]["current.html"])
        evidence = json.loads(enriched["artifacts"][EVIDENCE_FILE])
        self.assertEqual(evidence["review_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        self.assertEqual(evidence["evidence_spans"][0]["byte_start"], 0)
        self.assertNotIn("integrated_preview", evidence)
        model = json.loads(enriched["artifacts"]["review-viewmodel.json"])
        selected = [case for case in model["current_cases"] if case["review_work_item_id"] == WORK_A]
        self.assertEqual(selected[0]["evidence_bound_review"]["status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        for name, digest in enriched["manifest"]["files"].items():
            self.assertEqual(hashlib.sha256(enriched["artifacts"][name].encode()).hexdigest(), digest)
        blob = json.dumps(enriched, sort_keys=True)
        self.assertNotIn("p20_source_a.bin", blob)
        self.assertNotIn("synthetic://", blob)
        self.assertEqual(
            enriched,
            demo_pack_with_evidence(payload, deepcopy(payload), WORK_A, SOURCE_A.read_bytes(), commit="p22-test"),
        )

    def test_default_six_file_pack_is_unchanged_by_opt_in_feature(self) -> None:
        payload = load()
        before = demo_pack(payload, deepcopy(payload), commit="p22-default")
        demo_pack_with_evidence(payload, deepcopy(payload), WORK_A, SOURCE_A.read_bytes(), commit="p22-default")
        after = demo_pack(payload, deepcopy(payload), commit="p22-default")
        self.assertEqual(before, after)
        self.assertEqual(tuple(before["artifacts"]), ("index.html", "current.html", "changes.html", "review-viewmodel.json", "README.txt", "manifest.json"))

    def test_tamper_revocation_and_overlap_fail_closed(self) -> None:
        with self.assertRaises(PreviewParseError) as tampered:
            demo_pack_with_evidence(load(), load(), WORK_A, SOURCE_B.read_bytes(), commit="p22-test")
        self.assertEqual(tampered.exception.code, "LOCAL_CONTENT_SHA_MISMATCH")
        revoked = load()
        revoked["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        with self.assertRaises(PreviewParseError):
            demo_pack_with_evidence(revoked, revoked, WORK_A, SOURCE_A.read_bytes(), commit="p22-test")
        overlap = load()
        spans = overlap["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"]
        spans[0].update({"locator": "bytes:0-15", "start": 0, "end": 16})
        spans.append({"source_version_id": spans[0]["source_version_id"], "locator": "bytes:8-31", "start": 8, "end": 32})
        with self.assertRaises(PreviewParseError) as overlapping:
            demo_pack_with_evidence(overlap, overlap, WORK_A, SOURCE_A.read_bytes(), commit="p22-test")
        self.assertEqual(overlapping.exception.code, "OVERLAPPING_EVIDENCE_SPAN")

    def test_cli_requires_complete_explicit_opt_in_and_hides_path(self) -> None:
        incomplete = subprocess.run(
            ["python3", str(CLI), str(FIXTURE), str(FIXTURE), "--work-item-id", WORK_A],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(incomplete.returncode, 2)
        self.assertEqual(json.loads(incomplete.stdout)["parse_error"], "INCOMPLETE_EVIDENCE_OPT_IN")
        with tempfile.TemporaryDirectory(dir=FIXTURE.parent) as raw:
            current = Path(raw) / "current.json"
            current.write_text(FIXTURE.read_text())
            result = subprocess.run(
                ["python3", str(CLI), str(FIXTURE), str(current), "--work-item-id", WORK_A,
                 "--source-file", str(SOURCE_A), "--commit", "p22-cli"],
                cwd=REPO, text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["packet"], EVIDENCE_PACKET)
        self.assertNotIn(SOURCE_A.name, result.stdout)

    def test_flag_is_inactive(self) -> None:
        self.assertEqual(FLAGS["offline_portable_current_case_evidence_demo"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
