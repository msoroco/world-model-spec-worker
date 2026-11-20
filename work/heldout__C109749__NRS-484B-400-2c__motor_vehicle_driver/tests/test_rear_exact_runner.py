import json
import unittest
from pathlib import Path
from types import SimpleNamespace as S

from opposing_turn_rear_runner import check_config, device_inventory, rear_controls


class RearRunnerTests(unittest.TestCase):
    def test_selected_release_policy_controls_both_approaches(self):
        class Point:
            def __init__(self, x, y):
                self.x, self.y = x, y

            def distance(self, other):
                return ((self.x-other.x)**2 + (self.y-other.y)**2)**0.5

        class Actor:
            def __init__(self, x, yaw):
                self.location, self.yaw = Point(x, 0), yaw

            def get_location(self):
                return self.location

            def get_transform(self):
                return S(location=self.location, rotation=S(yaw=self.yaw))

            def get_velocity(self):
                return S(x=0., y=0.)

        def path(xs):
            return [S(transform=S(location=Point(x, 0))) for x in xs]

        actors = [Actor(-4, 0), Actor(4, 180)]
        paths = [path((-4, -2, 0)), path((4, 2, 0))]
        _, early = rear_controls(actors, paths, [0, 0], 0, 5.)
        self.assertEqual(early[0], {'throttle': 0., 'brake': 1., 'steer': 0.})
        self.assertGreater(early[1]['throttle'], 0.)
        _, released = rear_controls(actors, paths, [0, 0], 2, 5.)
        self.assertGreater(released[0]['throttle'], 0.)
        self.assertGreater(released[1]['throttle'], 0.)
        self.assertTrue(all(abs(row['steer']) <= .75 for row in released))

    def test_exact_rear_config_and_scope(self):
        local = Path(__file__).resolve().parents[1]
        source = local / 'config-rear_pass_no_device.json'
        config = json.loads((source if source.exists() else local / 'config.json').read_text())
        self.assertEqual(check_config(config), (
            float(config.get('route_step_m', 2.)),
            float(config.get('target_speed_mps', 5.)),
            float(config.get('overview_height_delta_m', 0.))))
        self.assertEqual(config['rear_policy']['subject_release_delay_ticks'], 2)
        config['selected_case_id'] = config['selected_case_id'].replace(
            '__rear_pass_no_device', '__front_pass_no_device')
        with self.assertRaisesRegex(ValueError, 'rear Native runner'):
            check_config(config)

    def test_uncontrolled_rear_rejects_route_signal(self):
        class Map:
            def to_opendrive(self):
                return '<OpenDRIVE><road id="10"><signals><signal id="S1"/></signals></road></OpenDRIVE>'
        class World:
            def get_actors(self):
                return []
        pair = {'subject': {'approach_road_id': 10,
                            'path': [S(is_junction=True, transform=S(location=None))]},
                'opposing': {'approach_road_id': 10}}
        with self.assertRaisesRegex(ValueError, 'possible governing'):
            device_inventory(World(), Map(), pair)


if __name__ == '__main__':
    unittest.main()
