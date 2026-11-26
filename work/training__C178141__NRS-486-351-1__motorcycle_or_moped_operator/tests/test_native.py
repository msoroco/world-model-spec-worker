import json
from pathlib import Path
import unittest

from geometry import check as geometry_check
from route import LATERAL_M, compare_requested_routes
from runner import CAMERAS, check, control, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_waypoint(self, loc, **kwargs):
        lane = -1 if loc.y == 4.5 else (-1 if self.wrong else -2)
        return type('WP', (), {'road_id': 1, 'lane_id': lane,
                               'transform': type('T', (), {'location': loc})()})()


class FakeSubject:
    def __init__(self, y):
        self.pose = type('T', (), {'location': FakeCarla.Location(-30, y, 2)})()
        self.velocity = type('V', (), {'x': 0.0, 'y': 0.0})()

    def get_transform(self):
        return self.pose

    def get_velocity(self):
        return self.velocity


class NativeDraft(unittest.TestCase):
    def test_geometry_route_and_camera_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['lane_ids'], [-1, -2])
        self.assertEqual(compare_requested_routes()['only_requested_difference'], 'lateral_position_m')
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 10)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))
        self.assertGreater(control(config, 0, FakeSubject(LATERAL_M[config['split_case']]))['throttle'], 0)


if __name__ == '__main__':
    unittest.main()
