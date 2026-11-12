import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('device_lane_construction',ROOT/'cases/core_device_lane/device_lane_construction.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)

class Waypoint:
    def __init__(self,x,direction=1,lane=1):
        self.x=x;self.direction=direction;self.lane_id=lane;self.road_id=1 if direction==1 else 2
        self.lane_type='Driving';self.left_lane_marking=NS(type='Broken')
        self.transform=NS(location=NS(x=x,y=3.5*(lane-1),z=0),rotation=NS(yaw=0 if direction==1 else 180))
    def next(self,step):return [Waypoint(self.x+self.direction*step,self.direction,self.lane_id)]
    def previous(self,step):return [Waypoint(self.x-self.direction*step,self.direction,self.lane_id)]
    def get_left_lane(self):return Waypoint(self.x,self.direction,self.lane_id+1)

class Light:
    def __init__(self,number,direction):self.id=number;self.direction=direction
    def get_affected_lane_waypoints(self):return [Waypoint(150 if self.direction==1 else -150,self.direction)]
    def get_opendrive_id(self):return str(self.id)
    def set_state(self,state):pass

class DeviceLaneConstructionTests(unittest.TestCase):
    def test_both_approaches_and_marked_excursion(self):
        lights=[Light(1,1),Light(2,-1)]
        for index,direction in [(0,1),(1,-1)]:
            site=module.select_site(None,lights,candidate_index=index)
            self.assertEqual(site['stop_station_m'],150)
            self.assertGreaterEqual(site['distance_m'][-1],2200)
            self.assertEqual(site['adjacent_lane_id'],2)
            base=module.lane_target(site,600,120)
            crossed=module.lane_target(site,750,150)
            self.assertNotEqual(base[1],crossed[1])
            self.assertEqual(site['route'][0].transform.location.x,0)
        with self.assertRaisesRegex(ValueError,'No requested'):
            module.select_site(None,lights,candidate_index=2)

if __name__=='__main__':unittest.main()
