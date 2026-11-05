import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/kdb"))
from offline_acupressure_protocol import resolve
from offline_seasonal_botanical import digest

FIXTURE = ROOT / "tests/kdb/fixtures/c08_b03_synthetic_protocol.json"

class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())

    def run_preview(self):
        return resolve(self.data["snapshot"], self.data["query"])

    def rehash(self, kind):
        names = {"sources": "source_sha256", "claims": "claim_sha256", "protocols": "protocol_sha256"}
        item = self.data["snapshot"][kind][0]
        item["content_sha256"] = digest(item["content"])
        self.data["query"][names[kind]] = item["content_sha256"]

    def test_positive_and_deterministic_cli(self):
        before = copy.deepcopy(self.data)
        result = self.run_preview()
        self.assertEqual(result["decision"], "PREVIEW_METADATA_ONLY")
        self.assertEqual(result["provenance"]["availability"], "PINNED_UNTRUSTED")
        self.assertEqual(self.data, before)
        raw = subprocess.check_output([sys.executable, str(ROOT / "services/kdb/offline_acupressure_protocol.py"), str(FIXTURE)])
        self.assertEqual(json.loads(raw), result)

    def test_missing_wrong_versions_and_hashes(self):
        for field in ("source_version_id", "claim_version_id", "protocol_version_id", "source_sha256", "claim_sha256", "protocol_sha256"):
            with self.subTest(field=field):
                old = self.data["query"][field]
                self.data["query"][field] = "wrong"
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")
                del self.data["query"][field]
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")
                self.data["query"][field] = old

    def test_scope_rights_lifecycle_and_duplicates(self):
        for path, value in [(("snapshot","tenant_scope"), "OTHER"), (("query","purpose"), "OTHER"), (("query","knowledge_as_of"), "2026-01-02"), (("query","display"), "REAL_PROTOCOL")]:
            with self.subTest(path=path):
                original = self.data[path[0]][path[1]]
                self.data[path[0]][path[1]] = value
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")
                self.data[path[0]][path[1]] = original
        for field, value in (("rights_status","REVOKED"), ("license_status","UNKNOWN"), ("rights_checked_as_of","2025-01-01"), ("lifecycle","WITHDRAWN"), ("current_version_id","SUPERSEDED")):
            with self.subTest(field=field):
                source = self.data["snapshot"]["sources"][0]
                old = source[field]; source[field] = value
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")
                source[field] = old
        for kind in ("sources", "claims", "protocols"):
            with self.subTest(kind=kind):
                self.data["snapshot"][kind].append(copy.deepcopy(self.data["snapshot"][kind][0]))
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")
                self.data["snapshot"][kind].pop()

    def test_untrusted_content_and_injection(self):
        for field, value in (("technique","do something"), ("diagnosis","x"), ("treatment","x"), ("pregnancy","safe"), ("children","safe"), ("high_risk","safe"), ("reviewer","forged"), ("signature","forged"), ("assessment","x"), ("safety_status","APPROVED"), ("eligibility","ELIGIBLE"), ("evidence_locator","external")):
            with self.subTest(field=field):
                self.setUp()
                self.data["snapshot"]["protocols"][0]["content"][field] = value
                self.rehash("protocols")
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")

    def test_claim_and_source_tampering(self):
        for kind in ("sources", "claims", "protocols"):
            with self.subTest(kind=kind):
                self.setUp()
                self.data["snapshot"][kind][0]["content"]["forged"] = True
                self.rehash(kind)
                self.assertEqual(self.run_preview()["decision"], "ABSTAIN")

    def test_missing_and_malformed(self):
        for kind in ("sources", "claims", "protocols"):
            with self.subTest(kind=kind):
                self.setUp(); self.data["snapshot"][kind] = []
                result = self.run_preview()
                self.assertEqual(result["decision"], "ABSTAIN")
                self.assertEqual(result["provenance"], {"availability": "UNAVAILABLE"})

    def test_output_schema_and_shape_mismatch(self):
        schema = json.loads((ROOT / "contracts/kdb/c08_acupressure_protocol_preview.v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        good = self.run_preview()
        jsonschema.validate(good, schema)
        self.data["query"]["display"] = "REAL_PROTOCOL"
        jsonschema.validate(self.run_preview(), schema)
        good["provenance"]["availability"] = "UNAVAILABLE"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(good, schema)

if __name__ == "__main__":
    unittest.main()
