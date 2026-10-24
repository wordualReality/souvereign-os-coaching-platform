"""Offline replay/DLQ policy. No n8n runtime. No numeric retry budget."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "n8n" / "kdb-dev" / "test_replay_dlq.cjs"
CANDIDATE = REPO / "n8n" / "kdb-dev" / "tenant-guard-candidate"


class ReplayDlqPolicy(unittest.TestCase):
    def test_offline_policy_pass(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            output = handle.name
        proc = subprocess.run(
            ["node", str(SCRIPT), str(CANDIDATE), output],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(Path(output).read_text())
        self.assertEqual(report["acceptance"]["offline_replay_dlq_policy"], "PASS")
        self.assertEqual(report["acceptance"]["numeric_retry_budget"], "NOT_INVENTED")
        self.assertEqual(report["acceptance"]["n8n_runtime"], "NOT_RUN")
        self.assertEqual(report["counts"]["receipt_pass"], 3)


if __name__ == "__main__":
    unittest.main()
