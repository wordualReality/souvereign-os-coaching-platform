import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT/'scripts/arcava/validate_a09_t44_policy_authority.py'
SEED='database/policies/001_project_b_rls_seed.sql'
CASE='docs/arcava/admission/synthetic/A09-T44/case.json'
ENGINE='docs/arcava/admission/synthetic/A09-T44/engine.json'

class PolicyAuthorityTests(unittest.TestCase):
    def cli(self,root):
        run=subprocess.run([sys.executable,str(SCRIPT),'--root',str(root)],capture_output=True,text=True,timeout=10)
        return run.returncode,json.loads(run.stdout)

    def test_current_source_denied_repeatably(self):
        a=self.cli(ROOT)
        self.assertEqual(a,self.cli(ROOT))
        self.assertEqual(a[0],0)
        self.assertEqual(a[1]['decision'],'BLOCK_UNAPPROVED_FOREIGN_SEED')
        self.assertEqual(a[1]['SQL_EXECUTION'],'NOT_EXECUTED')

    def test_mutations_cannot_authorize(self):
        variants=('owner_pin','changed_bytes','missing_case','missing_sql','source_location','approval','live_success','foreign_schema','public_grant','engine','symlink')
        for variant in variants:
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                for relative in (SEED,CASE,ENGINE):
                    dst=root/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,dst)
                case=json.loads((root/CASE).read_text())
                if variant=='missing_case': (root/CASE).unlink()
                elif variant=='missing_sql': (root/SEED).unlink()
                elif variant in ('changed_bytes','foreign_schema','public_grant'):
                    suffix={'changed_bytes':'-- changed','foreign_schema':'-- owner=KDB schema=canonical','public_grant':'grant all on schema project_b to public;'}[variant]
                    (root/SEED).write_bytes((root/SEED).read_bytes()+suffix.encode())
                elif variant=='engine': (root/ENGINE).write_text('{"entrypoint":"execute_sql"}')
                elif variant=='symlink': (root/SEED).unlink();(root/SEED).symlink_to(ROOT/SEED)
                else:
                    if variant=='owner_pin': case['owner_admitted']=True
                    elif variant=='source_location': case['historical_seed']='database/policies/approved.sql'
                    elif variant=='approval': case['historical_seed_authority']='APPROVED'
                    elif variant=='live_success': case['sql_apply']='PASS'
                    (root/CASE).write_text(json.dumps(case))
                code,result=self.cli(root)
                self.assertEqual(code,1)
                self.assertEqual(result['decision'],'BLOCK_UNAPPROVED_FOREIGN_SEED')
                self.assertEqual(result['SQL_EXECUTION'],'NOT_EXECUTED')
                self.assertTrue(result['input_errors'])

if __name__=='__main__': unittest.main()
