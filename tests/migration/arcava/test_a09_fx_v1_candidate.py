import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('validator',ROOT/'scripts/arcava/validate_a09_fx_v1_candidate.py')
validator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

class CandidateTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'docs/arcava/admission/synthetic/A09-FX-v1'
        self.manifest=json.loads((folder/'manifest.candidate.json').read_text())
        self.matrix=json.loads((folder/'applicability.json').read_text())

    def test_positive_repeatability(self):
        self.assertEqual(validator.validate(self.manifest,self.matrix),validator.validate(copy.deepcopy(self.manifest),copy.deepcopy(self.matrix)))

    def test_negatives(self):
        mutations={
            'missing':lambda m,x:x['tests'].pop(),
            'duplicate':lambda m,x:x['tests'].__setitem__(1,copy.deepcopy(x['tests'][0])),
            'reorder':lambda m,x:x['tests'].reverse(),
            'hash_alteration':lambda m,x:m['slots'][0]['values'].append('changed'),
            'forged_owner_pin':lambda m,x:m.__setitem__('owner_pin','approved'),
            'missing_binding':lambda m,x:m['slots'][0].pop('binding'),
            'source_drift':lambda m,x:x['tests'][0].__setitem__('source','https://example.invalid'),
            'oracle_drift':lambda m,x:x['tests'][0].__setitem__('oracle','PASS'),
            'approval':lambda m,x:m.__setitem__('approval','APPROVED'),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                m,x=copy.deepcopy(self.manifest),copy.deepcopy(self.matrix)
                mutate(m,x)
                with self.assertRaises(ValueError): validator.validate(m,x)

if __name__=='__main__': unittest.main()
