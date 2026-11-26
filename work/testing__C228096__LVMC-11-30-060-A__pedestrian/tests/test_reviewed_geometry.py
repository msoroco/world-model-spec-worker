"""CPU protocol checks for reviewed crossing-point polygon exclusion."""
import unittest

from reviewed_site import _inside


class ReviewedCrossingGeometryTests(unittest.TestCase):
    def test_roadway_point_inside(self):
        polygon = [[0, 0], [12, 0], [12, 8], [0, 8]]
        self.assertTrue(_inside([6, 4], polygon))

    def test_crosswalk_point_outside(self):
        polygon = [[0, 0], [2, 0], [2, 8], [0, 8]]
        self.assertFalse(_inside([6, 4], polygon))

    def test_bad_polygon_rejected(self):
        with self.assertRaisesRegex(ValueError, 'polygon'):
            _inside([1, 1], [[0, 0], [1, 1]])


if __name__ == '__main__':
    unittest.main()
