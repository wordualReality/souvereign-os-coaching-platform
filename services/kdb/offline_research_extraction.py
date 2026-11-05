"""Synthetic offline proposal preview; no provider, ingestion or review write."""
import hashlib
import json
import sys
from pathlib import Path

from offline_evidence_bound_review import _canonical_spans
from offline_source_bytes_proof import MAX_SOURCE_BYTES
from offline_seasonal_botanical import digest
from provenance_eligibility import REVIEW_QUEUE, REVIEW_STATE
from review_handoff_preview import PreviewParseError

VERSION = "kdb.c08.research-candidate.preview.v1"
FLAGS = {"scope": "SYNTHETIC_TEST_ONLY", "execution": "NON_EXECUTABLE",
         "admission": "NOT_ADMITTED", "review_state": REVIEW_STATE,
         "model_provider": "NONE", "model_response_authority": "UNTRUSTED",
         "provider_gate": "PROVIDER_EXECUTION_NOT_AUTHORIZED",
         "extraction_method": "DETERMINISTIC_SYNTHETIC_FIXTURE"}

class Denied(Exception):
    pass

def need(ok, reason):
    if not ok:
        raise Denied(reason)

def exact(obj, keys, reason):
    need(isinstance(obj, dict) and set(obj) == set(keys), reason)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def resolve(request):
    result = {"schema_version": VERSION, **FLAGS, "decision": "ABSTAIN",
              "reason": "INVALID_REQUEST", "provenance": {"availability": "UNAVAILABLE"}}
    try:
        exact(request, ("schema_version", "tenant", "purpose", "as_of", "sources", "candidate"), "INVALID_REQUEST")
        need(request["schema_version"] == VERSION, "SCHEMA_MISMATCH")
        need(request["tenant"] == "SYNTHETIC_TENANT", "TENANT_MISMATCH")
        need(request["purpose"] == REVIEW_QUEUE, "PURPOSE_MISMATCH")
        need(request["as_of"] == "2026-01-01", "STALE_SNAPSHOT")
        need(isinstance(request["sources"], list) and len(request["sources"]) == 1, "MISSING_OR_CONFLICTING_SOURCE")
        source = request["sources"][0]
        exact(source, ("source_id", "source_version_id", "current_version_id", "tenant", "purpose", "source_text", "content_sha256", "rights_snapshot", "rights_sha256"), "INVALID_SOURCE")
        need(source["source_id"] == "SYN-SOURCE-ALPHA" and source["source_version_id"] == source["current_version_id"] == "syn-source-version-1", "SOURCE_VERSION_MISMATCH")
        need(source["tenant"] == request["tenant"], "TENANT_MISMATCH")
        need(source["purpose"] == request["purpose"], "PURPOSE_MISMATCH")
        need(isinstance(source["source_text"], str), "INVALID_SOURCE_BYTES")
        try:
            data = source["source_text"].encode("utf-8")
        except UnicodeError:
            raise Denied("INVALID_UTF8")
        need(0 < len(data) <= MAX_SOURCE_BYTES, "SOURCE_SIZE_INVALID")
        need(data.startswith(b"SYNTHETIC-FIXTURE:"), "SYNTHETIC_SOURCE_REQUIRED")
        need(source["content_sha256"] == sha(data), "SOURCE_DIGEST_MISMATCH")
        rights = source["rights_snapshot"]
        exact(rights, ("source_version_id", "tenant", "purpose", "status", "license", "checked_as_of", "authority"), "INVALID_RIGHTS")
        need(source["rights_sha256"] == digest(rights), "RIGHTS_DIGEST_MISMATCH")
        need(rights == {"source_version_id": source["source_version_id"], "tenant": request["tenant"], "purpose": request["purpose"], "status": "ADMITTED", "license": "SYNTHETIC_FIXTURE_ONLY", "checked_as_of": request["as_of"], "authority": "UNTRUSTED_SYNTHETIC"}, "RIGHTS_NOT_ELIGIBLE")
        candidate = request["candidate"]
        exact(candidate, ("candidate_revision_id", "candidate_revision_sha256", "content"), "INVALID_CANDIDATE")
        need(candidate["candidate_revision_id"] == "SYN-CANDIDATE-REV-1", "CANDIDATE_VERSION_MISMATCH")
        content = candidate["content"]
        exact(content, ("source_id", "source_version_id", "source_sha256", "rights_sha256", "claim_code", "safety_review", "evidence_span_refs"), "INVALID_CANDIDATE_CONTENT")
        need(candidate["candidate_revision_sha256"] == digest(content), "CANDIDATE_DIGEST_MISMATCH")
        need((content["source_id"], content["source_version_id"], content["source_sha256"], content["rights_sha256"]) == (source["source_id"], source["source_version_id"], source["content_sha256"], source["rights_sha256"]), "CANDIDATE_SOURCE_MISMATCH")
        need(content["claim_code"] == "SYN-CANDIDATE-ALPHA", "UNSUPPORTED_CLAIM")
        need(content["safety_review"] == "NOT_REVIEWED", "SAFETY_REVIEW_INVALID")
        spans = content["evidence_span_refs"]
        need(isinstance(spans, list) and 0 < len(spans) <= 8, "EVIDENCE_COUNT_INVALID")
        canonical_input = []
        for span in spans:
            exact(span, ("source_version_id", "locator", "start", "end", "slice_sha256"), "INVALID_EVIDENCE_SPAN")
            need(type(span["start"]) is int and type(span["end"]) is int and isinstance(span["locator"], str) and len(span["locator"]) <= 32, "INVALID_EVIDENCE_SPAN")
            canonical_input.append({k: span[k] for k in ("source_version_id", "locator", "start", "end")})
        try:
            proof = _canonical_spans(canonical_input, source["source_version_id"], data)
        except PreviewParseError as exc:
            raise Denied(exc.code)
        for span in spans:
            start, end = span["start"], span["end"]
            try:
                data[:start].decode("utf-8"); data[:end].decode("utf-8"); data[start:end].decode("utf-8")
            except UnicodeError:
                raise Denied("UTF8_BOUNDARY_INVALID")
            need(span["slice_sha256"] == sha(data[start:end]), "EVIDENCE_SLICE_MISMATCH")
        result.update(decision="CANDIDATE_PREVIEW_ONLY", reason="SYNTHETIC_REVIEW_HANDOFF_ONLY",
                      provenance={"availability": "PINNED_UNTRUSTED", "source_id": source["source_id"],
                      "source_version_id": source["source_version_id"], "source_sha256": source["content_sha256"],
                      "rights_sha256": source["rights_sha256"], "candidate_revision_id": candidate["candidate_revision_id"],
                      "candidate_revision_sha256": candidate["candidate_revision_sha256"],
                      "evidence_count": len(proof), "evidence_proofs": proof,
                      "safety_review": "NOT_REVIEWED", "claim_semantics": "UNVERIFIED"})
    except Denied as exc:
        result["reason"] = str(exc)
    return result

def main():
    try:
        need(len(sys.argv) == 2, "INVALID_REQUEST")
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = resolve(data)
    except (Denied, OSError, UnicodeError, ValueError):
        result = {"schema_version": VERSION, **FLAGS, "decision": "ABSTAIN", "reason": "INVALID_REQUEST", "provenance": {"availability": "UNAVAILABLE"}}
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
