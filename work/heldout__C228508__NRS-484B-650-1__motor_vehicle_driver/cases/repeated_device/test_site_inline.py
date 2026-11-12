import unittest
from types import SimpleNamespace as NS
from device_lane_construction import select_pair

class WP:
    def __init__(self,x,lane=1):
        self.road_id=1;self.lane_id=lane;self.lane_type='Driving'
        self.left_lane_marking=NS(type='Broken')
        self.transform=NS(location=NS(x=x,y=3.5*(lane-1),z=0),rotation=NS(yaw=0))
    def next(self,n):return [WP(self.transform.location.x+n,self.lane_id)]
    def previous(self,n):return [WP(self.transform.location.x-n,self.lane_id)]
    def get_left_lane(self):return WP(self.transform.location.x,self.lane_id+1)
class Light:
    def __init__(self,actor,x):self.id=actor;self.x=x
    def get_opendrive_id(self):return 'L'+str(self.id)
    def get_affected_lane_waypoints(self):return [WP(self.x)]
    def set_state(self,state):pass
class SiteTests(unittest.TestCase):
    def test_two_distinct_governing_lights(self):
        first,second=select_pair(None,[Light(1,150),Light(2,700)])
        self.assertEqual((first['light_actor_id'],second['light_actor_id']),(1,2))
        self.assertEqual((first['stop_station_m'],second['stop_station_m']),(150,700))
    def test_one_light_rejected(self):
        with self.assertRaisesRegex(ValueError,'second distinct'):
            select_pair(None,[Light(1,150)])
