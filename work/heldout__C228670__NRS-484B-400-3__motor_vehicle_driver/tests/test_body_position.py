import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "body_position.py"
spec = importlib.util.spec_from_file_location("c228670_body_position", MODULE)
body_position = importlib.util.module_from_spec(spec)
spec.loader.exec_module(body_position)


SURVEY = {
    "approach_centerline_xy_m": [[0, -10], [0, 0]],
    "destination_left_curb_xy_m": [[0, -3], [-10, -3]],
}


def body(x, y, phase="approach"):
    return {"frame": 42, "phase": phase, "body_corners_xy_m": [
        [x - .5, y - 1], [x + .5, y - 1], [x + .5, y + 1], [x - .5, y + 1]]}


class PositionTests(unittest.TestCase):
    def test_measures_full_body_on_both_turn_legs(self):
        near = body_position.measure_frame(body(1.2, -6), SURVEY)
        farther = body_position.measure_frame(body(2.2, -6), SURVEY)
        self.assertTrue(near["all_corners_right_of_approach_centerline"])
        self.assertLess(min(farther["approach_centerline_signed_corner_offsets_m"]),
                        min(near["approach_centerline_signed_corner_offsets_m"]))
        destination = body_position.measure_frame(body(-5, -1.5, "departure"), SURVEY)
        self.assertEqual(destination["frame"], 42)
        self.assertGreater(destination["farthest_body_corner_from_departure_left_curb_m"], 0)

    def test_rejects_missing_corner_and_wrong_phase(self):
        value = body(1, -6)
        value["body_corners_xy_m"].pop()
        with self.assertRaisesRegex(ValueError, "four distinct"):
            body_position.measure_frame(value, SURVEY)
        with self.assertRaisesRegex(ValueError, "phase is unknown"):
            body_position.measure_frame(body(1, -6, "unknown"), SURVEY)
        value = body(1, -6)
        value["body_corners_xy_m"][0] = [float("nan"), 0]
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            body_position.measure_frame(value, SURVEY)


if __name__ == "__main__":
    unittest.main()
