"""Actual Native place sight queries, separate from actual-user rel.visible.

Virtual eyes/bodies occupy declared incoming through-lane stations whether or
not actual users are there. Every collision label is retained. Bounds are
sampled/censored and never a hazard standard or legal seeing/perception test.
"""
import math,hashlib
from pathlib import Path

def xyz(p):return [p.x,p.y,p.z]
class PlaceSight:
 def __init__(self,carla,world,mapping,actor,maximum_m=200.,step_m=10.,tolerance_m=.25):
  self.carla=carla;self.world=world;self.mapping=mapping;self.actor=actor;self.maximum=maximum_m;self.step=step_m;self.tolerance=tolerance_m;self.template=actor.bounding_box;self.chassis_offset=actor.get_transform().location.z;self.routes=[]
  for road,lanes,station in [(3,[-2,-1],392.99),(4,[1,2],.01)]:
   for lane in lanes:
    anchor=mapping.get_waypoint_xodr(road,lane,station)
    if anchor is None or anchor.lane_type!=carla.LaneType.Driving:raise ValueError('Missing actual through approach')
    self.routes.append({'road':road,'lane':lane,'anchor':anchor,'cache':{0.:anchor}})
 def waypoint(self,route,distance):
  if distance not in route['cache']:
   choices=route['anchor'].previous(distance);route['cache'][distance]=choices[0] if len(choices)==1 else None
  return route['cache'][distance]
 def ray(self,eye,target,subject_transform,virtual_transform,virtual_box):
  blockers=[];filtered=[]
  for hit in self.world.cast_ray(eye,target):
   why=None
   if self.actor.bounding_box.contains(hit.location,subject_transform):why='actual_subject_body'
   elif virtual_box.contains(hit.location,virtual_transform):why='declared_hypothetical_body_volume'
   elif hit.location.distance(eye)<.05:why='declared_eye_endpoint_margin'
   elif hit.location.distance(target)<.02:why='declared_target_endpoint_margin'
   item={'label':str(hit.label),'location_m':xyz(hit.location),'distance_from_eye_m':hit.location.distance(eye)}
   if why:item['excluded_reason']=why;filtered.append(item)
   else:blockers.append(item)
  return {'observer_m':xyz(eye),'target_m':xyz(target),'blockers':blockers,'excluded_hits':filtered,'clear':not blockers}
 def capture(self,frame,time_s):
  from carla_sgg.law_evidence import sampled_horizon
  if self.world.get_snapshot().frame!=frame:raise ValueError('Place queries require current original frame')
  c=self.carla;transform=self.actor.get_transform();eye=transform.transform(c.Location(z=1.5));body=sorted(self.actor.bounding_box.get_world_vertices(transform),key=lambda p:p.z)[-4:];approaches=[]
  for route in self.routes:
   observed={}
   def sample(distance,direction):
    key=(float(distance),direction)
    if key in observed:return observed[key]['rays']
    waypoint=self.waypoint(route,float(distance))
    if waypoint is None:return None
    pose=c.Transform(c.Location(waypoint.transform.location),waypoint.transform.rotation);pose.location.z+=self.chassis_offset;box=self.template
    if direction=='from_actual_model_point':observer=eye;targets=sorted(box.get_world_vertices(pose),key=lambda p:p.z)[-4:]
    else:observer=pose.transform(c.Location(z=1.5));targets=body
    rays=[self.ray(observer,target,transform,pose,box) for target in targets];observed[key]={'lane_route_distance_m':float(distance),'direction':direction,'hypothetical_vehicle_native_pose':str(pose),'hypothetical_native_matrix':pose.get_matrix(),'rays':rays};return rays
   outgoing=sampled_horizon(lambda d:sample(d,'from_actual_model_point'),self.maximum,self.step,self.tolerance);incoming=sampled_horizon(lambda d:sample(d,'toward_actual_subject_body'),self.maximum,self.step,self.tolerance);approaches.append({'road_id':route['road'],'lane_id':route['lane'],'anchor_station_m':route['anchor'].s,'anchor_native_m':xyz(route['anchor'].transform.location),'from_actual_model_point_horizon':outgoing,'toward_actual_subject_body_horizon':incoming,'all_actual_Native_queries':list(observed.values())})
  if self.world.get_snapshot().frame!=frame:raise ValueError('Original world advanced during place query')
  horizons=[v[k] for v in approaches for k in ['from_actual_model_point_horizon','toward_actual_subject_body_horizon']];unknown=any(v.get('unknown') for v in horizons)
  return {'schema':'stop257-Native-cross-traffic-place-sight-v1','sampler_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'hypothetical_body_local_vertices_m':[xyz(v) for v in self.template.get_local_vertices()],'hypothetical_chassis_offset_m':self.chassis_offset,'frame':frame,'time_s':time_s,'actual_model_point_native_m':xyz(eye),'model_point_local_m':[0,0,1.5],'minimum_sampled_place_horizon_m':None if unknown else min(v['distance_m'] for v in horizons),'unknown_route':unknown,'approaches':approaches,'measurement_convention':'Incoming through-lane waypoint-route metres upstream of each actual near-intersection approach anchor; both actual model point to hypothetical body and hypothetical eye to actual subject top-body. Four actual incoming lanes, irrespective of actual counterpart presence. Not Euclidean ray length.','hypothetical_body_convention':'Actual Native subject MKZ bounding box/chassis offset; top four body corners; vehicle-level waypoint pose, eyes1.5m above origin. All actual boxes/controls retained separately.','search_maximum_m':self.maximum,'scan_step_m':self.step,'first_sampled_occlusion_tolerance_m':self.tolerance,'censoring_and_limits':['at_least means sampled search-censored, not a physical cutoff','Narrow/nonmonotone occlusions between coarse samples may be missed','Collision visibility with declared body/endpoint exclusions is not optical recognizability, anatomical eye, gaze or perception','No numeric hazard, yielding, nearest-point or compliance criterion is defined'],'actual_user_visibility_remains_separate':True,'legal_compliance_established':False}
