import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("runner",ROOT/"runner.py")
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class SourceGatedBridgeTest(unittest.TestCase):
    def setUp(self):self.config=json.loads((ROOT/"config.json").read_text())
    def test_exact_selected_controller_and_cameras(self):
        proof=runner.check(self.config)
        self.assertTrue(proof["selected"])
        self.assertEqual(proof["frame_count"],600)
        self.assertEqual(proof["views"],["overview","approach","reference","driver"])
    def test_missing_survey_rejected(self):
        with self.assertRaisesRegex(Exception,"original assignment bridge survey required"):
            runner.read_survey(ROOT/"config.json")
    def test_requested_speed_does_not_prove_physical_or_legal_outcome(self):
        self.assertFalse(self.config["physical_completion"])
        self.assertIsNone(self.config["legal_verdict"])
    def test_wrong_case_rejected(self):
        self.config["case_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"exact assignment changed"):runner.check(self.config)
if __name__=="__main__":unittest.main()
