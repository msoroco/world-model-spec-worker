"""Canonical native output writers. Never repair or rewrite original evidence."""
import json, math
from pathlib import Path
from .common import write

REQUIRED=('measured_values','target_checks','setup_confirmed','behavior_attempted','maneuver_completed','termination_reason','physical_failure_flags','trace_reference','video_references','video_frame_map_reference','recording_description','recording_evidence','realized_observables')

def frame_record(index, frame, time_s, **extra):
    if type(index) is not int or index<0 or type(frame) is not int or isinstance(time_s,bool) or not isinstance(time_s,(int,float)) or not math.isfinite(time_s):raise ValueError('Invalid original frame')
    if set(extra)&{'video_frame','carla_frame','native_frame','time_s'}:raise ValueError('Cannot override original identity')
    return dict(extra,video_frame=index,carla_frame=frame,native_frame=frame,time_s=time_s)

def validate_result(result):
    if not isinstance(result,dict):raise ValueError('Native result must be an object')
    if any(k not in result for k in REQUIRED):raise ValueError('Missing native result field')
    if any(k in result for k in ('legal_verdict','compliant','violating')):raise ValueError('Prohibited legal verdict')
    if not result['target_checks'] or not result['video_references']:raise ValueError('Missing targets or footage')
    for check in result['target_checks']:
        if any(k not in check for k in ('target','requested','measured','method','tolerance','matched','physical_cause_confirmed','cause_evidence')):raise ValueError('Incomplete measured target')
    json.dumps(result,allow_nan=False)
    for key in ('setup_confirmed','behavior_attempted','maneuver_completed'):
        if type(result[key]) is not bool:raise ValueError('Explicit physical status required: '+key)
    return result

def write_result(attempt,result):
    path=Path(attempt)/'result.json'
    if path.exists():raise ValueError('Retain prior result; choose a fresh attempt')
    validate_result(result)
    with path.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return path

class FrameMap:
    """Append original identities once, at capture time, in acquisition order."""
    def __init__(self,path):
        self.stream=Path(path).open('x',buffering=1);self.index=0;self.previous=None
    def append(self,frame,time_s,**extra):
        row=frame_record(self.index,frame,time_s,**extra)
        if self.previous and (frame<=self.previous[0] or time_s<=self.previous[1]):raise ValueError('Original frames/times must increase')
        self.stream.write(json.dumps(row,allow_nan=False)+'\n');self.previous=(frame,time_s);self.index+=1
        return row
    def close(self):self.stream.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

"""Source-bound physical event assessment for migration002, CPU only.

Criteria are explicit engineering completion checks, never legal definitions.
Fixture generation is separate: no assessment branch inspects a fixture label.
"""
import copy, hashlib, json, math
from pathlib import Path

def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _read(path): return json.loads(Path(path).read_text())
def _rows(path):
 p=Path(path)
 return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.suffix=='.jsonl' else _read(p)
def _get(obj,path,default=None):
 try:
  for key in path.split('.'):
   obj=obj[int(key)] if isinstance(obj,list) else obj[key]
  return obj
 except (KeyError,TypeError,IndexError,ValueError):return default

