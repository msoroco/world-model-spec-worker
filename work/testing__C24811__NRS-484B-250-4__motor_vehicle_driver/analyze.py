"""Original dark-head, stop-line, earlier-stop, occupancy and ray measurements."""
import argparse,hashlib,json
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
from worker_exchange.native_output import write_result

def required(root,name):
 p=root/name
 if not p.is_file():raise ValueError('Missing required source: '+name)
 return p

def rows(root):
 values=[json.loads(s) for s in required(root,'interaction_history.jsonl').read_text().splitlines() if s]
 if not values:raise ValueError('No original interaction history')
 return values

def body_overlap(vertices,polygon):
 return MultiPoint([(v[0],v[1]) for v in vertices]).convex_hull.intersects(polygon)

def inoperative_heads(root):
 context=json.loads(required(root,'signal_context.json').read_text());samples=rows(root)
 if context.get('head_count')!=len(context.get('installed_heads',[])):raise ValueError('Four installed signal heads not sourced')
 if context.get('reference_kind','line')=='line' and not context.get('physical_stopline_tiles'):raise ValueError('Physical stop line inventory absent')
 identities={x['actor_id'] for x in context['installed_heads']}
 states=[{'frame':r['frame'],'heads':{x['actor_id']:x['state'] for x in r['head_states']}} for r in samples]
 if any(set(s['heads'])!=identities for s in states):raise ValueError('Head inventory changed during original episode')
 polygon=Polygon(context['intersection_polygon_xy_m'])
 entry=next((r for r in samples if body_overlap(r['states']['ego']['body_vertices_m'],polygon)),None)
 if entry is None:raise ValueError('No original subject entry sample')
 at_entry={x['actor_id']:x['state'] for x in entry['head_states']}
 return {'installed_head_count':context['head_count'],'covered_requested':context.get('covered_requested',False),'native_covers':context.get('native_covers',[]),'head_state_history':states,'entry_frame':entry['frame'],'entry_head_states':at_entry,
  'all_heads_dark_at_entry':bool(at_entry) and all(s=='Off' for s in at_entry.values()),'uncovered_pixel_verified':False,'reference_kind':context.get('reference_kind','line'),
  'physical_stopline_tile_count':len(context['physical_stopline_tiles']),
  'scope':'Native API state and authored uncovered candidate; physical pixels and official status require review'}

def stop_before_entry(root):
 context=json.loads(required(root,'signal_context.json').read_text());samples=rows(root);polygon=Polygon(context['intersection_polygon_xy_m'])
 stopline=float(context['reference_line_x_m']);entries=[];halts=[]
 for r in samples:
  ego=r['states']['ego'];front=max(v[0] for v in ego['body_vertices_m']);inside=body_overlap(ego['body_vertices_m'],polygon)
  if inside:entries.append({'frame':r['frame'],'time_s':r['time_s'],'front_x_m':front,'speed_mps':ego['speed_mps']})
  if ego['speed_mps']<.05 and front<stopline:halts.append({'frame':r['frame'],'time_s':r['time_s'],'front_x_m':front,'speed_mps':ego['speed_mps']})
 if not entries:raise ValueError('Missing entry observation')
 return {'stopline_x_m':stopline,'halt_samples_before_line':halts,'first_body_entry':entries[0],
  'sampled_halt_precedes_entry':bool(halts) and halts[0]['frame']<entries[0]['frame'],'reference_kind':context.get('reference_kind','line'),'exact_zero_speed_before_reference_frames':[r['frame'] for r in samples if r['states']['ego']['speed_mps']==0 and max(v[0] for v in r['states']['ego']['body_vertices_m'])<stopline],
  'sampling_limit':'20Hz original velocity and full-body vertices; continuous cessation and statutory stop judgment unresolved'}

