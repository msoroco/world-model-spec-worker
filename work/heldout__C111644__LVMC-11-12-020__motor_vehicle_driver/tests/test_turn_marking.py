from __future__ import annotations
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('turn_marking',Path(__file__).resolve().parents[1]/'turn_marking.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
n=importlib.util.spec_from_file_location('indication_native',Path(__file__).resolve().parents[1]/'indication_native.py')
native=importlib.util.module_from_spec(n);n.loader.exec_module(native)
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
if __name__=='__main__':unittest.main()
