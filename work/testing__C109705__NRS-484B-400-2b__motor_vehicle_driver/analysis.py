"""Analyze sealed departure sources without turning geometry into a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from departure_geometry import measure

SOURCES = ('original-bindings.json', 'original-map-packet.json',
           'original-trace.json', 'original-camera-index.json')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_sources(attempt):
    attempt = Path(attempt).resolve()
    files = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing required source: ' + name)
        files[name] = path
    manifest = json.loads(files['original-bindings.json'].read_text())
    for field, name in (('map', 'original-map-packet.json'),
                        ('trace', 'original-trace.json'),
                        ('camera_index', 'original-camera-index.json')):
        binding = manifest.get(field, {})
        if binding.get('path') != name or binding.get('sha256') != _sha(files[name]):
            raise ValueError('Original source binding differs: ' + name)
    return manifest, files


def measure_departure(attempt):
    manifest, files = _read_sources(attempt)
    map_packet = json.loads(files['original-map-packet.json'].read_text())
    trace_packet = json.loads(files['original-trace.json'].read_text())
    return measure(map_packet, trace_packet, case_id=manifest['case_id'])


def finalize(attempt, case_id):
    manifest, files = _read_sources(attempt)
    if manifest.get('case_id') != case_id:
        raise ValueError('Exact saved case differs')
    hashes = {name: _sha(path) for name, path in files.items()}
    return {
        'case_id': case_id,
        'measurements': {
            'departure_right_of_centerline': {
                'method': 'measure_departure',
                'value': measure_departure(attempt),
                'sources': hashes,
            }
        },
        'source_complete': True,
        'statutory_judgment': None,
    }


def write_native_result(attempt, report):
    """Project measured original rows to the runtime's diagnostic channel form."""
    attempt = Path(attempt)
    if (attempt / 'result.json').exists() or (attempt / 'trace.jsonl').exists():
        raise ValueError('Refusing to overwrite saved derived output')
    trace_packet = json.loads((attempt / 'original-trace.json').read_text())
    camera = json.loads((attempt / 'original-camera-index.json').read_text())
    map_packet = json.loads((attempt / 'original-map-packet.json').read_text())
    rows = trace_packet['samples']
    if len(rows) != 900 or set(camera['channels']) != {'dash', 'front', 'left', 'right'}:
        raise ValueError('Original duration or camera count differs')
    description = json.loads((attempt / 'construction.json').read_text())['recording_description']
    channels = description['channels']
    names = [item['name'] for item in channels]
    if names != ['full_body_departure_xy', 'centerline_and_right_half',
                 'departure_heading', 'camera_sources']:
        raise ValueError('Recording channel contract differs')
    output = {name: [] for name in names}
    traces = []
    for index, row in enumerate(rows):
        t = row['elapsed_seconds']
        if abs(t - rows[0]['elapsed_seconds'] - index / 20) > .002:
            raise ValueError('Original clock drift')
        point = row['position_xy_m']
        speed = row['speed_mps']
        traces.append({'frame': row['frame'], 'time_s': t,
                       'position': {'x': point[0], 'y': point[1], 'z': 0.0},
                       'position_m': [*point, 0.0],
                       'heading_deg': math.degrees(row['heading_rad']),
                       'speed_mps': speed, 'speed_mph': speed / .44704,
                       'velocity_mps': [speed * math.cos(row['heading_rad']),
                                        speed * math.sin(row['heading_rad']), 0.0],
                       'control': {}})
        frames = {name: camera['channels'][name][index] for name in camera['channels']}
        if any(item['frame'] != row['frame'] for item in frames.values()):
            raise ValueError('Original camera/frame join differs')
        values = (
            {'phase': row['phase'], 'body_corners_xy_m': row['body_corners_xy_m']},
            {'centerline_kind': map_packet['centerline_kind'],
             'centerline_origin_xy_m': map_packet['centerline_origin_xy_m'],
             'destination_direction_xy': map_packet['destination_direction_xy']},
            {'heading_rad': row['heading_rad'], 'road_id': row['road_id']},
            {'camera_frames': {name: item['frame'] for name, item in frames.items()}},
        )
        for name, value in zip(names, values):
            output[name].append({'time_s': t, 'value': value})
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    evidence = []
    for spec in channels:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                for row in output[name]))
        evidence.append({'name': name, 'unit': spec['unit'],
                         'reference': 'channels/' + name + '.jsonl'})
    (attempt / 'trace.jsonl').write_text(''.join(
        json.dumps(row, allow_nan=False) + '\n' for row in traces))
    target = json.loads((attempt / 'config.json').read_text())['departure_position_target']
    observed = report['measurements']['departure_right_of_centerline']['value']
    result = {
        'case_id': report['case_id'], 'measured_values': report['measurements'],
        'target_checks': [{'target': 'authored departure lateral setting',
                           'requested': target,
                           'measured': observed['observed_right_min_m'],
                           'method': 'sealed original full-body departure history',
                           'tolerance': 0.05, 'matched': False,
                           'physical_cause_confirmed': False,
                           'cause_evidence': report['measurements'][
                               'departure_right_of_centerline']['sources']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source projection; physical completion unverified',
        'physical_failure_flags': {'physical_completion_unverified': True},
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}, 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
    }
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt, result)
    validate_result(result)
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt)
    if Path(args.output).exists():
        raise ValueError('Refusing to overwrite analysis report')
    case_id = json.loads((attempt / 'config.json').read_text())['selected_case_id']
    report = finalize(attempt, case_id)
    write_native_result(attempt, report)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
