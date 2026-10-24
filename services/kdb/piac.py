"""Fail-closed PIAC verifier. No issuer, JWKS, or secret is configured here."""

class PiacVerificationError(Exception):
    """Every request is rejected until an independently admitted verifier exists."""


class FailClosedPiacVerifier:
    def verify(self, envelope: dict) -> None:
        # access_decision_ref and principal_context_ref are correlations, not proof.
        raise PiacVerificationError("PIAC_NOT_CONFIGURED_FAIL_CLOSED")
