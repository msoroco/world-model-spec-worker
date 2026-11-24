import json
import unittest
from runner import check
from pathlib import Path
class BundleTest(unittest.TestCase):
    def test_exact_case(self):
        scene=json.loads(Path("scene.json").read_text())
        self.assertTrue(check(scene)["native_source_packet_required"])
    def test_reject_wrong_target(self):
        scene=json.loads(Path("scene.json").read_text())
        scene["target_physical_relation"]="invalid"
        with self.assertRaises(ValueError): check(scene)
