"""P17 offline snapshot-delta workbench tests. No SQL write, n8n, or hosted apply."""
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
from offline_review_snapshot_delta import (  # noqa: E402
    PACKET,
    snapshot_delta,
    snapshot_delta_files,
    write_workbench_html,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
CLI = REPO / "services" / "kdb" / "offline_review_snapshot_delta_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
WORK_C = "aaaaaaaa-bbbb-4ccc-8ddd-777777777779"
SOURCE_A = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
SECRET_MEDIA = "P17_SECRET_MEDIA_<script>alert(1)</script>"
SECRET_PURPOSE = "P17_SECRET_PURPOSE_javascript:alert(1)"
SECRET_RIGHTS = 'P17_SECRET_RIGHTS_" onerror="alert(1)'
SECRET_LOCATOR = "P17_SECRET_LOCATOR_https://evil.example/x"
SECRET_COMMIT = "P17_SECRET_COMMIT\nwhoami"


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


def _receipt_blob(receipt: dict) -> str:
    return json.dumps(receipt, sort_keys=True)


def _third_entry(payload: dict) -> dict:
    extra = deepcopy(payload["entries"][1])
    extra["case_id"] = "P14-SYNTH-C"
    chain = extra["candidate_chain"]
    chain["source"]["source_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-111111111113"
    chain["source_version"]["source_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-111111111113"
    chain["source_version"]["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222224"
    chain["source_version"]["content_sha256"] = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    chain["submission"]["submission_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-333333333335"
    chain["submission"]["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222224"
    chain["submission"]["idempotency_key"] = "p17-preview-003"
    chain["candidate_revision"]["candidate_revision_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-555555555557"
    chain["candidate_revision"]["candidate_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-444444444446"
    chain["candidate_revision"]["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222224"
    chain["candidate_revision"]["submission_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-333333333335"
    chain["candidate_revision"]["proposal_command_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-666666666668"
    chain["candidate_revision"]["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    chain["candidate_revision"]["evidence_span_refs"] = [
        {
            "source_version_id": "aaaaaaaa-bbbb-4ccc-8ddd-222222222224",
            "locator": "bytes:0-31",
        }
    ]
    chain["review_work_item"]["review_work_item_id"] = WORK_C
    chain["review_work_item"]["candidate_revision_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-555555555557"
    chain["review_work_item"]["correlation_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-88888888888a"
    return extra


class OfflineReviewSnapshotDelta(unittest.TestCase):
    def test_identical_two_case_is_unchanged_sorted_and_gated(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = snapshot_delta(payload, payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["delta_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["added_count"], 0)
        self.assertEqual(receipt["removed_or_denied_count"], 0)
        self.assertEqual(receipt["unchanged_count"], 2)
        self.assertEqual(receipt["baseline_eligible_count"], 2)
        self.assertEqual(receipt["current_eligible_count"], 2)
        self.assertEqual(receipt["visible_current_count"], 2)
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["snapshot_authority"], "SNAPSHOT_UNTRUSTED")
        self.assertEqual(receipt["snapshot_order"], "SNAPSHOT_ORDER_NOT_ATTESTED")
        self.assertEqual(receipt["change_authority"], "POSSIBLE_CHANGE_ONLY")
        html_page = receipt["html"]
        self.assertTrue(html_page.startswith("<!DOCTYPE html>"))
        self.assertIn("default-src 'none'", html_page)
        self.assertIn("Nicht autorisiert, nur synthetische Vorschau.", html_page)
        self.assertIn("SNAPSHOT_UNTRUSTED", html_page)
        self.assertIn("POSSIBLE_CHANGE_ONLY", html_page)
        self.assertIn("SNAPSHOT_ORDER_NOT_ATTESTED", html_page)
        self.assertIn("EVENT_WATERMARK_UNKNOWN", html_page)
        self.assertIn(WORK_A, html_page)
        self.assertIn(WORK_B, html_page)
        self.assertLess(html_page.find(WORK_A), html_page.find(WORK_B))
        self.assertNotIn("<script", html_page)
        self.assertNotIn("<form", html_page)
        self.assertNotIn("READY", html_page)
        reversed_entries = {**payload, "entries": list(reversed(payload["entries"]))}
        self.assertEqual(
            html_page,
            snapshot_delta(reversed_entries, reversed_entries, commit="test-commit")["html"],
        )

    def test_cli_stdout_html_from_distinct_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            copy = Path(raw) / "p17-current-copy.json"
            copy.write_text(FIXTURE.read_text(), encoding="utf-8")
            proc = _cli([str(FIXTURE), str(copy), "--commit", "cli-test"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(proc.stdout.startswith("<!DOCTYPE html>"))
            self.assertIn("cli-test", proc.stdout)
            self.assertIn("UNCHANGED_COUNT", proc.stdout)
            self.assertEqual(proc.stderr, "")
            again = _cli([str(FIXTURE), str(copy), "--commit", "cli-test"])
            self.assertEqual(proc.stdout, again.stdout)

    def test_revoked_source_is_count_only_and_absent(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = snapshot_delta(baseline, current, commit="test-commit")
        self.assertEqual(receipt["delta_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["current_eligible_count"], 1)
        self.assertEqual(receipt["removed_or_denied_count"], 1)
        self.assertEqual(receipt["added_count"], 0)
        self.assertEqual(receipt["unchanged_count"], 1)
        blob = _receipt_blob(receipt)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(SOURCE_A, blob)
        self.assertIn(WORK_B, receipt["html"])
        swapped_entries = deepcopy(current)
        swapped_entries["entries"] = list(reversed(swapped_entries["entries"]))
        self.assertEqual(
            receipt["html"],
            snapshot_delta(baseline, swapped_entries, commit="test-commit")["html"],
        )
        swapped_history = snapshot_delta(current, baseline, commit="test-commit")
        self.assertEqual(swapped_history["snapshot_order"], "SNAPSHOT_ORDER_NOT_ATTESTED")
        self.assertEqual(swapped_history["change_authority"], "POSSIBLE_CHANGE_ONLY")
        self.assertIn("SNAPSHOT_ORDER_NOT_ATTESTED", swapped_history["html"])
        self.assertNotIn("ATTESTED_HISTORY", swapped_history["html"])
        self.assertNotIn("REVOKE_PROVEN", swapped_history["html"])

    def test_added_current_item_shows_only_current_ids(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"].append(_third_entry(current))
        receipt = snapshot_delta(baseline, current, commit="test-commit")
        self.assertEqual(receipt["added_count"], 1)
        self.assertEqual(receipt["removed_or_denied_count"], 0)
        self.assertEqual(receipt["current_eligible_count"], 3)
        self.assertIn(WORK_A, receipt["html"])
        self.assertIn(WORK_B, receipt["html"])
        self.assertIn(WORK_C, receipt["html"])

    def test_cross_tenant_in_either_snapshot_denies(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = snapshot_delta(baseline, current, commit="test-commit")
        self.assertEqual(receipt["delta_status"], "DELTA_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertEqual(receipt["card_count"], 0)
        html_page = receipt["html"]
        self.assertIn("DELTA_DENIED", html_page)
        self.assertNotIn("<table>", html_page)
        self.assertNotIn("TENANT_SYNTH_B", html_page)
        self.assertNotIn(WORK_A, html_page)
        self.assertNotIn(WORK_B, _receipt_blob(receipt))
        other = _load()
        other["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = snapshot_delta(other, _load(), commit="test-commit")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertNotIn(WORK_A, receipt["html"])

    def test_duplicate_stale_forged_empty_in_either_snapshot(self) -> None:
        dup = _load()
        dup["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = WORK_A
        receipt = snapshot_delta(_load(), dup, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertEqual(receipt["card_count"], 0)
        self.assertNotIn(WORK_A, receipt["html"])
        receipt = snapshot_delta(dup, _load(), commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        stale = _load()
        extra = deepcopy(stale["entries"][0]["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222229"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        stale["entries"][0]["candidate_chain"]["source_versions"] = [extra]
        receipt = snapshot_delta(_load(), stale, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        self.assertIn(WORK_B, receipt["html"])
        self.assertEqual(receipt["removed_or_denied_count"], 1)
        forged = _load()
        forged["entries"][0]["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        receipt = snapshot_delta(_load(), forged, commit="test-commit")
        self.assertNotIn("forged-reviewer", receipt["html"])
        self.assertNotIn(WORK_A, receipt["html"])
        empty = _load()
        empty["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        receipt = snapshot_delta(_load(), empty, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        pending = _load()
        pending["entries"][0]["candidate_chain"]["source"]["rights_status"] = "PENDING"
        receipt = snapshot_delta(_load(), pending, commit="test-commit")
        self.assertNotIn(WORK_A, receipt["html"])
        self.assertIn(WORK_B, receipt["html"])

    def test_secrets_and_removed_tokens_never_emitted(self) -> None:
        baseline = _load()
        current = _load()
        chain = current["entries"][0]["candidate_chain"]
        chain["source"]["rights_status"] = "REVOKED"
        chain["source_version"]["media_type"] = SECRET_MEDIA
        chain["candidate_revision"]["proposal_payload"]["title"] = SECRET_PURPOSE
        chain["source_version"]["rights_snapshot"]["rights_basis"] = SECRET_RIGHTS
        chain["source"]["external_locator"] = SECRET_LOCATOR
        remain = current["entries"][1]["candidate_chain"]
        remain["source_version"]["media_type"] = SECRET_MEDIA
        remain["candidate_revision"]["proposal_payload"]["title"] = SECRET_PURPOSE
        receipt = snapshot_delta(baseline, current, commit="test-commit")
        blob = _receipt_blob(receipt)
        self.assertEqual(receipt["delta_status"], "PREVIEW_ONLY")
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn("P17_SECRET_MEDIA_", blob)
        self.assertNotIn("P17_SECRET_PURPOSE_", blob)
        self.assertNotIn("P17_SECRET_RIGHTS_", blob)
        self.assertNotIn("P17_SECRET_LOCATOR_", blob)
        self.assertNotIn("<script", blob)
        self.assertNotIn("javascript:", blob)
        self.assertNotIn("https://evil.example", blob)
        self.assertNotIn("onerror=", blob)
        self.assertNotIn("media_type", receipt["html"])

    def test_duplicate_json_same_path_untrusted_commit_and_output(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            snapshot_delta_files(DUP_TOP, FIXTURE)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP), str(FIXTURE)])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "DUPLICATE_JSON_KEY")
        same = _cli([str(FIXTURE), str(FIXTURE)])
        self.assertEqual(same.returncode, 2)
        self.assertEqual(json.loads(same.stdout)["parse_error"], "SAME_SNAPSHOT_PATH")
        with self.assertRaises(PreviewParseError) as commit_err:
            snapshot_delta(_load(), _load(), commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")
        with self.assertRaises(PreviewParseError) as escaped:
            write_workbench_html("<!DOCTYPE html>", "/tmp/kdb-p17-escape.html")
        self.assertEqual(escaped.exception.code, "PATH_ESCAPE_DENIED")
        with self.assertRaises(PreviewParseError) as networked:
            write_workbench_html("<!DOCTYPE html>", "https://example.invalid/x.html")
        self.assertEqual(networked.exception.code, "NETWORK_PATH_DENIED")
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            dest = Path(raw) / "kdb-p17-delta-test.html"
            relative = dest.relative_to(REPO)
            written = write_workbench_html("<!DOCTYPE html>\n", relative)
            self.assertEqual(written.read_text(encoding="utf-8"), "<!DOCTYPE html>\n")
            with self.assertRaises(PreviewParseError) as exists:
                write_workbench_html("<!DOCTYPE html>\n", relative)
            self.assertEqual(exists.exception.code, "OUTPUT_EXISTS")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_snapshot_delta"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_workbench"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
