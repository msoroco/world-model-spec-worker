import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_route import command_step
class Vector:
 def __init__(self,x=0,y=0,z=0):self.x,self.y,self.z=x,y,z
class Transform:
 def __init__(self,x):self.location=Vector(x,0,0)
 def get_forward_vector(self):return Vector(1,0,0)
class Bike:
 id=22;is_alive=True;type_id='vehicle.bicycle'
 def __init__(self,x=-10):
  self.x=x;self.bounding_box=type('Box',(),{'extent':Vector(.5,0,0)})()
 def get_transform(self):return Transform(self.x)
 def set_target_velocity(self,v):self.last=v
 def get_velocity(self):return self.last
class TestRoute(unittest.TestCase):
 def test_cross_and_hold_calls(self):
  site={'bike_blueprint_id':'vehicle.bicycle','vehicle_route':[[-10,0,0],[10,0,0]],'stop_line':[[0,-3],[0,3]],'engineering_target_speed_mps':3.0}
  carla=type('Carla',(),{'Vector3D':Vector});bike=Bike()
  cross=command_step(bike,carla,{'operator_motion':'cross_stop_line'},site,4.0)
  self.assertEqual(cross['observed_mps'],[3.0,0.0,0.0])
  # Elapsed time cannot trigger the hold while the front body is still far away.
  hold=command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,4.0)
  self.assertEqual(hold['observed_mps'],[3.0,0.0,0.0])
  bike.x=-2.0
  hold=command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,0.2)
  self.assertEqual(hold['commanded_mps'],[0.0,0.0,0.0])
  self.assertAlmostEqual(hold['front_to_stop_line_m'],1.5)
  bike.x=1.0
  with self.assertRaisesRegex(ValueError,'crossed stop line'):command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,0.3)
 def test_opposite_approach(self):
  site={'bike_blueprint_id':'vehicle.bicycle','vehicle_route':[[10,0,0],[-10,0,0]],'stop_line':[[0,-3],[0,3]]}
  bike=Bike(2.0)
  bike.get_transform=lambda:type('BackTransform',(),{'location':Vector(2,0,0),'get_forward_vector':lambda self:Vector(-1,0,0)})()
  carla=type('Carla',(),{'Vector3D':Vector})
  self.assertEqual(command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},site,1)['commanded_mps'],[0.0,0.0,0.0])
 def test_fails_closed(self):
  site={'bike_blueprint_id':'vehicle.bicycle','vehicle_route':[[-10,0,0],[10,0,0]],'stop_line':[[0,-3],[0,3]],'engineering_target_speed_mps':3.0}
  carla=type('Carla',(),{'Vector3D':Vector});bike=Bike()
  with self.assertRaisesRegex(ValueError,'readback'):command_step(type('Wrong',(),{'is_alive':True,'type_id':'other'})(),carla,{'operator_motion':'cross_stop_line'},site,0)
  with self.assertRaisesRegex(ValueError,'unsafe'):command_step(bike,carla,{'operator_motion':'cross_stop_line'},{**site,'engineering_target_speed_mps':99},0)
  with self.assertRaisesRegex(ValueError,'degenerate'):command_step(bike,carla,{'operator_motion':'cross_stop_line'},{**site,'vehicle_route':[[0,0,0],[0,0,0]]},0)
  with self.assertRaisesRegex(ValueError,'does not cross'):command_step(bike,carla,{'operator_motion':'cross_stop_line'},{**site,'vehicle_route':[[-10,0,0],[-2,0,0]]},0)
  with self.assertRaisesRegex(ValueError,'stop-line margin'):command_step(bike,carla,{'operator_motion':'hold_before_stop_line'},{**site,'engineering_hold_margin_m':99},0)
if __name__=='__main__':unittest.main()
