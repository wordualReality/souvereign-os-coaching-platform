"""Offline SOV PIAC proof consumer negatives. No DB admission. No secrets logged."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "services" / "kdb"))
from digest_v2 import local_digest  # noqa: E402
from ed25519_pure import publickey, signature, verify  # noqa: E402
from facade import KdbCommandFacade  # noqa: E402
from piac import PiacVerificationError  # noqa: E402
from sov_proof_consumer import (  # noqa: E402
    COMMAND_CLAIM_BINDINGS,
    CONSUMER_DISABLED,
    DB_NOT_ADMITTED,
    LOCAL_VERIFIED,
    MAX_CHARS,
    MAX_NESTING,
    NEEDS_SOV_SECURITY_QS,
    OBSERVED_PRODUCER_SHA_NOT_ADOPTED,
    PIN_SHA,
    PAYLOAD_KEYS,
    ProofPublicMetadata,
    SovProofConsumer,
    SovProofError,
    activation_flag,
    canonical_json,
    consumer_enabled_by_flags,
)
from sov_proof_fixtures import (  # noqa: E402
    CONTENT,
    NOW,
    TENANT,
    EphemeralAuthority,
    claims,
    envelope,
    expected_context,
    o1_ascii_fields,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
PIN = ROOT / "contracts" / "kdb" / "piac-decision-proof" / "v1-pin-f68760d"


class Ed25519PureTests(unittest.TestCase):
    def test_rfc8032_empty_message(self):
        sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        pk = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = bytes.fromhex(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
        )
        self.assertEqual(publickey(sk), pk)
        self.assertEqual(signature(b"", sk, pk), sig)
        self.assertTrue(verify(sig, b"", pk))
        self.assertFalse(verify(sig, b"x", pk))


class PinContractTests(unittest.TestCase):
    def test_pin_sha_and_sidecar_hashes(self):
        pin = json.loads((PIN / "PIN.json").read_text())
        self.assertEqual(pin["producer_sha"], PIN_SHA)
        self.assertFalse(pin["normative_adoption"])
        self.assertEqual(pin["security_admission"], NEEDS_SOV_SECURITY_QS)
        self.assertEqual(pin["observed_producer_sha_not_adopted"], OBSERVED_PRODUCER_SHA_NOT_ADOPTED)
        self.assertEqual(pin["observed_artifact_blobs_identical"], 8)
        self.assertFalse(pin["pin_advanced"])
        pairs = (
            ("proof-envelope.schema.json", "proof-envelope.schema.sha256"),
            ("public-metadata.schema.json", "public-metadata.schema.sha256"),
            ("negative-vectors.json", "negative-vectors.sha256"),
            ("kdb-sql-v2-golden.json", "kdb-sql-v2-golden.sha256"),
        )
        for src, side in pairs:
            got = hashlib.sha256((PIN / src).read_bytes()).hexdigest()
            want = (PIN / side).read_text().strip().split()[0]
            self.assertEqual(got, want, src)

    def test_pinned_golden_matches_kdb_fixture(self):
        pinned = json.loads((PIN / "kdb-sql-v2-golden.json").read_text())
        local = json.loads((ROOT / "tests" / "kdb" / "fixtures" / "p5_sql_v2_golden.json").read_text())
        self.assertEqual(pinned["cases"], local["cases"])
        self.assertEqual(local_digest(o1_ascii_fields()), pinned["cases"][0]["digest"])

    def test_envelope_requires_full_claim_set(self):
        schema = json.loads((PIN / "proof-envelope.schema.json").read_text())
        self.assertEqual(set(schema["payload_required"]), PAYLOAD_KEYS)
        self.assertEqual(schema["operation_const"], "KDB_SOURCE_INTAKE")
        self.assertEqual(schema["max_ttl_seconds"], 300)

    def test_negative_vector_codes_are_named(self):
        vectors = json.loads((PIN / "negative-vectors.json").read_text())
        codes = {row["code"] for row in vectors["cases"]}
        self.assertEqual(
            codes,
            {
                "DENIED",
                "REVOKED",
                "STALE",
                "PRECONDITION_FAILED",
                "SIGNATURE_INVALID",
                "CLAIM_MISMATCH",
                "UNKNOWN_KEY",
                "UNKNOWN_SCHEMA",
                "AUTHORITY_NOT_CONFIGURED",
                "DIGEST_MISMATCH",
                "AUDIENCE_MISMATCH",
                "EXPIRED",
                "NOT_YET_VALID",
                "REPLAY",
                "DIGEST_CONTRACT_UNRESOLVED",
            },
        )


class ConsumerOfflineTests(unittest.TestCase):
    def setUp(self):
        self.authority = EphemeralAuthority()
        self.replay = set()
        self.consumer = SovProofConsumer(
            enabled=True,
            trust={self.authority.metadata.kid: self.authority.metadata},
            replay_store=self.replay,
            now=lambda: NOW,
        )

    def _raise(self, env, expected, code):
        with self.assertRaises(SovProofError) as ctx:
            self.consumer.evaluate(env, expected)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_flag_disabled_by_default(self):
        self.assertEqual(activation_flag(), "DISABLED_CONTRACT_ONLY")
        self.assertFalse(consumer_enabled_by_flags())
        closed = SovProofConsumer(
            enabled=False,
            trust={self.authority.metadata.kid: self.authority.metadata},
            replay_store=set(),
            now=lambda: NOW,
        )
        with self.assertRaises(SovProofError) as ctx:
            closed.evaluate(envelope(self.authority), expected_context())
        self.assertEqual(ctx.exception.code, CONSUMER_DISABLED)

    def test_empty_trust_is_authority_not_configured(self):
        bare = SovProofConsumer(enabled=True, trust={}, replay_store=set(), now=lambda: NOW)
        with self.assertRaises(SovProofError) as ctx:
            bare.evaluate(envelope(self.authority), expected_context())
        self.assertEqual(ctx.exception.code, "AUTHORITY_NOT_CONFIGURED")

    def test_synthetic_good_proof_is_local_only(self):
        verdict = self.consumer.evaluate(envelope(self.authority), expected_context())
        self.assertEqual(verdict["verdict"], LOCAL_VERIFIED)
        self.assertEqual(verdict["db_command"], DB_NOT_ADMITTED)
        self.assertFalse(verdict["db_command_admitted"])
        self.assertTrue(verdict["needs_sov_security_qs"])
        self.assertEqual(verdict["dependency"], NEEDS_SOV_SECURITY_QS)
        self.assertEqual(verdict["pin_sha"], PIN_SHA)

    def test_replay_jti(self):
        env = envelope(self.authority)
        self.consumer.evaluate(env, expected_context())
        self._raise(env, expected_context(), "REPLAY")

    def test_signature_invalid(self):
        env = envelope(self.authority)
        env["signature"] = "A" * 86
        self._raise(env, expected_context(), "SIGNATURE_INVALID")

    def test_unknown_kid(self):
        other = EphemeralAuthority()
        env = envelope(other)
        self._raise(env, expected_context(), "UNKNOWN_KEY")

    def test_unknown_schema_version(self):
        env = envelope(self.authority)
        env["proof_version"] = "PIAC_DECISION_PROOF_V0"
        self._raise(env, expected_context(), "UNKNOWN_SCHEMA")

    def test_ct_shc_operation_denied(self):
        env = envelope(self.authority, operation="ACTOR_IDENTITY")
        self._raise(env, expected_context(), "DENIED")

    def test_non_allow_denied(self):
        env = envelope(self.authority, decision="DENY")
        self._raise(env, expected_context(), "DENIED")

    def test_audience_mismatch(self):
        env = envelope(self.authority, aud="other-audience")
        self._raise(env, expected_context(), "AUDIENCE_MISMATCH")

    def test_tenant_mismatch(self):
        env = envelope(self.authority)
        expected = expected_context(tenant_id="TENANT_SYNTH_B")
        self._raise(env, expected, "CLAIM_MISMATCH")

    def test_subject_mismatch(self):
        other = "30000000-0000-4000-8000-000000000003"
        env = envelope(self.authority)
        expected = expected_context(subject_principal_id=other, subject_ref=other)
        self._raise(env, expected, "CLAIM_MISMATCH")

    def test_session_mismatch(self):
        env = envelope(self.authority)
        expected = expected_context(auth_session_id="20000000-0000-4000-8000-000000000099")
        self._raise(env, expected, "CLAIM_MISMATCH")

    def test_purpose_mismatch(self):
        env = envelope(self.authority)
        expected = expected_context(purpose_code="other-purpose")
        self._raise(env, expected, "CLAIM_MISMATCH")

    def test_identity_issuer_collision(self):
        env = envelope(self.authority, identity_issuer=self.authority.metadata.issuer)
        expected = expected_context(identity_issuer=self.authority.metadata.issuer)
        self._raise(env, expected, "CLAIM_MISMATCH")

    def test_revoked_epoch(self):
        env = envelope(self.authority)
        expected = expected_context(decision_epoch=5)
        self._raise(env, expected, "REVOKED")

    def test_expired(self):
        late = SovProofConsumer(
            enabled=True,
            trust={self.authority.metadata.kid: self.authority.metadata},
            replay_store=set(),
            now=lambda: NOW + 301,
        )
        with self.assertRaises(SovProofError) as ctx:
            late.evaluate(envelope(self.authority), expected_context())
        self.assertEqual(ctx.exception.code, "EXPIRED")

    def test_not_yet_valid(self):
        env = envelope(self.authority, nbf=NOW + 10, iat=NOW + 10, exp=NOW + 310)
        self._raise(env, expected_context(), "NOT_YET_VALID")

    def test_stale_ttl(self):
        env = envelope(self.authority, exp=NOW + 301)
        self._raise(env, expected_context(), "STALE")

    def test_digest_mismatch(self):
        env = envelope(self.authority, request_sha256="00" * 32)
        self._raise(env, expected_context(), "DIGEST_MISMATCH")

    def test_digest_bound_to_command_fields(self):
        original = local_digest(o1_ascii_fields())
        fields = list(o1_ascii_fields())
        fields[3] = "TENANT_SYNTH_B"
        env = envelope(self.authority, tenant_id="TENANT_SYNTH_B", request_sha256=original)
        expected = expected_context(command_fields=fields, tenant_id="TENANT_SYNTH_B")
        self._raise(env, expected, "DIGEST_MISMATCH")

    def test_digest_contract_unresolved(self):
        fields = list(o1_ascii_fields())
        fields[7] = True
        env = envelope(self.authority)
        expected = expected_context(command_fields=fields)
        self._raise(env, expected, "DIGEST_CONTRACT_UNRESOLVED")

    def test_missing_expected_context(self):
        with self.assertRaises(SovProofError) as ctx:
            self.consumer.evaluate(envelope(self.authority), None)
        self.assertEqual(ctx.exception.code, "PRECONDITION_FAILED")

    def test_missing_payload_claim(self):
        payload = claims(self.authority)
        del payload["jti"]
        env = envelope(self.authority, payload=payload)
        self._raise(env, expected_context(), "CLAIM_MISMATCH")

    def test_json_string_envelope(self):
        env = envelope(self.authority)
        verdict = self.consumer.evaluate(json.dumps(env, separators=(",", ":"), sort_keys=True), expected_context())
        self.assertEqual(verdict["verdict"], LOCAL_VERIFIED)
        self.assertFalse(verdict["db_command_admitted"])

    def test_facade_still_fail_closed_with_proof(self):
        env = envelope(self.authority)
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle({"piac_decision_proof": env, "access_decision_ref": "SYNTHETIC_ALLOW"})

    def test_consumer_not_wired_into_facade(self):
        facade = (ROOT / "services" / "kdb" / "facade.py").read_text()
        self.assertNotIn("sov_proof_consumer", facade)
        self.assertNotIn("DB_COMMAND_ADMITTED", facade)

    def test_each_signed_claim_binds_presented_command_field(self):
        for index, claim, reason in COMMAND_CLAIM_BINDINGS:
            with self.subTest(claim=claim):
                fields = list(o1_ascii_fields())
                fields[index] = "mutated-" + claim
                payload = claims(self.authority, request_sha256=local_digest(fields))
                env = envelope(self.authority, payload=payload)
                expected = expected_context(command_fields=fields)
                exc = self._raise(env, expected, "CLAIM_MISMATCH")
                self.assertEqual(exc.reason, reason)

    def test_trust_dict_key_must_match_metadata_kid(self):
        meta = self.authority.metadata
        with self.assertRaises(SovProofError) as ctx:
            SovProofConsumer(
                enabled=True,
                trust={"wrong-kid": meta},
                replay_store=set(),
                now=lambda: NOW,
            )
        self.assertEqual(ctx.exception.code, "UNKNOWN_KEY")

    def test_trust_algorithm_must_be_ed25519(self):
        meta = self.authority.metadata
        bad = ProofPublicMetadata(
            kid=meta.kid,
            algorithm="HMAC-SHA256",
            proof_version=meta.proof_version,
            issuer=meta.issuer,
            public_key_spki_base64url=meta.public_key_spki_base64url,
            rotation=meta.rotation,
        )
        with self.assertRaises(SovProofError) as ctx:
            SovProofConsumer(
                enabled=True,
                trust={meta.kid: bad},
                replay_store=set(),
                now=lambda: NOW,
            )
        self.assertEqual(ctx.exception.code, "UNKNOWN_KEY")

    def test_trust_kid_must_derive_from_spki(self):
        meta = self.authority.metadata
        other = EphemeralAuthority()
        spoofed = ProofPublicMetadata(
            kid=meta.kid,
            algorithm=meta.algorithm,
            proof_version=meta.proof_version,
            issuer=meta.issuer,
            public_key_spki_base64url=other.metadata.public_key_spki_base64url,
            rotation=meta.rotation,
        )
        with self.assertRaises(SovProofError) as ctx:
            SovProofConsumer(
                enabled=True,
                trust={meta.kid: spoofed},
                replay_store=set(),
                now=lambda: NOW,
            )
        self.assertEqual(ctx.exception.code, "UNKNOWN_KEY")

    def test_concurrent_same_jti_one_replay(self):
        env = envelope(self.authority)
        expected = expected_context()
        shared: set[str] = set()
        results: list[str] = []
        barrier = threading.Barrier(2)

        def run() -> None:
            consumer = SovProofConsumer(
                enabled=True,
                trust={self.authority.metadata.kid: self.authority.metadata},
                replay_store=shared,
                now=lambda: NOW,
            )
            barrier.wait()
            try:
                verdict = consumer.evaluate(env, expected)
                results.append(str(verdict["verdict"]))
            except SovProofError as exc:
                results.append(exc.code)

        workers = [threading.Thread(target=run), threading.Thread(target=run)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sorted(results), sorted([LOCAL_VERIFIED, "REPLAY"]))

    def test_lone_surrogate_is_unknown_schema(self):
        with self.assertRaises(SovProofError) as ctx:
            canonical_json({"k": "\ud800"})
        self.assertEqual(ctx.exception.code, "UNKNOWN_SCHEMA")

    def test_envelope_too_large(self):
        blob = "{" + ("a" * (MAX_CHARS + 1)) + "}"
        with self.assertRaises(SovProofError) as ctx:
            self.consumer.evaluate(blob, expected_context())
        self.assertEqual(ctx.exception.code, "UNKNOWN_SCHEMA")

    def test_envelope_too_deep(self):
        nested: object = []
        for _ in range(MAX_NESTING):
            nested = [nested]
        env = {
            "alg": "Ed25519",
            "kid": "x",
            "payload": nested,
            "proof_version": "PIAC_DECISION_PROOF_V1",
            "signature": "x",
        }
        with self.assertRaises(SovProofError) as ctx:
            self.consumer.evaluate(json.dumps(env), expected_context())
        self.assertEqual(ctx.exception.code, "UNKNOWN_SCHEMA")


if __name__ == "__main__":
    unittest.main()
