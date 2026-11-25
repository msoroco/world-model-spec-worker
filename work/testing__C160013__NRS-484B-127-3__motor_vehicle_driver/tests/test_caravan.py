import hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load('caravan_spacing');construct=load('caravan_construction');entry=load('caravan_entry');compare=load('caravan_comparison');control=load('caravan_control')
def body(x):return [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]]
def offset(vertices,dy):return [[x,y+dy] for x,y in vertices]
class Tests(unittest.TestCase):
 def fixture(self,root,spacing=10):
  ctx={'native_map_id':'TownX','highway_id':44,'road_id':7,'outside_business_district':True,'caravan_or_motorcade':True,'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]],'road_forward_xy':[1,0]}
  for key in ('business_district_source','caravan_membership_source','route_source','lane_source'):
   name=key+'.txt';content='synthetic structural test source for '+key+'\n';(root/name).write_text(content)
   ctx[key]={'path':name,'sha256':hashlib.sha256(content.encode()).hexdigest()}
  (root/'road_context.json').write_text(json.dumps(ctx))
  rows=[]
  for i in range(2):
   members=[{'actor_id':j+1,'body_vertices_xy_m':body(10+j*spacing+i)} for j in range(3)]
   rows.append({'frame':100+i,'time_s':1+i*.05,'road_id':7,'caravan_members':members,'entering_vehicle':{'actor_id':9,'body_vertices_xy_m':body(10+spacing/2+i)}})
  frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
  (root/'caravan_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
 def test_gap_changes_and_no_legal_cutoff(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,10);large=measure.analyze(root);self.fixture(root,5);small=measure.analyze(root)
   self.assertGreater(large['samples'][0]['gaps'][0]['body_clearance_m'],small['samples'][0]['gaps'][0]['body_clearance_m']);self.assertEqual(large['legal_conclusion'],'unresolved')
   self.assertTrue(large['caravan_forward_motion_observed'])
 def test_complete_body_occupancy_and_original_entry_transition(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,10)
   rows=[json.loads(s) for s in (root/'caravan_history.jsonl').read_text().splitlines()]
   rows[0]['entering_vehicle']['body_vertices_xy_m']=body(3)
   rows[1]['entering_vehicle']['body_vertices_xy_m']=body(16)
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   result=measure.analyze(root)
   self.assertFalse(result['samples'][0]['gaps'][0]['entering_body_wholly_between_member_bodies'])
   self.assertTrue(result['samples'][1]['gaps'][0]['entering_body_wholly_between_member_bodies'])
   self.assertTrue(result['gap_occupancy'][0]['observed_entry_transition'])
   self.fixture(root,3)
   narrow=measure.analyze(root)
   self.assertFalse(narrow['samples'][0]['gaps'][0]['entering_body_wholly_between_member_bodies'])
   self.assertEqual(narrow['gap_occupancy'],[])
   self.assertEqual(narrow['legal_conclusion'],'unresolved')
 def test_adjacent_lane_is_not_gap_occupancy(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,10)
   rows=[json.loads(s) for s in (root/'caravan_history.jsonl').read_text().splitlines()]
   for row in rows:
    row['entering_vehicle']['body_vertices_xy_m']=offset(row['entering_vehicle']['body_vertices_xy_m'],-3)
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   result=measure.analyze(root)
   self.assertEqual(result['gap_occupancy'],[])
   self.assertFalse(result['samples'][0]['gaps'][0]['entering_body_in_caravan_lane'])
 def test_entrant_must_be_distinct_and_collision_is_not_occupancy(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,10)
   rows=[json.loads(s) for s in (root/'caravan_history.jsonl').read_text().splitlines()]
   rows[0]['entering_vehicle']['actor_id']=1
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'Distinct entering vehicle'):measure.analyze(root)
   rows[0]['entering_vehicle']['actor_id']=9
   rows[0]['entering_vehicle']['body_vertices_xy_m']=body(10)
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   result=measure.analyze(root)
   self.assertTrue(result['samples'][0]['gaps'][0]['entering_body_touches_member'])
   self.assertFalse(result['samples'][0]['gaps'][0]['entering_body_wholly_between_member_bodies'])
 def test_activation_and_frame_source_required(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);ctx=json.loads((root/'road_context.json').read_text());ctx['outside_business_district']=False;(root/'road_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'activation'):measure.analyze(root)
   self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
 def test_changed_original_context_source_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   (root/'business_district_source.txt').write_text('changed\n')
   with self.assertRaisesRegex(ValueError,'Changed original context source: business_district_source'):measure.analyze(root)
 def test_membership_and_cadence_must_stay_joined(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   rows=[json.loads(s) for s in (root/'caravan_history.jsonl').read_text().splitlines()]
   rows[1]['caravan_members'][0]['actor_id']=88
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   with self.assertRaisesRegex(ValueError,'Caravan membership changed'):measure.analyze(root)
   self.fixture(root)
   rows=[json.loads(s) for s in (root/'caravan_history.jsonl').read_text().splitlines()]
   frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()]
   rows[1]['time_s']=frames[1]['time_s']=1.1
   (root/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   (root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'20 Hz frame cadence'):measure.analyze(root)
 def test_three_real_vehicle_spawns_and_cleanup(self):
  destroyed=[]
  def actor(x):return NS(get_location=lambda:NS(x=x,y=0),destroy=lambda:destroyed.append(x))
  it=iter([actor(0),actor(10),actor(20)]);world=NS(try_spawn_actor=lambda bp,tr:next(it))
  with construct.spawn_caravan(world,[('car','t')]*3) as actors:self.assertEqual(len(actors),3)
  self.assertEqual(destroyed,[20,10,0])
 def test_bounded_entry_plan_and_stop_before_narrow_gap(self):
  ctx={'road_forward_xy':[1,0],'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]]}
  wide=[{'actor_id':i+1,'body_vertices_xy_m':body(10+i*10)} for i in range(3)]
  narrow=[{'actor_id':i+1,'body_vertices_xy_m':body(10+i*3)} for i in range(3)]
  entrant=offset(body(15),-3)
  target=entry.plan_entry(ctx,wide,entrant,gap_index=0,outcome='occupy')
  self.assertEqual(len(target['waypoints_xy_m']),2)
  self.assertEqual(target['waypoints_xy_m'][-1],[15,0])
  self.assertFalse(target['actual_occupancy_confirmed'])
  with self.assertRaisesRegex(ValueError,'cannot fit'):entry.plan_entry(ctx,narrow,entrant,gap_index=0,outcome='occupy')
  stop=entry.plan_entry(ctx,narrow,entrant,gap_index=0,outcome='stop_before')
  self.assertEqual(len(stop['waypoints_xy_m']),1)
  self.assertEqual(stop['without_danger_judgment'],'unresolved')
 def test_independent_comparison_requires_fixed_sources_and_actual_entry(self):
  with tempfile.TemporaryDirectory() as tmp:
   wide=Path(tmp)/'wide';narrow=Path(tmp)/'narrow';wide.mkdir();narrow.mkdir()
   self.fixture(wide,10);self.fixture(narrow,3)
   narrow_rows=[json.loads(s) for s in (narrow/'caravan_history.jsonl').read_text().splitlines()]
   for row in narrow_rows:
    row['entering_vehicle']['body_vertices_xy_m']=offset(row['entering_vehicle']['body_vertices_xy_m'],-3)
   (narrow/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in narrow_rows))
   rows=[json.loads(s) for s in (wide/'caravan_history.jsonl').read_text().splitlines()]
   rows[0]['entering_vehicle']['body_vertices_xy_m']=body(3)
   rows[1]['entering_vehicle']['body_vertices_xy_m']=body(16)
   (wide/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in rows))
   result=compare.audit(wide,narrow,minimum_frames=2)
   self.assertTrue(result['wide_entry_observed'])
   self.assertFalse(result['physical_acceptance_claimed'])
   (narrow/'lane_source.txt').write_text('changed lane\n')
   ctx=json.loads((narrow/'road_context.json').read_text())
   ctx['lane_source']['sha256']=hashlib.sha256((narrow/'lane_source.txt').read_bytes()).hexdigest()
   (narrow/'road_context.json').write_text(json.dumps(ctx))
   with self.assertRaisesRegex(ValueError,'changed original context sources'):
    compare.audit(wide,narrow,minimum_frames=2)
   self.fixture(narrow,3)
   narrow_rows=[json.loads(s) for s in (narrow/'caravan_history.jsonl').read_text().splitlines()]
   for row in narrow_rows:
    row['entering_vehicle']['body_vertices_xy_m']=offset(row['entering_vehicle']['body_vertices_xy_m'],-3)
   (narrow/'caravan_history.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in narrow_rows))
   self.fixture(wide,10)
   with self.assertRaisesRegex(ValueError,'never entered and occupied'):
    compare.audit(wide,narrow,minimum_frames=2)
 def test_bounded_native_forward_control_and_clearance_guard(self):
  straight=control.command([0,0],0,1,[10,0],target_speed_mps=4)
  self.assertGreater(straight['throttle'],0)
  self.assertEqual(straight['brake'],0)
  self.assertFalse(straight['reverse'])
  turn=control.command([0,0],0,1,[10,5],target_speed_mps=4)
  self.assertGreater(turn['steer'],0)
  near=control.command([0,0],0,2,[10,0],target_speed_mps=4,nearest_body_clearance_m=1)
  self.assertEqual(near['brake'],1)
  self.assertEqual(near['throttle'],0)
  sent=[]
  carla=NS(VehicleControl=lambda **kw:kw)
  actor=NS(apply_control=lambda value:sent.append(value))
  self.assertEqual(control.apply(actor,carla,straight),sent[0])
  self.assertFalse(sent[0]['reverse'])
if __name__=='__main__':unittest.main()

class CaptureTests(unittest.TestCase):
 def test_reviewed_site_sources_and_changed_original_rejection(self):
  capture=load('caravan_capture')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   packet={'site_review_status':'reviewed_native_site','reviewer':'map operator',
           'district_review_basis':'Native parcel and map review',
           'caravan_review_basis':'three participant route records',
           'highway_review_basis':'Native highway map and road topology',
           'camera_review_basis':'four original camera viewpoints',
           'native_map_id':'TownReviewed','outside_business_district':True,
           'caravan_or_motorcade':True,'highway_id':4,'road_id':7,
           'road_forward_xy':[1,0],
           'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]]}
   for key in capture.SOURCE_KEYS:
    name=key+'.txt';data=('original reviewed '+key+'\n').encode()
    (root/name).write_bytes(data)
    packet[key]={'path':name,'sha256':hashlib.sha256(data).hexdigest()}
   self.assertEqual(len(capture.validate_site(packet,root,'TownReviewed')),4)
   with self.assertRaisesRegex(ValueError,'Native map differs'):
    capture.validate_site(packet,root,'TownOther')
   (root/'lane_source.txt').write_text('changed\n')
   with self.assertRaisesRegex(ValueError,'Changed original context source'):
    capture.validate_site(packet,root,'TownReviewed')

 def test_four_camera_original_frame_join_and_controls(self):
  capture=load('caravan_capture')
  class Actor:
   def __init__(self,actor_id,x,y):
    self.id=actor_id;self.x=x;self.y=y;self.controls=[]
    self.bounding_box=NS(get_world_vertices=lambda tr:[NS(x=x,y=y) for x,y in
     [[self.x-1,self.y-1],[self.x+1,self.y-1],[self.x+1,self.y+1],[self.x-1,self.y+1]]])
   def get_transform(self):return NS(location=NS(x=self.x,y=self.y),rotation=NS(yaw=0))
   def get_velocity(self):return NS(x=0,y=0)
   def apply_control(self,value):self.controls.append(value)
  actors=[Actor(1,10,0),Actor(2,20,0),Actor(3,30,0)]
  entrant=Actor(9,15,-3)
  listeners={};encoders={name:NS(frames=[],write=lambda data,name=name:encoders[name].frames.append(data))
                       for name in capture.CAMERAS}
  sensors={name:NS(listen=lambda fn,name=name:listeners.__setitem__(name,fn)) for name in capture.CAMERAS}
  counter=[99]
  def tick():
   counter[0]+=1
   for fn in listeners.values():fn(NS(frame=counter[0],raw_data=b'original pixels'))
  world=NS(tick=tick,get_snapshot=lambda:NS(frame=counter[0],timestamp=NS(elapsed_seconds=counter[0]*.05)))
  mapped=[];pipeline=[];history=[]
  packet={'road_forward_xy':[1,0],
          'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]],
          'selected_gap_index':0,'target_speed_mps':4,'road_id':7}
  carla=NS(VehicleControl=lambda **kw:kw)
  for outcome in ('occupy','stop_before'):
   counter[0]=99;mapped.clear();pipeline.clear();history.clear()
   for encoder in encoders.values():encoder.frames.clear()
   receipt=capture.capture_frames(world,carla,actors,entrant,sensors,encoders,
       NS(append=lambda f,t:mapped.append((f,t))),
       NS(write=lambda s:history.append(s)),
       NS(capture=lambda f,t:pipeline.append((f,t))),packet,outcome=outcome,frames=2)
   self.assertEqual(receipt['frames'],2)
   self.assertFalse(receipt['physical_acceptance_claimed'])
   self.assertEqual(len(history),2)
   self.assertEqual(mapped,pipeline)
   self.assertEqual({len(encoder.frames) for encoder in encoders.values()},{2})
   self.assertEqual(len(json.loads(history[0])['caravan_members']),3)
   self.assertTrue(all(actor.controls for actor in actors+[entrant]))
  self.assertEqual(receipt['plan']['outcome'],'stop_before')

class NativeRunnerTests(unittest.TestCase):
 def test_review_bundle_install_before_native_capture(self):
  native=load('caravan_native')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=root/'bundle';output=root/'attempt';bundle.mkdir();output.mkdir()
   (output/'construction.json').write_text('{}\n')
   packet={'site_review_status':'reviewed_native_site','reviewer':'map operator',
           'district_review_basis':'Native parcel and map review',
           'caravan_review_basis':'three participant route records',
           'highway_review_basis':'Native highway map and road topology',
           'camera_review_basis':'four original camera viewpoints',
           'native_map_id':'TownReviewed','outside_business_district':True,
           'caravan_or_motorcade':True,'highway_id':4,'road_id':7,
           'road_forward_xy':[1,0],
           'roadway_polygon_xy_m':[[0,-5],[80,-5],[80,5],[0,5]]}
   capture=load('caravan_capture')
   for key in capture.SOURCE_KEYS:
    name=key+'.txt';data=('reviewed '+key+'\n').encode()
    (bundle/name).write_bytes(data)
    packet[key]={'path':name,'sha256':hashlib.sha256(data).hexdigest()}
   (bundle/'site_packet.json').write_text(json.dumps(packet)+'\n')
   self.assertEqual(native._install_review(output,bundle),packet)
   self.assertTrue((output/'lane_source.txt').is_file())
   self.assertEqual((output/'construction.json').read_text(),'{}\n')
   packet['lane_source']['path']='construction.json'
   data=(output/'construction.json').read_bytes()
   (bundle/'construction.json').write_bytes(data)
   packet['lane_source']['sha256']=hashlib.sha256(data).hexdigest()
   (bundle/'site_packet.json').write_text(json.dumps(packet)+'\n')
   with self.assertRaisesRegex(ValueError,'collides'):
    native._install_review(output,bundle)

class CameraLifecycleTests(unittest.TestCase):
 def test_four_native_camera_spawns_and_reverse_cleanup(self):
  cameras=load('caravan_cameras')
  calls=[];stopped=[];destroyed=[]
  class Blueprint:
   def set_attribute(self,key,value):calls.append((key,value))
  def spawn(blueprint,transform,**kwargs):
   index=len([call for call in calls if call[0]=='spawn'])
   calls.append(('spawn',transform,kwargs))
   return NS(stop=lambda:stopped.append(index),destroy=lambda:destroyed.append(index))
  world=NS(get_blueprint_library=lambda:NS(find=lambda name:Blueprint()),spawn_actor=spawn)
  entrant=object();poses={name:name for name in cameras.PROFILE}
  with cameras.source_cameras(world,entrant,poses) as sensors:
   self.assertEqual(set(sensors),set(cameras.PROFILE))
   self.assertEqual(len([call for call in calls if call[0]=='spawn']),4)
   self.assertEqual(sum('attach_to' in call[2] for call in calls if call[0]=='spawn'),1)
  self.assertEqual(len(stopped),4)
  self.assertEqual(len(destroyed),4)
  self.assertEqual(len([call for call in calls if call[0]=='sensor_tick']),4)
