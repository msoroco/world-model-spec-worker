import json
from pathlib import Path
import unittest

from runner import check


ROOT = Path(__file__).resolve().parents[1]


class SelectedRunnerTest(unittest.TestCase):
    def test_camera_and_duration_profile(self):
        config = json.loads((ROOT / "config.json").read_text())
        result = check(config)
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["simulation_started"])

    def test_wrong_camera_rejected(self):
        config = json.loads((ROOT / "config.json").read_text())
        config["cameras"][2]["name"] = "rear"
        with self.assertRaisesRegex(ValueError, "four-camera profile"):
            check(config)


if __name__ == "__main__":
    unittest.main()
