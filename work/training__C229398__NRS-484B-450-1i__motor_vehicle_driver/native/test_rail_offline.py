import copy
import json
import unittest
from pathlib import Path
from runner import check


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads(Path("config.json").read_text())

    def test_full_window(self):
        self.assertEqual(check(self.cfg)["frames"],600)

    def test_missing_camera_rejected(self):
        bad=copy.deepcopy(self.cfg);bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"four named cameras"):
            check(bad)

    def test_short_controller_rejected(self):
        bad=copy.deepcopy(self.cfg);bad["control_phases"][-1]["last_frame"]=598
        with self.assertRaisesRegex(ValueError,"controller"):
            check(bad)

    def test_physical_claim_rejected(self):
        bad=copy.deepcopy(self.cfg);bad["physical_verified"]=True
        with self.assertRaisesRegex(ValueError,"physical or legal"):
            check(bad)
