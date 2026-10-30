"""P19 versioned offline review viewmodel tests. No SQL write, n8n, or hosted apply."""
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
    DEMO_ROOT,
    FIXED_FILES,
    demo_pack,
    write_demo_pack,
)
from offline_review_viewmodel import (  # noqa: E402
    PACKET,
    SCHEMA_VERSION,
    validate_viewmodel,
    viewmodel,
    viewmodel_files,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
CLI = REPO / "services" / "kdb" / "offline_review_viewmodel_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
WORK_C = "aaaaaaaa-bbbb-4ccc-8ddd-777777777779"
SOURCE_A = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
SECRET_MEDIA = "P19_SECRET_MEDIA_<script>alert(1)</script>"
SECRET_PURPOSE = "P19_SECRET_PURPOSE_javascript:alert(1)"
SECRET_RIGHTS = 'P19_SECRET_RIGHTS_" onerror="alert(1)'
SECRET_LOCATOR = "P19_SECRET_LOCATOR_https://evil.example/x"
SECRET_COMMIT = "P19_SECRET_COMMIT\nwhoami"


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


def _blob(model: dict) -> str:
    return json.dumps(model, sort_keys=True)


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
    chain["submission"]["idempotency_key"] = "p19-preview-003"
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


class OfflineReviewViewmodel(unittest.TestCase):
    def test_identical_two_case_is_sorted_gated_and_schema_valid(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        model = viewmodel(payload, deepcopy(payload), commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(model["packet"], PACKET)
        self.assertEqual(model["schema_version"], SCHEMA_VERSION)
        self.assertEqual(model["kind"], "KDB_REVIEW_OFFLINE_PREVIEW")
        self.assertTrue(model["internal_only"])
        self.assertTrue(model["non_normative"])
        self.assertEqual(model["viewmodel_status"], "PREVIEW_ONLY")
        self.assertIsNone(model["deny_code"])
        self.assertEqual(model["unchanged_count"], 2)
        self.assertEqual(model["added_count"], 0)
        self.assertEqual(model["removed_or_denied_count"], 0)
        self.assertEqual(model["assignment"], "NOT_ASSIGNED")
        self.assertEqual(model["final_authority"], "NOT_ADMITTED")
        self.assertEqual(model["snapshot_authority"], "SNAPSHOT_UNTRUSTED")
        self.assertEqual(len(model["current_cases"]), 2)
        self.assertEqual(model["current_cases"][0]["review_work_item_id"], WORK_A)
        self.assertEqual(model["current_cases"][1]["review_work_item_id"], WORK_B)
        self.assertNotIn("READY", _blob(model))
        validate_viewmodel(model)
        reversed_entries = {**payload, "entries": list(reversed(payload["entries"]))}
        again = viewmodel(reversed_entries, deepcopy(reversed_entries), commit="test-commit")
        self.assertEqual(_blob(model), _blob(again))

    def test_cli_stdout_json_without_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            copy = Path(raw) / "p19-current-copy.json"
            copy.write_text(FIXTURE.read_text(), encoding="utf-8")
            proc = _cli([str(FIXTURE), str(copy), "--commit", "cli-test"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            model = json.loads(proc.stdout)
            self.assertEqual(model["viewmodel_status"], "PREVIEW_ONLY")
            self.assertEqual(model["unchanged_count"], 2)
            self.assertEqual(model["source_commit"], "cli-test")
            self.assertEqual(proc.stderr, "")
            self.assertFalse(any(DEMO_ROOT.glob("cli-test*")))
            again = _cli([str(FIXTURE), str(copy), "--commit", "cli-test"])
            self.assertEqual(proc.stdout, again.stdout)

    def test_revoked_source_is_count_only_and_absent(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        model = viewmodel(baseline, current, commit="test-commit")
        self.assertEqual(model["viewmodel_status"], "PREVIEW_ONLY")
        self.assertEqual(model["current_eligible_count"], 1)
        self.assertEqual(model["removed_or_denied_count"], 1)
        self.assertEqual(model["unchanged_count"], 1)
        blob = _blob(model)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(SOURCE_A, blob)
        self.assertEqual(len(model["current_cases"]), 1)
        self.assertEqual(model["current_cases"][0]["review_work_item_id"], WORK_B)
        swapped = deepcopy(current)
        swapped["entries"] = list(reversed(swapped["entries"]))
        self.assertEqual(_blob(model), _blob(viewmodel(baseline, swapped, commit="test-commit")))

    def test_added_current_item_shows_only_current_ids(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"].append(_third_entry(current))
        model = viewmodel(baseline, current, commit="test-commit")
        self.assertEqual(model["added_count"], 1)
        self.assertEqual(model["current_eligible_count"], 3)
        ids = [item["review_work_item_id"] for item in model["current_cases"]]
        self.assertEqual(ids, [WORK_A, WORK_B, WORK_C])

    def test_cross_tenant_denied_has_empty_cases(self) -> None:
        baseline = _load()
        current = _load()
        current["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        model = viewmodel(baseline, current, commit="test-commit")
        self.assertEqual(model["viewmodel_status"], "DEMO_DENIED")
        self.assertEqual(model["deny_code"], "CROSS_TENANT")
        self.assertEqual(model["current_cases"], [])
        self.assertEqual(model["visible_current_count"], 0)
        self.assertNotIn("tenant_scope", model)
        blob = _blob(model)
        self.assertNotIn("TENANT_SYNTH_B", blob)
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn(WORK_B, blob)

    def test_duplicate_stale_forged_empty_in_either_snapshot(self) -> None:
        dup = _load()
        dup["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = WORK_A
        model = viewmodel(_load(), dup, commit="test-commit")
        self.assertEqual(model["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertEqual(model["current_cases"], [])
        self.assertNotIn(WORK_A, _blob(model))
        stale = _load()
        extra = deepcopy(stale["entries"][0]["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222229"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        stale["entries"][0]["candidate_chain"]["source_versions"] = [extra]
        model = viewmodel(_load(), stale, commit="test-commit")
        self.assertNotIn(WORK_A, _blob(model))
        self.assertEqual(model["current_cases"][0]["review_work_item_id"], WORK_B)
        forged = _load()
        forged["entries"][0]["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        model = viewmodel(_load(), forged, commit="test-commit")
        self.assertNotIn("forged-reviewer", _blob(model))
        self.assertNotIn(WORK_A, _blob(model))
        empty = _load()
        empty["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        model = viewmodel(_load(), empty, commit="test-commit")
        self.assertNotIn(WORK_A, _blob(model))
        pending = _load()
        pending["entries"][0]["candidate_chain"]["source"]["rights_status"] = "PENDING"
        model = viewmodel(_load(), pending, commit="test-commit")
        self.assertNotIn(WORK_A, _blob(model))
        self.assertEqual(model["current_cases"][0]["review_work_item_id"], WORK_B)

    def test_secrets_never_enter_the_viewmodel(self) -> None:
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
        model = viewmodel(baseline, current, commit="test-commit")
        blob = _blob(model)
        self.assertEqual(model["viewmodel_status"], "PREVIEW_ONLY")
        self.assertNotIn(WORK_A, blob)
        self.assertNotIn("P19_SECRET_MEDIA_", blob)
        self.assertNotIn("P19_SECRET_PURPOSE_", blob)
        self.assertNotIn("P19_SECRET_RIGHTS_", blob)
        self.assertNotIn("P19_SECRET_LOCATOR_", blob)
        self.assertNotIn("javascript:", blob)
        self.assertNotIn("https://evil.example", blob)
        self.assertNotIn("onerror=", blob)
        self.assertNotIn("media_type", blob)
        self.assertNotIn("rights_basis", blob)

    def test_additional_properties_are_rejected(self) -> None:
        model = viewmodel(_load(), _load(), commit="test-commit")
        extra = deepcopy(model)
        extra["unexpected"] = True
        with self.assertRaises(PreviewParseError) as caught:
            validate_viewmodel(extra)
        self.assertEqual(caught.exception.code, "SCHEMA_INVALID")
        case_extra = deepcopy(model)
        case_extra["current_cases"][0]["locator"] = "bytes:0-31"
        with self.assertRaises(PreviewParseError) as case_err:
            validate_viewmodel(case_extra)
        self.assertEqual(case_err.exception.code, "SCHEMA_INVALID")

    def test_six_file_demo_pack_hashes_viewmodel(self) -> None:
        payload = _load()
        receipt = demo_pack(payload, deepcopy(payload), commit="test-commit")
        self.assertEqual(len(FIXED_FILES), 6)
        self.assertIn("review-viewmodel.json", receipt["artifacts"])
        self.assertIn("review-viewmodel.json", receipt["file_sha256"])
        name = "p19-unit-pack"
        leftover = DEMO_ROOT / name
        if leftover.exists():
            for child in leftover.iterdir():
                child.unlink()
            leftover.rmdir()
        out = Path("tests/kdb/demo-artifacts") / name
        try:
            written = write_demo_pack(receipt["artifacts"], out)
            names = sorted(path.name for path in written.iterdir())
            self.assertEqual(names, sorted(FIXED_FILES))
            for filename, digest in receipt["file_sha256"].items():
                data = (written / filename).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            packed = json.loads((written / "review-viewmodel.json").read_text())
            self.assertEqual(packed["kind"], "KDB_REVIEW_OFFLINE_PREVIEW")
            self.assertEqual(len(packed["current_cases"]), 2)
        finally:
            target = DEMO_ROOT / name
            if target.exists():
                for child in target.iterdir():
                    child.unlink()
                target.rmdir()

    def test_duplicate_json_same_path_and_untrusted_commit(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            viewmodel_files(DUP_TOP, FIXTURE)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP), str(FIXTURE)])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "DUPLICATE_JSON_KEY")
        same = _cli([str(FIXTURE), str(FIXTURE)])
        self.assertEqual(same.returncode, 2)
        self.assertEqual(json.loads(same.stdout)["parse_error"], "SAME_SNAPSHOT_PATH")
        with self.assertRaises(PreviewParseError) as commit_err:
            viewmodel(_load(), _load(), commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_viewmodel"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_demo_pack"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
