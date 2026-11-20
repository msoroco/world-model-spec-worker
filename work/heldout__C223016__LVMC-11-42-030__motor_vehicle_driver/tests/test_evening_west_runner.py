"""CPU checks for the contraflow variant of the governed reversible lane."""

import json
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
runner_path = HERE / ('runner_evening_west.py' if (HERE / 'runner_evening_west.py').is_file() else 'runner.py')
spec = importlib.util.spec_from_file_location('west_runner', runner_path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
check_config, _spawn_subject = runner.check_config, runner._spawn_subject


def config_path():
    return HERE / ('config-evening-west.json' if (HERE / 'config-evening-west.json').is_file() else 'config.json')


class ContraflowRunnerTests(unittest.TestCase):
    def test_case_identity_and_direction(self):
        config = json.loads(config_path().read_text())
        self.assertTrue(check_config(config))
        with self.assertRaisesRegex(ValueError, 'evening west-with'):
            check_config(dict(config, subject_direction_xy=[1, 0]))

    def test_native_spawn_rotates_on_same_governed_lane(self):
        config = json.loads(config_path().read_text())
        spawn = SimpleNamespace(location=SimpleNamespace(x=0, y=0, z=0),
                                rotation=SimpleNamespace(pitch=0, yaw=0, roll=0))
        second = SimpleNamespace(location=SimpleNamespace(x=20, y=0, z=0),
                                 rotation=SimpleNamespace(pitch=0, yaw=0, roll=0))
        road = SimpleNamespace(get_spawn_points=lambda: [spawn, second],
                               get_waypoint=lambda location: SimpleNamespace(lane_id=-1))
        poses = []
        world = SimpleNamespace(get_map=lambda: road,
                                get_blueprint_library=lambda: SimpleNamespace(filter=lambda _: ['vehicle']),
                                try_spawn_actor=lambda bp, pose: poses.append(pose) or 'subject')
        carla = SimpleNamespace(Rotation=lambda **kwargs: SimpleNamespace(**kwargs),
                                Transform=lambda location, rotation: SimpleNamespace(
                                    location=location, rotation=rotation))
        self.assertEqual(_spawn_subject(world, carla, config), 'subject')
        self.assertEqual(poses[0].rotation.yaw, 180)
        expected = [spawn, second][config['spawn_candidate_index']]
        self.assertIs(poses[0].location, expected.location)


if __name__ == '__main__':
    unittest.main()
