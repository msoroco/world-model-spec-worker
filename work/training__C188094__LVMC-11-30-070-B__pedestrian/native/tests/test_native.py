import json
from pathlib import Path
import unittest

from geometry import check as geometry_check
from path import CROSSING_X_M, compare_requested_paths
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
        return type('WP', (), {'road_id': 2 if self.wrong else 1,
                               'lane_id': -1,
                               'transform': type('T', (), {'location': loc})()})()


class NativeDraft(unittest.TestCase):
    def test_geometry_path_and_camera_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['overpass_deck_height_m'], 5)
        self.assertEqual(compare_requested_paths()['only_requested_difference'], 'at_grade_crossing_x_m')
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 6)
        with self.assertRaisesRegex(RuntimeError, 'at-grade road survey failed'):
            survey(FakeCarla, FakeMap(True))
        self.assertIn(config['crossing_case'], CROSSING_X_M)


if __name__ == '__main__':
    unittest.main()
