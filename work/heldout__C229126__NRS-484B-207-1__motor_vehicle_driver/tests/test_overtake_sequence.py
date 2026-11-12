import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "overtake_sequence.py"
SPEC = importlib.util.spec_from_file_location("c229126_overtake_sequence", MODULE)
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)
CONTROL_SPEC = importlib.util.spec_from_file_location(
    "c229126_overtake_controller", MODULE.with_name("overtake_controller.py"))
controller = importlib.util.module_from_spec(CONTROL_SPEC)
CONTROL_SPEC.loader.exec_module(controller)


def corners(x, y):
    return [[x - 1, y - .5], [x + 1, y - .5],
            [x + 1, y + .5], [x - 1, y + .5]]


def source(early=False):
    positions = [(-4, 0), (0, 2), (2.5, 1.7 if early else 2),
                 (3.5, 1.7 if early else 2), (4.5, 1.4), (5, 1)]
    rows = []
    for frame, (x, y) in enumerate(positions):
        rows.append({"frame": frame, "time_s": frame * .05,
                     "ego_id": "subject", "other_id": "overtaken",
                     "ego_lane_id": 1 if frame in (0, 5) else 2,
                     "other_lane_id": 1,
                     "road_tangent_xy": [1, 0], "ego_heading_xy": [1, 0],
                     "other_heading_xy": [1, 0], "ego_corners": corners(x, y),
                     "other_corners": corners(0, 0), "other_speed_mps": 4})
    return rows


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "participant_footprints.jsonl"

    def write(self, rows):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return measurement.measure(self.path)

    def test_complete_return_reports_original_body_gap_and_time_gap(self):
        result = self.write(source())
        self.assertEqual(result["first_return_frame"], 4)
        self.assertAlmostEqual(result["body_clearance_at_first_return_m"], 2.5)
        self.assertAlmostEqual(result["time_gap_at_first_return_s"], .625)
        self.assertTrue(result["all_abreast_left"])
        self.assertFalse(result["legal_acceptance_claimed"])

    def test_early_return_is_measured_without_legal_label(self):
        result = self.write(source(early=True))
        self.assertEqual(result["first_return_frame"], 2)
        self.assertAlmostEqual(result["body_clearance_at_first_return_m"], .5)

    def test_missing_original_and_wrong_direction_rejected(self):
        rows = source()
        del rows[2]["ego_corners"]
        with self.assertRaisesRegex(ValueError, "four-corner"):
            self.write(rows)
        rows = source()
        rows[1]["other_heading_xy"] = [-1, 0]
        with self.assertRaisesRegex(ValueError, "same direction"):
            self.write(rows)

    def test_missing_frame_rejected(self):
        rows = source()
        rows[2]["frame"] = 4
        with self.assertRaisesRegex(ValueError, "frame join"):
            self.write(rows)

    def test_full_return_to_right_lane_required(self):
        rows = source()
        rows[-1]["ego_lane_id"] = 2
        with self.assertRaisesRegex(ValueError, "return to right lane"):
            self.write(rows)

    def test_controlled_left_gap_and_return_order(self):
        wide = controller.target("left_pass_wide", passed_abreast=True,
                                 body_clearance_m=0, right_lane_id=1, left_lane_id=2)
        narrow = controller.target("left_pass_narrow", passed_abreast=True,
                                   body_clearance_m=0, right_lane_id=1, left_lane_id=2)
        self.assertEqual((wide["phase"], wide["lane_id"]), ("pass_left", 2))
        self.assertGreater(wide["target_left_gap_m"], narrow["target_left_gap_m"])
        before = controller.target("return_before_clear", passed_abreast=True,
                                   body_clearance_m=0, right_lane_id=1, left_lane_id=2)
        after = controller.target("return_after_clear", passed_abreast=True,
                                  body_clearance_m=0, right_lane_id=1, left_lane_id=2)
        self.assertEqual((before["phase"], before["lane_id"]), ("return_right", 1))
        self.assertEqual((after["phase"], after["lane_id"]), ("pass_left", 2))
        unpassed = controller.target("return_before_clear", passed_abreast=False,
                                     body_clearance_m=0, right_lane_id=1, left_lane_id=2)
        self.assertEqual(unpassed["phase"], "pass_left")


if __name__ == "__main__":
    unittest.main()
