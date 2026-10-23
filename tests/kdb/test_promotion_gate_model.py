"""Pure model test for future KDB-only promotion eligibility; NOT DB integration proof."""
import unittest
class Denied(Exception): pass


def guarded_model_promotion(candidate, decision, context):
    if context['caller']!='KDB_PROMOTION_OWNER': raise Denied('NOT_KDB_OWNER')
    if not context.get('enable_promotion_test'): raise Denied('PROMOTION_DISABLED')
    if candidate['tenant'] != context['tenant'] or candidate['source_version']!=decision['source_version']:
        raise Denied('SCOPE_OR_SOURCE_VERSION_MISMATCH')
    if candidate['content_hash'] != decision['candidate_hash']:raise Denied('STALE_CANDIDATE_HASH')
    if decision['decision'] != 'APPROVED_FOR_PROMOTION' or not decision['human_signed']:raise Denied('MISSING_HUMAN_DECISION')
    if not context['rights_current'] or not context['safety_current'] or not context['taxo_current']:
        raise Denied('RIGHTS_SAFETY_TAXONOMY_NOT_FRESH')
    return {'protocol_version_id':'immutable-synthetic-version','owner':'KDB','candidate_hash':candidate['content_hash']}


C={'tenant':'tenant-A','source_version':'sourcev1','content_hash':'a'*64}
D={'source_version':'sourcev1','candidate_hash':'a'*64,'human_signed':True,'decision':'APPROVED_FOR_PROMOTION'}
X={'caller':'KDB_PROMOTION_OWNER','tenant':'tenant-A','enable_promotion_test':True,'rights_current':True,'safety_current':True,'taxo_current':True}
class PromotionModel(unittest.TestCase):
    def test_01_synthetic_qualified_promotion_model(self):
        self.assertEqual('KDB',guarded_model_promotion(C,D,X)['owner'])
    def test_02_o1_o3_cannot_promote(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,caller='N8N'))
    def test_03_disabled_even_for_owner(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,enable_promotion_test=False))
    def test_04_unsigned_review_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,dict(D,human_signed=False),X)
    def test_05_stale_candidate_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,dict(D,candidate_hash='b'*64),X)
    def test_06_tenant_crossing_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,tenant='tenant-B'))
    def test_07_withdrawn_rights_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,rights_current=False))
    def test_08_safety_expired_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,safety_current=False))
    def test_09_taxonomy_expired_refused(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,D,dict(X,taxo_current=False))
    def test_10_source_version_mismatch(self):
        with self.assertRaises(Denied):guarded_model_promotion(C,dict(D,source_version='sourcev2'),X)
