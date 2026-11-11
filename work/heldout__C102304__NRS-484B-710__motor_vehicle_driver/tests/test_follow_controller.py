import importlib.util
import math
import unittest
from pathlib import Path
from types import SimpleNamespace


path = Path(__file__).resolve().parents[1] / "follow_controller.py"
spec = importlib.util.spec_from_file_location("follow_controller", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def vector(x, y):
    return SimpleNamespace(x=x, y=y)


class Actor:
    def __init__(self, x, y, direction, speed):
        self.location = vector(x, y)
        self.direction = direction
        self.velocity = vector(direction * speed, 0)
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2))
        self.last_control = None

    def get_transform(self):
        return SimpleNamespace(location=self.location,
                               get_forward_vector=lambda: vector(self.direction, 0))

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.last_control = control


class FakeCarla:
    @staticmethod
    def VehicleControl(**kwargs):
        return SimpleNamespace(**kwargs)


class ControllerTests(unittest.TestCase):
    def test_both_approach_directions_apply_control_at_commanded_gap(self):
        distance = 4 + 500 / module.FEET_PER_METRE
        for direction in (1, -1):
            with self.subTest(direction=direction):
                ego = Actor(0, 0, direction, 7)
                apparatus = Actor(direction * distance, 0, direction, 8)
                measured = module.control_step(ego, apparatus, carla_module=FakeCarla)
                self.assertAlmostEqual(measured["projected_gap_m"], 500 / module.FEET_PER_METRE)
                self.assertGreater(ego.last_control.throttle, 0)
                self.assertEqual(ego.last_control.steer, 0)

    def test_short_gap_brakes_and_misaligned_actors_fail(self):
        ego, apparatus = Actor(0, 0, 1, 12), Actor(100, 0, 1, 8)
        measured = module.control_step(ego, apparatus, carla_module=FakeCarla)
        self.assertEqual(ego.last_control.throttle, 0)
        self.assertGreater(ego.last_control.brake, 0)
        self.assertLess(measured["gap_error_m"], 0)
        apparatus.direction = -1
        with self.assertRaisesRegex(ValueError, "aligned travel"):
            module.control_step(ego, apparatus, carla_module=FakeCarla)

    def test_rejects_nonfollowing_geometry_and_invalid_command(self):
        ego, apparatus = Actor(0, 0, 1, 8), Actor(160, 4, 1, 8)
        with self.assertRaisesRegex(ValueError, "following lane"):
            module.control_step(ego, apparatus, carla_module=FakeCarla)
        apparatus.location.y = 0
        with self.assertRaisesRegex(ValueError, "finite"):
            module.control_step(ego, apparatus, target_gap_ft=math.nan,
                                carla_module=FakeCarla)


if __name__ == "__main__":
    unittest.main()
