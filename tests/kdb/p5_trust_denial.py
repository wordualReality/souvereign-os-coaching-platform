"""Exact DB trust-denial classification for P5 signed-ingress oracles.

permission denied is not KDB_SECURITY_CONTEXT_NOT_CONFIGURED.
Unexpected SQL and transport errors are RED. This module does not connect
to PostgreSQL.
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
    "wrong role",
)


def classify_db_fail_closed(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    lower = blob.lower()
    if psql_rc == 0:
        return "POSITIVE_INGEST_WITHOUT_TRUST", "RED"
    if any(token in lower for token in UNEXPECTED):
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    if "permission denied" in lower:
        return "PERMISSION_DENIED_NOT_TRUST", "RED"
    if "KDB_SECURITY_CONTEXT_NOT_CONFIGURED" in blob:
        return "TRUST_FAIL_CLOSED", "CLOSED"
    return "TRUST_DENIAL_UNEXPECTED", "RED"
