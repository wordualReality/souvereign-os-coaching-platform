import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/kdb"))
import offline_gc01_handoff as gc
from provenance_eligibility import evaluate_review_eligibility

SEED = ROOT / "tests/kdb/fixtures/step10_gc01_synthetic_seed.json"

class GC01Test(unittest.TestCase):
    def setUp(self):
        self.bundle = gc.build_fixture(json.loads(SEED.read_text()))

    def test_positive_deterministic_schema_and_real_eligibility(self):
        original = copy.deepcopy(self.bundle)
        with patch.object(gc, "evaluate_review_eligibility", wraps=evaluate_review_eligibility) as checked:
            result = gc.run(self.bundle)
            self.assertEqual(checked.call_count, 1)
            chain = checked.call_args.args[0]
            self.assertEqual(chain["candidate_revision"]["review_state"], "PENDING_REVIEW")
            self.assertEqual(chain["review_work_item"]["state"], "REQUESTED")
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_REVIEW_HANDOFF")
        self.assertEqual(result["schema_check"], "O1_O2_O3_ENVELOPES_SCHEMA_VALID")
        self.assertEqual(result["evidence_check"], "LOCAL_BYTES_SPANS_VERIFIED")
        self.assertEqual(result["admission"], "NOT_ADMITTED")
        self.assertEqual(original, self.bundle)
        self.assertEqual(result, gc.run(self.bundle))
        cli = subprocess.check_output([sys.executable, str(ROOT / "services/kdb/offline_gc01_handoff.py"), str(SEED)])
        self.assertEqual(json.loads(cli), result)

    def test_schema_and_context_denials(self):
        for i, field, value in [(0,"command_id","not-uuid"), (1,"contract_id","WRONG"), (2,"correlation_id","bad"), (0,"issued_at","bad")]:
            with self.subTest(field=field):
                self.setUp(); self.bundle["commands"][i][field] = value
                result = gc.run(self.bundle)
                self.assertEqual((result["decision"], result["stage"]), ("ABSTAIN", "SCHEMA_DENIED"))
        for i, field, value in [(1,"correlation_id","aaaaaaaa-bbbb-4ccc-8ddd-999999999999"), (0,"tenant_scope","OTHER"), (0,"origin_owner","ARCAVA"), (0,"purpose","OTHER"), (0,"principal_context_ref","forged"), (0,"access_decision_ref","forged"), (1,"idempotency_key","gc01-command-001")]:
            with self.subTest(field=field):
                self.setUp(); self.bundle["commands"][i][field] = value
                self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")

    def test_rights_bytes_and_links_denied(self):
        for target, value in [("content_sha256","0"*64), ("rights_snapshot_sha256","0"*64), ("source_locator","real://bad")]:
            with self.subTest(target=target):
                self.setUp(); self.bundle["commands"][0]["payload"][target] = value
                self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); self.bundle["source_text"] += "!"; self.assertEqual(gc.run(self.bundle)["reason"], "SOURCE_DIGEST_MISMATCH")
        self.setUp(); self.bundle["commands"][0]["payload"]["rights"]["rights_status"] = "REVOKED"; self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); self.bundle["commands"][1]["payload"]["submission_id"] = gc.IDS["candidate"]; self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); self.bundle["commands"][2]["payload"]["candidate_revision_id"] = gc.IDS["candidate"]; self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); self.bundle["review_work_item_id"] = gc.IDS["candidate"]; self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")

    def test_evidence_denials(self):
        for span in [
            {"source_version_id":gc.IDS["version"],"locator":"bytes:19-99","start":19,"end":100},
            {"source_version_id":gc.IDS["version"],"locator":"bytes:28-28","start":28,"end":29},
            {"source_version_id":gc.IDS["source"],"locator":"bytes:19-23","start":19,"end":24},
        ]:
            with self.subTest(span=span):
                self.setUp(); self.bundle["commands"][1]["payload"]["evidence_spans"] = [span]
                self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); spans = self.bundle["commands"][1]["payload"]["evidence_spans"]; spans.append(copy.deepcopy(spans[0])); self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")
        self.setUp(); spans = self.bundle["commands"][1]["payload"]["evidence_spans"]; spans.append({"source_version_id":gc.IDS["version"],"locator":"bytes:20-24","start":20,"end":25}); self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")

    def test_replay_and_conflict_via_existing_policy(self):
        with patch.object(gc, "evaluate_review_eligibility", wraps=evaluate_review_eligibility) as checked:
            self.assertEqual(gc.run(self.bundle)["decision"], "ELIGIBLE_FOR_REVIEW_HANDOFF")
            prior = copy.deepcopy(checked.call_args.args[0]["submission"])
        self.bundle["prior_submissions"] = [copy.deepcopy(prior)]
        self.assertEqual(gc.run(self.bundle)["decision"], "ELIGIBLE_FOR_REVIEW_HANDOFF")
        self.bundle["prior_submissions"][0]["request_sha256"] = "e"*64
        self.assertEqual((gc.run(self.bundle)["stage"], gc.run(self.bundle)["reason"]), ("ELIGIBILITY_DENIED", "CONFLICTING_SUBMISSION"))
        self.bundle["prior_submissions"][0] = prior
        self.bundle["prior_submissions"][0]["submission_id"] = gc.IDS["candidate"]
        self.assertEqual(gc.run(self.bundle)["reason"], "DUPLICATE_SUBMISSION")

    def test_stale_version_and_forbidden_claims(self):
        with patch.object(gc, "evaluate_review_eligibility", wraps=evaluate_review_eligibility) as checked:
            gc.run(self.bundle)
            version = copy.deepcopy(checked.call_args.args[0]["source_version"])
        version["source_version_no"] = 2
        version["source_version_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222223"
        self.bundle["source_versions"] = [version]
        self.assertEqual(gc.run(self.bundle)["reason"], "STALE_SOURCE_VERSION")
        for key in ("approved", "reviewer", "clinical_efficacy", "safety", "protocol_version_id"):
            with self.subTest(key=key):
                self.setUp(); self.bundle["commands"][1]["payload"]["proposal_payload"][key] = True
                self.bundle["commands"][1]["payload"]["content_sha256"] = gc.digest(self.bundle["commands"][1]["payload"]["proposal_payload"])
                self.assertEqual(gc.run(self.bundle)["decision"], "ABSTAIN")

if __name__ == "__main__":
    unittest.main()
