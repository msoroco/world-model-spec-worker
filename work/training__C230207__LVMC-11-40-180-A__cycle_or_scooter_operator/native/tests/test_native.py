import unittest
from geometry import SIGN_NAME, check as geometry_check, open_drive
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Sidewalk = 'sidewalk'

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
        assert lane_type == FakeCarla.LaneType.Sidewalk
        return FakeWaypoint(location.x, location.y, -1 if self.wrong_lane else -2)


class FakeWorld:
    def __init__(self, **kwargs):
        self.mapping = FakeMap(**kwargs)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_plan(self):
        self.assertEqual(geometry_check()['sign_text'], SIGN_NAME)
        self.assertEqual(geometry_check()['sidewalk_lane_id'], -2)
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(runner_check()['cameras']), 4)

    def test_sign_and_sidewalk_survey(self):
        good = survey(FakeWorld(), FakeCarla)
        self.assertEqual(len(good['sidewalk']), 3)
        with self.assertRaisesRegex(RuntimeError, 'signed bicycle restriction'):
            survey(FakeWorld(wrong_sign=True), FakeCarla)
        with self.assertRaisesRegex(RuntimeError, 'governed roadway'):
            survey(FakeWorld(wrong_lane=True), FakeCarla)
