"""Saved-only overtake analysis with original frame joins and canonical result."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from overtake_measurement import measure


CASE_SUFFIXES = ('left_pass_wide', 'left_pass_narrow',
                 'return_before_clear', 'return_after_clear')
CASE_PREFIX = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__'


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_overtake(source):
    """Bind the selected statutory measurement to the retained body source."""
    return measure(source)


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('selected_case_id', '')
    if case_id not in {CASE_PREFIX + suffix for suffix in CASE_SUFFIXES} or (
            config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-207-1', 'C110161', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact overtake finalizer identity')
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    footprint_path, _ = _source(root, 'participant_footprints.jsonl')
    mapping, trace, footprints = (_rows(path) for path in
                                  (map_path, trace_path, footprint_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(footprints):
        raise ValueError('Original overtake source/frame-map length differs')
    for index, (video, motion, footprint) in enumerate(zip(mapping, trace, footprints)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (footprint.get('frame'), footprint.get('time_s')) != identity):
            raise ValueError('Original overtake source/frame-map join failed')
    observed = measure_overtake(footprint_path)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'overtake_observation': {
                'method': 'measure_overtake', 'value': observed,
                'sources': {'participant_footprints.jsonl': observed['source_sha256'],
                            'video_frames.jsonl': map_sha, 'trace.jsonl': trace_sha}}},
            'limitations': ['Measured left pass and right return do not establish a legal safe distance or safely clear judgment.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected overtake recording description missing')
    observed = report['measurements']['overtake_observation']['value']
    left_channel = root / 'left_pass_clearance_m.jsonl'
    return_channel = root / 'return_clearance_m.jsonl'
    if left_channel.exists() or return_channel.exists():
        raise ValueError('Retain prior derived overtake channel')
    left_channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['left_side_gap_m']}) + '\n'
        for row in observed['observations']))
    return_channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['ahead_clearance_m']}) + '\n'
        for row in observed['observations']))
    frames = observed['observations']
    gap = observed['min_abreast_lateral_gap_m']
    return_gap = observed['clearance_at_first_return_m']
    return {'case_id': report['case_id'],
            'measured_values': {'overtake_observation': observed},
            'target_checks': [
                {'target': 'minimum left-body clearance while abreast',
                 'requested': config.get('target_left_gap_m'), 'measured': gap,
                 'method': 'original Native body projection on road-left axis',
                 'tolerance': None, 'matched': False,
                 'physical_cause_confirmed': False,
                 'cause_evidence': 'Original body/tangent source; physical review pending'},
                {'target': 'body clearance at first rightward return',
                 'requested': config.get('requested_return_clearance_m'),
                 'measured': return_gap,
                 'method': 'original Native longitudinal body projection',
                 'tolerance': None, 'matched': False,
                 'physical_cause_confirmed': False,
                 'cause_evidence': 'Original body/tangent source; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved overtake measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [
                {'name': 'left_pass_clearance_m', 'unit': 'm',
                 'reference': 'left_pass_clearance_m.jsonl',
                 'sha256': sha256(left_channel.read_bytes()).hexdigest()},
                {'name': 'return_clearance_m', 'unit': 'm',
                 'reference': 'return_clearance_m.jsonl',
                 'sha256': sha256(return_channel.read_bytes()).hexdigest()}],
            'realized_observables': {
                'left_pass_clearance_m': {'unit': 'm',
                    'method': 'original Native left-body projection',
                    'time_window': 'abreast original frames', 'statistic': 'min',
                    'reference': 'left_pass_clearance_m.jsonl', 'value': gap,
                    'sample_window_s': [frames[0]['time_s'], frames[-1]['time_s']]},
                'return_clearance_m': {'unit': 'm',
                    'method': 'original Native longitudinal body projection',
                    'time_window': 'first rightward return', 'statistic': 'first',
                    'reference': 'return_clearance_m.jsonl', 'value': return_gap,
                    'sample_window_s': [frames[0]['time_s'], frames[-1]['time_s']]}},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior overtake analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
