"""Offline local source-bytes proof. Not source custody or live ingest.

Reads one bounded repo-local synthetic file and compares SHA-256 to the
declared SourceVersion.content_sha256 of one P15-selectable work item.
A local match is LOCAL_BYTES_MATCH_DECLARED_SHA only. It does not admit
rights, origin, C04, C05, or hosted ingest.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from offline_review_case_detail import case_detail, bound_work_item_id
from offline_review_inbox import (
    FORBIDDEN_SUBSTRINGS,
    MAX_CHARS,
    MAX_ENTRIES,
    inbox,
    parse_inbox_json,
)
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PreviewParseError,
    REPO_ROOT,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P20-OFFLINE-SOURCE-BYTES-EVIDENCE-PROOF-01"
MAX_SOURCE_BYTES = 65536
SHA256_HEX = r"^[0-9a-f]{64}$"
UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
LEAK_TOKENS = (
    "media_type",
    "rights_basis",
    "external_locator",
    "proposal_payload",
    "assigned_reviewer",
    "READY",
    "javascript:",
)
GAPS = (
    "RIGHTS_SNAPSHOT_UNATTESTED",
    "RIGHTS_DIGEST_UNVERIFIED",
    "ISSUER_UNVERIFIED",
    "EVENT_WATERMARK_UNKNOWN",
    "HOSTED_VERIFIED_NO",
    "CANDIDATE_CONTENT_SHA_IS_PROPOSAL_DOMAIN",
)


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _assert_redacted(blob: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")
    for token in LEAK_TOKENS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")


def _forbid_tokens(blob: str, tokens: Iterable[str]) -> None:
    for token in tokens:
        if token and token in blob:
            _deny_parse("PREVIEW_LEAK")


def _full_inbox(payload: Mapping[str, Any] | None, commit: str) -> dict[str, Any]:
    return inbox(
        payload,
        commit=commit,
        status_filter=None,
        page=1,
        page_size=MAX_ENTRIES,
    )


def _gates() -> dict[str, Any]:
    return {
        "packet": PACKET,
        "df_adoption": "DF-20261029-01",
        "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        "final_authority": "NOT_ADMITTED",
        "assignment": "NOT_ASSIGNED",
        "execution": "NON_EXECUTABLE",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "read_model": "NON_NORMATIVE_INTERNAL_PREVIEW",
        "publication": "NOT_PUBLISHED",
        "db_write": "NOT_ADMITTED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "logical_objects_claimed": "NOT_18_OF_18",
        "inventory_source": "UNCONFIRMED_ATC10_CANDIDATES",
        "physical_sql001_tables": 12,
        "source_commit_attestation": "LABEL_NOT_ATTESTED",
        "source_file_scope": "SOURCE_FILE_LOCAL_ONLY",
        "rights_authority": "NOT_ATTESTED",
        "origin_authority": "NOT_ATTESTED",
    }


def _identity_tokens(payload: Mapping[str, Any]) -> list[str]:
    tokens: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            lowered = value.lower()
            if re.fullmatch(UUID_RE, lowered):
                tokens.append(lowered)
                tokens.append(value)

    walk(payload)
    return tokens


def _load_payload(path: str | Path) -> dict[str, Any]:
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    return parse_inbox_json(text)


def _read_source_bytes(path: str | Path) -> bytes:
    text_path = str(path)
    location = Path(text_path)
    if ".." in location.parts:
        _deny_parse("PATH_ESCAPE_DENIED")
    if location.parent.is_symlink():
        _deny_parse("SYMLINK_DENIED")
    bound = _safe_local_file(path)
    stat = bound.stat()
    if stat.st_nlink > 1:
        _deny_parse("HARDLINK_DENIED")
    if stat.st_size < 1:
        _deny_parse("EMPTY_SOURCE_FILE")
    if stat.st_size > MAX_SOURCE_BYTES:
        _deny_parse("INPUT_TOO_LARGE")
    data = bound.read_bytes()
    if len(data) != stat.st_size:
        _deny_parse("INPUT_TOO_LARGE")
    return data


def _denied(*, deny_code: str, commit: str, hide: Iterable[str]) -> dict[str, Any]:
    receipt = {
        **_gates(),
        "source_commit": commit,
        "proof_status": "PROOF_DENIED",
        "deny_code": deny_code,
        "span_status": "SPAN_NOT_CHECKED",
        "explicit_gaps": list(GAPS),
        "atc10_named_candidates": len(ATC10_NAMED_CANDIDATES),
    }
    blob = json.dumps(receipt, sort_keys=True)
    _assert_redacted(blob)
    _forbid_tokens(blob, hide)
    return receipt


def _mismatch(*, commit: str, hide: Iterable[str]) -> dict[str, Any]:
    receipt = {
        **_gates(),
        "source_commit": commit,
        "proof_status": "LOCAL_CONTENT_SHA_MISMATCH",
        "deny_code": "LOCAL_CONTENT_SHA_MISMATCH",
        "span_status": "SPAN_NOT_CHECKED",
        "explicit_gaps": list(GAPS),
        "atc10_named_candidates": len(ATC10_NAMED_CANDIDATES),
    }
    blob = json.dumps(receipt, sort_keys=True)
    _assert_redacted(blob)
    _forbid_tokens(blob, hide)
    return receipt


def _selected_entry(payload: Mapping[str, Any], work_id: str) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for entry in payload.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        chain = entry.get("candidate_chain")
        if not isinstance(chain, dict):
            continue
        work = chain.get("review_work_item")
        if not isinstance(work, dict):
            continue
        item_id = str(work.get("review_work_item_id") or "").lower()
        if item_id == work_id:
            matches.append(entry)
    if len(matches) != 1:
        return None
    return matches[0]


def _span_status(spans: Any, version_id: str, byte_len: int) -> str:
    if not isinstance(spans, list) or not spans:
        _deny_parse("EMPTY_EVIDENCE")
    integer_spans: list[tuple[int, int]] = []
    textual_only = False
    for span in spans:
        if not isinstance(span, dict):
            _deny_parse("MALFORMED_EVIDENCE_SPAN")
        span_version = str(span.get("source_version_id") or "").lower()
        if span_version != version_id:
            _deny_parse("WRONG_SOURCE_VERSION_LINK")
        start = span.get("start")
        end = span.get("end")
        if start is None and end is None:
            textual_only = True
            continue
        if isinstance(start, bool) or isinstance(end, bool):
            _deny_parse("MALFORMED_EVIDENCE_SPAN")
        if not isinstance(start, int) or not isinstance(end, int):
            _deny_parse("MALFORMED_EVIDENCE_SPAN")
        if start < 0 or end < 0 or start >= end or end > byte_len:
            _deny_parse("OUT_OF_RANGE_EVIDENCE_SPAN")
        integer_spans.append((start, end))
    if textual_only or not integer_spans:
        return "UNVERIFIED_LOCAL_SPAN_SEMANTICS"
    seen: set[tuple[int, int]] = set()
    ordered = sorted(integer_spans)
    previous_end = -1
    for start, end in ordered:
        pair = (start, end)
        if pair in seen:
            _deny_parse("DUPLICATE_EVIDENCE_SPAN")
        seen.add(pair)
        if start < previous_end:
            _deny_parse("OVERLAPPING_EVIDENCE_SPAN")
        previous_end = end
    return "LOCAL_SPAN_OFFSETS_BOUNDED"


def _seal_match(receipt: dict[str, Any], hide: Iterable[str]) -> dict[str, Any]:
    blob = json.dumps(receipt, sort_keys=True)
    _assert_redacted(blob)
    _forbid_tokens(blob, hide)
    if "18/18" in blob:
        _deny_parse("PREVIEW_LEAK")
    return receipt


def source_bytes_proof(
    payload: Mapping[str, Any] | None,
    work_item_id: Any,
    source_bytes: bytes,
    *,
    commit: str = "UNPINNED_LOCAL",
    hide_extra: Iterable[str] = (),
) -> dict[str, Any]:
    pin = bound_commit(commit)
    selected = bound_work_item_id(work_item_id)
    if not isinstance(source_bytes, (bytes, bytearray)):
        _deny_parse("INVALID_SOURCE_BYTES")
    data = bytes(source_bytes)
    if len(data) < 1:
        _deny_parse("EMPTY_SOURCE_FILE")
    if len(data) > MAX_SOURCE_BYTES:
        _deny_parse("INPUT_TOO_LARGE")
    hide = list(hide_extra)
    if isinstance(payload, dict):
        hide.extend(_identity_tokens(payload))
    computed = hashlib.sha256(data).hexdigest()
    hide.append(computed)
    inbox_receipt = _full_inbox(payload, pin)
    if inbox_receipt.get("inbox_status") == "INBOX_DENIED" or inbox_receipt.get("deny_code"):
        return _denied(
            deny_code=str(inbox_receipt.get("deny_code") or "INBOX_DENIED"),
            commit=pin,
            hide=hide,
        )
    detail_receipt = case_detail(payload, selected, commit=pin)
    if detail_receipt.get("detail_status") != "DETAIL_ONLY":
        return _denied(
            deny_code=str(detail_receipt.get("deny_code") or "WORK_ITEM_NOT_SELECTABLE"),
            commit=pin,
            hide=hide,
        )
    detail = detail_receipt.get("detail")
    if not isinstance(detail, dict) or not isinstance(payload, dict):
        return _denied(deny_code="WORK_ITEM_NOT_SELECTABLE", commit=pin, hide=hide)
    entry = _selected_entry(payload, selected)
    if entry is None:
        return _denied(deny_code="WORK_ITEM_NOT_SELECTABLE", commit=pin, hide=hide)
    chain = entry.get("candidate_chain")
    if not isinstance(chain, dict):
        return _denied(deny_code="WORK_ITEM_NOT_SELECTABLE", commit=pin, hide=hide)
    source = chain.get("source")
    version = chain.get("source_version")
    candidate = chain.get("candidate_revision")
    if not isinstance(source, dict) or not isinstance(version, dict) or not isinstance(candidate, dict):
        return _denied(deny_code="IDENTITY_MISMATCH", commit=pin, hide=hide)
    source_id = str(source.get("source_id") or "").lower()
    version_id = str(version.get("source_version_id") or "").lower()
    if source_id != str(detail.get("source_id") or "").lower():
        return _denied(deny_code="IDENTITY_MISMATCH", commit=pin, hide=hide)
    if version_id != str(detail.get("source_version_id") or "").lower():
        return _denied(deny_code="IDENTITY_MISMATCH", commit=pin, hide=hide)
    declared = str(version.get("content_sha256") or "").lower()
    if re.fullmatch(SHA256_HEX, declared) is None:
        return _denied(deny_code="MISMATCHED_CONTENT_DIGEST", commit=pin, hide=hide)
    hide.append(declared)
    if not hmac.compare_digest(computed, declared):
        return _mismatch(commit=pin, hide=hide)
    try:
        span_status = _span_status(candidate.get("evidence_span_refs"), version_id, len(data))
    except PreviewParseError as exc:
        return _denied(deny_code=exc.code, commit=pin, hide=hide)
    receipt = {
        **_gates(),
        "source_commit": pin,
        "proof_status": "LOCAL_BYTES_MATCH_DECLARED_SHA",
        "deny_code": None,
        "review_work_item_id": selected,
        "source_id": source_id,
        "source_version_id": version_id,
        "source_byte_length": len(data),
        "span_status": span_status,
        "explicit_gaps": list(GAPS),
        "content_digest_proof": "LOCAL_BYTES_MATCH_DECLARED_SHA",
        "atc10_named_candidates": len(ATC10_NAMED_CANDIDATES),
    }
    return _seal_match(receipt, [computed, declared, *hide_extra])


def source_bytes_proof_files(
    batch_path: str | Path,
    work_item_id: Any,
    source_path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    payload = _load_payload(batch_path)
    data = _read_source_bytes(source_path)
    hide = [Path(str(source_path)).name, Path(str(source_path)).as_posix()]
    return source_bytes_proof(
        payload,
        work_item_id,
        data,
        commit=pin,
        hide_extra=hide,
    )
