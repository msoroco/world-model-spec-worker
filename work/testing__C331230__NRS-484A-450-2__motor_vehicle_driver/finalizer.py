"""Saved-only crosswalk stop measurements from original joined Native sources."""
import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_stop_measurements import analyze
from runner import CAMERAS,CASE,load_config

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def finalize(attempt,output):
 from worker_exchange.native_output import physical_result,write_result
 attempt=Path(attempt);output=Path(output)
 if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
  raise ValueError('Use a fresh saved-source attempt')
 cfg,site=load_config(attempt)
 required=('approach_context.json','stop_history.jsonl','video_frames.jsonl',
           'trace.jsonl','capture/evidence.jsonl',*(name+'.mkv' for name in CAMERAS))
 for name in required:
  if not (attempt/name).is_file():raise ValueError('Missing original source: '+name)
 report=analyze(attempt)
 ctx=json.loads((attempt/'approach_context.json').read_text())
 if ctx.get('physical_acceptance_claimed') is not False or ctx['crosswalk_origin']!='marked':
  raise ValueError('Original crosswalk context differs')
 sources={name:sha(attempt/name) for name in required}
 measurements={
  'crosswalk_reference':{'value':report['selected_reference'],'method':'source-bound near-side crosswalk geometry',
    'sources':{name:sources[name] for name in ('approach_context.json','stop_history.jsonl')}},
  'halt_ordering':{'value':{'first_halt':report['first_full_halt_before_crosswalk'],
      'first_crosswalk_entry':report['first_crosswalk_entry'],
      'first_intersection_entry':report['first_intersection_entry'],
      'ordered':report['full_halt_before_crosswalk_and_junction_observed']},
    'method':'original complete-body and speed frame join',
    'sources':{name:sources[name] for name in ('approach_context.json','stop_history.jsonl','video_frames.jsonl')}},
  'sign_context':{'value':{'native_stop_sign_id':ctx['native_stop_sign_id'],
       'official_sign_status':'unresolved'},'method':'original stop-sign and approach source',
    'sources':{name:sources[name] for name in ('approach_context.json','stop_history.jsonl')}}}
 channels=attempt/'channels';channels.mkdir()
 write(channels/'stop_context.json',{'case_id':CASE,'measurements':measurements,
       'legal_conclusion':'unresolved'})
 with (channels/'halt_timing.jsonl').open('w') as stream:
  for row in report['samples']:
   stream.write(json.dumps({'time_s':row['time_s'],'value':row},allow_nan=False)+'\n')
 result={'case_id':CASE,'measured_values':{'halt_before_crosswalk_observed':report['full_halt_before_crosswalk_and_junction_observed']},
  'target_checks':[{'target':'complete_halt_before_nearside_crosswalk','requested':True,
      'measured':report['full_halt_before_crosswalk_and_junction_observed'],
      'method':'original complete-body speed and crosswalk geometry',
      'tolerance':0,'matched':report['full_halt_before_crosswalk_and_junction_observed'],
      'physical_cause_confirmed':False,
      'cause_evidence':['approach_context.json','stop_history.jsonl','video_frames.jsonl']}],
  'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
  'termination_reason':'Saved source analysis; independent Native and legal review pending',
  'physical_failure_flags':['proper sign, crosswalk provenance and legal qualification unverified'],
  'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['recording_description'],
  'recording_evidence':[{'name':'stop_context','unit':'structured record','reference':'channels/stop_context.json'},
     {'name':'halt_timing','unit':'structured record','reference':'channels/halt_timing.jsonl'}],
  'source_evidence_hashes':sources,'capture_evidence_sha256':sources['capture/evidence.jsonl'],
  'realized_observables':{}}
 result=physical_result(attempt,result);write_result(attempt,result)
 write(output,{'format':'worker-c331230-saved-analysis','case_id':CASE,
       'measurements':measurements,'physical_acceptance_claimed':False,
       'legal_acceptance_claimed':False})
 return measurements

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True,type=Path)
 p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 print(json.dumps({'measurements':sorted(finalize(a.attempt,a.output)),
       'physical_acceptance_claimed':False}))
