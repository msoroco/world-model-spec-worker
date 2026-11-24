import unittest

from geometry import WIDTHS, check as geometry_check
from runner import CAMERAS, check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, width, wrong=False):
        self.road_id, self.lane_id, self.lane_width = 1, -2 if wrong else -1, width
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 8)})()


class FakeWorld:
    def __init__(self, width, wrong=False):
        self.width, self.wrong = width, wrong

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y, self.width, self.wrong)


class NativeDraft(unittest.TestCase):
    def test_width_variants_and_capture(self):
        self.assertEqual(WIDTHS, {'controlled_1': 7.5, 'controlled_2': 6.0})
        self.assertEqual(geometry_check(7.5)['paved_width_m'], 7.5)
        self.assertEqual(geometry_check(6.0)['paved_width_m'], 6.0)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(runner_check(7.5)['frames'], 600)
        self.assertFalse(runner_check(7.5)['physical_acceptance_claimed'])

    def test_native_width_readback_gate(self):
        self.assertEqual(len(survey(FakeWorld(6.0), FakeCarla, 6.0)), 3)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(6.0, wrong=True), FakeCarla, 6.0)
