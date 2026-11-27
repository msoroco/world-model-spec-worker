"""Authored lane topology checks; Native readback is a later local check."""
import unittest

from road_geometry import check, lane_centers


class GeometryTests(unittest.TestCase):
    def test_three_lanes_and_order(self):
        built = check()
        self.assertEqual(built["lane_ids"], [-1, -2, -3])
        centers = lane_centers()
        self.assertGreater(centers[-1], centers[-2])
        self.assertGreater(centers[-2], centers[-3])
        self.assertFalse(built["physical_realization_verified"])


if __name__ == "__main__":
    unittest.main()
