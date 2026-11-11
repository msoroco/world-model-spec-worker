import importlib.util,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('following_controller',ROOT/'following_controller.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Vehicle:
 def __init__(self,x,y,speed):self.x=x;self.y=y;self.speed=speed;self.control=None
 def get_location(self):return NS(x=self.x,y=self.y,z=0)
 def get_velocity(self):return NS(x=self.speed,y=0,z=0)
 def apply_control(self,value):self.control=value
class Tests(unittest.TestCase):
 def test_feedback_and_lane_change_use_native_measurements(self):
  ego,lead=Vehicle(5,0,8),Vehicle(15,0,5)
  c=module.FollowingController(NS,target_speed_mps=9,target_center_spacing_m=12,lane_change_start_m=10,lane_change_end_m=20,lead_speed_mps=5)
  first=c.step(ego,lead,route_origin_xyz=(0,0,0),route_forward_xy=(1,0),target_lane_center_xy=(12,3))
  self.assertEqual(first['measured_center_spacing_m'],10)
  self.assertFalse(first['lane_change_started']);self.assertGreater(ego.control.brake,0)
  ego.x=12;lead.x=22
  second=c.step(ego,lead,route_origin_xyz=(0,0,0),route_forward_xy=(1,0),target_lane_center_xy=(12,3))
  self.assertTrue(second['lane_change_started']);self.assertGreater(ego.control.steer,0)
  self.assertEqual(lead.control.steer,0)
 def test_lead_brake_and_missing_lead_rejected(self):
  ego,lead=Vehicle(12,0,6),Vehicle(22,0,5)
  c=module.FollowingController(NS,target_speed_mps=7,target_center_spacing_m=10,lane_change_start_m=10,lane_change_end_m=20,lead_speed_mps=5,lead_brake_start_m=11)
  result=c.step(ego,lead,route_origin_xyz=(0,0,0),route_forward_xy=(1,0),target_lane_center_xy=(12,3))
  self.assertGreater(result['lead_brake'],0)
  lead.x=5
  with self.assertRaisesRegex(ValueError,'Lead no longer ahead'):c.step(ego,lead,route_origin_xyz=(0,0,0),route_forward_xy=(1,0),target_lane_center_xy=(12,3))
if __name__=='__main__':unittest.main()
