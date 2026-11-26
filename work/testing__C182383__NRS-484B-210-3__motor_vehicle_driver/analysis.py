"""Saved-only original body envelope, paved edge and right-pass observations."""
import argparse
import hashlib
import json
from pathlib import Path
from package_spec import CAMERA_NAMES
from right_pass_envelope import measure_data
def need(ok,message):
 if not ok:raise ValueError(message)
def source(root,name):
 path=root/name
 if not path.is_file() or path.is_symlink():raise ValueError('Missing required source: '+name)
 return path
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source_sealed_paved_edge_measurement(value):return value
def envelope_from_rows(history):
 rows=history['samples'];packet={'assignment_id':history['assignment_id'],'original_trace_id':history['reviewed_site_sha256'],'ego_actor_id':history['actor_ids'][0],'overtaken_actor_id':history['actor_ids'][1],'expected_pass':history['requested_right_pass'],'frames':[]}
 for row in rows:
  ego_s,ego_y=row['ego_body_s_bounds_m'],row['ego_body_y_bounds_m'];target_s,target_y=row['target_body_s_bounds_m'],row['target_body_y_bounds_m'];paved=row['paved_y_bounds_m']
  packet['frames'].append({'time_s':row['time_s'],'ego_left_m':ego_y[0],'ego_right_m':ego_y[1],'overtaken_left_m':target_y[0],'overtaken_right_m':target_y[1],'paved_left_m':paved[0],'paved_right_m':paved[1],'longitudinal_overlap':max(ego_s[0],target_s[0])<=min(ego_s[1],target_s[1]),'ego_ahead_of_overtaken':ego_s[0]>target_s[1]})
 return packet
