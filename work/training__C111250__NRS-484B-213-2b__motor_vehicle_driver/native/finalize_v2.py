"""Recompute a 600-frame draft zone measurement from retained source rows."""
import argparse
import hashlib
import json
from pathlib import Path

from zone_measure import measure

SOURCES = ('road-context.json', 'vehicle-footprints.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_zone(metric):
    return {key: metric[key] for key in
            ('frames', 'first_active_frame', 'first_left_active_frame',
             'first_left_approach_frame', 'first_left_traversal_frame',
             'one_way_highway', 'subsection_2_applicability')}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = 'training__C111250__NRS-484B-213-2b__motor_vehicle_driver__probe_01'
    if config['case_id'] != case or construction['case_id'] != case:
        raise ValueError('Exact diagnostic case differs')
    metric = measure(attempt)
    bodies = read_rows(attempt / 'vehicle-footprints.jsonl')
    frame_map = read_rows(attempt / 'video_frames.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    if len(bodies) != len(frame_map) or len(trace) != 600:
        raise ValueError('Saved original row count differs')
    for row, mapping, pose in zip(bodies, frame_map, trace):
        if (row['native_frame'] != mapping['native_frame'] or
                pose['frame'] != mapping['carla_frame'] or
                abs(row['time_s'] - mapping['time_s']) > 1e-6):
            raise ValueError('Saved original footprint/trace/video join differs')
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row, mapping in zip(bodies, frame_map):
                value = row['body_xy_m'] if name == 'vehicle_footprint' else metric['one_way_highway']
                stream.write(json.dumps({'time_s': mapping['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'zone_measurement': {'method': 'measure_zone',
                              'value': measure_zone(metric),
                              'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'diagnostic_fixture': True,
              'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measure_zone(metric),
              'target_checks': [{'target': 'left-side footprint during active intersection zone',
                                 'requested': False,
                                 'measured': metric['first_left_active_frame'] is not None,
                                 'method': 'measure_zone', 'tolerance': 0,
                                 'matched': metric['first_left_active_frame'] is None,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame synthetic CPU diagnostic',
              'physical_failure_flags': ['Original Native roadway and body evidence unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
