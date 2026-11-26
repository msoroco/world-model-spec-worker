"""Static checks run without importing CARLA or starting a server."""
import copy
import json
import unittest
from pathlib import Path

from capture import check


class CaptureCheckTest(unittest.TestCase):
    def setUp(self):
        direct = Path(__file__).parent.parent / "config.json"
        if direct.is_file():
            config_text = direct.read_text()
        else:
            construction = json.loads(Path(__file__).with_name(
                "condition_a-construction.json").read_text())
            config_text = next(item["content"] for item in construction["files"]
                               if item["path"] == "config.json")
        self.config = json.loads(config_text)

    def test_exact_case(self):
        self.assertEqual(check(self.config)["case_id"], self.config["case_id"])
        self.assertFalse(check(self.config)["physical_acceptance_claimed"])

    def test_short_capture_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["duration_frames"] = 599
        with self.assertRaisesRegex(ValueError, "600-frame"):
            check(changed)

    def test_changed_release_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["turn_release_s"] = 12
        with self.assertRaisesRegex(ValueError, "turn policy"):
            check(changed)

    def test_missing_view_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named Native cameras"):
            check(changed)


if __name__ == "__main__":
    unittest.main()
