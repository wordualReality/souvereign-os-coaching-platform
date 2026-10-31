"""P21 offline evidence-bound review tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_evidence_bound_review import (  # noqa: E402
    PACKET,
    evidence_bound_review,
    evidence_bound_review_files,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests/kdb/fixtures/p20_inbox_byte_spans.json"
SOURCE_A = REPO / "tests/kdb/fixtures/p20_source_a.bin"
SOURCE_B = REPO / "tests/kdb/fixtures/p20_source_b.bin"
SOURCE_NFC = REPO / "tests/kdb/fixtures/p20_source_nfc.bin"
SOURCE_NFD = REPO / "tests/kdb/fixtures/p20_source_nfd.bin"
CLI = REPO / "services/kdb/offline_evidence_bound_review_cli.py"
FLAGS = json.loads((REPO / "contracts/kdb/activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
VERSION_A = "aaaaaaaa-bbbb-4ccc-8ddd-222222222222"
SOURCE_ID_A = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"


def load() -> dict:
    return json.loads(FIXTURE.read_text())


def blob(value: dict) -> str:
    return json.dumps(value, sort_keys=True)


class OfflineEvidenceBoundReview(unittest.TestCase):
    def test_positive_current_case_binds_real_slice_without_source_leak(self) -> None:
        payload = load()
        original = deepcopy(payload)
        receipt = evidence_bound_review_files(FIXTURE, WORK_A, SOURCE_A, commit="p21-test")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["review_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        self.assertEqual(receipt["span_semantics"], "ZERO_BASED_END_EXCLUSIVE_RECONCILED")
        self.assertEqual(receipt["evidence_span_count"], 1)
        span = receipt["evidence_spans"][0]
        self.assertEqual((span["byte_start"], span["byte_end_exclusive"], span["byte_length"]), (0, 32, 32))
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        text = blob(receipt)
        self.assertNotIn("P20-SYNTH-SRC-A", text)
        self.assertNotIn("p20_source_a.bin", text)
        self.assertNotIn("synthetic://", text)
        self.assertNotIn("9035ebdbe11b2732f76c5aa77dfeeb209da8153dabf2a4b225c2319180596a9b", text)
        self.assertEqual(receipt, evidence_bound_review_files(FIXTURE, WORK_A, SOURCE_A, commit="p21-test"))

    def test_cli_is_machine_readable_and_non_authoritative(self) -> None:
        proc = subprocess.run(
            ["python3", str(CLI), str(FIXTURE), "--work-item-id", WORK_A, "--source-file", str(SOURCE_A), "--commit", "p21-cli"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["review_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        self.assertEqual(receipt["source_commit"], "p21-cli")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_tamper_wrong_file_and_forged_version_fail_without_identity_leak(self) -> None:
        for data in (SOURCE_B.read_bytes(), SOURCE_A.read_bytes()[:-1] + b"X"):
            receipt = evidence_bound_review(load(), WORK_A, data, commit="p21-test")
            self.assertEqual(receipt["review_status"], "EVIDENCE_BOUND_REVIEW_DENIED")
            self.assertNotIn(WORK_A, blob(receipt))
            self.assertNotIn(SOURCE_ID_A, blob(receipt))
        forged = load()
        forged["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"][0]["source_version_id"] = "00000000-0000-4000-8000-000000000000"
        receipt = evidence_bound_review(forged, WORK_A, SOURCE_A.read_bytes(), commit="p21-test")
        self.assertIn(receipt["deny_code"], {"WRONG_SOURCE_VERSION_LINK", "WORK_ITEM_NOT_SELECTABLE"})
        self.assertNotIn(WORK_A, blob(receipt))

    def test_locator_integer_disagreement_invalid_duplicate_and_overlap_deny(self) -> None:
        cases: list[tuple[dict, str]] = []
        disagreement = load()
        disagreement["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"][0]["end"] = 31
        cases.append((disagreement, "EVIDENCE_OFFSET_DISAGREEMENT"))
        unknown = load()
        unknown["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"][0]["locator"] = "chars:0-31"
        cases.append((unknown, "UNVERIFIED_LOCAL_SPAN_SEMANTICS"))
        duplicate = load()
        spans = duplicate["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"]
        spans.append(deepcopy(spans[0]))
        cases.append((duplicate, "DUPLICATE_EVIDENCE_SPAN"))
        overlap = load()
        spans = overlap["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"]
        spans[0].update({"locator": "bytes:0-15", "start": 0, "end": 16})
        spans.append({"source_version_id": VERSION_A, "locator": "bytes:8-31", "start": 8, "end": 32})
        cases.append((overlap, "OVERLAPPING_EVIDENCE_SPAN"))
        for payload, expected in cases:
            receipt = evidence_bound_review(payload, WORK_A, SOURCE_A.read_bytes(), commit="p21-test")
            self.assertEqual(receipt["deny_code"], expected)
            self.assertNotIn(WORK_A, blob(receipt))

    def test_nfc_nfd_and_cross_tenant_revocation_are_fail_closed(self) -> None:
        nfc = load()
        import hashlib
        nfc["entries"][0]["candidate_chain"]["source_version"]["content_sha256"] = hashlib.sha256(SOURCE_NFC.read_bytes()).hexdigest()
        spans = nfc["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"]
        spans[0].update({"locator": f"bytes:0-{len(SOURCE_NFC.read_bytes()) - 1}", "start": 0, "end": len(SOURCE_NFC.read_bytes())})
        self.assertEqual(evidence_bound_review(nfc, WORK_A, SOURCE_NFC.read_bytes())["review_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        self.assertNotEqual(SOURCE_NFC.read_bytes(), SOURCE_NFD.read_bytes())
        self.assertEqual(evidence_bound_review(nfc, WORK_A, SOURCE_NFD.read_bytes())["review_status"], "EVIDENCE_BOUND_REVIEW_DENIED")
        cross = load()
        cross["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = evidence_bound_review(cross, WORK_A, SOURCE_A.read_bytes())
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        revoked = load()
        revoked["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        denied = evidence_bound_review(revoked, WORK_A, SOURCE_A.read_bytes())
        self.assertEqual(denied["review_status"], "EVIDENCE_BOUND_REVIEW_DENIED")
        self.assertNotIn(WORK_A, blob(denied))
        other = evidence_bound_review(revoked, WORK_B, SOURCE_B.read_bytes())
        self.assertEqual(other["review_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")

    def test_path_symlink_hardlink_and_oversize_rejected(self) -> None:
        with self.assertRaises(PreviewParseError):
            evidence_bound_review_files(FIXTURE, WORK_A, "../outside.bin")
        try:
            temp = tempfile.TemporaryDirectory(dir=SOURCE_A.parent)
        except PermissionError:
            self.skipTest("sandbox denies temporary files inside checkout")
        with temp as raw:
            root = Path(raw)
            symlink = root / "link.bin"
            try:
                symlink.symlink_to(SOURCE_A)
                with self.assertRaises(PreviewParseError):
                    evidence_bound_review_files(FIXTURE, WORK_A, symlink)
            except OSError:
                pass
            hard_src, hard_dst = root / "hard-src.bin", root / "hard-dst.bin"
            hard_src.write_bytes(SOURCE_A.read_bytes())
            try:
                os.link(hard_src, hard_dst)
                with self.assertRaises(PreviewParseError):
                    evidence_bound_review_files(FIXTURE, WORK_A, hard_dst)
            except OSError:
                pass
            huge = root / "huge.bin"
            huge.write_bytes(b"x" * 65537)
            with self.assertRaises(PreviewParseError):
                evidence_bound_review_files(FIXTURE, WORK_A, huge)

    def test_flag_is_inactive(self) -> None:
        self.assertEqual(FLAGS["offline_evidence_bound_review"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
