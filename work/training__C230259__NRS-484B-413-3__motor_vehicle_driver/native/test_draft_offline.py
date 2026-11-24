import copy
import json
import unittest
from pathlib import Path
from runner import check


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_window(self):
        self.assertEqual(check(self.config)["frames"], 600)

    def test_camera_missing(self):
        bad = copy.deepcopy(self.config); bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "four named cameras"):
            check(bad)

    def test_signal_timing(self):
        bad = copy.deepcopy(self.config); bad["control_phases"][1]["signal_request"] = "none"
        with self.assertRaisesRegex(ValueError, "prior warning"):
            check(bad)

    def test_short_window(self):
        bad = copy.deepcopy(self.config); bad["control_phases"][-1]["last_frame"] = 598
        with self.assertRaisesRegex(ValueError, "controller phases"):
            check(bad)

    def test_physical_claim(self):
        bad = copy.deepcopy(self.config); bad["physical_verified"] = True
        with self.assertRaisesRegex(ValueError, "physical or legal"):
            check(bad)
