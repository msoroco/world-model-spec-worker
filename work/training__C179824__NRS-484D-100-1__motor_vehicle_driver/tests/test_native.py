import unittest

from geometry import SIGN_NAME, check as geometry_check, open_drive
from runner import CAMERAS, check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, wrong_lane=False):
        self.road_id = 1
        self.lane_id = -2 if wrong_lane else -1
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 0)})()


class FakeMap:
    def __init__(self, bad_sign=False, wrong_lane=False):
        self.bad_sign, self.wrong_lane = bad_sign, wrong_lane

    def to_opendrive(self):
        return open_drive().replace(SIGN_NAME, 'NO HEADLAMPS') if self.bad_sign else open_drive()

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y, self.wrong_lane)


class FakeWorld:
    def __init__(self, **kwargs):
        self.mapping = FakeMap(**kwargs)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_capture(self):
        self.assertEqual(geometry_check()['sign_text'], SIGN_NAME)
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual([(row[0],row[1],row[2]) for row in CAMERAS], [
            ('overview',1920,1080),('approach',1280,720),
            ('reference_corner',1280,720),('driver_reference',1280,720)])

    def test_sign_and_lane_survey(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)['roadway']), 3)
        with self.assertRaisesRegex(RuntimeError, 'instruction readback'):
            survey(FakeWorld(bad_sign=True), FakeCarla)
        with self.assertRaisesRegex(RuntimeError, 'roadway readback'):
            survey(FakeWorld(wrong_lane=True), FakeCarla)
