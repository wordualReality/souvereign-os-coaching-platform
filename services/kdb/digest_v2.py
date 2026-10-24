"""KDB-owned SQL-v2 digest adapter.

The contract is SHA-256 of UTF-8 PostgreSQL jsonb_build_array(...)::text.
json.dumps is accepted only after byte identity with PostgreSQL is proved
for the exact vector. JSON.stringify is not this contract.
This module does not GRANT SQL EXECUTE to producers or n8n.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence

VERSION = "v2"
UNRESOLVED = "CANONICAL_DIGEST_CONTRACT_UNRESOLVED"


class DigestContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(code if not detail else f"{code}:{detail}")


def pg_jsonb_array_text(values: Sequence[object]) -> str:
    """Local encoder aimed at PostgreSQL 17 jsonb array ::text.

    Proven only against golden vectors. A mismatch is unresolved, not a guess.
    """
    return json.dumps(list(values), ensure_ascii=False, separators=(", ", ": "), sort_keys=True)


def digest_hex_from_jsonb_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def local_digest(values: Sequence[object]) -> str:
    if not values or values[0] != VERSION:
        raise DigestContractError(UNRESOLVED, "version")
    return digest_hex_from_jsonb_text(pg_jsonb_array_text(values))


def o1_fields(
    command_id: str,
    tenant_scope: str | None,
    origin_owner: str | None,
    purpose: str | None,
    source_class: str | None,
    external_locator: str | None,
    content_sha256: str | None,
    rights_digest: str | None,
    principal_context_ref: str | None,
    access_decision_ref: str | None,
    idempotency_key: str | None,
    submission_id: str | None,
) -> list[object]:
    return [
        VERSION,
        "SOURCE_INTAKE",
        command_id,
        tenant_scope,
        origin_owner,
        purpose,
        source_class,
        external_locator,
        content_sha256,
        rights_digest,
        principal_context_ref,
        access_decision_ref,
        idempotency_key,
        submission_id,
    ]


def o2_fields(
    command_id: str,
    tenant_scope: str | None,
    submission_id: str | None,
    source_version_id: str | None,
    candidate_id: str | None,
    revision_no: int | None,
    content_sha256: str | None,
    payload_digest: str | None,
    evidence_spans_digest: str | None,
    actor_ref: str | None,
    access_decision_ref: str | None,
) -> list[object]:
    return [
        VERSION,
        "CANDIDATE_PROPOSAL",
        command_id,
        tenant_scope,
        submission_id,
        source_version_id,
        candidate_id,
        revision_no,
        content_sha256,
        payload_digest,
        evidence_spans_digest,
        actor_ref,
        access_decision_ref,
    ]


def o3_fields(
    command_id: str,
    tenant_scope: str | None,
    candidate_revision_id: str | None,
    actor_ref: str | None,
    access_decision_ref: str | None,
) -> list[object]:
    return [
        VERSION,
        "REVIEW_HANDOFF",
        command_id,
        tenant_scope,
        candidate_revision_id,
        actor_ref,
        access_decision_ref,
    ]


def sql_jsonb_build_array(values: Sequence[object]) -> str:
    """SQL fragment for jsonb_build_array over Python values. Superuser tests only."""
    parts = []
    for value in values:
        if value is None:
            parts.append("NULL")
        elif isinstance(value, bool):
            parts.append("true" if value else "false")
        elif isinstance(value, int) and not isinstance(value, bool):
            parts.append(f"{value}::bigint" if abs(value) > 2_147_483_647 else str(value))
        elif isinstance(value, (dict, list)):
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            parts.append("'" + raw.replace("'", "''") + "'::jsonb")
        else:
            text = str(value).replace("'", "''")
            parts.append("'" + text + "'")
    return "jsonb_build_array(" + ", ".join(parts) + ")"
