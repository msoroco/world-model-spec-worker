import copy
import json
import unittest
from pathlib import Path
from runner import check


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_window(self):
        self.assertEqual(check(self.config)["frames"], 600)

    def test_missing_source_camera_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four source cameras"):
            check(changed)

    def test_short_window_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["duration_frames"] = 599
        with self.assertRaisesRegex(ValueError, "30-second"):
            check(changed)

    def test_changed_comparison_variable_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["entry_release_s"] += 1
        with self.assertRaisesRegex(ValueError, "entry release"):
            check(changed)

    def test_physical_claim_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["physical_verified"] = True
        with self.assertRaisesRegex(ValueError, "physical or legal"):
            check(changed)
