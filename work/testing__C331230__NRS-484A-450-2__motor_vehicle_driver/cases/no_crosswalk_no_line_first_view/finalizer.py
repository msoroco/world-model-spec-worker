"""Saved-only finalizer for the no-crosswalk stop-line and first-view cases."""
import argparse,hashlib,json
from pathlib import Path
from stop_reference_measurements import analyze
CAMERAS=('overview','approach','reference_corner','driver_reference')
SUFFIXES=('__no_crosswalk_marked_stop_line','__no_crosswalk_no_line_first_view')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def measure_stop_line_halt(attempt,report):
 names=('approach_context.json','stop_history.jsonl','video_frames.jsonl')
 return {'value':{'selected_reference':report['selected_reference'],
   'first_full_halt':report['first_full_halt'],
   'first_reference':report['first_reference'],
   'first_intersection_entry':report['first_intersection_entry'],
   'halt_before_reference_and_junction_observed':report['halt_before_reference_and_junction_observed']},
   'method':'measure_stop_line_halt','sources':{name:sha(Path(attempt)/name) for name in names}}

def measure_first_view_halt(attempt,report):
 names=('approach_context.json','stop_history.jsonl','sight_history.jsonl','video_frames.jsonl')
 return {'value':{'selected_reference':report['selected_reference'],
   'first_full_halt':report['first_full_halt'],
   'first_observed_view':report['first_observed_view'],
   'first_intersection_entry':report['first_intersection_entry'],
   'halt_before_reference_and_junction_observed':report['halt_before_reference_and_junction_observed'],
   'sight_limit':report['sight_limit']},
   'method':'measure_first_view_halt','sources':{name:sha(Path(attempt)/name) for name in names}}

def finalize(attempt,output):
 from worker_exchange.native_output import physical_result,write_result
 attempt=Path(attempt);output=Path(output)
 if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
  raise ValueError('Use a fresh saved-source attempt')
 cfg=json.loads((attempt/'config.json').read_text())
 case=cfg.get('selected_case_id')
 if not isinstance(case,str) or not case.endswith(SUFFIXES) or cfg.get('assignment_id')!=case.rsplit('__',1)[0]:
  raise ValueError('Exact no-crosswalk case identity differs')
 required=['config.json','approach_context.json','stop_history.jsonl','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl',*(name+'.mkv' for name in CAMERAS)]
 ctx=json.loads((attempt/'approach_context.json').read_text())
 if not ctx.get('stop_line_exists'):required.append('sight_history.jsonl')
 for name in required:
  if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
 report=analyze(attempt)
 expected='marked_stop_line' if case.endswith('__no_crosswalk_marked_stop_line') else 'first_observed_view'
 if report['selected_reference']!=expected:raise ValueError('Selected stop-reference source differs')
 sources={name:sha(attempt/name) for name in required}
 value={'reference':expected,'first_halt':report['first_full_halt'],'first_reference':report['first_reference'],
        'first_junction_entry':report['first_intersection_entry'],'first_observed_view':report['first_observed_view'],
        'ordered':report['halt_before_reference_and_junction_observed'],
        'sight_limit':report['sight_limit'],'legal_conclusion':'unresolved'}
 channels=attempt/'channels';channels.mkdir()
 (channels/'stop_context.json').write_text(json.dumps({'case_id':case,'stop_context':{'selected_reference':expected,'approach_context':ctx,'legal_conclusion':'unresolved'},'observation':value,'sources':sources},indent=2)+'\n')
 with (channels/'halt_timing.jsonl').open('w') as stream:
  for row in report['samples']:stream.write(json.dumps({'time_s':row['time_s'],'value':row})+'\n')
 target='complete_halt_before_marked_stop_line' if expected=='marked_stop_line' else 'complete_halt_relative_to_first_observed_view'
 result={'case_id':case,'measured_values':{'reference_observation':value},'target_checks':[{'target':target,
   'requested':True,'measured':value['ordered'],'method':'original complete-body/speed/reference frame join',
   'tolerance':0,'matched':value['ordered'],'physical_cause_confirmed':False,
   'cause_evidence':['approach_context.json','stop_history.jsonl','video_frames.jsonl']+(['sight_history.jsonl'] if expected=='first_observed_view' else [])}],
   'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
   'termination_reason':'Saved original-source analysis; Native and legal review pending',
   'physical_failure_flags':['sign authority, marking and driver view unresolved'],
   'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
   'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['recording_description'],
   'recording_evidence':[{'name':'stop_context','unit':'structured record','reference':'channels/stop_context.json'},
     {'name':'halt_timing','unit':'structured record','reference':'channels/halt_timing.jsonl'}],
   'source_evidence_hashes':sources,'capture_evidence_sha256':sources['capture/evidence.jsonl'],
   'realized_observables':{}}
 result=physical_result(attempt,result);write_result(attempt,result)
 output.write_text(json.dumps({'format':'worker-c331230-stop-reference-saved-analysis','case_id':case,
   'observation':value,'measurements':{'stop_line_halt_observation':measure_stop_line_halt(attempt,report)} if expected=='marked_stop_line' else {'first_view_halt_observation':measure_first_view_halt(attempt,report)},
   'source_sha256':sources,'physical_acceptance_claimed':False,
   'legal_acceptance_claimed':False},indent=2)+'\n')
 return value
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(finalize(a.attempt,a.output)))
