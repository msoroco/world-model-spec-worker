import importlib.util
import math
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


spec = importlib.util.spec_from_file_location('truck_follow_controller', Path(__file__).resolve().parents[1] / 'truck_follow_controller.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class FakeTruck:
    def __init__(self, x, y):
        self.x, self.y, self.speed, self.heading, self.last = x, y, 0.0, 0.0, None

    def get_velocity(self):
        return NS(x=self.speed * math.cos(self.heading), y=self.speed * math.sin(self.heading))

    def get_transform(self):
        return NS(location=NS(x=self.x, y=self.y), get_forward_vector=lambda: NS(x=math.cos(self.heading), y=math.sin(self.heading)))

    def apply_control(self, control):
        self.last = control

    def integrate_assumed(self):
        assert self.last is not None
        self.speed = max(0.0, self.speed + (2.0 * self.last.throttle - 4.0 * self.last.brake - 0.03 * self.speed) * policy.DT_S)
        self.heading += self.last.steer * 0.25 * policy.DT_S
        self.x += self.speed * math.cos(self.heading) * policy.DT_S
        self.y += self.speed * math.sin(self.heading) * policy.DT_S


class ControllerTests(unittest.TestCase):
    def test_pair_policy_preserves_gap_in_assumed_symmetric_dynamics(self):
        ego, lead = FakeTruck(100, -1.9), FakeTruck(262.4, -1.9)
        for _ in range(900):
            policy.apply_pair(ego, lead, lambda **kw: NS(**kw))
            ego.integrate_assumed(); lead.integrate_assumed()
        self.assertGreater(ego.speed, 10)
        self.assertLess(abs(lead.x - ego.x - 162.4), 0.01)
        self.assertLess(abs(ego.y + 1.9), 0.01)
        self.assertLess(abs(lead.y + 1.9), 0.01)

    def test_lateral_and_speed_errors_drive_control(self):
        actor = FakeTruck(100, -1.0)
        first = policy.command(actor)
        self.assertGreater(first['throttle'], 0)
        self.assertLess(first['steer'], 0)
        actor.speed = 18
        second = policy.command(actor)
        self.assertEqual(second['throttle'], 0)
        self.assertGreater(second['brake'], 0)
        with self.assertRaisesRegex(ValueError, 'target speed'):
            policy.command(actor, float('nan'))


if __name__ == '__main__':
    unittest.main()
