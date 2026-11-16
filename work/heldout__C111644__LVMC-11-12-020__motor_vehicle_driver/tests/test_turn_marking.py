from __future__ import annotations
import hashlib,importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
s=importlib.util.spec_from_file_location('turn_marking',Path(__file__).resolve().parents[1]/'turn_marking.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
n=importlib.util.spec_from_file_location('indication_native',Path(__file__).resolve().parents[1]/'indication_native.py')
native=importlib.util.module_from_spec(n);n.loader.exec_module(native)
import runner
class Fake:
 def __init__(self):self.calls=[]
 def intersection(self,**x):self.calls.append(('intersection',x));return x
 def turn_course_indication(self,**x):self.calls.append(('indication',x));return x
 def vehicle(self,**x):self.calls.append(('vehicle',x));return x
class MarkingTests(unittest.TestCase):
 def test_each_indication_creates_authorized_marker_and_route(self):
  for kind in ('marker','button','other_indication'):
   for variant in ('follow','depart'):
    f=Fake();scene=m.construct(f,kind,variant)
    self.assertEqual([x[0] for x in f.calls],['intersection','indication','vehicle'])
    self.assertEqual(scene['indication']['kind'],kind)
    self.assertEqual(scene['ego']['route']==scene['indication']['course_xy'],variant=='follow')
 def sample(self):
  indication={'kind':'marker','authorized':True,'within_intersection':True,
              'authorization_source':'original-control-record','course_xy':[[-20,0],[-5,0],[0,5],[0,20]]}
  frames=[{'frame':i,'time_s':i*.05,'subject_source':'original-ego','subject_center_xy':p}
          for i,p in enumerate(([-20,0],[-5,0],[0,5],[0,20]))]
  return indication,frames
 def test_original_course_measurement_and_source_rejection(self):
  indication,frames=self.sample();r=m.measure(indication,frames)
  self.assertEqual(r['max_center_deviation_m'],0);self.assertIsNone(r['legal_obedience_judgment'])
  indication['authorization_source']=''
  with self.assertRaisesRegex(ValueError,'authorized'):m.measure(indication,frames)
  indication['authorization_source']='source';frames[2]['subject_source']=''
  with self.assertRaisesRegex(ValueError,'synchronized'):m.measure(indication,frames)
 def test_comparison_fixed_conditions(self):
  indication,frames=self.sample();a=m.measure(indication,frames)
  a.update(intersection_hash='i',course_hash='c',camera_plan_hash='cam',duration_s=8,subject_hash='s')
  b=dict(a,max_center_deviation_m=3)
  self.assertTrue(m.audit_comparison(a,b,'route_response')['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,course_hash='x'),'route_response')

 def test_sourced_routes_isolate_response_from_both_approaches(self):
  for kind in ('marker','button','other_indication'):
   for approach in (-20.,20.):
    with self.subTest(kind=kind,approach=approach):
     source={'indication_form':kind,'intersection_id':'junction-1',
       'intersection_polygon_xy_m':[[-10.,-10.],[10.,-10.],[10.,10.],[-10.,10.]],
       'indicated_course_xy_m':[[approach,0.],[0.,0.],[0.,20.]]}
     follow=m.native_route_plan(source,'follow')
     depart=m.native_route_plan(source,'depart')
     self.assertEqual(follow['course_xy_m'],depart['course_xy_m'])
     self.assertEqual(follow['target_route_xy_m'][:2],depart['target_route_xy_m'][:2])
     self.assertEqual(follow['target_route_xy_m'][-1],[0.,20.])
     self.assertEqual(depart['target_route_xy_m'][-1],[4.,20.])
     self.assertIsNone(depart['legal_obedience_judgment'])

 def test_native_route_controller_steers_brakes_and_rejects_bad_source(self):
  source={'indication_form':'marker','intersection_id':'junction-1',
    'intersection_polygon_xy_m':[[-10.,-10.],[10.,-10.],[10.,10.],[-10.,10.]],
    'indicated_course_xy_m':[[-20.,0.],[0.,0.],[0.,20.]]}
  self.assertGreater(m.control_to_target((0.,0.),(1.,0.),(2.,0.),(0.,10.),3.)['steer'],0.)
  self.assertGreater(m.control_to_target((0.,0.),(1.,0.),(8.,0.),(10.,0.),3.)['brake'],0.)
  self.assertEqual(m.control_to_target((0.,0.),(1.,0.),(0.,0.),(0.,0.),3.)['brake'],1.)
  with self.assertRaisesRegex(ValueError,'Nonfinite'):
   m.control_to_target((float('nan'),0.),(1.,0.),(0.,0.),(10.,0.),3.)
  source['indicated_course_xy_m']=[[-20.,-20.],[-18.,-18.],[-16.,-16.]]
  with self.assertRaisesRegex(ValueError,'misses intersection'):
   m.native_route_plan(source,'follow')

 def test_route_response_audit_requires_fixed_source_and_observed_difference(self):
  cid='heldout__C111644__LVMC-11-12-020__motor_vehicle_driver__marker_'
  rows=lambda values:[{'frame':i,'time_s':i*.05,'deviation_m':value}
                      for i,value in enumerate(values)]
  a={'case_id':cid+'follow','samples':rows([0.,0.,.1])}
  b={'case_id':cid+'depart','samples':rows([0.,.5,2.])}
  plan={'route_variant':'follow','course_xy_m':[[0,0],[1,0],[1,1]],
        'target_route_xy_m':[[0,0],[1,0],[1,1]]}
  departed=dict(plan,route_variant='depart',target_route_xy_m=[[0,0],[1,0],[3,1]])
  self.assertTrue(m._route_response_from_reports(a,b,b'same',b'same',plan,departed)['comparison_complete'])
  button_a=dict(a,case_id=cid.replace('marker_','button_')+'follow')
  button_b=dict(b,case_id=cid.replace('marker_','button_')+'depart')
  self.assertTrue(m._route_response_from_reports(button_a,button_b,b'same',b'same',plan,departed)['comparison_complete'])
  with self.assertRaisesRegex(ValueError,'case identity'):
   m._route_response_from_reports(a,button_b,b'same',b'same',plan,departed)
  with self.assertRaisesRegex(ValueError,'Fixed indication source'):
   m._route_response_from_reports(a,b,b'same',b'changed',plan,departed)
  with self.assertRaisesRegex(ValueError,'response difference absent'):
   m._route_response_from_reports(a,dict(b,samples=rows([0.,0.,.1])),b'same',b'same',plan,departed)
  with self.assertRaisesRegex(ValueError,'frame/time sampling'):
   m._route_response_from_reports(a,dict(b,samples=[{'frame':5,'time_s':0.,'deviation_m':2.}]),b'same',b'same',plan,departed)

class NativeIndicationTests(unittest.TestCase):
 def record(self,kind):
  return {'authority_document':'fixture claim only','intersection_id':'junction-1','map_name':'TestMap',
   'indication_form':kind,'intersection_polygon_xy_m':[[-10,-10],[10,-10],[10,10],[-10,10]],
   'indicated_course_xy_m':[[-20,0],[0,0],[0,20]],
   'form_blueprints':{kind:[f'fixture.{kind}']},
   'indications':[{'form':kind,'blueprint_id':f'fixture.{kind}','x':0.,'y':0.,'z':0.,'yaw':0.}]}
 def source(self,folder,record):
  path=Path(folder)/'authority.json';path.write_text(json.dumps(record))
  return path,hashlib.sha256(path.read_bytes()).hexdigest()
 def world(self,*,junction=True,readback_shift=0.):
  class Location:
   def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z
  class Transform:
   def __init__(self,x,y,z,yaw):self.location=Location(x,y,z);self.yaw=yaw
  class Actor:
   destroyed=False
   def __init__(self,transform):self.transform=Transform(transform.location.x+readback_shift,transform.location.y,transform.location.z,transform.yaw)
   def get_transform(self):return self.transform
   def destroy(self):self.destroyed=True
  class Map:
   name='TestMap'
   def get_waypoint(self,location):return type('Waypoint',(),{'is_junction':junction})()
  class Library:
   def find(self,blueprint):return blueprint
  class World:
   spawned=[]
   def get_map(self):return Map()
   def get_blueprint_library(self):return Library()
   def try_spawn_actor(self,blueprint,transform):
    actor=Actor(transform);self.spawned.append((blueprint,actor));return actor
  return World(),Transform
 def test_three_forms_spawn_distinct_sourced_blueprints(self):
  for kind in ('marker','button','other_indication'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
    path,digest=self.source(temp,self.record(kind));world,transform=self.world()
    result=native.place_indications(world,path,digest,kind,transform)
    self.assertEqual(world.spawned[0][0],f'fixture.{kind}')
    self.assertEqual(result['physical_xy_m'],[[0.,0.]])
    self.assertFalse(result['authorization_verified_by_worker'])
    self.assertFalse(result['visible_pixels_verified'])
 def test_rejects_changed_form_hash_and_outside_polygon(self):
  with tempfile.TemporaryDirectory() as temp:
   record=self.record('button');path,digest=self.source(temp,record);world,transform=self.world()
   with self.assertRaisesRegex(ValueError,'form'):native.place_indications(world,path,digest,'marker',transform)
   record['indications'][0]['x']=20.;path.write_text(json.dumps(record))
   with self.assertRaisesRegex(ValueError,'hash'):native.place_indications(world,path,digest,'button',transform)
   new_digest=hashlib.sha256(path.read_bytes()).hexdigest()
   with self.assertRaisesRegex(ValueError,'outside'):native.place_indications(world,path,new_digest,'button',transform)
 def test_rejects_nonjunction_and_destroys_bad_readback(self):
  with tempfile.TemporaryDirectory() as temp:
   path,digest=self.source(temp,self.record('other_indication'))
   world,transform=self.world(junction=False)
   with self.assertRaisesRegex(ValueError,'junction'):native.place_indications(world,path,digest,'other_indication',transform)
   self.assertEqual(world.spawned,[])
   world,transform=self.world(readback_shift=1.)
   with self.assertRaisesRegex(ValueError,'readback'):native.place_indications(world,path,digest,'other_indication',transform)
   self.assertTrue(world.spawned[0][1].destroyed)

 def test_exact_runner_checks_identity_and_builds_all_four_native_cameras(self):
  case='heldout__C111644__LVMC-11-12-020__motor_vehicle_driver__marker_follow'
  config={'selected_case_id':case,'supported_case_ids':[case],
    'law_id':'LVMC-11-12-020','cell_id':'C111644','actor':'motor_vehicle_driver',
    'rate_hz':20,'frames':160,'duration_s':8,
    'cameras':[{'name':name,'width':spec[2][0],'height':spec[2][1]}
               for name,spec in runner.CAMERAS.items()]}
  self.assertEqual(runner._check_config(config),('marker','follow'))
  with self.assertRaisesRegex(ValueError,'configuration changed'):
   runner._check_config(dict(config,frames=159))
  class Blueprint:
   def __init__(self):self.attributes={}
   def set_attribute(self,key,value):self.attributes[key]=value
  class Sensor:
   def listen(self,callback):self.callback=callback
   def stop(self):self.stopped=True
   def destroy(self):self.destroyed=True
  class World:
   def __init__(self):self.blueprints=[];self.sensors=[]
   def get_blueprint_library(self):return self
   def find(self,name):
    self.asserted=name;item=Blueprint();self.blueprints.append(item);return item
   def spawn_actor(self,blueprint,transform,attach_to):
    self.assertEqualAttach=attach_to;item=Sensor();self.sensors.append(item);return item
  class Process:
   def __init__(self):self.stdin=io.BytesIO()
   def poll(self):return None
   def wait(self,timeout):return 0
  world=World()
  carla=SimpleNamespace(Transform=lambda *parts:parts,Location=lambda *parts:parts,
                        Rotation=lambda *parts:parts)
  with tempfile.TemporaryDirectory() as directory,patch.object(runner.subprocess,'Popen',return_value=Process()):
   camera=runner.OriginalCameras(world,carla,'ego',directory)
   self.assertEqual(len(world.sensors),4)
   self.assertEqual(world.assertEqualAttach,'ego')
   self.assertEqual([item.attributes['sensor_tick'] for item in world.blueprints],['0.05']*4)
   with self.assertRaisesRegex(ValueError,'Missing synchronized'):
    camera.wait(1,timeout_s=.001)
   camera.close()
   self.assertTrue(all(sensor.destroyed and sensor.stopped for sensor in world.sensors))

 def test_native_capture_handoff_accepts_materialized_directory_and_sourced_env(self):
  digest='a'*64
  self.assertEqual(runner._native_source_args(None,None,{'TURN_INDICATION_SOURCE':'source.json',
                   'TURN_INDICATION_SHA256':digest}),('source.json',digest))
  with self.assertRaisesRegex(ValueError,'TURN_INDICATION_SOURCE'):
   runner._native_source_args(None,None,{})
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   (root/'construction.json').write_text('{}')
   (root/'config.json').write_text('{}')
   (root/'runner.py').write_text('')
   runner._check_attempt_dir(root)
   (root/'turn_body_original.jsonl').write_text('')
   with self.assertRaisesRegex(ValueError,'already has acquisition'):
    runner._check_attempt_dir(root)

 def test_saved_original_turn_sources_derive_channels_and_reject_missing_camera(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   source=self.record('marker')
   (root/'turn_indication_original.json').write_text(json.dumps(source))
   plan={'course_xy_m':source['indicated_course_xy_m'],'indication_form':'marker',
         'intersection_id':'junction-1','route_variant':'follow'}
   (root/'turn_route_plan.json').write_text(json.dumps(plan))
   locations=[[-20.,0.],[0.,0.],[0.,20.]]
   body=[];trace=[];mapping=[]
   for i,(x,y) in enumerate(locations):
    frame,time=100+i,5.+i*.05
    corners=[[x-.1,y-.1],[x+.1,y-.1],[x+.1,y+.1],[x-.1,y+.1]]
    body.append({'frame':frame,'time_s':time,'subject':{
     'actor_id':1,'body_vertices_m':corners,'center_xy_m':[x,y]}})
    trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y}})
    mapping.append({'video_frame':i,'carla_frame':frame,'native_frame':frame,'time_s':time})
   def put(name,rows):
    (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
   put('turn_body_original.jsonl',body);put('trace.jsonl',trace)
   put('video_frames.jsonl',mapping)
   for name in m.CAMERAS:
    (root/(name+'.mkv')).write_bytes(b'fixture bytes only')
    put(name+'-frames.jsonl',[{'video_frame':i,'native_frame':row['frame'],
                               'time_s':row['time_s']} for i,row in enumerate(body)])
   names=['turn_indication_original.json','turn_route_plan.json',
          'turn_body_original.jsonl','trace.jsonl','video_frames.jsonl']
   names += [name+'.mkv' for name in m.CAMERAS]
   names += [name+'-frames.jsonl' for name in m.CAMERAS]
   (root/'turn_source_receipt.json').write_text(json.dumps({
    'case_id':'heldout__C111644__LVMC-11-12-020__motor_vehicle_driver__marker_follow',
    'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                     for name in names}}))
   report=m.finalize_original_sources(root)
   self.assertEqual(set(report['measurements']),set(m.CHANNELS))
   self.assertEqual(report['measurements']['original_course_deviation_m']['value'][-1]['value'],0.)
   self.assertFalse(report['physical_acceptance_claimed'])
   (root/'overview.mkv').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source'):
    m.analyze_original_sources(root)
if __name__=='__main__':unittest.main()
