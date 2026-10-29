"""Saved entrance-control geometry, original motion and sampled sight; no legal verdict."""
import argparse,hashlib,json
from pathlib import Path
from shapely.geometry import MultiPoint,box
from worker_exchange.native_output import write_result

def required(root,name):
 p=root/name
 if not p.is_file():raise ValueError('Missing required source: '+name)
 return p

def governing_control(root):
 c=json.loads(required(root,'control_context.json').read_text())
 if c.get('mode') not in ('yield_nearest','stop_within') or not c.get('map_landmarks'):
  raise ValueError('Missing original entrance control inventory')
 return {'mode':c['mode'],'map_landmarks':c['map_landmarks'],'stopline_present':c['stopline_present'],
  'crosswalk_present':c['crosswalk_present'],'physical_stopline_tiles':len(c['physical_stopline_tiles']),
  'actual_officer_signal_control':c['actual_officer_signal_control'],'sign_authorization':c['sign_authorization']}

def interaction_timing(root):
 rows=[json.loads(s) for s in required(root,'interaction_history.jsonl').read_text().splitlines() if s]
 if not rows:raise ValueError('Missing original interaction samples')
 junction=box(-7,-7,7,7);samples=[]
 for r in rows:
  e,t=r['ego'],r['through'];eb=MultiPoint([(v[0],v[1]) for v in e['body_vertices_m']]).convex_hull
  tb=MultiPoint([(v[0],v[1]) for v in t['body_vertices_m']]).convex_hull
  samples.append({'frame':r['frame'],'time_s':r['time_s'],'ego_speed_mps':e['speed_mps'],
   'ego_body_overlap_junction':eb.intersects(junction),'through_body_overlap_junction':tb.intersects(junction),
   'ego_min_x_m':min(v[0] for v in e['body_vertices_m']),'ego_max_x_m':max(v[0] for v in e['body_vertices_m']),
   'through_min_y_m':min(v[1] for v in t['body_vertices_m']),'through_max_y_m':max(v[1] for v in t['body_vertices_m'])})
 return {'samples':samples,'first_ego_body_entry_frame':next((v['frame'] for v in samples if v['ego_body_overlap_junction']),None),
  'engineering_stop_samples_upstream':[v['frame'] for v in samples if v['ego_speed_mps']<.05 and v['ego_max_x_m']<-7],
  'through_within_intersection_frames':[v['frame'] for v in samples if v['through_body_overlap_junction']],
  'sampling_limit':'20Hz body polygons and speeds; no statutory hazard/yield classification'}

def nearest_visible_point(root):
 rows=[json.loads(s) for s in required(root,'view_samples.jsonl').read_text().splitlines() if s]
 if not rows:raise ValueError('No original viewpoint samples')
 candidates=[r for r in rows if r.get('clear_ray') is True]
 if not candidates:raise ValueError('No original clear ray sample')
 winner=min(candidates,key=lambda r:r['distance_to_intersection_m'])
 return {'point_xy_m':winner['point_xy_m'],'distance_to_intersection_m':winner['distance_to_intersection_m'],
  'frame':winner['frame'],'clear_sample_count':len(candidates),'total_samples':len(rows),
  'sampling_note':'Nearest among original sampled clear rays; continuous nearest point and rendered pixel visibility unverified'}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());mode=cfg['mode'];context=governing_control(root);timing=interaction_timing(root)
 spec=[('governing_control','governing_control',context,['control_context.json']),
       ('intersection_motion','interaction_timing',timing,['interaction_history.jsonl'])]
 if mode=='yield_nearest':spec.append(('sampled_nearest_clear_view','nearest_visible_point',nearest_visible_point(root),['view_samples.jsonl']))
 values={key:{'method':method,'value':value,'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in names}} for key,method,value,names in spec}
 output.write_text(json.dumps({'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':values,
  'limitations':['Three-frame fixture is diagnostic only.','Original sign pixels, actual governing relation and physical behavior remain GPU checks.',
   'Immediate hazard, cautious proceeding, continuous nearest-view point and statutory yielding are unresolved.']},indent=2)+'\n')
 trace=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 (channels/'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\n' for r in trace))
 result={'case_id':cfg['selected_case_id'],'measured_values':{'sampled_ego_entry_frame':timing['first_ego_body_entry_frame']},
  'target_checks':[{'target':'ego_body_entry_sample','requested':True,'measured':timing['first_ego_body_entry_frame'] is not None,
   'method':'original full-body polygon junction overlap','tolerance':0,'matched':timing['first_ego_body_entry_frame'] is not None,
   'physical_cause_confirmed':False,'cause_evidence':'interaction_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved diagnostic only',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
  'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'channels/kin.speed.jsonl'}],'realized_observables':{}}
 write_result(root,result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 finalize(Path(a.attempt),Path(a.output))
