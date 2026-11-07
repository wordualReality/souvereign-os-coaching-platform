"""Synthetic preapply contract cannot authorize hosted mutation."""
import copy
import json
import unittest
from pathlib import Path

from a04_r1_creator_admission import evaluate, parse_and_evaluate
from hosted_recovery_preflight_diff import analyze

FIXTURE = Path(__file__).resolve().parent / "fixtures/a04_r1_creator_evidence.v1.json"

class CreatorAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(FIXTURE.read_text())

    def test_fixture_local_only(self):
        before = copy.deepcopy(self.doc)
        result = evaluate(self.doc)
        self.assertEqual(result["status"], "LOCAL_CREATOR_SAFE_FOR_DISPOSABLE")
        self.assertEqual(result["apply"], "NOT_AUTHORIZED")
        self.assertEqual(result["postcommit_restore"], "POSTCOMMIT_RESTORE_UNVERIFIED")
        self.assertEqual(self.doc, before)
        self.assertEqual(parse_and_evaluate(json.dumps(self.doc)), result)
        self.assertEqual(analyze(json.dumps(self.doc)), result)

    def test_creator_and_grant_mutations_fail_closed(self):
        variants = []
        doc=copy.deepcopy(self.doc); doc["schemas"][0]["creators"].append("unknown"); variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["schemas"][0]["acl_entries"][0]["grantor"]="other"; variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["schemas"][0]["acl_entries"][0]["grantable"]=True; variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["schemas"][0]["effective_usage"]["anon"]=True; variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["creators"][0]["global_default_raw"]=None; variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["creators"][0]["default_safe"]=False; variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["memberships"].append({"role":"kdb_schema_owner","member":"unknown","set":True}); variants.append(doc)
        doc=copy.deepcopy(self.doc); doc["session"]["current_user"]="kdb_schema_owner"; variants.append(doc)
        for item in variants:
            self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")

    def test_function_and_raw_acl_mutations_fail_closed(self):
        for field, value in (("raw_acl",None),("signature","forged()"),("definition_sha256","0"*64),("public_execute",True),("runtime_execute",True)):
            with self.subTest(field=field):
                item=copy.deepcopy(self.doc); item["functions"][0][field]=value
                self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")
        item=copy.deepcopy(self.doc); item["functions"][0]["acl_entries"][0]["grantor"]="other"
        self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")
        item=copy.deepcopy(self.doc); item["functions"].append(copy.deepcopy(item["functions"][0]))
        self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")

    def test_target_restore_source_and_duplicate_keys_fail_closed(self):
        for field in ("binding","source","restore"):
            item=copy.deepcopy(self.doc); item[field]["forged"]=True
            self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")
        item=copy.deepcopy(self.doc); item["restore"]["backup"]="VERIFIED"
        self.assertEqual(evaluate(item)["status"], "BLOCKED_CREATOR_AUTHORITY")
        self.assertEqual(parse_and_evaluate('{"version":"a","version":"b"}')["status"], "BLOCKED_CREATOR_AUTHORITY")

if __name__ == "__main__":
    unittest.main()
