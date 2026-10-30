"""P14 offline review-inbox read-model tests. No SQL write, n8n, or hosted apply."""
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
from offline_review_inbox import (  # noqa: E402
    MAX_CHARS,
    PACKET,
    inbox,
    inbox_file,
)
from review_handoff_preview import MAX_CHARS as PREVIEW_MAX_CHARS  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p14_inbox_two_eligible.json"
P13 = REPO / "tests" / "kdb" / "fixtures" / "p13_preview_eligible.json"
DUP_TOP = REPO / "tests" / "kdb" / "fixtures" / "p14_duplicate_top.json"
MALFORMED = REPO / "tests" / "kdb" / "fixtures" / "p14_malformed.json"
CLI = REPO / "services" / "kdb" / "offline_review_inbox_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
SECRET_MEDIA = "P14_SECRET_MEDIA_c1a9"
SECRET_PURPOSE = "P14_SECRET_PURPOSE_b7e2"
SECRET_RIGHTS = "P14_SECRET_RIGHTS_d4f0"
SECRET_LOCATOR = "P14_SECRET_LOCATOR_aa11"
SECRET_COMMIT = "P14_SECRET_COMMIT\nwhoami"


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


class OfflineReviewInbox(unittest.TestCase):
    def test_two_eligible_sorted_preview_only_still_not_admitted(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = inbox(payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["packet"], PACKET)
        self.assertEqual(receipt["inbox_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["snapshot_authority"], "SNAPSHOT_UNTRUSTED")
        self.assertEqual(receipt["read_model"], "NON_NORMATIVE_INTERNAL_PREVIEW")
        self.assertEqual(receipt["assignment"], "NOT_ASSIGNED")
        self.assertEqual(receipt["publication"], "NOT_PUBLISHED")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["execution"], "NON_EXECUTABLE")
        self.assertEqual(receipt["db_write"], "NOT_ADMITTED")
        self.assertEqual(receipt["c04_human_decision"], "NOT_WRITTEN")
        self.assertEqual(receipt["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(receipt["outbox"], "NOT_EMITTED")
        self.assertEqual(receipt["logical_objects_claimed"], "NOT_18_OF_18")
        self.assertEqual(receipt["hosted_verified"], "HOSTED_VERIFIED_NO")
        self.assertEqual(receipt["source_commit_attestation"], "LABEL_NOT_ATTESTED")
        self.assertEqual(receipt["card_count"], 2)
        self.assertEqual(receipt["deny_count"], 0)
        ids = [card["review_work_item_id"] for card in receipt["cards"]]
        self.assertEqual(ids, sorted(ids))
        self.assertNotIn("READY", json.dumps(receipt))
        for card in receipt["cards"]:
            self.assertNotIn("media_type", card)
            self.assertNotIn("external_locator", card)
            self.assertNotIn("proposal_payload", card)
            self.assertNotIn("rights_basis", card)
            self.assertEqual(card["review_queue"], "KDB_HUMAN_REVIEW")

    def test_cli_redacted_and_deterministic(self) -> None:
        proc = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["inbox_status"], "PREVIEW_ONLY")
        self.assertEqual(receipt["card_count"], 2)
        self.assertEqual(receipt["source_commit"], "cli-test")
        blob = proc.stdout + proc.stderr
        self.assertNotIn("synthetic://", blob)
        self.assertNotIn("KNOWLEDGE_INTAKE", blob)
        self.assertNotIn("synthetic-candidate", blob)
        self.assertEqual(proc.stderr, "")
        again = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.stdout, again.stdout)

    def test_permutation_and_conflict_order_invariance(self) -> None:
        payload = _load()
        reversed_entries = {
            **payload,
            "entries": list(reversed(payload["entries"])),
        }
        left = _canonical(inbox(payload, commit="test-commit"))
        right = _canonical(inbox(reversed_entries, commit="test-commit"))
        self.assertEqual(left, right)
        mixed = _load()
        revoked = deepcopy(mixed["entries"][1])
        revoked["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        mixed["entries"][1] = revoked
        swapped = {
            **mixed,
            "entries": list(reversed(mixed["entries"])),
        }
        self.assertEqual(
            _canonical(inbox(mixed, commit="test-commit")),
            _canonical(inbox(swapped, commit="test-commit")),
        )

    def test_revocation_wins_same_source_regardless_of_order(self) -> None:
        base = _p13()
        admitted = deepcopy(base)
        revoked = deepcopy(base)
        revoked["case_id"] = "P14-REV"
        revoked = _rewrite(
            revoked,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222230",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333340",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444450",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555560",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-666666666670",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-777777777780",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-888888888890",
            },
        )
        revoked["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        envelope = {
            "snapshot_case_id": "P14-REVOKE-WINS",
            "tenant_scope": "TENANT_SYNTH_A",
            "entries": [admitted, revoked],
        }
        receipt = inbox(envelope, commit="test-commit")
        self.assertEqual(receipt["card_count"], 0)
        self.assertEqual(receipt["inbox_status"], "PREVIEW_EMPTY")
        self.assertEqual(receipt["deny_counts"], [{"code": "REVOKED_SOURCE", "count": 2}])
        reversed_env = {**envelope, "entries": list(reversed(envelope["entries"]))}
        self.assertEqual(
            _canonical(inbox(envelope, commit="test-commit")),
            _canonical(inbox(reversed_env, commit="test-commit")),
        )

    def test_mixed_eligible_revoked_pending_stale_forged(self) -> None:
        eligible = _p13()
        revoked = deepcopy(eligible)
        revoked["case_id"] = "P14-MIX-REV"
        revoked = _rewrite(
            revoked,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-111111111111": "aaaaaaaa-bbbb-4ccc-8ddd-111111111113",
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222224",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333335",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444446",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555557",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-666666666668",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-777777777779",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-88888888888a",
            },
        )
        revoked["candidate_chain"]["source"]["rights_status"] = "REVOKED"
        pending = deepcopy(eligible)
        pending["case_id"] = "P14-MIX-PEND"
        pending = _rewrite(
            pending,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-111111111111": "aaaaaaaa-bbbb-4ccc-8ddd-111111111114",
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222225",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333336",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444447",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555558",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-666666666669",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-77777777777a",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-88888888888b",
            },
        )
        pending["candidate_chain"]["source"]["rights_status"] = "PENDING"
        stale = deepcopy(eligible)
        stale["case_id"] = "P14-MIX-STALE"
        stale = _rewrite(
            stale,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-111111111111": "aaaaaaaa-bbbb-4ccc-8ddd-111111111115",
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222226",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333337",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444448",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555559",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-66666666666a",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-77777777777b",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-88888888888c",
            },
        )
        extra = deepcopy(stale["candidate_chain"]["source_version"])
        extra["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222229"
        extra["source_version_no"] = 2
        extra["content_sha256"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        stale["candidate_chain"]["source_versions"] = [extra]
        forged = deepcopy(eligible)
        forged["case_id"] = "P14-MIX-FORGE"
        forged = _rewrite(
            forged,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-111111111111": "aaaaaaaa-bbbb-4ccc-8ddd-111111111116",
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222227",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333338",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444449",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-55555555555a",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-66666666666b",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-77777777777c",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-88888888888d",
            },
        )
        forged["candidate_chain"]["assigned_reviewer"] = "forged-reviewer"
        envelope = {
            "snapshot_case_id": "P14-MIXED",
            "tenant_scope": "TENANT_SYNTH_A",
            "entries": [forged, stale, pending, revoked, eligible],
        }
        receipt = inbox(envelope, commit="test-commit")
        self.assertEqual(receipt["card_count"], 1)
        self.assertEqual(receipt["deny_count"], 4)
        self.assertEqual(
            receipt["cards"][0]["review_work_item_id"],
            "aaaaaaaa-bbbb-4ccc-8ddd-777777777777",
        )
        codes = {item["code"] for item in receipt["deny_counts"]}
        self.assertEqual(
            codes,
            {"REVOKED_SOURCE", "MISSING_RIGHTS", "STALE_SOURCE_VERSION", "FORGED_REVIEWER_CLAIM"},
        )
        blob = json.dumps(receipt)
        self.assertNotIn("forged-reviewer", blob)
        self.assertNotIn("READY", blob)

    def test_duplicate_work_item_and_candidate_revision_deny_batch(self) -> None:
        payload = _load()
        dup_work = deepcopy(payload)
        dup_work["entries"][1]["candidate_chain"]["review_work_item"]["review_work_item_id"] = (
            dup_work["entries"][0]["candidate_chain"]["review_work_item"]["review_work_item_id"]
        )
        receipt = inbox(dup_work, commit="test-commit")
        self.assertEqual(receipt["inbox_status"], "INBOX_DENIED")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_WORK_ITEM")
        self.assertEqual(receipt["cards"], [])
        dup_rev = deepcopy(payload)
        dup_rev["entries"][1]["candidate_chain"]["candidate_revision"]["candidate_revision_id"] = (
            dup_rev["entries"][0]["candidate_chain"]["candidate_revision"]["candidate_revision_id"]
        )
        receipt = inbox(dup_rev, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "DUPLICATE_CANDIDATE_REVISION")
        self.assertEqual(receipt["cards"], [])

    def test_cross_tenant_whole_batch_no_leak(self) -> None:
        payload = _load()
        payload["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = inbox(payload, commit="test-commit")
        self.assertEqual(receipt["inbox_status"], "INBOX_DENIED")
        self.assertEqual(receipt["deny_code"], "CROSS_TENANT")
        self.assertEqual(receipt["cards"], [])
        blob = json.dumps(receipt)
        self.assertNotIn("TENANT_SYNTH_B", blob)
        self.assertEqual(receipt["tenant_scope"], "TENANT_SYNTH_A")
        self.assertEqual(receipt["card_count"], 0)

    def test_conflicting_rights_and_mixed_timestamps(self) -> None:
        admitted = _p13()
        pending = deepcopy(admitted)
        pending["case_id"] = "P14-CONFLICT"
        pending = _rewrite(
            pending,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222231",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333341",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444451",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555561",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-666666666671",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-777777777781",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-888888888891",
            },
        )
        pending["candidate_chain"]["source"]["rights_status"] = "PENDING"
        conflict = {
            "snapshot_case_id": "P14-CONFLICT-RIGHTS",
            "tenant_scope": "TENANT_SYNTH_A",
            "entries": [admitted, pending],
        }
        receipt = inbox(conflict, commit="test-commit")
        self.assertEqual(receipt["cards"], [])
        self.assertEqual(receipt["deny_counts"][0]["code"], "CONFLICTED_SOURCE_RIGHTS")
        stamped = _p13()
        other = deepcopy(stamped)
        other["case_id"] = "P14-TS"
        other = _rewrite(
            other,
            {
                "aaaaaaaa-bbbb-4ccc-8ddd-222222222222": "aaaaaaaa-bbbb-4ccc-8ddd-222222222232",
                "aaaaaaaa-bbbb-4ccc-8ddd-333333333333": "aaaaaaaa-bbbb-4ccc-8ddd-333333333342",
                "aaaaaaaa-bbbb-4ccc-8ddd-444444444444": "aaaaaaaa-bbbb-4ccc-8ddd-444444444452",
                "aaaaaaaa-bbbb-4ccc-8ddd-555555555555": "aaaaaaaa-bbbb-4ccc-8ddd-555555555562",
                "aaaaaaaa-bbbb-4ccc-8ddd-666666666666": "aaaaaaaa-bbbb-4ccc-8ddd-666666666672",
                "aaaaaaaa-bbbb-4ccc-8ddd-777777777777": "aaaaaaaa-bbbb-4ccc-8ddd-777777777782",
                "aaaaaaaa-bbbb-4ccc-8ddd-888888888888": "aaaaaaaa-bbbb-4ccc-8ddd-888888888892",
            },
        )
        stamped["candidate_chain"]["source"]["created_at"] = "2026-10-28T00:00:00Z"
        other["candidate_chain"]["source"]["created_at"] = "2026-10-29T00:00:00Z"
        mixed = {
            "snapshot_case_id": "P14-MIXED-TS",
            "tenant_scope": "TENANT_SYNTH_A",
            "entries": [stamped, other],
        }
        receipt = inbox(mixed, commit="test-commit")
        self.assertEqual(receipt["cards"], [])
        self.assertEqual(receipt["deny_counts"][0]["code"], "MIXED_RIGHTS_TIMESTAMP")

    def test_empty_batch_and_page_cannot_bypass_deny(self) -> None:
        empty = {
            "snapshot_case_id": "P14-EMPTY",
            "tenant_scope": "TENANT_SYNTH_A",
            "entries": [],
        }
        receipt = inbox(empty, commit="test-commit")
        self.assertEqual(receipt["deny_code"], "EMPTY_BATCH")
        self.assertEqual(receipt["cards"], [])
        payload = _load()
        payload["entries"][1]["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        paged = inbox(payload, commit="test-commit", page=1, page_size=1)
        self.assertEqual(paged["cards"], [])
        self.assertEqual(paged["deny_code"], "CROSS_TENANT")
        self.assertNotIn("TENANT_SYNTH_B", json.dumps(paged))
        denied_filter = inbox(_load(), commit="test-commit", status_filter="PREVIEW_DENIED")
        self.assertEqual(denied_filter["cards"], [])
        self.assertEqual(denied_filter["card_count"], 0)
        self.assertEqual(denied_filter["deny_count"], 0)

    def test_pagination_is_local_and_sorted(self) -> None:
        first = inbox(_load(), commit="test-commit", page=1, page_size=1)
        second = inbox(_load(), commit="test-commit", page=2, page_size=1)
        self.assertEqual(first["card_count"], 2)
        self.assertEqual(second["card_count"], 2)
        self.assertEqual(first["page_card_count"], 1)
        self.assertEqual(second["page_card_count"], 1)
        self.assertLess(
            first["cards"][0]["review_work_item_id"],
            second["cards"][0]["review_work_item_id"],
        )
        beyond = inbox(_load(), commit="test-commit", page=9, page_size=1)
        self.assertEqual(beyond["cards"], [])
        self.assertEqual(beyond["card_count"], 2)
        self.assertEqual(beyond["inbox_status"], "PREVIEW_ONLY")

    def test_secrets_never_emitted(self) -> None:
        payload = _load()
        chain = payload["entries"][0]["candidate_chain"]
        chain["source_version"]["media_type"] = SECRET_MEDIA
        chain["submission"]["purpose"] = SECRET_PURPOSE
        chain["source_version"]["rights_snapshot"]["rights_basis"] = SECRET_RIGHTS
        chain["source_version"]["rights_snapshot"]["allowed_purposes"] = [SECRET_PURPOSE]
        chain["source"]["external_locator"] = SECRET_LOCATOR
        receipt = inbox(payload, commit="test-commit")
        self.assertEqual(receipt["inbox_status"], "PREVIEW_ONLY")
        blob = json.dumps(receipt)
        self.assertNotIn(SECRET_MEDIA, blob)
        self.assertNotIn(SECRET_PURPOSE, blob)
        self.assertNotIn(SECRET_RIGHTS, blob)
        self.assertNotIn(SECRET_LOCATOR, blob)
        self.assertNotIn("media_type", blob)

    def test_duplicate_json_keys_rejected(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            inbox_file(DUP_TOP)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP_TOP)])
        self.assertEqual(proc.returncode, 2)
        error = json.loads(proc.stdout)
        self.assertEqual(error["parse_error"], "DUPLICATE_JSON_KEY")
        self.assertEqual(error["final_authority"], "NOT_ADMITTED")
        self.assertEqual(proc.stderr, "")

    def test_untrusted_commit_and_malformed(self) -> None:
        with self.assertRaises(PreviewParseError) as caught:
            inbox(_load(), commit=SECRET_COMMIT)
        self.assertEqual(caught.exception.code, "INVALID_COMMIT_LABEL")
        proc = _cli([str(FIXTURE), "--commit", SECRET_COMMIT])
        self.assertEqual(proc.returncode, 2)
        blob = proc.stdout + proc.stderr
        self.assertNotIn("whoami", blob)
        self.assertNotIn(SECRET_COMMIT, blob)
        with self.assertRaises(PreviewParseError) as malformed:
            inbox_file(MALFORMED)
        self.assertEqual(malformed.exception.code, "MALFORMED_JSON")

    def test_oversized_deep_huge_int(self) -> None:
        self.assertEqual(MAX_CHARS, PREVIEW_MAX_CHARS)
        with tempfile.TemporaryDirectory(dir=str(FIXTURE.parent)) as raw:
            tmp = Path(raw)
            huge = tmp / "oversized.json"
            huge.write_text("{" + ("a" * (MAX_CHARS + 8)), encoding="utf-8")
            with self.assertRaises(PreviewParseError) as oversized:
                inbox_file(huge)
            self.assertEqual(oversized.exception.code, "INPUT_TOO_LARGE")
            deep = {"entries": [{"n": {}}]}
            cursor = deep["entries"][0]["n"]
            for _ in range(10):
                cursor["n"] = {}
                cursor = cursor["n"]
            deep_path = tmp / "deep.json"
            deep_path.write_text(
                json.dumps(
                    {
                        "snapshot_case_id": "P14-DEEP",
                        "tenant_scope": "TENANT_SYNTH_A",
                        **deep,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PreviewParseError) as deep_err:
                inbox_file(deep_path)
            self.assertEqual(deep_err.exception.code, "INPUT_TOO_DEEP")
            huge_int = tmp / "hugeint.json"
            huge_int.write_text(
                '{"snapshot_case_id":"P14-HUGE","tenant_scope":"TENANT_SYNTH_A",'
                '"entries":[{"n":111111111111111111111}]}',
                encoding="utf-8",
            )
            with self.assertRaises(PreviewParseError) as huge_err:
                inbox_file(huge_int)
            self.assertEqual(huge_err.exception.code, "HUGE_INTEGER")

    def test_flag_inactive(self) -> None:
        self.assertEqual(
            FLAGS["offline_review_inbox_readmodel"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )
        self.assertEqual(
            FLAGS["offline_review_handoff_preview"],
            "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
