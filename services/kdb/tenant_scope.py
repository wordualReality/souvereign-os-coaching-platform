"""Fail-closed tenant_scope bound to O1/O2/O3 contracts.

The inactive n8n Fail Closed Classify candidate requires a string whose
trimmed form is nonempty and whose raw length is at most 128. Whitespace-only
values are denied even though JSON Schema minLength 1 would accept them.
Envelope tenant_scope is not a GUC and is not PIAC proof.
"""


class TenantScopeError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


MAX_LEN = 128


def require_tenant_scope(value, expected: str | None = None) -> str:
    if not isinstance(value, str) or value.strip() == "" or len(value) > MAX_LEN:
        raise TenantScopeError("TENANT_SCOPE_DENIED")
    if expected is not None and value != expected:
        raise TenantScopeError("TENANT_SCOPE_MISMATCH")
    return value
