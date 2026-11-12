import unittest
from types import SimpleNamespace as NS
from device_lane_construction import select_site, lane_target

class WP:
    def __init__(self,x,lane=1):
        self.road_id=1;self.lane_id=lane;self.lane_type='Driving'
        self.left_lane_marking=NS(type='Broken')
        self.transform=NS(location=NS(x=x,y=3.5*(lane-1),z=0),rotation=NS(yaw=0))
    def next(self,n):return [WP(self.transform.location.x+n,self.lane_id)]
    def previous(self,n):return [WP(self.transform.location.x-n,self.lane_id)]
    def get_left_lane(self):return WP(self.transform.location.x,self.lane_id+1)
class Light:
    id=1
    def get_opendrive_id(self):return 'L1'
    def get_affected_lane_waypoints(self):return [WP(150)]
    def set_state(self,state):pass
class SiteTests(unittest.TestCase):
    def test_signal_link_and_lateral_target(self):
        site=select_site(None,[Light()])
        self.assertEqual(site['stop_station_m'],150)
        self.assertNotEqual(lane_target(site,750,150)[1],lane_target(site,600,120)[1])
