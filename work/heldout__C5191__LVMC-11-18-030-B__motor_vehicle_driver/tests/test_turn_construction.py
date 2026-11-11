import math,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from turn_construction import select_marked_left_scene,targets
class WP:
 def __init__(self,x,y,yaw,road=1,lane=1,junction=False,marked=True):
  self.road_id,self.lane_id,self.is_junction,self.lane_type=road,lane,junction,'Driving'
  self.left_lane_marking=self.right_lane_marking=SimpleNamespace(type='Solid' if marked else 'None')
  self.transform=SimpleNamespace(location=SimpleNamespace(x=x,y=y),get_forward_vector=lambda:SimpleNamespace(x=math.cos(math.radians(yaw)),y=math.sin(math.radians(yaw))))
  self.follow=[];self.left=None
 def next(self,_):return self.follow
 def get_left_lane(self):return self.left
class Map:
 def __init__(self,starts):self.starts=starts
 def generate_waypoints(self,_):return self.starts
class TestTurnConstruction(unittest.TestCase):
 def scene(self,exit_yaw=90,marked=True):
  a=[WP(i*2,0,0) for i in range(13)];b=[WP(i*2,3.5,0,lane=2) for i in range(13)]
  for i in range(12):a[i].follow=[a[i+1]];b[i].follow=[b[i+1]]
  a[0].left=b[0];j=WP(26,0,0,junction=True);e=WP(26,8,exit_yaw,road=2,marked=marked);a[-1].follow=[j];j.follow=[e]
  return Map([a[0]])
 def test_connected_left_and_distinct_paths(self):
  s=select_marked_left_scene(self.scene());self.assertEqual(s['requested_heading_change_deg'],90)
  a=targets(s,'left_turn_lane_contained_approach');b=targets(s,'left_turn_early_boundary_crossing_no_signal');c=targets(s,'left_turn_early_boundary_crossing_signaled')
  self.assertEqual(a['targets_xy_m'][-1],b['targets_xy_m'][-1]);self.assertEqual(b['targets_xy_m'],c['targets_xy_m']);self.assertNotEqual(a['targets_xy_m'][8],b['targets_xy_m'][8]);self.assertFalse(b['indicator_requested']);self.assertTrue(c['indicator_requested'])
 def test_rejects_wrong_exit_and_unmarked(self):
  for scene in (self.scene(-90),self.scene(90,False)):
   with self.assertRaisesRegex(ValueError,'No connected'):select_marked_left_scene(scene)
