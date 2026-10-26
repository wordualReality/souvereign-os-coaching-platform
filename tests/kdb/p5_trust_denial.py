"""Exact DB trust-denial classification for P5 signed-ingress oracles.

Only a uniquely identified primary PostgreSQL
`ERROR: KDB_SECURITY_CONTEXT_NOT_CONFIGURED` with nonzero psql rc is CLOSED.
A later DETAIL or CONTEXT line that merely mentions the same token is RED.
permission denied is not that denial. This module does not connect to PostgreSQL.
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


def primary_error_message(body: str) -> str | None:
    """Return the first PostgreSQL ERROR message, ignoring DETAIL/CONTEXT."""
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line.startswith("ERROR:"):
            return line[len("ERROR:") :].strip()
    return None


def classify_db_fail_closed(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    if psql_rc == 0:
        return "POSITIVE_INGEST_WITHOUT_TRUST", "RED"
    primary = primary_error_message(blob)
    if primary == TRUST_SQLSTATE_MESSAGE:
        return "TRUST_FAIL_CLOSED", "CLOSED"
    if primary and primary.lower().startswith("permission denied"):
        return "PERMISSION_DENIED_NOT_TRUST", "RED"
    haystack = (primary or blob).lower()
    if any(token in haystack for token in UNEXPECTED):
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    return "TRUST_DENIAL_UNEXPECTED", "RED"
