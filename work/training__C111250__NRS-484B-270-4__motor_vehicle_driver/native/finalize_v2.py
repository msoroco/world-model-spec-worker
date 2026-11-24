"""Recompute an unselected cycle-facility measurement from retained source rows."""
import argparse
import hashlib
import json
from pathlib import Path
from measure_saved import measure

SOURCES = ('facility-context.json', 'body-history.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
CASE = 'training__C111250__NRS-484B-270-4__motor_vehicle_driver__controlled_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_cycle_lane(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if config['case_id'] != CASE or construction['case_id'] != CASE:
        raise ValueError('Exact diagnostic case differs')
    metric = measure_cycle_lane(attempt)
    bodies, frame_map, trace = [rows(attempt / name) for name in
                               ('body-history.jsonl', 'video_frames.jsonl', 'trace.jsonl')]
    if len(bodies) != 600 or len(frame_map) != 600 or len(trace) != 600:
        raise ValueError('Saved original row count differs')
    for row, mapping, pose in zip(bodies, frame_map, trace):
        if (row['native_frame'] != mapping['native_frame'] or
                pose['frame'] != mapping['carla_frame'] or
                abs(row['time_s'] - mapping['time_s']) > 1e-6):
            raise ValueError('Saved original body/trace/video join differs')
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row, mapping in zip(bodies, frame_map):
                value = row['body_xy_m'] if name == 'vehicle_body' else [3.5, 5.5]
                stream.write(json.dumps({'time_s': mapping['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    value = {key: metric[key] for key in ('frames', 'intersection_body_frames',
        'cycle_lane_intersection_overlap_frames', 'first_cycle_lane_intersection_overlap_frame',
        'official_designation_proven', 'subsection_3_exception_resolved', 'legal_verdict_claimed')}
    report = {'format': 'worker-analysis-report', 'case_id': CASE,
              'measurements': {'cycle_lane_intersection_measurement': {
                  'method': 'measure_cycle_lane', 'value': value,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'diagnostic_fixture': True,
              'physical_or_legal_acceptance': False}
    result = {'case_id': CASE, 'measured_values': value,
              'target_checks': [{'target': 'body intersection with authored cycle facility',
                                 'requested': False,
                                 'measured': metric['cycle_lane_intersection_overlap_frames'] > 0,
                                 'method': 'measure_cycle_lane', 'tolerance': 0,
                                 'matched': metric['cycle_lane_intersection_overlap_frames'] == 0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame synthetic CPU diagnostic',
              'physical_failure_flags': ['Original Native cycle-lane designation and body evidence unverified',
                                         'Subsection 3 exception unresolved'],
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
