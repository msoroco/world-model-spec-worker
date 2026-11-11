"""Saved-only analysis of the selected continuing-highway source point."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from highway_continuity_runner import CASE, check_config
from highway_continuity_source import measure_originals


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    check_config(config)
    topology_path, topology_sha = _source(root, 'highway_pair_topology.json')
    participants_path, participants_sha = _source(root, 'intersection_participants.jsonl')
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    inventory_path, inventory_sha = _source(root, 'control_inventory.json')
    inventory = json.loads(inventory_path.read_text())
    topology = json.loads(topology_path.read_text())
    if (inventory.get('format') != 'worker-ending-road-original-control-inventory' or
            str(inventory.get('junction_id')) != str(topology.get('junction_id')) or
            any(inventory.get(key) for key in
                ('ending_landmarks', 'through_landmarks', 'junction_lights'))):
        raise ValueError('Original highway-comparison control inventory differs')
    mapping, trace, participants = (_rows(path) for path in
                                    (map_path, trace_path, participants_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Original highway-comparison source/frame-map length differs')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (participant.get('frame'), participant.get('time_s')) != identity):
            raise ValueError('Original highway-comparison source/frame-map join failed')
    observed = measure_originals(topology_path, participants_path)
    return {'format': 'worker-analysis-report', 'case_id': CASE,
            'measurements': {'highway_continuity_observation': {
                'method': 'measure_originals', 'value': observed,
                'sources': {'highway_pair_topology.json': topology_sha,
                            'intersection_participants.jsonl': participants_sha,
                            'video_frames.jsonl': map_sha, 'trace.jsonl': trace_sha,
                            'control_inventory.json': inventory_sha}}},
            'limitations': ['Native OpenDRIVE continuity is an operational source point; legal highway identity and simultaneous entry require separate review.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected highway-continuity recording description missing')
    observed = report['measurements']['highway_continuity_observation']['value']
    channel = root / 'intersection_occupancy.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived intersection occupancy')
    channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': {'subject_in_conflict': row['subject_in_conflict'],
                  'other_in_conflict': row['other_in_conflict']}}) + '\n'
        for row in observed['observations']))
    rows = observed['observations']
    return {'case_id': CASE,
            'measured_values': {'highway_continuity_observation': observed},
            'target_checks': [{'target': 'continuing highway comparison point',
                'requested': True, 'measured': observed['selected_category'] == 'continuing',
                'method': 'original connected Native route topology', 'tolerance': None,
                'matched': False, 'physical_cause_confirmed': False,
                'cause_evidence': 'Original Native source; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved continuity measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [
                {'name': 'intersection_occupancy', 'unit': 'bool',
                 'reference': channel.name,
                 'sha256': sha256(channel.read_bytes()).hexdigest()},
                {'name': 'lanes', 'unit': 'structured topology',
                 'reference': 'highway_pair_topology.json',
                 'sha256': sha256((root / 'highway_pair_topology.json').read_bytes()).hexdigest()},
                {'name': 'control_inventory', 'unit': 'structured Native control inventory',
                 'reference': 'control_inventory.json',
                 'sha256': sha256((root / 'control_inventory.json').read_bytes()).hexdigest()}],
            'realized_observables': {'entry_delta_s': {'unit': 's',
                'method': 'first original body overlap against conflict polygon',
                'time_window': 'full original trace', 'statistic': 'first',
                'reference': channel.name, 'value': observed['entry_delta_s'],
                'sample_window_s': [rows[0]['time_s'], rows[-1]['time_s']]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior highway-continuity analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
