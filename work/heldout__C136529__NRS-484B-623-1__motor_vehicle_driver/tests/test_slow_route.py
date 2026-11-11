import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from slow_route import route_from
class Waypoint:
    def __init__(self,index,lane=1,width=2.75):
        self.index=index;self.lane_id=lane;self.lane_width=width;self.road_id=7;self.is_junction=False
        self.transform=SimpleNamespace(location=SimpleNamespace(x=lane*1.375,y=index*5.0,z=0))
    def next(self,step):return [Waypoint(self.index+1,self.lane_id,self.lane_width)] if self.index<32 else []
    def get_left_lane(self):return Waypoint(self.index,-self.lane_id,self.lane_width)
    def get_right_lane(self):return None
class RouteTest(unittest.TestCase):
    def test_narrow_connected_both_directions(self):
        for lane in (-1,1):
            route=route_from(Waypoint(0,lane))
            self.assertEqual(route['ego'].index,8)
            self.assertEqual(route['follower'].index,4)
            self.assertEqual(route['opposing'].index,24)
            self.assertLess(route['ego_lane_id']*route['opposing_lane_id'],0)
    def test_rejects_wide_and_short_road(self):
        with self.assertRaisesRegex(ValueError,'narrow'):route_from(Waypoint(0,width=5))
        class Short(Waypoint):
            def next(self,step):return []
        with self.assertRaisesRegex(ValueError,'uniquely connected'):route_from(Short(0))
if __name__=='__main__':unittest.main()
