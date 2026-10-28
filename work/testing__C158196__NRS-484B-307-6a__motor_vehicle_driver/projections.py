"""Measured native observation projections. No legal thresholds or inferred authority."""
import json,math

def inside(p,polygon):
 x,y=p[:2];odd=False
 for a,b in zip(polygon,polygon[1:]+polygon[:1]):
  cross=(x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
  if abs(cross)<1e-8 and min(a[0],b[0])-1e-8<=x<=max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8<=y<=max(a[1],b[1])+1e-8:return True
  if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:odd=not odd
 return odd

def hull(vertices):
 points=sorted(set((p[0],p[1]) for p in vertices))
 if len(points)<3:return [list(p) for p in points]
 def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 lower=[];upper=[]
 for p in points:
  while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
  lower.append(p)
 for p in reversed(points):
  while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
  upper.append(p)
 return [list(p) for p in lower[:-1]+upper[:-1]]

def intersects(vertices,polygon):
 vertices=hull(vertices)
 if any(inside(v,polygon) for v in vertices):return True
 if any(inside(v,[p[:2] for p in vertices]) for v in polygon):return True
 def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 for a,b in zip(vertices,vertices[1:]+vertices[:1]):
  for c,d in zip(polygon,polygon[1:]+polygon[:1]):
   if turn(a,b,c)*turn(a,b,d)<0 and turn(c,d,a)*turn(c,d,b)<0:return True
 return False

def gap(a,b):
 angle=math.radians(a['heading_deg']);f=[math.cos(angle),math.sin(angle)]
 return min(v[0]*f[0]+v[1]*f[1] for v in b['body_vertices_m'])-max(v[0]*f[0]+v[1]*f[1] for v in a['body_vertices_m'])

def validate_visibility(value):
 if value.get('visibility_criterion')!='any_of_nine_body_samples' or value.get('unknown_reason'):raise ValueError('Nine-point visibility geometry unknown')
 required=set(value.get('required_lane_ids',[]));approaches=value.get('approaches',[])
 if not required or {a.get('lane_id') for a in approaches}!=required:raise ValueError('Incomplete incoming sight approaches')
 for a in approaches:
  h=a.get('any_body_sight_horizon',{})
  if a.get('unknown_reason') or h.get('unknown') or h.get('bound') not in ('at_least','first_sampled_occlusion'):raise ValueError('Sight route limited or ambiguous')
  if len(a.get('body_rays_at_probe',[]))!=9:raise ValueError('Missing any-body probe rays')
  if h['bound']=='at_least' and h.get('distance_m',0)<230:raise ValueError('Incomplete declared230m sight search')
 return True

def require(mapping,key):
 if key not in mapping or mapping[key] is None:raise ValueError('Required measured input unavailable: '+key)
 return mapping[key]

class Projection:
 def __init__(self,ego_id,required,context):
  self.ego_id=ego_id;self.required=required;self.context=context;self.previous={};self.stop_events={};self.first_entries={};self.was_in={};self.last=None;self.start_positions={};self.braking={};self.rows=[]
 def __call__(self,row,event):
  original=require(event,'original_observations');participants=require(original,'participants');ego=next(p for p in participants if p['actor_id']==self.ego_id)
  devices=require(original,'devices');signals=[d for d in devices if d['blueprint'].startswith('traffic.traffic_light')]
  context=self.context;polygon=context.get('intersection_polygon',[]);hist=[]
  for p in participants:
   ident=p['actor_id'];vertices=require(p,'body_vertices_m');within=bool(polygon and intersects(vertices,polygon));prior=self.was_in.get(ident,False)
   if within and not prior and ident not in self.first_entries:self.first_entries[ident]={'frame':row['frame'],'time_s':row['time_s'],'previous_time_s':self.previous.get(ident,{}).get('time_s'),'footprint_vertices_m':vertices}
   self.was_in[ident]=within
   if p['speed_mps']<=.05 and self.previous.get(ident,{}).get('speed_mps',0)>.05 and ident not in self.stop_events:self.stop_events[ident]={'frame':row['frame'],'time_s':row['time_s'],'previous_time_s':self.previous.get(ident,{}).get('time_s'),'speed_mps':p['speed_mps'],'engineering_cessation_convention_mps':.05,'position_m':p['position_m'],'body_vertices_m':vertices}
   if p['accel_longitudinal_mps2']<0 and ident not in self.braking:self.braking[ident]={'time_s':row['time_s'],'position_m':p['position_m']}
   previous=self.previous.get(ident);self.previous[ident]={'time_s':row['time_s'],'position_m':p['position_m'],'speed_mps':p['speed_mps']}
   hist.append(dict(p,in_intersection=within,first_entry=self.first_entries.get(ident),first_engineering_cessation=self.stop_events.get(ident)))
  leader=next((p for p in participants if p['actor_id']==context.get('leader_id')),None)
  separation=gap(ego,leader) if leader else None
  occupancy={'native_projection':require(event['world'],'road_projection'),'body_vertices_m':ego['body_vertices_m'],'authored_driving_polygons':context['driving_polygons'],'whole_body_contained':all(any(inside(v,p) for p in context['driving_polygons']) for v in ego['body_vertices_m'])}
  known={
   'kin.speed':row['speed_mps'],'ego_speed':row['speed_mps'],'kin.velocity':ego['velocity_mps'],'kin.position':ego['position_m'],'kin.time':row['time_s'],'ru.subject':ego,
   'rel.surface_gap':separation,'drv.time_gap':{'gap_m':separation,'ego_speed_mps':row['speed_mps'],'seconds':separation/row['speed_mps'] if separation is not None and row['speed_mps']>0 else 'undefined_at_zero_speed'},
   'drv.following':{'subject_id':ego['actor_id'],'leader_id':context.get('leader_id'),'longitudinal_surface_gap_m':separation,'native_lane_relations':context.get('participant_lanes',{}),'definition':'measured same-lane positions and signed body separation; no headway standard'},
   'rel.ahead_behind_in_lane':{'subject_lane':occupancy['native_projection'],'participant_lane_positions':context.get('participant_lanes',{}),'surface_gap_m':separation},
   'env.wet_road':{'wetness':require(event['world']['weather'],'wetness'),'precipitation_deposits':require(event['world']['weather'],'precipitation_deposits'),'method':'actual CARLA weather readback; no wetness classification cutoff'},
   'env.ice_or_snow':{'authored_surface':context['surface'],'actual_weather':event['world']['weather'],'snow_or_ice':'not installed in this authored scene','provenance':'authored surface setup plus retained road and prop inventory'},
   'drv.queue_behind':{'participants':hist,'surface_gap_to_leader_m':separation},
   'drv.hard_deceleration':{'participants':[{'actor_id':p['actor_id'],'accel_longitudinal_mps2':p['accel_longitudinal_mps2']} for p in participants],'criterion':'raw measured acceleration, qualitative hard remains unresolved'},
   'dev.traffic_signal':signals,'dev.inoperative':{'signal_heads':signals,'all_indications_off':bool(signals) and all(s.get('state')=='Off' for s in signals),'uncovered_and_installed_proof':context.get('signal_proof',{})},
   'dev.governs':context.get('device_governance'),'st.lane_enters':context.get('incoming_topology'),'st.intersection':context.get('intersection_polygon'),
   'st.stop_line':context.get('stop_line'),'st.crosswalk':context.get('crosswalks'),
   'st.sight_distance':event.get('visibility'),'rel.visible':original.get('relations'),
   'drv.stopped':{'speed_mps':row['speed_mps'],'observed_cessation_events':self.stop_events,'engineering_cessation_convention_mps':.05,'position_m':ego['position_m']},
   'drv.entering_intersection':{'current_footprint_occupancy':self.was_in.get(self.ego_id,False),'entry_event':self.first_entries.get(self.ego_id,{'status':'not_entered_in_observed_history'}),'intersection_polygon':polygon},
   'drv.arrival_order':{'cessation_histories':self.stop_events,'current_participants':hist,'criterion':'original-time cessation brackets, no inferred courtesy or priority'},
   'drv.in_intersection':{'intersection_polygon':polygon,'participants':hist},
   'drv.yields_to':{'participants':hist,'entry_histories':self.first_entries,'cessation_histories':self.stop_events,'ego_measured_acceleration_mps2':ego['accel_longitudinal_mps2'],'criterion':'observed trajectories, occupancy and action history; priority interpretation downstream'},
   'drv.crossing_line':{'ego_vertices_m':ego['body_vertices_m'],'stop_line':context.get('stop_line'),'intersection_entry_history':self.first_entries.get(self.ego_id,{})},
   'drv.stopping_distance':{'braking_onset':self.braking.get(self.ego_id,{'status':'not_yet_observed'}),'cessation':self.stop_events.get(self.ego_id,{'status':'not_yet_observed'}),'current_position_m':ego['position_m'],'method':'retained native braking/cessation positions and original-time brackets'},
   'dev.speed_limit_sign':context.get('speed_sign'),'dev.position':context.get('speed_sign',{}).get('position_m'),
   'drv.within_signed_zone':{'ego_vertices_m':ego['body_vertices_m'],'governed_polygon':context.get('governed_polygon'),'footprint_intersects':intersects(ego['body_vertices_m'],context['governed_polygon']) if context.get('governed_polygon') else False},
   'rel.occupies':occupancy,
  }
  values={name:require(known,name) for name in self.required}
  if any(name in self.required for name in ('rel.surface_gap','drv.time_gap','drv.following')) and leader is None:raise ValueError('Required physical leader missing from original capture')
  if 'st.sight_distance' in self.required:
   visibility=require(event,'visibility')
   if not visibility:raise ValueError('Mandatory nine-point sight horizon unavailable')
   validate_visibility(visibility)
  self.last={'time_s':row['time_s'],'participants':hist,'ego_vertices':ego['body_vertices_m'],'values':values,'occupancy':occupancy,'entries':dict(self.first_entries),'stops':dict(self.stop_events)};self.rows.append(self.last)
  return values
