"""Saved-only finalization for a compatible opposing-left exact case."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from opposing_left_measurement import measure_opposing_left as _measure_opposing_left
from opposing_left_runner import check_config


def measure_opposing_left(root):
    return _measure_opposing_left(root)


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
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    participant_path, participant_sha = _source(root, 'opposing_left_participants.jsonl')
    context_path, context_sha = _source(root, 'opposing_left_context.json')
    mapping, trace, participants = (_rows(path) for path in
                                    (map_path, trace_path, participant_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Opposing-left original source/frame-map length differs')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (participant.get('frame'), participant.get('time_s')) != identity):
            raise ValueError('Opposing-left original source/frame-map join failed')
    observed = measure_opposing_left(root)
    observed['sources']['trace.jsonl'] = trace_sha
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {'opposing_left_observation': observed},
            'limitations': ['Original route and body motion do not establish a legal exception or physical completion.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected opposing-left recording description missing')
    observed = report['measurements']['opposing_left_observation']['value']
    return {'case_id': config['selected_case_id'],
            'measured_values': {'opposing_left_observation': observed},
            'target_checks': [{'target': 'connected opposite approach and leftward turn',
                'requested': True,
                'measured': {'approach_heading_dot': observed['approach_heading_dot'],
                             'planned_left_cross': observed['planned_left_cross'],
                             'observed_turn_heading_change_rad': observed['observed_turn_heading_change_rad']},
                'method': 'original Native route and body heading join',
                'tolerance': None, 'matched': False,
                'physical_cause_confirmed': False,
                'cause_evidence': 'Original Native source; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved opposing-left measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [
                {'name': 'opposing_left_context', 'unit': 'structured route',
                 'reference': 'opposing_left_context.json',
                 'sha256': sha256((root / 'opposing_left_context.json').read_bytes()).hexdigest()},
                {'name': 'opposing_left_participants', 'unit': 'm and rad',
                 'reference': 'opposing_left_participants.jsonl',
                 'sha256': sha256((root / 'opposing_left_participants.jsonl').read_bytes()).hexdigest()}],
            'realized_observables': {'turn_heading_change': {
                'unit': 'rad', 'method': 'first to last original turning actor heading',
                'time_window': 'full original trace', 'statistic': 'difference',
                'reference': 'opposing_left_participants.jsonl',
                'value': observed['observed_turn_heading_change_rad'],
                'sample_window_s': [0, (observed['frames'] - 1) / 20]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior opposing-left analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
