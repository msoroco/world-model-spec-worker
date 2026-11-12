import unittest
from types import SimpleNamespace as NS
from right_pass_construction import right_edge_target,pass_target
class WP:
    road_id=1;lane_id=1;lane_type='Driving';lane_width=3.5
    transform=NS(location=NS(x=0,y=0,z=0),rotation=NS(yaw=0))
    def get_right_lane(self):return None
class PassSiteTest(unittest.TestCase):
    def test_target_is_right_of_driving_edge_only_in_pass_window(self):
        route=[WP() for _ in range(10)]
        self.assertEqual(pass_target(route,250,0),(0,0))
        edge=right_edge_target(route[0],1.5)
        self.assertEqual(edge['road_edge_xy_m'],(0,-1.75))
        self.assertEqual(pass_target(route,350,0),(0,-3.25))
        self.assertEqual(pass_target(route,550,0),(0,0))
