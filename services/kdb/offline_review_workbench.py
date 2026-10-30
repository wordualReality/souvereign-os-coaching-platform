"""Static offline review workbench. Not a reviewer assignment.

Renders a portable UTF-8 HTML5 preview from a P14 batch after the full inbox
is re-evaluated and each eligible work item is opened through P15. The page is
SNAPSHOT_UNTRUSTED, NON_EXECUTABLE, NOT_ASSIGNED, and NOT_ADMITTED. It is not
an HTTP service, C04 case, or live reader.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from offline_review_case_detail import UUID_RE, case_detail
from offline_review_inbox import (
    FORBIDDEN_SUBSTRINGS,
    MAX_CHARS,
    MAX_ENTRIES,
    PACKET as INBOX_PACKET,
    inbox,
    parse_inbox_json,
)
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PACKET as PREVIEW_PACKET,
    REPAIR_PACKET,
    PreviewParseError,
    REPO_ROOT,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P16-STATIC-OFFLINE-REVIEW-WORKBENCH-01"
OUTPUT_NAME_RE = r"^[A-Za-z0-9._-]{1,64}\.html$"
CSP = (
    "default-src 'none'; script-src 'none'; connect-src 'none'; img-src 'none'; "
    "form-action 'none'; style-src 'unsafe-inline'; base-uri 'none'; object-src 'none'; "
    "frame-src 'none'"
)
CSS = """
body{font-family:system-ui,sans-serif;margin:1.5rem;line-height:1.4;color:#111}
.banner{font-weight:700;margin:0 0 0.75rem}
.gates{margin:0 0 1.25rem}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #333;padding:0.4rem 0.6rem;text-align:left}
a{color:inherit}
section{margin-top:2rem}
h1,h2,h3{font-size:1.1rem}
""".strip()
BANNER = "Nicht autorisiert, nur synthetische Vorschau."
GATES = "PREVIEW_ONLY SNAPSHOT_UNTRUSTED NOT_ADMITTED NOT_ASSIGNED NON_EXECUTABLE"


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _t(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _assert_redacted(blob: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")
    lowered = blob.lower()
    for token in ("<script", "javascript:", "<img", "<form", "onerror=", "onload="):
        if token in lowered:
            _deny_parse("PREVIEW_LEAK")


def _anchor(work_item_id: str) -> str:
    if re.fullmatch(UUID_RE, work_item_id) is None:
        _deny_parse("PREVIEW_LEAK")
    return "case-" + work_item_id.lower()


def _receipt(
    *,
    snapshot_case_id: str | None,
    tenant_scope: str | None,
    workbench_status: str,
    deny_code: str | None,
    html_page: str,
    card_count: int,
    detail_count: int,
    commit: str,
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
        "workbench_status": workbench_status,
        "deny_code": deny_code,
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


def _shell(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="de">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
        f"<title>{_t(title)}</title>\n"
        f"<style>\n{CSS}\n</style>\n"
        "</head>\n"
        "<body>\n"
        "<main>\n"
        f'<p class="banner">{_t(BANNER)}</p>\n'
        f'<p class="gates">{_t(GATES)}</p>\n'
        f"{body}"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def _denied_page(deny_code: str) -> str:
    body = (
        "<h1>KDB Review Workbench. Synthetische Vorschau</h1>\n"
        "<p>WORKBENCH_DENIED</p>\n"
        f"<p>deny_code {_t(deny_code)}</p>\n"
        "<p>Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veröffentlichung.</p>\n"
    )
    return _shell("KDB Review Workbench. Abgewiesen", body)


def _dt(term: str, value: Any) -> str:
    return f"<div><dt>{_t(term)}</dt><dd>{_t(value)}</dd></div>\n"


def _preview_page(
    *,
    snapshot_case_id: str,
    cards: list[dict[str, Any]],
    details: list[dict[str, Any]],
    commit: str,
) -> str:
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
    body = (
        "<h1>KDB Review Workbench. Synthetische Vorschau</h1>\n"
        f"<p>snapshot_case_id {_t(snapshot_case_id)}</p>\n"
        f"<p>source_commit {_t(commit)} LABEL_NOT_ATTESTED</p>\n"
        "<p>Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veröffentlichung.</p>\n"
        '<nav aria-label="Inbox">\n'
        "<h2>Inbox</h2>\n"
        "<table>\n"
        "<thead><tr>"
        "<th scope=\"col\">review_work_item_id</th>"
        "<th scope=\"col\">source_id</th>"
        "<th scope=\"col\">source_version_no</th>"
        "<th scope=\"col\">revision_no</th>"
        "<th scope=\"col\">work_item_state</th>"
        "<th scope=\"col\">evidence_span_count</th>"
        "</tr></thead>\n"
        "<tbody>\n"
        + "".join(rows)
        + "</tbody>\n"
        "</table>\n"
        "</nav>\n"
        "<h2>Fallansicht</h2>\n"
        + "".join(sections)
    )
    return _shell("KDB Review Workbench. Synthetische Vorschau", body)


def workbench(payload: Mapping[str, Any] | None, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    pin = bound_commit(commit)
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
    if inbox_status == "INBOX_DENIED" or inbox_deny:
        deny = str(inbox_deny or "INBOX_DENIED")
        page = _denied_page(deny)
        _assert_redacted(page)
        return _receipt(
            snapshot_case_id=snapshot_case_id if isinstance(snapshot_case_id, str) else None,
            tenant_scope=tenant_scope if isinstance(tenant_scope, str) else None,
            workbench_status="WORKBENCH_DENIED",
            deny_code=deny,
            html_page=page,
            card_count=0,
            detail_count=0,
            commit=pin,
        )
    cards = list(inbox_receipt.get("cards") or [])
    details: list[dict[str, Any]] = []
    for card in cards:
        work_id = card.get("review_work_item_id")
        item = case_detail(payload, work_id, commit=pin)
        if item.get("detail_status") == "DETAIL_ONLY" and isinstance(item.get("detail"), dict):
            details.append(item["detail"])
    page = _preview_page(
        snapshot_case_id=str(snapshot_case_id or ""),
        cards=cards,
        details=details,
        commit=pin,
    )
    _assert_redacted(page)
    if "READY" in page:
        _deny_parse("PREVIEW_LEAK")
    return _receipt(
        snapshot_case_id=snapshot_case_id if isinstance(snapshot_case_id, str) else None,
        tenant_scope=tenant_scope if isinstance(tenant_scope, str) else None,
        workbench_status="PREVIEW_ONLY",
        deny_code=None,
        html_page=page,
        card_count=len(cards),
        detail_count=len(details),
        commit=pin,
    )


def workbench_file(path: str | Path, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    pin = bound_commit(commit)
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    payload = parse_inbox_json(text)
    return workbench(payload, commit=pin)


def write_workbench_html(html_page: str, output: str | Path) -> Path:
    text_path = str(output)
    lowered = text_path.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("file:"):
        _deny_parse("NETWORK_PATH_DENIED")
    if "\x00" in text_path:
        _deny_parse("PATH_ESCAPE_DENIED")
    location = Path(text_path)
    if location.is_absolute():
        _deny_parse("PATH_ESCAPE_DENIED")
    if ".." in location.parts:
        _deny_parse("PATH_ESCAPE_DENIED")
    if location.is_symlink():
        _deny_parse("SYMLINK_DENIED")
    parent = location.parent
    if parent.is_symlink():
        _deny_parse("SYMLINK_DENIED")
    if not parent.exists() or not parent.is_dir():
        _deny_parse("MISSING_OUTPUT_DIR")
    resolved_parent = parent.resolve()
    try:
        resolved_parent.relative_to(REPO_ROOT)
    except ValueError:
        _deny_parse("PATH_ESCAPE_DENIED")
    if not re.fullmatch(OUTPUT_NAME_RE, location.name):
        _deny_parse("INVALID_OUTPUT_NAME")
    dest = resolved_parent / location.name
    if dest.exists() or dest.is_symlink():
        _deny_parse("OUTPUT_EXISTS")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    handle = os.open(dest, flags, 0o644)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(html_page)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest
