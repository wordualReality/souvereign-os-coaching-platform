"""GC01 synthetic command validation and local eligibility; no side effects."""
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import jsonschema
from offline_evidence_bound_review import _canonical_spans
from offline_seasonal_botanical import digest
from provenance_eligibility import EligibilityError, evaluate_review_eligibility
from review_handoff_preview import PreviewParseError

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ("o1_source_ingest.schema.json", "o2_candidate_proposal.schema.json", "o3_review_handoff.schema.json")
IDS = {
    "source": "aaaaaaaa-bbbb-4ccc-8ddd-111111111111",
    "version": "aaaaaaaa-bbbb-4ccc-8ddd-222222222222",
    "submission": "aaaaaaaa-bbbb-4ccc-8ddd-333333333333",
    "candidate": "aaaaaaaa-bbbb-4ccc-8ddd-444444444444",
    "revision": "aaaaaaaa-bbbb-4ccc-8ddd-555555555555",
    "work": "aaaaaaaa-bbbb-4ccc-8ddd-777777777777",
    "correlation": "aaaaaaaa-bbbb-4ccc-8ddd-888888888888",
}

class Denied(Exception):
    def __init__(self, stage, code):
        self.stage, self.code = stage, code

def need(value, code, stage="BINDING_DENIED"):
    if not value:
        raise Denied(stage, code)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def build_fixture(seed):
    need(seed == {"schema_version": "kdb.gc01.fixture.v1", "source_text": "SYNTHETIC-FIXTURE: alpha café."}, "UNSUPPORTED_FIXTURE")
    data = seed["source_text"].encode("utf-8")
    rights = {"rights_status": "ADMITTED", "rights_basis": "synthetic-fixture", "allowed_purposes": ["KNOWLEDGE_INTAKE"]}
    spans = [{"source_version_id": IDS["version"], "locator": "bytes:19-23", "start": 19, "end": 24}]
    proposal = {"title": "synthetic-candidate"}
    base = {"schema_version": "1.0", "correlation_id": IDS["correlation"], "issued_at": "2026-01-01T00:00:00Z", "origin_owner": "KDB", "tenant_scope": "TENANT_SYNTH_A", "principal_context_ref": "UNTRUSTED_FIXTURE_REF:PRINCIPAL", "access_decision_ref": "UNTRUSTED_FIXTURE_REF:ACCESS", "purpose": "KNOWLEDGE_INTAKE"}
    commands = []
    payloads = [
        {"submission_id": IDS["submission"], "source_class": "OWNER_AUTHORED", "source_locator": "synthetic://gc01/source", "content_sha256": sha(data), "rights_snapshot_sha256": digest(rights), "rights": rights, "acquired_at": "2026-01-01T00:00:00Z"},
        {"submission_id": IDS["submission"], "source_version_id": IDS["version"], "candidate_id": IDS["candidate"], "revision_no": 1, "content_sha256": digest(proposal), "evidence_spans": spans, "proposal_payload": proposal},
        {"candidate_revision_id": IDS["revision"], "review_queue": "KDB_HUMAN_REVIEW"},
    ]
    for i, contract in enumerate(("CT-KDB-R03-PIPE-001", "MAP04-C02", "MAP04-C03")):
        commands.append({**base, "command_id": f"aaaaaaaa-bbbb-4ccc-8ddd-{i+1:012d}", "contract_id": contract, "idempotency_key": f"gc01-command-{i+1:03d}", "payload": payloads[i]})
    return {"schema_version": "kdb.gc01.input.v1", "source_text": seed["source_text"], "source_version_projection": {"mapping": "SYNTHETIC_UUID_PROJECTION_ONLY", "source_id": IDS["source"], "source_version_id": IDS["version"], "source_version_no": 1}, "review_work_item_id": IDS["work"], "commands": commands, "prior_submissions": [], "source_versions": []}

