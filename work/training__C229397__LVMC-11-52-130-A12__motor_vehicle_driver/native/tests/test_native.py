import unittest

from geometry import CROSSWALK_RECT, TARGET_X, check as geometry_check
from runner import check as runner_check, survey, survey_crosswalk


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

    def get_crosswalks(self):
        if self.wrong:
            return []
        return [FakeCarla.Location(x, y, 8) for x, y in ((0,-6.5),(4,-6.5),(4,0),(0,0))]


class NativeDraft(unittest.TestCase):
    def test_geometry_and_camera_plan(self):
        self.assertEqual(geometry_check()['crosswalk_rect_xyxy_m'], CROSSWALK_RECT)
        self.assertEqual(TARGET_X, {'controlled_1': -14.0, 'controlled_2': -5.0})
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(runner_check()['camera_names']), 4)
        self.assertFalse(runner_check()['physical_acceptance_claimed'])

    def test_parking_lane_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)), 5)
        self.assertEqual(len(survey_crosswalk(FakeWorld())), 4)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(wrong=True), FakeCarla)
        with self.assertRaisesRegex(RuntimeError, 'marked-crosswalk geometry'):
            survey_crosswalk(FakeWorld(wrong=True))
