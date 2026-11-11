import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "lane_footprint.py"
SPEC = importlib.util.spec_from_file_location("lane_footprint", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FootprintTests(unittest.TestCase):
    def test_inside_and_crossing_in_both_travel_directions(self):
        forward_lane = [(0, 0), (20, 0), (20, 3), (0, 3)]
        reverse_lane = list(reversed(forward_lane))
        inside_body = [(4, 1), (6, 1), (6, 2), (4, 2)]
        crossing_body = [(4, 2.5), (6, 2.5), (6, 3.5), (4, 3.5)]
        for lane in (forward_lane, reverse_lane):
            with self.subTest(lane=lane):
                self.assertTrue(MODULE.measure_footprint(lane, inside_body)["full_footprint_inside"])
                crossing = MODULE.measure_footprint(lane, crossing_body)
                self.assertFalse(crossing["full_footprint_inside"])
                self.assertTrue(crossing["boundary_crossing"])
                self.assertLess(crossing["minimum_corner_clearance_m"], 0)

    def test_missing_or_invalid_geometry_is_rejected(self):
        lane = [(0, 0), (4, 0), (4, 3), (0, 3)]
        with self.assertRaises(ValueError):
            MODULE.measure_footprint(lane, [(1, 1)])
        with self.assertRaises(ValueError):
            MODULE.measure_footprint([(0, 0), (0, 0), (4, 3)], [(1, 1)] * 4)


if __name__ == "__main__":
    unittest.main()
