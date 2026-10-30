"""The normal worker launcher and the local importer resolve one runtime."""
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
batch=json.loads((ROOT/'batch.json').read_text())
sys.path.insert(0, str(ROOT/batch['runtime']['root']/'scenario_pipeline'))
from worker_exchange.preparation import runtime_for


class EntrypointTests(unittest.TestCase):
    def test_local_importer_uses_batch_runtime(self):
        batch=json.loads((ROOT/'batch.json').read_text())
        runtime=runtime_for(ROOT,batch)
        self.assertTrue(runtime.is_dir())
        manifest=json.loads((runtime/'SOURCE-MANIFEST.json').read_text())
        self.assertIn('scenario_pipeline/worker_exchange/delivery_handoff.py',manifest['files'])

    def test_ordinary_launchers(self):
        for argv in (['worker_check.py'],['runtime.py','--help']):
            result=subprocess.run([sys.executable,*argv],cwd=ROOT,text=True,
                                  capture_output=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[-1000:])


if __name__=='__main__':
    unittest.main()