def analyze(attempt):
 root=Path(attempt).resolve();config=json.loads(source(root,'config.json').read_text());case=config['selected_case_id'];receipt=json.loads(source(root,'original-source-receipt.json').read_text());diagnostic=receipt.get('diagnostic_fixture') is True
 need(receipt.get('source_kind')==('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture') and receipt.get('case_id')==case,'source provenance differs')
 for key,name in [('history_sha256','right-pass-history.json'),('trace_sha256','trace.jsonl'),('frame_map_sha256','video_frames.jsonl'),('envelope_sha256','right-pass-envelope.json'),('measurement_sha256','right-pass-measurement.json')]:need(receipt.get(key)==sha(source(root,name)),'sealed paved-edge source differs: '+name)
 history=json.loads(source(root,'right-pass-history.json').read_text());rows=history['samples'];traces=[json.loads(x) for x in source(root,'trace.jsonl').read_text().splitlines()];mapping=[json.loads(x) for x in source(root,'video_frames.jsonl').read_text().splitlines()]
 need(history.get('assignment_id')==config['assignment_id'] and history.get('case_id')==case and len(rows)==len(traces)==len(mapping) and len(rows)>=3 and len(history['actor_ids'])==2,'original case, actor or frame count differs')
 need(history.get('public_highway') is True and history.get('paved_surface_classified') is True and history.get('adjacent_surface_classified') is True and history.get('paved_surface_source') and history.get('paved_boundary_source') and history.get('connected_route_source'),'independent pavement classification/route source missing')
 for i,(row,trace,mapped) in enumerate(zip(rows,traces,mapping)):
  need(row['frame']==mapped['video_frame']==i and row['native_frame']==trace['frame']==mapped['native_frame']==mapped['carla_frame'] and row['time_s']==trace['time_s']==mapped['time_s'] and row['actor_ids']==history['actor_ids'] and abs(row['ego_speed_mps']-trace['speed_mps'])<1e-6,'original body/trace/video join differs')
  if not diagnostic:need(row['ego_position_xyz_m']==trace['position_m'],'original ego body pose differs from trace')
 envelope=json.loads(source(root,'right-pass-envelope.json').read_text());need(envelope==envelope_from_rows(history),'original body envelope differs from Native rows')
 measured=measure_data(envelope);need(json.loads(source(root,'right-pass-measurement.json').read_text())==measured,'saved body/pavement measurement differs')
 values={'paved_surface_classification':{'public_highway':True,'paved_surface_source':history['paved_surface_source'],'adjacent_surface_classified':True},'paved_edge_geometry':{'paved_boundary_source':history['paved_boundary_source'],'bounds_by_original_frame':[row['paved_y_bounds_m'] for row in rows]},'ego_and_overtaken_identity':{'actor_ids':history['actor_ids'],'driver_actor_id':history['driver_actor_id'],'overtaken_actor_source':history['overtaken_actor_source']},'ego_and_overtaken_body_envelopes':{'envelope_sha256':sha(root/'right-pass-envelope.json'),'frame_count':len(rows)},'right_side_pass_event':{'completed':measured['right_pass_completed'],'overlap_observations':measured['overlap_observations']},'actual_off_pavement_travel':{'observed':measured['actual_off_pavement_observed']},'physical_necessity_review':{'zero_clearance_fit_impossible':measured['zero_clearance_paved_fit_impossible_observed'],'legal_safe_alternative':'unresolved','review_limit':measured['review_limit']},'vehicle_motion':{'first_position_m':traces[0]['position_m'],'last_position_m':traces[-1]['position_m'],'maximum_speed_mps':max(row['ego_speed_mps'] for row in rows)}}
 sources={name:sha(source(root,name)) for name in ('right-pass-history.json','right-pass-envelope.json','original-source-receipt.json','trace.jsonl')}
 measurements={name:{'method':'source_sealed_paved_edge_measurement','value':source_sealed_paved_edge_measurement(value),'sources':sources} for name,value in values.items()}
 evidence=[]
 for channel in config['case']['recording_description']['channels']:
  name=channel['name'];path=root/('channel-'+name+'.jsonl');content=''.join(json.dumps({'time_s':row['time_s'],'value':row['ego_body_y_bounds_m'] if name in ('ego_and_overtaken_body_envelopes','actual_off_pavement_travel') else row['ego_body_s_bounds_m'] if name=='right_side_pass_event' else row['paved_y_bounds_m'] if name=='paved_edge_geometry' else row['ego_position_xyz_m'] if name=='vehicle_motion' else values[name]},sort_keys=True)+'\n' for row in rows)
  if path.exists():need(path.read_text()==content,'derived channel differs from saved source')
  else:path.write_text(content)
  evidence.append({'name':name,'unit':channel['unit'],'reference':path.name})
 context=root/'channel-reviewed_paved_edge_site.json';content=json.dumps({'reviewed_paved_edge_site':{'reviewed_site_sha256':history['reviewed_site_sha256'],'paved_surface_source':history['paved_surface_source'],'paved_boundary_source':history['paved_boundary_source']}},sort_keys=True)+'\n'
 if context.exists():need(context.read_text()==content,'reviewed paved-edge context differs')
 else:context.write_text(content)
 evidence.append({'name':'reviewed_paved_edge_site','unit':'source record','reference':context.name})
 from worker_exchange.native_output import physical_result,write_result
 result={'case_id':case,'measured_values':values,'target_checks':[{'target':'original right-side pass and off-pavement observations','requested':config['case']['requested_right_pass'],'measured':measured['right_pass_completed'],'method':'source-sealed body and paved-edge frames','tolerance':0,'matched':measured['right_pass_completed']==config['case']['requested_right_pass'],'physical_cause_confirmed':False,'cause_evidence':sources}],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'saved physical and legal review pending','physical_failure_flags':['physical_acceptance_unverified'],'trace_reference':'trace.jsonl','video_references':[n+'.mkv' for n in CAMERA_NAMES],'video_frame_map_reference':'video_frames.jsonl','recording_description':config['case']['recording_description'],'recording_evidence':evidence,'realized_observables':{},'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
 result=physical_result(root,result);write_result(root,result)
 return {'format':'worker-analysis-report','case_id':case,'analysis_complete':True,'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,'legal_verdict_claimed':False,'measurements':measurements,'physical_checks':result['physical_checks'],'realized_observables':result['realized_observables'],'limitations':['Actual off-pavement travel is separate from necessity; zero-clearance width alone cannot establish a safe lawful alternative.']}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if args.output.exists():raise ValueError('retain prior analysis report')
 args.output.write_text(json.dumps(analyze(args.attempt),indent=2)+'\n')
