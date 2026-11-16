from __future__ import annotations
import importlib.util,unittest,hashlib,json,tempfile,subprocess,shutil
from pathlib import Path
s=importlib.util.spec_from_file_location('road_half',Path(__file__).resolve().parents[1]/'road_half.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self):self.calls=[]
 def road(self,**x):self.calls.append(('road',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
 def closure(self,**x):self.calls.append(('closure',x));return x
 def sign(self,**x):self.calls.append(('sign',x));return x
class RoadHalfTests(unittest.TestCase):
 def test_all_exception_variants_create_physical_features(self):
  for exception in m.EXCEPTIONS:
   f=Fake();scene=m.construct(f,exception,'left')
   self.assertEqual(scene['ego']['route'][0][1],1)
   self.assertEqual(scene['road']['lanes'],3 if exception=='three_lanes' else (1 if exception=='posted_one_way' else 2))
   if exception=='right_half_closed':self.assertIn('closure',[x[0] for x in f.calls])
   if exception=='posted_one_way':self.assertIn('sign',[x[0] for x in f.calls])
   if exception=='overtaking_same_direction':self.assertEqual(len([x for x in f.calls if x[0]=='vehicle']),2)
 def sample(self):
  c={'exception':'none','exception_source':'original-road-context','road_source':'original-map','centerline':[[0,0],[10,0]]}
  f=[{'frame':i,'body_source':'original-footprint','ground_corners':[[i,-1],[i+1,-1],[i+1,-2],[i,-2]]} for i in range(2)]
  return c,f
 def test_original_full_body_side_and_missing_source(self):
  c,f=self.sample();r=m.measure(c,f);self.assertFalse(r['any_left_half_body'])
  f[0]['ground_corners']=[[0,1],[1,1],[1,2],[0,2]]
  self.assertTrue(m.measure(c,f)['any_left_half_body'])
  c['exception_source']=''
  with self.assertRaisesRegex(ValueError,'sourced'):m.measure(c,f)
 def test_fixed_condition_comparison(self):
  c,f=self.sample();a=m.measure(c,f);a.update(road_hash='r',centerline_hash='c',camera_plan_hash='cam',duration_s=8,actor_hash='a')
  changed=[dict(row,ground_corners=[[p[0],-p[1]] for p in row['ground_corners']]) for row in f]
  b=m.measure(c,changed);b.update(road_hash='r',centerline_hash='c',camera_plan_hash='cam',duration_s=8,actor_hash='a')
  self.assertTrue(m.audit_comparison(a,b,'body_side')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,road_hash='x'),'body_side')
  with self.assertRaisesRegex(ValueError,'derived body side'):m.audit_comparison(a,dict(b,any_left_half_body=False),'body_side')
 def test_saved_sources_join_and_required_feature(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   road={'road_id':17,'survey_source':'Native map waypoint survey','centerline':[[0,0],[10,0]],'right_half_sign':-1,'lane_count':2}
   road_bytes=(json.dumps(road)+'\n').encode();(root/'road_geometry.json').write_bytes(road_bytes)
   closure_bytes=(json.dumps({'road_id':17,'native_readback':{'barrier_actor_ids':[201,202]}})+'\n').encode()
   (root/'closure_original.json').write_bytes(closure_bytes)
   context={'road_id':17,'road_sha256':hashlib.sha256(road_bytes).hexdigest(),'exception':'right_half_closed',
            'feature':'physical_right_half_closure','closure_source_sha256':hashlib.sha256(closure_bytes).hexdigest()}
   (root/'exception_context.json').write_text(json.dumps(context)+'\n')
   body=[{'frame':i+100,'time_s':i/20,'ground_corners':[[i,-1],[i+1,-1],[i+1,-2],[i,-2]]} for i in range(2)]
   mapping=[{'carla_frame':r['frame'],'time_s':r['time_s']} for r in body]
   (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in body))
   (root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in mapping))
   result=m.measure_saved(root,expected_frames=2)
   self.assertFalse(result['any_left_half_body'])
   self.assertEqual(result['original_frames'],[100,101])
   self.assertFalse(result['physical_premise_confirmed'])
   (root/'body_history.jsonl').write_text(json.dumps(body[0])+'\n')
   with self.assertRaisesRegex(ValueError,'inventory incomplete'):m.measure_saved(root,expected_frames=2)
   (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in body))
   context['closure_source_sha256']=''
   (root/'exception_context.json').write_text(json.dumps(context)+'\n')
   with self.assertRaisesRegex(ValueError,'feature source hash differs'):m.measure_saved(root,expected_frames=2)
   context['closure_source_sha256']=hashlib.sha256(closure_bytes).hexdigest()
   context['road_sha256']='b'*64
   (root/'exception_context.json').write_text(json.dumps(context)+'\n')
   with self.assertRaisesRegex(ValueError,'road source hash differs'):m.measure_saved(root,expected_frames=2)
   context['road_sha256']=hashlib.sha256(road_bytes).hexdigest()
   (root/'exception_context.json').write_text(json.dumps(context)+'\n')
   (root/'closure_original.json').unlink()
   with self.assertRaisesRegex(ValueError,'feature source missing'):m.measure_saved(root,expected_frames=2)
 def test_direction_reversal_reverses_road_halves(self):
  c,f=self.sample();a=m.measure(c,f)
  c['right_half_sign']=1;b=m.measure(c,f)
  self.assertFalse(a['any_left_half_body']);self.assertTrue(b['any_left_half_body'])
 def test_native_adapter_surveys_loaded_road_and_spawns_features(self):
  class Location:
   def __init__(self):self.x=0.;self.y=0.;self.z=0.
  class Rotation:
   yaw=0.
  class Transform:
   def __init__(self):self.location=Location();self.rotation=Rotation()
  class Waypoint:
   road_id=17;lane_width=3.5;lane_type='Driving'
   def __init__(self,lane_id):self.lane_id=lane_id;self.transform=Transform()
   def get_left_lane(self):return Waypoint(1) if self.lane_id==-1 else None
   def get_right_lane(self):return Waypoint(-1) if self.lane_id==1 else None
  class Map:
   def get_waypoint_xodr(self,road_id,lane_id,s):return Waypoint(lane_id) if road_id==17 and lane_id in (-1,1) else None
  class Library:
   def find(self,asset):return asset
  class Actor:
   def __init__(self,actor_id):self.id=actor_id;self.destroyed=False
   def destroy(self):self.destroyed=True
  class World:
   def __init__(self):self.actors=[]
   def get_map(self):return Map()
   def get_blueprint_library(self):return Library()
   def try_spawn_actor(self,blueprint,transform):
    actor=Actor(len(self.actors)+1);self.actors.append(actor);return actor
  class Carla:
   class LaneType:Driving='Driving'
  site={'road_id':17,'lane_ids':[-1,1],'sample_s_m':[20,40],'s_origin_m':30,
        'ego_left_lane_id':1,'ego_right_lane_id':-1,'passed_vehicle_lane_id':-1,
        'blueprints':{'ego':'vehicle.test','passed_vehicle':'vehicle.other','barrier':'static.prop.barrier',
                      'one_way_sign':'static.prop.oneway'},
        'spawn_s_m':{'ego':20,'passed_vehicle':21},'route_s_m':{'ego':[20,40],'passed_vehicle':[21,40]},
        'closure_s_m':[20,30,40],'one_way_sign_s_m':20}
  world=World();adapter=m.NativeRoadHalfAdapter(world,Carla,site)
  scene=m.construct(adapter,'right_half_closed','left')
  self.assertEqual(scene['road']['lane_count'],2)
  self.assertEqual(scene['ego']['lane_id'],1)
  self.assertEqual(len(scene['features'][0]['native_readback']),3)
  self.assertEqual(len(world.actors),4)
  adapter.close();self.assertTrue(all(actor.destroyed for actor in world.actors))
  right=m.construct(m.NativeRoadHalfAdapter(World(),Carla,site),'none','right')
  self.assertEqual(right['ego']['lane_id'],-1)
  passing=m.construct(m.NativeRoadHalfAdapter(World(),Carla,site),'overtaking_same_direction','left')
  self.assertEqual(passing['features'][0]['lane_id'],-1)
  self.assertEqual(passing['ego']['lane_id'],1)
  site['lane_ids']=[-1]
  with self.assertRaisesRegex(ValueError,'lane count differs'):
   m.construct(m.NativeRoadHalfAdapter(World(),Carla,site),'none','right')
 def test_independent_delivery_and_comparison_audit(self):
  audit_spec=importlib.util.spec_from_file_location('c111250_audit',Path(__file__).resolve().parents[1]/'delivery_audit.py')
  audit=importlib.util.module_from_spec(audit_spec);audit_spec.loader.exec_module(audit)
  with tempfile.TemporaryDirectory() as temp:
   roots=[Path(temp)/part for part in ('right','left')]
   for root in roots:root.mkdir()
   road={'road_id':17,'survey_source':'Native map waypoint survey','centerline':[[0,0],[10,0]],'right_half_sign':-1,'lane_count':2}
   road_bytes=(json.dumps(road)+'\n').encode()
   context={'road_id':17,'road_sha256':hashlib.sha256(road_bytes).hexdigest(),'exception':'none','feature':None}
   mapping=[{'carla_frame':100+i,'time_s':i/20} for i in range(2)]
   plan={'cameras':list(audit.CAMERAS),'rate_hz':20,'expected_frames':2,'duration_s':.1}
   for root in roots:
    (root/'road_geometry.json').write_bytes(road_bytes)
    (root/'exception_context.json').write_text(json.dumps(context)+'\n')
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
    (root/'capture_contract.json').write_text(json.dumps(plan)+'\n')
    (root/'actor_identity.json').write_text(json.dumps({'subject_blueprint':'vehicle.test'})+'\n')
    for name in audit.CAMERAS:
     (root/(name+'-frames.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in mapping))
   for root,sign in zip(roots,(-1,1)):
    body=[{'frame':row['carla_frame'],'time_s':row['time_s'],
           'ground_corners':[[i,sign],[i+1,sign],[i+1,2*sign],[i,2*sign]]}
          for i,row in enumerate(mapping)]
    (root/'body_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in body))
   for name in audit.CAMERAS:
    video=roots[0]/(name+'.mkv')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=black:s=16x16:r=20',
                    '-frames:v','2','-c:v','ffv1',str(video)],check=True)
    shutil.copy2(video,roots[1]/video.name)
   self.assertTrue(audit.audit_delivery(roots[0],expected_frames=2)['source_join_complete'])
   self.assertTrue(audit.audit_comparison(*roots,'body_side',expected_frames=2)['comparison']['comparison_complete'])
   (roots[1]/'overview.mkv').unlink()
   with self.assertRaisesRegex(ValueError,'Missing original camera source'):
    audit.audit_delivery(roots[1],expected_frames=2)
if __name__=='__main__':unittest.main()
