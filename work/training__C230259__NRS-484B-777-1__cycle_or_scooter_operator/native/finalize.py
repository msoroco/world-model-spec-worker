"""Saved-only bicycle right-edge measurements; qualitative law review stays open."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_right_edge import SOURCES, digest, measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_activation(scope, context):
    return {'bicycle_source': scope['source_kind'], 'roadway_readback': True,
            'standing_vehicle_present': True, 'classification_review_pending': True}


def measure_speed_exception(scope, context):
    return {'nearby_moving_traffic_count': context['nearby_moving_traffic_count'],
            'lawful_commensurate_speed_review_pending': True}


def measure_left_turn_exception(scope, context):
    return {'left_turn_requested': context['left_turn_requested'],
            'preparation_review_pending': True}


def measure_position_and_care(scope, context):
    return {'right_edge_body_margin_min_m': scope['right_edge_body_margin_min_m'],
            'standing_vehicle_clearance_min_m': scope['standing_vehicle_clearance_min_m'],
            'practicability_reviewed': False, 'due_care_reviewed': False}


def measure_unsafe_context(scope, context):
    return {'standing_vehicle_pass_frames': len(scope['standing_vehicle_pass_frames']),
            'unsafe_to_keep_right_review_pending': True}


def measure_object_hazard(scope, context):
    return {'standing_vehicle_recorded': True, 'other_hazard_inventory': context['other_hazard_inventory'],
            'impeded_right_access_review_pending': True}


def measure_narrow_lane(scope, context):
    return {'driving_lane_width_m': context['driving_lane_width_m'],
            'side_by_side_safety_review_pending': True}


def measure_selected_witness(scope, context):
    return {'passing_frames': len(scope['standing_vehicle_pass_frames']),
            'right_edge_margin_m': scope['right_edge_body_margin_min_m'],
            'passing_clearance_m': scope['standing_vehicle_clearance_min_m']}


MEASUREMENTS = (
    ('activation', measure_activation, ('native-cycle-frames.jsonl', 'native-map-readback.json', 'standing-vehicle.json', 'context.json')),
    ('speed_exception', measure_speed_exception, ('native-cycle-frames.jsonl', 'context.json')),
    ('left_turn_exception', measure_left_turn_exception, ('native-cycle-frames.jsonl', 'context.json')),
    ('position_and_care', measure_position_and_care, ('native-cycle-frames.jsonl', 'native-map-readback.json', 'standing-vehicle.json')),
    ('unsafe_context', measure_unsafe_context, ('native-cycle-frames.jsonl', 'standing-vehicle.json', 'context.json')),
    ('object_hazard', measure_object_hazard, ('standing-vehicle.json', 'context.json')),
    ('narrow_lane', measure_narrow_lane, ('native-map-readback.json', 'context.json')),
    ('selected_witness', measure_selected_witness, ('native-cycle-frames.jsonl', 'standing-vehicle.json')),
)


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    for name in (*SOURCES, 'context.json', 'trace.jsonl', 'capture/evidence.jsonl'):
        required(root, name)
    for name in CAMERAS:
        required(root, name + '.mkv')
    expected = {name: digest(root / name) for name in SOURCES}
    context = json.loads((root / 'context.json').read_text())
    if context.get('law_id') != config['law_id'] or context.get('legal_verdict') is not None:
        raise ValueError('Wrong law or asserted legal verdict in saved context')
    diagnostic = context.get('source_kind') == 'synthetic_cpu'
    scope = measure(root, expected, diagnostic=diagnostic)
    tracks, mapping, trace, capture = (rows(root / name) for name in
        ('native-cycle-frames.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
    if any(len(stream) != 600 for stream in (tracks, mapping, trace, capture)):
        raise ValueError('Full 600-frame saved source required')
    for track, frame, state, event in zip(tracks, mapping, trace, capture):
        original = track['native_frame']
        if (frame['native_frame'] != original or state['frame'] != original or
                event['original_frame'] != original or
                any(frame['camera_native_frames'][name] != original for name in CAMERAS)):
            raise ValueError('Saved bicycle, trace and camera frame join differs')
    measurements = {key: {'method': function.__name__, 'value': function(scope, context),
                          'sources': {name: digest(root / name) for name in sources}}
                    for key, function, sources in MEASUREMENTS}
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    recording = []
    for item in config['recording_description']['channels']:
        name = item['name']
        path = channel_dir / (name.replace('/', '_') + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': {
            'actor_id': row['actor_id'], 'body_native_xy_m': row['body_native_xy_m'],
            'standing_body_native_xy_m': row['standing_body_native_xy_m'],
            'source_kind': row['source_kind']}}, separators=(',', ':')) + '\n' for row in tracks))
        recording.append({'name': name, 'unit': item['unit'], 'reference': 'channels/' + path.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        path = channel_dir / (name.replace('/', '_') + '.json')
        path.write_text(json.dumps({name: context}, separators=(',', ':')) + '\n')
        recording.append({'name': name, 'unit': item['unit'], 'reference': 'channels/' + path.name})
    result = {'case_id': config['case_id'], 'measured_values': scope,
              'target_checks': [{'target': 'requested_cycle_center_y_m',
                'requested': config['requested_cycle_center_y_m'],
                'measured': round(sum(point[1] for point in tracks[300]['body_native_xy_m']) / 4, 5),
                'method': 'saved original bicycle body centroid', 'tolerance': .4,
                'matched': abs(sum(point[1] for point in tracks[300]['body_native_xy_m']) / 4 - config['requested_cycle_center_y_m']) <= .4,
                'physical_cause_confirmed': False, 'cause_evidence': ['native-cycle-frames.jsonl']}],
              'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
              'maneuver_completed': not diagnostic,
              'termination_reason': 'full original source window' if not diagnostic else 'synthetic diagnostic window',
              'physical_failure_flags': ['physical_bicycle_and_due_care_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': recording,
              'realized_observables': {'right_edge_body_margin_min_m': {'value': scope['right_edge_body_margin_min_m'],
                  'unit': 'm', 'method': 'saved body/roadway edge join', 'time_window': '600 frames',
                  'statistic': 'minimum', 'reference': 'native-cycle-frames.jsonl'}},
              'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root / 'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'c230259-right-edge-saved-analysis-v1', 'case_id': config['case_id'],
              'measurements': measurements, 'right_edge_scope': scope,
              'original_native_source': not diagnostic, 'legal_verdict': None}
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
