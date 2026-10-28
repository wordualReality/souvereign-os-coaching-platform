"""Private KDB command facade. Not deployed. Rejects every request."""
from piac import FailClosedPiacVerifier
from tenant_scope import require_tenant_scope


class KdbCommandFacade:
    def __init__(self, verifier=None):
        self.verifier = verifier or FailClosedPiacVerifier()

    def handle(self, envelope: dict) -> dict:
        payload = envelope if isinstance(envelope, dict) else {}
        require_tenant_scope(payload.get("tenant_scope"))
        self.verifier.verify(envelope)
        raise RuntimeError("PIAC_ACCEPT_PATH_MUST_REMAIN_UNREACHABLE")