def default_descriptor(cfg):
 law=cfg['law_id'];d={'format':'worker-physical-completion-criteria-v002','criterion':'travel_progress','motion_source':'trace.jsonl','position_key':'position_m','minimum_progress_m':.25,'minimum_samples':2,'engineering_tolerances_not_legal':True,'context_sources':[]}
 if law in ('NRS-484B-400-2a','NRS-484B-400-2b'):
  d.update(criterion='intersection_clearance',motion_source='body_history.jsonl',body_key='body_vertices_m',context_sources=['road_geometry.json'],exit_axis=1,exit_sign=-1)
 elif law=='NRS-484B-253':
  d.update(criterion='intersection_clearance',motion_source='interaction_history.jsonl',body_key='subject_body_vertices_m',context_sources=['road_geometry.json'],exit_axis=1,exit_sign=-1)
 elif law in ('NRS-484B-250-1','NRS-484B-250-2'):
  d.update(criterion='intersection_clearance',motion_source='crossing_history.jsonl',body_key='ego_vertices_m',exit_axis=0,exit_sign=1)
 elif law=='NRS-484B-227-1':
  d.update(criterion='turn',motion_source='body_history.jsonl',body_key='body_vertices_m',context_sources=[],turn_degrees=90 if cfg['cell_id']=='C80909' else 180,turn_tolerance_deg=30)
  if cfg['cell_id']=='C80909':d.update(turn_sign=-1,destination_road=4,road_key='road_id')
 elif law=='NRS-484B-407':
  d.update(criterion='turn',motion_source='turn_history.jsonl',body_key='body_vertices_m',heading_key='heading_deg',cumulative_heading_key='cumulative_heading_change_deg',context_sources=['curve_context.json'],turn_degrees=180,turn_tolerance_deg=30)
 elif law=='NRS-484B-223-1b':
  d.update(criterion='lane_transition',motion_source='lane_history.jsonl',body_key='subject_vertices_m',lane_key='subject_lane_id',destination_lane=-1,context_sources=['scenario_geometry.json'])
 elif law=='NRS-484B-127-1':
  d.update(criterion='lane_transition',motion_source='following_samples.jsonl',body_key='ego_body_vertices_m',lane_key='ego_lane_id',destination_lane=-2,context_sources=['surface_context.json'])
 elif law=='NRS-484B-127-2':
  d.update(criterion='overtake_pass' if cfg.get('overtake') else 'following_progress',motion_source='truck_history.jsonl',body_key='ego_vertices_m',other_body_key='lead_vertices_m',context_sources=['truck_context.json'],lateral_transition_m=1)
 elif law in ('NRS-484B-257-1','NRS-484B-257-2'):
  d.update(criterion='intersection_clearance',motion_source='interaction_history.jsonl',body_key='ego.body_vertices_m',context_sources=['control_context.json'],exit_axis=0,exit_sign=1)
 elif law=='NRS-484B-307-6a':
  d.update(criterion='intersection_clearance',motion_source='signal_history.jsonl',body_key='ego.body_vertices_m',context_sources=['scenario_geometry.json','signal_context.json'],exit_axis=0,exit_sign=1)
 elif law=='NRS-484B-127-3':
  d.update(criterion='caravan_entry',motion_source='caravan_history.jsonl',body_key='participants.subject.body_vertices_m',context_sources=['caravan_context.json'],destination_lane=-1)
 elif law=='NRS-484B-413-2':
  d.update(motion_source='body_history.jsonl',body_key='body_vertices_m',context_sources=[])
  if cfg.get('course')=='change_lane':d.update(criterion='lane_transition',lane_key='lane_id',destination_lane=-2)
  else:d.update(criterion='road_transition',road_key='road_id',destination_road=4 if cfg.get('course')=='left_turn' else 3)
 elif law=='NRS-484B-113-2':
  goals=cfg.get('motion_route_xy_m') or [[cfg.get('reverse_target_x_m',-4),1.75]]
  d.update(criterion='reverse_goal',motion_source='reverse_history.jsonl',body_key='body_vertices_m',heading_key='heading_deg',velocity_key='velocity_mps',context_sources=['crosswalk_context.json'],goal_xy_m=goals[-1],goal_tolerance_m=3)
 elif law=='NRS-484B-250-4':
  d.update(criterion='intersection_clearance',motion_source='interaction_history.jsonl',body_key='states.ego.body_vertices_m',context_sources=['signal_context.json'],exit_axis=0,exit_sign=1)
 elif law=='NRS-484A-450-2':
  d.update(criterion='intersection_clearance',motion_source='stop_history.jsonl',body_key='body_vertices_m',context_sources=['crosswalk_geometry.json'],exit_axis=0,exit_sign=1)
 elif law=='NRS-484B-220-1':d['direction_xy']=[-1,0] if cfg.get('reverse_motion') else [1,0]
 if d['criterion']=='travel_progress':
  d['minimum_progress_m']=max(1.0,float(cfg.get('requested_speed_mps',5))*float(cfg.get('duration_s',45))/2)
  d['completion_goal_method']='Authored finite progress milestone: requested speed times planned duration divided by two; minimum1m. Engineering event criterion, not full recording acceptance or legal threshold.'
 d.update(cfg.get('physical_completion',{}))
 return d

