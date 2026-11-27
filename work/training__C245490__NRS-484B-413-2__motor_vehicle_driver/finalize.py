"""Measure saved C245490 signal evidence; never substitute commanded onset."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_signal import measure
from worker_exchange.native_output import physical_result, write_result


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCE_FILES = ('signal-source.jsonl', 'body_history.jsonl', 'trace.jsonl',
    'video_frames.jsonl', 'capture/evidence.jsonl', 'lane-source.json',
    'area-source.json', 'road.xodr', 'config.json')
CHANNELS = ('kin.position', 'kin.speed', 'sig.turn_indicator', 'sig.hand_signal',
    'drv.distance_while', 'kin.path_length', 'drv.turning', 'drv.lane_change',
    'env.precipitation', 'ego_pose',
    'continuous_signal_distance_before_course_change')


def required(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_signal_distance(signal, area_class):
    return measure(signal, area_class)


def measure_weather_source(evidence):
    samples = [row.get('world', {}).get('weather', {}).get('precipitation')
        for row in evidence]
    if any(type(value) not in (int, float) for value in samples):
        raise ValueError('Original weather source incomplete')
    return {'precipitation_min': min(samples), 'precipitation_max': max(samples),
        'threshold_waiver_applied': False}


def measure_area_context(area, threshold):
    return {'area_class_requested': area['area_class_requested'],
        'area_class_originally_verified': area.get('area_class_originally_verified') is True,
        'conditional_threshold_ft': threshold}


def measure_course_change(event, body):
    return {'event_frame': event, 'before_lane_id': body[event - 1]['lane_id'],
        'after_lane_id': body[event]['lane_id'],
        'body_vertices_samples': len(body)}


def finalize(attempt, output):
    root, destination = Path(attempt).resolve(), Path(output)
    if destination.exists():
        raise ValueError('Retain previous selected measurement')
    for name in SOURCE_FILES:
        required(root, name)
    for camera in CAMERAS:
        required(root, camera + '.mkv')
    config = json.loads((root / 'config.json').read_text())
    area = json.loads((root / 'area-source.json').read_text())
    lanes = json.loads((root / 'lane-source.json').read_text())
    provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
    diagnostic = provenance.get('provenance_kind') == 'synthetic_fixture'
    if provenance.get('diagnostic_fixture') is not diagnostic:
        raise ValueError('Acquisition provenance marker inconsistent')
    if area.get('area_class_requested') != config['area_class_requested']:
        raise ValueError('Area source differs from selected request')
    if [row.get('lane_id') for row in lanes.get('lanes', [])] != [-1, -2]:
        raise ValueError('Original same-direction lane survey absent')
    signal = records(root / 'signal-source.jsonl')
    body = records(root / 'body_history.jsonl')
    trace = records(root / 'trace.jsonl')
    frames = records(root / 'video_frames.jsonl')
    evidence = records(root / 'capture/evidence.jsonl')
    if any(len(rows) != 600 for rows in (signal, body, trace, frames, evidence)):
        raise ValueError('Incomplete original 600-frame source join')
    for index, (sample, extent, pose, frame, event) in enumerate(
            zip(signal, body, trace, frames, evidence)):
        identity = frame['carla_frame']
        if (sample['frame'] != index or sample['original_carla_frame'] != identity
                or extent['frame'] != identity or pose['frame'] != identity
                or event['original_frame'] != identity or frame['video_frame'] != index
                or abs(sample['time_s'] - frame['time_s']) > 1e-6
                or abs(extent['time_s'] - frame['time_s']) > 1e-6):
            raise ValueError('Original signal/body/Core/video frame join differs')
        if (sample['native_lane_id'] != extent['lane_id']
                or len(extent['body_vertices_m']) < 4):
            raise ValueError('Original lane/body observation differs')
    initial, destination_lane = ((-1, -2) if config['signal_side'] == 'right'
        else (-2, -1))
    observed_events = [i for i, row in enumerate(body[1:], 1)
        if body[i - 1]['lane_id'] == initial and row['lane_id'] == destination_lane]
    claimed_events = [i for i, row in enumerate(signal) if row['course_change']]
    if observed_events != claimed_events or len(observed_events) != 1:
        raise ValueError('Course-change event not independently bound to lane history')
    measured = measure_signal_distance(signal, config['area_class_requested'])
    weather = measure_weather_source(evidence)
    area_context = measure_area_context(area, measured['threshold_ft'])
    course = measure_course_change(observed_events[0], body)
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    recording_evidence = []
    for name in CHANNELS:
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for sample, extent, event in zip(signal, body, evidence):
                value = {'sample': sample, 'body_vertices_m': extent['body_vertices_m'],
                    'original_weather': event.get('world', {}).get('weather'),
                    'hand_signal_observed': False,
                    'visible_indicator_pixels_reviewed': False}
                stream.write(json.dumps({'time_s': sample['time_s'], 'value': value},
                    allow_nan=False) + '\n')
        recording_evidence.append({'name': name, 'unit': 'structured',
            'reference': 'channels/' + path.name})
    original_area_verified = area.get('area_class_originally_verified') is True
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
        'target_checks': [{'target': 'continuous signal before observed lane change',
            'requested': config['requested_signal_distance_ft'],
            'measured': measured['observed_continuous_distance_ft'],
            'method': 'saved post-tick signal and pose source joined to original lane history',
            'tolerance': 'none; sampled continuity and legal area class require review',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCE_FILES)}],
        'setup_confirmed': False, 'behavior_attempted': not diagnostic,
        'maneuver_completed': False,
        'termination_reason': 'Saved signal interval measured; physical and legal review pending',
        'physical_failure_flags': ['Original area classification and visible signal pixels unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording_evidence, 'realized_observables': {},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False}
    write_result(root, physical_result(root, result))
    bindings = {
        'signal_distance': ('measure_signal_distance', measured,
            ('signal-source.jsonl', 'body_history.jsonl', 'video_frames.jsonl')),
        'weather_source': ('measure_weather_source', weather,
            ('capture/evidence.jsonl', 'video_frames.jsonl')),
        'area_context': ('measure_area_context', area_context,
            ('area-source.json', 'road.xodr', 'video_frames.jsonl')),
        'course_change': ('measure_course_change', course,
            ('body_history.jsonl', 'signal-source.jsonl', 'video_frames.jsonl'))}
    report = {'format': 'worker-signal-selected-measurement',
        'case_id': config['selected_case_id'],
        'measurements': {key: {'method': method, 'value': value,
            'sources': {name: digest(root / name) for name in sources}}
            for key, (method, value, sources) in bindings.items()},
        'area_class_originally_verified': original_area_verified,
        'sampled_indicator_continuity_only': True,
        'visible_indicator_pixels_reviewed': False,
        'legal_compliance': 'unassessed', 'physical_acceptance_claimed': False}
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
