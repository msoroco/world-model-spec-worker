"""Source-joined travel direction on a signposted multilane one-way highway."""
import hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
REQUIRED=('road_context.json','travel_history.jsonl','video_frames.jsonl')
def _finite(x,label):
 if isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x):raise ValueError('Missing finite '+label)
 return float(x)
def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def analyze(root:Path)->dict:
 root=Path(root);hashes={}
 for name in REQUIRED:
  p=root/name
  if not p.is_file():raise ValueError('Missing original source: '+name)
  hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 ctx=json.loads((root/'road_context.json').read_text())
 for key in ('native_map_id','highway_id','road_id','one_way_designation_source','direction_sign_source','lane_geometry_source','travel_route_source'):
  if not ctx.get(key):raise ValueError('Missing road context: '+key)
 lanes=ctx.get('driving_lane_ids')
 if not isinstance(lanes,list) or len(set(lanes))<2:raise ValueError('Multilane highway not sourced')
 direction=ctx.get('designated_forward_xy')
 if not isinstance(direction,list) or len(direction)!=2:raise ValueError('Designated direction missing')
 dx,dy=(_finite(v,'designated direction') for v in direction);norm=math.hypot(dx,dy)
 if norm==0:raise ValueError('Zero designated direction')
 dx,dy=dx/norm,dy/norm
 polygon=Polygon(ctx.get('one_way_roadway_polygon_xy_m',[]))
 if not polygon.is_valid or polygon.area<=0:raise ValueError('Invalid one-way roadway')
 rows,frames=_rows(root/'travel_history.jsonl'),_rows(root/'video_frames.jsonl')
 if len(rows)<2 or len(rows)!=len(frames):raise ValueError('Incomplete travel history')
 prev=(-1,-math.inf);samples=[];centers=[]
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,time=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or time<=prev[1]:raise ValueError('Nonmonotone original history')
  prev=fid,time
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=time:raise ValueError('Original frame join failed')
  if row.get('road_id')!=ctx['road_id'] or row.get('lane_id') not in lanes:raise ValueError('Ego outside sourced one-way lanes')
  vertices=row.get('ego_body_vertices_xy_m')
  if not isinstance(vertices,list) or len(vertices)<4:raise ValueError('Missing complete body')
  body=MultiPoint([(_finite(p[0],'body x'),_finite(p[1],'body y')) for p in vertices]).convex_hull
  if body.area<=0:raise ValueError('Degenerate body')
  forward=row.get('ego_forward_xy')
  if not isinstance(forward,list) or len(forward)!=2:raise ValueError('Ego heading missing')
  fx,fy=(_finite(v,'ego heading') for v in forward);fn=math.hypot(fx,fy)
  if fn==0:raise ValueError('Zero ego heading')
  samples.append({'frame':fid,'time_s':time,'lane_id':row['lane_id'],'complete_body_on_one_way_roadway':polygon.covers(body),'heading_alignment':(fx*dx+fy*dy)/fn})
  centers.append((body.centroid.x,body.centroid.y))
 projected=[(centers[i+1][0]-centers[i][0])*dx+(centers[i+1][1]-centers[i][1])*dy for i in range(len(centers)-1)]
 return {'format':'worker-one-way-direction-observations','sources':hashes,'samples':samples,'projected_step_m':projected,'all_steps_designated_direction':all(v>0 for v in projected),'legal_conclusion':'unresolved pending sign/designation source and physical review'}
