"""Offline parser tests for the ujdz recovery candidate. No live database."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hosted_recovery_preflight_diff import PREIMAGE, TARGET, analyze

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class HostedRecoveryPreflight(unittest.TestCase):
    def test_target_is_ujdz_not_zobj(self) -> None:
        self.assertEqual(TARGET, "ujdzahwlximlmndexgmx")
        self.assertIn("zobjpmyccszkabybdmsf", PREIMAGE["forbidden_refs"])
        self.assertIn("wixdcaqdwmpccbfmxyea", PREIMAGE["forbidden_refs"])

    def test_match_fixture(self) -> None:
        report = analyze((FIXTURES / "ujdz_preflight_sample_match.txt").read_text())
        self.assertEqual(report["status"], "MATCH")
        self.assertEqual(report["protocol_rows"], 1)
        self.assertEqual(report["protocol_provenance"], "UNKNOWN")
        self.assertEqual(report["apply"], "NOT_AUTHORIZED")

    def test_drift_fixture(self) -> None:
        report = analyze((FIXTURES / "ujdz_preflight_sample_drift.txt").read_text())
        self.assertEqual(report["status"], "DRIFT")
        codes = {row["code"] for row in report["drifts"]}
        self.assertIn("PROTOCOL_ROW_COUNT_DRIFT", codes)
        self.assertIn("MISSING_ROLLBACK_OBJECTS_TEST_V2", codes)


if __name__ == "__main__":
    unittest.main()
