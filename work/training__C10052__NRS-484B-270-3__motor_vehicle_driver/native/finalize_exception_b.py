"""Saved-only unaccepted disabled-vehicle engineering diagnostic."""
import argparse
import json
from pathlib import Path
from exception_b_engineering import measure,policy,area,BIKE
from finalize import verify_original_joins,video_frames,rows,sha

def original_measure(attempt,source,samples,state,config):
    if source.get('source_kind')!='original_native' or source.get('accepted') is not False:
        raise ValueError('Original source scope missing')
    for field,name in (('samples_sha256','exception_b_native_samples.jsonl'),
        ('road_geometry_sha256','road_geometry.json'),('fault_application_sha256','fault-application.json')):
        if source.get(field)!=sha(attempt/name):raise ValueError('Original disabled source changed: '+name)
    fault=json.loads((attempt/'fault-application.json').read_text())
    if fault['fault_commanded']!=(state=='faulted') or fault['legal_disability_verified'] is not False:
        raise ValueError('Fault application scope changed')
    if state=='faulted' and not fault['fault_readback']:
        raise ValueError('Original fault did not read back')
    p=policy(state,config['candidate_id'])
    test=samples[100:p['propulsion_test_end_frame']]
    if len(test)<60 or any(r['throttle_command']<.4 or r['brake_command']!=0 for r in test):
        raise ValueError('Original propulsion test command missing')
    if any((r['powertrain_readback']['max_rpm']<=1.1)!=(state=='faulted') for r in test):
        raise ValueError('Original powertrain readback differs')
    movement=((test[-1]['ego_center_xy'][0]-test[0]['ego_center_xy'][0])**2+
              (test[-1]['ego_center_xy'][1]-test[0]['ego_center_xy'][1])**2)**.5
    occupancy=sum(area(r['ego_body_xy'],BIKE)>0 for r in samples[100:240])
    if occupancy==0:raise ValueError('No original bicycle-lane occupancy')
    return {'original_fault_readback':state=='faulted',
        'propulsion_test_frames':len(test),'propulsion_test_displacement_m':round(movement,4),
        'bicycle_lane_occupied_frames_100_240':occupancy,
        'physical_immobilization_observed':state=='faulted' and movement<.25,
        'legal_disability_verified':False,'legal_exception_verified':False,'accepted':False}

def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():raise ValueError('Use a fresh result path')
    config=json.loads((attempt/'config.json').read_text());suffix=config['case_suffix']
    state=suffix.removeprefix('exception_b_')
    if state not in ('faulted','healthy') or config['case_id'].rsplit('__',1)[-1]!=suffix:
        raise ValueError('Exact disabled-vehicle case identity differs')
    if config['duration_s']*config['rate_hz']!=480:raise ValueError('Capture duration changed')
    original=verify_original_joins(attempt,480)
    samples=rows(attempt/'exception_b_native_samples.jsonl')
    motion=rows(attempt/'native_samples.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if len(samples)!=480:raise ValueError('Disabled source rows incomplete')
    for row,ego,frame in zip(samples,motion,mapping):
        if row['native_frame']!=frame['native_frame'] or abs(row['time_s']-frame['time_s'])>1e-4 or row['ego_body_xy']!=ego['native_body_xy_m']:
            raise ValueError('Disabled source/ego original join changed')
    source=json.loads((attempt/'exception-b-source-manifest.json').read_text())
    if source.get('source_kind')=='original_native':
        measured=original_measure(attempt,source,samples,state,config)
    elif source.get('source_kind')=='synthetic_cpu_fixture':
        if source.get('samples_sha256')!=sha(attempt/'exception_b_native_samples.jsonl'):
            raise ValueError('Synthetic disabled source hash differs')
        measured=measure(samples,policy(state,config['candidate_id']))
    else:raise ValueError('Unknown disabled source scope')
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(count!=480 for count in counts.values()):raise ValueError('Source video frame count changed')
    description=config['recording_description'];recording=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():raise ValueError('Missing source channel: '+reference)
        recording.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        reference='exception_context.json' if context['name']=='requested_exception_context' else 'context.json'
        if not (attempt/reference).is_file():raise ValueError('Missing context: '+reference)
        recording.append({'name':context['name'],'unit':context['unit'],'reference':reference})
    count=measured['bicycle_lane_occupied_frames_100_240']
    result={'case_id':config['case_id'],
        'measured_values':{'bicycle_lane_occupied_frames_100_240':count,
            'propulsion_test_displacement_m':measured['propulsion_test_displacement_m']},
        'target_checks':[{'target':'source-bound disabled-vehicle response',
            'requested':state,'measured':measured,'method':'saved source-hashed drivetrain, command and body join',
            'tolerance':'engineering diagnostic only','matched':False,
            'physical_cause_confirmed':False,
            'cause_evidence':['exception_b_native_samples.jsonl','exception-b-source-manifest.json'],
            'legal_disability_confirmed':False}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full source duration retained',
        'physical_failure_flags':['legal_disability_operating_or_parking_and_facility_designation_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':recording,
        'realized_observables':{'bicycle_lane_occupied_frames_100_240':{'value':count,
            'unit':'frames','method':'saved ego full-body bicycle-lane overlap',
            'time_window':'frame 100 to 239','statistic':'occupied frames',
            'reference':'exception_b_native_samples.jsonl','sample_window_s':[5,12]}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10052-saved-exception-b-diagnostic-v1','case_id':config['case_id'],
        'candidate_id':config['candidate_id'],'measurements':measured,
        'original_joins':original,'video_frames':counts,
        'source_scope':source['source_kind'],'legal_exception_confirmed':False,'accepted':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
if __name__=='__main__':main()
