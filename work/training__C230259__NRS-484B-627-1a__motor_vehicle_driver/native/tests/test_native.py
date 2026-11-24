import unittest
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving='driving'
        Shoulder='shoulder'

    class Location:
        def __init__(self,x,y,z):
            self.x,self.y,self.z=x,y,z


class FakeWaypoint:
    def __init__(self,x,y,lane_id):
        self.road_id=1
        self.lane_id=lane_id
        self.transform=type('T',(),{'location':FakeCarla.Location(x,y,0)})()


class FakeMap:
    def __init__(self,wrong=False):
        self.wrong=wrong

    def get_waypoint(self,location,project_to_road,lane_type):
        lane_id=1 if location.y>0 else (-2 if location.y<-3.5 else -1)
        return FakeWaypoint(location.x,location.y,-1 if self.wrong else lane_id)


class FakeWorld:
    def __init__(self,wrong=False):
        self.mapping=FakeMap(wrong)

    def get_map(self):
        return self.mapping


class SlowTrafficDraft(unittest.TestCase):
    def test_geometry_and_capture(self):
        self.assertEqual(geometry_check()['right_paved_edge_y_m'],-6.5)
        self.assertEqual(runner_check()['frames'],600)
        self.assertEqual(len(runner_check()['camera_names']),4)

    def test_native_lane_survey(self):
        self.assertEqual(len(survey(FakeWorld(),FakeCarla)['lanes']),3)
        with self.assertRaisesRegex(RuntimeError,'one-lane-each-way'):
            survey(FakeWorld(wrong=True),FakeCarla)
