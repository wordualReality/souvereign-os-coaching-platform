"""Versioned SOV PIAC_DECISION_PROOF_V1 consumer. Disabled by default.

Pinned producer SHA f68760d is CONTRACT ONLY. The adapter never admits a
live issuer and never yields DB_COMMAND_ADMITTED. NEEDS_SOV_SECURITY_QS
remains named. This module does not GRANT SQL EXECUTE.
"""
from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from digest_v2 import DigestContractError, local_digest
from ed25519_pure import verify as ed25519_verify

PROOF_VERSION = "PIAC_DECISION_PROOF_V1"
ALG = "Ed25519"
OPERATION = "KDB_SOURCE_INTAKE"
DECISION_ALLOW = "ALLOW"
MAX_TTL_SECONDS = 300
COMMAND_FIELDS = 14
LOCAL_VERIFIED = "LOCAL_VERIFIED_ONLY"
DB_NOT_ADMITTED = "DB_COMMAND_NOT_ADMITTED"
CONSUMER_DISABLED = "CONSUMER_DISABLED"
NEEDS_SOV_SECURITY_QS = "NEEDS_SOV_SECURITY_QS"
PIN_SHA = "f68760d799831ff260f99eb5b02358a1a3bda979"
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")

PAYLOAD_KEYS = frozenset(
    {
        "actor_principal_id",
        "aud",
        "auth_session_id",
        "caller_workload",
        "command_id",
        "consent_grant_revision",
        "correlation_id",
        "decision",
        "decision_ref",
        "decision_revocation_epoch",
        "domain_guard_version",
        "entitlement_grant_revision",
        "exp",
        "external_locator",
        "iat",
        "identity_issuer",
        "identity_revision",
        "identity_revocation_epoch",
        "idempotency_key",
        "iss",
        "jti",
        "kid",
        "nbf",
        "operation",
        "origin_owner",
        "policy_version",
        "principal_context_ref",
        "proof_version",
        "purpose_code",
        "request_sha256",
        "resource_id",
        "resource_type",
        "rights_digest",
        "scope_code",
        "scope_type",
        "session_revision",
        "session_revocation_epoch",
        "source_class",
        "source_version_ref",
        "subject_principal_id",
        "subject_ref",
        "submission_id",
        "tenant_grant_revision",
        "tenant_id",
    }
)
LONG_KEYS = frozenset(
    {
        "consent_grant_revision",
        "decision_revocation_epoch",
        "entitlement_grant_revision",
        "exp",
        "iat",
        "identity_revision",
        "identity_revocation_epoch",
        "nbf",
        "session_revision",
        "session_revocation_epoch",
        "tenant_grant_revision",
    }
)
ENVELOPE_KEYS = ("alg", "kid", "payload", "proof_version", "signature")


class SovProofError(Exception):
    def __init__(self, code: str, reason: str = "") -> None:
        self.code = code
        self.reason = reason
        super().__init__(code if not reason else f"{code}:{reason}")


@dataclass(frozen=True)
class ProofPublicMetadata:
    kid: str
    algorithm: str
    proof_version: str
    issuer: str
    public_key_spki_base64url: str
    rotation: str


@dataclass(frozen=True)
class ExpectedContext:
    audience: str
    actor_principal_id: str
    subject_principal_id: str
    subject_ref: str
    auth_session_id: str
    session_revision: int
    identity_revision: int
    tenant_id: str
    scope_code: str
    purpose_code: str
    resource_type: str
    resource_id: str
    source_version_ref: str
    rights_digest: str
    policy_version: str
    domain_guard_version: str
    decision_epoch: int
    identity_epoch: int
    session_epoch: int
    identity_issuer: str
    command_id: str
    decision_ref: str
    caller_workload: str
    principal_context_ref: str
    correlation_id: str
    consent_grant_revision: int
    entitlement_grant_revision: int
    tenant_grant_revision: int
    command_fields: Sequence[object]


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    if not isinstance(text, str):
        raise ValueError("base64url text required")
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + pad)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def spki_from_raw(raw_pk: bytes) -> bytes:
    if len(raw_pk) != 32:
        raise SovProofError("UNKNOWN_KEY", "SPKI")
    return ED25519_SPKI_PREFIX + raw_pk


def kid_from_spki(spki: bytes) -> str:
    return "k-" + hashlib.sha256(spki).hexdigest()[:16]


def raw_pk_from_spki(spki: bytes) -> bytes:
    if len(spki) != 44 or not spki.startswith(ED25519_SPKI_PREFIX):
        raise SovProofError("UNKNOWN_KEY", "SPKI")
    return spki[12:]


def activation_flag(path: Path | None = None) -> str:
    root = Path(__file__).resolve().parents[2]
    flag_path = path or (root / "contracts" / "kdb" / "activation_flags.json")
    data = json.loads(flag_path.read_text())
    return str(data.get("sov_piac_proof_consumer_v1", "DISABLED_CONTRACT_ONLY"))


