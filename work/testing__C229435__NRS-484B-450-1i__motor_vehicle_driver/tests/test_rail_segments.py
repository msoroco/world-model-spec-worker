"""Guard the nearest-rail geometry against collinear false overlap."""
import unittest

from rail_proximity import _segment_distance


class SegmentDistanceTests(unittest.TestCase):
    def test_separated_collinear_segments(self):
        self.assertEqual(_segment_distance([0, 0], [1, 0], [3, 0], [4, 0]), 2)

    def test_overlapping_collinear_segments(self):
        self.assertEqual(_segment_distance([0, 0], [3, 0], [2, 0], [4, 0]), 0)


if __name__ == '__main__':
    unittest.main()
