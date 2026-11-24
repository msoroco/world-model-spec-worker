import unittest

from geometry import check as geometry_check
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Parking = 'parking'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, wrong=False):
        self.road_id, self.lane_id, self.lane_type = 1, -1 if wrong else -2, 'parking'
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 8)})()


class FakeWorld:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y, self.wrong)


class NativeDraft(unittest.TestCase):
    def test_geometry_and_camera_plan(self):
        self.assertEqual(geometry_check()['lane_types'], ['driving', 'parking'])
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(runner_check()['camera_names']), 4)
        self.assertFalse(runner_check()['physical_acceptance_claimed'])

    def test_parking_lane_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)), 4)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(wrong=True), FakeCarla)
