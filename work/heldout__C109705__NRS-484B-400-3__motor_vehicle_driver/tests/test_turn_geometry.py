import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_geometry import measure_turn_position


def rotate(point, angle):
    x, y = point
    return [x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle)]


class LeftTurnGeometryTests(unittest.TestCase):
    def test_directional_right_half_and_curb_distance(self):
        corners = [[0.5, -1], [1.5, -1], [1.5, -2], [0.5, -2]]
        base = dict(approach_centerline=[[0, -10], [0, 0]],
                    destination_left_curb=[[0, -3], [-10, -3]],
                    intersection_entry=[0, 0])
        measured = measure_turn_position(corners, **base)
        self.assertTrue(measured["approach_all_corners_right_of_centerline"])
        self.assertEqual(measured["approach_signed_corner_offsets_m"], [-0.5, -1.5, -1.5, -0.5])
        self.assertEqual(len(measured["destination_curb_corner_distances_m"]), 4)
        for angle in (math.pi / 2, math.pi):
            rotated = measure_turn_position(
                [rotate(point, angle) for point in corners],
                approach_centerline=[rotate(point, angle) for point in base["approach_centerline"]],
                destination_left_curb=[rotate(point, angle) for point in base["destination_left_curb"]],
                intersection_entry=rotate(base["intersection_entry"], angle))
            self.assertTrue(rotated["approach_all_corners_right_of_centerline"])
            for got, expected in zip(rotated["approach_signed_corner_offsets_m"],
                                     measured["approach_signed_corner_offsets_m"]):
                self.assertAlmostEqual(got, expected)

    def test_crossing_and_bad_sources_rejected(self):
        base = dict(approach_centerline=[[0, -10], [0, 0]],
                    destination_left_curb=[[0, -3], [-10, -3]],
                    intersection_entry=[0, 0])
        crossing = [[-1, -1], [1, -1], [1, -2], [-1, -2]]
        self.assertFalse(measure_turn_position(crossing, **base)[
            "approach_all_corners_right_of_centerline"])
        with self.assertRaisesRegex(ValueError, "entry is not on"):
            measure_turn_position(crossing, **dict(base, intersection_entry=[1, 0]))
        with self.assertRaisesRegex(ValueError, "Degenerate"):
            measure_turn_position(crossing, **dict(base, approach_centerline=[[0, 0], [0, 0]]))
        with self.assertRaisesRegex(ValueError, "four distinct"):
            measure_turn_position([[0, 0]] * 4, **base)


if __name__ == "__main__":
    unittest.main()
