"""Saved-only headlamp following analysis with original frame and context joins."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from headlamp_follow_measurement import measure


CASE_SUFFIXES = ('night_299_upper', 'night_299_other', 'night_300_upper',
                 'night_301_upper', 'day_299_upper', 'shoulder_299_upper')
CASE_PREFIX = 'heldout__C178038__NRS-484D-215-2__motor_vehicle_driver__'


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
    case_id = config.get('selected_case_id', '')
    if case_id not in {CASE_PREFIX + suffix for suffix in CASE_SUFFIXES} or (
            config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484D-215-2', 'C178038', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact headlamp finalizer identity')
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    footprint_path, _ = _source(root, 'following_footprints.jsonl')
    lamp_path, _ = _source(root, 'headlamp_readbacks.jsonl')
    context_path, _ = _source(root, 'lighting_context.json')
    mapping, trace, footprints, lamps = (_rows(path) for path in
                                        (map_path, trace_path, footprint_path, lamp_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(footprints) or len(mapping) != len(lamps):
        raise ValueError('Original headlamp source/frame-map length differs')
    for index, (video, motion, footprint, lamp) in enumerate(zip(mapping, trace, footprints, lamps)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (footprint.get('frame'), footprint.get('time_s')) != identity or
                (lamp.get('frame'), lamp.get('time_s')) != identity):
            raise ValueError('Original headlamp source/frame-map join failed')
    observed = measure(footprint_path, lamp_path, context_path)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'headlamp_following_observation': {
                'method': 'measure', 'value': observed,
                'sources': {**observed['sources'], 'video_frames.jsonl': map_sha,
                            'trace.jsonl': trace_sha}}},
            'limitations': ['Original readbacks and geometry do not establish permissible beam distribution, safe illumination distance or physical visibility.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected headlamp recording description missing')
    observed = report['measurements']['headlamp_following_observation']['value']
    frames = observed['observations']
    channel = root / 'headlamp_gap_ft.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived headlamp channel')
    channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['surface_gap_ft']}) + '\n' for row in frames))
    minimum = observed['minimum_surface_gap_ft']
    return {'case_id': report['case_id'],
            'measured_values': {'headlamp_following_observation': observed},
            'target_checks': [{'target': 'measured following separation in feet',
                               'requested': config.get('target_gap_ft'),
                               'measured': minimum,
                               'method': 'original Native ground-body polygon distance',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Original footprint/lamp readbacks joined to frame map; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved headlamp measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [{'name': 'headlamp_gap_ft', 'unit': 'ft',
                                    'reference': 'headlamp_gap_ft.jsonl',
                                    'sha256': sha256(channel.read_bytes()).hexdigest()}],
            'realized_observables': {'headlamp_gap_ft': {
                'unit': 'ft', 'method': 'original Native body polygon distance',
                'time_window': 'all original frames', 'statistic': 'min',
                'reference': 'headlamp_gap_ft.jsonl', 'value': minimum,
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
        raise ValueError('Retain prior headlamp analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
