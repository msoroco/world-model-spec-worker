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

    def test_missing_camera(self):
        changed = copy.deepcopy(self.config)
        changed["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four source cameras"):
            check(changed)

    def test_short_window(self):
        changed = copy.deepcopy(self.config)
        changed["duration_frames"] = 599
        with self.assertRaisesRegex(ValueError, "30-second"):
            check(changed)

    def test_wrong_stop_policy(self):
        changed = copy.deepcopy(self.config)
        changed["stop_policy"] = "other"
        with self.assertRaisesRegex(ValueError, "stop policy"):
            check(changed)

    def test_crosswalk_changes_branch(self):
        changed = copy.deepcopy(self.config)
        changed["near_crosswalk_present"] = True
        with self.assertRaisesRegex(ValueError, "stop-line branch"):
            check(changed)
