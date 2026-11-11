"""Original-frame complete-body backing onto and over a sourced crosswalk."""
import hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
REQUIRED=('crosswalk_context.json','reverse_history.jsonl','video_frames.jsonl')
def _finite(x,label):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('Missing finite '+label)
 return float(x)
def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def analyze(root:Path)->dict:
 root=Path(root);hashes={}
 for name in REQUIRED:
  p=root/name
  if not p.is_file():raise ValueError('Missing original source: '+name)
  hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 ctx=json.loads((root/'crosswalk_context.json').read_text())
 for key in ('native_map_id','road_id','crosswalk_id','crosswalk_geometry_source','crosswalk_camera_source','reverse_route_source','residence_district_source'):
  if not ctx.get(key):raise ValueError('Missing sourced crosswalk context: '+key)
 crosswalk=Polygon(ctx.get('crosswalk_polygon_xy_m',[]))
 if not crosswalk.is_valid or crosswalk.area<=0:raise ValueError('Invalid crosswalk polygon')
 rows,frames=_rows(root/'reverse_history.jsonl'),_rows(root/'video_frames.jsonl')
 if len(rows)<3 or len(rows)!=len(frames):raise ValueError('Incomplete reverse history')
 prev=(-1,-math.inf);samples=[]
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,t=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or t<=prev[1]:raise ValueError('Nonmonotone original history')
  prev=fid,t
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:raise ValueError('Original frame join failed')
  if row.get('road_id')!=ctx['road_id'] or row.get('crosswalk_id')!=ctx['crosswalk_id']:raise ValueError('Crosswalk/road identity mismatch')
  if type(row.get('native_reverse')) is not bool:raise ValueError('Missing Native reverse state')
  vertices=row.get('ego_body_vertices_xy_m')
  if not isinstance(vertices,list) or len(vertices)<4:raise ValueError('Missing complete ego body')
  body=MultiPoint([(_finite(v[0],'body x'),_finite(v[1],'body y')) for v in vertices]).convex_hull
  if body.area<=0:raise ValueError('Degenerate body')
  samples.append({'frame':fid,'time_s':t,'native_reverse':row['native_reverse'],'body_on_or_over_crosswalk':body.intersects(crosswalk),'body_fully_over_crosswalk':crosswalk.covers(body),'body_crosswalk_overlap_area_m2':body.intersection(crosswalk).area,'body_center_xy_m':[body.centroid.x,body.centroid.y]})
 if samples[0]['body_on_or_over_crosswalk']:raise ValueError('Missing before-crosswalk approach')
 backing=[s for s in samples if s['native_reverse']]
 if not backing:raise ValueError('No observed reverse state')
 return {'format':'worker-reverse-crosswalk-observations','sources':hashes,'samples':samples,'reverse_body_on_or_over_crosswalk':any(s['body_on_or_over_crosswalk'] for s in backing),'reverse_body_fully_over_crosswalk':any(s['body_fully_over_crosswalk'] for s in backing),'legal_conclusion':'unresolved pending physical source review'}
