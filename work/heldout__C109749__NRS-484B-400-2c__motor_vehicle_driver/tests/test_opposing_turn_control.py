import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('opposing_turn_control', ROOT / 'opposing_turn_control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def distance(self, other):
        return ((self.x-other.x)**2 + (self.y-other.y)**2)**0.5


class Actor:
    def __init__(self, x, y, yaw):
        self.location = Point(x, y)
        self.yaw = yaw

    def get_location(self):
        return self.location

    def get_transform(self):
        return SimpleNamespace(location=self.location, rotation=SimpleNamespace(yaw=self.yaw))

    def get_velocity(self):
        return SimpleNamespace(x=0.0, y=0.0)


def path(points):
    return [SimpleNamespace(transform=SimpleNamespace(location=Point(*xy))) for xy in points]


class TwoActorControlTests(unittest.TestCase):
    def test_both_approaches_receive_bounded_turn_commands(self):
        actors = [Actor(-4, 0, 0), Actor(4, 0, 180)]
        paths = [path([(-4, 0), (-2, 0), (0, 0), (0, 4)]),
                 path([(4, 0), (2, 0), (0, 0), (0, -4)])]
        indices, commands = control.command_pair(actors, paths, [0, 0], 0)
        self.assertEqual(indices, [1, 1])
        self.assertTrue(all(0 < row['throttle'] <= 0.45 for row in commands))
        self.assertTrue(all(-0.75 <= row['steer'] <= 0.75 for row in commands))

    def test_small_delayed_release_is_explicit_and_bounded(self):
        actors = [Actor(-4, 0, 0), Actor(4, 0, 180)]
        paths = [path([(-4, 0), (-2, 0), (0, 0)]),
                 path([(4, 0), (2, 0), (0, 0)])]
        _, commands = control.command_pair(actors, paths, [0, 0], 0, start_delays=(0, 2))
        self.assertEqual(commands[1], {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0})
        _, commands = control.command_pair(actors, paths, [0, 0], 2, start_delays=(0, 2))
        self.assertGreater(commands[1]['throttle'], 0)
        with self.assertRaisesRegex(ValueError, 'start delay'):
            control.command_pair(actors, paths, [0, 0], 0, start_delays=(0, 10))


if __name__ == '__main__':
    unittest.main()
