import unittest
from geometry import SIGN_NAME, check as geometry_check, open_drive
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'
        Shoulder = 'shoulder'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, lane_id):
        self.road_id = 1
        self.lane_id = lane_id
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 0)})()


class FakeMap:
    def __init__(self, wrong_sign=False, wrong_lane=False):
        self.wrong_sign, self.wrong_lane = wrong_sign, wrong_lane

    def to_opendrive(self):
        return open_drive().replace(SIGN_NAME, 'SCOOTERS ONLY') if self.wrong_sign else open_drive()

    def get_waypoint(self, location, project_to_road, lane_type):
        if lane_type == FakeCarla.LaneType.Shoulder:
            return FakeWaypoint(location.x, location.y, -1 if self.wrong_lane else -2)
        return FakeWaypoint(location.x, location.y, -2 if self.wrong_lane else -1)


class FakeWorld:
    def __init__(self, **kwargs):
        self.mapping = FakeMap(**kwargs)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_plan(self):
        self.assertEqual(geometry_check()['sign_text'], SIGN_NAME)
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(runner_check()['cameras']), 4)
        self.assertEqual(runner_check()['case_variants']['probe_01']['y_m'], -4.75)
        self.assertEqual(runner_check()['case_variants']['probe_02']['y_m'], -1.75)

    def test_sign_and_lane_survey(self):
        good = survey(FakeWorld(), FakeCarla)
        self.assertEqual(len(good['roadway']), 3)
        self.assertEqual(len(good['shoulder']), 3)
        with self.assertRaisesRegex(RuntimeError, 'signed bicycle restriction'):
            survey(FakeWorld(wrong_sign=True), FakeCarla)
        with self.assertRaisesRegex(RuntimeError, 'governed roadway'):
            survey(FakeWorld(wrong_lane=True), FakeCarla)
