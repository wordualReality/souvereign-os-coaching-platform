"""Offline review-inbox read model. Not a reviewer assignment.

Aggregates P13R per-candidate previews into a sorted, filterable, redacted
list. The receipt is a NON-NORMATIVE INTERNAL PREVIEW. It is SNAPSHOT_UNTRUSTED,
NON_EXECUTABLE, NOT_ASSIGNED, and NOT_ADMITTED. It does not write C04, C05,
outbox, or ingest. Cross-tenant input yields no cards. Revocation wins for
every item that shares a SourceID.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    CASE_ID_RE,
    MAX_CHARS,
    PACKET as PREVIEW_PACKET,
    QUEUE,
    REPAIR_PACKET,
    PreviewParseError,
    _bounded_int,
    _no_duplicate_object,
    _reject_constant,
    _safe_local_file,
    bound_commit,
    preview,
)
from tenant_scope import TenantScopeError, require_tenant_scope

PACKET = "KDB-M01-P14-OFFLINE-REVIEW-INBOX-READMODEL-01"
MAX_ENTRIES = 32
MAX_PAGE = 1024
MAX_INBOX_NESTING = 10
ENVELOPE_KEYS = frozenset({"snapshot_case_id", "tenant_scope", "entries"})
STATUS_FILTERS = frozenset({"PREVIEW_ONLY", "PREVIEW_DENIED", "REQUESTED"})
CARD_KEYS = frozenset(
    {
        "review_queue",
        "work_item_state",
        "tenant_scope",
        "source_id",
        "source_version_id",
        "source_version_no",
        "submission_id",
        "candidate_id",
        "candidate_revision_id",
        "revision_no",
        "review_work_item_id",
        "correlation_id",
        "rights_status",
        "evidence_span_count",
        "content_digest_proof",
    }
)
FORBIDDEN_SUBSTRINGS = (
    "synthetic://",
    "KNOWLEDGE_INTAKE",
    "synthetic-candidate",
    "owner-authored-fixture",
    "synthetic-protocol",
)


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _inbox_nesting(value: Any, depth: int = 1) -> None:
    if depth > MAX_INBOX_NESTING:
        _deny_parse("INPUT_TOO_DEEP")
    if isinstance(value, dict):
        for item in value.values():
            _inbox_nesting(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _inbox_nesting(item, depth + 1)


def parse_inbox_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or text == "":
        _deny_parse("EMPTY_INPUT")
    if len(text) > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_no_duplicate_object,
            parse_int=_bounded_int,
            parse_constant=_reject_constant,
            strict=True,
        )
    except PreviewParseError:
        raise
    except json.JSONDecodeError as exc:
        raise PreviewParseError("MALFORMED_JSON") from exc
    except ValueError as exc:
        raise PreviewParseError("MALFORMED_JSON") from exc
    if not isinstance(payload, dict):
        _deny_parse("INVALID_INPUT")
    _inbox_nesting(payload)
    extra = set(payload) - ENVELOPE_KEYS
    if extra:
        _deny_parse("UNEXPECTED_INPUT_KEY")
    return payload


def _bound_page(page: int, page_size: int) -> tuple[int, int]:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1 or page > MAX_PAGE:
        _deny_parse("INVALID_PAGE")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
        _deny_parse("INVALID_PAGE_SIZE")
    if page_size > MAX_ENTRIES:
        _deny_parse("INVALID_PAGE_SIZE")
    return page, page_size


def _bound_status(status_filter: str | None) -> str | None:
    if status_filter in (None, ""):
        return None
    if not isinstance(status_filter, str) or status_filter not in STATUS_FILTERS:
        _deny_parse("INVALID_STATUS_FILTER")
    return status_filter


def _walk_tenant_scopes(value: Any, found: list[Any]) -> None:
    if isinstance(value, dict):
        if "tenant_scope" in value:
            found.append(value.get("tenant_scope"))
        if "expected_tenant_scope" in value:
            found.append(value.get("expected_tenant_scope"))
        for item in value.values():
            _walk_tenant_scopes(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_tenant_scopes(item, found)


def _receipt(
    *,
    snapshot_case_id: str,
    tenant_scope: str | None,
    inbox_status: str,
    deny_code: str | None,
    cards: list[dict[str, Any]],
    deny_counts: list[dict[str, Any]],
    commit: str,
    status_filter: str | None,
    page: int,
    page_size: int,
    card_count: int,
    deny_count: int,
) -> dict[str, Any]:
    page_count = 0 if card_count == 0 else math.ceil(card_count / page_size)
    return {
        "packet": PACKET,
        "preview_packet": PREVIEW_PACKET,
        "repair_packet": REPAIR_PACKET,
        "df_adoption": "DF-20261029-01",
        "snapshot_case_id": snapshot_case_id,
        "tenant_scope": tenant_scope,
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "read_model": "NON_NORMATIVE_INTERNAL_PREVIEW",
        "inbox_status": inbox_status,
        "review_queue": QUEUE if cards else "NOT_QUEUED",
        "cards": cards,
        "card_count": card_count,
        "page_card_count": len(cards),
        "deny_count": deny_count,
        "deny_code": deny_code,
        "deny_counts": deny_counts,
        "sort": "review_work_item_id",
        "status_filter": status_filter or "ALL_PREVIEW_CARDS",
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
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


def _deny_counts(codes: list[str]) -> list[dict[str, Any]]:
    tallies = Counter(codes)
    return [{"code": code, "count": tallies[code]} for code in sorted(tallies)]


def _assert_card(card: Mapping[str, Any]) -> dict[str, Any]:
    extra = set(card) - CARD_KEYS
    if extra:
        _deny_parse("PREVIEW_LEAK")
    if "media_type" in card:
        _deny_parse("PREVIEW_LEAK")
    return dict(card)


def _assert_redacted(blob: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")


def _source_facts(entries: list[dict[str, Any]]) -> dict[str, dict[str, set[Any]]]:
    facts: dict[str, dict[str, set[Any]]] = {}
    for entry in entries:
        chain = entry.get("candidate_chain")
        if not isinstance(chain, dict):
            continue
        source = chain.get("source")
        if not isinstance(source, dict):
            continue
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or source_id == "":
            continue
        rec = facts.setdefault(source_id, {"rights": set(), "created_at": set()})
        rec["rights"].add(source.get("rights_status"))
        if "created_at" in source:
            rec["created_at"].add(source.get("created_at"))
    return facts


def _source_override(source_id: str, facts: dict[str, dict[str, set[Any]]]) -> str | None:
    rec = facts.get(source_id)
    if rec is None:
        return None
    rights = rec["rights"]
    if "REVOKED" in rights:
        return "REVOKED_SOURCE"
    if len(rec["created_at"]) > 1:
        return "MIXED_RIGHTS_TIMESTAMP"
    if len(rights) > 1:
        return "CONFLICTED_SOURCE_RIGHTS"
    return None


def _batch_structure_deny(entries: list[dict[str, Any]]) -> str | None:
    work_ids: list[str] = []
    revision_ids: list[str] = []
    version_to_source: dict[str, Any] = {}
    for entry in entries:
        chain = entry.get("candidate_chain")
        if not isinstance(chain, dict):
            continue
        work = chain.get("review_work_item")
        candidate = chain.get("candidate_revision")
        version = chain.get("source_version")
        source = chain.get("source")
        if isinstance(work, dict):
            work_id = work.get("review_work_item_id")
            if isinstance(work_id, str) and work_id:
                work_ids.append(work_id)
        if isinstance(candidate, dict):
            revision_id = candidate.get("candidate_revision_id")
            if isinstance(revision_id, str) and revision_id:
                revision_ids.append(revision_id)
        version_id = None
        source_id = None
        if isinstance(version, dict):
            version_id = version.get("source_version_id")
            source_id = version.get("source_id")
        if isinstance(source, dict) and source.get("source_id"):
            source_id = source.get("source_id")
        if isinstance(version_id, str) and version_id:
            previous = version_to_source.get(version_id)
            if previous is not None and source_id != previous:
                return "INCONSISTENT_SOURCE_VERSION_REF"
            version_to_source[version_id] = source_id
    if len(work_ids) != len(set(work_ids)):
        return "DUPLICATE_WORK_ITEM"
    if len(revision_ids) != len(set(revision_ids)):
        return "DUPLICATE_CANDIDATE_REVISION"
    return None


def _matches_filter(card: Mapping[str, Any], status_filter: str | None) -> bool:
    if status_filter in (None, "PREVIEW_ONLY"):
        return True
    if status_filter == "REQUESTED":
        return card.get("work_item_state") == "REQUESTED"
    return False


def inbox(
    payload: Mapping[str, Any] | None,
    *,
    commit: str = "UNPINNED_LOCAL",
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = MAX_ENTRIES,
) -> dict[str, Any]:
    pin = bound_commit(commit)
    page, page_size = _bound_page(page, page_size)
    status_filter = _bound_status(status_filter)
    if not isinstance(payload, dict):
        _deny_parse("INVALID_INPUT")
    extra = set(payload) - ENVELOPE_KEYS
    if extra:
        _deny_parse("UNTRUSTED_CLAIM")
    _inbox_nesting(payload)
    raw = deepcopy(payload)
    case_id = raw.get("snapshot_case_id")
    if not isinstance(case_id, str) or re.fullmatch(CASE_ID_RE, case_id) is None:
        _deny_parse("INVALID_CASE_ID")
    try:
        tenant = require_tenant_scope(raw.get("tenant_scope"))
    except TenantScopeError as exc:
        return _receipt(
            snapshot_case_id=case_id,
            tenant_scope=None,
            inbox_status="INBOX_DENIED",
            deny_code=exc.code,
            cards=[],
            deny_counts=_deny_counts([exc.code]),
            commit=pin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            card_count=0,
            deny_count=1,
        )
    entries = raw.get("entries")
    if not isinstance(entries, list):
        _deny_parse("INVALID_ENTRIES")
    if len(entries) > MAX_ENTRIES:
        _deny_parse("TOO_MANY_ENTRIES")
    if len(entries) == 0:
        receipt = _receipt(
            snapshot_case_id=case_id,
            tenant_scope=tenant,
            inbox_status="INBOX_DENIED",
            deny_code="EMPTY_BATCH",
            cards=[],
            deny_counts=_deny_counts(["EMPTY_BATCH"]),
            commit=pin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            card_count=0,
            deny_count=1,
        )
        _assert_redacted(json.dumps(receipt, sort_keys=True))
        return receipt
    for entry in entries:
        if not isinstance(entry, dict):
            _deny_parse("INVALID_ENTRY")
    tenants: list[Any] = []
    _walk_tenant_scopes(raw, tenants)
    if any(value != tenant for value in tenants):
        receipt = _receipt(
            snapshot_case_id=case_id,
            tenant_scope=tenant,
            inbox_status="INBOX_DENIED",
            deny_code="CROSS_TENANT",
            cards=[],
            deny_counts=_deny_counts(["CROSS_TENANT"]),
            commit=pin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            card_count=0,
            deny_count=1,
        )
        blob = json.dumps(receipt, sort_keys=True)
        _assert_redacted(blob)
        for value in tenants:
            if value != tenant and isinstance(value, str) and value in blob:
                _deny_parse("PREVIEW_LEAK")
        return receipt
    structural = _batch_structure_deny(entries)
    if structural is not None:
        receipt = _receipt(
            snapshot_case_id=case_id,
            tenant_scope=tenant,
            inbox_status="INBOX_DENIED",
            deny_code=structural,
            cards=[],
            deny_counts=_deny_counts([structural]),
            commit=pin,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            card_count=0,
            deny_count=1,
        )
        _assert_redacted(json.dumps(receipt, sort_keys=True))
        return receipt
    facts = _source_facts(entries)
    deny_codes: list[str] = []
    cards: list[dict[str, Any]] = []
    for entry in entries:
        item = preview(entry, commit=pin)
        chain = entry.get("candidate_chain")
        source_id = ""
        if isinstance(chain, dict) and isinstance(chain.get("source"), dict):
            source_id = str(chain["source"].get("source_id") or "")
        override = _source_override(source_id, facts)
        if override is not None:
            deny_codes.append(override)
            continue
        if item["preview_status"] != "PREVIEW_ONLY" or item.get("queue_card") is None:
            deny_codes.append(str(item.get("deny_code") or "PREVIEW_DENIED"))
            continue
        cards.append(_assert_card(item["queue_card"]))
    cards.sort(key=lambda card: str(card.get("review_work_item_id") or ""))
    if status_filter == "PREVIEW_DENIED":
        filtered: list[dict[str, Any]] = []
    else:
        filtered = [card for card in cards if _matches_filter(card, status_filter)]
    card_count = len(filtered)
    start = (page - 1) * page_size
    paged = filtered[start : start + page_size]
    inbox_status = "PREVIEW_ONLY" if paged or filtered else "PREVIEW_EMPTY"
    if filtered and not paged:
        inbox_status = "PREVIEW_ONLY"
    receipt = _receipt(
        snapshot_case_id=case_id,
        tenant_scope=tenant,
        inbox_status=inbox_status if filtered else "PREVIEW_EMPTY",
        deny_code=None,
        cards=paged,
        deny_counts=_deny_counts(deny_codes),
        commit=pin,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        card_count=card_count,
        deny_count=len(deny_codes),
    )
    blob = json.dumps(receipt, sort_keys=True)
    _assert_redacted(blob)
    return receipt


def inbox_file(
    path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = MAX_ENTRIES,
) -> dict[str, Any]:
    pin = bound_commit(commit)
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    payload = parse_inbox_json(text)
    return inbox(
        payload,
        commit=pin,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
