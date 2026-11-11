import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


path = Path(__file__).resolve().parents[1] / "stopped_controller.py"
spec = importlib.util.spec_from_file_location("stopped_controller", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def vector(x, y):
    return SimpleNamespace(x=x, y=y)


class Actor:
    def __init__(self, x, y, direction, speed):
        self.location = vector(x, y)
        self.direction = direction
        self.velocity = vector(direction * speed, 0)
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


class StoppedControllerTests(unittest.TestCase):
    def test_both_directions_and_below_at_above_targets(self):
        for direction in (1, -1):
            for target in (450, 500, 550):
                with self.subTest(direction=direction, target=target):
                    ego = Actor(0, 0, direction, 4)
                    apparatus = Actor(direction * (target / module.FEET_PER_METRE + 12), 0,
                                      direction, 0)
                    result = module.control_step(ego, apparatus, target_centre_ft=target,
                                                 carla_module=FakeCarla)
                    self.assertGreater(result["distance_error_m"], 0)
                    self.assertGreater(ego.last_control.throttle, 0)
                    self.assertFalse(ego.last_control.hand_brake)

    def test_parking_requires_target_and_low_speed(self):
        ego = Actor(0, 0, 1, 2)
        apparatus = Actor(500 / module.FEET_PER_METRE, 0, 1, 0)
        result = module.control_step(ego, apparatus, target_centre_ft=500, park=True,
                                     carla_module=FakeCarla)
        self.assertFalse(result["parked_command"])
        self.assertGreater(ego.last_control.brake, 0)
        ego.velocity = vector(0, 0)
        result = module.control_step(ego, apparatus, target_centre_ft=500, park=True,
                                     carla_module=FakeCarla)
        self.assertTrue(result["parked_command"])
        self.assertTrue(ego.last_control.hand_brake)

    def test_rejects_wrong_lane_moving_apparatus_and_bad_target(self):
        ego, apparatus = Actor(0, 0, 1, 4), Actor(160, 4, 1, 0)
        with self.assertRaisesRegex(ValueError, "approach lane"):
            module.control_step(ego, apparatus, target_centre_ft=500, carla_module=FakeCarla)
        apparatus.location.y = 0
        apparatus.velocity = vector(1, 0)
        with self.assertRaisesRegex(ValueError, "stationary apparatus"):
            module.control_step(ego, apparatus, target_centre_ft=500, carla_module=FakeCarla)
        apparatus.velocity = vector(0, 0)
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            module.control_step(ego, apparatus, target_centre_ft=0, carla_module=FakeCarla)


if __name__ == "__main__":
    unittest.main()
