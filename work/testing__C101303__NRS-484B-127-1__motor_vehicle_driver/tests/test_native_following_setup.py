import importlib.util,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_following_setup',ROOT/'native_following_setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
class Waypoint:
 def __init__(self,x,z,lane=-1):
  self.road_id=7;self.lane_id=lane;self.is_junction=False;self.lane_type='Driving'
  self.transform=NS(location=NS(x=x,y=0,z=z));self.successor=None;self.adjacent=None
 def next(self,step):return [self.successor] if self.successor else []
 def get_left_lane(self):return self.adjacent
 def get_right_lane(self):return None
class Tests(unittest.TestCase):
 def route(self,crest=True):
  points=[Waypoint(i*3,[0,1,2,3,4,3,2,1,0,0,0][i] if crest else 0) for i in range(11)]
  for a,b in zip(points,points[1:]):a.successor=b
  points[4].adjacent=Waypoint(12,4,-2)
  native=NS(get_waypoint=lambda p,project_to_road:points[0])
  return native,NS(location=points[0].transform.location),points
 def test_source_road_crest_and_adjacent_lane(self):
  native,start,_=self.route()
  r=setup.select_hill_crest_route(native,start,reviewed_road_id=7,following_lane_id=-1,target_lane_id=-2,minimum_length_m=30)
  self.assertEqual(r['crest_waypoint_index'],4);self.assertGreaterEqual(r['crest_rise_m'],4)
  self.assertEqual(r['target_lane_waypoint'].lane_id,-2)
 def test_flat_or_missing_target_lane_rejected(self):
  native,start,_=self.route(False)
  with self.assertRaisesRegex(ValueError,'hill crest'):setup.select_hill_crest_route(native,start,reviewed_road_id=7,following_lane_id=-1,target_lane_id=-2,minimum_length_m=30)
  native,start,points=self.route();points[4].adjacent=None
  with self.assertRaisesRegex(ValueError,'adjacent'):setup.select_hill_crest_route(native,start,reviewed_road_id=7,following_lane_id=-1,target_lane_id=-2,minimum_length_m=30)
 def test_real_native_spawns_and_cleanup(self):
  destroyed=[]
  def actor(x):return NS(get_location=lambda:NS(x=x,y=0,z=0),destroy=lambda:destroyed.append(x))
  actors=iter([actor(15),actor(0)]);world=NS(try_spawn_actor=lambda bp,tr:next(actors))
  with setup.spawn_following_pair(world,'vehicle','ego','lead') as pair:self.assertEqual(pair['initial_center_separation_m'],15)
  self.assertEqual(destroyed,[0,15])
if __name__=='__main__':unittest.main()
