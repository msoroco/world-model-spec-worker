from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_cameras import CAMERAS
from runner import PREFIX, check_config


def config(side="right"):
    case = PREFIX + "baseline_" + side
    return {"selected_case_id": case, "law_id": "NRS-484B-200-1",
            "cell_id": "C230259", "actor": "motor_vehicle_driver",
            "rate_hz": 20, "frames": 80, "duration_s": 4,
            "case": {"case_id": case, "recording_description": {"channels": []}},
            "cameras": [{"name": name, "width": profile[2][0],
                         "height": profile[2][1], "fov_deg": profile[3]}
                        for name, profile in CAMERAS.items()]}


class RunnerConfigTest(unittest.TestCase):
    def test_baseline_side_and_camera_contract(self):
        self.assertEqual(check_config(config("right")), "right")
        self.assertEqual(check_config(config("left")), "left")
        bad = config("left")
        bad["cameras"][1]["width"] = 320
        with self.assertRaisesRegex(ValueError, "profile differs"):
            check_config(bad)

    def test_exception_case_requires_separate_construction(self):
        bad = config()
        bad["selected_case_id"] = PREFIX + "three_lane_left"
        bad["case"]["case_id"] = bad["selected_case_id"]
        with self.assertRaisesRegex(ValueError, "only exact two-way baseline"):
            check_config(bad)


if __name__ == "__main__":
    unittest.main()
