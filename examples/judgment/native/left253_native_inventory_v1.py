"""Native device absence and every incoming lane link, measured before/during capture.

No legal control status or driver judgment is assigned. An unresolved query fails;
there is no configuration-only absence or connectivity fallback.
"""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):
 with Path(p).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
def inventory_object(obj):
 return {'id':obj.id,'name':obj.name,'type':str(obj.type),'location_m':[obj.transform.location.x,obj.transform.location.y,obj.transform.location.z],'rotation_deg':[obj.transform.rotation.pitch,obj.transform.rotation.yaw,obj.transform.rotation.roll],'body_vertices_native_m':[[v.x,v.y,v.z] for v in obj.bounding_box.get_world_vertices(__import__('carla').Transform())]}
class NativeInventory:
 def __init__(self,world,mapping,out):
  self.world=world;self.mapping=mapping;self.out=Path(out);self.map_hash=sha(self.out/'road.xodr');self.implementation=sha(self.out/'runner.py')
  xml=ET.parse(self.out/'road.xodr').getroot();assert not xml.findall('.//signal') and not xml.findall('.//signalReference')
  roads={int(r.attrib['id']):r for r in xml.findall('road')};connections=[]
  for junction in xml.findall('junction'):
   for c in junction.findall('connection'):
    incoming=int(c.attrib['incomingRoad']);connector=int(c.attrib['connectingRoad'])
    for link in c.findall('laneLink'):
     lane=int(link.attrib['from']);destination=int(link.attrib['to']);length=float(roads[incoming].attrib['length']);s=.1 if lane>0 else length-.1
     wp=mapping.get_waypoint_xodr(incoming,lane,s);assert wp is not None and wp.road_id==incoming and wp.lane_id==lane
     successors=wp.next(1.);connected=[w for w in successors if w.road_id==connector and w.lane_id==destination and w.is_junction]
     assert connected,'Native incoming waypoint does not reach declared junction connector: '+str((incoming,lane,connector,destination))
     native_junction=connected[0].get_junction();assert native_junction is not None
     connections.append({'incoming_road':incoming,'incoming_lane':lane,'connecting_road':connector,'connecting_lane':destination,'incoming_observed':True,'connected_junction_observed':True,'native_incoming_waypoint_id':wp.id,'native_incoming_s_m':wp.s,'native_successor_waypoint_ids':[w.id for w in connected],'native_junction_id':native_junction.id,'xml_junction_id':junction.attrib['id'],'method':'Actual Map.get_waypoint_xodr and Waypoint.next(1m) reach the declared connector/lane and native junction; XML alone does not establish this observation'})
  assert connections
  write(self.out/'native_incoming_lane_topology.json',{'schema':'native-incoming-lane-topology-v1','map_sha256':self.map_hash,'instrumentation_sha256':self.implementation,'connections':connections,'legal_intersection_region':'external lateral roadway-boundary construction, separate from this native topology'})
  self.stream=(self.out/'native_control_inventory.jsonl').open('x',buffering=1)
 def capture(self,frame,time_s):
  import carla
  actors=list(self.world.get_actors());traffic=[{'id':a.id,'type_id':a.type_id,'attributes':dict(a.attributes)} for a in actors if a.type_id.startswith('traffic.')]
  unknown=sorted({a.type_id for a in actors if not a.type_id.startswith(('vehicle.','walker.','sensor.','controller.','traffic.')) and a.type_id!='spectator'})
  lights=[inventory_object(o) for o in self.world.get_environment_objects(carla.CityObjectLabel.TrafficLight)];signs=[inventory_object(o) for o in self.world.get_environment_objects(carla.CityObjectLabel.TrafficSigns)]
  row={'schema':'native-control-inventory-v1','frame':frame,'time_s':time_s,'map_sha256':self.map_hash,'instrumentation_sha256':self.implementation,'scope':'entire_recorded_world','map_name':self.mapping.name,'api_queries':['World.get_actors','World.get_environment_objects:TrafficLight','World.get_environment_objects:TrafficSigns'],'traffic_actor_inventory':traffic,'environment_light_inventory':lights,'environment_sign_inventory':signs,'unclassified_actor_types':unknown,'complete_actor_inventory':[{'id':a.id,'type_id':a.type_id,'parent_id':None if a.parent is None else a.parent.id} for a in actors]}
  self.stream.write(json.dumps(row,allow_nan=False)+'\n');assert not traffic and not lights and not signs and not unknown,'Uncontrolled synthetic context contradicted or unresolved by native inventory'
  return row
 def close(self):self.stream.close()
if __name__=='__main__':
 from build_left253_construction_v1 import xodr
 root=ET.fromstring(xodr());print(json.dumps({'offline_xml_connections':sum(len(c.findall('laneLink')) for c in root.findall('junction/connection')),'native_connectivity_verified':False,'native_inventory_verified':False,'requires_live_queries_before_and_during_new_delivery':True}))
