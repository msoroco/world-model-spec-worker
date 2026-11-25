import json
from pathlib import Path
import unittest

from geometry import check as geometry_check
from stop_route import STOP_X_M, command
from runner import CAMERAS, check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'
        Sidewalk = 'sidewalk'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_waypoint(self, loc, **kwargs):
        transform = type('T', (), {'location': loc})()
        sidewalk = kwargs.get('lane_type') == FakeCarla.LaneType.Sidewalk
        lane_id = 1 if sidewalk else (1 if self.wrong else -1)
        return type('WP', (), {'road_id': 1, 'lane_id': lane_id,
                               'transform': transform})()


class NativeDraft(unittest.TestCase):
    def test_geometry_stop_and_camera_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['fixture_bounds_m']['min_x'], 0)
        self.assertEqual(set(STOP_X_M), {'outside', 'side_band', 'front'})
        self.assertEqual(command(config['stop_case'], 0, -60, 0)['phase'], 'approach')
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 6)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))


if __name__ == '__main__':
    unittest.main()
