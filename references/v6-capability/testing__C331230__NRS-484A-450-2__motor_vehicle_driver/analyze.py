"""Original body-front stopping samples relative to physical near-side crosswalk."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
 path=root/name
 if not path.is_file():raise ValueError('Missing required source: '+name)
 return path

def stop_before_crosswalk(root):
 geometry=json.loads(required(root,'crosswalk_geometry.json').read_text());rows=[json.loads(s) for s in required(root,'stop_history.jsonl').read_text().splitlines() if s]
 if not rows:raise ValueError('No original stop-approach samples')
 boundary=geometry['crosswalk_upstream_x_m'];samples=[]
 for row in rows:
  front=max(v[0] for v in row['body_vertices_m']);samples.append({'frame':row['frame'],'time_s':row['time_s'],
   'front_signed_distance_to_crosswalk_m':boundary-front,'speed_mps':row['speed_mps'],
   'body_front_before_crosswalk':front<boundary,'dwell_ticks_engineering':row['dwell_ticks'],'released':row['released']})
 first_crossing=next((s for s in samples if s['front_signed_distance_to_crosswalk_m']<=0),None)
 before=[s for s in samples if s['body_front_before_crosswalk']]
 return {'samples':samples,'first_crossing_frame':-1 if first_crossing is None else first_crossing['frame'],
  'minimum_pre_crossing_speed_mps':min(s['speed_mps'] for s in before) if before else -1,
  'crosswalk_upstream_x_m':boundary,'scope':'all original front-body and velocity samples; no statutory cessation epsilon or compliance verdict'}

def crosswalk_stop_context(root):
 geometry=json.loads(required(root,'crosswalk_geometry.json').read_text())
 return {'branch':geometry['branch'],'crosswalk_physical_tile_count':geometry['crosswalk_physical_tile_count'],
  'crosswalk_upstream_x_m':geometry['crosswalk_upstream_x_m'],'crosswalk_downstream_x_m':geometry['crosswalk_downstream_x_m'],
  'stop_sign_landmarks':geometry['stop_sign_landmarks'],'governed_approach_road_id':geometry['governed_approach_road_id'],
  'stopline_also_present':geometry['stopline_also_present'],'public_highway_designation':geometry['public_highway_designation'],
  'source':geometry['source']}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());motion=stop_before_crosswalk(root);context=crosswalk_stop_context(root)
 sha=lambda n:hashlib.sha256(required(root,n).read_bytes()).hexdigest()
 report={'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':{
  'pre_crosswalk_body_front_and_speed':{'method':'stop_before_crosswalk','value':motion,'sources':{'crosswalk_geometry.json':sha('crosswalk_geometry.json'),'stop_history.jsonl':sha('stop_history.jsonl')}},
  'selected_crosswalk_and_stop_control':{'method':'crosswalk_stop_context','value':context,'sources':{'crosswalk_geometry.json':sha('crosswalk_geometry.json')}}},
  'limitations':['Three-frame fixture is diagnostic only.','Actual STOP governance, crosswalk pixels, continuous cessation, viewpoint and source facts require GPU review.']}
 output.write_text(json.dumps(report,indent=2)+'\n')
 traces=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s];history=[json.loads(s) for s in required(root,'stop_history.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 for n,f in [('kin.speed','speed_mps'),('kin.velocity','velocity_mps')]:
  (channels/(n+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r[f]})+'\n' for r in traces))
 (channels/'stop_history.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r})+'\n' for r in history))
 case=cfg['case'];result={'case_id':case['case_id'],'measured_values':{'minimum_pre_crossing_speed_mps':motion['minimum_pre_crossing_speed_mps']},
  'target_checks':[{'target':'pre_crosswalk_stopping_samples','requested':'physical stop before near-side crosswalk','measured':len(motion['samples']),
   'method':'stop_before_crosswalk','tolerance':0,'matched':bool(motion['samples']),'physical_cause_confirmed':False,'cause_evidence':'stop_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved analysis; Native checks pending',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],
  'recording_evidence':[{'name':n,'unit':u,'reference':p} for n,u,p in [('kin.speed','m/s','channels/kin.speed.jsonl'),('kin.velocity','m/s','channels/kin.velocity.jsonl'),('stop_history','structured record','channels/stop_history.jsonl')]],'realized_observables':{}}
 write_result(root,result);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args();finalize(Path(a.attempt),Path(a.output))
