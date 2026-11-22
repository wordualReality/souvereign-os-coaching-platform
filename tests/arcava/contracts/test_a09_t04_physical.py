import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RUNNER=ROOT/'scripts/arcava/validate_a09_t04_physical.py'
PINS='docs/arcava/admission/synthetic/A09-T04/byte-pins.json'

class PhysicalTests(unittest.TestCase):
    def run_cli(self,root):
        return subprocess.run([sys.executable,str(RUNNER),'--root',str(root)],capture_output=True,text=True,timeout=10)

    def test_exact_physical_and_repeatability(self):
        a,b=self.run_cli(ROOT),self.run_cli(ROOT)
        self.assertEqual(a.returncode,0,a.stdout+a.stderr)
        self.assertEqual(a.stdout,b.stdout)
        value=json.loads(a.stdout)
        self.assertEqual(value['schema_count'],16)
        self.assertEqual(len(value['contract_ids']),4)
        self.assertEqual(value['original_T04'],'NOT_EXECUTED')

    def test_isolated_negative_cli(self):
        for variant in ('missing_schema','missing_manifest','missing_pins','tamper','swap','extra_schema','duplicate_pin','extra_pin','version','kind','path','escape','symlink','hash'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                shutil.copytree(ROOT/'contracts/arcava',root/'contracts/arcava')
                pin_path=root/PINS
                pin_path.parent.mkdir(parents=True)
                shutil.copyfile(ROOT/PINS,pin_path)
                pins=json.loads(pin_path.read_text())
                schema=root/pins['pins'][3]['path']
                manifest=root/'contracts/arcava/contract-manifest.json'
                if variant=='missing_schema': schema.unlink()
                elif variant=='missing_manifest': manifest.unlink()
                elif variant=='missing_pins': pin_path.unlink()
                elif variant=='tamper': schema.write_bytes(schema.read_bytes()+b' ')
                elif variant=='swap': schema.write_bytes((root/pins['pins'][4]['path']).read_bytes())
                elif variant=='extra_schema': (root/'contracts/arcava/extra.schema.json').write_text('{}')
                elif variant=='symlink':
                    schema.unlink();schema.symlink_to(ROOT/pins['pins'][3]['path'])
                else:
                    if variant=='duplicate_pin': pins['pins'][4]=dict(pins['pins'][3])
                    elif variant=='extra_pin': pins['pins'].append(dict(pins['pins'][3]))
                    elif variant=='version': pins['pins'][3]['version']='2.0'
                    elif variant=='kind': pins['pins'][3]['kind']='result'
                    elif variant=='path': pins['pins'][3]['path']=pins['pins'][4]['path']
                    elif variant=='escape': pins['pins'][3]['path']='../../outside'
                    elif variant=='hash': pins['pins'][3]['sha256']='0'*64
                    pin_path.write_text(json.dumps(pins))
                result=self.run_cli(root)
                self.assertEqual(result.returncode,1,result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout)['status'],'FAIL')

if __name__=='__main__': unittest.main()
