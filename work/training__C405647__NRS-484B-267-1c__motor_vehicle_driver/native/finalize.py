"""Finalize source-hashed saved emergency passage evidence without legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

AID = 'training__C405647__NRS-484B-267-1c__motor_vehicle_driver'
SOURCES = ('context-scope.json', 'actor-frames.jsonl', 'trace.jsonl',
           'video_frames.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(actors, scope):
    kinds = {row.get('source_kind') for row in actors}
    if kinds != {scope.get('source_kind')} or kinds not in ({'synthetic_cpu'}, {'original_native'}):
        raise ValueError('Saved actor source kind differs from context source')
    if len(actors) != 600:
        raise ValueError('Full 600-frame actor source required')
    first_motion = None
    first_center = None
    first_whole = None
    for index, row in enumerate(actors):
        if (row.get('frame') != index or row.get('video_frame') != index or
                abs(row.get('time_s', -1) - index / 20) > 1e-4):
            raise ValueError('Saved actor frame or time join differs')
        subject, approach = row.get('subject'), row.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('Both saved actor sources required')
        for actor in (subject, approach):
            center, body = actor.get('center_xy_m'), actor.get('body_xy_m')
            if (not isinstance(center, list) or len(center) != 2 or
                    not isinstance(body, list) or len(body) < 4 or
                    any(not isinstance(point, list) or len(point) != 2 or
                        any(not isinstance(x, (int, float)) for x in point)
                        for point in body)):
                raise ValueError('Original full body footprint missing')
        if row.get('lamp_request') is not True:
            raise ValueError('Original requested lamp channel missing')
        if row.get('approach_kind_request') != scope.get('approach_kind_request') or \
                row.get('officer_direction_request') != scope.get('officer_direction_request'):
            raise ValueError('Approach alternative or officer direction source differs')
        if first_motion is None and subject.get('speed_mps', 0) > 0.05:
            first_motion = index
        if first_center is None and approach['center_xy_m'][1] > subject['center_xy_m'][1]:
            first_center = index
        if first_whole is None and min(p[1] for p in approach['body_xy_m']) > \
                max(p[1] for p in subject['body_xy_m']):
            first_whole = index
    if any(value is None for value in (first_motion, first_center, first_whole)):
        raise ValueError('Saved full passage or ego release span missing')
    return {'source_kind': scope['source_kind'],
            'first_ego_motion_frame': first_motion,
            'first_center_passage_frame': first_center,
            'first_whole_body_passage_frame': first_whole,
            'remained_stopped_until_whole_body_passed': first_motion > first_whole,
            'approach_kind_request': scope['approach_kind_request'],
            'officer_direction_request': scope['officer_direction_request'],
            'authority_verified': bool(scope.get('original_authority_verified')),
            'qualifying_lamps_verified': bool(scope.get('qualifying_lamps_verified')),
            'officer_direction_verified': bool(scope.get('original_officer_direction_verified')),
            'physical_completion_verified': False}


def measure_wait(scope, measurement):
    return {'first_ego_motion_frame': measurement['first_ego_motion_frame'],
            'first_whole_body_passage_frame': measurement['first_whole_body_passage_frame'],
            'remained_stopped_until_whole_body_passed':
                measurement['remained_stopped_until_whole_body_passed'],
            'source_kind': scope['source_kind']}


def measure_officer(scope, measurement):
    return {'officer_direction_request': scope['officer_direction_request'],
            'original_officer_direction_verified':
                bool(scope.get('original_officer_direction_verified')),
            'first_ego_motion_frame': measurement['first_ego_motion_frame'],
            'source_kind': scope['source_kind']}


def measure_official(scope, measurement):
    return {'approach_kind_request': scope['approach_kind_request'],
            'original_authority_verified': bool(scope.get('original_authority_verified')),
            'qualifying_lamps_verified': bool(scope.get('qualifying_lamps_verified')),
            'first_whole_body_passage_frame': measurement['first_whole_body_passage_frame'],
            'source_kind': scope['source_kind']}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    scope = json.loads((attempt / 'context-scope.json').read_text())
    suffix = scope.get('case_suffix')
    case_id = AID + '__' + str(suffix)
    if (suffix not in ('probe_a', 'probe_b', 'exception_1_1', 'exception_1_2',
                       'official_1', 'official_2') or
            config.get('case_id') != case_id or construction.get('case_id') != case_id or
            config.get('candidate_id') not in ('primary', 'fallback1', 'fallback2')):
        raise ValueError('Exact saved case or candidate differs')
    for name, expected in scope.get('native_source_hashes', {}).items():
        if not (attempt / name).is_file() or sha(attempt / name) != expected:
            raise ValueError('Saved Native source hash differs: ' + name)
    actor = rows(attempt / 'actor-frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    if len(actor) != len(trace) or len(trace) != len(mapping) or len(mapping) != 600:
        raise ValueError('Saved actor/trace/video frame counts differ')
    for index, (a, t, m) in enumerate(zip(actor, trace, mapping)):
        if (m.get('video_frame') != index or m.get('native_frame') != a.get('native_frame') or
                m.get('carla_frame') != a.get('native_frame') or
                t.get('frame') != a.get('native_frame') or
                abs(t.get('time_s', -1) - m.get('time_s', -2)) > 1e-6):
            raise ValueError('Saved actor/trace/video frame join differs')
    measurement = measure(actor, scope)
    expected_wait = suffix in ('probe_a', 'official_1')
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for a, m in zip(actor, mapping):
                subject, approach = a['subject'], a['approach']
                values = {
                    'drv.responding_emergency': scope['approach_kind_request'],
                    'drv.stopped': subject['speed_mps'] <= .05,
                    'rel.occupies': {'road_id': 1, 'lane_id': -2},
                    'kin.position': subject['center_xy_m'],
                    'rel.ahead_behind_in_lane': approach['center_xy_m'][1] - subject['center_xy_m'][1],
                    'drv.cleared_line': min(p[1] for p in approach['body_xy_m']) >
                                        max(p[1] for p in subject['body_xy_m']),
                    'kin.velocity': subject['speed_mps'],
                    'approach_kind': scope['approach_kind_request'],
                    'qualifying_lamp_pixels': bool(scope.get('qualifying_lamps_verified')),
                    'officer_direction': scope['officer_direction_request'],
                    'subject_body': subject['body_xy_m'],
                    'emergency_body': approach['body_xy_m'],
                    'video_frame_join': {'native_frame': m['native_frame'],
                                         'video_frame': m['video_frame']},
                    'rel.same_direction': True,
                    'rel.surface_gap': max(0., approach['center_xy_m'][1] -
                                           subject['center_xy_m'][1] - 4.5),
                }
                stream.write(json.dumps({'time_s': m['time_s'], 'value': values[name]}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    measurements = {}
    method_by_suffix = {'probe_a': ('wait_until_passed', measure_wait),
                        'probe_b': ('wait_until_passed', measure_wait),
                        'exception_1_1': ('officer_direction_exception', measure_officer),
                        'exception_1_2': ('officer_direction_exception', measure_officer),
                        'official_1': ('official_vehicle_wait', measure_official),
                        'official_2': ('official_vehicle_wait', measure_official)}
    key, method = method_by_suffix[suffix]
    measurements[key] = {'method': method.__name__, 'value': method(scope, measurement),
                         'sources': {name: sha(attempt / name)
                                     for name in ('context-scope.json', 'actor-frames.jsonl')}}
    report = {'format': 'c405647-1c-saved-analysis-v1', 'case_id': case_id,
              'measurements': measurements, 'whole_body_timing': measurement,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = {'case_id': case_id, 'measured_values': measurement,
              'target_checks': [{'target': 'remain stopped until whole approaching body passes',
                                 'requested': expected_wait,
                                 'measured': measurement['remained_stopped_until_whole_body_passed'],
                                 'method': 'saved original body footprint and speed time join',
                                 'tolerance': 0,
                                 'matched': expected_wait == measurement['remained_stopped_until_whole_body_passed'],
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full diagnostic 600-frame saved window',
              'physical_failure_flags': ['Original authority, qualifying lamps and Native behavior unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if measurement['source_kind'] == 'synthetic_cpu'
                                 else 'original_native', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
