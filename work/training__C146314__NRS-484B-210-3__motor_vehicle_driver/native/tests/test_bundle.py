"""Materialized exact right-pass construction checks."""
import unittest

import geometry
import necessity
import runner


class RightPassBundleTest(unittest.TestCase):
    def test_authored_road_and_routes(self):
        checked = runner.check()
        self.assertEqual(checked['frames'], 600)
        self.assertEqual(geometry.check()['paved_driving_lanes'], [-1, -2])
        self.assertTrue(necessity.check()['paved_case']['feasible'])
        self.assertFalse(necessity.check()['shoulder_case']['feasible'])
        self.assertEqual(len(checked['camera_names']), 4)


if __name__ == '__main__':
    unittest.main()
