"""Saved-only C10052 pedestrian timing diagnostic for exact bundles.

The result is always unaccepted. Original source checks do not decide the
statutory practicable-return or right-of-way questions.
"""
import argparse
import json
from pathlib import Path

from finalize import verify_original_joins, video_frames, rows, sha
from measure_facility import overlap_area
from pedestrian_engineering import CONFLICT_BOUNDS_M, measure as measure_synthetic


def measured_original(attempt, source):
    sample_path=attempt/'pedestrian_native_samples.jsonl'
    geometry_path=attempt/'pedestrian_geometry.json'
    road_path=attempt/'road_geometry.json'
    if source.get('source_kind')!='original_native' or source.get('accepted') is not False:
        raise ValueError('Original pedestrian source scope missing')
    if not str(source.get('pedestrian_blueprint','')).startswith('walker.pedestrian.'):
        raise ValueError('Original pedestrian actor class missing')
    for key,path in (('samples_sha256',sample_path),('geometry_sha256',geometry_path),
                     ('road_geometry_sha256',road_path)):
        if source.get(key)!=sha(path):
            raise ValueError('Original pedestrian source hash differs: '+key)
    geometry=json.loads(geometry_path.read_text())
    road=json.loads(road_path.read_text())
    if geometry.get('native_map_sha256')!=road.get('native_map_sha256'):
        raise ValueError('Original pedestrian map survey differs')
    survey=road.get('native_lane_survey',{})
    if survey.get('sidewalk',{}).get('lane_id')!=-3 or survey.get('bicycle_facility',{}).get('lane_id')!=-2:
        raise ValueError('Native sidewalk or facility lane readback missing')
    source_rows=rows(sample_path)
    if len(source_rows)!=480:
        raise ValueError('Original pedestrian rows incomplete')
    if any(row.get('pedestrian_actor_id')!=source.get('pedestrian_actor_id') or
           row.get('pedestrian_blueprint')!=source.get('pedestrian_blueprint') or
           row.get('pedestrian_native_road_id')!=1 or
           row.get('pedestrian_native_lane_id') not in (-2,-3) or
           len(row.get('sidewalk_obstacle_actor_bodies_xy',[]))!=4 or
           len(row.get('buffer_obstacle_actor_bodies_xy',[]))!=4
           for row in source_rows):
        raise ValueError('Original pedestrian/obstruction identity differs')
    pedestrian=[i for i,row in enumerate(source_rows)
                if overlap_area(row['pedestrian_body_xy'],CONFLICT_BOUNDS_M)>.01]
    ego=[i for i,row in enumerate(source_rows)
         if overlap_area(row['ego_body_xy'],CONFLICT_BOUNDS_M)>.01]
    if not pedestrian or not ego:
        raise ValueError('Original shared conflict region missing')
    simultaneous=len(set(pedestrian)&set(ego))
    return {'first_pedestrian_conflict_frame':source_rows[pedestrian[0]]['native_frame'],
            'last_pedestrian_conflict_frame':source_rows[pedestrian[-1]]['native_frame'],
            'first_ego_conflict_frame':source_rows[ego[0]]['native_frame'],
            'simultaneous_conflict_frames':simultaneous,
            'obstruction_actors_present':True,
            'statutory_pedestrian_qualification_verified':False,
            'practicable_return_verified':False,
            'source_sha256':{'samples':sha(sample_path),'geometry':sha(geometry_path),
                             'road':sha(road_path)},'accepted':False}


def finalize(attempt, output):
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior pedestrian result; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    suffix=config['case_suffix']
    if suffix not in ('pedestrian_clear','pedestrian_conflict') or config['case_id'].rsplit('__',1)[-1]!=suffix:
        raise ValueError('Exact pedestrian case identity differs')
    if round(config['duration_s']*config['rate_hz'])!=480:
        raise ValueError('Expected original 480-frame attempt')
    original=verify_original_joins(attempt,480)
    source_path=attempt/'pedestrian-source-manifest.json'
    source=json.loads(source_path.read_text())
    pedestrian_rows=rows(attempt/'pedestrian_native_samples.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if len(pedestrian_rows)!=480:
        raise ValueError('Pedestrian source rows incomplete')
    for pedestrian,ego,frame in zip(pedestrian_rows,motion,mapping):
        if (pedestrian.get('native_frame')!=frame['native_frame'] or
            abs(pedestrian.get('time_s',-1)-frame['time_s'])>1e-4 or
            pedestrian.get('ego_body_xy')!=ego['native_body_xy_m']):
            raise ValueError('Pedestrian/ego original body or frame join differs')
    if source.get('source_kind')=='original_native':
        measured=measured_original(attempt,source)
    elif source.get('source_kind')=='synthetic_cpu_fixture':
        if source.get('samples_sha256')!=sha(attempt/'pedestrian_native_samples.jsonl'):
            raise ValueError('Synthetic pedestrian source hash differs')
        policy={'capture_frames':480,'case_suffix':suffix,
                'candidate_id':config['candidate_id']}
        measured=measure_synthetic(pedestrian_rows,policy)
    else:
        raise ValueError('Unrecognized pedestrian source scope')
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(count!=480 for count in counts.values()):
        raise ValueError('Original camera frame count differs')
    description=config['recording_description']
    recording=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        reference='exception_context.json' if context['name']=='requested_exception_context' else 'context.json'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording.append({'name':context['name'],'unit':context['unit'],'reference':reference})
    simultaneous=measured['simultaneous_conflict_frames']
    requested=0 if suffix=='pedestrian_clear' else 20
    matched=simultaneous==requested
    result={'case_id':config['case_id'],
        'measured_values':{'simultaneous_conflict_frames':simultaneous},
        'target_checks':[{'target':'ego/pedestrian shared conflict occupancy timing',
            'requested':requested,'measured':simultaneous,
            'method':'saved source-hashed full-body conflict join',
            'tolerance':'exact 20 Hz frame count','matched':matched,
            'physical_cause_confirmed':False,
            'cause_evidence':['pedestrian_native_samples.jsonl','pedestrian_geometry.json',
                              'pedestrian-source-manifest.json']}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full source duration retained',
        'physical_failure_flags':['pedestrian_qualification_facility_priority_and_pixels_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':recording,
        'realized_observables':{'simultaneous_conflict_frames':{'value':simultaneous,
            'unit':'frames','method':'saved full-body conflict occupancy',
            'time_window':'entire 24 s','statistic':'simultaneous frames',
            'reference':'pedestrian_native_samples.jsonl','sample_window_s':[0,24]}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10052-saved-pedestrian-diagnostic-v1',
        'case_id':config['case_id'],'candidate_id':config['candidate_id'],
        'measurements':measured,'original_joins':original,
        'video_frames':counts,'source_scope':source['source_kind'],
        'legal_priority_confirmed':False,'accepted':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()
