import importlib.util
from pathlib import Path
from types import SimpleNamespace as N
import unittest

path = Path(__file__).resolve().parents[1] / "stopped_controller.py"
spec = importlib.util.spec_from_file_location("stopped_controller", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Actor:
    def __init__(self, x, speed=0):
        self.x, self.speed, self.command = x, speed, None

    def get_transform(self):
        return N(location=N(x=self.x, y=0),
                 get_forward_vector=lambda: N(x=1, y=0))

    def get_velocity(self):
        return N(x=self.speed, y=0)

    def apply_control(self, command):
        self.command = command


class StoppedApproachTests(unittest.TestCase):
    def test_approach_and_braking_requests(self):
        carla = N(VehicleControl=lambda **kw: N(**kw))
        ego, apparatus = Actor(0), Actor(160)
        first = module.approach_step(ego, apparatus, carla_module=carla)
        self.assertGreater(first["throttle"], 0)
        self.assertEqual(apparatus.command, None)
        ego.x = 151
        second = module.approach_step(ego, apparatus, carla_module=carla)
        self.assertEqual(second["throttle"], 0)
        self.assertGreater(second["brake"], 0)

    def test_rejects_wrong_approach_geometry(self):
        carla = N(VehicleControl=lambda **kw: N(**kw))
        with self.assertRaisesRegex(ValueError, "not ahead"):
            module.approach_step(Actor(0), Actor(-1), carla_module=carla)


if __name__ == "__main__":
    unittest.main()
