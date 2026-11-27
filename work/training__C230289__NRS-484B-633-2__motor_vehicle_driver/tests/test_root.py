import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("root_runner",ROOT/"runner.py")
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class RootContract(unittest.TestCase):
    def test_selected_source_gate(self):
        config=json.loads((ROOT/"config.json").read_text())
        proof=runner.check(config)
        self.assertTrue(proof["selected"])
        self.assertEqual(proof["frame_count"],600)
        self.assertEqual(proof["views"],["overview","approach","reference_corner","driver_reference"])
if __name__=="__main__":unittest.main()
