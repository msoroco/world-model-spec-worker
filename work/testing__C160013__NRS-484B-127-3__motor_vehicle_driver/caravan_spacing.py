"""Original-frame caravan gap and entering-vehicle occupancy observations."""
import hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon,Point
REQUIRED=('road_context.json','caravan_history.jsonl','video_frames.jsonl')
def _finite(x,label):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('Missing finite '+label)
 return float(x)
def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def _source(root,ref,key):
 if not isinstance(ref,dict) or not isinstance(ref.get('path'),str) or not isinstance(ref.get('sha256'),str):raise ValueError('Missing original context source: '+key)
 rel=Path(ref['path'])
 if rel.is_absolute() or not rel.parts or '..' in rel.parts or ref['path'] in ('','.'):raise ValueError('Unsafe context source: '+key)
 path=root/rel
 if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Missing or escaping context source: '+key)
 if path.stat().st_size==0 or path.stat().st_size>2*1024*1024:raise ValueError('Empty or oversized context source: '+key)
 path.read_text(encoding='utf-8')
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=ref['sha256']:raise ValueError('Changed original context source: '+key)
 return digest
def _body(actor):
 if not isinstance(actor,dict) or not isinstance(actor.get('body_vertices_xy_m'),list) or len(actor['body_vertices_xy_m'])<4:raise ValueError('Missing complete body')
 poly=MultiPoint([(_finite(p[0],'body x'),_finite(p[1],'body y')) for p in actor['body_vertices_xy_m']]).convex_hull
 if poly.area<=0:raise ValueError('Degenerate body')
 return poly
