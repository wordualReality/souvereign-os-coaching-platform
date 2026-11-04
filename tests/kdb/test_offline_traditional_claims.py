"""Synthetic traditional-claim contract and fail-closed semantics."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/kdb'))
from offline_seasonal_botanical import digest
from offline_traditional_claims import resolve

FIXTURE = ROOT / 'tests/kdb/fixtures/c08_b02_synthetic_traditional_claim.json'
SCHEMA = ROOT / 'contracts/kdb/c08_traditional_claim_preview.v1.schema.json'
SCRIPT = ROOT / 'services/kdb/offline_traditional_claims.py'


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def rehash_claim(data):
    claim = data['snapshot']['claims'][0]
    claim['content_sha256'] = digest(claim['content'])


class SyntheticTraditionalClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)

    def check(self, data):
        before = deepcopy(data)
        result = resolve(data['snapshot'], data['query'])
        self.assertEqual(data, before, 'resolver must not mutate input')
        self.validator.validate(result)
        self.assertEqual((result['scope'], result['mode'], result['execution'], result['admission']),
                         ('SYNTHETIC_TEST_ONLY', 'PREVIEW_ONLY', 'NON_EXECUTABLE', 'NOT_ADMITTED'))
        self.assertEqual(result['snapshot_trust'], 'UNTRUSTED_SYNTHETIC_SNAPSHOT')
        return result

    def test_cli_determinism_and_contract(self):
        first = subprocess.check_output([sys.executable, str(SCRIPT), str(FIXTURE)], text=True)
        second = subprocess.check_output([sys.executable, str(SCRIPT), str(FIXTURE)], text=True)
        self.assertEqual(first, second)
        result = self.check(fixture())
        self.assertEqual(json.loads(first), result)
        self.assertEqual((result['decision'], result['framework'], result['review_status']),
                         ('PREVIEW_CONTEXT_ONLY', 'TCM', 'UNVERIFIED_SYNTHETIC'))
        self.assertEqual(result['evidence_boundary'], 'NO_BIOMEDICAL_EFFICACY_OR_DIAGNOSIS_INFERRED')
        self.assertEqual(result['provenance']['availability'], 'CLAIM_PINNED_UNTRUSTED')
        self.assertEqual(result['provenance']['claim_version_id'], 'SYN-CLAIMVER-TRAD-ALPHA-1')
        forged = deepcopy(result); forged['reviewer_approved'] = True
        self.assertFalse(self.validator.is_valid(forged))

    def test_traditions_never_merge(self):
        data = fixture(); data['query']['expected_framework'] = 'AYURVEDA'
        result = self.check(data)
        self.assertEqual((result['decision'], result['reason']), ('ABSTAIN', 'TRADITION_MISMATCH'))
        self.assertEqual(result['provenance']['availability'], 'CLAIM_PINNED_UNTRUSTED')
        data = fixture(); data['snapshot']['claims'][0]['content']['framework'] = 'AYURVEDA'; rehash_claim(data)
        data['query']['expected_framework'] = 'AYURVEDA'
        self.assertEqual(self.check(data)['reason'], 'TRADITION_MISMATCH')
        source = data['snapshot']['sources'][0]; source['content']['framework'] = 'AYURVEDA'
        source['content_sha256'] = digest(source['content'])
        data['snapshot']['claims'][0]['source_content_sha256'] = source['content_sha256']
        self.assertEqual(self.check(data)['framework'], 'AYURVEDA')

    def test_clinical_claims_and_unsupported_evidence_abstain(self):
        for claim_type, reason in [('BIOMEDICAL_RESEARCH', 'RESEARCH_EVIDENCE_NOT_VERIFIED'),
                                   ('CLINICAL_EFFICACY', 'MEDICAL_INTERPRETATION_PROHIBITED'),
                                   ('DIAGNOSIS', 'MEDICAL_INTERPRETATION_PROHIBITED'),
                                   ('TREATMENT', 'MEDICAL_INTERPRETATION_PROHIBITED'),
                                   ('PERSONAL_PREFERENCE', 'PERSONAL_PREFERENCE_NOT_KDB_AUTHORITY')]:
            with self.subTest(claim_type=claim_type):
                data = fixture(); data['snapshot']['claims'][0]['content'].update(claim_type=claim_type, evidence_type='CLINICAL_STUDY'); rehash_claim(data)
                self.assertEqual((self.check(data)['decision'], self.check(data)['reason']), ('ABSTAIN', reason))
        data = fixture(); data['snapshot']['claims'][0]['content']['evidence_type'] = 'CLINICAL_STUDY'; rehash_claim(data)
        self.assertEqual(self.check(data)['reason'], 'UNSUPPORTED_EVIDENCE_TYPE')

    def test_no_result_and_missing_provenance(self):
        data = fixture(); data['query']['claim_version_id'] = 'SYN-CLAIMVER-UNKNOWN'
        result = self.check(data)
        self.assertEqual(result['reason'], 'CLAIM_VERSION_UNKNOWN')
        self.assertEqual(result['provenance']['availability'], 'SOURCE_PINNED_UNTRUSTED')
        self.assertEqual(result['provenance']['source_version_id'], 'SYN-VER-TRAD-ALPHA-1')
        for key in ('statement_id', 'evidence_locator'):
            with self.subTest(key=key):
                data = fixture(); data['snapshot']['sources'][0]['content'][key] = ''
                data['snapshot']['sources'][0]['content_sha256'] = digest(data['snapshot']['sources'][0]['content'])
                self.assertIn(self.check(data)['reason'], ('STATEMENT_PROVENANCE_MISSING', 'EVIDENCE_PROVENANCE_MISSING'))

    def test_source_and_claim_version_negative_matrix(self):
        cases = [
            ('source missing', lambda d: d['snapshot'].update(sources=[]), 'SOURCE_MISSING'),
            ('claim missing', lambda d: d['snapshot'].update(claims=[]), 'CLAIM_MISSING'),
            ('unknown source', lambda d: d['query'].update(source_version_id='SYN-VER-UNKNOWN'), 'SOURCE_VERSION_UNKNOWN'),
            ('revoked', lambda d: d['snapshot']['sources'][0].update(rights_status='REVOKED'), 'RIGHTS_NOT_ADMITTED'),
            ('unknown rights', lambda d: d['snapshot']['sources'][0].update(rights_status='UNKNOWN'), 'RIGHTS_NOT_ADMITTED'),
            ('withdrawn', lambda d: d['snapshot']['sources'][0].update(lifecycle_disposition='WITHDRAWN'), 'SOURCE_WITHDRAWN_OR_INELIGIBLE'),
            ('stale source', lambda d: d['snapshot']['sources'][0].update(current_version_id='SYN-VER-TRAD-ALPHA-2'), 'STALE_SOURCE_VERSION'),
            ('stale claim', lambda d: d['snapshot']['claims'][0].update(current_claim_version_id='SYN-CLAIMVER-TRAD-ALPHA-2'), 'STALE_CLAIM_VERSION'),
            ('tenant', lambda d: d['query'].update(tenant_scope='OTHER'), 'TENANT_MISMATCH'),
            ('purpose', lambda d: d['query'].update(purpose='OTHER'), 'PURPOSE_MISMATCH'),
            ('license', lambda d: d['snapshot']['sources'][0].update(license_status='UNKNOWN'), 'LICENSE_UNCLEAR'),
            ('stale rights', lambda d: d['snapshot']['sources'][0].update(rights_checked_as_of='2026-11-03'), 'STALE_RIGHTS_SNAPSHOT'),
            ('claim source mismatch', lambda d: d['snapshot']['claims'][0].update(source_version_id='SYN-VER-OTHER'), 'CLAIM_SOURCE_MISMATCH'),
            ('source tamper', lambda d: d['snapshot']['sources'][0]['content'].update(fixture_source_label='SYN-SOURCE-OTHER'), 'SOURCE_DIGEST_MISMATCH'),
            ('claim tamper', lambda d: d['snapshot']['claims'][0]['content'].update(statement_code='SYN-TRAD-BETA'), 'CLAIM_DIGEST_MISMATCH'),
            ('tradition unspecified', lambda d: d['query'].update(expected_framework=None), 'UNSPECIFIED_TRADITION'),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                data = fixture(); mutate(data)
                self.assertEqual((self.check(data)['decision'], self.check(data)['reason']), ('ABSTAIN', expected))

    def test_conflicts_and_evidence_binding(self):
        for collection, reason in [('sources', 'CONFLICTING_SOURCE_VERSION'), ('claims', 'CONFLICTING_CLAIM_VERSION')]:
            with self.subTest(collection=collection):
                data = fixture(); data['snapshot'][collection].append(deepcopy(data['snapshot'][collection][0]))
                self.assertEqual(self.check(data)['reason'], reason)
        data = fixture(); other = deepcopy(data['snapshot']['sources'][0]); other['source_version_id'] = 'SYN-VER-TRAD-ALPHA-2'; other['current_version_id'] = other['source_version_id']; data['snapshot']['sources'].append(other)
        self.assertEqual(self.check(data)['reason'], 'CONFLICTING_SOURCE_VERSION')
        data = fixture(); other = deepcopy(data['snapshot']['claims'][0]); other['claim_version_id'] = 'SYN-CLAIMVER-TRAD-ALPHA-2'; other['current_claim_version_id'] = other['claim_version_id']; data['snapshot']['claims'].append(other)
        self.assertEqual(self.check(data)['reason'], 'CONFLICTING_CLAIM_VERSION')
        data = fixture(); data['snapshot']['claims'][0]['content']['evidence_locator'] = 'fixture://other/evidence#statement-1'; rehash_claim(data)
        self.assertEqual(self.check(data)['reason'], 'CLAIM_EVIDENCE_MISMATCH')
        data = fixture(); data['snapshot']['claims'][0]['content']['review_status'] = 'APPROVED'; rehash_claim(data)
        self.assertEqual(self.check(data)['reason'], 'REVIEW_STATUS_NOT_ALLOWED')

    def test_untrusted_authority_and_personal_data_do_not_pass(self):
        for key in ('role', 'reviewer', 'approved', 'scientifically_proven', 'diagnosis', 'dosha', 'constitution', 'email', 'symptoms'):
            with self.subTest(key=key):
                data = fixture(); data['query'][key] = 'UNTRUSTED'
                result = self.check(data)
                self.assertEqual(result['reason'], 'UNTRUSTED_AUTHORITY_MEDICAL_OR_PERSONAL_DATA')
                self.assertNotIn('UNTRUSTED', json.dumps(result).replace('UNTRUSTED_SYNTHETIC_SNAPSHOT', '').replace('UNTRUSTED_AUTHORITY_MEDICAL_OR_PERSONAL_DATA', ''))
        data = fixture(); original = self.check(data); data['query']['consumer_preference'] = 'SYNTHETIC_DISPLAY_FILTER'
        self.assertEqual(self.check(data), original)
        data['query']['consumer_preference'] = {'name': 'PRIVATE'}
        self.assertEqual(self.check(data)['decision'], 'ABSTAIN')

    def test_invalid_input_cli_returns_abstention(self):
        with tempfile.TemporaryDirectory() as directory:
            output = subprocess.check_output([sys.executable, str(SCRIPT), str(Path(directory) / 'missing.json')], text=True)
        result = json.loads(output); self.validator.validate(result)
        self.assertEqual((result['decision'], result['provenance']['availability']), ('ABSTAIN', 'UNAVAILABLE'))


if __name__ == '__main__': unittest.main()