def _finite_number(v):return type(v) in (int,float) and math.isfinite(v)
def _body(row,key):
 v=_get(row,key)
 if not isinstance(v,list) or len(v)<4 or any(not isinstance(p,list) or len(p)<2 or not all(_finite_number(x) for x in p) for p in v):raise ValueError('Missing complete finite body geometry: '+key)
 return v

def _center(body):return [(min(v[i] for v in body)+max(v[i] for v in body))/2 for i in (0,1)]
def _point(row,d):
 if d.get('body_key'):return _center(_body(row,d['body_key']))
 point=_get(row,d.get('position_key','position_m'))
 if not isinstance(point,(list,tuple)) or len(point)<2 or not all(_finite_number(v) for v in point):raise ValueError('Missing finite original position')
 return list(point[:2])
def _overlap(body,polygon):
 # All packaged intersections are axis-aligned. Retain body extents rather than
 # reducing the event to source-presence or speed alone.
 return all(max(v[i] for v in body)>=min(p[i] for p in polygon) and min(v[i] for v in body)<=max(p[i] for p in polygon) for i in (0,1))
def _interval(rows,mapping):
 frames=[r['frame'] for r in rows];times={r['carla_frame']:r['time_s'] for r in mapping}
 return [{'first_frame':frames[0],'last_frame':frames[-1],'first_time_s':times[frames[0]],'last_time_s':times[frames[-1]]}]
def _check(status,method,sources,intervals,details=None,missing=None):
 return {'status':status,'method':method,'intervals':intervals,'sources':dict(sources),'details':details or {},'missing_evidence':missing or [],'legal_verdict_claimed':False,'physical_causation_claimed':False}

