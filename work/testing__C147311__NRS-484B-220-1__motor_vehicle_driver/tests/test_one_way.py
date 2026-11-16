import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('one_way_measurements');native=load('native_one_way');comparison=load('comparison_audit');control=load('direction_control');site=load('site_review')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
class Tests(unittest.TestCase):
 def fixture(self,root,reverse=False):
  (root/'designation.txt').write_text('Synthetic designation source')
  (root/'sign.txt').write_text('Synthetic sign source')
  ref=lambda name:{'path':name,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
  packet={'native_map_id':'TownX','highway_id':44,'road_id':5,'driving_lane_ids':[-1,-2],
          'designation_text':'synthetic one-way only','designated_forward_xy':[1,0],
          'reviewer':'CPU fixture','designation_review_basis':'synthetic test only',
          'designation_source':ref('designation.txt'),
          'signs':[{'sign_id':'synthetic-sign','code':'one_way','governs_road_id':5,
                    'governs_lane_ids':[-1,-2],'location_xy_m':[1,0],
                    'source':ref('sign.txt')}]}
  (root/'site_packet.json').write_text(json.dumps(packet))
  ctx={'native_map_id':'TownX','highway_id':44,'road_id':5,'one_way_designation_source':'authority-map','direction_sign_source':'sign-camera','lane_geometry_source':'native-map','travel_route_source':'waypoint-chain','driving_lane_ids':[-1,-2],'designated_forward_xy':[1,0],'one_way_roadway_polygon_xy_m':[[0,-4],[30,-4],[30,4],[0,4]]}
  (root/'road_context.json').write_text(json.dumps(ctx))
  xs=[20,15,10] if reverse else [10,15,20]
  rows=[{'frame':100+i,'time_s':1+i*.05,'road_id':5,'lane_id':-1,'ego_body_vertices_xy_m':body(x),'ego_forward_xy':[-1,0] if reverse else [1,0]} for i,x in enumerate(xs)]
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'travel_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_designated_and_wrong_direction(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);self.assertTrue(measure.analyze(root)['all_steps_designated_direction'])
   self.fixture(root,True);r=measure.analyze(root);self.assertFalse(r['all_steps_designated_direction']);self.assertLess(r['samples'][0]['heading_alignment'],0)
 def test_wrong_lane_and_stale_frame_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);rows=[json.loads(x) for x in (root/'travel_history.jsonl').read_text().splitlines()];rows[1]['lane_id']=1;(root/'travel_history.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   with self.assertRaisesRegex(ValueError,'one-way lanes'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(x) for x in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=900;(root/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_saved_measurement_rejects_missing_or_stale_site_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   self.assertIn('sign.txt',measure.analyze(root)['sources'])
   (root/'sign.txt').write_text('changed source')
   with self.assertRaisesRegex(ValueError,'Stale sign source hash'):measure.analyze(root)
   self.fixture(root);(root/'site_packet.json').unlink()
   with self.assertRaisesRegex(ValueError,'Missing original source: site_packet.json'):measure.analyze(root)
 def test_native_multilane_inventory(self):
  wps=[NS(road_id=5,lane_id=i,lane_type='Driving') for i in (-1,-2)]
  world=NS(get_map=lambda:NS(generate_waypoints=lambda spacing:wps))
  self.assertEqual(native.verify_multilane_one_way(world,5,[-1,-2])['selected_lane_ids'],[-2,-1])
  wps.append(NS(road_id=5,lane_id=1,lane_type='Driving'))
  with self.assertRaisesRegex(ValueError,'opposing'):native.verify_multilane_one_way(world,5,[-1,1])
 def test_paired_native_routes_use_same_lane_and_opposite_order(self):
  def wp(lane,x,y=0):return NS(road_id=5,lane_id=lane,lane_type='Driving',transform=NS(location=NS(x=x,y=y)))
  points=[wp(-1,x) for x in (20,0,10)]+[wp(-2,x,3) for x in (0,10,20)]
  world=NS(get_map=lambda:NS(generate_waypoints=lambda spacing:points))
  plan=native.paired_route_points(world,5,[-1,-2],[1,0],travel_lane_id=-1)
  self.assertEqual(plan['with_designation_xy_m'],[[0.0,0.0],[10.0,0.0],[20.0,0.0]])
  self.assertEqual(plan['against_designation_xy_m'],list(reversed(plan['with_designation_xy_m'])))
  self.assertEqual(plan['lane_id'],-1)
  with self.assertRaisesRegex(ValueError,'Travel lane'):native.paired_route_points(world,5,[-1,-2],[1,0],travel_lane_id=-3)
  points[:]=[wp(-1,0),wp(-1,3),wp(-2,0,3),wp(-2,3,3)]
  with self.assertRaisesRegex(ValueError,'span too short'):native.paired_route_points(world,5,[-1,-2],[1,0],travel_lane_id=-1)
 def test_comparison_audit_rejects_changed_context_and_missing_direction(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);positive=root/'with';negative=root/'against';positive.mkdir();negative.mkdir()
   self.fixture(positive);self.fixture(negative,True)
   receipt=comparison.audit(positive,negative)
   self.assertEqual(receipt['frame_count'],3)
   self.assertEqual(receipt['physical_acceptance'],'unresolved')
   ctx=json.loads((negative/'road_context.json').read_text());ctx['direction_sign_source']='different sign'
   (negative/'road_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'road context differs'):comparison.audit(positive,negative)
   self.fixture(negative)
   with self.assertRaisesRegex(ValueError,'Against-designation heading'):comparison.audit(positive,negative)
   self.fixture(negative,True)
   (negative/'sign.txt').write_text('Different synthetic sign source')
   packet=json.loads((negative/'site_packet.json').read_text())
   packet['signs'][0]['source']['sha256']=hashlib.sha256((negative/'sign.txt').read_bytes()).hexdigest()
   (negative/'site_packet.json').write_text(json.dumps(packet))
   with self.assertRaisesRegex(ValueError,'site source differs'):comparison.audit(positive,negative)
 def test_route_follower_drives_both_directions_and_stops_at_end(self):
  forward=control.RouteFollower([[0,0],[10,0],[20,0]])
  reverse=control.RouteFollower([[20,0],[10,0],[0,0]])
  self.assertEqual(forward.step([0,0],[1,0],0)['target_index'],1)
  self.assertEqual(reverse.step([20,0],[-1,0],0)['target_index'],1)
  self.assertGreater(forward.step([0,0],[1,0],0)['throttle'],0)
  self.assertGreater(reverse.step([20,0],[-1,0],0)['throttle'],0)
  self.assertEqual(forward.step([10,0],[1,0],3)['target_index'],2)
  self.assertEqual(reverse.step([10,0],[-1,0],3)['target_index'],2)
  self.assertTrue(forward.step([20,0],[1,0],0)['route_complete'])
  self.assertTrue(reverse.step([0,0],[-1,0],0)['route_complete'])
  self.assertLess(control.RouteFollower([[0,0],[10,0]]).step([0,2],[1,0],0)['steer'],0)
  with self.assertRaisesRegex(ValueError,'Duplicate route'):control.RouteFollower([[0,0],[0,0]])
 def test_site_source_binding_rejects_stale_or_missing_sign(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   (root/'designation.txt').write_text('Synthetic designation test source')
   (root/'sign.txt').write_text('Synthetic one-way sign test source')
   ref=lambda name:{'path':name,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
   packet={'native_map_id':'TownX','road_id':5,'driving_lane_ids':[-1,-2],
           'highway_id':'synthetic-highway','designation_text':'synthetic one-way designation',
           'designated_forward_xy':[1,0],'reviewer':'CPU synthetic test',
           'designation_review_basis':'synthetic test only','designation_source':ref('designation.txt'),
           'signs':[{'sign_id':'synthetic-sign','code':'one_way','governs_road_id':5,
                     'governs_lane_ids':[-1,-2],'location_xy_m':[0,0],
                     'source':ref('sign.txt')}]}
   self.assertEqual(site.validate(packet,root,expected_map_id='TownX',road_id=5,lane_ids=[-1,-2])['physical_sign_visibility'],'unverified')
   def wp(lane,x,y):return NS(road_id=5,lane_id=lane,lane_type='Driving',transform=NS(location=NS(x=x,y=y)))
   points=[wp(lane,x,y) for lane,y in ((-1,0),(-2,3)) for x in (0,10,20)]
   world=NS(get_map=lambda:NS(name='TownX',generate_waypoints=lambda spacing:points))
   prepared=native.prepare_reviewed_route(world,packet,root,travel_lane_id=-1)
   self.assertEqual(prepared['routes']['against_designation_xy_m'][0],[20.0,0.0])
   (root/'sign.txt').write_text('changed')
   with self.assertRaisesRegex(ValueError,'Stale sign source hash'):
    site.validate(packet,root,expected_map_id='TownX',road_id=5,lane_ids=[-1,-2])
   (root/'sign.txt').write_text('Synthetic one-way sign test source')
   packet['signs'][0]['governs_lane_ids']=[-1]
   with self.assertRaisesRegex(ValueError,'omits selected lane'):
    site.validate(packet,root,expected_map_id='TownX',road_id=5,lane_ids=[-1,-2])
if __name__=='__main__':unittest.main()
