import unittest
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving='driving'
    class Location:
        def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,z):
        self.road_id=1;self.lane_id=-1
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,z)})()


class FakeMap:
    def __init__(self,wrong_sign=False):self.wrong_sign=wrong_sign
    def to_opendrive(self):
        return open_drive().replace('value="25"','value="35"') if self.wrong_sign else open_drive()
    def get_waypoint(self,location,project_to_road,lane_type):
        z=8 if 0<=location.x<=100 else 0
        return FakeWaypoint(location.x,location.y,z)


class FakeWorld:
    def __init__(self,wrong_sign=False):self.mapping=FakeMap(wrong_sign)
    def get_map(self):return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry(self):
        g=geometry_check();self.assertEqual(g['posting_distance_m'],30.48)
        self.assertEqual(g['sign_limit_mph'],25)

    def test_capture_plan(self):
        p=runner_check();self.assertEqual(p['frames'],600)
        self.assertEqual(len(p['cameras']),4)
        self.assertFalse(p['physical_acceptance_claimed'])

    def test_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)['bridge']),5)
        with self.assertRaisesRegex(RuntimeError,'sign readback differs'):
            survey(FakeWorld(wrong_sign=True),FakeCarla)
