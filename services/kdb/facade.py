"""Private KDB command facade. Not deployed. Rejects every request."""
from piac import FailClosedPiacVerifier, PiacVerificationError

class KdbCommandFacade:
    def __init__(self, verifier=None):
        self.verifier = verifier or FailClosedPiacVerifier()

    def handle(self, envelope: dict) -> dict:
        self.verifier.verify(envelope)
        raise RuntimeError("PIAC_ACCEPT_PATH_MUST_REMAIN_UNREACHABLE")
