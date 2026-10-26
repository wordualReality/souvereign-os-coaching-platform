"""Exact DB trust-denial classification for P5 signed-ingress oracles.

TRUST_FAIL_CLOSED requires nonzero psql rc and exactly one PostgreSQL
ERROR line whose message is KDB_SECURITY_CONTEXT_NOT_CONFIGURED.
A later DETAIL/CONTEXT mention, a second ERROR line, permission denied,
transport failure and rc 0 stay RED. This module does not connect to PostgreSQL.
"""
from __future__ import annotations

TRUST_SQLSTATE_MESSAGE = "KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
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


def error_messages(body: str) -> list[str]:
    """Return every PostgreSQL ERROR message. DETAIL/CONTEXT are ignored."""
    found: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line.startswith("ERROR:"):
            found.append(line[len("ERROR:") :].strip())
    return found


def primary_error_message(body: str) -> str | None:
    messages = error_messages(body)
    return messages[0] if messages else None


def classify_db_fail_closed(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    if psql_rc == 0:
        return "POSITIVE_INGEST_WITHOUT_TRUST", "RED"
    messages = error_messages(blob)
    if len(messages) > 1:
        return "MULTIPLE_PRIMARY_ERRORS", "RED"
    primary = messages[0] if messages else None
    if primary == TRUST_SQLSTATE_MESSAGE:
        return "TRUST_FAIL_CLOSED", "CLOSED"
    if primary and primary.lower().startswith("permission denied"):
        return "PERMISSION_DENIED_NOT_TRUST", "RED"
    haystack = (primary or blob).lower()
    if any(token in haystack for token in UNEXPECTED):
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    return "TRUST_DENIAL_UNEXPECTED", "RED"
