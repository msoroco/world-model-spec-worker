import copy
import json
import unittest
from pathlib import Path
from runner import check


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_full_window(self):
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

    def test_changed_speed(self):
        changed = copy.deepcopy(self.config)
        changed["speed_request_mph"] += 1
        with self.assertRaisesRegex(ValueError, "speed or exception context"):
            check(changed)

    def test_changed_exception_context(self):
        changed = copy.deepcopy(self.config)
        changed["planned_context"] = "unknown"
        with self.assertRaisesRegex(ValueError, "speed or exception context"):
            check(changed)

    def test_fabricated_context(self):
        changed = copy.deepcopy(self.config)
        changed["calendar_verified"] = True
        with self.assertRaisesRegex(ValueError, "exception context"):
            check(changed)