def analyze(root:Path)->dict:
 root=Path(root);hashes={}
 for name in REQUIRED:
  p=root/name
  if not p.is_file():raise ValueError('Missing original source: '+name)
  hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 ctx=json.loads((root/'road_context.json').read_text())
 for key in ('native_map_id','highway_id','road_id'):
  if not ctx.get(key):raise ValueError('Missing sourced caravan context: '+key)
 context_hashes={key:_source(root,ctx.get(key),key) for key in ('business_district_source','caravan_membership_source','route_source','lane_source')}
 if ctx.get('outside_business_district') is not True or ctx.get('caravan_or_motorcade') is not True:raise ValueError('Caravan/district activation unresolved')
 road=Polygon(ctx.get('roadway_polygon_xy_m',[]))
 if not road.is_valid or road.area<=0:raise ValueError('Invalid roadway')
 forward=ctx.get('road_forward_xy')
 if not isinstance(forward,list) or len(forward)!=2:raise ValueError('Road direction missing')
 fx,fy=(_finite(v,'road direction') for v in forward);norm=math.hypot(fx,fy)
 if norm==0:raise ValueError('Zero road direction')
 fx,fy=fx/norm,fy/norm
 rows,frames=_rows(root/'caravan_history.jsonl'),_rows(root/'video_frames.jsonl')
 if len(rows)<2 or len(rows)!=len(frames):raise ValueError('Incomplete caravan history')
 prev=(-1,-math.inf);samples=[];member_centers={};member_ids=None;entrant_id=None;forward_motion={};member_types=None;entrant_type=None
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,t=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or t<=prev[1]:raise ValueError('Nonmonotone original history')
  if i and (fid!=prev[0]+1 or abs(t-prev[1]-.05)>1e-4):raise ValueError('Original 20 Hz frame cadence required')
  prev=fid,t
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:raise ValueError('Original frame join failed')
  if row.get('road_id')!=ctx.get('road_id'):raise ValueError('Wrong caravan road')
  members=row.get('caravan_members')
  if not isinstance(members,list) or len(members)<3 or len({m.get('actor_id') for m in members})!=len(members):raise ValueError('Three distinct caravan vehicles required')
  ids={m.get('actor_id') for m in members}
  if any(type(actor_id) is not int for actor_id in ids):raise ValueError('Original caravan actor IDs required')
  if member_ids is None:member_ids=ids
  elif ids!=member_ids:raise ValueError('Caravan membership changed across original frames')
  types={m['actor_id']:m.get('blueprint_id') for m in members}
  if any(not isinstance(kind,str) or not kind for kind in types.values()):raise ValueError('Original caravan vehicle types required')
  if member_types is None:member_types=types
  elif types!=member_types:raise ValueError('Caravan vehicle types changed across original frames')
  entrant=row.get('entering_vehicle')
  if not isinstance(entrant,dict) or type(entrant.get('actor_id')) is not int or entrant['actor_id'] in {m.get('actor_id') for m in members}:
   raise ValueError('Distinct entering vehicle required')
  if entrant_id is None:entrant_id=entrant['actor_id']
  elif entrant['actor_id']!=entrant_id:raise ValueError('Entering vehicle identity changed across original frames')
  if not isinstance(entrant.get('blueprint_id'),str) or not entrant['blueprint_id']:raise ValueError('Original entering vehicle type required')
  if entrant_type is None:entrant_type=entrant['blueprint_id']
  elif entrant_type!=entrant['blueprint_id']:raise ValueError('Entering vehicle type changed across original frames')
  bodies=[_body(m) for m in members];other=_body(entrant)
  if not all(road.covers(b) for b in bodies+[other]):raise ValueError('Vehicle outside sourced highway')
  ordered=sorted(zip(members,bodies),key=lambda mb:mb[1].centroid.x*fx+mb[1].centroid.y*fy)
  for member,body in ordered:
   current=body.centroid.x*fx+body.centroid.y*fy
   previous=member_centers.get(member['actor_id'])
   if previous is not None:
    if current<previous-1e-4:raise ValueError('Caravan member reversed against highway direction')
    forward_motion[member['actor_id']]=forward_motion.get(member['actor_id'],False) or current>previous+1e-4
   member_centers[member['actor_id']]=current
  gaps=[]
  def extent(poly):
   values=[x*fx+y*fy for x,y in poly.exterior.coords]
   return min(values),max(values)
  entrant_min,entrant_max=extent(other)
  lateral=(-fy,fx)
  entrant_side_min,entrant_side_max=(min(x*lateral[0]+y*lateral[1] for x,y in other.exterior.coords),max(x*lateral[0]+y*lateral[1] for x,y in other.exterior.coords))
  for (rear,rb),(front,fb) in zip(ordered,ordered[1:]):
   along=(fb.centroid.x-rb.centroid.x)*fx+(fb.centroid.y-rb.centroid.y)*fy
   clearance=rb.distance(fb)
   rear_edge=extent(rb)[1];front_edge=extent(fb)[0]
   rear_side=(min(x*lateral[0]+y*lateral[1] for x,y in rb.exterior.coords),max(x*lateral[0]+y*lateral[1] for x,y in rb.exterior.coords))
   front_side=(min(x*lateral[0]+y*lateral[1] for x,y in fb.exterior.coords),max(x*lateral[0]+y*lateral[1] for x,y in fb.exterior.coords))
   in_lane=entrant_side_min>=max(rear_side[0],front_side[0])-1e-4 and entrant_side_max<=min(rear_side[1],front_side[1])+1e-4
   occupied=(front_edge>rear_edge and entrant_min>=rear_edge and entrant_max<=front_edge and in_lane and
             not rb.intersects(other) and not fb.intersects(other))
   midpoint=((fb.centroid.x+rb.centroid.x)/2,(fb.centroid.y+rb.centroid.y)/2)
   gaps.append({'rear_actor_id':rear['actor_id'],'front_actor_id':front['actor_id'],'along_center_distance_m':along,'body_clearance_m':clearance,'longitudinal_opening_m':max(0.0,front_edge-rear_edge),'gap_midpoint_distance_to_entering_body_m':other.distance(Point(midpoint)),'entering_body_in_caravan_lane':in_lane,'entering_body_wholly_between_member_bodies':occupied,'entering_body_touches_member':rb.intersects(other) or fb.intersects(other)})
  samples.append({'frame':fid,'time_s':t,'gaps':gaps,'entering_vehicle_body_area_m2':other.area})
 occupied_pairs={(g['rear_actor_id'],g['front_actor_id']) for sample in samples for g in sample['gaps'] if g['entering_body_wholly_between_member_bodies']}
 transitions=[]
 for pair in sorted(occupied_pairs):
  states=[next((g['entering_body_wholly_between_member_bodies'] for g in sample['gaps'] if (g['rear_actor_id'],g['front_actor_id'])==pair),False) for sample in samples]
  transitions.append({'rear_actor_id':pair[0],'front_actor_id':pair[1],'occupied_on_original_frame':True,'observed_entry_transition':any(not a and b for a,b in zip(states,states[1:]))})
 return {'format':'worker-caravan-spacing-observations','sources':hashes,'context_source_hashes':context_hashes,'samples':samples,'gap_occupancy':transitions,'caravan_forward_motion_observed':all(forward_motion.get(actor_id,False) for actor_id in member_ids),'member_blueprint_ids':sorted(member_types.values()),'entrant_blueprint_id':entrant_type,'sufficient_space_without_danger_judgment':'unresolved; no statutory numeric gap','legal_conclusion':'unresolved'}
