"""C08 synthetic consumer contract and fail-closed resolver tests."""
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
from offline_seasonal_botanical import digest, resolve

FIXTURE = ROOT / 'tests/kdb/fixtures/c08_b01_synthetic_preview.json'
SCHEMA = ROOT / 'contracts/kdb/c08_seasonal_botanical_preview.v1.schema.json'
SCRIPT = ROOT / 'services/kdb/offline_seasonal_botanical.py'


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class SyntheticBotanicalPreviewTests(unittest.TestCase):
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
        self.assertEqual(result['admission'], 'NOT_ADMITTED')
        self.assertEqual(result['execution'], 'NON_EXECUTABLE')
        return result

    def test_cli_deterministic_and_contract(self):
        a = subprocess.check_output([sys.executable, str(SCRIPT), str(FIXTURE)], text=True)
        b = subprocess.check_output([sys.executable, str(SCRIPT), str(FIXTURE)], text=True)
        self.assertEqual(a, b)
        expected = self.check(fixture())
        self.assertEqual(json.loads(a), expected)
        self.assertEqual(expected['decision'], 'PREVIEW')
        self.assertTrue(expected['in_typical_season'])
        self.assertEqual(expected['lookalike_status'], 'NO_LOOKALIKE_IN_SYNTHETIC_FIXTURE')
        self.assertEqual(expected['identity_status'], 'UNAMBIGUOUS_SYNTHETIC')
        self.assertEqual(expected['provenance']['source_version_id'], 'SYN-VER-ALPHA-1')
        self.assertEqual(expected['provenance']['availability'], 'PINNED_UNTRUSTED')
        self.assertEqual(expected['interpretation'], 'TYPICAL_NOT_REALTIME_INVENTORY')

    def test_unreadable_input_is_bounded_abstention(self):
        with tempfile.TemporaryDirectory() as directory:
            output = subprocess.check_output([sys.executable, str(SCRIPT), str(Path(directory) / 'missing.json')], text=True)
        result = json.loads(output)
        self.validator.validate(result)
        self.assertEqual((result['decision'], result['reason'], result['provenance']['availability']), ('ABSTAIN', 'INVALID_INPUT_ENVELOPE', 'UNAVAILABLE'))

    def test_hemispheres_are_explicit_source_data(self):
        north = fixture(); north['query']['month'] = 10
        self.assertFalse(self.check(north)['in_typical_season'])
        south = fixture(); south['query'].update(hemisphere='SOUTH', month=10)
        self.assertTrue(self.check(south)['in_typical_season'])
        self.assertEqual(self.check(south)['typical_months'], [9, 10, 11])

    def test_absence_and_uncertainty_keep_pinned_provenance(self):
        other = fixture(); other['query']['plant_id'] = 'SYNTHETIC:BETA'
        result = self.check(other)
        self.assertEqual(result['reason'], 'SPECIES_NOT_IN_PINNED_SOURCE')
        self.assertEqual(result['provenance']['source_id'], 'SYN-SRC-ALPHA')
        region = fixture(); region['query']['region'] = 'SYN-BB'
        result = self.check(region)
        self.assertEqual((result['decision'], result['reason'], result['uncertainty']), ('ABSTAIN', 'SEASON_UNCERTAIN', 'UNCERTAIN'))
        missing = fixture(); missing['query']['region'] = 'SYN-CC'
        self.assertEqual(self.check(missing)['reason'], 'NO_EVIDENCE_FOR_REGION_HEMISPHERE')
        self.assertIn('provenance', self.check(missing))

    def test_untrusted_snapshot_negative_matrix(self):
        cases = [
            ('unknown version', lambda d: d['query'].update(source_version_id='SYN-VER-UNKNOWN'), 'SOURCE_VERSION_UNKNOWN'),
            ('revoked', lambda d: d['snapshot']['sources'][0].update(rights_status='REVOKED'), 'RIGHTS_NOT_ADMITTED'),
            ('unknown rights', lambda d: d['snapshot']['sources'][0].update(rights_status='UNKNOWN'), 'RIGHTS_NOT_ADMITTED'),
            ('stale version', lambda d: d['snapshot']['sources'][0].update(current_version_id='SYN-VER-ALPHA-2'), 'STALE_VERSION'),
            ('cross tenant', lambda d: d['query'].update(tenant_scope='OTHER'), 'TENANT_MISMATCH'),
            ('purpose', lambda d: d['query'].update(purpose='OTHER'), 'PURPOSE_MISMATCH'),
            ('license', lambda d: d['snapshot']['sources'][0].update(license_status='UNKNOWN'), 'LICENSE_UNCLEAR'),
            ('stale rights', lambda d: d['snapshot']['sources'][0].update(rights_checked_as_of='2026-11-03'), 'STALE_RIGHTS_SNAPSHOT'),
            ('stale snapshot', lambda d: d['query'].update(knowledge_as_of='2026-11-03'), 'STALE_SNAPSHOT'),
            ('invalid date', lambda d: d['query'].update(knowledge_as_of='2026-02-30'), 'INVALID_AS_OF'),
            ('lifecycle', lambda d: d['snapshot']['sources'][0].update(lifecycle_disposition='WITHDRAWN'), 'LIFECYCLE_NOT_ELIGIBLE'),
            ('source absent', lambda d: d['snapshot'].update(sources=[]), 'SOURCE_MISSING'),
            ('month', lambda d: d['query'].update(month=None), 'MONTH_REQUIRED'),
            ('boolean month', lambda d: d['query'].update(month=True), 'MONTH_REQUIRED'),
            ('hemisphere', lambda d: d['query'].update(hemisphere=None), 'HEMISPHERE_REQUIRED'),
            ('undocumented part', lambda d: d['query'].update(plant_part='ROOT'), 'UNDOCUMENTED_PLANT_PART'),
            ('review approval claim', lambda d: d['query'].update(reviewer_approved=True), 'UNTRUSTED_AUTHORITY_OR_HEALTH_CLAIM'),
            ('health claim', lambda d: d['snapshot']['sources'][0]['content'].update(health_claim='untrusted'), 'UNTRUSTED_AUTHORITY_OR_HEALTH_CLAIM'),
            ('tampered content', lambda d: d['snapshot']['sources'][0]['content'].update(scientific_name='Synthetic species BETA'), 'CONTENT_DIGEST_MISMATCH'),
        ]
        for label, mutate, reason in cases:
            with self.subTest(label=label):
                data = fixture(); mutate(data)
                result = self.check(data)
                self.assertEqual((result['decision'], result['reason']), ('ABSTAIN', reason))
                self.assertIn(result['provenance']['availability'], ('UNAVAILABLE', 'PINNED_UNTRUSTED'))

    def test_content_semantic_fail_closed_with_rehashed_input(self):
        cases = [('identity_status', 'AMBIGUOUS', 'AMBIGUOUS_SPECIES'),
                 ('lookalike_status', 'POTENTIALLY_POISONOUS', 'LOOKALIKE_UNRESOLVED'),
                 ('statement_id', '', 'EVIDENCE_MISSING'), ('evidence_locator', '', 'EVIDENCE_MISSING')]
        for field, value, reason in cases:
            with self.subTest(field=field):
                data = fixture(); src = data['snapshot']['sources'][0]
                src['content'][field] = value; src['content_sha256'] = digest(src['content'])
                self.assertEqual(self.check(data)['reason'], reason)
        data = fixture(); src = data['snapshot']['sources'][0]
        src['content']['season_records'][0]['uncertainty'] = 'DISPUTED'; src['content_sha256'] = digest(src['content'])
        self.assertEqual(self.check(data)['reason'], 'SEASON_DISPUTED')
        data = fixture(); src = data['snapshot']['sources'][0]
        src['content']['season_records'].append(deepcopy(src['content']['season_records'][0])); src['content_sha256'] = digest(src['content'])
        self.assertEqual(self.check(data)['reason'], 'CONFLICTING_SEASON_RECORDS')

    def test_conflicting_and_duplicate_versions_abstain(self):
        data = fixture(); data['snapshot']['sources'].append(deepcopy(data['snapshot']['sources'][0]))
        self.assertEqual(self.check(data)['reason'], 'CONFLICTING_VERSION')
        data = fixture(); other = deepcopy(data['snapshot']['sources'][0]); other['source_version_id'] = 'SYN-VER-ALPHA-2'; other['current_version_id'] = other['source_version_id']; data['snapshot']['sources'].append(other)
        self.assertEqual(self.check(data)['reason'], 'CONFLICTING_VERSION')


if __name__ == '__main__': unittest.main()
