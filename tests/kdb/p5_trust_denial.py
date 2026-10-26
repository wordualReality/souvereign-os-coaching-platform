"""Exact DB trust-denial classification for P5 signed-ingress oracles.

TRUST_FAIL_CLOSED requires psql_rc exactly 3, no transport/FATAL/psql
diagnostic, and exactly one PostgreSQL ERROR line whose message is
KDB_SECURITY_CONTEXT_NOT_CONFIGURED. DETAIL/CONTEXT mentions, a second
ERROR line, permission denied, other exit codes and mixed transport stay
RED. This module does not connect to PostgreSQL.
"""
from __future__ import annotations

TRUST_SQLSTATE_MESSAGE = "KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
TRUST_PSQL_RC = 3
TRANSPORT = (
    "could not connect",
    "connection refused",
    "server closed the connection",
    "fatal:",
    "psql: error:",
    "timeout expired",
    "could not translate host",
    "connection to server",
    "ssl syscall",
    "no pg_hba.conf",
)
SQL_UNEXPECTED = (
    "does not exist",
    "syntax error",
    "division by zero",
    "invalid input syntax",
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


def has_transport_or_fatal(body: str) -> bool:
    lower = (body or "").lower()
    return any(token in lower for token in TRANSPORT)


def classify_db_fail_closed(*, psql_rc: int, body: str) -> tuple[str, str]:
    blob = body or ""
    if psql_rc == 0:
        return "POSITIVE_INGEST_WITHOUT_TRUST", "RED"
    if has_transport_or_fatal(blob):
        return "TRANSPORT_OR_FATAL", "RED"
    messages = error_messages(blob)
    if len(messages) > 1:
        return "MULTIPLE_PRIMARY_ERRORS", "RED"
    if psql_rc != TRUST_PSQL_RC:
        return "WRONG_PSQL_RC", "RED"
    primary = messages[0] if messages else None
    if primary == TRUST_SQLSTATE_MESSAGE:
        return "TRUST_FAIL_CLOSED", "CLOSED"
    if primary and primary.lower().startswith("permission denied"):
        return "PERMISSION_DENIED_NOT_TRUST", "RED"
    if primary and any(token in primary.lower() for token in SQL_UNEXPECTED):
        return "UNEXPECTED_SQL_OR_CONNECTION", "RED"
    return "TRUST_DENIAL_UNEXPECTED", "RED"


CLEAN_PG17 = (
    "ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED\n"
    "CONTEXT:  PL/pgSQL function kdb_ops.ingest_source(uuid,uuid,text,text,text,"
    "text,text,text,text,jsonb,text,text,text,text,uuid,timestamp with time zone) "
    "line 21 at RAISE"
)
DETAIL_SPOOF = (
    "ERROR:  KDB_OTHER_FAILURE\n"
    "DETAIL:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
)
CONTEXT_SPOOF = (
    "ERROR:  KDB_OTHER_FAILURE\n"
    "CONTEXT:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED"
)
DUAL_ERROR = (
    "ERROR:  KDB_SECURITY_CONTEXT_NOT_CONFIGURED\n"
    "ERROR:  KDB_OTHER_FAILURE"
)
TRUST_PLUS_TRANSPORT = (
    CLEAN_PG17
    + "\n"
    + 'psql: error: connection to server at "127.0.0.1", port 1 failed: Connection refused'
)
GRANT_STRIP = "ERROR:  permission denied for function ingest_source"

RB02_MATRIX = (
    ("clean_trust_rc3", 3, CLEAN_PG17, "TRUST_FAIL_CLOSED", "CLOSED"),
    ("clean_trust_rc1", 1, CLEAN_PG17, "WRONG_PSQL_RC", "RED"),
    ("clean_trust_rc2", 2, CLEAN_PG17, "WRONG_PSQL_RC", "RED"),
    ("clean_trust_rc_neg15", -15, CLEAN_PG17, "WRONG_PSQL_RC", "RED"),
    ("trust_plus_transport_rc2", 2, TRUST_PLUS_TRANSPORT, "TRANSPORT_OR_FATAL", "RED"),
    ("trust_plus_transport_rc3", 3, TRUST_PLUS_TRANSPORT, "TRANSPORT_OR_FATAL", "RED"),
    ("multiple_primary_errors", 3, DUAL_ERROR, "MULTIPLE_PRIMARY_ERRORS", "RED"),
    ("detail_spoof", 3, DETAIL_SPOOF, "TRUST_DENIAL_UNEXPECTED", "RED"),
    ("context_spoof", 3, CONTEXT_SPOOF, "TRUST_DENIAL_UNEXPECTED", "RED"),
    ("grant_strip", 3, GRANT_STRIP, "PERMISSION_DENIED_NOT_TRUST", "RED"),
)


def evaluate_rb02_matrix() -> list[tuple[str, str, str, str, str]]:
    """Return (label, got_code, got_sev, exp_code, exp_sev) for every cell."""
    rows = []
    for label, rc, body, exp_code, exp_sev in RB02_MATRIX:
        code, sev = classify_db_fail_closed(psql_rc=rc, body=body)
        rows.append((label, code, sev, exp_code, exp_sev))
    return rows
