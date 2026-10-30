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

def _box(point,width=1.6,length=4):
 x,y=point;return [[x+dx,y+dy,z] for z in (0,1.5) for dx,dy in [(-length/2,-width/2),(-length/2,width/2),(length/2,width/2),(length/2,-width/2)]]
def _put(obj,path,value):
 keys=path.split('.')
 for key in keys[:-1]:obj=obj.setdefault(key,{})
 obj[keys[-1]]=value

def make_motion_fixture(root,cfg,kind):
 """Author three-frame Native-style SOFTWARE data, never accepted recording.

The assessor never reads ``kind``. Only this diagnostic generator does. Existing
law packets are retained or refreshed from the new original-shaped source.
"""
 root=Path(root);d=default_descriptor(cfg);source=root/d['motion_source']
 if kind=='missing_evidence':
  if source.exists():source.unlink()
  return {'removed_source':d['motion_source'],'descriptor':d}
 if kind not in ('complete_motion','incomplete_motion'):raise ValueError('Unknown physical fixture kind')
 mapping=_rows(root/'video_frames.jsonl')
 if len(mapping)!=3:raise ValueError('Physical diagnostic generator expects retained three original frames')
 old=_rows(source) if source.exists() else []
 if not isinstance(old,list):old=[]
 complete=kind=='complete_motion';criterion=d['criterion'];points=[[0,1.75],[5,1.75],[10,1.75]];headings=[0,0,0]
 if criterion=='intersection_clearance':
  points=[[-20,1.75],[0,1.75],[1.75,-20]] if d.get('exit_axis')==1 else [[-20,1.75],[0,1.75],[20,1.75]]
  headings=[0,45,-90] if d.get('exit_axis')==1 else [0,0,0]
 elif criterion=='turn':
  angle=d['turn_degrees'];sign=d.get('turn_sign',1);points=[[-20,-5],[0,-1],[0,-20]] if angle==90 else [[-20,-5],[0,-1],[-20,5]];headings=[0,sign*angle/2,sign*angle]
 elif criterion=='reverse_goal':
  goal=d['goal_xy_m'];points=[[goal[0]-10,goal[1]],[goal[0]-5,goal[1]],list(goal)];headings=[180,180,180]
 elif criterion=='lane_transition':points=[[0,5.25 if d['destination_lane']==-1 else 1.75],[5,3.5],[10,1.75 if d['destination_lane']==-1 else 5.25]]
 elif criterion=='road_transition':points=[[-20,1.75],[0,1.75],[1.75,-20 if d['destination_road']==4 else 20]];headings=[0,45,90]
 elif criterion=='overtake_pass':points=[[0,-6],[20,-2],[40,-6]]
 elif criterion=='following_progress':points=[[0,-6],[10,-6],[20,-6]]
 elif criterion=='caravan_entry':points=[[180,1.75],[190,1.75],[200,1.75]]
 elif d.get('direction_xy')==[-1,0]:points=[[10,1.75],[5,1.75],[0,1.75]];headings=[180]*3
 if criterion=='travel_progress':
  goal=d['minimum_progress_m']*1.2;direction=d.get('direction_xy',[1,0]);points=[[direction[0]*goal*i/2,1.75+direction[1]*goal*i/2] for i in range(3)]
 if not complete:
  if criterion=='travel_progress':
   goal=d['minimum_progress_m'];direction=d.get('direction_xy',[1,0]);points=[[direction[0]*goal*i/5,1.75+direction[1]*goal*i/5] for i in range(3)]
  elif criterion=='intersection_clearance':points=[[-20,1.75],[-10,1.75],[0,1.75]];headings=[0,0,0]
  elif criterion=='turn':points=[[-20,-5],[-15,-3],[-10,-1]];headings=[0,d.get('turn_sign',1)*d['turn_degrees']*.2,d.get('turn_sign',1)*d['turn_degrees']*.4]
  elif criterion in ('lane_transition','road_transition'):points=[[i*5,points[0][1]] for i in range(3)]
  elif criterion=='reverse_goal':
   goal=d['goal_xy_m'];points=[[goal[0]-15+i*5,goal[1]] for i in range(3)]
  elif criterion=='overtake_pass':points=[[i*5,-6] for i in range(3)]
  elif criterion=='caravan_entry':points=[[180+10*i,1.75] for i in range(3)]
  else:points=[points[0]]*3;headings=[headings[0]]*3
 rows=[]
 for i,m in enumerate(mapping):
  row=copy.deepcopy(old[min(i,len(old)-1)]) if old else {}
  row.update(frame=m['carla_frame'],time_s=m['time_s'])
  if d.get('body_key'):_put(row,d['body_key'],_box(points[i],2.4 if '127-2' in cfg['law_id'] else 1.6,10 if '127-2' in cfg['law_id'] else 4))
  else:_put(row,d.get('position_key','position_m'),[*points[i],0])
  row['heading_deg']=headings[i]
  for speed_key in ('speed_mps','subject_speed_mps','ego_speed_mps'):
   if speed_key in row:row[speed_key]=5
  for role_key in ('ego','states.ego'):
   actor=_get(row,role_key)
   if isinstance(actor,dict) and 'speed_mps' in actor:actor['speed_mps']=5
  if d.get('heading_key'):_put(row,d['heading_key'],headings[i])
  if d.get('cumulative_heading_key'):_put(row,d['cumulative_heading_key'],headings[i]-headings[0])
  if criterion=='lane_transition':_put(row,d['lane_key'],d['destination_lane'] if complete and i else (-2 if d['destination_lane']==-1 else -1))
  if criterion=='road_transition':_put(row,d['road_key'],([1,13 if d['destination_road']==4 else 14,d['destination_road']][i] if complete else 1))
  if criterion=='turn' and d.get('destination_road'):_put(row,d.get('road_key','road_id'),[1,13,d['destination_road']][i] if complete else [1,1,13][i])
  if criterion in ('following_progress','overtake_pass'):
   other=[20+5*i,-6] if criterion=='overtake_pass' else [160+10*i,-6]
   _put(row,d['other_body_key'],_box(other,2.4,10))
   row.setdefault('entrant_vertices_m',_box([80+10*i,-2],1.8,4));row['requested_phase']='overtaking' if criterion=='overtake_pass' and i==1 else 'following'
  if criterion=='reverse_goal':_put(row,d.get('velocity_key','velocity_mps'),[5 if any(math.dist(a,b)>0 for a,b in zip(points,points[1:])) else 0,0,0]);row['reverse_control']=True
  if criterion=='caravan_entry':
   roles=row.setdefault('participants',{})
   for role,point in [('front',[250+10*i,1.75]),('rear',[110+10*i,1.75]),('entrant',[145+10*i,1.75 if complete and i else 5.25])]:
    actor=roles.setdefault(role,{});actor['body_vertices_m']=_box(point);actor['speed_mps']=5;actor['lane_id']=-1 if role!='entrant' or complete and i else -2
   roles['subject']['speed_mps']=5 if complete else 0;roles['subject']['lane_id']=-1
  rows.append(row)
 source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
 # Keep the standard original trace/frame identities coherent with the authored
 # motion source. Non-motion trace fields remain retained diagnostic context.
 trace=_rows(root/'trace.jsonl');moving=any(math.dist(a,b)>0 for a,b in zip(points,points[1:]))
 for i,row in enumerate(trace):
  row.update(frame=mapping[i]['carla_frame'],time_s=mapping[i]['time_s'],position_m=[*points[i],0],position={'x':points[i][0],'y':points[i][1],'z':0},heading_deg=headings[i],speed_mps=5 if moving else 0,velocity_mps=[5*math.cos(math.radians(headings[i])) if moving else 0,5*math.sin(math.radians(headings[i])) if moving else 0,0])
 (root/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trace))
 # Existing aggregate law packets remain analyses of exactly these frames.
 packet_path=root/'case_observation.json'
 if packet_path.exists():
  p=_read(packet_path)
  if cfg['law_id'] in ('NRS-484B-250-1','NRS-484B-250-2'):
   p['entry_events']['ego']={'frame':mapping[1]['carla_frame'],'time_s':mapping[1]['time_s']};p['ego_clearance_frame']=mapping[2]['carla_frame'];p['motion_rows']=[{'frame':m['carla_frame'],'ego_speed_mps':5 if complete else 0,'other_speed_mps':5} for m in mapping]
  elif cfg['law_id']=='NRS-484B-227-1':p['trajectory']=[{'frame':m['carla_frame'],'velocity_xy':[5*math.cos(math.radians(headings[i])),5*math.sin(math.radians(headings[i]))] if complete else [0,0],'body_vertices_m':_box(points[i]),'body_overlaps_median':False} for i,m in enumerate(mapping)]
  elif cfg['law_id']=='NRS-484B-220-1':p['velocity_rows']=[{'frame':r['frame'],'velocity_xy':r['velocity_mps'][:2]} for r in trace]
  elif cfg['law_id']=='NRS-484B-413-2':p['path_rows']=[{'x_m':v[0],'y_m':v[1]} for v in points];p['turn_onset_frame']=mapping[-1]['carla_frame']
  elif cfg['law_id']=='NRS-484B-600-1a':
   for r in p['motion_rows']:r['ego_speed_mps']=5 if complete else 0
  packet_path.write_text(json.dumps(p,indent=2)+'\n')
 return {'motion_source':d['motion_source'],'descriptor':d,'provenance_kind':'native','fixture_provenance':'software_authored_native_style; never an accepted recording'}
