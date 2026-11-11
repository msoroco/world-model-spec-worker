"""Saved-only source-joined analysis for the first bicycle signal case."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from rider_turn_signal_measurement import measure


CASE_ID = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_signal_once'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required original source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    if (config.get('selected_case_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            CASE_ID, 'NRS-484B-768-1', 'C111588', 'cycle_or_scooter_operator'):
        raise ValueError('Wrong exact rider finalizer identity')
    paths = {}
    hashes = {}
    for name in ('video_frames.jsonl', 'trace.jsonl', 'rider_motion.jsonl',
                 'rider_arm_bones.jsonl', 'rider_signal_review.jsonl',
                 'rider_context.json', *CAMERAS):
        paths[name], hashes[name] = _source(root, name)
    mapping, trace, motion, bones, reviews = (_rows(paths[name]) for name in
        ('video_frames.jsonl', 'trace.jsonl', 'rider_motion.jsonl',
         'rider_arm_bones.jsonl', 'rider_signal_review.jsonl'))
    if not mapping or len({len(rows) for rows in (mapping, trace, motion, bones, reviews)}) != 1:
        raise ValueError('Original rider source/frame-map length differs')
    rider_id = json.loads(paths['rider_context.json'].read_text()).get('rider_id')
    for index, (video, motion_row, rider_row, bone, review) in enumerate(
            zip(mapping, trace, motion, bones, reviews)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion_row.get('frame'), motion_row.get('time_s')) != identity or
                (rider_row.get('frame'), rider_row.get('time_s')) != identity or
                (bone.get('frame'), bone.get('time_s')) != identity or
                (review.get('frame'), review.get('time_s')) != identity or
                bone.get('rider_id') != rider_id or
                rider_row.get('rider_id') != rider_id):
            raise ValueError('Original rider source/frame-map join failed')
    observed = measure(paths['rider_motion.jsonl'], paths['rider_signal_review.jsonl'],
                       paths['rider_context.json'], paths['driver_reference.mkv'])
    return {'format': 'worker-analysis-report', 'case_id': CASE_ID,
            'measurements': {'rider_turn_signal_observation': {
                'method': 'measure', 'value': observed,
                'sources': {**observed['sources'], **hashes}}},
            'limitations': ['Bone readback and source-video review do not establish an appropriate legal signal or reasonable safety.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Rider recording description missing')
    observed = report['measurements']['rider_turn_signal_observation']['value']
    channel = root / 'rider_signal_event.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived rider signal channel')
    channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['visible_signal'], 'signal_type': row['signal_type']}) + '\n'
        for row in observed['observations']))
    frames = observed['observations']
    return {'case_id': CASE_ID,
            'measured_values': {'rider_turn_signal_observation': observed},
            'target_checks': [{'target': 'one visible signal before measured turn onset',
                               'requested': 'one pre-turn signal',
                               'measured': observed['pre_turn_visible_signal_frames'],
                               'method': 'original source-video frame review joined to rider yaw',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Original bone and video sources joined; physical rider/signal review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved rider signal measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': list(CAMERAS),
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [{'name': 'rider_signal_event', 'unit': 'bool',
                                    'reference': 'rider_signal_event.jsonl',
                                    'sha256': sha256(channel.read_bytes()).hexdigest()}],
            'realized_observables': {'rider_signal_event': {
                'unit': 'bool', 'method': 'source-video frame review',
                'time_window': 'all original frames', 'statistic': 'pre-turn visible frames',
                'reference': 'rider_signal_event.jsonl',
                'value': observed['pre_turn_visible_signal_frames'],
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
        raise ValueError('Retain prior rider analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
