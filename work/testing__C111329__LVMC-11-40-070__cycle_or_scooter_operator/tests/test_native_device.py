import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_device import read_site, construct, audit_original_history
from comparison_audit import audit

SITE = {"source_kind":"original_local_native_site_inventory","map_name":"TownX","jurisdiction_source":"map-survey","governed_approach":"northbound","stop_line":[[0,-3],[0,3]],"vehicle_route":[[-10,0,0],[10,0,0]],"device_id":"10","device_type":"signal","device_authority_source":"traffic-order","vehicle_applicability_source":"sign-face","bike_blueprint_id":"vehicle.bicycle","participant_class":"human_powered_bicycle","classification_source":"reviewed test bicycle type","police_authority_source":"dispatch"}
CASE={"case_id":"case-red","device_type":"signal","officer_direction":"none"}
class Location:
 def __init__(self,x=0,y=0,z=0):self.x,self.y,self.z=x,y,z
 def distance(self,other):return abs(self.x-other.x)+abs(self.y-other.y)+abs(self.z-other.z)
class Transform:
 def __init__(self,location):self.location=location
class Actor:
 id=10;is_alive=True;type_id="vehicle.bicycle"
 def __init__(self,loc=None):self.loc=loc or Location();self.destroyed=False
 def get_transform(self):return Transform(self.loc)
 def destroy(self):self.destroyed=True
class Library:
 def find(self,x):return type("BP",(),{"id":x})()
class World:
 def __init__(self):self.fail=False;self.created=None
 def get_map(self):return type("Map",(),{"name":"TownX"})()
 def get_actors(self):return [Actor()]
 def get_blueprint_library(self):return Library()
 def spawn_actor(self,bp,transform):
  self.created=Actor(Location(100,0,0) if self.fail else transform.location)
  return self.created
CARLA=type("Carla",(),{"Transform":Transform,"Location":Location})

def samples(officer=False):
 rows=[]
 for i,x in enumerate([-1.0,1.0]):
  rows.append({"source_kind":"original_native","frame":50+i,"time_s":2+i*.05,"bike_id":"22","bike_blueprint_id":"vehicle.bicycle","device_id":"10","device_state":"red","bike_front_xy":[x,0],"officer_actor_id":"99" if officer else None,"officer_command":"proceed" if officer else "none","officer_authority_source":"dispatch" if officer else None})
 return rows
class TestDevice(unittest.TestCase):
 def test_source_hash_and_fields(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"site.json";p.write_text(json.dumps(SITE));h=hashlib.sha256(p.read_bytes()).hexdigest()
   self.assertEqual(read_site(p,h),SITE)
   with self.assertRaisesRegex(ValueError,"hash mismatch"):read_site(p,"0"*64)
   bad=dict(SITE);bad.pop("device_authority_source");p.write_text(json.dumps(bad))
   with self.assertRaisesRegex(ValueError,"missing Native site field"):read_site(p,hashlib.sha256(p.read_bytes()).hexdigest())
   for participant in ("electric_bicycle", "electric_scooter"):
    p.write_text(json.dumps({**SITE,"participant_class":participant}))
    with self.assertRaisesRegex(ValueError,"selected witness requires a human-powered bicycle"):
     read_site(p,hashlib.sha256(p.read_bytes()).hexdigest())
 def test_construct_and_cleanup(self):
  world=World();result=construct(world,CARLA,SITE,CASE);self.assertEqual(result["bike"].type_id,"vehicle.bicycle")
  world.fail=True
  with self.assertRaisesRegex(ValueError,"spawn location readback"):construct(world,CARLA,SITE,CASE)
  self.assertTrue(world.created.destroyed)
  with self.assertRaisesRegex(ValueError,"Police Officer authority"):construct(World(),CARLA,{k:v for k,v in SITE.items() if k!="police_authority_source"},{**CASE,"officer_direction":"proceed"})
 def test_original_measurement(self):
  value=audit_original_history(CASE,SITE,samples());self.assertEqual(value["crossing_frame"],51);self.assertEqual(value["device_state_at_crossing"],"red")
  with self.assertRaisesRegex(ValueError,"identity changed"):audit_original_history(CASE,SITE,[samples()[0],{**samples()[1],"bike_id":"23"}])
  with self.assertRaisesRegex(ValueError,"Officer identity"):audit_original_history({**CASE,"officer_direction":"proceed"},SITE,samples())
  self.assertEqual(audit_original_history({**CASE,"officer_direction":"proceed"},SITE,samples(True))["officer_command_at_crossing"],"proceed")
 def test_comparison(self):
  context={"map_name":"TownX","jurisdiction_source":"survey","governed_approach":"northbound","bike_blueprint_id":"bicycle","route":"northbound","camera_contract":"four","duration_s":45,"device_authority_source":"order","vehicle_applicability_source":"sign","device_type":"signal","device_instruction":"red","officer_direction":"none"}
  left={"format":"c111329-saved-instruction-measurement","case_id":"a","source_kind":"original_native","legal_assessment":"unresolved","device_id":"10","bike_id":"22","crossing_frame":None,"hold_window_frames":[980,999],"device_state_at_response":"red","officer_command_at_response":"none","context":context,"source_hashes":{"site":"aaa","trace":"bbb"}}
  right={**left,"case_id":"b","crossing_frame":51,"hold_window_frames":None}
  comp={"comparison_id":"obey-red","case_ids":["a","b"],"deliberate_variable":"operator_motion"}
  self.assertTrue(audit(comp,left,right)["passed"])
  with self.assertRaisesRegex(ValueError,"variable did not differ"):audit(comp,left,{**right,"crossing_frame":None,"hold_window_frames":[980,999]})
  with self.assertRaisesRegex(ValueError,"fixed condition changed"):audit(comp,left,{**right,"context":{**context,"map_name":"TownY"}})
  with self.assertRaisesRegex(ValueError,"missing source-bound context"):audit(comp,left,{**right,"source_hashes":{}})
if __name__=="__main__":unittest.main()
