"""P13 offline review-handoff preview tests. No SQL write, n8n, or hosted apply."""
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
from review_handoff_preview import (  # noqa: E402
    MAX_CHARS,
    PACKET,
    REPAIR_PACKET,
    PreviewParseError,
    preview,
    preview_file,
)

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p13_preview_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p13_duplicate_top.json"
DUP_NEST = REPO / "tests" / "kdb" / "fixtures" / "p13_duplicate_nested.json"
MALFORMED = REPO / "tests" / "kdb" / "fixtures" / "p13_malformed.json"
CLI = REPO / "services" / "kdb" / "review_handoff_preview_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
SECRET_MEDIA = "P13R_SECRET_MEDIA_9f3c2a1b"
SECRET_COMMIT = "P13R_SECRET_COMMIT\nwhoami"


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
        self.assertEqual(receipt["repair_packet"], REPAIR_PACKET)
        self.assertEqual(receipt["preview_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["source_commit_attestation"], "LABEL_NOT_ATTESTED")
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
        self.assertNotIn("media_type", card)
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
        self.assertEqual(receipt["source_commit_attestation"], "LABEL_NOT_ATTESTED")
        self.assertNotIn("media_type", receipt["queue_card"])
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

    def test_duplicate_json_keys_rejected(self) -> None:
        with self.assertRaises(PreviewParseError) as top:
            preview_file(DUP_TOP)
        self.assertEqual(top.exception.code, "DUPLICATE_JSON_KEY")
        with self.assertRaises(PreviewParseError) as nested:
            preview_file(DUP_NEST)
        self.assertEqual(nested.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP)])
        self.assertEqual(proc.returncode, 2)
        error = json.loads(proc.stdout)
        self.assertEqual(error["parse_error"], "DUPLICATE_JSON_KEY")
        self.assertEqual(error["final_authority"], "NOT_ADMITTED")
        self.assertIsNone(error.get("queue_card"))
        self.assertEqual(proc.stderr, "")

    def test_malicious_media_type_not_copied_to_card(self) -> None:
        payload = _load()
        payload["candidate_chain"]["source_version"]["media_type"] = SECRET_MEDIA
        receipt = preview(payload)
        self.assertEqual(receipt["preview_status"], "PREVIEW_ONLY")
        self.assertNotIn("media_type", receipt["queue_card"])
        blob = json.dumps(receipt) + json.dumps(receipt["queue_card"])
        self.assertNotIn(SECRET_MEDIA, blob)

    def test_untrusted_commit_label_rejected(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            preview(_load(), commit=SECRET_COMMIT)
        self.assertEqual(caught.exception.code, "INVALID_COMMIT_LABEL")
        proc = _cli([str(FIXTURE), "--commit", SECRET_COMMIT])
        self.assertEqual(proc.returncode, 2)
        blob = proc.stdout + proc.stderr
        self.assertNotIn(SECRET_COMMIT, blob)
        self.assertNotIn("whoami", blob)
        error = json.loads(proc.stdout)
        self.assertEqual(error["parse_error"], "INVALID_COMMIT_LABEL")
        self.assertEqual(error["final_authority"], "NOT_ADMITTED")

    def test_oversized_deep_huge_int_and_malformed(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            tmp = Path(raw)
            huge = tmp / "oversized.json"
            huge.write_text("{" + ("a" * (MAX_CHARS + 8)), encoding="utf-8")
            with self.assertRaises(PreviewParseError) as oversized:
                preview_file(huge)
            self.assertEqual(oversized.exception.code, "INPUT_TOO_LARGE")
            deep = {"candidate_chain": {}}
            cursor = deep["candidate_chain"]
            for index in range(10):
                cursor["n"] = {}
                cursor = cursor["n"]
            deep_path = tmp / "deep.json"
            deep_path.write_text(
                json.dumps(
                    {
                        "case_id": "P13-DEEP",
                        "expected_tenant_scope": "TENANT_SYNTH_A",
                        **deep,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PreviewParseError) as deep_err:
                preview_file(deep_path)
            self.assertEqual(deep_err.exception.code, "INPUT_TOO_DEEP")
            huge_int = tmp / "hugeint.json"
            huge_int.write_text(
                '{"case_id":"P13-HUGE","expected_tenant_scope":"TENANT_SYNTH_A",'
                '"candidate_chain":{"n":111111111111111111111}}',
                encoding="utf-8",
            )
            with self.assertRaises(PreviewParseError) as huge_err:
                preview_file(huge_int)
            self.assertEqual(huge_err.exception.code, "HUGE_INTEGER")
        with self.assertRaises(PreviewParseError) as malformed:
            preview_file(MALFORMED)
        self.assertEqual(malformed.exception.code, "MALFORMED_JSON")
        proc = _cli([str(MALFORMED)])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "MALFORMED_JSON")
        self.assertEqual(proc.stderr, "")

    def test_path_escape_symlink_and_missing(self) -> None:
        with self.assertRaises(PreviewParseError) as escaped:
            preview_file("/etc/hosts")
        self.assertEqual(escaped.exception.code, "PATH_ESCAPE_DENIED")
        with self.assertRaises(PreviewParseError) as missing:
            preview_file(FIXTURE.parent / "p13_missing_no_such_file.json")
        self.assertEqual(missing.exception.code, "MISSING_INPUT_FILE")
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            link = Path(raw) / "escape.json"
            link.symlink_to(FIXTURE)
            with self.assertRaises(PreviewParseError) as linked:
                preview_file(link)
            self.assertEqual(linked.exception.code, "SYMLINK_DENIED")
        proc = _cli(["https://example.invalid/preview.json"])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["parse_error"], "NETWORK_PATH_DENIED")
        self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
