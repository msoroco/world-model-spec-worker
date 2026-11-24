"""Measure the authored stop-device request from retained sources only."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines() if line]


def measure_device_response(root):
    actors = rows(root, 'native-raw-actors.jsonl')
    mapping_path = required(root, 'native-map-readback.json')
    mapping = json.loads(mapping_path.read_text())
    if len(actors) != 600 or mapping['stop_landmark_readback']['s_m'] != 50.0:
        raise ValueError('Device source or 600-frame actor source changed')
    stopped = 0
    crossings = 0
    for index, row in enumerate(actors):
        body = row['ego']['body_native_xyz_m']
        if row['frame'] != index or len(body) != 8:
            raise ValueError('Actor body/frame source changed')
        front = max(point[0] for point in body)
        if front < 50.0 and row['ego']['speed_mps'] < 0.1:
            stopped += 1
        if front >= 50.0:
            crossings += 1
    return {'value': {'stopped_before_frames': stopped, 'body_at_station_frames': crossings},
            'method': 'measure_device_response',
            'sources': {'native-raw-actors.jsonl': sha(root / 'native-raw-actors.jsonl'),
                        'native-map-readback.json': sha(mapping_path)},
            'scope': 'Authored diagnostic station; official placement and legal effect unverified'}


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    measurement = measure_device_response(root)
    actors = rows(root, 'native-raw-actors.jsonl')
    frames = rows(root, 'video_frames.jsonl')
    trace = rows(root, 'trace.jsonl')
    evidence = rows(root, 'capture/evidence.jsonl')
    if any(len(source) != 600 for source in (actors, frames, trace, evidence)):
        raise ValueError('Retained 600-frame source counts differ')
    for actor, frame, motion, source in zip(actors, frames, trace, evidence):
        native = actor['native_frame']
        if any(value != native for value in (frame['native_frame'], frame['carla_frame'], motion['frame'], source['original_frame'])):
            raise ValueError('Native frame join differs')
        if any(abs(value - actor['time_s']) > 1e-6 for value in (frame['time_s'], motion['time_s'], source['recording_time_s'])):
            raise ValueError('Native time join differs')
    channels = root / 'channels'
    if channels.exists():
        raise ValueError('Fixture supplied derived channels')
    channels.mkdir()
    (channels / 'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': row['ego']['speed_mps']}) + '\n' for row in actors))
    (channels / 'device_body.jsonl').write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': row['ego']['body_native_xyz_m']}) + '\n' for row in actors))
    recorded = config['recording_description']
    evidence_rows = [{'name': channel['name'], 'unit': channel['unit'],
                      'reference': 'channels/' + channel['name'] + '.jsonl'} for channel in recorded['channels']]
    values = measurement['value']
    requested = bool(config['requested_obey'])
    matched = values['stopped_before_frames'] >= 20 if requested else values['body_at_station_frames'] > 0 and values['stopped_before_frames'] == 0
    result = {
        'case_id': config['case_id'],
        'measured_values': values,
        'target_checks': [{'target': 'authored stop-device approach response',
                           'requested': 'stop before station' if requested else 'pass station',
                           'measured': values, 'method': '600 retained body and speed rows',
                           'tolerance': '20 frames is a diagnostic controller target, not a legal threshold',
                           'matched': matched, 'physical_cause_confirmed': False,
                           'cause_evidence': ['native-raw-actors.jsonl', 'native-map-readback.json']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'synthetic full-duration source fixture processed',
        'physical_failure_flags': ['official_placement_unverified', 'officer_direction_unverified',
                                   'signal_exception_unreviewed', 'original_pixels_unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': recorded, 'recording_evidence': evidence_rows,
        'realized_observables': {}, 'provenance_kind': 'synthetic_cpu_fixture',
        'accepted': False, 'legal_verdict_claimed': False,
    }
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    report = {'format': 'c10389-device-current-v2-analysis', 'case_id': config['case_id'],
              'measurements': {'device_response': measurement},
              'source_only': True, 'official_placement_verified': False,
              'legal_outcome_claimed': False}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
