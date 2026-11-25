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
        self.transform = type('Transform', (), {'location': FakeCarla.Location(x, y, 0)})()


class FakeMap:
    def __init__(self, permission, damaged=False, wrong_lane=False):
        self.permission = permission
        self.damaged = damaged
        self.wrong_lane = wrong_lane

    def to_opendrive(self):
        road = open_drive(self.permission)
        return road.replace(SIGN_NAME, 'UNRELATED SIGN') if self.damaged else road

    def get_waypoint(self, location, project_to_road, lane_type):
        lane_id = 1 if location.y > 0 else (-2 if location.y < -3 else -1)
        return FakeWaypoint(location.x, location.y, -1 if self.wrong_lane else lane_id)


class FakeWorld:
    def __init__(self, permission, **kwargs):
        self.mapping = FakeMap(permission, **kwargs)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_permission_pair_and_capture_contract(self):
        self.assertIsNone(geometry_check(False)['sign_id'])
        self.assertEqual(geometry_check(True)['sign_text'], SIGN_NAME)
        self.assertNotEqual(open_drive(False), open_drive(True))
        self.assertEqual(runner_check(True)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)

    def test_present_and_absent_device_survey(self):
        for permission in (False, True):
            result = survey(FakeWorld(permission), FakeCarla, permission)
            self.assertEqual(len(result['lanes']), 3)
            self.assertEqual(result['permission_device_requested'], permission)
        with self.assertRaisesRegex(RuntimeError, 'permission device readback'):
            survey(FakeWorld(True, damaged=True), FakeCarla, True)
        with self.assertRaisesRegex(RuntimeError, 'absent-device case'):
            survey(FakeWorld(True), FakeCarla, False)
        with self.assertRaisesRegex(RuntimeError, 'curb-side lane'):
            survey(FakeWorld(False, wrong_lane=True), FakeCarla, False)
