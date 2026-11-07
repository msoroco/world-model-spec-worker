"""CPU check for post-tick Native speed measurement."""
import math
from types import SimpleNamespace
import unittest

from runner import observed_speed_mps


class Actor:
    def __init__(self, velocity):
        self.velocity = velocity

    def get_velocity(self):
        return self.velocity


class RunnerSpeedTests(unittest.TestCase):
    def test_observed_speed_reads_current_velocity(self):
        actor = Actor(SimpleNamespace(x=3.0, y=4.0, z=0.0))
        self.assertEqual(observed_speed_mps(actor), 5.0)
        actor.velocity = SimpleNamespace(x=0.0, y=0.0, z=2.0)
        self.assertEqual(observed_speed_mps(actor), 2.0)

    def test_nonfinite_velocity_rejected(self):
        actor = Actor(SimpleNamespace(x=math.nan, y=0.0, z=0.0))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            observed_speed_mps(actor)


if __name__ == '__main__':
    unittest.main()