def assess_physical(root,cfg,target_checks=None):
 root=Path(root);d=default_descriptor(cfg);sources={};missing=[];errors=[];rows=[];mapping=[];intervals=[];observables={}
 for name in ['config.json','video_frames.jsonl','trace.jsonl',d['motion_source'],*d.get('context_sources',[])]:
  p=root/name
  if p.is_file():sources[name]=_sha(p)
  else:missing.append(name)
 if missing:
  detail={'criterion':d,'reason':'Required original source is missing'}
  return {'physical_checks':{k:_check('unverified','source-bound '+k+' assessment v002',sources,[],detail,sorted(set(missing))) for k in ('setup','target','maneuver')},'realized_observables':{},'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False}
 try:
  mapping=_rows(root/'video_frames.jsonl');rows=_rows(root/d['motion_source'])
  if not isinstance(rows,list) or len(rows)<d.get('minimum_samples',2):raise ValueError('Insufficient original motion samples')
  frame_times={r['carla_frame']:r['time_s'] for r in mapping}
  if len(frame_times)!=len(mapping) or not all(_finite_number(t) for t in frame_times.values()):raise ValueError('Invalid original frame map')
  previous=-1
  for r in rows:
   f=r.get('frame')
   if type(f) is not int or f not in frame_times or f<=previous:raise ValueError('Original motion/frame identity join failed')
   if 'time_s' in r and (not _finite_number(r['time_s']) or abs(r['time_s']-frame_times[f])>1e-4):raise ValueError('Original motion timestamp join failed')
   previous=f
  intervals=_interval(rows,mapping);points=[_point(r,d) for r in rows]
  displacement=math.dist(points[0],points[-1]);path=sum(math.dist(a,b) for a,b in zip(points,points[1:]));minimum=d.get('minimum_progress_m',.25)
  detail={'criterion':d['criterion'],'sample_count':len(rows),'displacement_m':displacement,'sampled_path_m':path,'engineering_minimum_progress_m':minimum,'not_a_legal_threshold':True}
  observables={'original_motion':{'frames':[r['frame'] for r in rows],'times_s':[frame_times[r['frame']] for r in rows],'body_centers_xy_m':points,'sampled_path_m':path,'displacement_m':displacement},'completion_criterion':copy.deepcopy(d)}
  criterion=d['criterion'];met=False
  if criterion=='travel_progress':
   direction=d.get('direction_xy')
   projected=sum((points[-1][i]-points[0][i])*direction[i] for i in (0,1)) if direction else displacement
   detail['projected_progress_m']=projected;met=projected>=minimum
  elif criterion=='intersection_clearance':
   polygon=d.get('intersection_polygon_xy_m')
   if polygon is None:
    for name in d.get('context_sources',[]):
     context=_read(root/name);polygon=context.get('intersection_xy_m') or context.get('intersection_polygon_xy_m') or context.get('intersection_polygon')
     if polygon:break
   polygon=polygon or [[-7,-7],[7,-7],[7,7],[-7,7]]
   bodies=[_body(r,d['body_key']) for r in rows];inside=[_overlap(b,polygon) for b in bodies]
   entry=next((i for i,v in enumerate(inside) if v and (i==0 or not inside[i-1])),None)
   axis=d.get('exit_axis',0);sign=d.get('exit_sign',1);bound=max(p[axis] for p in polygon) if sign>0 else min(p[axis] for p in polygon)
   clear=[(min(v[axis] for v in b)>bound if sign>0 else max(v[axis] for v in b)<bound) for b in bodies]
   departure=next((i for i,v in enumerate(clear) if v and entry is not None and i>entry),None)
   met=entry is not None and departure is not None and clear[-1] and path>=minimum
   detail.update(intersection_polygon_xy_m=polygon,body_overlap_by_frame=inside,entry_frame=None if entry is None else rows[entry]['frame'],clearance_frame=None if departure is None else rows[departure]['frame'],departure_clear_by_frame=clear)
  elif criterion in ('lane_transition','road_transition'):
   key=d.get('lane_key') if criterion=='lane_transition' else d.get('road_key','road_id');values=[_get(r,key) for r in rows]
   if any(type(v) is not int for v in values):raise ValueError('Missing original lane/road readback: '+key)
   destination=d['destination_lane'] if criterion=='lane_transition' else d['destination_road']
   first=next((i for i,v in enumerate(values) if v==destination and i>0),None)
   met=values[0]!=destination and first is not None and values[-1]==destination and path>=minimum
   detail.update(original_values=values,destination=destination,transition_frame=None if first is None else rows[first]['frame'])
  elif criterion=='turn':
   cumulative=d.get('cumulative_heading_key');headings=[_get(r,d.get('heading_key','heading_deg')) for r in rows]
   trace_by_frame={r['frame']:r for r in _rows(root/'trace.jsonl')}
   headings=[v if _finite_number(v) else trace_by_frame.get(r['frame'],{}).get('heading_deg') for r,v in zip(rows,headings)]
   if cumulative and all(_finite_number(_get(r,cumulative)) for r in rows):change=_get(rows[-1],cumulative)-_get(rows[0],cumulative)
   elif all(_finite_number(v) for v in headings):change=sum((b-a+180)%360-180 for a,b in zip(headings,headings[1:]))
   else:raise ValueError('Missing original heading samples')
   requested=d['turn_degrees'];tolerance=d.get('turn_tolerance_deg',30)
   if not all(_finite_number(v) for v in headings):raise ValueError('Missing endpoint heading orientation')
   net=(headings[-1]-headings[0]+180)%360-180
   orientation_ok=abs(abs(net)-requested)<=tolerance
   if d.get('turn_sign') and requested<180:orientation_ok=orientation_ok and net*d['turn_sign']>0
   destination_ok=True
   if d.get('destination_road'):
    road=_get(rows[-1],d.get('road_key','road_id'))
    if type(road) is not int:raise ValueError('Missing destination road readback')
    destination_ok=road==d['destination_road']
   met=abs(change)>=requested-tolerance and orientation_ok and destination_ok and path>=minimum
   detail.update(observed_heading_change_deg=change,net_endpoint_orientation_change_deg=net,authored_turn_degrees=requested,engineering_turn_tolerance_deg=tolerance,destination_road_verified=destination_ok)
   observables['original_motion']['heading_deg']=headings
  elif criterion=='reverse_goal':
   signed=[]
   for r in rows:
    heading=_get(r,d.get('heading_key','heading_deg'));velocity=_get(r,d.get('velocity_key','velocity_mps'))
    if not _finite_number(heading) or not isinstance(velocity,list) or len(velocity)<2:raise ValueError('Missing signed reverse motion evidence')
    signed.append(velocity[0]*math.cos(math.radians(heading))+velocity[1]*math.sin(math.radians(heading)))
   goal=d.get('goal_xy_m')
   if not isinstance(goal,list) or len(goal)!=2:raise ValueError('Missing authored reverse route goal')
   distances=[math.dist(p,goal) for p in points];reverse=any(v<0 for v in signed);reached=min(distances)<=d.get('goal_tolerance_m',3)
   met=reverse and reached and path>=minimum;detail.update(signed_forward_velocity_mps=signed,goal_xy_m=goal,minimum_goal_distance_m=min(distances),engineering_goal_tolerance_m=d.get('goal_tolerance_m',3))
  elif criterion in ('following_progress','overtake_pass'):
   other=[_center(_body(r,d['other_body_key'])) for r in rows];orders=[o[0]-p[0] for p,o in zip(points,other)];other_path=sum(math.dist(a,b) for a,b in zip(other,other[1:]))
   if criterion=='following_progress':met=path>=minimum and other_path>=minimum and all(v>0 for v in orders)
   else:met=orders[0]>0 and orders[-1]<0 and max(p[1] for p in points)-min(p[1] for p in points)>=d.get('lateral_transition_m',1) and path>=minimum
   detail.update(other_centers_xy_m=other,other_minus_subject_x_m=orders,other_sampled_path_m=other_path)
  elif criterion=='caravan_entry':
   lanes=[];inside=[]
   for r in rows:
    roles=r.get('participants',{});entrant=roles.get('entrant',{});rear=roles.get('rear',{});subject=roles.get('subject',{})
    eb=_body(entrant,'body_vertices_m');rb=_body(rear,'body_vertices_m');sb=_body(subject,'body_vertices_m')
    if type(entrant.get('lane_id')) is not int:raise ValueError('Missing entrant lane readback')
    lanes.append(entrant['lane_id']);inside.append(min(v[0] for v in eb)>max(v[0] for v in rb) and max(v[0] for v in eb)<min(v[0] for v in sb))
   destination=d.get('destination_lane',-1);met=lanes[0]!=destination and any(v==destination and b for v,b in zip(lanes,inside)) and lanes[-1]==destination and path>=minimum
   detail.update(entrant_lane_ids=lanes,whole_entrant_between_pair=inside,destination_lane=destination)
  else:raise ValueError('Unsupported authored physical criterion: '+criterion)
  maneuver=_check('met' if met else 'not_met','original sampled '+criterion+' v002',sources,intervals,detail)
  expected_count=round(float(cfg['duration_s'])*float(cfg['rate_hz']));expected_span=max(0,(expected_count-1)/float(cfg['rate_hz']))
  actual_span=mapping[-1]['time_s']-mapping[0]['time_s'];complete_capture=len(mapping)==expected_count and len(rows)==len(mapping) and abs(actual_span-expected_span)<=1e-4
  setup=_check('met' if complete_capture else 'not_met','source identity/timestamp joins plus full planned recording count and duration v002',sources,intervals,{'joined_motion_samples':len(rows),'planned_frame_count':expected_count,'observed_frame_count':len(mapping),'planned_observation_span_s':expected_span,'observed_observation_span_s':actual_span,'legal_scope_not_accepted':True})
  target_status='unverified' if not target_checks else ('met' if all(t.get('matched') is True for t in target_checks) else 'not_met')
  target=_check(target_status,'selected analyzer measured target matching v002; no causation inference',sources,intervals,{'checks':target_checks or []})
 except (OSError,ValueError,TypeError,KeyError,IndexError,ZeroDivisionError) as error:
  errors.append(str(error));detail={'criterion':d,'errors':errors}
  setup=_check('unverified','source identity and timestamp join v002',sources,intervals,detail)
  target=_check('unverified','selected analyzer measured target matching v002',sources,intervals,detail)
  maneuver=_check('unverified','original sampled motion assessment v002',sources,intervals,detail)
 return {'physical_checks':{'setup':setup,'target':target,'maneuver':maneuver},'realized_observables':observables,'setup_confirmed':setup['status']=='met','behavior_attempted':target['status']=='met','maneuver_completed':maneuver['status']=='met'}

"""Saved C109705 physical motion evidence, distinct from legal acceptance.

The predicates describe this authored connected route. They do not define
statutory entry, centerline proximity, safety, or legal compliance.
"""
import hashlib
import json
import math
from pathlib import Path

LT_REQUIRED = ('road_geometry.json', 'body_history.jsonl', 'video_frames.jsonl')

def lt_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def lt_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def assess_left_turn(attempt):
    """Return a source-bound physical maneuver assessment and realized observations."""
    root = Path(attempt)
    paths = {name: root / name for name in LT_REQUIRED}
    sources = {name: lt_sha(path) for name, path in paths.items() if path.is_file()}
    if (root / 'config.json').is_file():
        sources['config.json'] = lt_sha(root / 'config.json')
    method = 'c109705_ordered_approach_connector_departure_full_body_clearance'
    available_intervals = []
    try:
        available_map = lt_rows(paths['video_frames.jsonl'])
        if available_map:
            available_intervals = [{'start_frame': available_map[0]['carla_frame'],
                                    'end_frame': available_map[-1]['carla_frame'],
                                    'start_time_s': available_map[0]['time_s'],
                                    'end_time_s': available_map[-1]['time_s']}]
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    def outcome(status, detail, intervals=(), observed=None):
        return {'status': status, 'method': method, 'intervals': list(intervals) or list(available_intervals),
                'sources': dict(sources), 'observed': observed or {}, 'missing': [],
                'detail': detail, 'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        result = outcome('unverified', 'Missing required original evidence: ' + ', '.join(missing))
        result['missing'] = missing
        return result
    try:
        from shapely.geometry import MultiPoint, Polygon
        geometry = json.loads(paths['road_geometry.json'].read_text())
        rows, mapping = lt_rows(paths['body_history.jsonl']), lt_rows(paths['video_frames.jsonl'])
        if not rows or not mapping:
            raise ValueError('Empty original body history or frame map')
        if len(rows) != len(mapping):
            raise ValueError('Body history does not cover every original frame')
        polygon = Polygon(geometry['intersection_xy_m'])
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError('Invalid authored intersection polygon')
        road_ids = [geometry[k] for k in ('approach_road_id', 'connector_road_id', 'departure_road_id')]
        if len(set(road_ids)) != 3 or geometry.get('two_way') is not True:
            raise ValueError('Connected two-directional road identity missing')
        direction = geometry['departure_direction_xy']
        if len(direction) != 2 or not all(math.isfinite(v) for v in direction) or math.hypot(*direction) == 0:
            raise ValueError('Departure roadway direction missing')
        for i, (row, frame) in enumerate(zip(rows, mapping)):
            if row['frame'] != frame['carla_frame'] or frame['video_frame'] != i:
                raise ValueError('Original frame identity join differs')
            if not math.isfinite(row['time_s']) or abs(row['time_s'] - frame['time_s']) > .0001:
                raise ValueError('Original timestamp join differs')
            if i and (row['frame'] <= rows[i - 1]['frame'] or row['time_s'] <= rows[i - 1]['time_s']):
                raise ValueError('Original chronology is not strictly increasing')
            if len(row['body_vertices_m']) < 4 or any(len(v) < 3 or not all(math.isfinite(n) for n in v) for v in row['body_vertices_m']):
                raise ValueError('Incomplete full-body vertices')
            if row.get('road_id') is None:
                raise ValueError('Native roadway identity unavailable')
        intervals = [{'start_frame': rows[0]['frame'], 'end_frame': rows[-1]['frame'],
                      'start_time_s': rows[0]['time_s'], 'end_time_s': rows[-1]['time_s']}]
        hulls = [MultiPoint([v[:2] for v in r['body_vertices_m']]).convex_hull for r in rows]
        centers = [[sum(v[d] for v in r['body_vertices_m']) / len(r['body_vertices_m']) for d in (0, 1)] for r in rows]
        approach = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[0]]
        connectors = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[1] and hulls[i].intersects(polygon)]
        clear_departures = [i for i, r in enumerate(rows) if r['road_id'] == road_ids[2] and not hulls[i].intersects(polygon)]
        ordered = bool(approach and clear_departures) and any(approach[0] < c < clear_departures[-1] for c in connectors)
        # Positive downstream movement must be observed after entering the
        # connector; no duration/position epsilon is used as a legal threshold.
        downstream_progress = max((sum((centers[d][k] - centers[c][k]) * direction[k] for k in (0, 1))
                                   for c in connectors for d in clear_departures if c < d), default=0)
        complete = bool(ordered) and downstream_progress > 0
        observed = {'native_road_id_history': [{'frame': r['frame'], 'time_s': r['time_s'], 'road_id': r['road_id']} for r in rows],
                    'body_junction_overlap': [{'frame': r['frame'], 'intersects': hulls[i].intersects(polygon)} for i, r in enumerate(rows)],
                    'clear_departure_frames': [rows[i]['frame'] for i in clear_departures],
                    'downstream_progress_projection_m': downstream_progress,
                    'observed_motion': any(centers[i] != centers[i - 1] for i in range(1, len(centers)))}
        result = outcome('met' if complete else 'not_met',
                         'Ordered approach, connector interaction and full-body downstream clearance observed.' if complete else
                         'Valid original history does not establish the complete ordered route and downstream clearance.', intervals, observed)
        return result
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        return outcome('unverified', str(error))

