import json
from pathlib import Path
import unittest

from controller import TARGET_MPH, command
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
        return type('WP', (), {'road_id': 1, 'lane_id': -2 if self.wrong else -1,
                               'transform': type('T', (), {'location': loc})()})()


class NativeDraft(unittest.TestCase):
    def test_road_survey_and_speed_bundle(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['length_m'], 800)
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 7)
        with self.assertRaisesRegex(RuntimeError, 'roadway survey failed'):
            survey(FakeCarla, FakeMap(True))
        self.assertGreater(command(config['speed_case'], 0, 0)['throttle'], 0)
        self.assertIn(config['speed_case'], TARGET_MPH)


if __name__ == '__main__':
    unittest.main()
