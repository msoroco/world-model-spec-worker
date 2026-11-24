import json
from pathlib import Path
import unittest

from entry import WHEEL_GAP_M
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
    def test_geometry_bus_targets_and_cameras(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['curb_face_y_m'], -5)
        self.assertLess(WHEEL_GAP_M['near'], .4572)
        self.assertGreater(WHEEL_GAP_M['far'], .4572)
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 6)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))


if __name__ == '__main__':
    unittest.main()
