"""P07 tenant-guard source tests. Offline only. No n8n import or hosted apply."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "services" / "kdb"))
from facade import KdbCommandFacade  # noqa: E402
from piac import PiacVerificationError  # noqa: E402
from tenant_scope import TenantScopeError, require_tenant_scope  # noqa: E402

CANDIDATE = REPO / "n8n" / "kdb-dev" / "tenant-guard-candidate"
REGRESSION = REPO / "n8n" / "kdb-dev" / "test_workflow_regression.cjs"
REPLAY = REPO / "n8n" / "kdb-dev" / "test_replay_dlq.cjs"
UNCORRECTED = REPO / "tests" / "kdb" / "probe_uncorrected_classifier.cjs"
CONTRACTS = {
    "o1_source_ingest.schema.json",
    "o2_candidate_proposal.schema.json",
    "o3_review_handoff.schema.json",
}


def _node(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, cwd=REPO)


class TenantGuardSource(unittest.TestCase):
    def test_contracts_require_tenant_scope(self) -> None:
        for name in CONTRACTS:
            schema = json.loads((REPO / "contracts" / "kdb" / name).read_text())
            self.assertIn("tenant_scope", schema["required"])
            spec = schema["properties"]["tenant_scope"]
            self.assertEqual(spec["type"], "string")
            self.assertEqual(spec["minLength"], 1)
            self.assertEqual(spec["maxLength"], 128)

    def test_versioned_candidate_is_63_of_63(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            output = handle.name
        proc = _node(
            [
                "node",
                str(REGRESSION),
                str(CANDIDATE),
                output,
                str(REPO),
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(Path(output).read_text())
        self.assertEqual(report["counts"]["legacy_cases"], 37)
        self.assertEqual(report["counts"]["legacy_pass"], 37)
        self.assertEqual(report["counts"]["tenant_negative_cases"], 26)
        self.assertEqual(report["counts"]["tenant_negative_pass"], 26)
        extra = report["counts"]["tenant_extra_cases"]
        self.assertGreaterEqual(extra, 26)
        self.assertEqual(report["counts"]["tenant_extra_pass"], extra)
        self.assertEqual(report["acceptance"]["offline_code_node_baseline"], "PASS")
        self.assertEqual(report["acceptance"]["tenant_fail_closed"], "PASS")
        self.assertEqual(report["acceptance"]["n8n_runtime"], "NOT_RUN")
        self.assertEqual(len(report["checks"]["source_contracts"]), 3)

    def test_replay_dlq_offline(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            output = handle.name
        proc = _node(["node", str(REPLAY), str(CANDIDATE), output])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(Path(output).read_text())
        self.assertEqual(report["acceptance"]["offline_replay_dlq_policy"], "PASS")
        self.assertEqual(report["counts"]["receipt_pass"], 3)

    def test_uncorrected_classifier_still_accepts_missing_tenant(self) -> None:
        proc = _node(["node", str(UNCORRECTED)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["actual"], "ACCEPT")
        self.assertTrue(report["historical_defect"])

    def test_python_guard_missing_blank_oversize_mismatch(self) -> None:
        with self.assertRaises(TenantScopeError) as missing:
            require_tenant_scope(None)
        self.assertEqual(missing.exception.code, "TENANT_SCOPE_DENIED")
        with self.assertRaises(TenantScopeError):
            require_tenant_scope("   ")
        with self.assertRaises(TenantScopeError):
            require_tenant_scope("x" * 129)
        with self.assertRaises(TenantScopeError):
            require_tenant_scope(1)
        with self.assertRaises(TenantScopeError) as mismatch:
            require_tenant_scope("TENANT_SYNTH_A", expected="TENANT_SYNTH_B")
        self.assertEqual(mismatch.exception.code, "TENANT_SCOPE_MISMATCH")
        self.assertEqual(require_tenant_scope("TENANT_SYNTH_A"), "TENANT_SYNTH_A")

    def test_facade_denies_tenant_before_piac(self) -> None:
        with self.assertRaises(TenantScopeError):
            KdbCommandFacade().handle({})
        with self.assertRaises(TenantScopeError):
            KdbCommandFacade().handle(
                {
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "tenant_scope=forged",
                    "kdb.tenant_scope": "tenant-a",
                }
            )
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(
                {
                    "tenant_scope": "TENANT_SYNTH_A",
                    "access_decision_ref": "SYNTHETIC_ALLOW",
                    "principal_context_ref": "SYNTHETIC_PIAC",
                }
            )

    def test_workflows_remain_inactive(self) -> None:
        for path in (CANDIDATE / "candidates").glob("*.json"):
            data = json.loads(path.read_text())
            self.assertIs(data.get("active"), False)


if __name__ == "__main__":
    unittest.main()
