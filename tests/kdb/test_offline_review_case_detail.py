"""P15 offline review case-detail tests. No SQL write, n8n, or hosted apply."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_case_detail import (  # noqa: E402
    PACKET,
    case_detail,
    case_detail_file,
)
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
P13 = REPO / "tests" / "kdb" / "fixtures" / "p13_preview_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
MALFORMED = REPO / "tests" / "kdb" / "fixtures" / "p14_malformed.json"
CLI = REPO / "services" / "kdb" / "offline_review_case_detail_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
WORK_A = "aaaaaaaa-bbbb-4ccc-8ddd-777777777777"
WORK_B = "aaaaaaaa-bbbb-4ccc-8ddd-777777777778"
UNKNOWN = "00000000-0000-4000-8000-000000000000"
SECRET_MEDIA = "P15_SECRET_MEDIA_c1a9"
SECRET_PURPOSE = "P15_SECRET_PURPOSE_b7e2"
SECRET_RIGHTS = "P15_SECRET_RIGHTS_d4f0"
SECRET_LOCATOR = "P15_SECRET_LOCATOR_aa11"
SECRET_COMMIT = "P15_SECRET_COMMIT\nwhoami"
GIANT = "A" * 4096


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def _p13() -> dict:
    return json.loads(P13.read_text())


def _cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


def _canonical(receipt: dict) -> str:
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"))


def _rewrite(entry: dict, mapping: dict[str, str]) -> dict:
    text = json.dumps(entry)
    for old, new in mapping.items():
        text = text.replace(old, new)
    return json.loads(text)


class OfflineReviewCaseDetail(unittest.TestCase):
    def test_select_first_and_second_detail_only(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        first = case_detail(payload, WORK_A, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(first["packet"], PACKET)
        self.assertEqual(first["detail_status"], "DETAIL_ONLY")
        self.assertEqual(first["snapshot_authority"], "SNAPSHOT_UNTRUSTED")
        self.assertEqual(first["assignment"], "NOT_ASSIGNED")
        self.assertEqual(first["final_authority"], "NOT_ADMITTED")
        self.assertEqual(first["execution"], "NON_EXECUTABLE")
        self.assertEqual(first["c04_human_decision"], "NOT_WRITTEN")
        self.assertEqual(first["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(first["outbox"], "NOT_EMITTED")
        self.assertEqual(first["logical_objects_claimed"], "NOT_18_OF_18")
        detail = first["detail"]
        self.assertEqual(detail["review_work_item_id"], WORK_A)
        self.assertEqual(detail["work_item_state"], "REQUESTED")
        self.assertEqual(detail["review_queue"], "KDB_HUMAN_REVIEW")
        self.assertEqual(detail["evidence_span_count"], 1)
        self.assertEqual(detail["provenance_trace"]["declared_sha"], "NOT_VERIFIED")
        self.assertEqual(detail["provenance_trace"]["event_watermark"], "UNKNOWN")
        self.assertIn("CONTENT_SHA_OPAQUE_UNPROVEN", detail["explicit_gaps"])
        self.assertNotIn("media_type", detail)
        self.assertNotIn("external_locator", detail)
        self.assertNotIn("proposal_payload", detail)
        second = case_detail(payload, WORK_B, commit="test-commit")
        self.assertEqual(second["detail"]["review_work_item_id"], WORK_B)
        self.assertNotEqual(first["detail"]["source_id"], second["detail"]["source_id"])
        blob = json.dumps(first)
        self.assertNotIn("READY", blob)
        self.assertNotIn("synthetic://", blob)

    def test_cli_and_permutation_stable(self) -> None:
        proc = _cli([str(FIXTURE), "--work-item-id", WORK_A, "--commit", "cli-test"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["detail_status"], "DETAIL_ONLY")
        self.assertEqual(receipt["source_commit"], "cli-test")
        self.assertEqual(receipt["source_commit_attestation"], "LABEL_NOT_ATTESTED")
        self.assertEqual(proc.stderr, "")
        again = _cli([str(FIXTURE), "--work-item-id", WORK_A, "--commit", "cli-test"])
        self.assertEqual(proc.stdout, again.stdout)
        payload = _load()
        reversed_entries = {**payload, "entries": list(reversed(payload["entries"]))}
        self.assertEqual(
            _canonical(case_detail(payload, WORK_B, commit="test-commit")),
            _canonical(case_detail(reversed_entries, WORK_B, commit="test-commit")),
        )

    def test_unknown_and_invalid_selector_not_echoed(self) -> None:
        receipt = case_detail(_load(), UNKNOWN, commit="test-commit")
        self.assertEqual(receipt["detail_status"], "DETAIL_DENIED")
        self.assertEqual(receipt["deny_code"], "WORK_ITEM_NOT_SELECTABLE")
        self.assertIsNone(receipt["detail"])
        self.assertNotIn(UNKNOWN, json.dumps(receipt))
        with self.assertRaises(PreviewParseError) as caught:
            case_detail(_load(), GIANT, commit="test-commit")
        self.assertEqual(caught.exception.code, "INVALID_WORK_ITEM_ID")
        proc = _cli([str(FIXTURE), "--work-item-id", GIANT])
        self.assertEqual(proc.returncode, 2)
        blob = proc.stdout + proc.stderr
        self.assertNotIn(GIANT, blob)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "INVALID_WORK_ITEM_ID")
        proc = _cli([str(FIXTURE), "--work-item-id", "../../etc/passwd"])
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("etc/passwd", proc.stdout + proc.stderr)

    def test_cross_tenant_batch_denies_selection(self) -> None:
        payload = _load()
        payload["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = case_detail(payload, WORK_A, commit="test-commit")
        self.assertEqual(receipt["detail_status"], "DETAIL_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertIsNone(receipt["detail"])
        blob = json.dumps(receipt)
        self.assertNotIn("TENANT_SYNTH_B", blob)
        self.assertNotIn(WORK_A, blob)

    def test_revoked_source_not_selectable_other_source_is(self) -> None:
        payload = _load()
        payload["entries"][0]["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        denied = case_detail(payload, WORK_A, commit="test-commit")
        self.assertEqual(denied["deny_code"], "WORK_ITEM_NOT_SELECTABLE")
        self.assertIsNone(denied["detail"])
        self.assertNotIn(WORK_A, json.dumps(denied))
        allowed = case_detail(payload, WORK_B, commit="test-commit")
        self.assertEqual(allowed["detail_status"], "DETAIL_ONLY")
        self.assertEqual(allowed["detail"]["review_work_item_id"], WORK_B)

    def test_duplicate_work_item_and_stale_and_forged(self) -> None:
        dup = _load()
        dup["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = WORK_A
        receipt = case_detail(dup, WORK_A, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertIsNone(receipt["detail"])
        stale = _load()
        extra = deepcopy(stale["entries"][0]["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222229"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        stale["entries"][0]["candidate_chain"]["source_versions"] = [extra]
        receipt = case_detail(stale, WORK_A, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "WORK_ITEM_NOT_SELECTABLE")
        self.assertIsNone(receipt["detail"])
        still = case_detail(stale, WORK_B, commit="test-commit")
        self.assertEqual(still["detail_status"], "DETAIL_ONLY")
        forged = _load()
        forged["entries"][0]["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        receipt = case_detail(forged, WORK_A, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "WORK_ITEM_NOT_SELECTABLE")
        self.assertNotIn("forged-reviewer", json.dumps(receipt))

    def test_empty_evidence_and_secrets_never_printed(self) -> None:
        empty = _load()
        empty["entries"][0]["candidate_chain"]["candidate_revision"]["evidence_span_refs"] = []
        receipt = case_detail(empty, WORK_A, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "WORK_ITEM_NOT_SELECTABLE")
        self.assertIsNone(receipt["detail"])
        payload = _load()
        chain = payload["entries"][0]["candidate_chain"]
        chain["source_version"]["media_type"] = SECRET_MEDIA
        chain["submission"]["purpose"] = SECRET_PURPOSE
        chain["source_version"]["rights_snapshot"]["rights_basis"] = SECRET_RIGHTS
        chain["source_version"]["rights_snapshot"]["allowed_purposes"] = [SECRET_PURPOSE]
        chain["source"]["external_locator"] = SECRET_LOCATOR
        receipt = case_detail(payload, WORK_A, commit="test-commit")
        self.assertEqual(receipt["detail_status"], "DETAIL_ONLY")
        blob = json.dumps(receipt)
        self.assertNotIn(SECRET_MEDIA, blob)
        self.assertNotIn(SECRET_PURPOSE, blob)
        self.assertNotIn(SECRET_RIGHTS, blob)
        self.assertNotIn(SECRET_LOCATOR, blob)
        self.assertNotIn("media_type", blob)

    def test_duplicate_json_untrusted_commit_malformed(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            case_detail_file(DUP_TOP, WORK_A)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP), "--work-item-id", WORK_A])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "DUPLICATE_JSON_KEY")
        with self.assertRaises(PreviewParseError) as commit_err:
            case_detail(_load(), WORK_A, commit=SECRET_COMMIT)
        self.assertEqual(commit_err.exception.code, "INVALID_COMMIT_LABEL")
        proc = _cli([str(FIXTURE), "--work-item-id", WORK_A, "--commit", SECRET_COMMIT])
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("whoami", proc.stdout + proc.stderr)
        with self.assertRaises(PreviewParseError) as malformed:
            case_detail_file(MALFORMED, WORK_A)
        self.assertEqual(malformed.exception.code, "MALFORMED_JSON")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_case_detail"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_inbox_readmodel"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
