import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from intersection_geometry import Box, target_pose
from stop_controller import command, front_gap


class StopControllerTests(unittest.TestCase):
    def setUp(self):
        self.boundary = Box(-8, -8, 8, 8)

    def test_each_approach_brakes_at_target(self):
        for approach in ("east", "west", "north", "south"):
            with self.subTest(approach=approach):
                x, y, heading = target_pose(self.boundary, approach, 4.0, 4.5, 1.8)
                self.assertAlmostEqual(front_gap(self.boundary, approach, x, y, heading, 4.5), 4.0)
                near = command(self.boundary, approach, x, y, heading, 3.0, 4.5, 4.0)
                self.assertEqual(near.throttle, 0)
                self.assertGreater(near.brake, 0)
                halted = command(self.boundary, approach, x, y, heading, 0.0, 4.5, 4.0)
                self.assertEqual(halted.brake, 1.0)

    def test_far_approach_requests_motion(self):
        x, y, h = target_pose(self.boundary, "east", 40.0, 4.5, 1.8)
        requested = command(self.boundary, "east", x, y, h, 5.0, 4.5, 4.0)
        self.assertGreater(requested.throttle, 0)
        self.assertEqual(requested.brake, 0)

    def test_wrong_heading_and_invalid_motion_rejected(self):
        with self.assertRaisesRegex(ValueError, "aligned"):
            command(self.boundary, "east", 20, 0, 0, 5, 4.5, 4)
        with self.assertRaisesRegex(ValueError, "Invalid motion"):
            command(self.boundary, "east", 20, 0, 180, -1, 4.5, 4)


if __name__ == "__main__":
    unittest.main()