def consumer_enabled_by_flags(path: Path | None = None) -> bool:
    return activation_flag(path) == "ENABLED"


class SovProofConsumer:
    """Fail-closed consumer. Default construction stays disabled."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        trust: Mapping[str, ProofPublicMetadata] | None = None,
        replay_store: set[str] | None = None,
        now: Callable[[], int] | None = None,
    ) -> None:
        self.enabled = enabled
        self.trust = dict(trust or {})
        self.replay_store = replay_store if replay_store is not None else set()
        self.now = now or (lambda: 0)

    def evaluate(self, envelope: object, expected: ExpectedContext | None) -> dict[str, Any]:
        if not self.enabled:
            raise SovProofError(CONSUMER_DISABLED, "DEFAULT_DISABLED")
        if not self.trust:
            raise SovProofError("AUTHORITY_NOT_CONFIGURED", "TRUST_SET")
        if expected is None:
            raise SovProofError("PRECONDITION_FAILED", "EXPECTED_CONTEXT")
        parsed = self._read_envelope(envelope)
        self._verify_schema(parsed)
        kid = _text(parsed, "kid")
        metadata = self.trust.get(kid)
        if metadata is None or metadata.proof_version != PROOF_VERSION:
            raise SovProofError("UNKNOWN_KEY", "KID")
        payload = parsed.get("payload")
        if not isinstance(payload, dict):
            raise SovProofError("UNKNOWN_SCHEMA", "payload")
        try:
            signature = b64url_decode(_text(parsed, "signature"))
        except Exception as exc:
            raise SovProofError("SIGNATURE_INVALID", "SIGNATURE_ENCODING") from exc
        canonical = canonical_json(payload).encode("utf-8")
        try:
            spki = b64url_decode(metadata.public_key_spki_base64url)
        except Exception as exc:
            raise SovProofError("UNKNOWN_KEY", "SPKI") from exc
        raw_pk = raw_pk_from_spki(spki)
        if not ed25519_verify(signature, canonical, raw_pk):
            raise SovProofError("SIGNATURE_INVALID", "SIGNATURE")
        self._verify_claims(payload, metadata, kid, expected)
        return {
            "verdict": LOCAL_VERIFIED,
            "db_command": DB_NOT_ADMITTED,
            "db_command_admitted": False,
            "needs_sov_security_qs": True,
            "dependency": NEEDS_SOV_SECURITY_QS,
            "pin_sha": PIN_SHA,
            "command_id": _text(payload, "command_id"),
            "tenant_id": _text(payload, "tenant_id"),
        }

    def _read_envelope(self, envelope: object) -> dict[str, Any]:
        if isinstance(envelope, str):
            try:
                envelope = json.loads(envelope)
            except json.JSONDecodeError as exc:
                raise SovProofError("UNKNOWN_SCHEMA", "ENVELOPE") from exc
        if not isinstance(envelope, dict):
            raise SovProofError("UNKNOWN_SCHEMA", "envelope")
        return envelope

    def _verify_schema(self, envelope: dict[str, Any]) -> None:
        for key in ENVELOPE_KEYS:
            if key not in envelope:
                raise SovProofError("UNKNOWN_SCHEMA", key)
        if envelope.get("proof_version") != PROOF_VERSION:
            raise SovProofError("UNKNOWN_SCHEMA", "PROOF_VERSION")
        if envelope.get("alg") != ALG:
            raise SovProofError("UNKNOWN_SCHEMA", "ALG")

    def _verify_claims(
        self,
        payload: dict[str, Any],
        metadata: ProofPublicMetadata,
        kid: str,
        expected: ExpectedContext,
    ) -> None:
        if set(payload.keys()) != PAYLOAD_KEYS:
            raise SovProofError("CLAIM_MISMATCH", "CLAIM_SET")
        if _text(payload, "proof_version") != PROOF_VERSION:
            raise SovProofError("UNKNOWN_SCHEMA", "PAYLOAD_VERSION")
        if _text(payload, "kid") != kid or _text(payload, "iss") != metadata.issuer:
            raise SovProofError("CLAIM_MISMATCH", "ISSUER_KEY")
        if _text(payload, "iss") == _text(payload, "identity_issuer"):
            raise SovProofError("CLAIM_MISMATCH", "ISSUER_NOT_DISTINCT")
        if _text(payload, "decision") != DECISION_ALLOW:
            raise SovProofError("DENIED", "DECISION_NOT_ALLOW")
        if _text(payload, "operation") != OPERATION:
            raise SovProofError("DENIED", "OPERATION")
        if _text(payload, "aud") != expected.audience:
            raise SovProofError("AUDIENCE_MISMATCH", "AUD")
        _require(payload, "actor_principal_id", expected.actor_principal_id, "ACTOR")
        _require(payload, "subject_principal_id", expected.subject_principal_id, "SUBJECT")
        _require(payload, "subject_ref", expected.subject_ref, "SUBJECT_REF")
        _require(payload, "auth_session_id", expected.auth_session_id, "SESSION")
        _require_long(payload, "session_revision", expected.session_revision, "CLAIM_MISMATCH", "SESSION_REVISION")
        _require_long(payload, "identity_revision", expected.identity_revision, "CLAIM_MISMATCH", "IDENTITY_REVISION")
        _require(payload, "caller_workload", expected.caller_workload, "CALLER")
        _require(payload, "principal_context_ref", expected.principal_context_ref, "PRINCIPAL_CONTEXT")
        _require(payload, "correlation_id", expected.correlation_id, "CORRELATION")
        _require_long(payload, "consent_grant_revision", expected.consent_grant_revision, "CLAIM_MISMATCH", "CONSENT_GRANT")
        _require_long(
            payload,
            "entitlement_grant_revision",
            expected.entitlement_grant_revision,
            "CLAIM_MISMATCH",
            "ENTITLEMENT_GRANT",
        )
        _require_long(payload, "tenant_grant_revision", expected.tenant_grant_revision, "CLAIM_MISMATCH", "TENANT_GRANT")
        _require(payload, "tenant_id", expected.tenant_id, "TENANT")
        _require(payload, "scope_code", expected.scope_code, "SCOPE")
        _require(payload, "scope_type", "TENANT", "SCOPE_TYPE")
        _require(payload, "purpose_code", expected.purpose_code, "PURPOSE")
        _require(payload, "resource_type", expected.resource_type, "RESOURCE_TYPE")
        _require(payload, "resource_id", expected.resource_id, "RESOURCE")
        _require(payload, "source_version_ref", expected.source_version_ref, "SOURCE_VERSION")
        _require(payload, "rights_digest", expected.rights_digest, "RIGHTS")
        _require(payload, "policy_version", expected.policy_version, "POLICY")
        _require(payload, "domain_guard_version", expected.domain_guard_version, "DOMAIN_GUARD")
        _require(payload, "identity_issuer", expected.identity_issuer, "IDENTITY_ISSUER")
        _require(payload, "command_id", expected.command_id, "COMMAND_ID")
        _require(payload, "decision_ref", expected.decision_ref, "DECISION_REF")
        _require_long(payload, "decision_revocation_epoch", expected.decision_epoch, "REVOKED", "DECISION_EPOCH")
        _require_long(payload, "identity_revocation_epoch", expected.identity_epoch, "REVOKED", "IDENTITY_EPOCH")
        _require_long(payload, "session_revocation_epoch", expected.session_epoch, "REVOKED", "SESSION_EPOCH")
        _require_command_digest(payload, expected.command_fields)
        now = self.now()
        nbf = _long(payload, "nbf")
        iat = _long(payload, "iat")
        exp = _long(payload, "exp")
        if now < nbf or now < iat:
            raise SovProofError("NOT_YET_VALID", "NBF")
        if now >= exp:
            raise SovProofError("EXPIRED", "EXP")
        if exp <= iat or (exp - iat) > MAX_TTL_SECONDS:
            raise SovProofError("STALE", "TTL")
        jti = _text(payload, "jti")
        if not jti.strip():
            raise SovProofError("CLAIM_MISMATCH", "JTI")
        if jti in self.replay_store:
            raise SovProofError("REPLAY", "JTI")
        self.replay_store.add(jti)


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise SovProofError("CLAIM_MISMATCH", key)
    return value


def _long(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SovProofError("CLAIM_MISMATCH", key)
    return value


def _require(payload: dict[str, Any], key: str, expected: str, reason: str) -> None:
    if expected is None or _text(payload, key) != expected:
        raise SovProofError("CLAIM_MISMATCH", reason)


def _require_long(payload: dict[str, Any], key: str, expected: int, code: str, reason: str) -> None:
    if _long(payload, key) != expected:
        raise SovProofError(code, reason)


def _require_command_digest(payload: dict[str, Any], command: Sequence[object]) -> None:
    try:
        recomputed = local_digest(command)
    except DigestContractError as exc:
        raise SovProofError("DIGEST_CONTRACT_UNRESOLVED", "COMMAND") from exc
    if recomputed != _text(payload, "request_sha256"):
        raise SovProofError("DIGEST_MISMATCH", "REQUEST_SHA256")
    if len(command) != COMMAND_FIELDS:
        raise SovProofError("DIGEST_MISMATCH", "FIELD_COUNT")
    _command_field(command, 2, _text(payload, "command_id"), "COMMAND_ID")
    _command_field(command, 3, _text(payload, "tenant_id"), "TENANT")
    _command_field(command, 5, _text(payload, "purpose_code"), "PURPOSE")
    _command_field(command, 8, _text(payload, "source_version_ref"), "SOURCE_VERSION")
    _command_field(command, 9, _text(payload, "rights_digest"), "RIGHTS")
    _command_field(command, 11, _text(payload, "decision_ref"), "DECISION_REF")


def _command_field(command: Sequence[object], index: int, expected: str, reason: str) -> None:
    value = command[index]
    if value != expected:
        raise SovProofError("CLAIM_MISMATCH", reason)
