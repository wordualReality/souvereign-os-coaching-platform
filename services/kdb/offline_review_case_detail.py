"""Offline review case detail. Not a reviewer assignment.

Selects one review_work_item_id from a P14 inbox batch after the full batch
is re-evaluated. The receipt is DETAIL_ONLY, SNAPSHOT_UNTRUSTED, NON_EXECUTABLE,
NOT_ASSIGNED, and NOT_ADMITTED. Pagination or status filters cannot select a
denied item. This is not a C04 case, C05 publication, or live reader.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from offline_review_inbox import (
    CARD_KEYS,
    FORBIDDEN_SUBSTRINGS,
    MAX_CHARS,
    MAX_ENTRIES,
    PACKET as INBOX_PACKET,
    QUEUE,
    inbox,
    parse_inbox_json,
)
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PACKET as PREVIEW_PACKET,
    REPAIR_PACKET,
    PreviewParseError,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P15-OFFLINE-REVIEW-CASE-DETAIL-01"
UUID_RE = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
CONSUMER_O1 = "kdb://m01/o1_source_ingest/1.0"
CONSUMER_O2 = "kdb://m01/o2_candidate_proposal/1.0"
CONSUMER_O3 = "kdb://m01/o3_review_handoff/1.0"
PROVENANCE_TRACE = {
    "tenant_scope_check": "CHECKED",
    "source_rights": "DECLARED_SYNTHETIC",
    "p08_eligibility": "LOCAL_ELIGIBLE_OFFLINE_ONLY",
    "declared_sha": "NOT_VERIFIED",
    "event_watermark": "UNKNOWN",
}
ELIGIBILITY_REASONS = (
    "TENANT_SCOPE_CHECKED",
    "P08_REVIEW_ELIGIBLE_OFFLINE",
    "P14_CARD_SELECTED",
)
EXPLICIT_GAPS = (
    "CONTENT_SHA_OPAQUE_UNPROVEN",
    "EVENT_WATERMARK_UNTRUSTED",
    "LIVE_PIAC_ISSUER_UNPROVEN",
    "C04_NOT_WRITTEN",
    "C05_NOT_WRITTEN",
    "HOSTED_VERIFIED_NO",
)


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def bound_work_item_id(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(UUID_RE, value) is None:
        _deny_parse("INVALID_WORK_ITEM_ID")
    return value.lower()


def _assert_redacted(blob: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")


def _receipt(
    *,
    snapshot_case_id: str | None,
    tenant_scope: str | None,
    detail_status: str,
    deny_code: str | None,
    detail: dict[str, Any] | None,
    commit: str,
    inbox_status: str | None,
    eligible_card_count: int,
    inbox_deny_code: str | None,
) -> dict[str, Any]:
    return {
        "packet": PACKET,
        "inbox_packet": INBOX_PACKET,
        "preview_packet": PREVIEW_PACKET,
        "repair_packet": REPAIR_PACKET,
        "df_adoption": "DF-20261029-01",
        "snapshot_case_id": snapshot_case_id,
        "tenant_scope": tenant_scope,
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "read_model": "NON_NORMATIVE_INTERNAL_PREVIEW",
        "detail_status": detail_status,
        "detail": detail,
        "deny_code": deny_code,
        "inbox_status": inbox_status,
        "inbox_deny_code": inbox_deny_code,
        "eligible_card_count": eligible_card_count,
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
        "source_commit_attestation": "LABEL_NOT_ATTESTED",
    }


def _detail_from_card(card: Mapping[str, Any]) -> dict[str, Any]:
    extra = set(card) - CARD_KEYS
    if extra:
        _deny_parse("PREVIEW_LEAK")
    if "media_type" in card:
        _deny_parse("PREVIEW_LEAK")
    if card.get("work_item_state") != "REQUESTED":
        _deny_parse("PREVIEW_LEAK")
    if card.get("review_queue") != QUEUE:
        _deny_parse("PREVIEW_LEAK")
    return {
        "review_queue": card["review_queue"],
        "work_item_state": card["work_item_state"],
        "tenant_scope": card["tenant_scope"],
        "source_id": card["source_id"],
        "source_version_id": card["source_version_id"],
        "source_version_no": card["source_version_no"],
        "submission_id": card["submission_id"],
        "candidate_id": card["candidate_id"],
        "candidate_revision_id": card["candidate_revision_id"],
        "revision_no": card["revision_no"],
        "review_work_item_id": card["review_work_item_id"],
        "correlation_id": card["correlation_id"],
        "rights_status": card["rights_status"],
        "evidence_span_count": card["evidence_span_count"],
        "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
        "consumer_o1": CONSUMER_O1,
        "consumer_o2": CONSUMER_O2,
        "consumer_o3": CONSUMER_O3,
        "provenance_trace": dict(PROVENANCE_TRACE),
        "eligibility_reasons": list(ELIGIBILITY_REASONS),
        "explicit_gaps": list(EXPLICIT_GAPS),
    }


def case_detail(
    payload: Mapping[str, Any] | None,
    work_item_id: Any,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    selected = bound_work_item_id(work_item_id)
    inbox_receipt = inbox(
        payload,
        commit=pin,
        status_filter=None,
        page=1,
        page_size=MAX_ENTRIES,
    )
    snapshot_case_id = inbox_receipt.get("snapshot_case_id")
    tenant_scope = inbox_receipt.get("tenant_scope")
    inbox_status = inbox_receipt.get("inbox_status")
    inbox_deny = inbox_receipt.get("deny_code")
    eligible = int(inbox_receipt.get("card_count") or 0)
    if inbox_status == "INBOX_DENIED" or inbox_deny:
        receipt = _receipt(
            snapshot_case_id=snapshot_case_id if isinstance(snapshot_case_id, str) else None,
            tenant_scope=tenant_scope if isinstance(tenant_scope, str) else None,
            detail_status="DETAIL_DENIED",
            deny_code=str(inbox_deny or "INBOX_DENIED"),
            detail=None,
            commit=pin,
            inbox_status=str(inbox_status or "INBOX_DENIED"),
            eligible_card_count=0,
            inbox_deny_code=str(inbox_deny or "INBOX_DENIED"),
        )
        _assert_redacted(json.dumps(receipt, sort_keys=True))
        return receipt
    matches = [
        card
        for card in inbox_receipt.get("cards") or []
        if str(card.get("review_work_item_id") or "").lower() == selected
    ]
    if len(matches) != 1:
        receipt = _receipt(
            snapshot_case_id=snapshot_case_id if isinstance(snapshot_case_id, str) else None,
            tenant_scope=tenant_scope if isinstance(tenant_scope, str) else None,
            detail_status="DETAIL_DENIED",
            deny_code="WORK_ITEM_NOT_SELECTABLE",
            detail=None,
            commit=pin,
            inbox_status=str(inbox_status or "PREVIEW_EMPTY"),
            eligible_card_count=eligible,
            inbox_deny_code=None,
        )
        blob = json.dumps(receipt, sort_keys=True)
        _assert_redacted(blob)
        if selected in blob:
            _deny_parse("PREVIEW_LEAK")
        return receipt
    detail = _detail_from_card(matches[0])
    receipt = _receipt(
        snapshot_case_id=snapshot_case_id if isinstance(snapshot_case_id, str) else None,
        tenant_scope=tenant_scope if isinstance(tenant_scope, str) else None,
        detail_status="DETAIL_ONLY",
        deny_code=None,
        detail=detail,
        commit=pin,
        inbox_status=str(inbox_status or "PREVIEW_ONLY"),
        eligible_card_count=eligible,
        inbox_deny_code=None,
    )
    blob = json.dumps(receipt, sort_keys=True)
    _assert_redacted(blob)
    if "READY" in blob:
        _deny_parse("PREVIEW_LEAK")
    return receipt


def case_detail_file(
    path: str | Path,
    work_item_id: Any,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    selected = bound_work_item_id(work_item_id)
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    payload = parse_inbox_json(text)
    return case_detail(payload, selected, commit=pin)
