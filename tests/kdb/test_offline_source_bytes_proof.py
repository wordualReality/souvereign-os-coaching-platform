"""P20 offline source-bytes proof tests. No SQL write, n8n, or hosted apply."""
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
from offline_source_bytes_proof import (  # noqa: E402
    PACKET,
    source_bytes_proof,
    source_bytes_proof_files,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p20_inbox_match.json"
SPAN_FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p20_inbox_byte_spans.json"
NFC_FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p20_inbox_nfc.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
SOURCE_A = REPO / "tests" / "kdb" / "fixtures" / "p20_source_a.bin"
SOURCE_B = REPO / "tests" / "kdb" / "fixtures" / "p20_source_b.bin"
SOURCE_NFC = REPO / "tests" / "kdb" / "fixtures" / "p20_source_nfc.bin"
SOURCE_NFD = REPO / "tests" / "kdb" / "fixtures" / "p20_source_nfd.bin"
CLI = REPO / "services" / "kdb" / "offline_source_bytes_proof_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
UNKNOWN = "00000000-0000-4000-8000-000000000000"
SOURCE_ID_A = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
SHA_A = "9035ebdbe11b2732f76c5aa77dfeeb209da8153dabf2a4b225c2319180596a9b"
SECRET_COMMIT = "P20_SECRET_COMMIT\nwhoami"


def _load(path: Path = FIXTURE) -> dict:
    return json.loads(path.read_text())


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


def _blob(receipt: dict) -> str:
    return json.dumps(receipt, sort_keys=True)


class OfflineSourceBytesProof(unittest.TestCase):
    def test_matching_local_bytes_remain_gated(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = source_bytes_proof_files(FIXTURE, WORK_A, SOURCE_A, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["proof_status"], "LOCAL_BYTES_MATCH_DECLARED_SHA")
        self.assertEqual(receipt["source_file_scope"], "SOURCE_FILE_LOCAL_ONLY")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["hosted_verified"], "HOSTED_VERIFIED_NO")
        self.assertEqual(receipt["review_work_item_id"], WORK_A)
        self.assertEqual(receipt["source_byte_length"], 32)
        self.assertEqual(receipt["span_status"], "UNVERIFIED_LOCAL_SPAN_SEMANTICS")
        self.assertIn("RIGHTS_SNAPSHOT_UNATTESTED", receipt["explicit_gaps"])
        self.assertIn("RIGHTS_DIGEST_UNVERIFIED", receipt["explicit_gaps"])
        blob = _blob(receipt)
        self.assertNotIn(SHA_A, blob)
        self.assertNotIn("p20_source_a.bin", blob)
        self.assertNotIn("P20-SYNTH-SRC-A", blob)
        again = source_bytes_proof_files(FIXTURE, WORK_A, SOURCE_A, commit="test-commit")
        self.assertEqual(_blob(receipt), _blob(again))

    def test_cli_stdout_match_without_write(self) -> None:
        proc = _cli(
            [
                str(FIXTURE),
                "--work-item-id",
                WORK_A,
                "--source-file",
                str(SOURCE_A),
                "--commit",
                "cli-test",
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["proof_status"], "LOCAL_BYTES_MATCH_DECLARED_SHA")
        self.assertEqual(receipt["source_commit"], "cli-test")
        self.assertEqual(proc.stderr, "")
        self.assertNotIn("P20-SYNTH-SRC-A", proc.stdout)
        self.assertNotIn(SHA_A, proc.stdout)

    def test_one_byte_tamper_is_mismatch_without_ids(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(SOURCE_A.parent)) as raw:
            tampered = Path(raw) / "p20-tampered.bin"
            data = bytearray(SOURCE_A.read_bytes())
            data[-1] ^= 0x01
            tampered.write_bytes(data)
            receipt = source_bytes_proof_files(FIXTURE, WORK_A, tampered, commit="test-commit")
            blob = _blob(receipt)
            self.assertEqual(receipt["proof_status"], "LOCAL_CONTENT_SHA_MISMATCH")
            self.assertNotIn(WORK_A, blob)
            self.assertNotIn(SOURCE_ID_A, blob)
            self.assertNotIn(SHA_A, blob)
            self.assertNotIn("p20-tampered.bin", blob)
            self.assertNotIn("P20-SYNTH-SRC-A", blob)

    def test_wrong_source_file_is_mismatch(self) -> None:
        receipt = source_bytes_proof_files(FIXTURE, WORK_A, SOURCE_B, commit="test-commit")
        blob = _blob(receipt)
        self.assertEqual(receipt["proof_status"], "LOCAL_CONTENT_SHA_MISMATCH")
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(WORK_B, blob)
        self.assertNotIn(SHA_A, blob)

    def test_integer_byte_spans_are_bounded(self) -> None:
        receipt = source_bytes_proof_files(SPAN_FIXTURE, WORK_A, SOURCE_A, commit="test-commit")
        self.assertEqual(receipt["proof_status"], "LOCAL_BYTES_MATCH_DECLARED_SHA")
        self.assertEqual(receipt["span_status"], "LOCAL_SPAN_OFFSETS_BOUNDED")

    def test_utf8_normalization_uses_raw_bytes(self) -> None:
        match = source_bytes_proof_files(NFC_FIXTURE, WORK_A, SOURCE_NFC, commit="test-commit")
        self.assertEqual(match["proof_status"], "LOCAL_BYTES_MATCH_DECLARED_SHA")
        mismatch = source_bytes_proof_files(NFC_FIXTURE, WORK_A, SOURCE_NFD, commit="test-commit")
        self.assertEqual(mismatch["proof_status"], "LOCAL_CONTENT_SHA_MISMATCH")
        self.assertNotIn(WORK_A, _blob(mismatch))

    def test_cross_tenant_and_revoked_hide_identities(self) -> None:
        cross = _load()
        cross["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = source_bytes_proof(cross, WORK_A, SOURCE_A.read_bytes(), commit="test-commit")
        blob = _blob(receipt)
        self.assertEqual(receipt["proof_status"], "PROOF_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn("TENANT_SYNTH_B", blob)
        revoked = _load()
        revoked["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = source_bytes_proof(revoked, WORK_A, SOURCE_A.read_bytes(), commit="test-commit")
        self.assertEqual(receipt["proof_status"], "PROOF_DENIED")
        self.assertNotIn(WORK_A, _blob(receipt))
        other = source_bytes_proof(revoked, WORK_B, SOURCE_B.read_bytes(), commit="test-commit")
        self.assertEqual(other["proof_status"], "LOCAL_BYTES_MATCH_DECLARED_SHA")
        self.assertEqual(other["review_work_item_id"], WORK_B)

    def test_duplicate_unknown_forged_and_empty_evidence(self) -> None:
        dup = _load()
        dup["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = WORK_A
        receipt = source_bytes_proof(dup, WORK_A, SOURCE_A.read_bytes(), commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertNotIn(WORK_A, _blob(receipt))
        missing = source_bytes_proof(_load(), UNKNOWN, SOURCE_A.read_bytes(), commit="test-commit")
        self.assertEqual(missing["proof_status"], "PROOF_DENIED")
        self.assertNotIn(UNKNOWN, _blob(missing))
        forged = _load()
        forged["entries"][0]["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        receipt = source_bytes_proof(forged, WORK_A, SOURCE_A.read_bytes(), commit="test-commit")
        self.assertNotIn("forged-reviewer", _blob(receipt))
        self.assertNotIn(WORK_A, _blob(receipt))
        empty = _load()
        empty["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        receipt = source_bytes_proof(empty, WORK_A, SOURCE_A.read_bytes(), commit="test-commit")
        self.assertNotIn(WORK_A, _blob(receipt))

    def test_path_and_input_rejects(self) -> None:
        with self.assertRaises(PreviewParseError) as escaped:
            source_bytes_proof_files(
                FIXTURE,
                WORK_A,
                "../souvereign-os-coaching-platform-kdb-p06/tests/kdb/fixtures/p20_source_a.bin",
            )
        self.assertEqual(escaped.exception.code, "PATH_ESCAPE_DENIED")
        with self.assertRaises(PreviewParseError) as networked:
            source_bytes_proof_files(FIXTURE, WORK_A, "https://example.invalid/x.bin")
        self.assertEqual(networked.exception.code, "NETWORK_PATH_DENIED")
        proc = _cli([str(DUP_TOP), "--work-item-id", WORK_A, "--source-file", str(SOURCE_A)])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "DUPLICATE_JSON_KEY")
        with self.assertRaises(PreviewParseError) as commit_err:
            source_bytes_proof(_load(), WORK_A, SOURCE_A.read_bytes(), commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")
        with tempfile.TemporaryDirectory(dir=str(SOURCE_A.parent)) as raw:
            huge = Path(raw) / "p20-huge.bin"
            huge.write_bytes(b"A" * (65536 + 1))
            with self.assertRaises(PreviewParseError) as oversized:
                source_bytes_proof_files(FIXTURE, WORK_A, huge)
            self.assertEqual(oversized.exception.code, "INPUT_TOO_LARGE")
            link_src = Path(raw) / "p20-link-src.bin"
            link_dst = Path(raw) / "p20-hardlink.bin"
            link_src.write_bytes(SOURCE_A.read_bytes())
            try:
                os.link(link_src, link_dst)
            except OSError:
                self.skipTest("hardlink unsupported")
            with self.assertRaises(PreviewParseError) as linked:
                source_bytes_proof_files(FIXTURE, WORK_A, link_dst)
            self.assertEqual(linked.exception.code, "HARDLINK_DENIED")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_source_bytes_proof"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_viewmodel"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
