"""Offline ProtocolVersion lifecycle / withdrawal read-eligibility gate.

SQL 001 kinds: PUBLISHED, REVALIDATION_REQUIRED, WITHDRAWN, SUPERSEDED.
Withdrawal and revoked source rights win. A local positive result is
READ_ELIGIBLE_OFFLINE_ONLY and NON_EXECUTABLE. It is not C04, C05,
outbox dispatch, or a public projection.

Event order is derived only from prior_event_id plus strictly later
occurred_at. There is no trusted watermark contract. Opaque content_sha256
is not recomputed from canonical_snapshot bytes.
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from tenant_scope import require_tenant_scope

SHA256_HEX = r"^[0-9a-f]{64}$"
UUID_RE = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
KINDS = frozenset({"PUBLISHED", "REVALIDATION_REQUIRED", "WITHDRAWN", "SUPERSEDED"})
RIGHTS_OK = "ADMITTED"
OWNER_NAMESPACE = "KDB"
DIGEST_PROOF = "OPAQUE_SHA_UNPROVEN"

PROTOCOL_KEYS = frozenset(
    {"protocol_id", "owning_module_ref", "taxonomy_version_ref", "created_at"}
)
PROTOCOL_VERSION_KEYS = frozenset(
    {
        "protocol_version_id",
        "protocol_id",
        "version_no",
        "source_candidate_revision_id",
        "human_decision_id",
        "content_sha256",
        "canonical_snapshot",
        "taxonomy_version_ref",
        "published_at",
        "created_at",
    }
)
EVENT_KEYS = frozenset(
    {
        "lifecycle_event_id",
        "protocol_version_id",
        "kind",
        "reason_code",
        "prior_event_id",
        "occurred_at",
        "recorded_at",
        "decision_ref",
    }
)
SOURCE_KEYS = frozenset(
    {
        "source_id",
        "tenant_scope",
        "source_class",
        "external_locator",
        "rights_status",
        "owner_namespace",
        "created_at",
    }
)
SOURCE_VERSION_KEYS = frozenset(
    {
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
    }
)
CANDIDATE_KEYS = frozenset(
    {
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
    }
)
CHAIN_KEYS = frozenset(
    {
        "protocol",
        "protocol_version",
        "lifecycle_events",
        "source",
        "source_version",
        "candidate_revision",
    }
)
UNTRUSTED_CLAIM_KEYS = frozenset(
    {
        "role",
        "is_admin",
        "auto_approve",
        "auto_approved",
        "approved",
        "decision",
        "human_signed",
        "publisher",
        "auto_publish",
        "kdb.tenant_scope",
        "tenant_id",
        "bypass",
        "canonical",
        "digest_verified",
        "independently_verified",
        "expires_at",
    }
)

CONTRACT_GAPS = (
    "TRUSTED_EVENT_WATERMARK_ABSENT",
    "LIFECYCLE_TABLES_HAVE_NO_TENANT_SCOPE",
    "O4_O5_PHYSICAL_RPC_UNKNOWN",
    "CONTENT_SHA_OPAQUE_NOT_RECOMPUTED",
    "HUMAN_DECISION_ID_IS_PIN_NOT_C04_WRITER",
    "C04_HUMAN_REVIEW_DECISION_HAS_NO_WRITE_API",
    "C05_CANONICAL_ADMISSION_HAS_NO_WRITE_API",
    "OUTBOX_DISPATCH_INACTIVE_M01",
)


class LifecycleError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.executable = False
        self.db_write = "NOT_ADMITTED"
        self.c04_human_decision = "NOT_WRITTEN"
        self.c05_canonical_admission = "NOT_WRITTEN"
        self.outbox = "NOT_EMITTED"
        self.content_digest_proof = DIGEST_PROOF


class LifecycleResult:
    decision = "READ_ELIGIBLE_OFFLINE_ONLY"
    code = "PUBLISHED_READ_ELIGIBLE_OFFLINE_ONLY"
    executable = False
    execution = "NON_EXECUTABLE"
    db_write = "NOT_ADMITTED"
    c04_human_decision = "NOT_WRITTEN"
    c05_canonical_admission = "NOT_WRITTEN"
    outbox = "NOT_EMITTED"
    content_digest_proof = DIGEST_PROOF
    contract_gaps = CONTRACT_GAPS

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "code": self.code,
            "executable": self.executable,
            "execution": self.execution,
            "db_write": self.db_write,
            "c04_human_decision": self.c04_human_decision,
            "c05_canonical_admission": self.c05_canonical_admission,
            "outbox": self.outbox,
            "content_digest_proof": self.content_digest_proof,
            "contract_gaps": list(self.contract_gaps),
        }


def _deny(code: str) -> None:
    raise LifecycleError(code)


def _need_dict(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _deny(code)
    return value


def _need_str(value: Any, code: str, *, min_len: int = 1, max_len: int | None = None) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        _deny(code)
    if min_len and len(value) < min_len:
        _deny(code)
    if max_len is not None and len(value) > max_len:
        _deny(code)
    return value


def _need_uuid(value: Any, code: str) -> str:
    text = _need_str(value, code)
    if re.fullmatch(UUID_RE, text) is None:
        _deny(code)
    return text.lower()


def _need_sha(value: Any, code: str) -> str:
    text = _need_str(value, code, min_len=64, max_len=64)
    if re.fullmatch(SHA256_HEX, text) is None:
        _deny(code)
    return text


def _need_int_pos(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _deny(code)
    return value


def _forbid_unknown(record: Mapping[str, Any], allowed: frozenset[str], code: str) -> None:
    extra = set(record) - allowed
    if extra & UNTRUSTED_CLAIM_KEYS:
        _deny("UNTRUSTED_CLAIM")
    if extra:
        _deny(code)


def _parse_time(value: Any, code: str) -> datetime:
    text = _need_str(value, code)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        _deny(code)
    if parsed.tzinfo is None:
        _deny("INDETERMINATE_EVENT_ORDER")
    return parsed


def _order_events(events: list[dict[str, Any]], protocol_version_id: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    seen_kind_decision: set[tuple[str, str]] = set()
    for event in events:
        item = _need_dict(event, "MALFORMED_EVENT")
        _forbid_unknown(item, EVENT_KEYS, "UNTRUSTED_CLAIM")
        event_id = _need_uuid(item.get("lifecycle_event_id"), "INVALID_LIFECYCLE_EVENT_ID")
        if event_id in by_id:
            _deny("DUPLICATE_EVENT")
        if _need_uuid(item.get("protocol_version_id"), "WRONG_PROTOCOL_VERSION") != protocol_version_id:
            _deny("WRONG_PROTOCOL_VERSION")
        kind = item.get("kind")
        if kind not in KINDS:
            _deny("INVALID_LIFECYCLE_KIND")
        _need_str(item.get("reason_code"), "INVALID_REASON_CODE")
        decision_ref = _need_str(item.get("decision_ref"), "INVALID_DECISION_REF")
        key = (kind, decision_ref)
        if key in seen_kind_decision:
            _deny("DUPLICATE_EVENT")
        seen_kind_decision.add(key)
        _parse_time(item.get("occurred_at"), "INDETERMINATE_EVENT_ORDER")
        _parse_time(item.get("recorded_at"), "INDETERMINATE_EVENT_ORDER")
        prior = item.get("prior_event_id")
        if prior is not None:
            _need_uuid(prior, "MISSING_PRIOR_EVENT")
        by_id[event_id] = item

    if not by_id:
        _deny("MISSING_LIFECYCLE_EVENT")

    successors: dict[str, list[str]] = {event_id: [] for event_id in by_id}
    roots: list[str] = []
    for event_id, item in by_id.items():
        prior = item.get("prior_event_id")
        if prior is None:
            roots.append(event_id)
            continue
        prior_id = prior.lower()
        if prior_id not in by_id:
            _deny("MISSING_PRIOR_EVENT")
        successors[prior_id].append(event_id)
    if len(roots) != 1:
        _deny("INDETERMINATE_EVENT_ORDER")
    for kids in successors.values():
        if len(kids) > 1:
            _deny("FORKED_EVENT_HISTORY")

    ordered: list[dict[str, Any]] = []
    current = roots[0]
    seen: set[str] = set()
    while current is not None:
        if current in seen:
            _deny("INDETERMINATE_EVENT_ORDER")
        seen.add(current)
        ordered.append(by_id[current])
        kids = successors[current]
        current = kids[0] if kids else None
    if len(ordered) != len(by_id):
        _deny("INDETERMINATE_EVENT_ORDER")

    for index in range(1, len(ordered)):
        prior_time = _parse_time(ordered[index - 1].get("occurred_at"), "INDETERMINATE_EVENT_ORDER")
        later_time = _parse_time(ordered[index].get("occurred_at"), "INDETERMINATE_EVENT_ORDER")
        if later_time <= prior_time:
            _deny("INDETERMINATE_EVENT_ORDER")
    return ordered


def evaluate_lifecycle_read_eligibility(chain: Mapping[str, Any] | None) -> LifecycleResult:
    raw = _need_dict(chain, "INVALID_CHAIN")
    _forbid_unknown(raw, CHAIN_KEYS, "UNTRUSTED_CLAIM")
    if "human_review_decision" in raw or "outbox_event" in raw or "protocol_version_write" in raw:
        _deny("UNTRUSTED_CLAIM")

    protocol = deepcopy(_need_dict(raw.get("protocol"), "MISSING_PROVENANCE"))
    version = deepcopy(_need_dict(raw.get("protocol_version"), "MISSING_PROVENANCE"))
    source = deepcopy(_need_dict(raw.get("source"), "UNKNOWN_SOURCE"))
    source_version = deepcopy(_need_dict(raw.get("source_version"), "MISSING_PROVENANCE"))
    candidate = deepcopy(_need_dict(raw.get("candidate_revision"), "MISSING_PROVENANCE"))
    events_raw = raw.get("lifecycle_events")
    if not isinstance(events_raw, list):
        _deny("MISSING_LIFECYCLE_EVENT")

    _forbid_unknown(protocol, PROTOCOL_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(version, PROTOCOL_VERSION_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(source, SOURCE_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(source_version, SOURCE_VERSION_KEYS, "UNTRUSTED_CLAIM")
    _forbid_unknown(candidate, CANDIDATE_KEYS, "UNTRUSTED_CLAIM")

    protocol_id = _need_uuid(protocol.get("protocol_id"), "INVALID_PROTOCOL_ID")
    _need_str(protocol.get("owning_module_ref"), "INVALID_OWNING_MODULE_REF")
    taxonomy = _need_str(protocol.get("taxonomy_version_ref"), "INVALID_TAXONOMY_VERSION_REF")

    protocol_version_id = _need_uuid(version.get("protocol_version_id"), "INVALID_PROTOCOL_VERSION_ID")
    if _need_uuid(version.get("protocol_id"), "WRONG_PROTOCOL_VERSION") != protocol_id:
        _deny("WRONG_PROTOCOL_VERSION")
    _need_int_pos(version.get("version_no"), "INVALID_VERSION_NO")
    candidate_id = _need_uuid(version.get("source_candidate_revision_id"), "MISSING_PROVENANCE")
    _need_uuid(version.get("human_decision_id"), "INVALID_HUMAN_DECISION_PIN")
    _need_sha(version.get("content_sha256"), "INVALID_CONTENT_DIGEST")
    snapshot = version.get("canonical_snapshot")
    if not isinstance(snapshot, dict) or len(snapshot) < 1:
        _deny("INVALID_CANONICAL_SNAPSHOT")
    if _need_str(version.get("taxonomy_version_ref"), "INVALID_TAXONOMY_VERSION_REF") != taxonomy:
        _deny("INDETERMINATE_TAXONOMY_PIN")
    _parse_time(version.get("published_at"), "INVALID_PUBLISHED_AT")

    tenant = require_tenant_scope(source.get("tenant_scope"))
    if require_tenant_scope(source_version.get("tenant_scope")) != tenant:
        _deny("CROSS_TENANT")
    if require_tenant_scope(candidate.get("tenant_scope")) != tenant:
        _deny("CROSS_TENANT")
    source_id = _need_uuid(source.get("source_id"), "INVALID_SOURCE_ID")
    if source.get("owner_namespace") != OWNER_NAMESPACE:
        _deny("OWNER_NAMESPACE_DENIED")
    source_version_id = _need_uuid(source_version.get("source_version_id"), "MISSING_PROVENANCE")
    if _need_uuid(source_version.get("source_id"), "MISSING_PROVENANCE") != source_id:
        _deny("MISSING_PROVENANCE")
    if _need_uuid(candidate.get("candidate_revision_id"), "MISSING_PROVENANCE") != candidate_id:
        _deny("MISSING_PROVENANCE")
    if _need_uuid(candidate.get("source_version_id"), "MISSING_PROVENANCE") != source_version_id:
        _deny("MISSING_PROVENANCE")

    ordered = _order_events([deepcopy(item) for item in events_raw], protocol_version_id)
    kinds = {item["kind"] for item in ordered}
    published_count = sum(1 for item in ordered if item["kind"] == "PUBLISHED")
    if published_count > 1:
        _deny("CONFLICTING_PUBLISHED")

    rights_status = source.get("rights_status")
    if rights_status == "REVOKED":
        _deny("REVOKED_SOURCE")
    if rights_status != RIGHTS_OK:
        _deny("SOURCE_RIGHTS_NOT_ADMITTED")

    if "WITHDRAWN" in kinds:
        _deny("WITHDRAWN")
    if "SUPERSEDED" in kinds:
        _deny("SUPERSEDED")
    if "REVALIDATION_REQUIRED" in kinds:
        _deny("REVALIDATION_REQUIRED")
    if kinds != {"PUBLISHED"}:
        _deny("INDETERMINATE_EVENT_ORDER")
    return LifecycleResult()
