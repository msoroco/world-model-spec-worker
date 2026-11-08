"""Saved-only traffic-conflict diagnostic for exact C10052 exception C bundles."""
import argparse
import json
from pathlib import Path

from exception_c_engineering import body,measure,overlap,policy,BIKE_BOUNDS
from finalize import verify_original_joins,video_frames,rows,sha

BIKE_POLYGON=[[-15,-5],[20,-5],[20,-3],[-15,-3]]

def original_measure(attempt,source,samples,response):
    if source.get('source_kind')!='original_native' or source.get('accepted') is not False:
        raise ValueError('Original conflict source scope missing')
    if source.get('samples_sha256')!=sha(attempt/'exception_c_native_samples.jsonl') or \
       source.get('road_geometry_sha256')!=sha(attempt/'road_geometry.json'):
        raise ValueError('Original conflict source bytes changed')
    actor=source.get('conflict_actor_id')
    blueprint=source.get('conflict_actor_blueprint')
    if response=='avoid' and (type(actor) is not int or not str(blueprint).startswith('vehicle.')):
        raise ValueError('Original other-traffic actor class missing')
    if response=='no_conflict' and (actor is not None or blueprint is not None):
        raise ValueError('No-conflict original actor present')
    road=json.loads((attempt/'road_geometry.json').read_text())
    survey=road.get('native_lane_survey',{})
    if survey.get('bicycle_facility',{}).get('lane_id')!=-2 or \
       survey.get('driving_approach',{}).get('lane_id')!=-1:
        raise ValueError('Native driving/bicycle lane readback missing')
    active=[];bike=[];actual=[];straight=[]
    for index,row in enumerate(samples):
        if row.get('conflict_actor_active'):
            if row.get('conflict_actor_id')!=actor or row.get('conflict_actor_blueprint')!=blueprint:
                raise ValueError('Original actor identity changed')
            active.append(index)
            actor_body=row['conflict_actor_body_xy']
            if overlap(row['ego_body_xy'],actor_body)>.001:actual.append(index)
            if overlap(body(row['ego_center_xy'][0],-1.5),actor_body)>.001:straight.append(index)
        elif row.get('conflict_actor_id') is not None or row.get('conflict_actor_body_xy'):
            raise ValueError('Inactive original actor retained body')
        if overlap(row['ego_body_xy'],BIKE_POLYGON)>.001:bike.append(index)
        if row.get('ego_native_road_id') not in (1,2) or row.get('ego_native_lane_id') not in (-1,-2):
            raise ValueError('Original ego lane identity changed')
    return {'active_conflict_actor_frames':len(active),
        'counterfactual_straight_collision_frames':len(straight),
        'actual_collision_frames':len(actual),
        'bicycle_lane_occupied_frames':len(bike),
        'actor_original_native_verified':bool(active),
        'legal_exception_verified':False,'accepted':False,
        'source_sha256':{'samples':sha(attempt/'exception_c_native_samples.jsonl'),
                         'road':sha(attempt/'road_geometry.json')}}

def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior conflict result; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    suffix=config['case_suffix'];response=suffix.removeprefix('exception_c_')
    if response not in ('avoid','no_conflict') or config['case_id'].rsplit('__',1)[-1]!=suffix:
        raise ValueError('Exact conflict case identity differs')
    if round(config['duration_s']*config['rate_hz'])!=480:
        raise ValueError('Expected 480-frame source attempt')
    original=verify_original_joins(attempt,480)
    samples=rows(attempt/'exception_c_native_samples.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if len(samples)!=480:raise ValueError('Conflict actor source rows incomplete')
    for row,ego,frame in zip(samples,motion,mapping):
        if row['native_frame']!=frame['native_frame'] or \
           abs(row['time_s']-frame['time_s'])>1e-4 or \
           row['ego_body_xy']!=ego['native_body_xy_m']:
            raise ValueError('Conflict/ego original body or frame join differs')
    source=json.loads((attempt/'exception-c-source-manifest.json').read_text())
    if source.get('source_kind')=='original_native':
        measured=original_measure(attempt,source,samples,response)
    elif source.get('source_kind')=='synthetic_cpu_fixture':
        if source.get('samples_sha256')!=sha(attempt/'exception_c_native_samples.jsonl'):
            raise ValueError('Synthetic conflict source hash differs')
        measured=measure(samples,policy(response,config['candidate_id']))
    else:raise ValueError('Unknown conflict source scope')
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(count!=480 for count in counts.values()):
        raise ValueError('Original camera frame count differs')
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
                           'actual_collision_frames':measured['actual_collision_frames']},
        'target_checks':[{'target':'other-traffic conflict avoidance geometry',
            'requested':response,'measured':{'actor_frames':measured['active_conflict_actor_frames'],
                'bicycle_lane_frames':count,'actual_collision_frames':measured['actual_collision_frames']},
            'method':'saved source-hashed actor and ego body join',
            'tolerance':'source observation only','matched':False,
            'physical_cause_confirmed':False,
            'cause_evidence':['exception_c_native_samples.jsonl','exception-c-source-manifest.json']}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full source duration retained',
        'physical_failure_flags':['original_conflict_necessity_camera_pixels_and_legal_exception_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':recording,
        'realized_observables':{'bicycle_lane_occupied_frames':{'value':count,
            'unit':'frames','method':'saved ego full-body bicycle-lane overlap',
            'time_window':'entire 24 s','statistic':'occupied frames',
            'reference':'exception_c_native_samples.jsonl','sample_window_s':[0,24]}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10052-saved-exception-c-diagnostic-v1',
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
