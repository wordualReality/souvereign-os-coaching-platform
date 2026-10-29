"""Offline review-handoff preview. Not a reviewer assignment.

Assembles a redacted KDB_HUMAN_REVIEW queue card from O1/O2/O3 identities
after P07 tenant_scope and P08 provenance checks. A local PREVIEW_ONLY
result is NON_EXECUTABLE and NOT_ADMITTED. It does not write C04, C05,
outbox, or ingest. Revoked or pending rights, stale versions, cross-tenant
links, empty evidence, and forged reviewer claims produce no card.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from provenance_eligibility import EligibilityError, evaluate_review_eligibility
from tenant_scope import TenantScopeError, require_tenant_scope

PACKET = "KDB-M01-P13-OFFLINE-REVIEW-HANDOFF-PREVIEW-01"
QUEUE = "KDB_HUMAN_REVIEW"
MAX_CHARS = 65536
CASE_ID_RE = r"^[A-Za-z0-9._-]{1,64}$"
INPUT_KEYS = frozenset({"case_id", "expected_tenant_scope", "candidate_chain"})
FORGED_KEYS = frozenset(
    {
        "assigned_to",
        "assigned_reviewer",
        "reviewer_principal_ref",
        "human_review_decision",
        "auto_approve",
        "auto_approved",
        "human_signed",
        "publisher",
    }
)
REDACT_SUBSTRINGS = (
    "synthetic://",
    "KNOWLEDGE_INTAKE",
    "synthetic-candidate",
    "owner-authored-fixture",
    "synthetic-protocol",
)
ATC10_NAMED_CANDIDATES = (
    "Source",
    "SourceVersion",
    "CanonicalKnowledgeItem",
    "CanonicalKnowledgeVersion",
    "Claim",
    "Evidence",
    "CanonicalReviewCase",
    "KnowledgeSynthesisRun",
    "SynthesisCandidate",
    "RestrictedKnowledgeProjection",
    "RetrievalIndexProjection",
    "CanonicalLifecycleSignal",
    "BotanicalProfile",
    "TaxonomyVersion",
    "TaxonomyNode",
    "CanonicalClassificationBinding",
    "TranscriptArtifact",
    "SourceDerivationRecord",
)


class PreviewParseError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _forged(value: Any) -> bool:
    if isinstance(value, dict):
        if FORGED_KEYS & set(value):
            return True
        return any(_forged(item) for item in value.values())
    if isinstance(value, list):
        return any(_forged(item) for item in value)
    return False


def _receipt(
    *,
    case_id: str,
    preview_status: str,
    deny_code: str | None,
    queue_card: dict[str, Any] | None,
    commit: str,
) -> dict[str, Any]:
    return {
        "packet": PACKET,
        "df_adoption": "DF-20261029-01",
        "case_id": case_id,
        "preview_status": preview_status,
        "review_queue": QUEUE if preview_status == "PREVIEW_ONLY" else "NOT_QUEUED",
        "queue_card": queue_card,
        "deny_code": deny_code,
        "assignment": "NOT_ASSIGNED",
        "publication": "NOT_PUBLISHED",
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "db_write": "NOT_ADMITTED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
        "inventory_source": "UNCONFIRMED_ATC10_CANDIDATES",
        "logical_objects_claimed": "NOT_18_OF_18",
        "physical_sql001_tables": 12,
        "atc10_named_candidates": len(ATC10_NAMED_CANDIDATES),
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "source_commit": commit,
    }


def _queue_card(chain: Mapping[str, Any]) -> dict[str, Any]:
    source = chain["source"]
    version = chain["source_version"]
    submission = chain["submission"]
    candidate = chain["candidate_revision"]
    work = chain["review_work_item"]
    spans = candidate.get("evidence_span_refs") or []
    return {
        "review_queue": QUEUE,
        "work_item_state": str(work.get("state") or ""),
        "tenant_scope": str(source.get("tenant_scope") or ""),
        "source_id": str(source.get("source_id") or ""),
        "source_version_id": str(version.get("source_version_id") or ""),
        "source_version_no": int(version.get("source_version_no") or 0),
        "submission_id": str(submission.get("submission_id") or ""),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "candidate_revision_id": str(candidate.get("candidate_revision_id") or ""),
        "revision_no": int(candidate.get("revision_no") or 0),
        "review_work_item_id": str(work.get("review_work_item_id") or ""),
        "correlation_id": str(work.get("correlation_id") or ""),
        "rights_status": str(source.get("rights_status") or ""),
        "media_type": str(version.get("media_type") or ""),
        "evidence_span_count": len(spans) if isinstance(spans, list) else 0,
        "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
    }


def _assert_redacted(blob: str) -> None:
    for token in REDACT_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")


def preview(payload: Mapping[str, Any] | None, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    raw = deepcopy(payload if isinstance(payload, dict) else {})
    extra = set(raw) - INPUT_KEYS
    if extra:
        _deny_parse("UNTRUSTED_CLAIM")
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or re.fullmatch(CASE_ID_RE, case_id) is None:
        _deny_parse("INVALID_CASE_ID")
    if _forged(raw):
        return _receipt(
            case_id=case_id,
            preview_status="PREVIEW_DENIED",
            deny_code="FORGED_REVIEWER_CLAIM",
            queue_card=None,
            commit=commit,
        )
    try:
        expected = require_tenant_scope(raw.get("expected_tenant_scope"))
        chain = raw.get("candidate_chain")
        if not isinstance(chain, dict):
            _deny_parse("MISSING_CHAIN")
        require_tenant_scope(chain.get("source", {}).get("tenant_scope") if isinstance(chain.get("source"), dict) else None, expected)
    except TenantScopeError as exc:
        return _receipt(
            case_id=case_id,
            preview_status="PREVIEW_DENIED",
            deny_code=exc.code,
            queue_card=None,
            commit=commit,
        )
    try:
        evaluate_review_eligibility(chain)
    except EligibilityError as exc:
        return _receipt(
            case_id=case_id,
            preview_status="PREVIEW_DENIED",
            deny_code=exc.code,
            queue_card=None,
            commit=commit,
        )
    card = _queue_card(chain)
    receipt = _receipt(
        case_id=case_id,
        preview_status="PREVIEW_ONLY",
        deny_code=None,
        queue_card=card,
        commit=commit,
    )
    _assert_redacted(json.dumps(receipt, sort_keys=True))
    return receipt


def preview_file(path: str | Path, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    text_path = str(path)
    lowered = text_path.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("file:"):
        _deny_parse("NETWORK_PATH_DENIED")
    location = Path(path)
    if not location.is_file():
        _deny_parse("MISSING_INPUT_FILE")
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    text = location.read_text(encoding="utf-8")
    if len(text) > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PreviewParseError("MALFORMED_JSON") from exc
    if not isinstance(payload, dict):
        _deny_parse("INVALID_INPUT")
    return preview(payload, commit=commit)
