"""Saved-only C215286 result from retained original reverse/crosswalk sources."""
import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_reverse import analyze

ASSIGNMENT='testing__C215286__NRS-484B-113-2__motor_vehicle_driver'
OVER=ASSIGNMENT+'__reverse_over_crosswalk'
SHORT=ASSIGNMENT+'__reverse_stops_before_crosswalk'
CAMERAS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_reverse_crosswalk(report):
 return {'reverse_body_on_or_over_crosswalk':report['reverse_body_on_or_over_crosswalk'],
         'reverse_body_fully_over_crosswalk':report['reverse_body_fully_over_crosswalk'],
         'backward_motion_observed':report['backward_motion_observed']}


def finalize(attempt,output):
 from worker_exchange.native_output import physical_result,write_result
 attempt,output=Path(attempt),Path(output)
 if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
  raise ValueError('Retain prior finalization; use a fresh attempt')
 for name in ('config.json','crosswalk_context.json','site_packet.json',
              'reverse_history.jsonl','video_frames.jsonl','trace.jsonl',
              'capture/evidence.jsonl',*CAMERAS):
  if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
 config=json.loads((attempt/'config.json').read_text())
 if config.get('selected_case_id') not in (OVER,SHORT):
  raise ValueError('Exact C215286 selected case required')
 description=config.get('recording_description')
 if not isinstance(description,dict) or not description.get('channels'):
  raise ValueError('Selected recording description required')
 report=analyze(attempt)
 expected=config['selected_case_id']==OVER
 observed=report['reverse_body_on_or_over_crosswalk']
 channel_dir=attempt/'channels';channel_dir.mkdir()
 extract={
  'native_reverse':lambda sample:sample['native_reverse'],
  'backward_motion':lambda sample:sample['observed_backward_motion'],
  'crosswalk_overlap':lambda sample:sample['body_on_or_over_crosswalk'],
 }
 evidence=[]
 for name,fn in extract.items():
  path=channel_dir/(name+'.jsonl')
  with path.open('x') as stream:
   for sample in report['samples']:
    stream.write(json.dumps({'original_frame':sample['frame'],
                             'time_s':sample['time_s'],'value':fn(sample)},
                            separators=(',',':'))+'\n')
  evidence.append({'name':name,'unit':'boolean','reference':'channels/'+path.name})
 context={'crosswalk_context':json.loads((attempt/'crosswalk_context.json').read_text())}
 (channel_dir/'crosswalk_context.json').write_text(json.dumps(context,indent=2)+'\n')
 evidence.append({'name':'crosswalk_context','unit':'structured record',
                  'reference':'channels/crosswalk_context.json'})
 check={'target':'backward complete-body crosswalk overlap',
        'requested':expected,'measured':observed,
        'method':'original reverse readback at both interval ends, backward complete-body displacement and sourced crosswalk polygon',
        'tolerance':0,'matched':observed==expected and report['backward_motion_observed'],
        'physical_cause_confirmed':False,
        'cause_evidence':['reverse_history.jsonl','video_frames.jsonl',
                          'crosswalk_context.json','site_packet.json']}
 result={'case_id':config['selected_case_id'],
         'measured_values':{'reverse_body_on_or_over_crosswalk':observed,
                            'reverse_body_fully_over_crosswalk':report['reverse_body_fully_over_crosswalk'],
                            'backward_motion_observed':report['backward_motion_observed']},
         'target_checks':[check],'setup_confirmed':False,'behavior_attempted':False,
         'maneuver_completed':False,
         'termination_reason':'saved original-source analysis; legal and physical review remain separate',
         'physical_failure_flags':['actual marked crosswalk and residence-district status require independent review',
                                   'source-camera visibility requires full decode and pixel review'],
         'trace_reference':'trace.jsonl','video_references':list(CAMERAS),
         'video_frame_map_reference':'video_frames.jsonl',
         'recording_description':description,'recording_evidence':evidence,
         'source_evidence_hashes':report['sources'],
         'capture_evidence_sha256':_sha(attempt/'capture/evidence.jsonl'),
         'realized_observables':{}}
 result=physical_result(attempt,result)
 measurement_sources={name:report['sources'][name] for name in
                      ('crosswalk_context.json','reverse_history.jsonl','video_frames.jsonl')}
 measurements={'reverse_crosswalk':{
  'method':'measure_reverse_crosswalk','value':measure_reverse_crosswalk(report),
  'sources':measurement_sources}}
 analysis={'format':'worker-reverse-crosswalk-analysis',
           'case_id':config['selected_case_id'],'measurements':measurements,
           'source_report':report,'source_hashes':report['sources'],
           'physical_checks':result['physical_checks'],'legal_verdict_asserted':False}
 write_result(attempt,result)
 output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
 return analysis


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
 parser.add_argument('--output',required=True);args=parser.parse_args()
 finalize(args.attempt,args.output)


if __name__=='__main__':main()
