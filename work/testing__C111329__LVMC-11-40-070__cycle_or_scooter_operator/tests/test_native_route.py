import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_route import command_step
class Vector:
 def __init__(self,x=0,y=0,z=0):self.x,self.y,self.z=x,y,z
class Bike:
 id=22;is_alive=True;type_id='vehicle.bicycle'
 def set_target_velocity(self,v):self.last=v
 def get_velocity(self):return self.last
class TestRoute(unittest.TestCase):
 def test_cross_and_hold_calls(self):
  site={'bike_blueprint_id':'vehicle.bicycle','vehicle_route':[[-10,0,0],[10,0,0]],'engineering_target_speed_mps':3.0}
  carla=type('Carla',(),{'Vector3D':Vector});bike=Bike()
  cross=command_step(bike,carla,{'operator_motion':'cross_stop_line'},site,4.0)
  self.assertEqual(cross['observed_mps'],[3.0,0.0,0.0])
  hold=command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,4.0)
  self.assertEqual(hold['observed_mps'],[0.0,0.0,0.0])
  self.assertEqual(command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,2.0)['commanded_mps'],[3.0,0.0,0.0])
 def test_fails_closed(self):
  site={'bike_blueprint_id':'vehicle.bicycle','vehicle_route':[[-10,0,0],[10,0,0]],'engineering_target_speed_mps':3.0}
  carla=type('Carla',(),{'Vector3D':Vector});bike=Bike()
  with self.assertRaisesRegex(ValueError,'readback'):command_step(type('Wrong',(),{'is_alive':True,'type_id':'other'})(),carla,{'operator_motion':'cross_stop_line'},site,0)
  with self.assertRaisesRegex(ValueError,'unsafe'):command_step(bike,carla,{'operator_motion':'cross_stop_line'},{**site,'engineering_target_speed_mps':99},0)
  with self.assertRaisesRegex(ValueError,'degenerate'):command_step(bike,carla,{'operator_motion':'cross_stop_line'},{**site,'vehicle_route':[[0,0,0],[0,0,0]]},0)
if __name__=='__main__':unittest.main()
