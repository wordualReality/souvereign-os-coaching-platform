"""P18 portable offline review demo-pack tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_demo_pack import (  # noqa: E402
    DEMO_ROOT,
    FIXED_FILES,
    PACKET,
    demo_pack,
    demo_pack_files,
    write_demo_pack,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
CLI = REPO / "services" / "kdb" / "offline_review_demo_pack_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
SOURCE_A = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
SECRET_MEDIA = "P18_SECRET_MEDIA_<script>alert(1)</script>"
SECRET_PURPOSE = "P18_SECRET_PURPOSE_javascript:alert(1)"
SECRET_RIGHTS = 'P18_SECRET_RIGHTS_" onerror="alert(1)'
SECRET_LOCATOR = "P18_SECRET_LOCATOR_https://evil.example/x"
SECRET_COMMIT = "P18_SECRET_COMMIT\nwhoami"


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


def _bundle(receipt: dict) -> str:
    return "".join(receipt["artifacts"][name] for name in FIXED_FILES) + json.dumps(
        receipt["manifest"], sort_keys=True
    )


class OfflineReviewDemoPack(unittest.TestCase):
    def test_identical_two_case_pack_is_gated_and_linked(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = demo_pack(payload, deepcopy(payload), commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["pack_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["unchanged_count"], 2)
        self.assertEqual(receipt["added_count"], 0)
        self.assertEqual(receipt["removed_or_denied_count"], 0)
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["integrity"], "LOCAL_FILE_INTEGRITY_ONLY")
        artifacts = receipt["artifacts"]
        self.assertEqual(set(artifacts), set(FIXED_FILES))
        index = artifacts["index.html"]
        current = artifacts["current.html"]
        changes = artifacts["changes.html"]
        self.assertTrue(index.startswith("<!DOCTYPE html>"))
        self.assertIn("default-src 'none'", index)
        self.assertIn("default-src 'none'", current)
        self.assertIn("default-src 'none'", changes)
        self.assertIn("href=\"index.html\"", current)
        self.assertIn("href=\"current.html\"", index)
        self.assertIn("href=\"changes.html\"", index)
        self.assertIn(f'href="current.html#case-{WORK_A}"', index)
        self.assertIn(f'id="case-{WORK_A}"', current)
        self.assertIn(WORK_A, current)
        self.assertIn(WORK_B, current)
        self.assertIn("SNAPSHOT_ORDER_NOT_ATTESTED", changes)
        self.assertNotIn("<script", index)
        self.assertNotIn("<form", current)
        reversed_entries = {**payload, "entries": list(reversed(payload["entries"]))}
        again = demo_pack(reversed_entries, deepcopy(reversed_entries), commit="test-commit")
        for name in FIXED_FILES:
            self.assertEqual(artifacts[name], again["artifacts"][name])

    def test_cli_stdout_manifest_without_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            copy = Path(raw) / "p18-current-copy.json"
            copy.write_text(FIXTURE.read_text(), encoding="utf-8")
            proc = _cli([str(FIXTURE), str(copy), "--commit", "cli-test"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["pack_status"], "PREVIEW_ONLY")
            self.assertEqual(manifest["unchanged_count"], 2)
            self.assertEqual(manifest["integrity"], "LOCAL_FILE_INTEGRITY_ONLY")
            self.assertNotIn("<!DOCTYPE html>", proc.stdout)
            self.assertEqual(proc.stderr, "")
            self.assertFalse(any(DEMO_ROOT.glob("cli-test*")))

    def test_revoked_source_absent_from_every_artifact(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = demo_pack(baseline, current, commit="test-commit")
        self.assertEqual(receipt["pack_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["current_eligible_count"], 1)
        self.assertEqual(receipt["removed_or_denied_count"], 1)
        blob = _bundle(receipt)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(SOURCE_A, blob)
        self.assertIn(WORK_B, receipt["artifacts"]["current.html"])
        self.assertIn(WORK_B, receipt["artifacts"]["index.html"])
        self.assertIn("REMOVED_OR_DENIED_COUNT", receipt["artifacts"]["changes.html"])

    def test_cross_tenant_denied_pack_has_no_case_pages(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = demo_pack(baseline, current, commit="test-commit")
        self.assertEqual(receipt["pack_status"], "DEMO_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        blob = _bundle(receipt)
        self.assertIn("DEMO_DENIED", receipt["artifacts"]["index.html"])
        self.assertNotIn("<table>", receipt["artifacts"]["index.html"])
        self.assertNotIn("TENANT_SYNTH_B", blob)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(WORK_B, blob)
        self.assertNotIn(f'href="current.html#case-', receipt["artifacts"]["index.html"])

    def test_secrets_never_enter_the_bundle(self) -> None:
        baseline = _load()
        current = _load()
        chain = current["entries"][0]["candidate_chain"]
        chain["source"]["rights_status"] = "REVOKED"
        chain["source_version"]["media_type"] = SECRET_MEDIA
        chain["candidate_revision"]["proposal_payload"]["title"] = SECRET_PURPOSE
        chain["source_version"]["rights_snapshot"]["rights_basis"] = SECRET_RIGHTS
        chain["source"]["external_locator"] = SECRET_LOCATOR
        receipt = demo_pack(baseline, current, commit="test-commit")
        blob = _bundle(receipt)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn("P18_SECRET_MEDIA_", blob)
        self.assertNotIn("javascript:", blob)
        self.assertNotIn("https://evil.example", blob)
        self.assertNotIn("onerror=", blob)
        self.assertNotIn("<script", blob)

    def test_write_pack_checksums_and_cleanup(self) -> None:
        payload = _load()
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            copy = Path(raw) / "p18-current-copy.json"
            copy.write_text(FIXTURE.read_text(), encoding="utf-8")
            receipt = demo_pack_files(FIXTURE, copy, commit="test-commit")
        name = "p18-unit-pack"
        out = Path("tests/kdb/demo-artifacts") / name
        try:
            written = write_demo_pack(receipt["artifacts"], out)
            self.assertEqual(written.name, name)
            for filename in FIXED_FILES:
                path = written / filename
                self.assertTrue(path.is_file())
            for filename, digest in receipt["file_sha256"].items():
                data = (written / filename).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            manifest = json.loads((written / "manifest.json").read_text())
            self.assertEqual(manifest["files"]["index.html"], receipt["file_sha256"]["index.html"])
            with self.assertRaises(PreviewParseError) as exists:
                write_demo_pack(receipt["artifacts"], out)
            self.assertEqual(exists.exception.code, "OUTPUT_EXISTS")
        finally:
            target = DEMO_ROOT / name
            if target.exists():
                for child in target.iterdir():
                    child.unlink()
                target.rmdir()

    def test_output_path_and_interrupted_write(self) -> None:
        payload = _load()
        receipt = demo_pack(payload, deepcopy(payload), commit="test-commit")
        with self.assertRaises(PreviewParseError) as escaped:
            write_demo_pack(receipt["artifacts"], "/tmp/kdb-p18-escape")
        self.assertEqual(escaped.exception.code, "PATH_ESCAPE_DENIED")
        with self.assertRaises(PreviewParseError) as networked:
            write_demo_pack(receipt["artifacts"], "https://example.invalid/x")
        self.assertEqual(networked.exception.code, "NETWORK_PATH_DENIED")
        with self.assertRaises(PreviewParseError) as parent:
            write_demo_pack(receipt["artifacts"], "tests/kdb/fixtures/p18-wrong-root")
        self.assertEqual(parent.exception.code, "PATH_ESCAPE_DENIED")
        name = "p18-flaky-pack"
        leftover = DEMO_ROOT / name
        if leftover.exists():
            shutil.rmtree(leftover)
        out = Path("tests/kdb/demo-artifacts") / name
        real_open = os.open

        def flaky(*args, **kwargs):
            path = args[0] if args else kwargs.get("path")
            if str(path).endswith("README.txt"):
                raise OSError("injected-fail")
            return real_open(*args, **kwargs)

        with patch("offline_review_demo_pack.os.open", side_effect=flaky):
            with self.assertRaises(OSError):
                write_demo_pack(receipt["artifacts"], out)
        self.assertFalse((DEMO_ROOT / name).exists())
        same = _cli([str(FIXTURE), str(FIXTURE)])
        self.assertEqual(same.returncode, 2)
        self.assertEqual(json.loads(same.stdout)["parse_error"], "SAME_SNAPSHOT_PATH")
        with self.assertRaises(PreviewParseError) as dup:
            demo_pack_files(DUP_TOP, FIXTURE)
        self.assertEqual(dup.exception.code, "DUPLICATE_JSON_KEY")
        with self.assertRaises(PreviewParseError) as commit_err:
            demo_pack(_load(), _load(), commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_demo_pack"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_snapshot_delta"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
