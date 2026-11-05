"""Local cross-slice assurance only; no O1/O2/O3 command or write."""
import copy
import importlib
import json
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/kdb"))
MANIFEST = ROOT / "docs/kdb/m01/step10_h01_handover.v1.json"
MODULES = {
    "B01": "offline_seasonal_botanical",
    "B02": "offline_traditional_claims",
    "B03": "offline_acupressure_protocol",
    "B04": "offline_research_extraction",
}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def resolve_entry(entry):
    fixture = read(ROOT / entry["fixture"])
    module = importlib.import_module(MODULES[entry["id"]])
    return module.resolve(fixture["snapshot"], fixture["query"]) if "snapshot" in fixture else module.resolve(fixture)

def check_output(entry, output):
    if output.get("scope") != "SYNTHETIC_TEST_ONLY" or output.get("execution") != "NON_EXECUTABLE" or output.get("admission") != "NOT_ADMITTED":
        return "UNSUPPORTED_CONTRACT_BOUNDARY"
    if output.get("schema_version") != entry["contract_version"] or output.get("decision") != entry["decision"]:
        return "UNSUPPORTED_CONTRACT_BOUNDARY"
    if entry["id"] == "B03" and (output["provenance"].get("safety_status") != "UNKNOWN" or output["provenance"].get("review_status") != "NOT_REVIEWED"):
        return "UNSUPPORTED_CONTRACT_BOUNDARY"
    if entry["id"] == "B04" and (output.get("review_state") != "PENDING_REVIEW" or output.get("model_provider") != "NONE" or output.get("provider_gate") != "PROVIDER_EXECUTION_NOT_AUTHORIZED"):
        return "UNSUPPORTED_CONTRACT_BOUNDARY"
    try:
        jsonschema.validate(output, read(ROOT / entry["contract"]))
    except jsonschema.ValidationError:
        return "UNSUPPORTED_CONTRACT_BOUNDARY"
    return "SYNTHETIC_PREVIEW_ONLY"

class HandoverTest(unittest.TestCase):
    def setUp(self):
        self.manifest = read(MANIFEST)
        self.entries = {entry["id"]: entry for entry in self.manifest["slices"]}

    def test_manifest_paths_schemas_and_resolvers(self):
        self.assertEqual(set(self.entries), set(MODULES))
        self.assertEqual(self.manifest["baseline_sha"], "f7d093b58d1c91861d871294cc5392806c1206b4")
        self.assertEqual(self.manifest["target_gate_status"], "OPEN")
        for entry in self.entries.values():
            with self.subTest(slice=entry["id"]):
                self.assertEqual(entry["owner"], "KDB")
                for key in ("resolver", "contract", "fixture", "tests"):
                    path = (ROOT / entry[key]).resolve()
                    self.assertTrue(path.is_relative_to(ROOT) and path.is_file())
                jsonschema.Draft202012Validator.check_schema(read(ROOT / entry["contract"]))
                self.assertEqual(check_output(entry, resolve_entry(entry)), "SYNTHETIC_PREVIEW_ONLY")
                self.assertEqual(resolve_entry(entry), resolve_entry(entry))

    def test_status_confusion_fails_closed(self):
        for entry in self.entries.values():
            original = resolve_entry(entry)
            for field, value in (("admission", "ADMITTED"), ("execution", "EXECUTABLE"), ("scope", "PRODUCTION")):
                with self.subTest(slice=entry["id"], field=field):
                    result = copy.deepcopy(original); result[field] = value
                    self.assertEqual(check_output(entry, result), "UNSUPPORTED_CONTRACT_BOUNDARY")
        b03 = self.entries["B03"]; result = resolve_entry(b03)
        result["provenance"]["safety_status"] = "SAFE"
        self.assertEqual(check_output(b03, result), "UNSUPPORTED_CONTRACT_BOUNDARY")
        b04 = self.entries["B04"]; result = resolve_entry(b04)
        result["review_state"] = "APPROVED"
        self.assertEqual(check_output(b04, result), "UNSUPPORTED_CONTRACT_BOUNDARY")
        result = resolve_entry(b04); result["model_provider"] = "LIVE"
        self.assertEqual(check_output(b04, result), "UNSUPPORTED_CONTRACT_BOUNDARY")

    def test_no_implicit_command_or_cross_slice_promotion(self):
        b04 = resolve_entry(self.entries["B04"])
        self.assertNotIn("command_id", b04)
        self.assertNotIn("review_queue", b04)
        self.assertEqual(b04["review_state"], "PENDING_REVIEW")
        self.assertEqual(b04["admission"], "NOT_ADMITTED")
        o2 = read(ROOT / "contracts/kdb/o2_candidate_proposal.schema.json")
        version_schema = o2["properties"]["payload"]["properties"]["source_version_id"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(b04["provenance"]["source_version_id"], version_schema, format_checker=jsonschema.FormatChecker())
        self.assertEqual(self.manifest["cross_slice_boundary"], "UNSUPPORTED_CONTRACT_BOUNDARY")
        self.assertEqual(self.manifest["missing_criteria"], ["REAL_O1_O2_O3_UUID_ENVELOPES", "FULL_PROVENANCE_ELIGIBILITY_CHAIN"])

    def test_semantic_separation(self):
        b01 = resolve_entry(self.entries["B01"])
        self.assertEqual(b01["scope"], "SYNTHETIC_TEST_ONLY")
        b02 = resolve_entry(self.entries["B02"])
        self.assertEqual(b02["claim_type"], "TRADITIONAL_CONTEXT")
        self.assertEqual(b02["evidence_boundary"], "NO_BIOMEDICAL_EFFICACY_OR_DIAGNOSIS_INFERRED")
        b03 = resolve_entry(self.entries["B03"])
        self.assertEqual(b03["provenance"]["eligibility"], "NOT_ELIGIBLE_FOR_EXECUTION")
        b04 = resolve_entry(self.entries["B04"])
        self.assertEqual(b04["provider_gate"], "PROVIDER_EXECUTION_NOT_AUTHORIZED")

if __name__ == "__main__":
    unittest.main()
