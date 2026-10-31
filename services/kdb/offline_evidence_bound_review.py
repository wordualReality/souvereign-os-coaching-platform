"""P21 offline evidence-bound current-case review preview.

Composes the guarded P14/P15 selection with P20 local source-byte binding and
canonical byte-span reconciliation.  Results are synthetic, preview-only and
never authorize review, publication, database writes, or source provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from offline_source_bytes_proof import (
    _identity_tokens,
    _load_payload,
    _read_source_bytes,
    _selected_entry,
    source_bytes_proof,
)
from offline_review_case_detail import bound_work_item_id
from offline_review_viewmodel import viewmodel_with_evidence
from review_handoff_preview import PreviewParseError, bound_commit

PACKET = "KDB-M01-P21-OFFLINE-EVIDENCE-BOUND-REVIEW-01"
CANONICAL_LOCATOR = re.compile(r"^bytes:(0|[1-9][0-9]*)-(0|[1-9][0-9]*)$")
GAPS = (
    "SOURCE_CUSTODY_NOT_ATTESTED",
    "RIGHTS_AND_LICENSE_NOT_ATTESTED",
    "EVIDENCE_SEMANTIC_CORRECTNESS_UNVERIFIED",
    "ISSUER_UNVERIFIED",
    "EVENT_WATERMARK_UNKNOWN",
    "HOSTED_VERIFIED_NO",
)


def _deny(code: str, commit: str, hide: Iterable[str]) -> dict[str, Any]:
    receipt = {
        "packet": PACKET,
        "source_commit": commit,
        "review_status": "EVIDENCE_BOUND_REVIEW_DENIED",
        "deny_code": code,
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "assignment": "NOT_ASSIGNED",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "explicit_gaps": list(GAPS),
    }
    blob = json.dumps(receipt, sort_keys=True)
    for token in hide:
        if token and token in blob:
            raise PreviewParseError("PREVIEW_LEAK")
    return receipt


def _canonical_spans(spans: Any, version_id: str, data: bytes) -> list[dict[str, Any]]:
    if not isinstance(spans, list) or not spans:
        raise PreviewParseError("EMPTY_EVIDENCE")
    parsed: list[tuple[int, int]] = []
    for span in spans:
        if not isinstance(span, dict) or set(span) - {"source_version_id", "locator", "start", "end"}:
            raise PreviewParseError("MALFORMED_EVIDENCE_SPAN")
        if str(span.get("source_version_id") or "").lower() != version_id:
            raise PreviewParseError("WRONG_SOURCE_VERSION_LINK")
        locator = span.get("locator")
        if not isinstance(locator, str):
            raise PreviewParseError("UNVERIFIED_LOCAL_SPAN_SEMANTICS")
        matched = CANONICAL_LOCATOR.fullmatch(locator)
        if matched is None:
            raise PreviewParseError("UNVERIFIED_LOCAL_SPAN_SEMANTICS")
        first, last = int(matched.group(1)), int(matched.group(2))
        if last < first:
            raise PreviewParseError("INVALID_EVIDENCE_RANGE")
        start, end = first, last + 1
        supplied_start, supplied_end = span.get("start"), span.get("end")
        if isinstance(supplied_start, bool) or isinstance(supplied_end, bool):
            raise PreviewParseError("MALFORMED_EVIDENCE_SPAN")
        if supplied_start is not None or supplied_end is not None:
            if not isinstance(supplied_start, int) or not isinstance(supplied_end, int):
                raise PreviewParseError("MALFORMED_EVIDENCE_SPAN")
            if (supplied_start, supplied_end) != (start, end):
                raise PreviewParseError("EVIDENCE_OFFSET_DISAGREEMENT")
        if start < 0 or start >= end or end > len(data):
            raise PreviewParseError("OUT_OF_RANGE_EVIDENCE_SPAN")
        parsed.append((start, end))
    ordered = sorted(parsed)
    for index, pair in enumerate(ordered):
        if index and pair == ordered[index - 1]:
            raise PreviewParseError("DUPLICATE_EVIDENCE_SPAN")
        if index and pair[0] < ordered[index - 1][1]:
            raise PreviewParseError("OVERLAPPING_EVIDENCE_SPAN")
    return [
        {
            "ordinal": index + 1,
            "byte_start": start,
            "byte_end_exclusive": end,
            "byte_length": end - start,
            "local_slice_proof_sha256": hashlib.sha256(
                b"KDB-P21-LOCAL-SLICE\x00"
                + start.to_bytes(8, "big")
                + end.to_bytes(8, "big")
                + data[start:end]
            ).hexdigest(),
            "proof_scope": "LOCAL_SOURCE_SLICE_ONLY",
        }
        for index, (start, end) in enumerate(ordered)
    ]


def evidence_bound_review(
    payload: Mapping[str, Any] | None,
    work_item_id: Any,
    source_bytes: bytes,
    *,
    commit: str = "UNPINNED_LOCAL",
    hide_extra: Iterable[str] = (),
) -> dict[str, Any]:
    pin = bound_commit(commit)
    selected = bound_work_item_id(work_item_id)
    hide = list(hide_extra)
    if isinstance(payload, dict):
        hide.extend(_identity_tokens(payload))
    p20 = source_bytes_proof(payload, selected, source_bytes, commit=pin, hide_extra=hide_extra)
    if p20.get("proof_status") != "LOCAL_BYTES_MATCH_DECLARED_SHA":
        return _deny(str(p20.get("deny_code") or p20.get("proof_status") or "PROOF_DENIED"), pin, hide)
    if not isinstance(payload, dict):
        return _deny("WORK_ITEM_NOT_SELECTABLE", pin, hide)
    entry = _selected_entry(payload, selected)
    if entry is None:
        return _deny("WORK_ITEM_NOT_SELECTABLE", pin, hide)
    chain = entry.get("candidate_chain")
    if not isinstance(chain, dict):
        return _deny("WORK_ITEM_NOT_SELECTABLE", pin, hide)
    version = chain.get("source_version")
    candidate = chain.get("candidate_revision")
    if not isinstance(version, dict) or not isinstance(candidate, dict):
        return _deny("IDENTITY_MISMATCH", pin, hide)
    version_id = str(version.get("source_version_id") or "").lower()
    data = bytes(source_bytes)
    try:
        spans = _canonical_spans(candidate.get("evidence_span_refs"), version_id, data)
    except PreviewParseError as exc:
        return _deny(exc.code, pin, hide)
    receipt = {
        "packet": PACKET,
        "df_adoption": "DF-20261029-01",
        "source_commit": pin,
        "review_status": "LOCAL_BYTES_AND_SPANS_BOUNDED",
        "deny_code": None,
        "review_work_item_id": selected,
        "source_version_id": version_id,
        "evidence_span_count": len(spans),
        "evidence_spans": spans,
        "content_digest_proof": "LOCAL_BYTES_MATCH_DECLARED_SHA",
        "span_semantics": "ZERO_BASED_END_EXCLUSIVE_RECONCILED",
        "read_model": "INTERNAL_ONLY_NON_NORMATIVE_PREVIEW",
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "assignment": "NOT_ASSIGNED",
        "publication": "NOT_PUBLISHED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "logical_objects_claimed": "NOT_18_OF_18",
        "explicit_gaps": list(GAPS),
    }
    receipt["integrated_preview"] = viewmodel_with_evidence(
        payload,
        payload,
        receipt,
        commit=pin,
    )
    blob = json.dumps(receipt, sort_keys=True)
    for token in hide_extra:
        if token and token in blob:
            raise PreviewParseError("PREVIEW_LEAK")
    return receipt


def evidence_bound_review_files(
    batch_path: str | Path,
    work_item_id: Any,
    source_path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    payload = _load_payload(batch_path)
    data = _read_source_bytes(source_path)
    path = Path(str(source_path))
    return evidence_bound_review(
        payload,
        work_item_id,
        data,
        commit=commit,
        hide_extra=(path.name, path.as_posix()),
    )
