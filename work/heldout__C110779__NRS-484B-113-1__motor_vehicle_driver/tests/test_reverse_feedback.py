import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reverse_feedback import command


class ReverseFeedbackTests(unittest.TestCase):
    def test_reverse_speed_feedback_and_stop(self):
        target = (-5, 0)
        accelerating = command((0, 0), 0, 0, target, 2)
        self.assertTrue(accelerating['reverse'])
        self.assertGreater(accelerating['throttle'], 0)
        self.assertEqual(accelerating['brake'], 0)
        slowing = command((0, 0), 0, -4, target, 2)
        self.assertGreater(slowing['brake'], 0)
        self.assertEqual(slowing['throttle'], 0)
        stopped = command((-4.8, 0), 0, -1, target, 2)
        self.assertTrue(stopped['target_reached'])
        self.assertEqual(stopped['brake'], 1)

    def test_reverse_steering_sign_and_geometry_rejection(self):
        left_behind = command((0, 0), 0, 0, (-5, 1), 2)
        right_behind = command((0, 0), 0, 0, (-5, -1), 2)
        self.assertGreater(left_behind['steer'], 0)
        self.assertLess(right_behind['steer'], 0)
        with self.assertRaisesRegex(ValueError, 'positive'):
            command((0, 0), 0, 0, (-5, 0), 0)
        with self.assertRaisesRegex(ValueError, 'Finite'):
            command((0, 0), math.nan, 0, (-5, 0), 2)


if __name__ == '__main__':
    unittest.main()
