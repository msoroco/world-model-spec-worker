from __future__ import annotations
import importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('reverse_runner',Path(__file__).resolve().parents[1]/'runner.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Location:
 def __init__(self,x):self.x=x;self.y=0;self.z=0
class Transform:
 def __init__(self,x):self.location=Location(x)
class Waypoint:
 def __init__(self,x,width=2.8):self.transform=Transform(x);self.lane_width=width;self.is_junction=False;self.road_id=1;self.lane_id=-1
 def previous(self,d):return [Waypoint(self.transform.location.x-d,self.lane_width)]
 def next(self,d):return [Waypoint(self.transform.location.x+d,self.lane_width)]
class Map:
 def get_spawn_points(self):return [Transform(0)]
 def get_waypoint(self,location):return Waypoint(location.x)
class RunnerTests(unittest.TestCase):
 def test_selects_connected_narrow_lane_both_directions(self):
  scene=m.choose_narrow_road(Map())
  self.assertEqual(scene['other'].transform.location.x,-12)
  self.assertEqual(scene['front'].transform.location.x,18)
 def test_rejects_wide_lane(self):
  class Wide(Map):
   def get_waypoint(self,location):return Waypoint(location.x,3.5)
  with self.assertRaisesRegex(ValueError,'No connected Native narrow-road'):m.choose_narrow_road(Wide())
 def test_exact_config_and_lazy_carla(self):
  config=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
  self.assertTrue(m.check_config(config))
  config['cell_id']='different'
  with self.assertRaisesRegex(ValueError,'wrong law/cell/actor'):m.check_config(config)
if __name__=='__main__':unittest.main()
