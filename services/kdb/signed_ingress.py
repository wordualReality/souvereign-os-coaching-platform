"""Test-only synthetic signed ingress. Not a PIAC issuer and not DB trust.

Ephemeral HMAC keys stay in process memory. Default production PIAC remains
fail-closed. A valid synthetic MAC is LOCAL_SIGNED_INGRESS_VERIFIED only.
It is never DB_COMMAND_ADMITTED. access_decision_ref is not authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Set
from typing import Any

LOCAL_VERIFIED = "LOCAL_SIGNED_INGRESS_VERIFIED"
DB_NOT_ADMITTED = "DB_COMMAND_NOT_ADMITTED"
REVOCATION_UNAVAILABLE = "REVOCATION_PROOF_UNAVAILABLE"


class SignedIngressError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_claims(claims: dict[str, Any]) -> bytes:
    return json.dumps(claims, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def mac_hex(key: bytes, claims: dict[str, Any]) -> str:
    return hmac.new(key, _canonical_claims(claims), hashlib.sha256).hexdigest()


class SignedIngressVerifier:
    """Isolated verifier. Requires an explicit revocation registry."""

    required = (
        "iss",
        "aud",
        "kid",
        "jti",
        "nbf",
        "exp",
        "principal",
        "tenant",
        "purpose",
        "command_id",
        "request_digest",
        "nonce",
    )

    def __init__(
        self,
        *,
        keys: dict[str, bytes],
        issuer: str,
        audience: str,
        replay_store: set[str],
        revocation_store: Set[str] | None,
        now: Callable[[], int],
    ) -> None:
        self.keys = keys
        self.issuer = issuer
        self.audience = audience
        self.replay_store = replay_store
        self.revocation_store = revocation_store
        self.now = now

    def verify(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if self.revocation_store is None:
            raise SignedIngressError(REVOCATION_UNAVAILABLE)
        claims = envelope.get("claims")
        presented = envelope.get("mac")
        if not isinstance(claims, dict) or not isinstance(presented, str):
            raise SignedIngressError("SIGNED_INGRESS_MALFORMED")
        for field in self.required:
            if field not in claims or claims[field] in (None, ""):
                raise SignedIngressError("SIGNED_INGRESS_MISSING_CLAIM")
        if claims.get("iss") != self.issuer:
            raise SignedIngressError("SIGNED_INGRESS_UNKNOWN_ISSUER")
        if claims.get("aud") != self.audience:
            raise SignedIngressError("SIGNED_INGRESS_WRONG_AUDIENCE")
        kid = claims["kid"]
        if kid in self.revocation_store:
            raise SignedIngressError("SIGNED_INGRESS_REVOKED")
        key = self.keys.get(kid)
        if key is None:
            raise SignedIngressError("SIGNED_INGRESS_UNKNOWN_KEY")
        expected = mac_hex(key, claims)
        if not hmac.compare_digest(expected, presented):
            raise SignedIngressError("SIGNED_INGRESS_BAD_SIGNATURE")
        now = self.now()
        if int(claims["nbf"]) > now:
            raise SignedIngressError("SIGNED_INGRESS_NOT_YET_VALID")
        if int(claims["exp"]) <= now:
            raise SignedIngressError("SIGNED_INGRESS_EXPIRED")
        jti = str(claims["jti"])
        if jti in self.replay_store:
            raise SignedIngressError("SIGNED_INGRESS_REPLAY")
        self.replay_store.add(jti)
        return {"verdict": LOCAL_VERIFIED, "command_id": claims["command_id"], "tenant": claims["tenant"]}


class SignedIngressPipeline:
    def __init__(self, verifier: SignedIngressVerifier) -> None:
        self.verifier = verifier

    def evaluate(
        self,
        *,
        envelope: dict[str, Any],
        signed: dict[str, Any],
        expected_digest: str,
        db_attempt: Callable[[], str],
    ) -> dict[str, str]:
        claims = signed.get("claims") or {}
        if claims.get("tenant") != envelope.get("tenant"):
            raise SignedIngressError("SIGNED_INGRESS_MIXED_TENANT")
        if claims.get("purpose") != envelope.get("purpose"):
            raise SignedIngressError("SIGNED_INGRESS_WRONG_PURPOSE")
        if claims.get("command_id") != envelope.get("command_id"):
            raise SignedIngressError("SIGNED_INGRESS_COMMAND_MISMATCH")
        if claims.get("request_digest") != expected_digest:
            raise SignedIngressError("SIGNED_INGRESS_DIGEST_MISMATCH")
        if envelope.get("access_decision_ref"):
            # correlation only; ignored as authentication
            pass
        local = self.verifier.verify(signed)
        db_blob = db_attempt()
        if "RECORDED" in db_blob.replace(" ", ""):
            raise SignedIngressError("DB_COMMAND_ADMITTED")
        return {
            "local_signed_ingress": local["verdict"],
            "db_command": DB_NOT_ADMITTED,
            "db_denial": db_blob.split("\n", 1)[0][:200],
        }
