"""The speed fallback changes the actual CARLA control input near target speed."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from native_construction import control_step  # noqa: E402


class Actor:
    def __init__(self):
        self.controls = []

    def get_location(self):
        return NS(x=0.0, y=0.0, z=0.0)

    def get_velocity(self):
        return NS(x=8.0, y=0.0, z=0.0)

    def get_transform(self):
        return NS(rotation=NS(yaw=0.0))

    def apply_control(self, control):
        self.controls.append(control)


class Carla:
    @staticmethod
    def VehicleControl(**fields):
        return NS(**fields)


class SpeedFallbackTest(unittest.TestCase):
    def test_target_speed_changes_bounded_throttle(self):
        primary, fallback = Actor(), Actor()
        route = [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0]]
        control_step(Carla, primary, route, 1.0, 0.0, 8.0)
        control_step(Carla, fallback, route, 1.0, 0.0, 9.5)
        self.assertEqual(primary.controls[0].throttle, 0.0)
        self.assertGreater(fallback.controls[0].throttle, 0.0)
        self.assertLessEqual(fallback.controls[0].throttle, .55)


if __name__ == '__main__':
    unittest.main()
