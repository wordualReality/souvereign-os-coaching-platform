"""Map disposable PG17 Source-to-Review rows onto P08/P10 diagnostic input.

Fixture DML is TEST_FIXTURE_ADMIN only. This mapper does not grant runtime
read authority and does not invent C04/C05 rows.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SOURCE_KEYS = (
    "source_id",
    "tenant_scope",
    "source_class",
    "external_locator",
    "rights_status",
    "owner_namespace",
    "created_at",
)
SOURCE_VERSION_KEYS = (
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
)
SUBMISSION_KEYS = (
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
)
CANDIDATE_KEYS = (
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
)
WORK_ITEM_KEYS = (
    "review_work_item_id",
    "candidate_revision_id",
    "tenant_scope",
    "owner_queue",
    "state",
    "correlation_id",
    "created_at",
)

REDACT_SUBSTRINGS = (
    "synthetic://",
    "KNOWLEDGE_INTAKE",
    "synthetic-candidate",
    "owner-authored-fixture",
    "synthetic-protocol",
)


def _as_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, (int, float, list, dict)):
        return value
    return str(value)


def _pick(record: Mapping[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("MISSING_SNAPSHOT_ROW")
    out: dict[str, Any] = {}
    for key in keys:
        if key not in record:
            continue
        value = record[key]
        if key.endswith("_id") or key.endswith("_at") or key in {
            "external_locator",
            "tenant_scope",
            "source_class",
            "rights_status",
            "owner_namespace",
            "media_type",
            "origin_owner",
            "idempotency_key",
            "request_sha256",
            "principal_context_ref",
            "access_decision_ref",
            "purpose",
            "status",
            "content_sha256",
            "rights_snapshot_sha256",
            "validation_state",
            "review_state",
            "owner_queue",
            "state",
        }:
            out[key] = _as_text(value)
        elif key in {"source_version_no", "revision_no"}:
            out[key] = int(value)
        else:
            out[key] = value
    return out


def map_candidate_chain(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": _pick(snapshot.get("source"), SOURCE_KEYS),
        "source_version": _pick(snapshot.get("source_version"), SOURCE_VERSION_KEYS),
        "submission": _pick(snapshot.get("submission"), SUBMISSION_KEYS),
        "candidate_revision": _pick(snapshot.get("candidate_revision"), CANDIDATE_KEYS),
        "review_work_item": _pick(snapshot.get("review_work_item"), WORK_ITEM_KEYS),
    }


def map_without_work_item(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    chain = map_candidate_chain(snapshot)
    del chain["review_work_item"]
    if isinstance(snapshot.get("orphan_candidate"), dict):
        chain["candidate_revision"] = _pick(snapshot["orphan_candidate"], CANDIDATE_KEYS)
    return chain


def diagnostic_payload(
    *,
    case_id: str,
    expected_tenant_scope: str,
    candidate_chain: Mapping[str, Any],
    lifecycle_chain: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "expected_tenant_scope": expected_tenant_scope,
        "candidate_chain": dict(candidate_chain),
        "lifecycle_chain": dict(lifecycle_chain),
    }


def id_digest(snapshot: Mapping[str, Any]) -> str:
    ids = {
        "source_id": _as_text((snapshot.get("source") or {}).get("source_id")),
        "source_version_id": _as_text(
            (snapshot.get("source_version") or {}).get("source_version_id")
        ),
        "submission_id": _as_text((snapshot.get("submission") or {}).get("submission_id")),
        "candidate_revision_id": _as_text(
            (snapshot.get("candidate_revision") or {}).get("candidate_revision_id")
        ),
        "review_work_item_id": _as_text(
            (snapshot.get("review_work_item") or {}).get("review_work_item_id")
        ),
    }
    payload = json.dumps(ids, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_redacted(blob: str) -> None:
    for token in REDACT_SUBSTRINGS:
        if token in blob:
            raise AssertionError(f"P11_RECEIPT_LEAK {token}")
