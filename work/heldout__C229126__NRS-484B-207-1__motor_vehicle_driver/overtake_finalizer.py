"""Saved-only original-source analysis for the C229126 pass comparisons."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from overtake_sequence import measure
from runner import check_config


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required original source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    config_path, config_sha = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    check_config(config)
    frame_path, frame_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    body_path, body_sha = _source(root, 'participant_footprints.jsonl')
    mapping, trace, body = (_rows(path) for path in
                            (frame_path, trace_path, body_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(body):
        raise ValueError('Original frame, trace and body source lengths differ')
    for index, (video, motion, footprint) in enumerate(zip(mapping, trace, body)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (footprint.get('frame'), footprint.get('time_s')) != identity):
            raise ValueError('Original frame, trace and body source join failed')
    observation = measure(body_path)
    return {'format': 'worker-analysis-report',
            'case_id': config['selected_case_id'],
            'measurements': {'overtake_sequence': {
                'method': 'measure original actor body, lane and speed rows',
                'value': observation,
                'sources': {'config.json': config_sha,
                            'video_frames.jsonl': frame_sha,
                            'trace.jsonl': trace_sha,
                            'participant_footprints.jsonl': body_sha}}},
            'limitations': ['Observed body gap and return timing do not decide statutory safe distance or safely clear.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected recording description missing')
    observation = report['measurements']['overtake_sequence']['value']
    samples = observation['samples']
    channels = (
        ('left_pass_clearance_m', 'left_gap_m'),
        ('return_clearance_m', 'longitudinal_clearance_m'),
    )
    evidence = []
    realized = {}
    for name, key in channels:
        path = root / (name + '.jsonl')
        if path.exists():
            raise ValueError('Retain prior derived overtake channel')
        path.write_text(''.join(json.dumps({'frame': row['frame'],
                                            'time_s': row['time_s'],
                                            'value': row[key]}) + '\n'
                                for row in samples))
        value = (observation['minimum_abreast_left_gap_m'] if name == 'left_pass_clearance_m'
                 else observation['body_clearance_at_first_return_m'])
        evidence.append({'name': name, 'unit': 'm', 'reference': path.name,
                         'sha256': sha256(path.read_bytes()).hexdigest()})
        realized[name] = {'unit': 'm', 'method': 'original Native actor body projection',
                          'time_window': 'complete source sequence',
                          'statistic': 'minimum abreast' if name == 'left_pass_clearance_m'
                                       else 'first rightward return',
                          'reference': path.name, 'value': value,
                          'sample_window_s': [samples[0]['time_s'], samples[-1]['time_s']]}
    return {'case_id': report['case_id'],
            'measured_values': {'overtake_sequence': observation},
            'target_checks': [
                {'target': 'minimum left-body clearance while abreast',
                 'requested': config['target_left_gap_m'],
                 'measured': observation['minimum_abreast_left_gap_m'],
                 'method': 'original body projection on road-left axis',
                 'tolerance': None, 'matched': False,
                 'physical_cause_confirmed': False,
                 'cause_evidence': 'Original source; physical review pending'},
                {'target': 'body clearance at first rightward return',
                 'requested': config['requested_return_clearance_m'],
                 'measured': observation['body_clearance_at_first_return_m'],
                 'method': 'original longitudinal body projection',
                 'tolerance': None, 'matched': False,
                 'physical_cause_confirmed': False,
                 'cause_evidence': 'Original source; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved body measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': evidence,
            'realized_observables': realized,
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
