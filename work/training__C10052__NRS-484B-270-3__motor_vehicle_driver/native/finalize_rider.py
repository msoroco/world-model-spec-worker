"""Saved-only rider conflict diagnostic for exact C10052 case bundles."""
import argparse
import json
from pathlib import Path

from finalize import verify_original_joins, video_frames, rows, sha
from measure_rider_native import measure as measure_original
from measure_rider_yield import measure as measure_synthetic


def derive_channels(attempt, description, motion, rider_rows, mapping):
    """Produce derived recording rows from retained raw source rows at save time."""
    geometry = json.loads((attempt/'road_geometry.json').read_text())
    evidence = rows(attempt/'capture/evidence.jsonl')
    if len(evidence) != len(motion):
        raise ValueError('Original pedestrian source coverage differs')
    channels = attempt/'channels'
    channels.mkdir(exist_ok=True)
    for item in description['channels']:
        name = item['name']
        values = []
        for ego, rider, frame, observed in zip(
                motion, rider_rows, mapping, evidence, strict=True):
            if name in ('st.bicycle_lane_or_path', 'st.driveway_or_alley_entrance'):
                value = geometry
            elif name == 'rel.occupies':
                value = ego['native_body_xy_m']
            elif name == 'kin.extent':
                value = {'body_xy_m': ego['native_body_xy_m']}
            elif name == 'kin.position':
                value = ego['native_center_xy_m']
            elif name == 'ego_speed':
                value = ego['speed_mps']
            elif name == 'drv.standing_or_parked':
                value = {'observed_speed_mps': ego['speed_mps']}
            elif name == 'ru.pedestrian':
                pedestrians = [person for person in observed.get(
                    'original_observations', {}).get('participants', [])
                    if person.get('blueprint', '').startswith('walker.pedestrian.')]
                if len(pedestrians) != 1:
                    raise ValueError('Missing required pedestrian source')
                person = pedestrians[0]
                value = {'native_actor_id': person['actor_id'],
                         'native_body_vertices_m': person['body_vertices_m'],
                         'source_frame': observed['original_frame']}
            elif name.startswith('ru.') and name[3:] in (
                    'bicycle', 'electric_bicycle', 'electric_scooter'):
                value = {'native_actor_id': rider['rider_actor_id'],
                         'native_body_xy_m': rider['rider_body_xy'],
                         'synthetic_diagnostic': True}
            elif name == 'exception_context':
                value = {'source': 'exception_context.json',
                         'observed_exception_status': 'unresolved'}
            elif name == 'native_body_pose_control':
                value = ego
            elif name == 'camera_frame_join':
                value = frame
            else:
                raise ValueError('No retained source mapping for rider channel: '+name)
            values.append({'time_s': ego['time_s'], 'value': value})
        (channels/(name+'.jsonl')).write_text(''.join(
            json.dumps(row, allow_nan=False)+'\n' for row in values))


def finalize(attempt, output):
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior saved rider result; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    case_id=config['case_id']
    rider_type,response=config['case_suffix'].removeprefix('rider_').rsplit('_',1)
    if rider_type!=config.get('rider_type') or response!=config.get('rider_response'):
        raise ValueError('Exact rider case identity differs')
    if round(config['duration_s']*config['rate_hz'])!=480:
        raise ValueError('Expected original 480-frame attempt')
    original=verify_original_joins(attempt,480)
    source_path=attempt/'rider-source-manifest.json'
    if not source_path.is_file():
        raise ValueError('Missing required source: rider-source-manifest.json')
    source=json.loads(source_path.read_text())
    if source.get('rider_type')!=rider_type:
        raise ValueError('Exact rider source type differs')
    rider_rows=rows(attempt/'rider_native_samples.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if len(rider_rows)!=480:
        raise ValueError('Original rider rows incomplete')
    for rider,ego,frame in zip(rider_rows,motion,mapping):
        if (rider.get('native_frame')!=frame['native_frame'] or
            rider.get('time_s')!=frame['time_s'] or
            rider.get('ego_body_xy')!=ego['native_body_xy_m'] or
            rider.get('ego_speed_mps')!=ego['speed_mps'] or
            rider.get('ego_native_road_id')!=ego['native_road_id']):
            raise ValueError('Original rider/ego body or frame join differs')
    if source.get('source_kind')=='original_native':
        measured=measure_original(attempt)
    elif source.get('source_kind')=='synthetic_native_shaped_diagnostic':
        measured=measure_synthetic(attempt/'rider_native_samples.jsonl',
            attempt/'rider_geometry.json',source_path)
    else:
        raise ValueError('Unrecognized rider source scope')
    videos=[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(count!=480 for count in counts.values()):
        raise ValueError('Original camera frame count differs')
    description=config['recording_description']
    derive_channels(attempt, description, motion, rider_rows, mapping)
    recording=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording.append({'name':channel['name'],'unit':channel['unit'],
                          'reference':reference})
    for context in description['context_inputs']:
        reference='exception_context.json' if context['name']=='requested_exception_context' else 'context.json'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording.append({'name':context['name'],'unit':context['unit'],'reference':reference})
    requested=response=='clear'
    observed=measured['ego_entered_after_rider_cleared']
    scope=source['source_kind']
    result={'case_id':case_id,
        'measured_values':{'rider_clearance_s':measured['clearance_s'],
            'simultaneous_conflict_frames':measured['simultaneous_conflict_frames'],
            'ego_entered_after_rider_cleared':observed},
        'target_checks':[{'target':'ego enters shared conflict only after rider clears',
            'requested':requested,'measured':observed,
            'method':'saved source-hashed original Native ego/rider full-body conflict join',
            'tolerance':'20 Hz sample resolution; exact boolean comparison',
            'matched':observed==requested,'physical_cause_confirmed':False,
            'cause_evidence':['rider_native_samples.jsonl','rider_geometry.json',
                              'rider-source-manifest.json']}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':True,
        'termination_reason':'full source duration retained',
        'physical_failure_flags':['rider_asset_facility_priority_and_original_pixels_unverified'],
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':recording,
        'realized_observables':{'rider_clearance_s':{'value':measured['clearance_s'],
            'unit':'s','method':'saved full-body conflict occupancy timing',
            'time_window':'entire 24 s','statistic':'last rider to first ego conflict entry',
            'reference':'rider_native_samples.jsonl','sample_window_s':[0,24]}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10052-saved-rider-conflict-diagnostic-v1','case_id':case_id,
        'candidate_id':config['candidate_id'],
        'measurements':{'rider_conflict_observation':{'method':'source_hashed_full_body_conflict',
            'value':measured,'sources':measured['source_sha256']}},
        'original_joins':original,'video_frames':counts,'source_scope':scope,
        'legal_priority_confirmed':False,'accepted':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()
