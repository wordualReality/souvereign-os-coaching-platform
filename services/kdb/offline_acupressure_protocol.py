"""Synthetic non-executable protocol metadata, never professional advice."""
import json
import re
import sys
from pathlib import Path
from offline_seasonal_botanical import digest

VERSION = "kdb.c08.acupressure-protocol.preview.v1"
FLAGS = {"scope": "SYNTHETIC_TEST_ONLY", "execution": "NON_EXECUTABLE", "admission": "NOT_ADMITTED"}

class Denied(Exception):
    pass

def check(ok, reason):
    if not ok:
        raise Denied(reason)

def exact(value, keys, reason):
    check(isinstance(value, dict) and set(value) == set(keys), reason)

def resolve(snapshot, query):
    out = {"schema_version": VERSION, **FLAGS, "decision": "ABSTAIN", "reason": "INVALID_INPUT", "provenance": {"availability": "UNAVAILABLE"}}
    try:
        exact(snapshot, ("schema_version", "tenant_scope", "purpose", "knowledge_as_of", "sources", "claims", "protocols"), "INVALID_SNAPSHOT")
        exact(query, ("tenant_scope", "purpose", "knowledge_as_of", "source_version_id", "claim_version_id", "protocol_version_id", "source_sha256", "claim_sha256", "protocol_sha256", "display"), "INVALID_QUERY")
        check(snapshot["schema_version"] == VERSION, "SCHEMA_MISMATCH")
        check(snapshot["tenant_scope"] == query["tenant_scope"] == "SYNTHETIC_TENANT", "TENANT_MISMATCH")
        check(snapshot["purpose"] == query["purpose"] == "SYNTHETIC_PROTOCOL_METADATA", "PURPOSE_MISMATCH")
        check(snapshot["knowledge_as_of"] == query["knowledge_as_of"] == "2026-01-01", "STALE_SNAPSHOT")
        check(query["display"] == "METADATA_ONLY", "BLOCKED_PENDING_PROFESSIONAL_REVIEW")
        chosen = {}
        for name, idkey, hashkey, extra in (
            ("sources", "source_version_id", "source_sha256", ("rights_status", "license_status", "rights_checked_as_of", "lifecycle")),
            ("claims", "claim_version_id", "claim_sha256", ()),
            ("protocols", "protocol_version_id", "protocol_sha256", ())):
            records = snapshot[name]
            check(isinstance(records, list) and len(records) == 1, "MISSING_OR_CONFLICTING_" + name.upper())
            obj = records[0]
            exact(obj, (name[:-1] + "_id", idkey, "current_version_id", "content_sha256", "content") + extra, "INVALID_" + name.upper())
            check(obj[idkey] == obj["current_version_id"] == query[idkey], "VERSION_MISMATCH")
            check(isinstance(obj["content_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", obj["content_sha256"]) is not None, "INVALID_DIGEST")
            check(obj["content_sha256"] == query[hashkey] == digest(obj["content"]), "DIGEST_MISMATCH")
            chosen[name] = obj
        s, c, p = (chosen[n] for n in ("sources", "claims", "protocols"))
        check((s["source_id"], s["source_version_id"], c["claim_id"], c["claim_version_id"], p["protocol_id"], p["protocol_version_id"]) == ("SYN-SRC-ALPHA", "SYN-SRCVER-1", "SYN-CLAIM-ALPHA", "SYN-CLAIMVER-1", "SYN-PROTOCOL-ALPHA", "SYN-PROTOCOLVER-1"), "INVALID_SYNTHETIC_ID")
        check((s["rights_status"], s["license_status"], s["rights_checked_as_of"], s["lifecycle"]) == ("ADMITTED", "SYNTHETIC_FIXTURE_ONLY", snapshot["knowledge_as_of"], "SYNTHETIC_PREVIEW"), "SOURCE_RIGHTS_OR_LIFECYCLE_INVALID")
        sc, cc, pc = s["content"], c["content"], p["content"]
        check(sc == {"source_label": "SYN-SOURCE-ALPHA", "evidence_locator": "fixture://source/alpha#evidence"}, "SOURCE_EVIDENCE_INVALID")
        check(cc == {"source_version_id": s["source_version_id"], "source_sha256": s["content_sha256"], "evidence_locator": sc["evidence_locator"], "review_status": "NOT_REVIEWED", "evidence_status": "UNKNOWN"}, "CLAIM_EVIDENCE_OR_REVIEW_INVALID")
        check(isinstance(pc, dict) and pc.get("informational") is True and pc.get("executable") is False, "NON_EXECUTABLE_FLAGS_REQUIRED")
        check(pc == {"source_version_id": s["source_version_id"], "source_sha256": s["content_sha256"], "claim_version_id": c["claim_version_id"], "claim_sha256": c["content_sha256"], "category": "SYNTHETIC_LABEL", "review_status": "NOT_REVIEWED", "safety_status": "UNKNOWN", "contraindication_status": "UNKNOWN", "eligibility": "NOT_ELIGIBLE_FOR_EXECUTION", "lifecycle": "SYNTHETIC_PREVIEW", "disclosure": "NO_PROFESSIONAL_REVIEW_OR_INSTRUCTION", "informational": True, "executable": False}, "PROTOCOL_SAFETY_OR_PROVENANCE_INVALID")
        out.update(decision="PREVIEW_METADATA_ONLY", reason="SYNTHETIC_METADATA_ONLY", provenance={"availability": "PINNED_UNTRUSTED", "source_id": s["source_id"], "source_version_id": s["source_version_id"], "source_sha256": s["content_sha256"], "rights_status": s["rights_status"], "license_status": s["license_status"], "rights_checked_as_of": s["rights_checked_as_of"], "claim_id": c["claim_id"], "claim_version_id": c["claim_version_id"], "claim_sha256": c["content_sha256"], "evidence_locator": sc["evidence_locator"], "protocol_id": p["protocol_id"], "protocol_version_id": p["protocol_version_id"], "protocol_sha256": p["content_sha256"], **{k: pc[k] for k in ("category", "review_status", "safety_status", "contraindication_status", "eligibility", "lifecycle", "disclosure")}})
    except Denied as exc:
        out["reason"] = str(exc)
    return out

def main():
    try:
        check(len(sys.argv) == 2, "INVALID_INPUT_ENVELOPE")
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        exact(data, ("snapshot", "query"), "INVALID_INPUT_ENVELOPE")
        output = resolve(data["snapshot"], data["query"])
    except (Denied, OSError, UnicodeError, ValueError):
        output = {"schema_version": VERSION, **FLAGS, "decision": "ABSTAIN", "reason": "INVALID_INPUT_ENVELOPE", "provenance": {"availability": "UNAVAILABLE"}}
    print(json.dumps(output, sort_keys=True))

if __name__ == "__main__":
    main()
