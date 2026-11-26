import json
from pathlib import Path
import unittest

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
        at = FakeCarla.Location(loc.x, loc.y, loc.z)
        transform = type('Transform', (), {'location': at})()
        return type('Waypoint', (), {'road_id': 1, 'lane_id': 1 if self.wrong else -1,
                                       'transform': transform})()


class NativeDraft(unittest.TestCase):
    def test_contract_and_survey(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertGreater(geometry_check()['grade'], 0)
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 5)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))


if __name__ == '__main__':
    unittest.main()
