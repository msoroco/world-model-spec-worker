import json
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
