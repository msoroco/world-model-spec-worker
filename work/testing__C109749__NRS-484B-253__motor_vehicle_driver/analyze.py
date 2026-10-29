"""Original opposing movement and subject yield-window measurement; no hazard verdict."""
import argparse,hashlib,json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
 path=root/name
 if not path.is_file():raise ValueError('Missing required source: '+name)
 return path

def inside(vertices,polygon):
 xs=[v[0] for v in polygon];ys=[v[1] for v in polygon];return max(v[0] for v in vertices)>=min(xs) and min(v[0] for v in vertices)<=max(xs) and max(v[1] for v in vertices)>=min(ys) and min(v[1] for v in vertices)<=max(ys)

def opposing_yield_window(root):
 road=json.loads(required(root,'road_geometry.json').read_text());rows=[json.loads(s) for s in required(root,'interaction_history.jsonl').read_text().splitlines() if s]
 if not rows:raise ValueError('No original opposing interaction samples')
 observations=[]
 for row in rows:
  opposite=inside(row['opposing_body_vertices_m'],road['intersection_xy_m']);subject=inside(row['subject_body_vertices_m'],road['intersection_xy_m'])
  observations.append({'frame':row['frame'],'time_s':row['time_s'],'opposing_body_intersects_junction':opposite,
   'subject_body_intersects_junction':subject,'subject_speed_mps':row['subject_speed_mps'],'opposing_speed_mps':row['opposing_speed_mps'],
   'left_indicator_bit':row['subject_left_indicator_bit'],'ego_release_observed':row['ego_release_observed']})
 return {'original_samples':observations,'opposing_inside_sample_count':sum(x['opposing_body_intersects_junction'] for x in observations),
  'simultaneous_body_overlap_sample_count':sum(x['opposing_body_intersects_junction'] and x['subject_body_intersects_junction'] for x in observations),
  'scope':'finite body and motion samples; immediate hazard and right of way are legal judgments left unresolved'}

def two_way_context(root):
 road=json.loads(required(root,'road_geometry.json').read_text())
 return {'two_way':bool(road['two_way']),'approach_road_id':road['approach_road_id'],'opposing_road_id':2,
  'connector_road_id':road['connector_road_id'],'public_highway_designation':road['public_highway_designation']}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());measure=opposing_yield_window(root);context=two_way_context(root)
 sha=lambda name:hashlib.sha256(required(root,name).read_bytes()).hexdigest()
 report={'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':{
  'opposing_yield_window':{'method':'opposing_yield_window','value':measure,'sources':{'road_geometry.json':sha('road_geometry.json'),'interaction_history.jsonl':sha('interaction_history.jsonl')}},
  'two_way_opposing_context':{'method':'two_way_context','value':context,'sources':{'road_geometry.json':sha('road_geometry.json')}}},
  'limitations':['Fixture is a software diagnostic; Native trajectory is unverified.',
   'Opposing actor presence, lamp pixels, governing priority, immediate hazard and lawful yielding require GPU/source review.']}
 output.write_text(json.dumps(report,indent=2)+'\n')
 rows=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 interactions=[json.loads(s) for s in required(root,'interaction_history.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 for name,field in [('kin.speed','speed_mps'),('kin.velocity','velocity_mps')]:
  (channels/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r[field]})+'\n' for r in rows))
 (channels/'interaction_history.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r})+'\n' for r in interactions))
 case=cfg['case'];result={'case_id':case['case_id'],'measured_values':{'opposing_inside_samples':measure['opposing_inside_sample_count']},
  'target_checks':[{'target':'opposing_yield_window','requested':'opposing movement measured','measured':len(measure['original_samples']),
   'method':'opposing_yield_window','tolerance':0,'matched':bool(measure['original_samples']),'physical_cause_confirmed':False,
   'cause_evidence':'interaction_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved analysis; physical checks pending',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],
  'recording_evidence':[{'name':n,'unit':u,'reference':p} for n,u,p in [('kin.speed','m/s','channels/kin.speed.jsonl'),('kin.velocity','m/s','channels/kin.velocity.jsonl'),('interaction_history','structured record','channels/interaction_history.jsonl')]],'realized_observables':{}}
 write_result(root,result);return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args();finalize(Path(a.attempt),Path(a.output))
