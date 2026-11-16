"""Original-frame complete-body backing onto and over a sourced crosswalk."""
import hashlib,importlib.util,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
REQUIRED=('crosswalk_context.json','site_packet.json','reverse_history.jsonl','video_frames.jsonl')
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
 packet=json.loads((root/'site_packet.json').read_text())
 spec=importlib.util.spec_from_file_location('reverse_saved_site_review',Path(__file__).with_name('site_review.py'))
 site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)
 review=site.validate(packet,root,native_map_id=ctx['native_map_id'],
                      road_id=ctx['road_id'],crosswalk_id=ctx['crosswalk_id'])
 if packet['crosswalk_polygon_xy_m']!=ctx['crosswalk_polygon_xy_m']:
  raise ValueError('Saved site packet crosswalk geometry differs')
 rows,frames=_rows(root/'reverse_history.jsonl'),_rows(root/'video_frames.jsonl')
 if len(rows)<3 or len(rows)!=len(frames):raise ValueError('Incomplete reverse history')
 prev=(-1,-math.inf);samples=[];prior_center=None;prior_reverse=None
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,t=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or t<=prev[1]:raise ValueError('Nonmonotone original history')
  prev=fid,t
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:raise ValueError('Original frame join failed')
  if row.get('road_id')!=ctx['road_id'] or row.get('crosswalk_id')!=ctx['crosswalk_id']:raise ValueError('Crosswalk/road identity mismatch')
  if type(row.get('native_reverse')) is not bool:raise ValueError('Missing Native reverse state')
  forward=row.get('ego_forward_xy')
  if not isinstance(forward,list) or len(forward)!=2:raise ValueError('Missing original ego heading')
  fx,fy=(_finite(v,'ego heading') for v in forward)
  norm=math.hypot(fx,fy)
  if norm<0.1:raise ValueError('Zero original ego heading')
  fx,fy=fx/norm,fy/norm
  vertices=row.get('ego_body_vertices_xy_m')
  if not isinstance(vertices,list) or len(vertices)<4:raise ValueError('Missing complete ego body')
  body=MultiPoint([(_finite(v[0],'body x'),_finite(v[1],'body y')) for v in vertices]).convex_hull
  if body.area<=0:raise ValueError('Degenerate body')
  center=(body.centroid.x,body.centroid.y)
  projected_step=None if prior_center is None else (center[0]-prior_center[0])*fx+(center[1]-prior_center[1])*fy
  prior_center=center
  # Projection sign is a motion observation, not a legal distance threshold.
  backward=bool(prior_reverse is True and row['native_reverse'] and projected_step is not None and projected_step<0)
  prior_reverse=row['native_reverse']
  samples.append({'frame':fid,'time_s':t,'native_reverse':row['native_reverse'],
                  'projected_step_along_heading_m':projected_step,
                  'observed_backward_motion':backward,
                  'body_on_or_over_crosswalk':body.intersects(crosswalk),
                  'body_fully_over_crosswalk':crosswalk.covers(body),
                  'body_crosswalk_overlap_area_m2':body.intersection(crosswalk).area,
                  'body_center_xy_m':[center[0],center[1]]})
 if samples[0]['body_on_or_over_crosswalk']:raise ValueError('Missing before-crosswalk approach')
 backing=[s for s in samples if s['observed_backward_motion']]
 if not any(s['native_reverse'] for s in samples):raise ValueError('No observed reverse state')
 for bound in review['sources'].values():hashes[bound['path']]=bound['sha256']
 return {'format':'worker-reverse-crosswalk-observations','sources':hashes,
         'site_source_review':review,'samples':samples,
         'backward_motion_observed':bool(backing),
         'reverse_body_on_or_over_crosswalk':any(s['body_on_or_over_crosswalk'] for s in backing),
         'reverse_body_fully_over_crosswalk':any(s['body_fully_over_crosswalk'] for s in backing),
         'legal_conclusion':'unresolved pending physical source review'}
