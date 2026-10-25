"""Independent tenant-digest oracle classification.

A trust-guard rejection never passes the tenant-digest assertion.
Unexpected SQL and connection errors are RED, not CLOSED.
This module does not connect to PostgreSQL.
"""
from __future__ import annotations

UNEXPECTED = (
    "could not connect",
    "connection refused",
    "does not exist",
    "syntax error",
    "division by zero",
    "invalid input syntax",
    "server closed the connection",
    "not postgresql 17",
    "could not translate host",
    "timeout expired",
    "connection to server",
    "no such file or directory",
)


def unexpected_token(blob: str) -> str | None:
    lower = (blob or "").lower()
    for token in UNEXPECTED:
        if token in lower:
            return token
    return None


def classify_runtime_execute(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    if psql_rc == 0:
        return "RUNTIME_EXECUTE_ACCEPTED", "RED"
    hit = unexpected_token(blob)
    if hit:
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    if "permission denied" in blob.lower():
        return "RUNTIME_EXECUTE_DENIED", "CLOSED"
    return "RUNTIME_EXECUTE_UNEXPECTED", "RED"


def classify_trust_fail_closed(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    if psql_rc == 0:
        return "POSITIVE_INGEST_WITHOUT_TRUST", "RED"
    hit = unexpected_token(blob)
    if hit:
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    if "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in blob:
        return "TRUST_FAIL_CLOSED", "CLOSED"
    return "TRUST_FAIL_CLOSED_UNEXPECTED", "RED"


def classify_tenant_digest_probe(*, psql_rc: int, body: str) -> tuple[str, str]:
    """CLOSED only for exact KDB_HASH_MISMATCH while EXECUTE is present.

    KDB_SECURITY_CONTEXT_NOT_CONFIGURED is RED here. That is the trust
    gate, not tenant-digest binding.
    """
    blob = body or ""
    if psql_rc == 0:
        return "TENANT_GUC_SPOOF_ACCEPTED_AT_DB", "RED"
    hit = unexpected_token(blob)
    if hit:
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    if "KDB_HASH_MISMATCH" in blob:
        return "DIGEST_TENANT_BINDING_VERIFIED", "CLOSED"
    if "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in blob:
        return "DIGEST_TENANT_BINDING_BROKEN", "RED"
    return "TENANT_SPOOF_UNEXPECTED", "RED"
