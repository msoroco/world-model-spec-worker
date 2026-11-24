"""Selected-requirement measurements from sealed original approach sources.

These values describe observed geometry and motion. They do not decide whether
an approach satisfies the statute's nearest-centerline phrase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from approach import _verified, measure, validate_context

SOURCES = ('intersection-context.json', 'approach-history.jsonl',
           'video_frames.jsonl')


def _source(attempt: Path):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    originals = {}
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
        path, digest = _verified(attempt, name, acquisition)
        originals[name] = {'path': path, 'sha256': digest}
    return acquisition, originals


def measure_left_turn(attempt: Path) -> dict:
    observed = measure(attempt)
    return {'approach_frames': len(observed['approach_frames']),
            'departure_frames': len(observed['departure_frames']),
            'left_turn_heading_change_rad': observed['observed_left_turn_heading_change_rad']}


def measure_two_directional(attempt: Path) -> dict:
    _, originals = _source(attempt)
    context = json.loads(originals['intersection-context.json']['path'].read_text())
    validate_context(context)
    return {'road_ids': [road['road_id'] for road in context['intersecting_roads']],
            'lane_counts': [len(road['lanes']) for road in context['intersecting_roads']],
            'public_highway_source': context['public_highway_source']}


def measure_right_half(attempt: Path) -> dict:
    observed = measure(attempt)
    return {'centerline_kind': observed['centerline_kind'],
            'nearest_body_edge_range_m': observed['nearest_body_edge_range_m'],
            'all_sampled_body_in_right_half': observed['all_sampled_body_in_right_half']}


def finalize(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    acquisition, originals = _source(attempt)
    if acquisition.get('case_id') != case_id:
        raise ValueError('wrong exact saved case')
    hashes = {name: row['sha256'] for name, row in originals.items()}
    values = {}
    for key, method in (('left_turn_observed', measure_left_turn),
                        ('two_directional_roads', measure_two_directional),
                        ('approach_right_half', measure_right_half)):
        values[key] = {'method': method.__name__, 'value': method(attempt),
                       'sources': hashes}
    return {'case_id': case_id, 'measurements': values,
            'source_complete': True, 'legal_nearest_portion_verdict': 'unresolved',
            'acquisition_sha256': hashlib.sha256((attempt / 'acquisition.json').read_bytes()).hexdigest()}


def write_native_result(attempt: Path, report: dict) -> dict:
    """Project sealed body/map/camera rows into diagnostic Native result fields."""
    attempt = Path(attempt)
    if (attempt / 'result.json').exists() or (attempt / 'channels').exists() or (attempt / 'trace.jsonl').exists():
        raise ValueError('refusing to overwrite saved result or channel outputs')
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['selected_case_id']
    if report['case_id'] != case_id:
        raise ValueError('materialized exact case differs')
    acquisition, originals = _source(attempt)
    history = [json.loads(line) for line in originals['approach-history.jsonl']['path'].read_text().splitlines() if line.strip()]
    frames = [json.loads(line) for line in originals['video_frames.jsonl']['path'].read_text().splitlines() if line.strip()]
    context = json.loads(originals['intersection-context.json']['path'].read_text())
    if len(history) != len(frames) or not history:
        raise ValueError('original body/camera frame count differs')
    description = json.loads((attempt / 'construction.json').read_text())['recording_description']
    names = [item['name'] for item in description['channels']]
    if names != ['full_body_approach_xy', 'centerline_and_right_half', 'departure_heading', 'camera_sources']:
        raise ValueError('recording channel contract differs')
    channels = {name: [] for name in names}
    trace = []
    previous = None
    for index, (body, frame) in enumerate(zip(history, frames)):
        if body['frame'] != frame['carla_frame'] or frame['video_frame'] != index or abs(body['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('original body/camera frame join differs')
        vertices = body['ego_body_vertices_xy_m']
        center = [sum(vertex[axis] for vertex in vertices) / len(vertices) for axis in (0, 1)]
        if previous is None:
            velocity = [0.0, 0.0, 0.0]
        else:
            dt = body['time_s'] - previous[1]
            if dt <= 0:
                raise ValueError('original body sample time did not advance')
            velocity = [(center[0] - previous[0][0]) / dt,
                        (center[1] - previous[0][1]) / dt, 0.0]
        speed = math.hypot(*velocity[:2])
        previous = (center, body['time_s'])
        trace.append({'frame': body['frame'], 'time_s': body['time_s'],
                      'position': {'x': center[0], 'y': center[1], 'z': 0.0},
                      'position_m': [*center, 0.0],
                      'heading_deg': math.degrees(body['ego_heading_rad']),
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': velocity, 'control': {}})
        values = (vertices,
                  {'centerline_xy_m': context['approach_centerline_xy_m'],
                   'half_width_m': context['approach_half_width_m'], 'road_id': body['road_id']},
                  {'heading_rad': body['ego_heading_rad'], 'road_id': body['road_id']},
                  {'camera_frames': frame['camera_frames'], 'camera_times_s': frame['camera_times_s']})
        for name, value in zip(names, values):
            channels[name].append({'time_s': body['time_s'], 'value': value})
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    evidence = []
    for spec in description['channels']:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row in channels[name]:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': spec['unit'], 'reference': 'channels/' + name + '.jsonl'})
    with (attempt / 'trace.jsonl').open('x') as stream:
        for row in trace:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
    measured = report['measurements']['approach_right_half']['value']['nearest_body_edge_range_m'][0]
    requested = config['target_approach_offset_m']
    check = {'target': 'authored approach body offset', 'requested': requested,
             'measured': measured, 'method': 'sealed original full-body approach history',
             'tolerance': 0.05, 'matched': abs(requested - measured) <= 0.05,
             'physical_cause_confirmed': False,
             'cause_evidence': {name: row['sha256'] for name, row in originals.items()}}
    result = {'case_id': case_id, 'measured_values': report['measurements'],
              'target_checks': [check], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved source projection; physical completion unverified',
              'physical_failure_flags': {'physical_completion_unverified': True},
              'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'provenance_kind': 'synthetic_fixture' if acquisition.get('diagnostic_fixture') else 'native',
              'diagnostic_fixture': acquisition.get('diagnostic_fixture') is True,
              'physical_acceptance_claimed': False}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt, result)
    validate_result(result)
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing to overwrite saved output')
    acquisition = json.loads((args.attempt / 'acquisition.json').read_text())
    case_id = acquisition.get('case_id')
    if not isinstance(case_id, str) or not case_id:
        raise ValueError('original acquisition case missing')
    report = finalize(args.attempt, case_id)
    write_native_result(args.attempt, report)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
