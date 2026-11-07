"""Strict parser adversarial tests; no network or database connection."""
import copy
import json
import re
import unittest
from pathlib import Path
from hosted_recovery_preflight_diff import analyze, TARGET, LEDGER, EXPECTED_CATALOG, EXPORTED_PREIMAGE

def fixture():
    return {"version":"kdb.a04.synthetic-preimage.v1","binding":{"claimed_project_ref":TARGET,"export_origin":"SYNTHETIC_LOCAL_FIXTURE","attestation":"SYNTHETIC_ONLY"},"ledger":copy.deepcopy(LEDGER),"catalog":copy.deepcopy(EXPECTED_CATALOG)}

def check(doc):
    return analyze(json.dumps(doc))

class PreflightTest(unittest.TestCase):
    def test_synthetic_match_never_authorizes(self):
        report = check(fixture())
        self.assertEqual(report["status"], "SYNTHETIC_PREIMAGE_MATCH")
        self.assertEqual(report["target_attestation"], "AUTHORITATIVE_TARGET_NOT_VERIFIED")
        self.assertEqual(report["apply"], "NOT_AUTHORIZED")
        self.assertEqual(report, check(fixture()))
        stored = Path(__file__).resolve().parent / "fixtures/a04_synthetic_preimage_v1.json"
        self.assertEqual(report, analyze(stored.read_text(encoding="utf-8")))

    def test_old_false_positive_is_denied(self):
        report = analyze("12345678|x\n"*6 + "kdb_runtime kdb_ingest_writer kdb_reviewer rollback_objects_test_v2 legacy_protocol_rows|1")
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertNotIn("claimed_project_ref", report)

    def test_target_binding_and_forgery(self):
        for val in ("zobjpmyccszkabybdmsf", "wixdcaqdwmpccbfmxyea", "", None):
            with self.subTest(value=val):
                doc = fixture(); doc["binding"]["claimed_project_ref"] = val
                self.assertEqual(check(doc)["status"], "ABSTAIN")
        for field in ("claimed_project_ref","export_origin","attestation"):
            doc = fixture(); del doc["binding"][field]
            self.assertEqual(check(doc)["code"], "TARGET_UNVERIFIED")
        doc = fixture(); doc["binding"]["attestation"] = "VERIFIED_PROVIDER"
        self.assertEqual(check(doc)["code"], "TARGET_UNVERIFIED")
        self.assertEqual(analyze('{"version":"a","version":"b"}')["status"], "ABSTAIN")

    def test_ledger_strict(self):
        variants = []
        doc=fixture(); doc["ledger"][0]["md5"]="0"*32; variants.append(doc)
        doc=fixture(); doc["ledger"][0]["version"]="20261012000000"; variants.append(doc)
        doc=fixture(); doc["ledger"].append(copy.deepcopy(doc["ledger"][0])); variants.append(doc)
        doc=fixture(); doc["ledger"].pop(); variants.append(doc)
        doc=fixture(); doc["ledger"][0]["octets"]=True; variants.append(doc)
        for doc in variants:
            self.assertEqual(check(doc)["code"], "LEDGER_DRIFT")

    def test_catalog_adversarial(self):
        for mutate in ("protocol","role","membership","acl","policy","table","function","extension","digest","public","other_creator","bool"):
            with self.subTest(mutate=mutate):
                doc=fixture(); cat=doc["catalog"]
                if mutate=="protocol": cat["protected_protocol"]["rows"]=2
                if mutate=="role": cat["roles"].pop()
                if mutate=="membership": cat["memberships"][0]["set"]=True
                if mutate=="acl": del cat["default_function_acl"]
                if mutate=="policy": cat["policies"].append("stale")
                if mutate=="table": cat["legacy_application_tables"].append("evil")
                if mutate=="function": cat["kdb_functions"].append("evil")
                if mutate=="extension": cat["pgcrypto"]["namespace"]="public"
                if mutate=="digest": cat["pgcrypto"]["signature"]="digest(text,text)"
                if mutate=="public": cat["pgcrypto"]["public_execute"]=True
                if mutate=="other_creator": cat["default_function_acl"].append({"creator":"other","grantee":"PUBLIC","execute":True})
                if mutate=="bool": cat["protected_protocol"]["rows"]=True
                self.assertEqual(check(doc)["status"], "DRIFT")

    def test_catalog_export_adversarial(self):
        self.assertEqual(check(EXPORTED_PREIMAGE)["status"], "SYNTHETIC_PREIMAGE_MATCH")
        variants = []
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["roles"].pop(); variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["memberships"][0]["set"]=True; variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["relations"][0]["force_rls"]=True; variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["relations"][0]["raw_acl"]="forged"; variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["functions"].append({"signature":"evil()"}); variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["default_function_acl"].append({"creator":"evil"}); variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["pgcrypto"]["namespace"]="public"; variants.append(doc)
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["protocol_count"]=True; variants.append(doc)
        for doc in variants:
            self.assertEqual(check(doc)["status"], "DRIFT")
        doc=copy.deepcopy(EXPORTED_PREIMAGE); doc["binding"]["attestation"]="VERIFIED"
        self.assertEqual(check(doc)["status"], "ABSTAIN")

    def test_p3_p4_derivatives_change_only_scoped_parts(self):
        root = Path(__file__).resolve().parents[2]
        pairs = [
            ("database/migrations/kdb/20261024190000__kdb_m01_p3__fail_closed_security.sql", "database/migrations/kdb/candidates/202611070002__a04_p3_extensions_disposable.sql"),
            ("database/migrations/kdb/20261024220000__kdb_m01_p4__digest_oracle_integrity.sql", "database/migrations/kdb/candidates/202611070003__a04_p4_extensions_disposable.sql"),
        ]
        for index, (source_path, derivative_path) in enumerate(pairs):
            with self.subTest(source=source_path):
                source = (root / source_path).read_text().replace("public.digest", "extensions.digest")
                derived = (root / derivative_path).read_text()
                derived = derived.removeprefix("-- A04 DERIVATIVE: DISPOSABLE ONLY / HOSTED NOT AUTHORIZED.\n")
                derived, count = re.subn(r"\n-- A04 isolated harness only\..*?END \$a04_guard\$;\n", "", derived, count=1, flags=re.S)
                self.assertEqual(count, 1)
                if index == 0:
                    derived, count = re.subn(r"DO \$a04_roles\$.*?END \$a04_roles\$;", "CREATE ROLE kdb_migrator NOLOGIN NOBYPASSRLS NOSUPERUSER NOINHERIT;", derived, count=1, flags=re.S)
                    self.assertEqual(count, 1)
                self.assertEqual(derived, source)

if __name__ == "__main__":
    unittest.main()
