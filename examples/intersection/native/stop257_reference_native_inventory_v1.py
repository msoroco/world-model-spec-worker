"""Original complete native entrance/control inventories for stop257, no verdicts."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class NativeInventory:
 def __init__(self,world,mapping,out,runner,markings):
  self.world=world;self.mapping=mapping;self.out=Path(out);self.map_hash=sha(self.out/'road.xodr');self.runner_sha=sha(runner);self.helper_sha=sha(__file__);self.marking_ids={a.id for a in markings};xml=ET.parse(self.out/'road.xodr').getroot();roads={int(r.attrib['id']):r for r in xml.findall('road')};connections=[]
  for junction in xml.findall('junction'):
   for c in junction.findall('connection'):
    incoming=int(c.attrib['incomingRoad']);connector=int(c.attrib['connectingRoad'])
    for link in c.findall('laneLink'):
     lane=int(link.attrib['from']);dest=int(link.attrib['to']);length=float(roads[incoming].attrib['length']);wp=mapping.get_waypoint_xodr(incoming,lane,.1 if lane>0 else length-.1);assert wp is not None
     nexts=[w for w in wp.next(1) if w.road_id==connector and w.lane_id==dest and w.is_junction];assert nexts,'Missing actual incoming connection'
     connections.append({'incoming_road':incoming,'incoming_lane':lane,'connecting_road':connector,'connecting_lane':dest,'incoming_observed':True,'connected_junction_observed':True,'incoming_native_id':wp.id,'native_successor_ids':[w.id for w in nexts],'native_junction_id':nexts[0].junction_id})
  landmarks=[]
  for l in mapping.get_all_landmarks():
   valid=[{'from_lane':int(v[0]),'to_lane':int(v[1])} for v in l.get_lane_validities()]
   landmarks.append({'id':l.id,'type':l.type,'road_id':l.road_id,'s':l.s,'orientation':str(l.orientation),'valid_lanes':valid,'native_transform':str(l.transform)})
  assert len(landmarks)==1 and all(v['type']=='206' for v in landmarks),'Unexpected native map controls'
  (self.out/'native_incoming_lane_topology.json').write_text(json.dumps({'schema':'stop257-native-incoming-lane-topology-v1','map_sha256':self.map_hash,'runner_sha256':self.runner_sha,'helper_sha256':self.helper_sha,'connections':connections,'landmarks':landmarks,'source_signals':[dict(s.attrib) for s in xml.findall('.//signal')],'native_control_semantics':'Physical Native sign/entrance observation. Authorization and non-through-highway status remain separately sourced external synthetic assumptions.'},indent=2)+'\n')
  assert landmarks[0]['road_id']==1 and all(s.attrib.get('type') not in ('205','206') for r in xml.findall('road') if r.attrib['id']!='1' for s in r.findall('./signals/signal')),'Unexpected entrance obligation'
  self.entrances=[{'incoming_road':road,'incoming_lanes':sorted({c['incoming_lane'] for c in connections if c['incoming_road']==road}),'control':'stop_sign' if road==1 else 'none','stop_yield_obligation':road==1,'source':'Complete original XODR signals plus actual Native landmarks/topology','administrative_status':'Externally synthetic non-through/public-way/authorized West STOP; not inferred from appearance'} for road in [1,2,3,4]]
  assert all(e['incoming_lanes'] for e in self.entrances),'Missing entrance inventory'
  self.stream=(self.out/'native_control_inventory.jsonl').open('x',buffering=1)
 def capture(self,frame,time_s):
  import carla
  actors=list(self.world.get_actors());unknown=[{'id':a.id,'type_id':a.type_id} for a in actors if a.id not in self.marking_ids and a.type_id!='spectator' and not a.type_id.startswith(('vehicle.','sensor.','traffic.stop'))]
  def environment(label):
   return [{'id':o.id,'name':o.name,'type':str(o.type),'position_m':[o.transform.location.x,o.transform.location.y,o.transform.location.z],'vertices_m':[[v.x,v.y,v.z] for v in o.bounding_box.get_world_vertices(carla.Transform())]} for o in self.world.get_environment_objects(label)]
  traffic=[{'id':a.id,'type_id':a.type_id,'attributes':dict(a.attributes),'native_transform':str(a.get_transform())} for a in actors if a.type_id.startswith('traffic.')];lights=environment(carla.CityObjectLabel.TrafficLight);signs=environment(carla.CityObjectLabel.TrafficSigns);sidewalks=environment(carla.CityObjectLabel.Sidewalks)
  row={'schema':'stop257-native-control-inventory-v1','frame':frame,'time_s':time_s,'map_sha256':self.map_hash,'runner_sha256':self.runner_sha,'helper_sha256':self.helper_sha,'scope':'entire_recorded_world','map_name':self.mapping.name,'api_queries':['World.get_actors','World.get_environment_objects:TrafficLight','World.get_environment_objects:TrafficSigns','World.get_environment_objects:Sidewalks'],'traffic_actor_inventory':traffic,'environment_light_inventory':lights,'environment_sign_inventory':signs,'environment_sidewalk_inventory':sidewalks,'unclassified_actor_types':unknown,'complete_actor_inventory':[{'id':a.id,'type_id':a.type_id,'parent_id':None if a.parent is None else a.parent.id} for a in actors],'observed_physical_road_marking_actor_ids':sorted(self.marking_ids),'observed_physical_stopline_actor_ids':sorted(a.id for a in actors if a.id in self.marking_ids and 'physical_stopline_' in a.attributes.get('role_name','')),'observed_physical_crosswalk_actor_ids':sorted(a.id for a in actors if a.id in self.marking_ids and 'crosswalk_stripe_' in a.attributes.get('role_name',''))}
  row['entrance_obligations']=self.entrances
  row['participant_entrance_obligations']=[{'actor_id':a.id,'role':a.attributes.get('role_name'),'incoming_road':1 if a.attributes.get('role_name','').endswith('_ego') else 3,'stop_yield_obligation':a.attributes.get('role_name','').endswith('_ego'),'governing_control':'West STOP' if a.attributes.get('role_name','').endswith('_ego') else 'No stop/yield sign on recorded incoming road3','scope':'Selected entrance obligation; no immunity from other duties'} for a in actors if a.type_id.startswith('vehicle.')]
  row['actual_vehicle_waypoints']=[]
  for actor in actors:
   if actor.type_id.startswith('vehicle.'):
    wp=self.mapping.get_waypoint(actor.get_location(),project_to_road=False,lane_type=carla.LaneType.Driving)
    row['actual_vehicle_waypoints'].append({'actor_id':actor.id,'role':actor.attributes.get('role_name'),'native_road_id':None if wp is None else wp.road_id,'native_lane_id':None if wp is None else wp.lane_id,'native_station_m':None if wp is None else wp.s,'junction':None if wp is None else wp.is_junction})
  self.stream.write(json.dumps(row,allow_nan=False)+'\n');assert len(traffic)==1 and all(v['type_id']=='traffic.stop' for v in traffic) and not lights and not unknown,'Actual governing-control context changed or unresolved';return row
 def close(self):self.stream.close()