# Migration002: source provenance, capture sealing and evidence-backed results.
def provenance_kind(root):
    root=Path(root)
    for filename in ('acquisition-provenance.json','capture-seal.json'):
        p=root/filename
        if p.is_file():
            value=json.loads(p.read_text());kind=value.get('provenance_kind',value.get('kind'))
            if kind in ('native','synthetic_fixture'):return kind
    old=root/'native-run-status.json'
    if old.is_file():
        value=json.loads(old.read_text())
        if isinstance(value.get('errors'),list):return 'native'  # Failed Native capture is still Native provenance.
    return 'synthetic_fixture'

def provenance_record(root):
    root=Path(root);kind=provenance_kind(root)
    marker=root/'acquisition-provenance.json'
    value=json.loads(marker.read_text()) if marker.is_file() else {}
    return {'provenance_kind':kind,'diagnostic_fixture':value.get('diagnostic_fixture',kind!='native'),
            'scope':'Source protocol provenance, not physical or legal acceptance'}

def capture_context(values):
    result={}
    for key in ('geometry','native_landmarks','native_map_name','cal','surface_authoring','context','aisle_inventory'):
        if key in values:
            try:json.dumps(values[key],allow_nan=False);result[key]=values[key]
            except (TypeError,ValueError):pass
    landmarks=values.get('landmarks')
    if landmarks is not None:result['landmark_ids']=[str(x.id) for x in landmarks]
    mapping=values.get('mapping')
    if mapping is not None:result['native_map_name']=mapping.name
    return result

