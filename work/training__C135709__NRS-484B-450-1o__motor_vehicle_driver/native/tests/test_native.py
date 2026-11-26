import json
from pathlib import Path
import unittest

from controller import STATIONS_M, command
from geometry import check as geometry_check
from runner import CAMERAS, check, survey


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
        transform = type('T', (), {'location': loc})()
        return type('WP', (), {'road_id': 1, 'lane_id': 1 if self.wrong else -1,
                               'transform': transform})()


class NativeDraft(unittest.TestCase):
    def test_geometry_controller_and_camera_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['park_bounds_m']['min_x'], -20.0)
        self.assertLess(STATIONS_M['inside'], 0)
        self.assertGreater(STATIONS_M['outside'], 0)
        self.assertEqual(command(config['zone_case'], 0, -80, 0)['phase'], 'approach')
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 5)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))


if __name__ == '__main__':
    unittest.main()