def run(bundle):
    receipt = {"decision": "ABSTAIN", "stage": "INPUT_DENIED", "reason": "INVALID_INPUT", "scope": "SYNTHETIC_TEST_ONLY", "admission": "NOT_ADMITTED", "execution": "NON_EXECUTABLE", "authority": "UNTRUSTED_FIXTURE_REF", "mapping": "SYNTHETIC_UUID_PROJECTION_ONLY", "review_state": "PENDING_REVIEW", "work_item_state": "REQUESTED"}
    try:
        need(isinstance(bundle, dict) and set(bundle) == {"schema_version", "source_text", "source_version_projection", "review_work_item_id", "commands", "prior_submissions", "source_versions"} and bundle["schema_version"] == "kdb.gc01.input.v1", "INVALID_INPUT")
        cmds = bundle["commands"]
        need(isinstance(cmds, list) and len(cmds) == 3, "INVALID_COMMAND_COUNT")
        for cmd, name in zip(cmds, SCHEMAS):
            schema = json.loads((ROOT / "contracts/kdb" / name).read_text())
            try:
                jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(cmd)
            except jsonschema.ValidationError:
                raise Denied("SCHEMA_DENIED", "INVALID_COMMAND_SCHEMA")
            try:
                stamp = datetime.fromisoformat(cmd["issued_at"].replace("Z", "+00:00"))
                need(stamp.tzinfo is not None and "T" in cmd["issued_at"], "INVALID_ISSUED_AT", "SCHEMA_DENIED")
            except ValueError:
                raise Denied("SCHEMA_DENIED", "INVALID_ISSUED_AT")
        o1, o2, o3 = cmds
        for field in ("correlation_id", "tenant_scope", "origin_owner", "principal_context_ref", "access_decision_ref", "purpose", "issued_at"):
            need(o1[field] == o2[field] == o3[field], "COMMAND_CONTEXT_MISMATCH")
        need(o1["tenant_scope"] == "TENANT_SYNTH_A" and o1["origin_owner"] == "KDB" and o1["purpose"] == "KNOWLEDGE_INTAKE", "SYNTHETIC_CONTEXT_REQUIRED")
        need(o1["issued_at"] == "2026-01-01T00:00:00Z" and o1["payload"]["acquired_at"] == "2026-01-01T00:00:00Z", "FIXTURE_FRESHNESS_MISMATCH")
        need(o1["principal_context_ref"] == "UNTRUSTED_FIXTURE_REF:PRINCIPAL" and o1["access_decision_ref"] == "UNTRUSTED_FIXTURE_REF:ACCESS", "UNTRUSTED_REF_REQUIRED")
        need(len({c["command_id"] for c in cmds}) == 3 and len({c["idempotency_key"] for c in cmds}) == 3, "CONFLICTING_COMMAND_IDEMPOTENCY")
        projection = bundle["source_version_projection"]
        need(projection == {"mapping": "SYNTHETIC_UUID_PROJECTION_ONLY", "source_id": IDS["source"], "source_version_id": IDS["version"], "source_version_no": 1}, "INVALID_SOURCE_PROJECTION")
        need(bundle["review_work_item_id"] == IDS["work"], "INVALID_WORK_ITEM")
        p1, p2, p3 = (c["payload"] for c in cmds)
        need(p1["submission_id"] == p2["submission_id"] == IDS["submission"] and p2["source_version_id"] == projection["source_version_id"], "WRONG_SOURCE_SUBMISSION_LINK")
        need(p2["candidate_id"] == IDS["candidate"] and p3["candidate_revision_id"] == IDS["revision"], "WRONG_CANDIDATE_LINK")
        need(p1["source_class"] == "OWNER_AUTHORED" and p1["source_locator"] == "synthetic://gc01/source", "UNSUPPORTED_SOURCE")
        need(isinstance(bundle["source_text"], str), "INVALID_SOURCE")
        try:
            data = bundle["source_text"].encode("utf-8")
        except UnicodeError:
            raise Denied("BINDING_DENIED", "INVALID_UTF8")
        need(data.startswith(b"SYNTHETIC-FIXTURE:") and 0 < len(data) <= 65536, "UNSUPPORTED_SOURCE")
        need(sha(data) == p1["content_sha256"], "SOURCE_DIGEST_MISMATCH")
        need(p1["content_sha256"] == "d1a2d945e6060cec9d215a2a839f26ff52bf7e7071e5eddffd2310032e516f8a", "ORIGINAL_FIXTURE_PIN_MISMATCH")
        rights = p1["rights"]
        need(rights == {"rights_status": "ADMITTED", "rights_basis": "synthetic-fixture", "allowed_purposes": ["KNOWLEDGE_INTAKE"]}, "RIGHTS_NOT_ELIGIBLE")
        need(digest(rights) == p1["rights_snapshot_sha256"], "RIGHTS_DIGEST_MISMATCH")
        need(p2["proposal_payload"] == {"title": "synthetic-candidate"}, "UNSUPPORTED_PROPOSAL")
        need(digest(p2["proposal_payload"]) == p2["content_sha256"], "CANDIDATE_DIGEST_MISMATCH")
        try:
            proofs = _canonical_spans(p2["evidence_spans"], projection["source_version_id"], data)
        except PreviewParseError as exc:
            raise Denied("EVIDENCE_DENIED", exc.code)
        for span in proofs:
            try:
                data[:span["byte_start"]].decode("utf-8"); data[:span["byte_end_exclusive"]].decode("utf-8")
            except UnicodeError:
                raise Denied("EVIDENCE_DENIED", "UTF8_BOUNDARY_INVALID")
        prior = bundle["prior_submissions"]
        need(isinstance(prior, list) and len(prior) <= 1, "INVALID_REPLAY")
        request_sha = digest(o1)
        chain = {
            "source": {"source_id": projection["source_id"], "tenant_scope": o1["tenant_scope"], "source_class": p1["source_class"], "external_locator": p1["source_locator"], "rights_status": rights["rights_status"], "owner_namespace": "KDB"},
            "source_version": {"source_version_id": projection["source_version_id"], "source_id": projection["source_id"], "tenant_scope": o1["tenant_scope"], "content_sha256": p1["content_sha256"], "rights_snapshot": rights, "rights_snapshot_sha256": p1["rights_snapshot_sha256"], "media_type": "text/plain", "source_version_no": projection["source_version_no"], "acquired_at": p1["acquired_at"]},
            "submission": {"submission_id": p1["submission_id"], "tenant_scope": o1["tenant_scope"], "origin_owner": o1["origin_owner"], "idempotency_key": o1["idempotency_key"], "request_sha256": request_sha, "principal_context_ref": o1["principal_context_ref"], "access_decision_ref": o1["access_decision_ref"], "purpose": o1["purpose"], "source_version_id": projection["source_version_id"], "status": "RECORDED"},
            "candidate_revision": {"candidate_revision_id": p3["candidate_revision_id"], "candidate_id": p2["candidate_id"], "revision_no": p2["revision_no"], "tenant_scope": o2["tenant_scope"], "source_version_id": p2["source_version_id"], "submission_id": p2["submission_id"], "proposal_command_id": o2["command_id"], "content_sha256": p2["content_sha256"], "evidence_span_refs": p2["evidence_spans"], "proposal_payload": p2["proposal_payload"], "validation_state": "STRUCTURE_VALIDATED", "review_state": "PENDING_REVIEW"},
            "review_work_item": {"review_work_item_id": bundle["review_work_item_id"], "candidate_revision_id": p3["candidate_revision_id"], "tenant_scope": o3["tenant_scope"], "owner_queue": p3["review_queue"], "state": "REQUESTED", "correlation_id": o3["correlation_id"]},
            "prior_submissions": prior,
            "source_versions": bundle["source_versions"],
        }
        try:
            eligibility = evaluate_review_eligibility(chain)
        except EligibilityError as exc:
            raise Denied("ELIGIBILITY_DENIED", exc.code)
        receipt.update(decision=eligibility.decision, stage="LOCAL_CHAIN_ELIGIBLE_FOR_REVIEW_HANDOFF", reason=eligibility.code, schema_check="O1_O2_O3_ENVELOPES_SCHEMA_VALID", evidence_check="LOCAL_BYTES_SPANS_VERIFIED", source_sha256=p1["content_sha256"], rights_sha256=p1["rights_snapshot_sha256"], candidate_sha256=p2["content_sha256"], command_set_sha256=digest(cmds), source_version_id=projection["source_version_id"], original_fixture_source_version="syn-source-version-1", original_fixture_source_sha256="d1a2d945e6060cec9d215a2a839f26ff52bf7e7071e5eddffd2310032e516f8a", original_fixture_commit="f7d093b58d1c91861d871294cc5392806c1206b4", evidence_count=len(proofs), gaps=list(eligibility.contract_gaps))
    except Denied as exc:
        receipt.update(stage=exc.stage, reason=exc.code)
    return receipt

def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("missing fixture")
        seed = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = run(build_fixture(seed))
    except (ValueError, OSError, UnicodeError, Denied):
        result = {"decision": "ABSTAIN", "reason": "INVALID_FIXTURE", "admission": "NOT_ADMITTED", "execution": "NON_EXECUTABLE"}
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
