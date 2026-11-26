import copy
import json
import unittest
from pathlib import Path
from runner import check

class DraftContract(unittest.TestCase):
    def setUp(self): self.config=json.loads(Path("config.json").read_text())
    def test_exact_window(self): self.assertEqual(check(self.config)["frames"],600)
    def test_missing_camera(self):
        bad=copy.deepcopy(self.config);bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"Four source cameras"):check(bad)
    def test_short_window(self):
        bad=copy.deepcopy(self.config);bad["duration_frames"]=599
        with self.assertRaisesRegex(ValueError,"30-second"):check(bad)
    def test_changed_release(self):
        bad=copy.deepcopy(self.config);bad["turn_release_s"]+=1
        with self.assertRaisesRegex(ValueError,"turn release"):check(bad)
    def test_signal_missing(self):
        bad=copy.deepcopy(self.config);bad["left_signal_requested"]=False
        with self.assertRaisesRegex(ValueError,"turn signal"):check(bad)
