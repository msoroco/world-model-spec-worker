import math
import unittest

from drive import command
from layout import planned_pose


class PhysicalControllerTests(unittest.TestCase):
    def test_turn_steers_toward_curved_target(self):
        x, y, yaw = planned_pose(100, True)
        control = command(100, True, (x, y), yaw, 2.6)
        self.assertGreater(control['steer'], 0)
        self.assertLessEqual(control['steer'], 1)
        self.assertEqual(control['target_speed_mps'], 2.6)

    def test_straight_controller_keeps_heading(self):
        x, y, yaw = planned_pose(50, False)
        control = command(50, False, (x, y), yaw, 3.0)
        self.assertAlmostEqual(control['steer'], 0)

    def test_terminal_braking(self):
        x, y, yaw = planned_pose(599, True)
        control = command(599, True, (x, y), yaw, 0.2)
        self.assertEqual(control['throttle'], 0)
        self.assertGreater(control['brake'], 0)

    def test_nonfinite_motion_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            command(100, True, (math.nan, 0), 0, 2.0)
