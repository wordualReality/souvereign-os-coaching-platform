"""Read-only offline diagnostic over P07 tenant, P08 provenance, and P09 lifecycle.

This is a local operator demonstration. Every receipt is NON_EXECUTABLE and
NOT_ADMITTED, including when the three stage checks are internally coherent.
It does not write SQL, call the network, emit outbox, or create C04/C05.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from lifecycle_eligibility import LifecycleError, evaluate_lifecycle_read_eligibility
from provenance_eligibility import EligibilityError, evaluate_review_eligibility
from tenant_scope import TenantScopeError, require_tenant_scope

MAX_CHARS = 65536
MAX_NESTING = 8
MAX_INT_DIGITS = 18
CASE_ID_RE = r"^[A-Za-z0-9._-]{1,64}$"
INPUT_KEYS = frozenset(
    {"case_id", "expected_tenant_scope", "candidate_chain", "lifecycle_chain"}
)
LIMITATIONS = (
    "FINAL_ALWAYS_NOT_ADMITTED",
    "NO_VERIFIED_C04_C05_TRANSITION",
    "CONTENT_SHA_OPAQUE_UNPROVEN",
    "EVENT_WATERMARK_UNTRUSTED",
    "PIAC_NOT_CONFIGURED",
    "NO_DB_WRITE",
    "NO_OUTBOX",
)


class DiagnosticParseError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _reject_constant(value: str) -> None:
    raise DiagnosticParseError("NONCANONICAL_JSON")


def _bounded_int(value: str) -> int:
    digits = value[1:] if value[:1] in "+-" else value
    if len(digits) > MAX_INT_DIGITS:
        raise DiagnosticParseError("HUGE_INTEGER")
    return int(value)


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DiagnosticParseError("DUPLICATE_JSON_KEY")
        seen[key] = value
    return seen


def _nesting(value: Any, depth: int = 1) -> None:
    if depth > MAX_NESTING:
        raise DiagnosticParseError("INPUT_TOO_DEEP")
    if isinstance(value, dict):
        for item in value.values():
            _nesting(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _nesting(item, depth + 1)


def parse_diagnostic_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or text == "":
        raise DiagnosticParseError("EMPTY_INPUT")
    if len(text) > MAX_CHARS:
        raise DiagnosticParseError("INPUT_TOO_LARGE")
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_no_duplicate_object,
            parse_int=_bounded_int,
            parse_constant=_reject_constant,
        )
    except DiagnosticParseError:
        raise
    except json.JSONDecodeError as exc:
        raise DiagnosticParseError("MALFORMED_JSON") from exc
    except ValueError as exc:
        raise DiagnosticParseError("MALFORMED_JSON") from exc
    if not isinstance(payload, dict):
        raise DiagnosticParseError("INVALID_INPUT")
    _nesting(payload)
    extra = set(payload) - INPUT_KEYS
    if extra:
        raise DiagnosticParseError("UNEXPECTED_INPUT_KEY")
    return payload


def _stage(status: str, code: str) -> dict[str, str]:
    return {"status": status, "code": code}


def _receipt(
    *,
    case_id: str,
    stages: dict[str, dict[str, str]],
    commit: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "db_write": "NOT_ADMITTED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
        "event_watermark": "UNTRUSTED",
        "piac": "NOT_CONFIGURED_FAIL_CLOSED",
        "stages": stages,
        "source_commit": commit,
        "limitations": list(LIMITATIONS),
    }


def _lookup(mapping: Mapping[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def diagnose(payload: Mapping[str, Any] | None, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    raw = deepcopy(payload if isinstance(payload, dict) else {})
    extra = set(raw) - INPUT_KEYS
    if extra:
        raise DiagnosticParseError("UNEXPECTED_INPUT_KEY")
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or re.fullmatch(CASE_ID_RE, case_id) is None:
        raise DiagnosticParseError("INVALID_CASE_ID")
    stages = {
        "tenant_scope": _stage("NOT_RUN", "NOT_RUN"),
        "linkage": _stage("NOT_RUN", "NOT_RUN"),
        "provenance": _stage("NOT_RUN", "NOT_RUN"),
        "lifecycle": _stage("NOT_RUN", "NOT_RUN"),
        "c04_c05_transition": _stage("ABSENT", "NO_VERIFIED_C04_C05_TRANSITION"),
    }
    try:
        expected = require_tenant_scope(raw.get("expected_tenant_scope"))
        candidate = raw.get("candidate_chain")
        lifecycle = raw.get("lifecycle_chain")
        if not isinstance(candidate, dict) or not isinstance(lifecycle, dict):
            raise DiagnosticParseError("MISSING_CHAIN")
        require_tenant_scope(_lookup(candidate, "source", "tenant_scope"), expected)
        require_tenant_scope(_lookup(candidate, "source_version", "tenant_scope"), expected)
        require_tenant_scope(_lookup(candidate, "candidate_revision", "tenant_scope"), expected)
        require_tenant_scope(_lookup(candidate, "submission", "tenant_scope"), expected)
        require_tenant_scope(_lookup(candidate, "review_work_item", "tenant_scope"), expected)
        require_tenant_scope(_lookup(lifecycle, "source", "tenant_scope"), expected)
        require_tenant_scope(_lookup(lifecycle, "source_version", "tenant_scope"), expected)
        require_tenant_scope(_lookup(lifecycle, "candidate_revision", "tenant_scope"), expected)
        stages["tenant_scope"] = _stage("STAGE_LOCAL_ELIGIBLE", "TENANT_SCOPE_BOUND")
    except TenantScopeError as exc:
        stages["tenant_scope"] = _stage("DENY", exc.code)
        return _receipt(case_id=case_id, stages=stages, commit=commit)

    cand_source = _lookup(candidate, "source", "source_id")
    life_source = _lookup(lifecycle, "source", "source_id")
    cand_version = _lookup(candidate, "source_version", "source_version_id")
    life_version = _lookup(lifecycle, "source_version", "source_version_id")
    cand_revision = _lookup(candidate, "candidate_revision", "candidate_revision_id")
    life_revision = _lookup(lifecycle, "protocol_version", "source_candidate_revision_id")
    if None in (cand_source, life_source, cand_version, life_version, cand_revision, life_revision):
        stages["linkage"] = _stage("INDETERMINATE", "CONTRACT_GAP_OR_MISSING_JOIN")
    elif cand_source != life_source:
        stages["linkage"] = _stage("DENY", "SOURCE_ID_MISMATCH")
    elif cand_version != life_version:
        stages["linkage"] = _stage("DENY", "SOURCE_VERSION_MISMATCH")
    elif cand_revision != life_revision:
        stages["linkage"] = _stage("DENY", "CANDIDATE_PROTOCOL_LINK_MISMATCH")
    else:
        stages["linkage"] = _stage("STAGE_LOCAL_ELIGIBLE", "CHAIN_IDS_BOUND")

    try:
        provenance = evaluate_review_eligibility(candidate)
        stages["provenance"] = _stage("STAGE_LOCAL_ELIGIBLE", provenance.code)
    except EligibilityError as exc:
        stages["provenance"] = _stage("DENY", exc.code)

    try:
        lifecycle_result = evaluate_lifecycle_read_eligibility(lifecycle)
        stages["lifecycle"] = _stage("STAGE_LOCAL_ELIGIBLE", lifecycle_result.code)
    except LifecycleError as exc:
        stages["lifecycle"] = _stage("DENY", exc.code)

    return _receipt(case_id=case_id, stages=stages, commit=commit)


def diagnose_file(path: str | Path, *, commit: str = "UNPINNED_LOCAL") -> dict[str, Any]:
    text_path = str(path)
    lowered = text_path.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("file:"):
        raise DiagnosticParseError("NETWORK_PATH_DENIED")
    location = Path(path)
    if not location.is_file():
        raise DiagnosticParseError("MISSING_INPUT_FILE")
    size = location.stat().st_size
    if size > MAX_CHARS:
        raise DiagnosticParseError("INPUT_TOO_LARGE")
    text = location.read_text(encoding="utf-8")
    payload = parse_diagnostic_json(text)
    before = json.dumps(payload, sort_keys=True)
    receipt = diagnose(payload, commit=commit)
    after = json.dumps(payload, sort_keys=True)
    if before != after:
        raise DiagnosticParseError("INPUT_MUTATED")
    return receipt