def priority_sequence(root):
 context=json.loads(required(root,'signal_context.json').read_text());samples=rows(root);polygon=Polygon(context['intersection_polygon_xy_m'])
 earlier=[{'frame':r['frame'],'time_s':r['time_s']} for r in samples if r['states']['earlier_stopped']['speed_mps']<.05 and not body_overlap(r['states']['earlier_stopped']['body_vertices_m'],polygon)]
 occupant=[{'frame':r['frame'],'time_s':r['time_s']} for r in samples if body_overlap(r['states']['inside_vehicle']['body_vertices_m'],polygon)]
 entry=next((r for r in samples if body_overlap(r['states']['ego']['body_vertices_m'],polygon)),None)
 if not earlier or not occupant or entry is None:raise ValueError('Missing earlier stop, occupancy or subject entry')
 return {'earlier_stopped_samples':earlier,'other_occupancy_samples':occupant,'ego_first_body_entry_frame':entry['frame'],
  'earlier_stop_before_ego_entry':earlier[0]['frame']<entry['frame'],
  'other_occupancy_before_ego_entry':occupant[0]['frame']<entry['frame'],
  'judgment_limit':'Actual yielded priority and cautiousness require physical review; no numerical caution standard'}

def sight_obstruction(root):
 samples=rows(root);rays=[r['sight_ray'] for r in samples]
 blocked=[{'frame':r['frame'],'time_s':r['time_s'],'hit_count':len(r['sight_ray']['hits'])} for r in samples if r['sight_ray']['hits']]
 if not blocked:raise ValueError('No original obstructed sight ray')
 candidates=[dict(frame=r['frame'],time_s=r['time_s'],**c) for r in samples for c in r.get('sight_candidates',[])]
 if not candidates:raise ValueError('Missing original sampled viewpoint candidates')
 clear=[c for c in candidates if c['clear']]
 nearest=min(clear,key=lambda c:c['distance_to_intersection_m']) if clear else None
 return {'sample_count':len(rays),'blocked_samples':blocked,'observer_points_m':[r['eye_m'] for r in rays],'sampled_viewpoint_candidates':candidates,'nearest_sampled_clear_point':nearest,'clear_candidate_count':len(clear),'sampling_spacing_m':1,
  'sampling_limit':'Finite original Native rays; driver anatomy, continuous nearest clear point and rendered pixels unverified'}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());spec=[
 ('installed_dark_signal_heads','inoperative_heads',inoperative_heads(root),['signal_context.json','interaction_history.jsonl']),
 ('marked_line_stop_before_entry','stop_before_entry',stop_before_entry(root),['signal_context.json','interaction_history.jsonl']),
 ('earlier_stop_and_intersection_occupancy','priority_sequence',priority_sequence(root),['signal_context.json','interaction_history.jsonl']),
 ('sampled_sight_obstruction','sight_obstruction',sight_obstruction(root),['interaction_history.jsonl'])]
 values={key:{'method':method,'value':value,'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in names}} for key,method,value,names in spec}
 output.write_text(json.dumps({'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':values,
  'limitations':['Diagnostic three-frame packet is software compatibility only.','Uncovered official heads, actual cessation, pixel visibility, connected routes and complete Native occlusion need GPU review.',
   'Cautious proceeding and legal yielding remain unresolved.']},indent=2)+'\n')
 trace=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 (channels/'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\n' for r in trace))
 halt=values['marked_line_stop_before_entry']['value']
 result={'case_id':cfg['selected_case_id'],'measured_values':{'first_body_entry_frame':halt['first_body_entry']['frame']},
  'target_checks':[{'target':'sampled_stop_before_entry','requested':cfg['request_stop'],'measured':halt['sampled_halt_precedes_entry'],
   'method':'original 20Hz full body and velocity sample ordering','tolerance':0,'matched':halt['sampled_halt_precedes_entry']==cfg['request_stop'],
   'physical_cause_confirmed':False,'cause_evidence':'interaction_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved analysis; Native verification pending',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
  'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'channels/kin.speed.jsonl'}],'realized_observables':{}}
 write_result(root,result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 finalize(Path(a.attempt),Path(a.output))
