"""Saved-only left-lane analysis with explicit unresolved statutory predicates."""
import argparse
import json
from pathlib import Path

from left_lane_measure import measure, sha

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native-actors.jsonl', 'native-road-context.json',
           'native-map-readback.json', 'context.json')


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_activation(observed, road, context):
    return {'same_direction_marked_lane_count': road['same_direction_marked_lane_count'],
            'extreme_left_lane_id': road['extreme_left_lane_id'],
            'controlled_access_original_verified': context.get('controlled_access_original_verified', False),
            'controlled_access_review_pending': True}


def measure_speed_and_overtake(observed, road, context):
    return {'rear_higher_speed_behind_frames': observed['rear_higher_speed_behind_frames'],
            'overtake_crossing_frame': observed['overtake_crossing_frame'],
            'slow_extreme_left_frames': observed['slow_extreme_left_frames'],
            'posted_limit_original_verified': road.get('posted_limit_original_verified', False),
            'driver_notice_review_pending': True}


def measure_maintenance_exception(observed, road, context):
    return {'maintenance_or_emergency_duty_verified':
            context['maintenance_or_emergency_duty_verified'],
            'subsection_2_exception_review_pending': True}


def measure_selected_witness(observed, road, context):
    return {'slow_extreme_left_after_overtake_frames':
            observed['slow_extreme_left_after_overtake_frames'],
            'ego_exited_left_before_crossing':
            observed['ego_exited_left_before_crossing'],
            'legal_verdict_claimed': False}


MEASUREMENTS = (
    ('activation', measure_activation, ('native-map-readback.json', 'native-road-context.json')),
    ('speed_and_overtake', measure_speed_and_overtake,
     ('native-actors.jsonl', 'native-road-context.json')),
    ('maintenance_exception', measure_maintenance_exception, ('context.json',)),
    ('selected_witness', measure_selected_witness,
     ('native-actors.jsonl', 'native-road-context.json')),
)


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    for name in (*SOURCES, 'trace.jsonl', 'video_frames.jsonl',
                 'capture/evidence.jsonl'):
        required(root, name)
    for name in CAMERAS:
        required(root, name + '.mkv')
    road = json.loads((root / 'native-road-context.json').read_text())
    context = json.loads((root / 'context.json').read_text())
    mapping = json.loads((root / 'native-map-readback.json').read_text())
    if (context.get('law_id') != config['law_id'] or
            context.get('legal_verdict') is not None or
            mapping.get('same_direction_marked_lane_count') != 2):
        raise ValueError('Wrong law, lane map or asserted legal verdict')
    expected = {name: sha(root / name) for name in ('native-actors.jsonl',
                                                      'native-road-context.json')}
    observed = measure(root / 'native-actors.jsonl',
                       root / 'native-road-context.json', expected)
    streams = [rows(root / name) for name in ('native-actors.jsonl',
        'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')]
    if any(len(stream) != 600 for stream in streams):
        raise ValueError('Full 600-frame saved source required')
    for actor, frame, state, event in zip(*streams):
        native = actor['native_frame']
        if (frame['native_frame'] != native or state['frame'] != native or
                event['original_frame'] != native or
                any(frame['camera_native_frames'][name] != native for name in CAMERAS)):
            raise ValueError('Saved actor, trace and camera frame join differs')
    measurements = {key: {'method': function.__name__,
            'value': function(observed, road, context),
            'sources': {name: sha(root / name) for name in sources}}
        for key, function, sources in MEASUREMENTS}
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    recording = []
    for channel in config['recording_description']['channels']:
        name = channel['name']
        path = channel_dir / (name.replace('/', '_') + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
            'value': {'ego_lane_id': row['ego_lane_id'],
                      'rear_lane_id': row['rear_lane_id'],
                      'ego_longitudinal_m': row['ego_longitudinal_m'],
                      'rear_longitudinal_m': row['rear_longitudinal_m'],
                      'ego_speed_mps': row['ego_speed_mps'],
                      'rear_speed_mps': row['rear_speed_mps']}},
            separators=(',', ':')) + '\n' for row in streams[0]))
        recording.append({'name': name, 'unit': channel['unit'],
                          'reference': 'channels/' + path.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        path = channel_dir / (name.replace('/', '_') + '.json')
        path.write_text(json.dumps({name: context}, separators=(',', ':')) + '\n')
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/' + path.name})
    requested = config['slow_extreme_left_lane_continuation']
    measured = observed['slow_extreme_left_after_overtake_frames'] > 0
    diagnostic = road['source_kind'] != 'original_native'
    result = {'case_id': config['case_id'],
        'measured_values': {'slow_extreme_left_after_overtake_frames':
                            observed['slow_extreme_left_after_overtake_frames'],
                            'overtake_crossing_frame': observed['overtake_crossing_frame']},
        'target_checks': [{'target': 'slow_extreme_left_lane_continuation',
                           'requested': requested, 'measured': measured,
                           'method': 'saved original actor lane relation',
                           'tolerance': 0, 'matched': requested == measured,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native-actors.jsonl']}],
        'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
        'maneuver_completed': not diagnostic,
        'termination_reason': 'full original source window' if not diagnostic
                              else 'synthetic diagnostic window',
        'physical_failure_flags': ['controlled_access_speed_notice_exception_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording,
        'realized_observables': {'slow_left_after_overtake_frames': {
            'value': observed['slow_extreme_left_after_overtake_frames'],
            'unit': 'frames', 'method': 'saved Native actor lane and speed join',
            'time_window': '600 frames', 'statistic': 'count',
            'reference': 'native-actors.jsonl'}},
        'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root / 'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'c230259-left-lane-saved-analysis-v1',
        'case_id': config['case_id'], 'measurements': measurements,
        'left_lane_scope': observed, 'original_native_source': not diagnostic,
        'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == '__main__':
    main()
