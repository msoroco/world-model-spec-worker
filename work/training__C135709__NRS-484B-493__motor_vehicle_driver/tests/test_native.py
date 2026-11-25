import unittest

from geometry import SIGN_NAME, check as geometry_check, open_drive
from runner import CAMERAS, check as runner_check, survey


class FakeCarla:
    class LaneType:
        Shoulder = 'shoulder'
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, lane_id):
        self.road_id = 1
        self.lane_id = lane_id
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 0)})()


class FakeMap:
    def __init__(self, bad_sign=False, wrong_lane=False):
        self.bad_sign = bad_sign
        self.wrong_lane = wrong_lane

    def to_opendrive(self):
        return open_drive().replace(SIGN_NAME, 'PARKING PERMITTED') if self.bad_sign else open_drive()

    def get_waypoint(self, location, project_to_road, lane_type):
        lane_id = 1 if location.y > 0 else (-2 if location.y < -3 else -1)
        if self.wrong_lane:
            lane_id = -1
        return FakeWaypoint(location.x, location.y, lane_id)


class FakeWorld:
    def __init__(self, **kwargs):
        self.mapping = FakeMap(**kwargs)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_capture_plan(self):
        self.assertEqual(geometry_check()['sign_text'], SIGN_NAME)
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)

    def test_sign_and_curb_survey(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)['lanes']), 3)
        with self.assertRaisesRegex(RuntimeError, 'notice readback'):
            survey(FakeWorld(bad_sign=True), FakeCarla)
        with self.assertRaisesRegex(RuntimeError, 'curb-side lane'):
            survey(FakeWorld(wrong_lane=True), FakeCarla)
