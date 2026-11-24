"""Measure recorded synthetic entry order from retained actor body rows."""
import argparse
import hashlib
import json
from pathlib import Path

CASE = 'training__C111294__NRS-484B-250-2__motor_vehicle_driver__controlled_2'
SOURCES = ('actor-history.json', 'road-context.json', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_entry(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((attempt / 'road-context.json').read_text())
    raw = json.loads((attempt / 'actor-history.json').read_text())
    if (context.get('source_kind') != 'synthetic_cpu_diagnostic' or
            context.get('official_device_governance_verified') is not False or
            raw.get('case_id') != CASE or raw.get('synthetic') is not True):
        raise ValueError('Source context or provenance differs')
    rows = raw['rows']
    if len(rows) != 600:
        raise ValueError('Expected 600 actor rows')
    mapping = [json.loads(x) for x in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(x) for x in (attempt / 'trace.jsonl').read_text().splitlines()]
    if len(mapping) != 600 or len(trace) != 600:
        raise ValueError('Original frame map or trace length differs')
    ego_entry = other_entry = None
    ego_exit = other_exit = None
    for frame, (row, video, pose) in enumerate(zip(rows, mapping, trace)):
        time = frame / 20
        if (row['frame'] != frame or video['native_frame'] != frame or
                pose['frame'] != frame or abs(row['time_s'] - time) > 1e-6 or
                abs(video['time_s'] - time) > 1e-6):
            raise ValueError('Original actor/video/trace join differs')
        ego = row['ego']['body_xyz_m']
        other = row['other']['body_xyz_m']
        if ego_entry is None and max(p[0] for p in ego) >= -20:
            ego_entry = time
        if other_entry is None and max(p[1] for p in other) >= -20:
            other_entry = time
        if ego_exit is None and min(p[0] for p in ego) >= 20:
            ego_exit = time
        if other_exit is None and min(p[1] for p in other) >= 20:
            other_exit = time
    if any(x is None for x in (ego_entry, other_entry, ego_exit, other_exit)):
        raise ValueError('Both recorded bodies must traverse intersection')
    return {'frames': 600, 'ego_front_entry_s': ego_entry,
            'other_front_entry_s': other_entry,
            'ego_rear_exit_s': ego_exit, 'other_rear_exit_s': other_exit,
            'ego_minus_other_front_entry_s': round(ego_entry - other_entry, 6),
            'approximate_same_time_legally_determined': False,
            'official_device_governance_verified': False,
            'right_of_way_legally_determined': False}


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
    metric = measure_entry(attempt)
    raw = json.loads((attempt / 'actor-history.json').read_text())
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in raw['rows']:
                value = row['ego']['body_xyz_m'] if name == 'ego_body' else row['other']['body_xyz_m']
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    report = {'format': 'worker-analysis-report', 'case_id': CASE,
              'measurements': {'crossroads_entry_measurement': {
                  'method': 'measure_entry', 'value': metric,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'diagnostic_fixture': True,
              'physical_or_legal_acceptance': False}
    result = {'case_id': CASE, 'measured_values': metric,
              'target_checks': [{'target': 'left ego entry after right other entry',
                                 'requested': False, 'measured': metric['ego_minus_other_front_entry_s'] > 0,
                                 'method': 'measure_entry', 'tolerance': 0,
                                 'matched': metric['ego_minus_other_front_entry_s'] <= 0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame synthetic CPU diagnostic',
              'physical_failure_flags': ['Original Native entry and official device governance unverified'],
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
