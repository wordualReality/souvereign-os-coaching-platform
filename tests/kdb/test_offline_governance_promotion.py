import hashlib
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/kdb'))
from offline_governance_promotion import validate


def sample():
    h = lambda b: hashlib.sha256(b).hexdigest()
    candidate = b'{"test_only":true}'
    rights = b'{"test_only":true}'
    evidence = b'[{"test_only":true}]'
    return dict(fixture='SYNTHETIC_TEST_ONLY', rights_status='ADMITTED', purpose='KNOWLEDGE_INTAKE', tenant='TENANT_SYNTH', candidate_tenant='TENANT_SYNTH', review_tenant='TENANT_SYNTH', source_id='SOURCE', candidate_revision_id='REV1', review_candidate_revision_id='REV1', decision_id='DEC1', review_item_id='ITEM1', command_id='CMD1', reviewer_ref='TEST_ONLY:reviewer', authority_ref='TEST_ONLY:authority', signed_decision_ref='TEST_ONLY:signature', source_sha256=h(b'synthetic'), candidate_bytes=candidate, candidate_content_sha256=h(candidate), review_candidate_sha256=h(candidate), rights_bytes=rights, rights_sha256=h(rights), evidence_bytes=evidence, evidence_sha256=h(evidence), decision='APPROVED_FOR_PROMOTION', lifecycle='PUBLISHED', prior_lifecycle=None, version_no=1)


class GovernanceFixtureTests(unittest.TestCase):
    def test_positive_and_idempotency(self):
        e = sample()
        self.assertFalse(validate(e, b'synthetic')['admitted'])
        self.assertEqual(validate(e, b'synthetic', deepcopy(e))['status'], 'SYNTHETIC_REPLAY_NOOP')

    def test_negative_matrix(self):
        for key, value, reason in [
            ('rights_status','REVOKED','RIGHTS_NOT_ADMITTED'), ('rights_status','BLOCKED','RIGHTS_NOT_ADMITTED'), ('signed_decision_ref','','MISSING_SIGNED_DECISION_REF'),
            ('evidence_sha256','','INVALID_EVIDENCE_SHA256'), ('review_tenant','OTHER','TENANT_MISMATCH'),
            ('review_candidate_revision_id','REV2','REVISION_MISMATCH'), ('review_candidate_sha256','d'*64,'CANDIDATE_DIGEST_MISMATCH'),
            ('reviewer_ref','','MISSING_REVIEWER_REF'), ('authority_ref','','MISSING_AUTHORITY_REF'),
            ('prior_lifecycle','WITHDRAWN','LIFECYCLE_OUT_OF_ORDER'), ('fixture','REAL','FIXTURE_REQUIRED'),
            ('candidate_bytes',b'tampered','INVALID_CANDIDATE_BYTES'), ('rights_bytes',b'tampered','INVALID_RIGHTS_BYTES'), ('evidence_bytes',b'tampered','INVALID_EVIDENCE_BYTES')]:
            with self.subTest(key=key):
                e = sample(); e[key] = value
                with self.assertRaisesRegex(ValueError, reason): validate(e, b'synthetic')

    def test_bad_source_and_conflict(self):
        e = sample()
        with self.assertRaisesRegex(ValueError, 'SOURCE_BYTES_MISMATCH'): validate(e, b'tampered')
        other = deepcopy(e); other['decision_id'] = 'DEC2'
        with self.assertRaisesRegex(ValueError, 'CONFLICTING_REPLAY'): validate(other, b'synthetic', e)
        revoked = deepcopy(e); revoked['rights_status'] = 'REVOKED'
        with self.assertRaisesRegex(ValueError, 'RIGHTS_NOT_ADMITTED'): validate(revoked, b'synthetic', e)


if __name__ == '__main__':
    unittest.main()
