import unittest

from geometry import check as geometry_check, open_drive
from runner import CAMERAS, check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving='driving'
        Shoulder='shoulder'

    class Location:
        def __init__(self,x,y,z):
            self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,lane):
        self.road_id=1
        self.lane_id=lane
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,0)})()


class FakeMap:
    def __init__(self,wrong=False):
        self.wrong=wrong

    def get_waypoint(self,location,project_to_road,lane_type):
        lane=-1 if location.y>-3 else -2
        return FakeWaypoint(location.x,location.y,0 if self.wrong else lane)

    def to_opendrive(self):
        return open_drive()


class FakeWorld:
    def __init__(self,wrong=False):
        self.mapping=FakeMap(wrong)

    def get_map(self):
        return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_and_capture(self):
        self.assertEqual(geometry_check()['curbside_shoulder_lane_id'],-2)
        self.assertEqual(runner_check()['frames'],600)
        self.assertEqual(len(CAMERAS),4)

    def test_curb_and_travel_survey(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)['lanes']),2)
        with self.assertRaisesRegex(RuntimeError,'departure lane'):
            survey(FakeWorld(wrong=True),FakeCarla)
