"""Footprint checks for original Native lane occupancy readback."""

import importlib.util
import unittest
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "center_lane_geometry.py"
spec = importlib.util.spec_from_file_location("center_lane_geometry_3b", path)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


LANE = [(0, -2), (100, -2), (100, 2), (0, 2)]


def body(x, y, *, reverse=False):
    corners = [(x - 2, y - 0.8), (x + 2, y - 0.8),
               (x + 2, y + 0.8), (x - 2, y + 0.8)]
    if reverse:
        corners.reverse()
    return [(a, b, z) for z in (0, 1.5) for a, b in corners]


class OriginalBodyGeometryTests(unittest.TestCase):
    def test_full_partial_and_absent_occupancy_from_either_heading(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.assertEqual(geometry.body_occupancy(LANE, body(40, 0, reverse=reverse)), {
                    "body_overlaps_center_lane": True, "body_within_center_lane": True})
                self.assertEqual(geometry.body_occupancy(LANE, body(40, 2.5, reverse=reverse)), {
                    "body_overlaps_center_lane": True, "body_within_center_lane": False})
                self.assertEqual(geometry.body_occupancy(LANE, body(40, 8, reverse=reverse)), {
                    "body_overlaps_center_lane": False, "body_within_center_lane": False})

    def test_separated_collinear_edges_do_not_intersect(self):
        self.assertFalse(geometry.body_occupancy(LANE, body(120, 0))["body_overlaps_center_lane"])

    def test_rejects_missing_or_nonfinite_original_geometry(self):
        with self.assertRaisesRegex(ValueError, "eight original"):
            geometry.body_occupancy(LANE, body(40, 0)[:7])
        bad = body(40, 0)
        bad[0] = (float("nan"), 0, 0)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            geometry.body_occupancy(LANE, bad)


if __name__ == "__main__":
    unittest.main()
