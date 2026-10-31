"""P23 deterministic ZIP, verifier, extraction and browser acceptance tests."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services/kdb"))
from offline_demo_acceptance_kit import (  # noqa: E402
    browser_smoke,
    build_acceptance_zip,
    extract_verified_zip,
    verify_acceptance_zip,
)
from offline_review_demo_pack import DEMO_ROOT, EVIDENCE_FILES  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests/kdb/fixtures/p20_inbox_byte_spans.json"
SOURCE = REPO / "tests/kdb/fixtures/p20_source_a.bin"
WORK = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
FLAGS = json.loads((REPO / "contracts/kdb/activation_flags.json").read_text())


class OfflineDemoAcceptanceKit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(dir=FIXTURE.parent)
        cls.current = Path(cls.temp.name) / "current.json"
        cls.current.write_bytes(FIXTURE.read_bytes())
        token = uuid.uuid4().hex
        cls.rel_a = Path("tests/kdb/demo-artifacts") / f"p23-{token}-a.zip"
        cls.rel_b = Path("tests/kdb/demo-artifacts") / f"p23-{token}-b.zip"
        cls.path_a = REPO / cls.rel_a
        cls.path_b = REPO / cls.rel_b
        cls.receipt_a = build_acceptance_zip(FIXTURE, cls.current, WORK, SOURCE, cls.rel_a, commit="p23-test")
        cls.receipt_b = build_acceptance_zip(FIXTURE, cls.current, WORK, SOURCE, cls.rel_b, commit="p23-test")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
        cls.path_a.unlink(missing_ok=True); cls.path_b.unlink(missing_ok=True)

    def test_repeat_build_is_byte_identical_and_manifest_verifies(self) -> None:
        self.assertEqual(self.path_a.read_bytes(), self.path_b.read_bytes())
        self.assertEqual(self.receipt_a["zip_sha256"], self.receipt_b["zip_sha256"])
        verified = verify_acceptance_zip(self.rel_a)
        self.assertEqual(verified["file_count"], 7)
        self.assertEqual(verified["evidence_status"], "LOCAL_BYTES_AND_SPANS_BOUNDED")
        self.assertEqual(verified["final_authority"], "NOT_ADMITTED")
        with zipfile.ZipFile(self.path_a) as archive:
            self.assertEqual(archive.namelist(), list(EVIDENCE_FILES))
            blob = b"".join(archive.read(name) for name in archive.namelist())
        self.assertNotIn(SOURCE.name.encode(), blob)
        self.assertNotIn(str(SOURCE).encode(), blob)

    def _variant(self, transform) -> Path:
        target = DEMO_ROOT / f"p23-{uuid.uuid4().hex}-bad.zip"
        with zipfile.ZipFile(self.path_a) as source, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as out:
            entries = [(name, source.read(name)) for name in source.namelist()]
            for name, data in transform(entries): out.writestr(name, data)
        self.addCleanup(target.unlink, missing_ok=True)
        return target.relative_to(REPO)

    def test_tamper_missing_extra_and_traversal_fail_closed(self) -> None:
        def tamper(entries):
            return [(name, data + b"x" if name == "current.html" else data) for name, data in entries]
        cases = [
            self._variant(tamper),
            self._variant(lambda entries: entries[:-1]),
            self._variant(lambda entries: entries + [("extra.txt", b"x")]),
            self._variant(lambda entries: entries[:-1] + [("../escape.txt", b"x")]),
        ]
        for path in cases:
            with self.assertRaises(PreviewParseError): verify_acceptance_zip(path)

    def test_revoked_tenant_overlap_and_path_inputs_fail_closed(self) -> None:
        base = json.loads(FIXTURE.read_text())
        variants = []
        revoked = deepcopy(base); revoked["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"; variants.append(revoked)
        tenant = deepcopy(base); tenant["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_OTHER"; variants.append(tenant)
        overlap = deepcopy(base)
        spans = overlap["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"]
        spans[0].update({"locator": "bytes:0-15", "start": 0, "end": 16})
        spans.append({"source_version_id": spans[0]["source_version_id"], "locator": "bytes:8-31", "start": 8, "end": 32})
        variants.append(overlap)
        stale = deepcopy(base)
        stale["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"][0]["source_version_id"] = "00000000-0000-4000-8000-000000000000"
        variants.append(stale)
        for index, payload in enumerate(variants):
            current = Path(self.temp.name) / f"invalid-{index}.json"; current.write_text(json.dumps(payload))
            output = Path("tests/kdb/demo-artifacts") / f"p23-{uuid.uuid4().hex}-denied.zip"
            with self.assertRaises(PreviewParseError):
                build_acceptance_zip(FIXTURE, current, WORK, SOURCE, output, commit="p23-test")
            self.assertFalse((REPO / output).exists())
        with self.assertRaises(PreviewParseError):
            build_acceptance_zip(FIXTURE, self.current, WORK, "../source.bin", Path("tests/kdb/demo-artifacts") / f"p23-{uuid.uuid4().hex}.zip", commit="p23-test")

    def test_verified_extract_is_bounded_and_exact(self) -> None:
        name = f"p23-extract-{uuid.uuid4().hex}"
        target = DEMO_ROOT / name
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        extracted = extract_verified_zip(self.rel_a, Path("tests/kdb/demo-artifacts") / name)
        self.assertEqual(extracted, target)
        self.assertEqual({item.name for item in target.iterdir()}, set(EVIDENCE_FILES))
        with self.assertRaises(PreviewParseError): extract_verified_zip(self.rel_a, "../escape")

    def test_real_browser_navigation_smoke(self) -> None:
        receipt = browser_smoke(self.rel_a)
        self.assertEqual(receipt["browser_smoke"], "PASS")
        self.assertEqual(receipt["path"], "index.html -> current.html -> current-case-evidence.json")
        self.assertEqual(FLAGS["offline_demo_acceptance_kit"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
