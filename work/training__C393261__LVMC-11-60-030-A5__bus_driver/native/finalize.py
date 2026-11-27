"""Finalize original bus dwell sources without inventing a designated limit."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'terminus-context.json', 'terminus-history.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           *(view + '.mkv' for view in VIEWS))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def measure_bus_dwell(root):
    return measure(Path(root) / 'terminus-history.jsonl',
                   Path(root) / 'terminus-context.json')


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists(),
            'Fresh saved-only bus finalization required')
    for name in ('config.json', 'construction.json', 'terminus-review.json', *SOURCES):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('case_id')
    require(case == construction.get('case_id') and
            case in config.get('supported_case_ids', []), 'Exact bus case changed')
    review = json.loads((attempt / 'terminus-review.json').read_text())
    require(review.get('case_id') == case and
            review.get('assignment_id') == case.rsplit('__', 1)[0],
            'Original bus source review identity differs')
    require(review.get('review_kind') in ('original_native_source', 'synthetic_diagnostic'),
            'Original or declared synthetic bus review required')
    for name in SOURCES:
        if review['review_kind'] == 'synthetic_diagnostic' and name.endswith('.mkv'):
            continue
        require(review.get('source_sha256', {}).get(name) == sha(attempt / name),
                'Reviewed bus source hash differs: ' + name)
    frame_map = rows(attempt / 'video_frames.jsonl')
    history = rows(attempt / 'terminus-history.jsonl')
    require(len(frame_map) == len(history) == 600, 'Full original bus frame span missing')
    for i, (frame, pose) in enumerate(zip(frame_map, history)):
        require(frame.get('video_frame') == pose.get('video_frame') == i and
                frame.get('native_frame') == pose.get('native_frame') and
                abs(frame.get('time_s', -10) - pose.get('time_s', -20)) < .005,
                'Original bus frame/time join differs')
        camera = frame.get('camera_native_frames', {})
        require(set(camera) == set(VIEWS) and
                all(camera[view] == frame['native_frame'] for view in VIEWS),
                'Four original camera frame joins differ')
    measured = measure_bus_dwell(attempt)
    context = json.loads((attempt / 'terminus-context.json').read_text())
    trace_path = attempt / 'trace.jsonl'
    if not trace_path.exists():
        trace = []
        for row in history:
            xyz, velocity = row['position_xyz_m'], row['velocity_xyz_mps']
            speed = sum(v * v for v in velocity) ** .5
            trace.append({'frame': row['native_frame'], 'time_s': row['time_s'],
                          'position': dict(zip(('x', 'y', 'z'), xyz)), 'position_m': xyz,
                          'heading_deg': 0, 'speed_mps': speed,
                          'speed_mph': speed / .44704, 'velocity_mps': velocity,
                          'control': row.get('control', {})})
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                      for row in trace))
    else:
        trace = rows(trace_path)
        require(len(trace) == 600, 'Original bus trace frame count differs')
        for left, right in zip(trace, history):
            require(left.get('frame') == right['native_frame'] and
                    abs(left.get('time_s', -10) - right['time_s']) < .005 and
                    all(abs(a - b) < .01 for a, b in
                        zip(left.get('position_m', []), right['position_xyz_m'])),
                    'Original bus trace differs from Native bus history')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for spec in config['recording_description']['channels']:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row in history:
                xyz, velocity = row['position_xyz_m'], row['velocity_xyz_mps']
                in_zone = -2 <= xyz[0] <= 20 and abs(xyz[1] + 5.25) <= 1.5
                stationary = sum(v * v for v in velocity) ** .5 < .25
                values = {
                    'ru.bus': {'subject_id': row['subject_id'],
                               'blueprint_id': row['blueprint_id'],
                               'non_tour_activity_verified': context.get('actual_loading_activity_verified', False)},
                    'st.curb_zone': {'endpoint_id': context.get('endpoint_id'),
                                     'native_survey': context['native_survey']},
                    'dev.regulatory_sign': {'terminus_signal': context['native_survey']['terminus_signal'],
                                            'physical_pixels_verified': context.get('physical_sign_pixels_verified', False),
                                            'official_designation_verified': context.get('designation_verified', False)},
                    'drv.standing_or_parked': {'stationary': stationary, 'in_endpoint_zone': in_zone},
                    'kin.time': {'native_frame': row['native_frame'], 'time_s': row['time_s']},
                    'rel.occupies': {'position_xyz_m': xyz, 'in_endpoint_zone': in_zone},
                    'drv.condition_in_effect': {'designation_verified': context.get('designation_verified', False),
                                                 'designated_period_s': measured['designated_period_s']},
                }
                value = values[name]
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': spec['unit'],
                         'reference': 'channels/' + path.name})
    hashes = {name: sha(attempt / name) for name in SOURCES}
    hashes['terminus-review.json'] = sha(attempt / 'terminus-review.json')
    report = {'format': 'worker-analysis-report-v1', 'case_id': case,
              'measurements': {'bus_dwell': {'method': 'measure_bus_dwell',
                  'value': measured, 'sources': hashes}},
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'source-measured complete stationary bus occupancy',
                  'requested': config['physical_target']['target_dwell_s'],
                  'measured': measured['longest_complete_interval_s'],
                  'method': 'Original Native post-tick position and velocity',
                  'tolerance': .25,
                  'matched': abs(measured['longest_complete_interval_s'] -
                                 config['physical_target']['target_dwell_s']) <= .25,
                  'physical_cause_confirmed': False, 'cause_evidence': list(hashes)}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'full 600-frame source diagnostic',
              'physical_failure_flags': ['Official period and bus activity require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence + [{'name': 'designation_authority_source',
                  'unit': 'structured', 'reference': 'terminus-context.json'}],
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if
              review['review_kind'] == 'synthetic_diagnostic' else 'original_native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