def seal_capture(attempt,*,frames,restoration,errors,encoder_exit_codes=None,context=None):
    from .common import tree,digest,sha
    root=Path(attempt)
    if errors or restoration.get('restored') is not True:raise ValueError('Cannot seal capture before verified restoration')
    codes=encoder_exit_codes or {}
    if codes and any(code!=0 for code in codes.values()):raise ValueError('Cannot seal unclosed/failed encoders')
    sources=tree(root)
    if not (root/'trace.jsonl').is_file() or not (root/'video_frames.jsonl').is_file():raise ValueError('Cannot seal missing original acquisition')
    write(root/'acquisition-context.json',context or {})
    sources=tree(root)
    receipt={'format':'worker-sealed-capture-v2','provenance_kind':'native','diagnostic_fixture':json.loads((root/'acquisition-provenance.json').read_text()).get('diagnostic_fixture',False) if (root/'acquisition-provenance.json').is_file() else False,
       'frames':frames,'restoration':restoration,'encoder_exit_codes':codes,'sources':sources,
       'native_revision':{'construction_sha256':sha(root/'construction.json'),'runner_sha256':sha(root/'runner.py')},
       'events':['capture_finished','encoders_closed','restoration_verified'],'source_digest':digest(sources),
       'physical_acceptance_claimed':False}
    if (root/'capture-seal.json').exists():raise ValueError('Retain existing capture seal')
    write(root/'capture-seal.json',receipt);return receipt

