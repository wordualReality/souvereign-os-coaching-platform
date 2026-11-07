#!/usr/bin/env python3
"""Strict synthetic preimage comparison; never authenticates or authorizes apply."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TARGET = "ujdzahwlximlmndexgmx"
FORBIDDEN = ("zobjpmyccszkabybdmsf", "wixdcaqdwmpccbfmxyea")
PREIMAGE = json.loads((FIXTURES / "ujdz_legacy_preimage.json").read_text())
EXPORTED_PREIMAGE = json.loads((FIXTURES / "a04_catalog_export_expected.v1.json").read_text())
LEDGER = [
    {"version":"20261022205952","name":"core_foundation","octets":16250,"md5":"bbaac834073823f665a0c7b2cbdccc8d"},
    {"version":"20261022210203","name":"security_boundary","octets":8898,"md5":"3241767e3d4696acb01716cfdaed5e95"},
    {"version":"20261022210217","name":"api_boundary","octets":2541,"md5":"d280bbc6bb1bf2b834c824003c8e88d"},
    {"version":"20261022210310","name":"idempotency_repair","octets":915,"md5":"f2b858e2453922378d6c3839754fbfc4"},
    {"version":"20261022210536","name":"publication_fk_index","octets":150,"md5":"59fd566c8f4131d7965506cc05dd1cae"},
    {"version":"20261022211240","name":"rollback_objects_test_v2","octets":1770,"md5":"a52da421c2419244350e13c5cc5216e6"}
]
EXPECTED_CATALOG = {
    "scope":["canonical","dev_staging","kdb_api","kdb_audit","kdb_canonical","kdb_staging","kdb_governance","kdb_ops"],
    "present_schemas":["canonical","dev_staging","kdb_api","kdb_audit"],
    "protected_protocol":{"rows":1,"provenance":"UNKNOWN","owner":"postgres","rls":True,"force_rls":False,"acl":[{"grantor":"postgres","grantee":"postgres","privileges":["ALL"]}]},
    "legacy_application_tables":[],"kdb_functions":[],"policies":[],
    "roles":[{"name":n,"login":False,"inherit":False,"bypassrls":False} for n in ("kdb_runtime","kdb_ingest_writer","kdb_reviewer")],
    "memberships":[{"role":n,"member":"postgres","admin":True,"set":False,"inherit":False} for n in ("kdb_runtime","kdb_ingest_writer","kdb_reviewer")],
    "schema_acl":[],"default_function_acl":[],"function_acl":[],
    "pgcrypto":{"extension":"pgcrypto","namespace":"extensions","signature":"digest(bytea,text)","owner_execute":True,"public_execute":False}
}

class DuplicateKey(ValueError):
    pass

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(key)
        result[key] = value
    return result

def analyze(text: str) -> dict:
    result = {"status":"ABSTAIN","code":"INVALID_DOCUMENT","apply":"NOT_AUTHORIZED",
              "target_attestation":"AUTHORITATIVE_TARGET_NOT_VERIFIED",
              "protocol_provenance":"UNKNOWN"}
    try:
        doc = json.loads(text, object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        return result
    if not isinstance(doc, dict):
        return result
    if doc.get("version") == "kdb.a04.catalog-export.disposable.v1":
        binding = doc.get("binding")
        if not isinstance(binding, dict) or binding != EXPORTED_PREIMAGE["binding"]:
            result["code"] = "TARGET_UNVERIFIED"
            return result
        result["claimed_project_ref"] = binding["claimed_project_ref"]
        canonical = json.dumps(doc, sort_keys=True, separators=(",",":"), ensure_ascii=False)
        expected = json.dumps(EXPORTED_PREIMAGE, sort_keys=True, separators=(",",":"), ensure_ascii=False)
        if canonical != expected:
            result.update(status="DRIFT",code="SCOPED_CATALOG_EXPORT_DRIFT")
            return result
        result.update(status="SYNTHETIC_PREIMAGE_MATCH",code="SYNTHETIC_ONLY",document_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        return result
    if set(doc) != {"version","binding","ledger","catalog"} or doc["version"] != "kdb.a04.synthetic-preimage.v1":
        return result
    binding = doc["binding"]
    if not isinstance(binding, dict) or set(binding) != {"claimed_project_ref","export_origin","attestation"}:
        result["code"] = "TARGET_UNVERIFIED"
        return result
    claim = binding["claimed_project_ref"]
    if not isinstance(claim, str) or claim != TARGET:
        result["code"] = "FORBIDDEN_TARGET_REF" if claim in FORBIDDEN else "TARGET_UNVERIFIED"
        return result
    result["claimed_project_ref"] = claim
    if binding["export_origin"] != "SYNTHETIC_LOCAL_FIXTURE" or binding["attestation"] != "SYNTHETIC_ONLY":
        result["code"] = "TARGET_UNVERIFIED"
        return result
    ledger = doc["ledger"]
    if not isinstance(ledger, list) or ledger != LEDGER or any(type(row.get("octets")) is not int for row in ledger if isinstance(row, dict)):
        result.update(status="DRIFT",code="LEDGER_DRIFT")
        return result
    catalog = doc["catalog"]
    if not isinstance(catalog, dict) or catalog != EXPECTED_CATALOG:
        result.update(status="DRIFT",code="CATALOG_DRIFT")
        return result
    # Python considers bool equal to 0/1: canonical JSON prevents type substitution.
    if json.dumps(catalog, sort_keys=True, separators=(",",":")) != json.dumps(EXPECTED_CATALOG, sort_keys=True, separators=(",",":")):
        result.update(status="DRIFT",code="CATALOG_TYPE_DRIFT")
        return result
    canonical = json.dumps(doc, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")
    result.update(status="SYNTHETIC_PREIMAGE_MATCH",code="SYNTHETIC_ONLY",document_sha256=hashlib.sha256(canonical).hexdigest())
    return result

def main():
    if len(sys.argv) == 1:
        report = analyze((FIXTURES / "a04_synthetic_preimage_v1.json").read_text(encoding="utf-8"))
        if report["status"] != "SYNTHETIC_PREIMAGE_MATCH":
            raise SystemExit("SYNTHETIC_SELF_CHECK_FAILED")
        print("SYNTHETIC_PREIMAGE_MATCH / AUTHORITATIVE_TARGET_NOT_VERIFIED / APPLY_NOT_AUTHORIZED")
        return
    if len(sys.argv) != 2:
        raise SystemExit("usage: hosted_recovery_preflight_diff.py <synthetic-json>")
    try:
        report = analyze(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        report = {"status":"ABSTAIN","code":"INVALID_DOCUMENT","apply":"NOT_AUTHORIZED"}
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "SYNTHETIC_PREIMAGE_MATCH":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
