import unittest
from geometry import check as geometry_check
from runner import check as runner_check, survey, target


class FakeCarla:
    class LaneType:
        Driving='driving'
    class Location:
        def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,lane):
        self.road_id=1;self.lane_id=lane
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,0)})()


class FakeMap:
    def __init__(self,wrong=False):self.wrong=wrong
    def get_waypoint(self,location,project_to_road,lane_type):
        lane=-2 if location.y<-3.5 else -1
        return FakeWaypoint(location.x,location.y,-3 if self.wrong else lane)


class FakeWorld:
    def __init__(self,wrong=False):self.mapping=FakeMap(wrong)
    def get_map(self):return self.mapping


class NativeDraft(unittest.TestCase):
    def test_geometry_plan(self):
        self.assertEqual(geometry_check()['road_length_m'],1700)
        self.assertEqual(runner_check()['frames'],600)
        self.assertEqual(len(runner_check()['cameras']),4)

    def test_controller_speed_and_lane_change_request(self):
        self.assertLess(target('x__probe_02',-200)[0],35.7632)
        self.assertGreater(target('x__probe_03',-200)[0],35.7632)
        self.assertLess(target('x__probe_03',-200)[1],0)
        self.assertEqual(target('x__probe_03',-400)[1],0)

    def test_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)),6)
        with self.assertRaisesRegex(RuntimeError,'Native lane survey differs'):
            survey(FakeWorld(wrong=True),FakeCarla)
