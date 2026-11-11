import importlib.util
from pathlib import Path
from types import SimpleNamespace as N
import unittest

path = Path(__file__).resolve().parents[1] / 'park_controller.py'
spec = importlib.util.spec_from_file_location('park_controller', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Actor:
    def __init__(self, x, speed=0):
        self.x, self.speed, self.command = x, speed, None

    def get_transform(self):
        return N(location=N(x=self.x, y=0), get_forward_vector=lambda: N(x=1, y=0))

    def get_velocity(self):
        return N(x=self.speed, y=0)

    def apply_control(self, value):
        self.command = value


class ParkingControllerTests(unittest.TestCase):
    def test_approach_stop_and_handbrake_requests(self):
        carla = N(VehicleControl=lambda **kw: N(**kw))
        ego, apparatus = Actor(0), Actor(160)
        self.assertFalse(module.park_step(ego, apparatus, carla_module=carla)['parking_requested'])
        self.assertGreater(ego.command.throttle, 0)
        ego.x = 160 - 500 / module.FEET_PER_METRE
        ego.speed = 2
        self.assertFalse(module.park_step(ego, apparatus, carla_module=carla)['parking_requested'])
        self.assertGreater(ego.command.brake, 0)
        ego.speed = 0
        self.assertTrue(module.park_step(ego, apparatus, carla_module=carla)['parking_requested'])
        self.assertTrue(ego.command.hand_brake)

    def test_rejects_wrong_lane_position(self):
        with self.assertRaisesRegex(ValueError, 'not ahead'):
            module.park_step(Actor(5), Actor(0), carla_module=N(VehicleControl=lambda **kw: N(**kw)))


if __name__ == '__main__':
    unittest.main()
