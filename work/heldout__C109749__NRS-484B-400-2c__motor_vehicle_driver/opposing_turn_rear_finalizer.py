"""Saved-only finalization of the rear opposing-left-turn delivery case."""

import argparse
import hashlib
import json
from pathlib import Path

from opposing_turn_measurement import measure
from opposing_turn_rear_runner import check_config


ORIGINALS = ('subject_original.jsonl', 'opposing_original.jsonl',
             'topology_original.json', 'devices_original.json',
             'video_frames.jsonl', 'trace.jsonl')


def _source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_opposing_turn(root):
    return measure(*(_source(root, name) for name in ORIGINALS[:4]))


def analyze(root):
    root = Path(root)
    config = json.loads(_source(root, 'config.json').read_text())
    check_config(config)
    subject = _rows(_source(root, ORIGINALS[0]))
    opposing = _rows(_source(root, ORIGINALS[1]))
    mapping = _rows(_source(root, ORIGINALS[4]))
    trace = _rows(_source(root, ORIGINALS[5]))
    if not len(subject) >= 3 or not len(subject) == len(opposing) == len(mapping) == len(trace):
        raise ValueError('Original opposing-turn source lengths differ')
    for index, (a, b, frame_map, state) in enumerate(zip(subject, opposing, mapping, trace)):
        if (frame_map.get('video_frame') != index or
                frame_map.get('carla_frame') != state.get('frame') or
                state.get('frame') != a.get('frame') or a.get('frame') != b.get('frame') or
                frame_map.get('time_s') != state.get('time_s') or
                state.get('time_s') != a.get('time_s') or a.get('time_s') != b.get('time_s')):
            raise ValueError('Original opposing-turn frame/time join differs')
    observed = measure_opposing_turn(root)
    channels = {
        'simultaneous_left_turn_frames': [
            {'frame': row['frame'], 'time_s': row['time_s'], 'value': 1}
            for row in observed['observations']],
        'closest_ground_body_clearance_m': [
            {'frame': row['frame'], 'time_s': row['time_s'],
             'value': row['ground_body_clearance_m']}
            for row in observed['observations']],
    }
    for name, rows in channels.items():
        path = root / (name + '.jsonl')
        if path.exists():
            raise ValueError('Retain prior opposing-turn derived channel: ' + name)
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    return {
        'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
        'measurements': {'opposing_turn_geometry': {
            'method': 'measure_opposing_turn', 'value': observed,
            'sources': {name: _sha(_source(root, name)) for name in ORIGINALS}}},
        'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False,
    }


def result(root, report):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    observed = report['measurements']['opposing_turn_geometry']['value']
    recorded = []
    realized = {}
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        path = _source(root, name + '.jsonl')
        rows = _rows(path)
        if not rows:
            raise ValueError('Missing derived opposing-turn channel: ' + name)
        recorded.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name, 'sha256': _sha(path)})
        realized[name] = {
            'unit': channel['unit'], 'method': channel['method'],
            'time_window': channel['time_window'],
            'statistic': 'count' if name.startswith('simultaneous') else 'at_closest_center',
            'reference': path.name,
            'value': (observed['simultaneous_frames'] if name.startswith('simultaneous')
                      else observed['closest']['ground_body_clearance_m']),
            'sample_window_s': [rows[0]['time_s'], rows[-1]['time_s']],
        }
    for name, original in (('opposing_topology', ORIGINALS[2]),
                           ('opposing_devices', ORIGINALS[3])):
        copied = root / (name + '-recorded.json')
        if copied.exists():
            raise ValueError('Retain prior derived opposing-turn context')
        copied.write_text(json.dumps({name: json.loads(_source(root, original).read_text())}) + '\n')
        recorded.append({'name': name, 'unit': 'structured record',
                         'reference': copied.name, 'sha256': _sha(copied)})
    return {
        'case_id': report['case_id'],
        'measured_values': {'opposing_turn_geometry': observed},
        'target_checks': [{
            'target': 'simultaneous opposing left turns on two-directional highways with measured relative body geometry',
            'requested': config['selected_case_id'], 'measured': observed,
            'method': 'joined original 20 Hz Native actor bodies, headings, map and device inventory',
            'tolerance': None, 'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': 'Original source geometry; physical front/rear order and legal applicability need independent review'}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved original-source measurement complete; physical and legal outcome unverified',
        'physical_failure_flags': {'motion_unverified': True, 'crossing_order_unverified': True},
        'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['case']['recording_description'],
        'recording_evidence': recorded, 'realized_observables': realized,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior opposing-turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result(args.attempt, report))


if __name__ == '__main__':
    main()
