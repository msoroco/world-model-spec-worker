"""Measure a retained one-way left turn from original geometry and joined frames."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from turn_geometry import measure
from turn_native_runner import check_config


def source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_turn(geometry, footprints):
    """Case-specific original map/footprint measurement, without a legal verdict."""
    return measure(geometry, footprints)


def analyze(root):
    root = Path(root)
    config = json.loads(source(root, 'config.json').read_text())
    check_config(config)
    geometry = source(root, 'road_geometry.json')
    footprints = source(root, 'body_footprints.json')
    observed = measure_turn(geometry, footprints)
    original = json.loads(footprints.read_text())['frames']
    history = rows(source(root, 'body_footprints.jsonl'))
    mapping = rows(source(root, 'video_frames.jsonl'))
    trace = rows(source(root, 'trace.jsonl'))
    if original != history or len(history) < 3 or len(mapping) != len(history) or len(trace) != len(history):
        raise ValueError('Original turn footprint, trace and frame-map lengths differ')
    for index, (frame_map, state, body) in enumerate(zip(mapping, trace, history)):
        if (frame_map.get('video_frame') != index
                or frame_map.get('carla_frame') != state.get('frame')
                or state.get('frame') != body.get('frame')
                or frame_map.get('time_s') != state.get('time_s')
                or state.get('time_s') != body.get('time_s')
                or body.get('subject_id') != observed['subject_id']):
            raise ValueError('Original turn frame join differs')
    from turn_geometry import _line, _signed
    road = json.loads(geometry.read_text())
    curb = _line(road['source_left_curb'])
    center = _line(road['destination_centerline'])
    channels = {'approach_left_curb_distance_m': [], 'departure_centerline_signed_m': []}
    for body in history:
        points = body['ground_corners']
        if body['phase'] == 'approach':
            value = min(abs(_signed(point, curb)) for point in points)
            channels['approach_left_curb_distance_m'].append((body['frame'], body['time_s'], value))
        elif body['phase'] == 'leaving_intersection':
            value = max(_signed(point, center) for point in points)
            channels['departure_centerline_signed_m'].append((body['frame'], body['time_s'], value))
    for name, samples in channels.items():
        (root / (name + '.jsonl')).write_text(''.join(
            json.dumps({'frame': frame, 'time_s': time_s, 'value': value}) + '\n'
            for frame, time_s, value in samples))
    inputs = ('road_geometry.json', 'body_footprints.json', 'body_footprints.jsonl',
              'video_frames.jsonl', 'trace.jsonl')
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {'turn_geometry': {'method': 'measure_turn', 'value': observed,
                                              'sources': {name: sha(source(root, name)) for name in inputs}}},
            'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False}


def result(root, report):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    observed = report['measurements']['turn_geometry']['value']
    recorded = []
    realized = {}
    values = {'approach_left_curb_distance_m': observed['approach_left_curb_nearest_m'],
              'departure_centerline_signed_m': observed['departure_centerline_max_signed_m']}
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        path = root / (name + '.jsonl')
        samples = rows(path)
        if not samples:
            raise ValueError('Missing derived turn samples: ' + name)
        recorded.append({'name': name, 'unit': channel['unit'], 'reference': path.name, 'sha256': sha(path)})
        realized[name] = {'unit': channel['unit'], 'method': channel['method'],
                          'time_window': channel['time_window'],
                          'statistic': 'minimum' if name.startswith('approach') else 'maximum',
                          'reference': path.name, 'value': values[name],
                          'sample_window_s': [samples[0]['time_s'], samples[-1]['time_s']]}
    for name in ('road_geometry', 'body_footprints'):
        original = root / (name + '.json')
        derived = root / (name + '-recorded.json')
        if derived.exists():
            raise ValueError('Retain prior derived turn context')
        derived.write_text(json.dumps({name: json.loads(original.read_text())}) + '\n')
        recorded.append({'name': name, 'unit': 'structured record',
                         'reference': derived.name, 'sha256': sha(derived)})
    return {'case_id': report['case_id'], 'measured_values': {'turn_geometry': observed},
            'target_checks': [{'target': 'left turn from one-way to two-directional road with measured approach and departure',
                               'requested': config['selected_case_id'],
                               'measured': observed,
                               'method': 'original map lines and joined four-corner body footprints',
                               'tolerance': None, 'matched': True,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Map geometry and body footprints; Native motion and legal practicability require independent review'}],
            'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
            'termination_reason': 'Saved source measurement complete; physical and legal outcome unverified',
            'physical_failure_flags': {'motion_unverified': True, 'practicability_unverified': True},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': config['case']['recording_description'],
            'recording_evidence': recorded, 'realized_observables': realized,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result(args.attempt, report))


if __name__ == '__main__':
    main()
