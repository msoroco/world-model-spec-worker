import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from runner import check,controller,read_original

class NativeContractTest(unittest.TestCase):
    def test_selected_config(self):
        config=json.loads(Path('config.json').read_text())
        result=check(config)
        self.assertEqual(result['frames'],600)
        self.assertIsNone(result['observed_crossing_station_m'])
    def test_controller_and_missing_original(self):
        motion=controller((0,0),0,0,[(0,0),(2,0),(4,1),(5,3)])
        self.assertGreater(motion['throttle'],0)
        self.assertLessEqual(abs(motion['steer']),1)
        with self.assertRaisesRegex(ValueError,'Original divided-road'):
            read_original(None,None)
    def test_runtime_capture_launch_shape_source_gate(self):
        env=os.environ.copy()
        env.pop('SCENARIO_DIVIDED_CONTEXT',None)
        env.pop('SCENARIO_TURN_ANNOTATIONS',None)
        result=subprocess.run([sys.executable,'runner.py','--output-dir','.',
                               '--host','127.0.0.1','--port','2000'],
                              env=env,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Original divided-road survey and turn annotation required',result.stderr)
