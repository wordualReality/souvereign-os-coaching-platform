"""Versioned offline review viewmodel. Not a live consumer contract.

Builds a machine-readable JSON preview from a P14 inbox batch, P15 case
detail, and P17 count-only snapshot delta. The document is SNAPSHOT_UNTRUSTED,
NON_EXECUTABLE, NOT_ASSIGNED, and NOT_ADMITTED. It is not a C04 case, C05
publication, or admitted producer/consumer API.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from offline_review_case_detail import case_detail
from offline_review_inbox import (
    FORBIDDEN_SUBSTRINGS,
    MAX_CHARS,
    MAX_ENTRIES,
    inbox,
    parse_inbox_json,
)
from offline_review_snapshot_delta import snapshot_delta
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PreviewParseError,
    REPO_ROOT,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P19-VERSIONED-OFFLINE-REVIEW-VIEWMODEL-01"
SCHEMA_ID = "kdb-internal://m01/offline_review_viewmodel.schema.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "kdb" / "offline_review_viewmodel.schema.json"
SCHEMA_VERSION = "1.0"
KIND = "KDB_REVIEW_OFFLINE_PREVIEW"
PREVIEW_CONTRACT_VERSION = "kdb://m01/offline_review_viewmodel/1.0"
CASE_KEYS = frozenset(
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
        "consumer_o1",
        "consumer_o2",
        "consumer_o3",
        "eligibility_reasons",
        "explicit_gaps",
        "provenance_trace",
    }
)
UUID_KEYS = (
    "source_id",
    "source_version_id",
    "submission_id",
    "candidate_id",
    "candidate_revision_id",
    "review_work_item_id",
    "correlation_id",
)
LEAK_TOKENS = (
    "media_type",
    "rights_basis",
    "external_locator",
    "proposal_payload",
    "assigned_reviewer",
    "READY",
    "approved",
)


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _load_schema() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file() or SCHEMA_PATH.is_symlink():
        _deny_parse("SCHEMA_MISSING")
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewParseError("SCHEMA_MISSING") from exc
    if not isinstance(schema, dict):
        _deny_parse("SCHEMA_MISSING")
    return schema


def _resolve(schema: Mapping[str, Any], root: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/$defs/"):
        _deny_parse("SCHEMA_INVALID")
    name = ref.split("/")[-1]
    defs = root.get("$defs")
    if not isinstance(defs, dict) or name not in defs:
        _deny_parse("SCHEMA_INVALID")
    resolved = defs[name]
    if not isinstance(resolved, dict):
        _deny_parse("SCHEMA_INVALID")
    return resolved


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _validate_instance(instance: Any, schema: Mapping[str, Any], root: Mapping[str, Any]) -> None:
    schema = _resolve(schema, root)
    expected = schema.get("type")
    if isinstance(expected, str):
        if not _type_ok(instance, expected):
            _deny_parse("SCHEMA_INVALID")
    elif isinstance(expected, list):
        if not any(_type_ok(instance, item) for item in expected if isinstance(item, str)):
            _deny_parse("SCHEMA_INVALID")
    if "const" in schema and instance != schema["const"]:
        _deny_parse("SCHEMA_INVALID")
    if "enum" in schema and instance not in schema["enum"]:
        _deny_parse("SCHEMA_INVALID")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            _deny_parse("SCHEMA_INVALID")
        if "maxLength" in schema and len(instance) > int(schema["maxLength"]):
            _deny_parse("SCHEMA_INVALID")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, instance) is None:
            _deny_parse("SCHEMA_INVALID")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < int(schema["minimum"]):
            _deny_parse("SCHEMA_INVALID")
        if "maximum" in schema and instance > int(schema["maximum"]):
            _deny_parse("SCHEMA_INVALID")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            _deny_parse("SCHEMA_INVALID")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            _deny_parse("SCHEMA_INVALID")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for item in instance:
                _validate_instance(item, item_schema, root)
    if isinstance(instance, dict):
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for key in required:
            if key not in instance:
                _deny_parse("SCHEMA_INVALID")
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(props)
            if extra:
                _deny_parse("SCHEMA_INVALID")
        for key, value in instance.items():
            child = props.get(key)
            if isinstance(child, dict):
                _validate_instance(value, child, root)


def validate_viewmodel(instance: Mapping[str, Any] | None) -> None:
    if not isinstance(instance, dict):
        _deny_parse("SCHEMA_INVALID")
    schema = _load_schema()
    _validate_instance(instance, schema, schema)


def _assert_redacted(blob: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")
    for token in LEAK_TOKENS:
        if token in blob:
            _deny_parse("PREVIEW_LEAK")


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
    for key in UUID_KEYS:
        value = card.get(key)
        if isinstance(value, str) and value:
            tokens.append(value)
            tokens.append(value.lower())
    return tokens


def _forbid_tokens(blob: str, tokens: Iterable[str]) -> None:
    for token in tokens:
        if token and token in blob:
            _deny_parse("PREVIEW_LEAK")


def _zero_counts() -> dict[str, int]:
    return {
        "baseline_eligible_count": 0,
        "current_eligible_count": 0,
        "visible_current_count": 0,
        "added_count": 0,
        "removed_or_denied_count": 0,
        "unchanged_count": 0,
    }


def _counts_from_delta(delta: Mapping[str, Any]) -> dict[str, int]:
    if delta.get("delta_status") == "DELTA_DENIED":
        return _zero_counts()
    return {
        "baseline_eligible_count": int(delta.get("baseline_eligible_count") or 0),
        "current_eligible_count": int(delta.get("current_eligible_count") or 0),
        "visible_current_count": int(delta.get("visible_current_count") or 0),
        "added_count": int(delta.get("added_count") or 0),
        "removed_or_denied_count": int(delta.get("removed_or_denied_count") or 0),
        "unchanged_count": int(delta.get("unchanged_count") or 0),
    }


def _gates() -> dict[str, Any]:
    return {
        "packet": PACKET,
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "internal_only": True,
        "non_normative": True,
        "preview_contract_version": PREVIEW_CONTRACT_VERSION,
        "df_adoption": "DF-20261029-01",
        "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        "final_authority": "NOT_ADMITTED",
        "assignment": "NOT_ASSIGNED",
        "execution": "NON_EXECUTABLE",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "snapshot_order": "SNAPSHOT_ORDER_NOT_ATTESTED",
        "change_authority": "POSSIBLE_CHANGE_ONLY",
        "event_watermark": "EVENT_WATERMARK_UNKNOWN",
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
    }


def _case_from_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    extra = set(detail) - CASE_KEYS
    if extra:
        _deny_parse("PREVIEW_LEAK")
    for forbidden in ("media_type", "locator", "payload", "rights_basis"):
        if forbidden in detail:
            _deny_parse("PREVIEW_LEAK")
    case: dict[str, Any] = {}
    for key in CASE_KEYS:
        if key not in detail:
            _deny_parse("PREVIEW_LEAK")
        case[key] = detail[key]
    case["eligibility_reasons"] = list(detail["eligibility_reasons"])
    case["explicit_gaps"] = list(detail["explicit_gaps"])
    case["provenance_trace"] = dict(detail["provenance_trace"])
    for key in UUID_KEYS:
        case[key] = str(case[key]).lower()
    return case


def _seal(model: dict[str, Any], removed_tokens: Iterable[str]) -> dict[str, Any]:
    validate_viewmodel(model)
    blob = json.dumps(model, sort_keys=True)
    _assert_redacted(blob)
    _forbid_tokens(blob, removed_tokens)
    if ATC10_NAMED_CANDIDATES and "18/18" in blob:
        _deny_parse("PREVIEW_LEAK")
    return model


def _denied_model(*, deny_code: str, commit: str) -> dict[str, Any]:
    model = {
        **_gates(),
        "source_commit": commit,
        "viewmodel_status": "DEMO_DENIED",
        "deny_code": deny_code,
        **_zero_counts(),
        "current_cases": [],
    }
    return _seal(model, ())


def viewmodel(
    baseline: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    delta = snapshot_delta(baseline, current, commit=pin)
    if delta.get("delta_status") == "DELTA_DENIED":
        return _denied_model(deny_code=str(delta.get("deny_code") or "DELTA_DENIED"), commit=pin)
    counts = _counts_from_delta(delta)
    curr_inbox = _full_inbox(current, pin)
    curr_deny = _batch_denied(curr_inbox)
    if curr_deny:
        return _denied_model(deny_code=curr_deny, commit=pin)
    tenant = curr_inbox.get("tenant_scope")
    if not isinstance(tenant, str) or not tenant:
        return _denied_model(deny_code="CROSS_TENANT", commit=pin)
    cards = list(curr_inbox.get("cards") or [])
    cases: list[dict[str, Any]] = []
    for card in cards:
        work_id = card.get("review_work_item_id")
        item = case_detail(current, work_id, commit=pin)
        detail = item.get("detail")
        if item.get("detail_status") != "DETAIL_ONLY" or not isinstance(detail, dict):
            _deny_parse("PREVIEW_LEAK")
        cases.append(_case_from_detail(detail))
    cases.sort(key=lambda item: str(item["review_work_item_id"]))
    if len(cases) != counts["visible_current_count"]:
        _deny_parse("PREVIEW_LEAK")
    if len(cases) > MAX_ENTRIES:
        _deny_parse("PREVIEW_LEAK")
    base_inbox = _full_inbox(baseline, pin)
    base_cards = list(base_inbox.get("cards") or [])
    current_ids = set(_work_ids(cases))
    removed_tokens: list[str] = []
    for card in base_cards:
        work_id = str(card.get("review_work_item_id") or "").lower()
        if work_id and work_id not in current_ids:
            removed_tokens.extend(_card_tokens(card))
    model = {
        **_gates(),
        "source_commit": pin,
        "viewmodel_status": "PREVIEW_ONLY",
        "deny_code": None,
        "tenant_scope": tenant,
        **counts,
        "current_cases": cases,
    }
    return _seal(model, removed_tokens)


def _load_payload(path: str | Path) -> tuple[dict[str, Any], Path]:
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    return parse_inbox_json(text), location


def viewmodel_files(
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
    return viewmodel(baseline, current, commit=pin)
