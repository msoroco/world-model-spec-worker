"""Saved-only, unaccepted emergency context diagnostic for C10052."""
import argparse
import json
from pathlib import Path

from finalize import verify_original_joins,video_frames,rows,sha

def overlap(body):
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return max(0,min(max(xs),20)-max(min(xs),-15))*max(0,min(max(ys),-3)-max(min(ys),-5))

def measure(samples,packet,response):
    if len(samples)!=480 or packet.get('format')!='synthetic-incident-packet-v1':
        raise ValueError('Incident source duration or packet changed')
    if packet.get('provenance')!='independent_synthetic_dispatch_fixture':
        raise ValueError('Synthetic incident packet provenance changed')
    if packet.get('incident_id')!='fixture-incident-001':
        raise ValueError('Incident identity changed')
    expected=response=='emergency'
    if packet.get('requested_vehicle_response') is not expected or \
       (packet.get('declared_start_frame'),packet.get('declared_end_frame')) != \
       ((100,240) if expected else (None,None)):
        raise ValueError('Incident interval/response changed')
    active=occupied=joined=0
    for index,row in enumerate(samples):
        event=expected and 100<=index<240
        if row.get('incident_active') is not event or \
           row.get('incident_id') != (packet['incident_id'] if event else None):
            raise ValueError('Incident frame join changed')
        body_overlap=overlap(row['ego_body_xy'])>.001
        active+=event;occupied+=body_overlap;joined+=event and body_overlap
    return {'incident_active_frames':active,'bicycle_lane_occupied_frames':occupied,
            'incident_occupied_frames':joined,'original_emergency_verified':False,
            'legal_exception_verified':False,'accepted':False}

def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior result; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    suffix=config['case_suffix'];response=suffix.removeprefix('exception_f_')
    if response not in ('emergency','routine') or config['case_id'].rsplit('__',1)[-1]!=suffix:
        raise ValueError('Exact emergency case identity differs')
    if config['duration_s']*config['rate_hz']!=480:raise ValueError('Expected 480-frame attempt')
    original=verify_original_joins(attempt,480)
    samples=rows(attempt/'exception_f_native_samples.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if len(samples)!=480:raise ValueError('Incident source rows incomplete')
    for row,ego,frame in zip(samples,motion,mapping):
        if row['native_frame']!=frame['native_frame'] or \
           abs(row['time_s']-frame['time_s'])>1e-4 or \
           row['ego_body_xy']!=ego['native_body_xy_m']:
            raise ValueError('Incident/ego original body or frame join differs')
    source=json.loads((attempt/'exception-f-source-manifest.json').read_text())
    if source.get('source_kind') not in ('original_native','synthetic_cpu_fixture') or \
       source.get('accepted') is not False or \
       source.get('samples_sha256')!=sha(attempt/'exception_f_native_samples.jsonl') or \
       source.get('incident_packet_sha256')!=sha(attempt/'incident-packet.json'):
        raise ValueError('Incident source scope or bytes changed')
    packet=json.loads((attempt/'incident-packet.json').read_text())
    measured=measure(samples,packet,response)
    if source['source_kind']=='original_native':
        road=json.loads((attempt/'road_geometry.json').read_text())
        survey=road.get('native_lane_survey',{})
        if source.get('road_geometry_sha256')!=sha(attempt/'road_geometry.json') or \
           survey.get('bicycle_facility',{}).get('lane_id')!=-2 or \
           survey.get('driving_approach',{}).get('lane_id')!=-1:
            raise ValueError('Original Native lane survey missing')
        if response=='emergency' and (type(source.get('conflict_actor_id')) is not int or
           not str(source.get('conflict_actor_blueprint')).startswith('vehicle.')):
            raise ValueError('Original incident-scene actor missing')
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(count!=480 for count in counts.values()):raise ValueError('Camera frame count differs')
    description=config['recording_description'];recording=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        reference='exception_context.json' if context['name']=='requested_exception_context' else 'context.json'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording.append({'name':context['name'],'unit':context['unit'],'reference':reference})
    count=measured['bicycle_lane_occupied_frames']
    result={'case_id':config['case_id'],
        'measured_values':{'bicycle_lane_occupied_frames':count,
                           'incident_occupied_frames':measured['incident_occupied_frames']},
        'target_checks':[{'target':'source-grounded emergency context during facility occupancy',
            'requested':response,'measured':measured,
            'method':'saved incident packet, frame join and ego full-body overlap',
            'tolerance':'source observation only','matched':False,
            'physical_cause_confirmed':False,
            'cause_evidence':['exception_f_native_samples.jsonl','incident-packet.json']}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full source duration retained',
        'physical_failure_flags':['original_emergency_provenance_and_legal_exception_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':recording,
        'realized_observables':{'bicycle_lane_occupied_frames':{'value':count,
            'unit':'frames','method':'saved ego full-body bicycle-lane overlap',
            'time_window':'entire 24 s','statistic':'occupied frames',
            'reference':'exception_f_native_samples.jsonl','sample_window_s':[0,24]}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10052-saved-exception-f-diagnostic-v1',
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'measurements':measured,'original_joins':original,
            'video_frames':counts,'source_scope':source['source_kind'],
            'legal_exception_confirmed':False,'accepted':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))

if __name__=='__main__':main()
