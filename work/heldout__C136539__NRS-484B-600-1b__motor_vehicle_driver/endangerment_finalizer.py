"""Saved-only exposure analysis joined to original Native trace and video frames."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from endangerment_measurement import measure


def measure_exposure(source_path):
    """Named saved measurement entrypoint for the selected requirement."""
    return measure(source_path)


def _read_source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _read_source(root, 'config.json')
    config = json.loads(config_path.read_text())
    case = config.get('selected_case_id', '')
    if not case.startswith('heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver__') or (
            config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1b', 'C136539', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact exposure finalizer identity')
    frame_path, frame_sha = _read_source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _read_source(root, 'trace.jsonl')
    source_path, source_sha = _read_source(root, 'exposed_actor_footprints.jsonl')
    frames, trace, source = _rows(frame_path), _rows(trace_path), _rows(source_path)
    if not frames or len(frames) != len(trace) or len(frames) != len(source):
        raise ValueError('Original exposure source/frame-map length differs')
    for index, (frame, motion, exposure) in enumerate(zip(frames, trace, source)):
        if (frame.get('video_frame') != index or
                motion.get('frame') != frame.get('carla_frame') or
                exposure.get('frame') != frame.get('carla_frame') or
                motion.get('time_s') != frame.get('time_s') or
                exposure.get('time_s') != frame.get('time_s')):
            raise ValueError('Original exposure source/frame-map join failed')
    observed = measure_exposure(source_path)
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'person_or_property_exposure': {
                'method': 'measure_exposure', 'value': observed,
                'sources': {'video_frames.jsonl': frame_sha, 'trace.jsonl': trace_sha,
                            'exposed_actor_footprints.jsonl': source_sha}}},
            'limitations': ['Radial closing time is an engineering proxy; no legal endangerment threshold or physical visibility is established.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected exposure recording description missing')
    observed = report['measurements']['person_or_property_exposure']['value']
    frames = observed['observations']
    channel = root / 'exposure_gap_m.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived exposure channel')
    channel.write_text(''.join(json.dumps({
        'frame': frame['frame'], 'time_s': frame['time_s'],
        'value': frame['surface_gap_m']}) + '\n' for frame in frames))
    minimum = observed['minimum_surface_gap_m']
    return {'case_id': report['case_id'],
            'measured_values': {'person_or_property_exposure': observed},
            'target_checks': [{'target': 'measured original participant/property exposure',
                               'requested': 'retained subject/exposed body motion',
                               'measured': minimum,
                               'method': 'original Native polygon surface gap',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Source joined to original frame map; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved exposure measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [{'name': 'exposure_gap_m', 'unit': 'm',
                                    'reference': 'exposure_gap_m.jsonl',
                                    'sha256': sha256(channel.read_bytes()).hexdigest()}],
            'realized_observables': {'exposure_gap_m': {
                'unit': 'm', 'method': 'original Native body polygon distance',
                'time_window': 'all original frames', 'statistic': 'min',
                'reference': 'exposure_gap_m.jsonl', 'value': minimum,
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
        raise ValueError('Retain prior exposure analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
