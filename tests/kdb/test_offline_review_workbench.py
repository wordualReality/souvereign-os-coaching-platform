"""P16 static offline review-workbench tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_workbench import (  # noqa: E402
    PACKET,
    workbench,
    workbench_file,
    write_workbench_html,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
CLI = REPO / "services" / "kdb" / "offline_review_workbench_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
SECRET_MEDIA = "P16_SECRET_MEDIA_<script>alert(1)</script>"
SECRET_PURPOSE = "P16_SECRET_PURPOSE_javascript:alert(1)"
SECRET_RIGHTS = 'P16_SECRET_RIGHTS_" onerror="alert(1)'
SECRET_LOCATOR = "P16_SECRET_LOCATOR_https://evil.example/x"
SECRET_COMMIT = "P16_SECRET_COMMIT\nwhoami"


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


class OfflineReviewWorkbench(unittest.TestCase):
    def test_two_case_html_is_sorted_stable_and_gated(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = workbench(payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["workbench_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["card_count"], 2)
        self.assertEqual(receipt["detail_count"], 2)
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["snapshot_authority"], "SNAPSHOT_UNTRUSTED")
        html_page = receipt["html"]
        self.assertTrue(html_page.startswith("<!DOCTYPE html>"))
        self.assertIn("default-src 'none'", html_page)
        self.assertIn("script-src 'none'", html_page)
        self.assertIn("Nicht autorisiert, nur synthetische Vorschau.", html_page)
        self.assertIn("SNAPSHOT_UNTRUSTED", html_page)
        self.assertIn("NOT_ADMITTED", html_page)
        self.assertIn("NOT_ASSIGNED", html_page)
        self.assertIn(f'href="#case-{WORK_A}"', html_page)
        self.assertIn(f'id="case-{WORK_A}"', html_page)
        self.assertIn(f'href="#case-{WORK_B}"', html_page)
        self.assertLess(html_page.find(WORK_A), html_page.find(WORK_B))
        self.assertNotIn("<script", html_page)
        self.assertNotIn("<form", html_page)
        self.assertNotIn("<img", html_page)
        self.assertNotIn("READY", html_page)
        reversed_entries = {**payload, "entries": list(reversed(payload["entries"]))}
        self.assertEqual(html_page, workbench(reversed_entries, commit="test-commit")["html"])
        self.assertEqual(html_page, workbench(payload, commit="test-commit")["html"])

    def test_cli_stdout_html(self) -> None:
        proc = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("<!DOCTYPE html>"))
        self.assertIn("cli-test", proc.stdout)
        self.assertIn("LABEL_NOT_ATTESTED", proc.stdout)
        self.assertEqual(proc.stderr, "")
        again = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.stdout, again.stdout)

    def test_cross_tenant_denied_screen(self) -> None:
        payload = _load()
        payload["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = workbench(payload, commit="test-commit")
        self.assertEqual(receipt["workbench_status"], "WORKBENCH_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertEqual(receipt["card_count"], 0)
        self.assertEqual(receipt["detail_count"], 0)
        html_page = receipt["html"]
        self.assertIn("WORKBENCH_DENIED", html_page)
        self.assertNotIn("<table>", html_page)
        self.assertNotIn("TENANT_SYNTH_B", html_page)
        self.assertNotIn(WORK_A, html_page)
        self.assertNotIn(WORK_B, html_page)

    def test_revoked_source_omitted_other_remains(self) -> None:
        payload = _load()
        payload["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = workbench(payload, commit="test-commit")
        self.assertEqual(receipt["workbench_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["card_count"], 1)
        self.assertEqual(receipt["detail_count"], 1)
        html_page = receipt["html"]
        self.assertNotIn(WORK_A, html_page)
        self.assertIn(WORK_B, html_page)
        swapped = _load()
        swapped["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        swapped["entries"] = list(reversed(swapped["entries"]))
        self.assertEqual(html_page, workbench(swapped, commit="test-commit")["html"])

    def test_duplicate_stale_forged_empty_evidence(self) -> None:
        dup = _load()
        dup["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = WORK_A
        receipt = workbench(dup, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertEqual(receipt["card_count"], 0)
        stale = _load()
        extra = deepcopy(stale["entries"][0]["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222229"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        stale["entries"][0]["candidate_chain"]["source_versions"] = [extra]
        receipt = workbench(stale, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        self.assertIn(WORK_B, receipt["html"])
        forged = _load()
        forged["entries"][0]["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        receipt = workbench(forged, commit="test-commit")
        self.assertNotIn("forged-reviewer", receipt["html"])
        empty = _load()
        empty["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        receipt = workbench(empty, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        pending = _load()
        pending["entries"][0]["candidate_chain"]["source"]["rights_status"] = "PENDING"
        receipt = workbench(pending, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        self.assertIn(WORK_B, receipt["html"])

    def test_secrets_and_html_payloads_never_emitted(self) -> None:
        payload = _load()
        chain = payload["entries"][0]["candidate_chain"]
        chain["source_version"]["media_type"] = SECRET_MEDIA
        chain["candidate_revision"]["proposal_payload"]["title"] = SECRET_PURPOSE
        chain["source_version"]["rights_snapshot"]["rights_basis"] = SECRET_RIGHTS
        chain["source"]["external_locator"] = SECRET_LOCATOR
        receipt = workbench(payload, commit="test-commit")
        self.assertEqual(receipt["workbench_status"], "PREVIEW_ONLY")
        html_page = receipt["html"]
        self.assertNotIn("P16_SECRET_MEDIA_", html_page)
        self.assertNotIn("P16_SECRET_PURPOSE_", html_page)
        self.assertNotIn("P16_SECRET_RIGHTS_", html_page)
        self.assertNotIn("P16_SECRET_LOCATOR_", html_page)
        self.assertNotIn("<script", html_page)
        self.assertNotIn("javascript:", html_page)
        self.assertNotIn("https://evil.example", html_page)
        self.assertNotIn("onerror=", html_page)
        self.assertNotIn("media_type", html_page)

    def test_duplicate_json_untrusted_commit_and_output_path(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            workbench_file(DUP_TOP)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP)])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "DUPLICATE_JSON_KEY")
        with self.assertRaises(PreviewParseError) as commit_err:
            workbench(_load(), commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")
        with self.assertRaises(PreviewParseError) as escaped:
            write_workbench_html("<!DOCTYPE html>", "/tmp/kdb-p16-escape.html")
        self.assertEqual(escaped.exception.code, "PATH_ESCAPE_DENIED")
        with self.assertRaises(PreviewParseError) as networked:
            write_workbench_html("<!DOCTYPE html>", "https://example.invalid/x.html")
        self.assertEqual(networked.exception.code, "NETWORK_PATH_DENIED")
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            dest = Path(raw) / "kdb-p16-workbench-test.html"
            relative = dest.relative_to(REPO)
            written = write_workbench_html("<!DOCTYPE html>\n", relative)
            self.assertEqual(written.read_text(encoding="utf-8"), "<!DOCTYPE html>\n")
            with self.assertRaises(PreviewParseError) as exists:
                write_workbench_html("<!DOCTYPE html>\n", relative)
            self.assertEqual(exists.exception.code, "OUTPUT_EXISTS")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_workbench"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_case_detail"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
