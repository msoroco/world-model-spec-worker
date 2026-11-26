import copy
import json
import unittest
from pathlib import Path
from capture import check

class SelectedContract(unittest.TestCase):
    def setUp(self): self.config=json.loads(Path("config.json").read_text())
    def test_exact(self): self.assertEqual(check(self.config)["frames"],600)
    def test_missing_device(self):
        bad=copy.deepcopy(self.config);bad["device_indicated_angle_deg"]=None
        with self.assertRaisesRegex(ValueError,"device"): check(bad)
    def test_missing_camera(self):
        bad=copy.deepcopy(self.config);bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"Four named"): check(bad)
    def test_short_window(self):
        bad=copy.deepcopy(self.config);bad["duration_frames"]=599
        with self.assertRaisesRegex(ValueError,"30-second"): check(bad)
