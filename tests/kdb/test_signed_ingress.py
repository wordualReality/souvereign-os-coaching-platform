"""Synthetic signed-ingress negatives. No private key is stored. No tokens logged."""
import secrets
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from signed_ingress import (  # noqa: E402
    REVOCATION_UNAVAILABLE,
    SignedIngressError,
    SignedIngressVerifier,
    mac_hex,
)


def _now() -> int:
    return 1_000_000


def _claims(**overrides):
    base = {
        "iss": "kdb-synth-issuer",
        "aud": "kdb-local-ingress",
        "kid": "kid-1",
        "jti": "jti-1",
        "nbf": 999_000,
        "exp": 1_100_000,
        "principal": "PRINCIPAL_REF_SYNTH_PIPELINE",
        "tenant": "TENANT_SYNTH_A",
        "purpose": "kdb_knowledge_intake",
        "command_id": "00000000-0000-4000-8000-0000000000aa",
        "request_digest": "a" * 64,
        "nonce": "nonce-1",
    }
    base.update(overrides)
    return base


class SignedIngressTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)
        self.replay = set()
        self.revoked = set()
        self.verifier = SignedIngressVerifier(
            keys={"kid-1": self.key},
            issuer="kdb-synth-issuer",
            audience="kdb-local-ingress",
            replay_store=self.replay,
            revocation_store=self.revoked,
            now=_now,
        )

    def _ok(self, **overrides):
        claims = _claims(**overrides)
        return {"claims": claims, "mac": mac_hex(self.key, claims)}

    def test_valid_synthetic_is_local_only(self):
        verdict = self.verifier.verify(self._ok())
        self.assertEqual(verdict["verdict"], "LOCAL_SIGNED_INGRESS_VERIFIED")

    def test_revocation_registry_required(self):
        bare = SignedIngressVerifier(
            keys={"kid-1": self.key},
            issuer="kdb-synth-issuer",
            audience="kdb-local-ingress",
            replay_store=set(),
            revocation_store=None,
            now=_now,
        )
        with self.assertRaises(SignedIngressError) as ctx:
            bare.verify(self._ok())
        self.assertEqual(ctx.exception.code, REVOCATION_UNAVAILABLE)

    def test_bad_signature(self):
        env = self._ok()
        env["mac"] = "00" * 32
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_BAD_SIGNATURE")

    def test_unknown_issuer(self):
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok(iss="other"))
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_UNKNOWN_ISSUER")

    def test_wrong_audience(self):
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok(aud="prod"))
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_WRONG_AUDIENCE")

    def test_unknown_key(self):
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok(kid="kid-missing"))
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_UNKNOWN_KEY")

    def test_expired_and_future(self):
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok(exp=1))
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_EXPIRED")
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok(nbf=2_000_000))
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_NOT_YET_VALID")

    def test_replay(self):
        env = self._ok()
        self.verifier.verify(env)
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_REPLAY")

    def test_revoked_kid(self):
        self.revoked.add("kid-1")
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(self._ok())
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_REVOKED")

    def test_missing_claim(self):
        claims = _claims()
        del claims["purpose"]
        env = {"claims": claims, "mac": mac_hex(self.key, claims)}
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MISSING_CLAIM")

    def test_access_decision_ref_is_not_auth(self):
        env = self._ok()
        env["claims"]["access_decision_ref"] = "SYNTHETIC_ALLOW"
        env["mac"] = mac_hex(self.key, env["claims"])
        verdict = self.verifier.verify(env)
        self.assertEqual(verdict["verdict"], "LOCAL_SIGNED_INGRESS_VERIFIED")

    def test_list_kid_is_typed_fail_closed(self):
        env = self._ok(kid=["kid-1"])
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MALFORMED")

    def test_dict_kid_is_typed_fail_closed(self):
        env = self._ok(kid={"kid": "kid-1"})
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MALFORMED")

    def test_unicode_mac_is_typed_fail_closed(self):
        env = self._ok()
        env["mac"] = "ü" * 32
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MALFORMED")

    def test_non_string_mac_is_typed_fail_closed(self):
        env = self._ok()
        env["mac"] = {"hex": "00"}
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MALFORMED")

    def test_missing_mac_is_typed_fail_closed(self):
        env = self._ok()
        del env["mac"]
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_MALFORMED")

    def test_wrong_length_mac_is_bad_signature(self):
        env = self._ok()
        env["mac"] = "00"
        with self.assertRaises(SignedIngressError) as ctx:
            self.verifier.verify(env)
        self.assertEqual(ctx.exception.code, "SIGNED_INGRESS_BAD_SIGNATURE")


if __name__ == "__main__":
    unittest.main()
