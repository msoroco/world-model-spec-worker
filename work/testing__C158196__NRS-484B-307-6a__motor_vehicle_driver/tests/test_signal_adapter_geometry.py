"""CPU geometry checks for surveyed intersection entry calculations."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_carla_adapter import inside_polygon, signed_distance


class AdapterGeometryTest(unittest.TestCase):
    def test_polygon_entry_sign_and_boundary(self):
        polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
        self.assertFalse(inside_polygon(-2, 5, polygon))
        self.assertTrue(inside_polygon(2, 5, polygon))
        self.assertLess(signed_distance(-2, 5, polygon), 0)
        self.assertGreater(signed_distance(2, 5, polygon), 0)
        self.assertEqual(signed_distance(0, 5, polygon), 0)

    def test_degenerate_polygon_rejected(self):
        with self.assertRaisesRegex(ValueError, "degenerate"):
            signed_distance(2, 2, [[0, 0], [0, 0], [1, 1]])


if __name__ == "__main__":
    unittest.main()
