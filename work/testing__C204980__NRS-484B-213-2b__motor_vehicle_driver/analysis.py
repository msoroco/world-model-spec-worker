"""Saved-only source-bound railroad crossing finalizer; no legal evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rail_left import CASES, measure_original

ASSIGNMENT = 'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def load_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def source_inventory(attempt, case_id, expected_frames):
    attempt = Path(attempt)
    manifest = attempt / 'source-hashes.json'
    if not manifest.is_file():
        manifest = attempt / 'original-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original rail source manifest missing')
    hashes = load_json(manifest)
    required = ('rail-frames.jsonl', 'rail-context.json', 'frame-map.json',
                *(name + '.mkv' for name in CAMERAS),
                *(f'reviewed-{kind}.json' for kind in
                  ('highway', 'railroad', 'crossing', 'vehicle')))
    if not set(required) <= set(hashes):
        raise ValueError('original rail source inventory incomplete')
    for name, digest in hashes.items():
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        if path.is_symlink() or sha(path) != digest:
            raise ValueError('original rail source changed: ' + name)
    context = load_json(attempt / 'rail-context.json')
    if context.get('case_id') != case_id or context.get('physical_acceptance_claimed') is not False:
        raise ValueError('original rail context identity/claim invalid')
    rows = load_rows(attempt / 'rail-frames.jsonl')
    if len(rows) != expected_frames:
        raise ValueError('original rail frame count differs')
    mapping = load_json(attempt / 'frame-map.json')
    frames = [row['original_frame'] for row in rows]
    if mapping.get('frames') != frames or any(mapping.get('camera_frames', {}).get(camera) != frames
                                                for camera in CAMERAS):
        raise ValueError('original rail camera/frame join differs')
    scene = context['scene']
    for kind in ('highway', 'railroad', 'crossing', 'vehicle'):
        if sha(attempt / f'reviewed-{kind}.json') != scene['reviewed_source_sha256'][kind]:
            raise ValueError('reviewed rail source binding changed: ' + kind)
    return hashes, rows, scene, manifest


def measure_left_side(observation, attempt):
    return {'observed_left_body_extent_at_probe': observation['observed_left_body_extent_at_probe'],
            'body_reference_assumption': observation['body_reference_assumption']}


def measure_crossing_distance(observation, attempt):
    return {'observed_leading_body_distance_ft': observation['observed_leading_body_distance_ft'],
            'statutory_distance_ft': 100,
            'approach_within_100ft_by_assumed_reference': observation['approach_within_100ft_by_assumed_reference']}


def measure_traversal(observation, attempt):
    return {'observed_traversal_at_probe': observation['observed_traversal_at_probe'],
            'crossing_source_sha256': sha(Path(attempt) / 'reviewed-crossing.json')}


def measure_one_way(observation, attempt):
    return {'one_way_highway_observed': observation['one_way_highway_observed'],
            'authority_source_sha256': sha(Path(attempt) / 'reviewed-highway.json')}


def measure_rail_qualification(observation, attempt):
    record = load_json(Path(attempt) / 'reviewed-railroad.json')
    return {'stationary_rail_carrier_person_or_property':
            record['stationary_rail_carrier_person_or_property'],
            'streetcar_rail': record['streetcar_rail'],
            'reviewed_source_sha256': sha(Path(attempt) / 'reviewed-railroad.json')}


def selected_measurements(observation, attempt):
    methods = {
        'left_side_measurement': (measure_left_side, ('rail-frames.jsonl',)),
        'crossing_distance_measurement': (measure_crossing_distance,
                                          ('rail-frames.jsonl', 'reviewed-crossing.json')),
        'traversal_measurement': (measure_traversal,
                                  ('rail-frames.jsonl', 'reviewed-crossing.json')),
        'one_way_measurement': (measure_one_way,
                                ('rail-context.json', 'reviewed-highway.json')),
        'rail_qualification_measurement': (measure_rail_qualification,
                                           ('reviewed-railroad.json',)),
    }
    return {name: {'method': method.__name__, 'value': method(observation, attempt),
                   'sources': {source: sha(Path(attempt) / source) for source in sources}}
            for name, (method, sources) in methods.items()}


def analyze(attempt_dir, *, assignment_id, case_id, expected_frames=900,
            recording_description=None):
    from worker_exchange.native_output import frame_record, validate_result

    attempt = Path(attempt_dir).resolve()
    if assignment_id != ASSIGNMENT or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('saved railroad analysis assignment/case mismatch')
    case = next((item for item in CASES if case_id == ASSIGNMENT + '__' + item.case_id), None)
    if case is None:
        raise ValueError('unknown exact saved railroad case')
    hashes, rows, scene, manifest = source_inventory(attempt, case_id, expected_frames)
    manifest_digest = sha(manifest)
    observation = measure_original(rows, scene, case)
    if recording_description is None:
        recording_description = load_json(attempt / 'config.json')['case']['recording_description']
    if not isinstance(recording_description, dict):
        raise ValueError('railroad recording description missing')
    for name in ('result.json', 'analysis-report.json'):
        if (attempt / name).exists():
            raise ValueError('saved railroad output exists; retain prior analysis')
    original_trace = attempt / 'trace.jsonl'
    if original_trace.is_file():
        trace = load_rows(original_trace)
        if len(trace) != expected_frames or any(
                trace[i].get('frame') != row['original_frame'] or
                abs(trace[i].get('time_s', -1) - row['time_s']) > 1e-4
                for i, row in enumerate(rows)):
            raise ValueError('original Core rail trace frame/time differs')
    else:
        with original_trace.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'frame': row['original_frame'],
                    'time_s': row['time_s'],
                    'position_m': [row['leading_body_station_m'],
                                   row['body_leftmost_lateral_m'], 0],
                    'speed_mps': row['ego_speed_mps']}, sort_keys=True) + '\n')
    video_map = attempt / 'video_frames.jsonl'
    mapping = [frame_record(i, row['original_frame'], row['time_s'],
                            camera_frames={name: row['original_frame'] for name in CAMERAS})
               for i, row in enumerate(rows)]
    if video_map.is_file():
        existing = load_rows(video_map)
        if len(existing) != expected_frames or any(
                existing[i].get('carla_frame') != row['carla_frame'] or
                abs(existing[i].get('time_s', -1) - row['time_s']) > 1e-4
                for i, row in enumerate(mapping)):
            raise ValueError('original rail video frame map differs')
    else:
        video_map.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                     for row in mapping))
    values = {
        'rail_qualification': lambda row: {'rail_carrier_sha256': row['rail_carrier_sha256']},
        'highway_direction': lambda row: {'one_way_highway': row['one_way_highway']},
        'crossing_extent': lambda row: {'near_edge_sha256': row['crossing_near_edge_source_sha256']},
        'ego_body_side_and_station': lambda row: {
            'leading_station_m': row['leading_body_station_m'],
            'trailing_station_m': row['trailing_body_station_m'],
            'leftmost_lateral_m': row['body_leftmost_lateral_m'],
            'rightmost_lateral_m': row['body_rightmost_lateral_m']},
        'original_frame_and_camera_join': lambda row: {'frame': row['original_frame'],
            'camera_frames': {name: row['original_frame'] for name in CAMERAS}},
    }
    evidence = []
    for channel in recording_description.get('channels', []):
        name = channel['name']
        if name not in values:
            raise ValueError('unimplemented original rail channel: ' + name)
        reference = 'channels/' + name + '.jsonl'
        path = attempt / reference
        path.parent.mkdir(exist_ok=True)
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': values[name](row)}, sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
    checks = []
    for target, requested, measured in (
            ('left side at probe', case.left_side,
             observation['observed_left_body_extent_at_probe']),
            ('one-way highway source', case.one_way,
             observation['one_way_highway_observed']),
            ('crossing overlap at probe', case.target_leading_distance_ft < 0,
             observation['observed_traversal_at_probe'])):
        checks.append({'target': target, 'requested': requested, 'measured': measured,
                       'method': 'sealed original body, crossing and highway source join',
                       'tolerance': 0, 'matched': requested == measured,
                       'physical_cause_confirmed': False,
                       'cause_evidence': hashes['rail-frames.jsonl']})
    result = {'case_id': case_id, 'measured_values': observation,
              'target_checks': checks,
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original rail packets measured; physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': recording_description,
              'recording_evidence': evidence, 'realized_observables': {}}
    validate_result(result)
    for name, digest in hashes.items():
        if sha(attempt / name) != digest:
            raise ValueError('original rail source changed during analysis: ' + name)
    if sha(manifest) != manifest_digest:
        raise ValueError('original rail source manifest changed during analysis')
    measurements = selected_measurements(observation, attempt)
    (attempt / 'result.json').write_text(json.dumps(result, sort_keys=True) + '\n')
    return {'format': 'c204980-saved-rail-analysis-v1', 'case_id': case_id,
            'observation': observation, 'measurements': measurements,
            'source_manifest_sha256': manifest_digest,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--assignment')
    parser.add_argument('--case')
    args = parser.parse_args()
    config = load_json(Path(args.attempt) / 'config.json')
    assignment = args.assignment or config['assignment_id']
    case = args.case or config['selected_case_id']
    if assignment != config['assignment_id'] or case != config['selected_case_id']:
        raise ValueError('selected saved railroad config mismatch')
    report = analyze(args.attempt, assignment_id=assignment, case_id=case,
                     expected_frames=round(config['duration_s'] * config['rate_hz']))
    Path(args.output).write_text(json.dumps(report, sort_keys=True) + '\n')
    print(json.dumps({'case_id': case, 'source_bound_saved_analysis': True}, sort_keys=True))


if __name__ == '__main__':
    main()
