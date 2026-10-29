"""Offline SourceVersion → Submission → CandidateRevision → ReviewWorkItem gate.

This is eligibility for a review handoff only. It does not write SQL, emit
outbox events, create a HumanReviewDecision, or admit a ProtocolVersion.
C04 and C05 stay KDB-only and inactive.

Fields come from SQL 001 plus O1/O2/O3. Pins that those contracts do not
define are reported as gaps, not invented as required checks.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from tenant_scope import require_tenant_scope

SHA256_HEX = r"^[0-9a-f]{64}$"
UUID_RE = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

SOURCE_CLASSES = frozenset(
    {
        "PUBLIC_LINK",
        "LICENSED_DOCUMENT",
        "AUTHORIZED_UPLOAD",
        "OWNER_AUTHORED",
        "MEDIA_REFERENCE",
    }
)
ORIGIN_OWNERS = frozenset({"ARCAVA", "KDB", "APPROVED_EXTERNAL"})
RIGHTS_OK = "ADMITTED"
REVIEW_STATE = "PENDING_REVIEW"
WORK_ITEM_STATE = "REQUESTED"
REVIEW_QUEUE = "KDB_HUMAN_REVIEW"
OWNER_NAMESPACE = "KDB"
SUBMISSION_RECORDED = "RECORDED"
VALIDATION_OK = frozenset({"STRUCTURE_VALIDATED", "PENDING_VALIDATION"})

SOURCE_KEYS = frozenset(
    {
        "source_id",
        "tenant_scope",
        "source_class",
        "external_locator",
        "rights_status",
        "owner_namespace",
        "created_at",
    }
)
SOURCE_VERSION_KEYS = frozenset(
    {
        "source_version_id",
        "source_id",
        "tenant_scope",
        "content_sha256",
        "rights_snapshot",
        "rights_snapshot_sha256",
        "media_type",
        "source_version_no",
        "acquired_at",
        "created_at",
    }
)
SUBMISSION_KEYS = frozenset(
    {
        "submission_id",
        "tenant_scope",
        "origin_owner",
        "idempotency_key",
        "request_sha256",
        "principal_context_ref",
        "access_decision_ref",
        "purpose",
        "source_version_id",
        "status",
        "created_at",
    }
)
CANDIDATE_KEYS = frozenset(
    {
        "candidate_revision_id",
        "candidate_id",
        "revision_no",
        "tenant_scope",
        "source_version_id",
        "submission_id",
        "proposal_command_id",
        "content_sha256",
        "evidence_span_refs",
        "proposal_payload",
        "validation_state",
        "review_state",
        "created_at",
    }
)
WORK_ITEM_KEYS = frozenset(
    {
        "review_work_item_id",
        "candidate_revision_id",
        "tenant_scope",
        "owner_queue",
        "state",
        "correlation_id",
        "created_at",
    }
)
SPAN_KEYS = frozenset({"source_version_id", "locator", "start", "end"})
CHAIN_KEYS = frozenset(
    {
        "source",
        "source_version",
        "source_versions",
        "submission",
        "prior_submissions",
        "candidate_revision",
        "review_work_item",
    }
)
UNTRUSTED_CLAIM_KEYS = frozenset(
    {
        "role",
        "is_admin",
        "auto_approve",
        "auto_approved",
        "approved",
        "decision",
        "human_signed",
        "publisher",
        "kdb.tenant_scope",
        "tenant_id",
        "bypass",
        "canonical",
        "protocol_version_id",
    }
)
REVIEWER_FLAG_KEYS = frozenset(
    {"auto_approve", "auto_approved", "approved", "decision", "human_signed"}
)

CONTRACT_GAPS = (
    "SEMANTIC_DESCRIPTOR_VERSION_PIN_ABSENT_FROM_O1_O2_O3_AND_SQL_001",
    "TAXONOMY_VERSION_PIN_ABSENT_FROM_O1_O2_O3_AND_SQL_001",
    "SEMANTIC_RULE_VERSION_PIN_ABSENT_FROM_O1_O2_O3_AND_SQL_001",
    "DERIVATION_VERSION_TABLE_ABSENT_FROM_12_TABLE_ADR",
    "EVIDENCE_VERSION_TABLE_ABSENT_FROM_12_TABLE_ADR",
    "PRINCIPAL_AND_ACCESS_REFS_ARE_STRINGS_NOT_TRUSTED_PIAC",
    "C04_HUMAN_REVIEW_DECISION_HAS_NO_WRITE_API",
    "C05_CANONICAL_ADMISSION_HAS_NO_WRITE_API",
)


class EligibilityError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.db_write = "NOT_ADMITTED"
        self.c04_human_decision = "NOT_WRITTEN"
        self.c05_canonical_admission = "NOT_WRITTEN"


class EligibilityResult:
    decision = "ELIGIBLE_FOR_REVIEW_HANDOFF"
    code = "PENDING_REVIEW_HANDOFF_ELIGIBLE"
    db_write = "NOT_ADMITTED"
    c04_human_decision = "NOT_WRITTEN"
    c05_canonical_admission = "NOT_WRITTEN"
    contract_gaps = CONTRACT_GAPS

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "code": self.code,
            "db_write": self.db_write,
            "c04_human_decision": self.c04_human_decision,
            "c05_canonical_admission": self.c05_canonical_admission,
            "contract_gaps": list(self.contract_gaps),
        }


def _deny(code: str) -> None:
    raise EligibilityError(code)


def _need_dict(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _deny(code)
    return value


def _need_str(value: Any, code: str, *, min_len: int = 1, max_len: int | None = None) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        _deny(code)
    if min_len and len(value) < min_len:
        _deny(code)
    if max_len is not None and len(value) > max_len:
        _deny(code)
    return value


def _need_uuid(value: Any, code: str) -> str:
    text = _need_str(value, code)
    if re.fullmatch(UUID_RE, text) is None:
        _deny(code)
    return text.lower()


def _need_sha(value: Any, code: str) -> str:
    text = _need_str(value, code, min_len=64, max_len=64)
    if re.fullmatch(SHA256_HEX, text) is None:
        _deny(code)
    return text


def _need_int_pos(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _deny(code)
    return value


def _forbid_unknown(record: Mapping[str, Any], allowed: frozenset[str], code: str) -> None:
    extra = set(record) - allowed
    if extra & UNTRUSTED_CLAIM_KEYS:
        _deny("UNTRUSTED_CLAIM")
    if extra & REVIEWER_FLAG_KEYS:
        _deny("CONTRADICTORY_REVIEWER_FLAG")
    if extra:
        _deny(code)


def _tenant(value: Any) -> str:
    return require_tenant_scope(value)


def _same_tenant(expected: str, value: Any, code: str = "CROSS_TENANT") -> str:
    got = _tenant(value)
    if got != expected:
        _deny(code)
    return got


def evaluate_review_eligibility(chain: Mapping[str, Any] | None) -> EligibilityResult:
    raw = _need_dict(chain, "INVALID_CHAIN")
    _forbid_unknown(raw, CHAIN_KEYS, "UNTRUSTED_CLAIM")
    if "human_review_decision" in raw or "protocol_version" in raw:
        _deny("CONTRADICTORY_REVIEWER_FLAG")

    source = deepcopy(_need_dict(raw.get("source"), "MISSING_SOURCE"))
    version = deepcopy(_need_dict(raw.get("source_version"), "ABSENT_SOURCE_VERSION_LINK"))
    submission = deepcopy(_need_dict(raw.get("submission"), "MISSING_SUBMISSION"))
    candidate = deepcopy(_need_dict(raw.get("candidate_revision"), "MISSING_CANDIDATE_REVISION"))
    work_item = deepcopy(_need_dict(raw.get("review_work_item"), "MISSING_REVIEW_WORK_ITEM"))

    _forbid_unknown(source, SOURCE_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(version, SOURCE_VERSION_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(submission, SUBMISSION_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(candidate, CANDIDATE_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(work_item, WORK_ITEM_KEYS, "UNTRUSTED_CLAIM")

    tenant = _tenant(source.get("tenant_scope"))
    _same_tenant(tenant, version.get("tenant_scope"))
    _same_tenant(tenant, submission.get("tenant_scope"))
    _same_tenant(tenant, candidate.get("tenant_scope"))
    _same_tenant(tenant, work_item.get("tenant_scope"))

    source_id = _need_uuid(source.get("source_id"), "INVALID_SOURCE_ID")
    if source.get("owner_namespace") != OWNER_NAMESPACE:
        _deny("OWNER_NAMESPACE_DENIED")
    if source.get("source_class") not in SOURCE_CLASSES:
        _deny("INVALID_SOURCE_CLASS")
    _need_str(source.get("external_locator"), "INVALID_SOURCE_LOCATOR", max_len=4096)

    rights_status = source.get("rights_status")
    if rights_status == "REVOKED":
        _deny("REVOKED_SOURCE")
    if rights_status in {"PENDING", "BLOCKED"}:
        _deny("MISSING_RIGHTS")
    if rights_status != RIGHTS_OK:
        _deny("MISSING_RIGHTS")

    source_version_id = _need_uuid(version.get("source_version_id"), "ABSENT_SOURCE_VERSION_LINK")
    if _need_uuid(version.get("source_id"), "ABSENT_SOURCE_VERSION_LINK") != source_id:
        _deny("WRONG_SOURCE_VERSION_LINK")
    content_sha = _need_sha(version.get("content_sha256"), "MISMATCHED_CONTENT_DIGEST")
    rights_sha = _need_sha(version.get("rights_snapshot_sha256"), "MISMATCHED_RIGHTS_DIGEST")
    snapshot = _need_dict(version.get("rights_snapshot"), "MISSING_RIGHTS")
    if snapshot.get("rights_status") != RIGHTS_OK:
        _deny("MISSING_RIGHTS")
    _need_str(snapshot.get("rights_basis"), "MISSING_RIGHTS")
    purposes = snapshot.get("allowed_purposes")
    if not isinstance(purposes, list) or not purposes or any(not isinstance(item, str) or item.strip() == "" for item in purposes):
        _deny("MISSING_RIGHTS")
    version_no = _need_int_pos(version.get("source_version_no"), "INVALID_SOURCE_VERSION_NO")
    _need_str(version.get("media_type"), "INVALID_MEDIA_TYPE")
    _need_str(version.get("acquired_at"), "INVALID_ACQUIRED_AT")

    extras = raw.get("source_versions", [])
    if extras is None:
        extras = []
    if not isinstance(extras, list):
        _deny("INVALID_SOURCE_VERSIONS")
    bound_is_latest = True
    for extra in extras:
        other = _need_dict(extra, "INVALID_SOURCE_VERSIONS")
        _forbid_unknown(other, SOURCE_VERSION_KEYS, "UNTRUSTED_CLAIM")
        if _need_uuid(other.get("source_id"), "WRONG_SOURCE_VERSION_LINK") != source_id:
            continue
        _same_tenant(tenant, other.get("tenant_scope"))
        other_version_id = _need_uuid(other.get("source_version_id"), "ABSENT_SOURCE_VERSION_LINK")
        if other_version_id == source_version_id:
            if _need_sha(other.get("content_sha256"), "MISMATCHED_CONTENT_DIGEST") != content_sha:
                _deny("MISMATCHED_CONTENT_DIGEST")
            if _need_sha(other.get("rights_snapshot_sha256"), "MISMATCHED_RIGHTS_DIGEST") != rights_sha:
                _deny("MISMATCHED_RIGHTS_DIGEST")
        other_no = _need_int_pos(other.get("source_version_no"), "INVALID_SOURCE_VERSION_NO")
        if other_no > version_no:
            bound_is_latest = False
    if not bound_is_latest:
        _deny("STALE_SOURCE_VERSION")

    submission_id = _need_uuid(submission.get("submission_id"), "INVALID_SUBMISSION_ID")
    if submission.get("origin_owner") not in ORIGIN_OWNERS:
        _deny("INVALID_ORIGIN_OWNER")
    idempotency = _need_str(submission.get("idempotency_key"), "INVALID_IDEMPOTENCY_KEY", min_len=8, max_len=256)
    request_sha = _need_sha(submission.get("request_sha256"), "INVALID_REQUEST_DIGEST")
    _need_str(submission.get("principal_context_ref"), "UNTRUSTED_CLAIM")
    _need_str(submission.get("access_decision_ref"), "UNTRUSTED_CLAIM")
    purpose = _need_str(submission.get("purpose"), "WRONG_PURPOSE")
    if purpose not in purposes:
        _deny("WRONG_PURPOSE")
    if _need_uuid(submission.get("source_version_id"), "ABSENT_SOURCE_VERSION_LINK") != source_version_id:
        _deny("WRONG_SOURCE_VERSION_LINK")
    if submission.get("status", SUBMISSION_RECORDED) != SUBMISSION_RECORDED:
        _deny("SUBMISSION_NOT_RECORDED")

    priors = raw.get("prior_submissions", [])
    if priors is None:
        priors = []
    if not isinstance(priors, list):
        _deny("INVALID_PRIOR_SUBMISSIONS")
    for prior in priors:
        other = _need_dict(prior, "INVALID_PRIOR_SUBMISSIONS")
        _forbid_unknown(other, SUBMISSION_KEYS, "UNTRUSTED_CLAIM")
        same_key = (
            _same_tenant(tenant, other.get("tenant_scope")) == tenant
            and other.get("origin_owner") == submission.get("origin_owner")
            and other.get("idempotency_key") == idempotency
        )
        if not same_key:
            continue
        other_id = _need_uuid(other.get("submission_id"), "INVALID_SUBMISSION_ID")
        other_sha = _need_sha(other.get("request_sha256"), "INVALID_REQUEST_DIGEST")
        if other_sha != request_sha:
            _deny("CONFLICTING_SUBMISSION")
        if other_id != submission_id:
            _deny("DUPLICATE_SUBMISSION")

    candidate_revision_id = _need_uuid(candidate.get("candidate_revision_id"), "INVALID_CANDIDATE_REVISION_ID")
    _need_uuid(candidate.get("candidate_id"), "INVALID_CANDIDATE_ID")
    _need_int_pos(candidate.get("revision_no"), "INVALID_REVISION_NO")
    if _need_uuid(candidate.get("source_version_id"), "ABSENT_SOURCE_VERSION_LINK") != source_version_id:
        _deny("WRONG_SOURCE_VERSION_LINK")
    if _need_uuid(candidate.get("submission_id"), "INVALID_SUBMISSION_ID") != submission_id:
        _deny("WRONG_SUBMISSION_LINK")
    _need_uuid(candidate.get("proposal_command_id"), "INVALID_PROPOSAL_COMMAND_ID")
    _need_sha(candidate.get("content_sha256"), "MISMATCHED_CONTENT_DIGEST")
    payload = _need_dict(candidate.get("proposal_payload"), "INVALID_PROPOSAL_PAYLOAD")
    if len(payload) < 1:
        _deny("INVALID_PROPOSAL_PAYLOAD")
    if candidate.get("review_state") != REVIEW_STATE:
        _deny("CONTRADICTORY_REVIEWER_FLAG")
    if candidate.get("validation_state") not in VALIDATION_OK:
        if candidate.get("validation_state") in {"RIGHTS_BLOCKED"}:
            _deny("MISSING_RIGHTS")
        if candidate.get("validation_state") in {"INSUFFICIENT_EVIDENCE", "QUARANTINED"}:
            _deny("EMPTY_EVIDENCE")
        _deny("CANDIDATE_NOT_ELIGIBLE")

    spans = candidate.get("evidence_span_refs")
    if not isinstance(spans, list) or len(spans) < 1:
        _deny("EMPTY_EVIDENCE")
    for span in spans:
        item = _need_dict(span, "MALFORMED_EVIDENCE_SPAN")
        _forbid_unknown(item, SPAN_KEYS, "MALFORMED_EVIDENCE_SPAN")
        if _need_uuid(item.get("source_version_id"), "WRONG_SOURCE_VERSION_LINK") != source_version_id:
            _deny("WRONG_SOURCE_VERSION_LINK")
        locator = _need_str(item.get("locator"), "MALFORMED_EVIDENCE_SPAN")
        if len(locator) > 4096:
            _deny("OUT_OF_RANGE_EVIDENCE_SPAN")
        start = item.get("start")
        end = item.get("end")
        if start is not None or end is not None:
            if isinstance(start, bool) or isinstance(end, bool):
                _deny("MALFORMED_EVIDENCE_SPAN")
            if not isinstance(start, int) or not isinstance(end, int):
                _deny("MALFORMED_EVIDENCE_SPAN")
            if start < 0 or end < 0 or start > end:
                _deny("OUT_OF_RANGE_EVIDENCE_SPAN")

    if _need_uuid(work_item.get("candidate_revision_id"), "WRONG_REVIEW_WORK_ITEM") != candidate_revision_id:
        _deny("WRONG_REVIEW_WORK_ITEM")
    _need_uuid(work_item.get("review_work_item_id"), "INVALID_REVIEW_WORK_ITEM_ID")
    _need_uuid(work_item.get("correlation_id"), "INVALID_CORRELATION_ID")
    if work_item.get("owner_queue") != REVIEW_QUEUE:
        _deny("CONTRADICTORY_REVIEWER_FLAG")
    if work_item.get("state") != WORK_ITEM_STATE:
        _deny("CONTRADICTORY_REVIEWER_FLAG")

    # Declared digest copies, when present on the version vs a second pin, must match.
    declared_rights = version.get("rights_snapshot_sha256")
    if declared_rights != rights_sha:
        _deny("MISMATCHED_RIGHTS_DIGEST")
    return EligibilityResult()
