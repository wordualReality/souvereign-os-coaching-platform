"""Synthetic fixture guard; never an authorization or production writer."""
from __future__ import annotations

import hashlib
import re

HEX = re.compile(r'^[0-9a-f]{64}$')


def validate(envelope: dict, source_bytes: bytes, previous: dict | None = None) -> dict:
    """Validate a bounded synthetic C04/C05 candidate without side effects."""
    def require(condition: bool, code: str) -> None:
        if not condition:
            raise ValueError(code)

    require(envelope.get('fixture') == 'SYNTHETIC_TEST_ONLY', 'FIXTURE_REQUIRED')
    require(envelope.get('rights_status') == 'ADMITTED', 'RIGHTS_NOT_ADMITTED')
    require(envelope.get('purpose') == 'KNOWLEDGE_INTAKE', 'PURPOSE_DENIED')
    for key in ('tenant', 'source_id', 'candidate_revision_id', 'decision_id',
                'review_item_id', 'command_id', 'reviewer_ref', 'authority_ref',
                'signed_decision_ref'):
        require(isinstance(envelope.get(key), str) and bool(envelope[key].strip()), 'MISSING_' + key.upper())
    require(envelope['reviewer_ref'].startswith('TEST_ONLY:'), 'REVIEWER_NOT_FIXTURE')
    require(envelope['authority_ref'].startswith('TEST_ONLY:'), 'AUTHORITY_NOT_FIXTURE')
    require(envelope['signed_decision_ref'].startswith('TEST_ONLY:'), 'SIGNATURE_NOT_FIXTURE')
    for key in ('source_sha256', 'candidate_content_sha256', 'rights_sha256', 'evidence_sha256'):
        require(isinstance(envelope.get(key), str) and bool(HEX.fullmatch(envelope[key])), 'INVALID_' + key.upper())
    require(hashlib.sha256(source_bytes).hexdigest() == envelope['source_sha256'], 'SOURCE_BYTES_MISMATCH')
    for payload, digest in (('candidate_bytes', 'candidate_content_sha256'), ('rights_bytes', 'rights_sha256'), ('evidence_bytes', 'evidence_sha256')):
        value = envelope.get(payload)
        require(isinstance(value, bytes) and hashlib.sha256(value).hexdigest() == envelope[digest], 'INVALID_' + payload.upper())
    require(envelope.get('decision') == 'APPROVED_FOR_PROMOTION', 'DECISION_NOT_APPROVED')
    require(envelope.get('lifecycle') == 'PUBLISHED' and envelope.get('prior_lifecycle') is None, 'LIFECYCLE_OUT_OF_ORDER')
    require(type(envelope.get('version_no')) is int and envelope['version_no'] == 1, 'VERSION_INVALID')
    require(envelope.get('candidate_tenant') == envelope['tenant'] == envelope.get('review_tenant'), 'TENANT_MISMATCH')
    require(envelope.get('review_candidate_revision_id') == envelope['candidate_revision_id'], 'REVISION_MISMATCH')
    require(envelope.get('review_candidate_sha256') == envelope['candidate_content_sha256'], 'CANDIDATE_DIGEST_MISMATCH')
    if previous is not None:
        require(previous == envelope, 'CONFLICTING_REPLAY')
        return {'status': 'SYNTHETIC_REPLAY_NOOP', 'admitted': False}
    return {'status': 'PREVIEW_ONLY / SYNTHETIC_FIXTURE / NOT_PRODUCTION_ADMITTED', 'admitted': False}
