import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        config=json.loads(Path("config.json").read_text())
        self.assertTrue(check(config)["offline_contract_passed"])
    def test_reject_wrong_centerline(self):
        config=json.loads(Path("config.json").read_text())
        config["centerline_kind"]="wrong"
        with self.assertRaisesRegex(ValueError,"centerline"):
            check(config)
    def test_reject_wrong_lateral_target(self):
        config=json.loads(Path("config.json").read_text())
        config["target_approach_offset_m"]=0
        with self.assertRaisesRegex(ValueError,"position target"):
            check(config)
