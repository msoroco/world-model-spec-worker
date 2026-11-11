"""Original-frame all-head Off, stop-reference and post-stop priority observations."""
import hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
REQUIRED=('junction_context.json','entry_history.jsonl','video_frames.jsonl')
def _finite(x,label):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('Missing finite '+label)
 return float(x)
def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def _body(vertices):
 if not isinstance(vertices,list) or len(vertices)<4:raise ValueError('Missing complete body')
 poly=MultiPoint([(_finite(p[0],'body x'),_finite(p[1],'body y')) for p in vertices]).convex_hull
 if poly.area<=0:raise ValueError('Degenerate body')
 return poly
def analyze(root:Path)->dict:
 root=Path(root);hashes={}
 for name in REQUIRED:
  p=root/name
  if not p.is_file():raise ValueError('Missing original source: '+name)
  hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 ctx=json.loads((root/'junction_context.json').read_text())
 for key in ('native_map_id','intersection_id','all_entrance_signal_source','installed_uncovered_source','stop_reference_source','junction_source','other_vehicle_source'):
  if not ctx.get(key):raise ValueError('Missing sourced junction context: '+key)
 if ctx.get('installed_uncovered') is not True:raise ValueError('Installed uncovered signal status unresolved')
 heads=ctx.get('entrance_signal_ids')
 if not isinstance(heads,list) or len(heads)<2 or len(set(heads))!=len(heads):raise ValueError('All-entrance signal inventory missing')
 reference=ctx.get('stop_reference_kind')
 if reference not in ('marked_stop_line','near_crosswalk','nearest_view'):raise ValueError('Stop-reference hierarchy missing')
 if reference!='marked_stop_line' and ctx.get('marked_stop_line_present') is not False:raise ValueError('Marked-line priority unresolved')
 if reference=='nearest_view' and ctx.get('near_crosswalk_present') is not False:raise ValueError('Near-crosswalk priority unresolved')
 polygon=Polygon(ctx.get('intersection_polygon_xy_m',[]))
 if not polygon.is_valid or polygon.area<=0:raise ValueError('Invalid intersection polygon')
 rows,frames=_rows(root/'entry_history.jsonl'),_rows(root/'video_frames.jsonl')
 if len(rows)<3 or len(rows)!=len(frames):raise ValueError('Incomplete entry history')
 prev=(-1,-math.inf);samples=[];entry=None
 for i,(row,frame) in enumerate(zip(rows,frames)):
  fid,t=row.get('frame'),_finite(row.get('time_s'),'time')
  if type(fid) is not int or fid<=prev[0] or t<=prev[1]:raise ValueError('Nonmonotone original history')
  prev=fid,t
  if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:raise ValueError('Original frame join failed')
  states=row.get('entrance_signal_states')
  if not isinstance(states,dict) or set(states)!={str(h) for h in heads} or any(v!='Off' for v in states.values()):raise ValueError('All entrance signals not observed Off')
  ego=_body(row.get('ego_body_vertices_xy_m'));other=_body(row.get('other_body_vertices_xy_m'))
  speed=_finite(row.get('ego_speed_mps'),'ego speed')
  if speed<0:raise ValueError('Negative speed')
  before=row.get('ego_complete_body_before_stop_reference')
  if type(before) is not bool:raise ValueError('Missing complete-body reference position')
  other_stopped=row.get('other_completed_stop')
  if type(other_stopped) is not bool:raise ValueError('Missing other prior-stop history')
  inside=ego.intersects(polygon)
  if i==0 and inside:raise ValueError('Missing pre-entry history')
  if inside and entry is None:entry={'frame':fid,'time_s':t,'other_inside':other.intersects(polygon),'other_completed_stop':other_stopped}
  samples.append({'frame':fid,'time_s':t,'ego_speed_mps':speed,'ego_body_before_reference':before,'ego_inside':inside,'other_inside':other.intersects(polygon),'other_completed_stop':other_stopped})
 if entry is None:raise ValueError('No observed ego entry')
 stopped=any(s['ego_speed_mps']<=0.05 and s['ego_body_before_reference'] for s in samples if s['time_s']<entry['time_s'])
 return {'format':'worker-inoperative-signal-stop-priority','sources':hashes,'stop_reference_kind':reference,'first_ego_entry':entry,'observed_pre_entry_stop':stopped,'other_priority_at_entry':entry['other_inside'] or entry['other_completed_stop'],'samples':samples,'cautious_yield_judgment':'unresolved','legal_conclusion':'unresolved'}