def finalize_report(root,output):
    from .common import sha
    path=Path(output)
    if path.is_file():
        report=json.loads(path.read_text());report.update(provenance_record(root))
        report['limitations']=[s for s in report.get('limitations',[]) if 'fixture' not in s.lower()]
        report['limitations']+=['Diagnostic provenance denotes a software fixture only; Native source provenance does not establish physical acceptance.']
        if (Path(root)/'result.json').is_file():
            result=json.loads((Path(root)/'result.json').read_text());report['physical_checks']=result['physical_checks'];report['realized_observables']=result['realized_observables']
        write(path,report)

def physical_result(root,result):
    from .common import sha
    root=Path(root);cfg=json.loads((root/'config.json').read_text())
    assessment=assess_physical(root,cfg,result.get('target_checks',[]));checks=assessment['physical_checks'];observed=assessment['realized_observables']
    if cfg.get('law_id') in ('NRS-484B-400-2a','NRS-484B-400-2b'):
        check=assess_left_turn(root);checks['maneuver']=check;observed['left_turn']=check.get('observed',{})
    motion=observed.get('original_motion',{})
    attempt_status='unverified' if not motion else ('met' if motion.get('sampled_path_m',0)>0 else 'not_met')
    checks['attempt']={'status':attempt_status,'method':'observed finite original motion; separate from target success','intervals':checks['maneuver'].get('intervals',[]),'sources':checks['maneuver']['sources'],'physical_causation_claimed':False}
    result['physical_checks']=checks
    result['setup_confirmed']=checks['setup']['status']=='met'
    result['maneuver_completed']=checks['maneuver']['status']=='met'
    result['behavior_attempted']=checks.get('attempt',checks['target'])['status']=='met'
    result['physical_observations']=observed
    descriptor=default_descriptor(cfg);reference=descriptor['motion_source'];summary={}
    for name,unit,statistic in [('sampled_path_m','m','sum of consecutive body-center distances'),('displacement_m','m','first-to-last body-center distance')]:
        value=motion.get(name)
        if type(value) in (int,float) and math.isfinite(value):summary[name]={'value':value,'unit':unit,'statistic':statistic,'method':'original timestamp-joined sampled body geometry','time_window':'recorded original motion interval','reference':reference}
    result['realized_observables']=summary
    result.update(provenance_record(root));result['physical_acceptance_claimed']=False
    result['termination_reason']='Saved evidence assessed; maneuver '+checks['maneuver']['status']+'; legal judgments remain separate'
    return result

def missing_evidence_result(root,error):
    from .common import sha
    root=Path(root);cfg=json.loads((root/'config.json').read_text())
    sources={name:sha(root/name) for name in ('config.json','trace.jsonl','video_frames.jsonl') if (root/name).is_file()}
    check={'status':'unverified','method':'selected_analyzer_missing_required_evidence','intervals':[],
           'sources':sources,'missing':[str(error)]}
    result={'case_id':cfg['selected_case_id'],'measured_values':{},'target_checks':[{'target':'required_evidence','requested':True,'measured':False,'method':check['method'],'tolerance':0,'matched':False,'physical_cause_confirmed':False,'cause_evidence':str(error)}],
      'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'Required evidence unavailable',
      'physical_checks':{k:dict(check) for k in ('setup','target','maneuver')},'realized_observables':{},'physical_observations':{'available_source_hashes':sources},
      'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
      'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],'recording_evidence':[],
      'physical_acceptance_claimed':False,**provenance_record(root)}
    validate_result(result);write(root/'result.json',result);return result
