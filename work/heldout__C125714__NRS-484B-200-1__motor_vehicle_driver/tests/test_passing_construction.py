import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from passing_construction import spawn_lead, lead_control, subject_passing_control


def waypoint(x):
    location = SimpleNamespace(x=x, y=0, z=0)
    return SimpleNamespace(transform=SimpleNamespace(location=location,
        get_forward_vector=lambda: SimpleNamespace(x=1, y=0)))


class FakeActor:
    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=0, y=0),
                               get_forward_vector=lambda: SimpleNamespace(x=1, y=0))

    def get_velocity(self):
        return SimpleNamespace(x=2, y=0)


class PassingConstructionTests(unittest.TestCase):
    def test_spawns_lead_ahead_and_controls_two_speeds(self):
        route = [waypoint(i*2.5) for i in range(13)]
        calls = []
        world = SimpleNamespace(
            get_blueprint_library=lambda: SimpleNamespace(find=lambda name: name),
            try_spawn_actor=lambda blueprint, transform: calls.append((blueprint, transform)) or FakeActor())
        lead = spawn_lead(world, route)
        self.assertIs(calls[0][1], route[3].transform)
        self.assertGreater(lead_control(lead, route, 0)['throttle'], 0)
        self.assertGreater(subject_passing_control(lead, (10, 1))['throttle'],
                           lead_control(lead, route, 0)['throttle'])

    def test_rejects_short_or_wrong_order_route(self):
        world = SimpleNamespace()
        with self.assertRaisesRegex(ValueError, 'route lacks'):
            spawn_lead(world, [waypoint(i*2.5) for i in range(5)])
        with self.assertRaisesRegex(ValueError, 'not ahead'):
            spawn_lead(world, [waypoint(-i*2.5) for i in range(13)])


if __name__ == '__main__':
    unittest.main()
