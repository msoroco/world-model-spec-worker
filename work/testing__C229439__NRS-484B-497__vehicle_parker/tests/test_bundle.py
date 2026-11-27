import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_oneway import CAMERAS, control, phase_for
from runner import selected_config


class BundleTests(unittest.TestCase):
    def test_exact_selected_case_and_camera_profile(self):
        cfg = selected_config()
        self.assertEqual(cfg["case"]["case_id"], cfg["selected_case_id"])
        self.assertEqual(cfg["rate_hz"], 20)
        self.assertEqual(cfg["duration_s"], 20)
        self.assertEqual([(v["name"], v["width"], v["height"]) for v in cfg["cameras"]],
                         list(CAMERAS))

    def test_activity_controller_is_executable_without_carla(self):
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        activity = cfg["case"]["requested_activity"]
        self.assertEqual(phase_for(activity, False, 0, 400), "approach")
        self.assertEqual(phase_for(activity, True, 0, 400), "hold")
        self.assertGreaterEqual(control(1, 3, "approach", activity,
                                        cfg["engineering_brake_gain"])["brake"], 0)


if __name__ == "__main__":
    unittest.main()
