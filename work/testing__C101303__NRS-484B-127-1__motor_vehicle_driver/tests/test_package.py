import importlib.util,pathlib,unittest,json,math,sys
P=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
spec=importlib.util.spec_from_file_location('runtime_case',P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from projections import Projection,inside,intersects,hull,validate_visibility
class TestPackage(unittest.TestCase):
 def test_offline(self):m.offline_check()
 def test_brake(self):self.assertGreater(m.control(0,0,0,15,[(x,0) for x in range(100)],3)['brake'],0)
 def test_heading_wrap(self):self.assertEqual(m.heading_error(359,1),2)
 def test_gap_uses_footprints(self):self.assertEqual(m.physical_gap([[0,0],[4,0]],[[20,0],[24,0]],[1,0]),16)
 def test_observed_window(self):self.assertEqual(m.summarize([dict(time_s=1,value=100),dict(time_s=16,value=3),dict(time_s=20,value=5)],15,24),(4,[16,20]))
 def test_empty_window_rejected(self):
  with self.assertRaises(ValueError):m.summarize([],15,24)
 def test_no_requested_measurements(self):
  for c in json.loads((P/'config.json').read_text())['cases']:
   for v in c['variable_assignments'].values():
    if v['kind']=='subject_behavior':self.assertIsNone(v['value'])
 def test_runtime_has_conditional_success(self):
  source=(P/'runner.py').read_text();self.assertIn('return 0 if success else 2',source);self.assertNotIn('return 2 # Partial',source)
 def test_box_hull_ignores_native_corner_order(self):self.assertEqual(len(hull([[0,0],[1,1],[1,0],[0,1],[0,0]])),4)
 def test_edge_crossing_overlap(self):self.assertTrue(intersects([[-2,-.1],[2,-.1],[2,.1],[-2,.1]],[[-.1,-2],[.1,-2],[.1,2],[-.1,2]]))
 def event(self,speed=3,time=.05):
  a=dict(actor_id=1,blueprint='vehicle.fixture',heading_deg=0,body_vertices_m=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],position_m=[0,0,0],velocity_mps=[speed,0,0],speed_mps=speed,accel_longitudinal_mps2=-1)
  b=dict(a,actor_id=2,body_vertices_m=[[10,0,0],[11,0,0],[11,1,0],[10,1,0]],position_m=[10,0,0])
  return dict(frame=1,time_s=time,speed_mps=speed),dict(original_observations=dict(participants=[a,b],devices=[],relations=[]),world=dict(road_projection={'road_id':1,'lane_id':-1},weather={'wetness':0,'precipitation_deposits':0}))
 def test_measured_projection_gap(self):
  p=Projection(1,['rel.surface_gap','kin.speed'],dict(leader_id=2,driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event();self.assertEqual(p(r,e)['rel.surface_gap'],9)
 def test_missing_required_leader_fails(self):
  p=Projection(1,['rel.surface_gap'],dict(leader_id=99,driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event()
  with self.assertRaises(ValueError):p(r,e)
 def test_stationary_initialization_is_not_stop_event(self):
  p=Projection(1,['kin.speed'],dict(driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event(0);p(r,e);self.assertEqual(p.stop_events,{})
 def test_history_timestamp_mismatch(self):
  trace=[{'time_s':0}];people=[{'time_s':1,'participants':[]}];body=[{'time_s':0,'vertices':[[0,0]]}]
  with self.assertRaises(ValueError):m.validate_histories(trace,people,body,[])
 def test_unmeasured_participant_rejected(self):
  with self.assertRaises(ValueError):m.validate_histories([{'time_s':0}],[{'time_s':0,'participants':[{'actor_id':1}]}],[{'time_s':0,'vertices':[[0,0]]}],[1])
 def test_missing_sight_approach_rejected(self):
  with self.assertRaises(ValueError):validate_visibility({'visibility_criterion':'any_of_nine_body_samples','required_lane_ids':[-1,1],'approaches':[]})
 def test_route_limited_sight_rejected(self):
  with self.assertRaises(ValueError):validate_visibility({'visibility_criterion':'any_of_nine_body_samples','required_lane_ids':[-1],'approaches':[{'lane_id':-1,'any_body_sight_horizon':{'bound':'route_limit','unknown':True}}]})
 def test_actual_cessation_history(self):
  p=Projection(1,['kin.speed'],dict(driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event(3);p(r,e);r,e=self.event(0,.1);p(r,e);self.assertEqual(p.stop_events[1]['previous_time_s'],.05)
