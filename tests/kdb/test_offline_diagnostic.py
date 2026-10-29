"""P10 offline integrated diagnostic tests. No SQL write, n8n, or hosted apply."""
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
from facade import KdbCommandFacade  # noqa: E402
from offline_diagnostic import (  # noqa: E402
    DiagnosticParseError,
    diagnose,
    diagnose_file,
    parse_diagnostic_json,
)
from piac import PiacVerificationError  # noqa: E402

FIXTURE = REPO / "tests" / "kdb" / "fixtures" / "p10_stage_coherent.json"
DUP = REPO / "tests" / "kdb" / "fixtures" / "p10_duplicate_keys.json"
CLI = REPO / "services" / "kdb" / "offline_diagnostic_cli.py"
FLAGS = json.loads((REPO / "contracts" / "kdb" / "activation_flags.json").read_text())
EVENT_WD = "aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb2"


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


class OfflineDiagnostic(unittest.TestCase):
    def test_coherent_stages_still_not_admitted(self) -> None:
        payload = _load()
        original = deepcopy(payload)
        receipt = diagnose(payload, commit="test-commit")
        self.assertEqual(payload, original)
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["execution"], "NON_EXECUTABLE")
        self.assertEqual(receipt["db_write"], "NOT_ADMITTED")
        self.assertEqual(receipt["c04_human_decision"], "NOT_WRITTEN")
        self.assertEqual(receipt["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(receipt["outbox"], "NOT_EMITTED")
        self.assertEqual(receipt["content_digest_proof"], "OPAQUE_SHA_UNPROVEN")
        self.assertEqual(receipt["event_watermark"], "UNTRUSTED")
        self.assertNotIn("ALLOW", json.dumps(receipt))
        self.assertNotIn("DB_COMMAND_ADMITTED", json.dumps(receipt))
        self.assertEqual(receipt["stages"]["tenant_scope"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["stages"]["linkage"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["stages"]["provenance"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["stages"]["lifecycle"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["stages"]["c04_c05_transition"]["status"], "ABSENT")
        self.assertEqual(
            receipt["stages"]["c04_c05_transition"]["code"],
            "NO_VERIFIED_C04_C05_TRANSITION",
        )
        self.assertNotIn("synthetic://", json.dumps(receipt))
        self.assertNotIn("synthetic-candidate", json.dumps(receipt))

    def test_cli_happy_path_redacted(self) -> None:
        proc = _cli([str(FIXTURE), "--commit", "cli-test"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")
        self.assertEqual(receipt["source_commit"], "cli-test")
        self.assertNotIn("synthetic://", proc.stdout)
        self.assertNotIn("KNOWLEDGE_INTAKE", proc.stdout)

    def test_published_plus_pending_review_is_not_publication(self) -> None:
        payload = _load()
        self.assertEqual(
            payload["candidate_chain"]["candidate_revision"]["review_state"],
            "PENDING_REVIEW",
        )
        self.assertEqual(payload["lifecycle_chain"]["lifecycle_events"][0]["kind"], "PUBLISHED")
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["provenance"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["stages"]["lifecycle"]["status"], "STAGE_LOCAL_ELIGIBLE")
        self.assertEqual(receipt["c05_canonical_admission"], "NOT_WRITTEN")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_cross_tenant(self) -> None:
        payload = _load()
        payload["candidate_chain"]["source"]["tenant_scope"] = "TENANT_SYNTH_B"
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["tenant_scope"]["status"], "DENY")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_source_version_mismatch(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["source_version"]["source_version_id"] = (
            "aaaaaaaa-bbbb-4ccc-8ddd-999999999999"
        )
        payload["lifecycle_chain"]["candidate_revision"]["source_version_id"] = (
            "aaaaaaaa-bbbb-4ccc-8ddd-999999999999"
        )
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["linkage"]["code"], "SOURCE_VERSION_MISMATCH")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_rights_revoked_after_candidate(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["source"]["rights_status"] = "REVOKED"
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "REVOKED_SOURCE")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_withdrawal_after_published(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["lifecycle_events"].append(
            {
                "lifecycle_event_id": EVENT_WD,
                "protocol_version_id": payload["lifecycle_chain"]["protocol_version"][
                    "protocol_version_id"
                ],
                "kind": "WITHDRAWN",
                "reason_code": "synthetic-withdrawn",
                "prior_event_id": payload["lifecycle_chain"]["lifecycle_events"][0][
                    "lifecycle_event_id"
                ],
                "occurred_at": "2026-10-29T11:00:00Z",
                "recorded_at": "2026-10-29T11:00:00Z",
                "decision_ref": "decision-withdrawn",
            }
        )
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "WITHDRAWN")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_withdrawal_before_published(self) -> None:
        payload = _load()
        pub = payload["lifecycle_chain"]["lifecycle_events"][0]
        payload["lifecycle_chain"]["lifecycle_events"] = [
            {
                "lifecycle_event_id": EVENT_WD,
                "protocol_version_id": pub["protocol_version_id"],
                "kind": "WITHDRAWN",
                "reason_code": "synthetic-withdrawn",
                "prior_event_id": None,
                "occurred_at": "2026-10-29T09:00:00Z",
                "recorded_at": "2026-10-29T09:00:00Z",
                "decision_ref": "decision-withdrawn",
            },
            dict(pub, prior_event_id=EVENT_WD, occurred_at="2026-10-29T10:00:00Z", recorded_at="2026-10-29T10:00:00Z"),
        ]
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "WITHDRAWN")

    def test_missing_prior_and_equal_timestamps(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["lifecycle_events"].append(
            {
                "lifecycle_event_id": EVENT_WD,
                "protocol_version_id": payload["lifecycle_chain"]["protocol_version"][
                    "protocol_version_id"
                ],
                "kind": "WITHDRAWN",
                "reason_code": "synthetic-withdrawn",
                "prior_event_id": "aaaaaaaa-bbbb-4ccc-8ddd-ffffffffffff",
                "occurred_at": "2026-10-29T11:00:00Z",
                "recorded_at": "2026-10-29T11:00:00Z",
                "decision_ref": "decision-withdrawn",
            }
        )
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "MISSING_PRIOR_EVENT")
        payload = _load()
        payload["lifecycle_chain"]["lifecycle_events"].append(
            {
                "lifecycle_event_id": EVENT_WD,
                "protocol_version_id": payload["lifecycle_chain"]["protocol_version"][
                    "protocol_version_id"
                ],
                "kind": "WITHDRAWN",
                "reason_code": "synthetic-withdrawn",
                "prior_event_id": payload["lifecycle_chain"]["lifecycle_events"][0][
                    "lifecycle_event_id"
                ],
                "occurred_at": "2026-10-29T10:00:00Z",
                "recorded_at": "2026-10-29T10:00:00Z",
                "decision_ref": "decision-withdrawn",
            }
        )
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "INDETERMINATE_EVENT_ORDER")

    def test_conflicting_published(self) -> None:
        payload = _load()
        first = payload["lifecycle_chain"]["lifecycle_events"][0]
        payload["lifecycle_chain"]["lifecycle_events"].append(
            dict(
                first,
                lifecycle_event_id="aaaaaaaa-bbbb-4ccc-8ddd-bbbbbbbbbbb5",
                prior_event_id=first["lifecycle_event_id"],
                occurred_at="2026-10-29T11:00:00Z",
                recorded_at="2026-10-29T11:00:00Z",
                decision_ref="decision-published-2",
            )
        )
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "CONFLICTING_PUBLISHED")

    def test_opaque_tampered_snapshot_stays_unproven(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["protocol_version"]["canonical_snapshot"] = {"title": "tampered"}
        receipt = diagnose(payload)
        self.assertEqual(receipt["content_digest_proof"], "OPAQUE_SHA_UNPROVEN")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_publisher_claim(self) -> None:
        payload = _load()
        payload["lifecycle_chain"]["publisher"] = "kdb_publisher"
        receipt = diagnose(payload)
        self.assertEqual(receipt["stages"]["lifecycle"]["code"], "UNTRUSTED_CLAIM")
        self.assertEqual(receipt["final_authority"], "NOT_ADMITTED")

    def test_duplicate_json_keys_and_missing_file(self) -> None:
        with self.assertRaises(DiagnosticParseError) as ctx:
            parse_diagnostic_json(DUP.read_text())
        self.assertEqual(ctx.exception.code, "DUPLICATE_JSON_KEY")
        proc = _cli([str(DUP)])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("DUPLICATE_JSON_KEY", proc.stdout)
        proc = _cli(["/tmp/kdb-p10-missing-input.json"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("MISSING_INPUT_FILE", proc.stdout)

    def test_huge_integer_and_deep_object(self) -> None:
        with self.assertRaises(DiagnosticParseError) as ctx:
            parse_diagnostic_json('{"case_id": "P10-HUGE", "n": 12345678901234567890}')
        self.assertEqual(ctx.exception.code, "HUGE_INTEGER")
        nested = {"v": 1}
        for _ in range(10):
            nested = {"v": nested}
        text = json.dumps(
            {
                "case_id": "P10-DEEP",
                "expected_tenant_scope": "TENANT_SYNTH_A",
                "candidate_chain": nested,
                "lifecycle_chain": {},
            }
        )
        with self.assertRaises(DiagnosticParseError) as ctx:
            parse_diagnostic_json(text)
        self.assertEqual(ctx.exception.code, "INPUT_TOO_DEEP")

    def test_network_path_denied(self) -> None:
        with self.assertRaises(DiagnosticParseError) as ctx:
            diagnose_file("https://example.invalid/p10.json")
        self.assertEqual(ctx.exception.code, "NETWORK_PATH_DENIED")

    def test_facade_still_rejects(self) -> None:
        payload = _load()
        diagnose(payload)
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(
                {
                    "tenant_scope": payload["expected_tenant_scope"],
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "SYNTHETIC_PIAC",
                    "payload": payload,
                }
            )

    def test_no_db_or_network_side_effects(self) -> None:
        payload = _load()
        receipt = diagnose_file(FIXTURE)
        self.assertEqual(receipt["db_write"], "NOT_ADMITTED")
        self.assertEqual(FLAGS["offline_diagnostic_vertical_slice"], "INACTIVE_VERSION_CONTROLLED_CANDIDATE")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            handle.write(json.dumps(payload).encode("utf-8"))
            path = handle.name
        before = Path(path).read_text()
        diagnose_file(path)
        self.assertEqual(Path(path).read_text(), before)

    def test_cli_malformed_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{")
            path = handle.name
        proc = _cli([path])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("MALFORMED_JSON", proc.stdout)


if __name__ == "__main__":
    unittest.main()
