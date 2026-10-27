"""Ephemeral test proofs for the disabled-by-default SOV consumer.

Signing keys stay in process memory for the test run. They are not a
trust anchor and must not be checked in.
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from digest_v2 import local_digest, o1_fields  # noqa: E402
from ed25519_pure import publickey, signature  # noqa: E402
from sov_proof_consumer import (  # noqa: E402
    ALG,
    OPERATION,
    PROOF_VERSION,
    ExpectedContext,
    ProofPublicMetadata,
    b64url_encode,
    canonical_json,
    kid_from_spki,
    spki_from_raw,
)

NOW = 1_000_000
ACTOR = "10000000-0000-4000-8000-000000000001"
SESSION = "20000000-0000-4000-8000-000000000002"
COMMAND_ID = "00000000-0000-4000-8000-000000000001"
SUBMISSION_ID = "00000000-0000-4000-8000-000000000002"
TENANT = "TENANT_SYNTH_A"
PURPOSE = "kdb_knowledge_intake"
CONTENT = "ab" * 32
RIGHTS = "fc44c824ba88e94bcac1056acea3aaf49eab60585ba167514dc9aeb3276bb0f2"
PRINCIPAL = "PRINCIPAL_REF_SYNTH_PIPELINE"
ACCESS = "ACCESS_SYNTH_OK"
SYNTH_ISSUER = "sov-piac-decision-proof-v1-synthetic"
IDENTITY_ISSUER = "idp-synthetic"
AUDIENCE = "kdb-command"


def o1_ascii_fields() -> list[object]:
    return o1_fields(
        COMMAND_ID,
        TENANT,
        "KDB",
        PURPOSE,
        "LICENSED_DOCUMENT",
        "synthetic://kdb/p5/a",
        CONTENT,
        RIGHTS,
        PRINCIPAL,
        ACCESS,
        "idem-p5",
        SUBMISSION_ID,
    )


def expected_context(**overrides: Any) -> ExpectedContext:
    fields = overrides.pop("command_fields", o1_ascii_fields())
    data = dict(
        audience=AUDIENCE,
        actor_principal_id=ACTOR,
        subject_principal_id=ACTOR,
        subject_ref=ACTOR,
        auth_session_id=SESSION,
        session_revision=4,
        identity_revision=4,
        tenant_id=TENANT,
        scope_code="scope-a",
        purpose_code=PURPOSE,
        resource_type="kdb_source",
        resource_id="kdb-source-1",
        source_version_ref=CONTENT,
        rights_digest=RIGHTS,
        policy_version="policy-v1",
        domain_guard_version="kdb-guard-v1",
        decision_epoch=4,
        identity_epoch=4,
        session_epoch=4,
        identity_issuer=IDENTITY_ISSUER,
        command_id=COMMAND_ID,
        decision_ref=ACCESS,
        caller_workload="kdb-command",
        principal_context_ref=PRINCIPAL,
        correlation_id="corr-synth",
        consent_grant_revision=1,
        entitlement_grant_revision=1,
        tenant_grant_revision=1,
        command_fields=fields,
    )
    data.update(overrides)
    return ExpectedContext(**data)


class EphemeralAuthority:
    def __init__(self, seed: bytes | None = None) -> None:
        self.seed = seed or secrets.token_bytes(32)
        self.raw_pk = publickey(self.seed)
        spki = spki_from_raw(self.raw_pk)
        kid = kid_from_spki(spki)
        self.metadata = ProofPublicMetadata(
            kid=kid,
            algorithm=ALG,
            proof_version=PROOF_VERSION,
            issuer=SYNTH_ISSUER,
            public_key_spki_base64url=b64url_encode(spki),
            rotation="ephemeral-runtime",
        )

    def sign(self, payload_bytes: bytes) -> bytes:
        return signature(payload_bytes, self.seed, self.raw_pk)


def claims(authority: EphemeralAuthority, **overrides: Any) -> dict[str, Any]:
    fields = overrides.get("command_fields", o1_ascii_fields())
    body = {
        "actor_principal_id": ACTOR,
        "aud": AUDIENCE,
        "auth_session_id": SESSION,
        "caller_workload": "kdb-command",
        "command_id": COMMAND_ID,
        "consent_grant_revision": 1,
        "correlation_id": "corr-synth",
        "decision": "ALLOW",
        "decision_ref": ACCESS,
        "decision_revocation_epoch": 4,
        "domain_guard_version": "kdb-guard-v1",
        "entitlement_grant_revision": 1,
        "exp": NOW + 300,
        "external_locator": "synthetic://kdb/p5/a",
        "iat": NOW,
        "identity_issuer": IDENTITY_ISSUER,
        "identity_revision": 4,
        "identity_revocation_epoch": 4,
        "idempotency_key": "idem-p5",
        "iss": authority.metadata.issuer,
        "jti": "jti-synth-1",
        "kid": authority.metadata.kid,
        "nbf": NOW,
        "operation": OPERATION,
        "origin_owner": "KDB",
        "policy_version": "policy-v1",
        "principal_context_ref": PRINCIPAL,
        "proof_version": PROOF_VERSION,
        "purpose_code": PURPOSE,
        "request_sha256": local_digest(fields),
        "resource_id": "kdb-source-1",
        "resource_type": "kdb_source",
        "rights_digest": RIGHTS,
        "scope_code": "scope-a",
        "scope_type": "TENANT",
        "session_revision": 4,
        "session_revocation_epoch": 4,
        "source_class": "LICENSED_DOCUMENT",
        "source_version_ref": CONTENT,
        "subject_principal_id": ACTOR,
        "subject_ref": ACTOR,
        "submission_id": SUBMISSION_ID,
        "tenant_grant_revision": 1,
        "tenant_id": TENANT,
    }
    body.update({k: v for k, v in overrides.items() if k != "command_fields"})
    return body


def envelope(authority: EphemeralAuthority, payload: dict[str, Any] | None = None, **claim_overrides: Any) -> dict[str, Any]:
    payload = payload if payload is not None else claims(authority, **claim_overrides)
    signed = authority.sign(canonical_json(payload).encode("utf-8"))
    return {
        "alg": ALG,
        "kid": authority.metadata.kid,
        "payload": payload,
        "proof_version": PROOF_VERSION,
        "signature": b64url_encode(signed),
    }
