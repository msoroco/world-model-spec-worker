"""Original-frame caravan gap and entering-vehicle occupancy observations."""
import hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon,Point
REQUIRED=('road_context.json','caravan_history.jsonl','video_frames.jsonl')
def _finite(x,label):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('Missing finite '+label)
 return float(x)
def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
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
 for key in ('native_map_id','highway_id','road_id','business_district_source','caravan_membership_source','route_source','lane_source'):
  if not ctx.get(key):raise ValueError('Missing sourced caravan context: '+key)
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
 prev=(-1,-math.inf);samples=[]
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,t=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or t<=prev[1]:raise ValueError('Nonmonotone original history')
  prev=fid,t
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:raise ValueError('Original frame join failed')
  if row.get('road_id')!=ctx.get('road_id'):raise ValueError('Wrong caravan road')
  members=row.get('caravan_members')
  if not isinstance(members,list) or len(members)<3 or len({m.get('actor_id') for m in members})!=len(members):raise ValueError('Three distinct caravan vehicles required')
  bodies=[_body(m) for m in members];other=_body(row.get('entering_vehicle'))
  if not all(road.covers(b) for b in bodies+[other]):raise ValueError('Vehicle outside sourced highway')
  ordered=sorted(zip(members,bodies),key=lambda mb:mb[1].centroid.x*fx+mb[1].centroid.y*fy)
  gaps=[]
  for (rear,rb),(front,fb) in zip(ordered,ordered[1:]):
   along=(fb.centroid.x-rb.centroid.x)*fx+(fb.centroid.y-rb.centroid.y)*fy
   clearance=rb.distance(fb)
   midpoint=((fb.centroid.x+rb.centroid.x)/2,(fb.centroid.y+rb.centroid.y)/2)
   gaps.append({'rear_actor_id':rear['actor_id'],'front_actor_id':front['actor_id'],'along_center_distance_m':along,'body_clearance_m':clearance,'gap_midpoint_distance_to_entering_body_m':other.distance(Point(midpoint))})
  samples.append({'frame':fid,'time_s':t,'gaps':gaps,'entering_vehicle_body_area_m2':other.area})
 return {'format':'worker-caravan-spacing-observations','sources':hashes,'samples':samples,'sufficient_space_without_danger_judgment':'unresolved; no statutory numeric gap','legal_conclusion':'unresolved'}
