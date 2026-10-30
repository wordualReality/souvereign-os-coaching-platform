"""Offline snapshot-delta workbench. Not a lifecycle clock.

Compares two user-supplied synthetic P14 batches after each is re-evaluated
unpaged and unfiltered. Current eligible cases may be shown. Removed or
no-longer-eligible baseline items are COUNT ONLY. The page is SNAPSHOT_UNTRUSTED,
NON_EXECUTABLE, NOT_ASSIGNED, and NOT_ADMITTED. Snapshot order is an input, not
an attested event sequence.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from offline_review_case_detail import case_detail
from offline_review_inbox import (
    MAX_CHARS,
    MAX_ENTRIES,
    PACKET as INBOX_PACKET,
    inbox,
    parse_inbox_json,
)
from offline_review_workbench import (
    BANNER,
    CSP,
    CSS,
    GATES,
    PACKET as WORKBENCH_PACKET,
    _anchor,
    _assert_redacted,
    _dt,
    _shell,
    _t,
    write_workbench_html,
)
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PACKET as PREVIEW_PACKET,
    REPAIR_PACKET,
    PreviewParseError,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P17-OFFLINE-SNAPSHOT-DELTA-WORKBENCH-01"
CHANGE_LABELS = "POSSIBLE_CHANGE_ONLY SNAPSHOT_ORDER_NOT_ATTESTED EVENT_WATERMARK_UNKNOWN"
ORDER_COPY = "Die Snapshot-Reihenfolge ist eine Eingabe. Sie ist keine belegte Ereignisfolge."


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _full_inbox(payload: Mapping[str, Any] | None, commit: str) -> dict[str, Any]:
    return inbox(
        payload,
        commit=commit,
        status_filter=None,
        page=1,
        page_size=MAX_ENTRIES,
    )


def _batch_denied(receipt: Mapping[str, Any]) -> str | None:
    if receipt.get("inbox_status") == "INBOX_DENIED":
        return str(receipt.get("deny_code") or "INBOX_DENIED")
    deny = receipt.get("deny_code")
    if isinstance(deny, str) and deny:
        return deny
    return None


def _work_ids(cards: Iterable[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for card in cards:
        work_id = card.get("review_work_item_id")
        if isinstance(work_id, str) and work_id:
            ids.append(work_id.lower())
    return ids


def _card_tokens(card: Mapping[str, Any]) -> list[str]:
    tokens: list[str] = []
    for key in (
        "review_work_item_id",
        "source_id",
        "source_version_id",
        "submission_id",
        "candidate_id",
        "candidate_revision_id",
        "correlation_id",
    ):
        value = card.get(key)
        if isinstance(value, str) and value:
            tokens.append(value)
            tokens.append(value.lower())
    return tokens


def _forbid_tokens(blob: str, tokens: Iterable[str]) -> None:
    for token in tokens:
        if token and token in blob:
            _deny_parse("PREVIEW_LEAK")


def _receipt(
    *,
    current_snapshot_case_id: str | None,
    tenant_scope: str | None,
    delta_status: str,
    deny_code: str | None,
    html_page: str,
    counts: Mapping[str, int],
    card_count: int,
    detail_count: int,
    commit: str,
) -> dict[str, Any]:
    return {
        "packet": PACKET,
        "inbox_packet": INBOX_PACKET,
        "workbench_packet": WORKBENCH_PACKET,
        "preview_packet": PREVIEW_PACKET,
        "repair_packet": REPAIR_PACKET,
        "df_adoption": "DF-20261029-01",
        "snapshot_case_id": current_snapshot_case_id,
        "tenant_scope": tenant_scope,
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "read_model": "NON_NORMATIVE_INTERNAL_PREVIEW",
        "delta_status": delta_status,
        "deny_code": deny_code,
        "change_authority": "POSSIBLE_CHANGE_ONLY",
        "snapshot_order": "SNAPSHOT_ORDER_NOT_ATTESTED",
        "event_watermark": "EVENT_WATERMARK_UNKNOWN",
        "baseline_eligible_count": counts["baseline_eligible_count"],
        "current_eligible_count": counts["current_eligible_count"],
        "visible_current_count": counts["visible_current_count"],
        "added_count": counts["added_count"],
        "removed_or_denied_count": counts["removed_or_denied_count"],
        "unchanged_count": counts["unchanged_count"],
        "html": html_page,
        "card_count": card_count,
        "detail_count": detail_count,
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


def _zero_counts() -> dict[str, int]:
    return {
        "baseline_eligible_count": 0,
        "current_eligible_count": 0,
        "visible_current_count": 0,
        "added_count": 0,
        "removed_or_denied_count": 0,
        "unchanged_count": 0,
    }


def _denied_page(deny_code: str) -> str:
    body = (
        "<h1>KDB Review Snapshot-Delta. Synthetische Vorschau</h1>\n"
        "<p>DELTA_DENIED</p>\n"
        f"<p>deny_code {_t(deny_code)}</p>\n"
        "<p>Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veröffentlichung.</p>\n"
    )
    return _shell("KDB Review Snapshot-Delta. Abgewiesen", body)


def _counts_block(counts: Mapping[str, int]) -> str:
    return (
        '<section class="summary">\n'
        "<h2>Snapshot-Vergleich</h2>\n"
        f"<p>{_t(CHANGE_LABELS)}</p>\n"
        f"<p>{_t(ORDER_COPY)}</p>\n"
        "<dl>\n"
        + _dt("BASELINE_ELIGIBLE_COUNT", counts["baseline_eligible_count"])
        + _dt("CURRENT_ELIGIBLE_COUNT", counts["current_eligible_count"])
        + _dt("VISIBLE_CURRENT_COUNT", counts["visible_current_count"])
        + _dt("ADDED_COUNT", counts["added_count"])
        + _dt("REMOVED_OR_DENIED_COUNT", counts["removed_or_denied_count"])
        + _dt("UNCHANGED_COUNT", counts["unchanged_count"])
        + "</dl>\n"
        "</section>\n"
    )


def _cases_body(cards: list[dict[str, Any]], details: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    rows = []
    for card in cards:
        work_id = str(card["review_work_item_id"])
        anchor = _anchor(work_id)
        rows.append(
            "<tr>"
            f'<th scope="row"><a href="#{_t(anchor)}">{_t(work_id)}</a></th>'
            f"<td>{_t(card.get('source_id'))}</td>"
            f"<td>{_t(card.get('source_version_no'))}</td>"
            f"<td>{_t(card.get('revision_no'))}</td>"
            f"<td>{_t(card.get('work_item_state'))}</td>"
            f"<td>{_t(card.get('evidence_span_count'))}</td>"
            "</tr>\n"
        )
    sections = []
    for detail in details:
        work_id = str(detail["review_work_item_id"])
        anchor = _anchor(work_id)
        trace = detail.get("provenance_trace") or {}
        reasons = detail.get("eligibility_reasons") or []
        gaps = detail.get("explicit_gaps") or []
        sections.append(
            f'<section id="{_t(anchor)}" tabindex="-1">\n'
            f"<h3>Fall {_t(work_id)}</h3>\n"
            "<dl>\n"
            + _dt("review_queue", detail.get("review_queue"))
            + _dt("work_item_state", detail.get("work_item_state"))
            + _dt("tenant_scope", detail.get("tenant_scope"))
            + _dt("source_id", detail.get("source_id"))
            + _dt("source_version_id", detail.get("source_version_id"))
            + _dt("source_version_no", detail.get("source_version_no"))
            + _dt("submission_id", detail.get("submission_id"))
            + _dt("candidate_id", detail.get("candidate_id"))
            + _dt("candidate_revision_id", detail.get("candidate_revision_id"))
            + _dt("revision_no", detail.get("revision_no"))
            + _dt("review_work_item_id", detail.get("review_work_item_id"))
            + _dt("correlation_id", detail.get("correlation_id"))
            + _dt("rights_status", detail.get("rights_status"))
            + _dt("evidence_span_count", detail.get("evidence_span_count"))
            + _dt("consumer_o1", detail.get("consumer_o1"))
            + _dt("consumer_o2", detail.get("consumer_o2"))
            + _dt("consumer_o3", detail.get("consumer_o3"))
            + _dt("tenant_scope_check", trace.get("tenant_scope_check"))
            + _dt("source_rights", trace.get("source_rights"))
            + _dt("p08_eligibility", trace.get("p08_eligibility"))
            + _dt("declared_sha", trace.get("declared_sha"))
            + _dt("event_watermark", trace.get("event_watermark"))
            + _dt("eligibility_reasons", " ".join(str(item) for item in reasons))
            + _dt("explicit_gaps", " ".join(str(item) for item in gaps))
            + "</dl>\n"
            "</section>\n"
        )
    return (
        '<nav aria-label="Aktuelle Inbox">\n'
        "<h2>Aktuelle Inbox</h2>\n"
        "<table>\n"
        "<thead><tr>"
        '<th scope="col">review_work_item_id</th>'
        '<th scope="col">source_id</th>'
        '<th scope="col">source_version_no</th>'
        '<th scope="col">revision_no</th>'
        '<th scope="col">work_item_state</th>'
        '<th scope="col">evidence_span_count</th>'
        "</tr></thead>\n"
        "<tbody>\n"
        + "".join(rows)
        + "</tbody>\n"
        "</table>\n"
        "</nav>\n"
        "<h2>Fallansicht</h2>\n"
        + "".join(sections)
    )


def _preview_page(
    *,
    snapshot_case_id: str,
    cards: list[dict[str, Any]],
    details: list[dict[str, Any]],
    counts: Mapping[str, int],
    commit: str,
) -> str:
    body = (
        "<h1>KDB Review Snapshot-Delta. Synthetische Vorschau</h1>\n"
        f"<p>snapshot_case_id {_t(snapshot_case_id)}</p>\n"
        f"<p>source_commit {_t(commit)} LABEL_NOT_ATTESTED</p>\n"
        "<p>Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veröffentlichung.</p>\n"
        + _counts_block(counts)
        + _cases_body(cards, details)
    )
    return _shell("KDB Review Snapshot-Delta. Synthetische Vorschau", body)


def _denied_receipt(*, deny_code: str, commit: str) -> dict[str, Any]:
    page = _denied_page(deny_code)
    _assert_redacted(page)
    receipt = _receipt(
        current_snapshot_case_id=None,
        tenant_scope=None,
        delta_status="DELTA_DENIED",
        deny_code=deny_code,
        html_page=page,
        counts=_zero_counts(),
        card_count=0,
        detail_count=0,
        commit=commit,
    )
    _assert_redacted(json.dumps({key: value for key, value in receipt.items() if key != "html"}, sort_keys=True))
    return receipt


def snapshot_delta(
    baseline: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    base_inbox = _full_inbox(baseline, pin)
    curr_inbox = _full_inbox(current, pin)
    base_deny = _batch_denied(base_inbox)
    if base_deny:
        return _denied_receipt(deny_code=base_deny, commit=pin)
    curr_deny = _batch_denied(curr_inbox)
    if curr_deny:
        return _denied_receipt(deny_code=curr_deny, commit=pin)
    base_tenant = base_inbox.get("tenant_scope")
    curr_tenant = curr_inbox.get("tenant_scope")
    if not isinstance(base_tenant, str) or not isinstance(curr_tenant, str) or base_tenant != curr_tenant:
        return _denied_receipt(deny_code="CROSS_TENANT", commit=pin)
    base_cards = list(base_inbox.get("cards") or [])
    curr_cards = list(curr_inbox.get("cards") or [])
    base_ids = set(_work_ids(base_cards))
    curr_ids = set(_work_ids(curr_cards))
    added = curr_ids - base_ids
    removed = base_ids - curr_ids
    unchanged = base_ids & curr_ids
    counts = {
        "baseline_eligible_count": len(base_ids),
        "current_eligible_count": len(curr_ids),
        "visible_current_count": len(curr_ids),
        "added_count": len(added),
        "removed_or_denied_count": len(removed),
        "unchanged_count": len(unchanged),
    }
    details: list[dict[str, Any]] = []
    for card in curr_cards:
        work_id = card.get("review_work_item_id")
        item = case_detail(current, work_id, commit=pin)
        if item.get("detail_status") == "DETAIL_ONLY" and isinstance(item.get("detail"), dict):
            details.append(item["detail"])
    page = _preview_page(
        snapshot_case_id=str(curr_inbox.get("snapshot_case_id") or ""),
        cards=curr_cards,
        details=details,
        counts=counts,
        commit=pin,
    )
    _assert_redacted(page)
    if "READY" in page:
        _deny_parse("PREVIEW_LEAK")
    removed_tokens: list[str] = []
    for card in base_cards:
        work_id = str(card.get("review_work_item_id") or "").lower()
        if work_id in removed:
            removed_tokens.extend(_card_tokens(card))
    receipt = _receipt(
        current_snapshot_case_id=curr_inbox.get("snapshot_case_id")
        if isinstance(curr_inbox.get("snapshot_case_id"), str)
        else None,
        tenant_scope=curr_tenant,
        delta_status="PREVIEW_ONLY",
        deny_code=None,
        html_page=page,
        counts=counts,
        card_count=len(curr_cards),
        detail_count=len(details),
        commit=pin,
    )
    redacted = json.dumps(receipt, sort_keys=True)
    _assert_redacted(redacted)
    _forbid_tokens(redacted, removed_tokens)
    _forbid_tokens(page, removed_tokens)
    return receipt


def _load_payload(path: str | Path) -> tuple[dict[str, Any], Path]:
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    return parse_inbox_json(text), location


def snapshot_delta_files(
    baseline_path: str | Path,
    current_path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    baseline, baseline_location = _load_payload(baseline_path)
    current, current_location = _load_payload(current_path)
    if baseline_location.resolve() == current_location.resolve():
        _deny_parse("SAME_SNAPSHOT_PATH")
    return snapshot_delta(baseline, current, commit=pin)


# write_workbench_html is the P16 exclusive local HTML writer.
__all__ = [
    "PACKET",
    "snapshot_delta",
    "snapshot_delta_files",
    "write_workbench_html",
]
