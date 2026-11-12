"""Saved-only right-half observation, joined to original Native trace and frames."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from right_half_measurement import measure


CASE_SUFFIXES = ('baseline_right_east', 'baseline_right_west', 'unexcepted_left',
                 'passing_same_direction', 'right_half_closed', 'three_lane',
                 'posted_one_way', 'insufficient_width')
CASE_PREFIX = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__'


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_right_half(path):
    """Derive the case measurement from retained original directed footprints."""
    return measure(path)


def measure_passing(root):
    from passing_source_audit import audit
    return audit(root)


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('selected_case_id', '')
    if case_id not in {CASE_PREFIX + suffix for suffix in CASE_SUFFIXES} or (
            config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-200-1', 'C125714', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact right-half finalizer identity')
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    original_path, original_sha = _source(root, 'directed_roadway_footprints.jsonl')
    mapping, trace, original = _rows(map_path), _rows(trace_path), _rows(original_path)
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(original):
        raise ValueError('Original right-half source/frame-map length differs')
    for index, (video, motion, roadway) in enumerate(zip(mapping, trace, original)):
        frame, time_s = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or motion.get('frame') != frame or
                motion.get('time_s') != time_s or roadway.get('frame') != frame or
                roadway.get('time_s') != time_s):
            raise ValueError('Original right-half source/frame-map join failed')
    measured = measure_right_half(original_path)
    passing_path, passing_sha = _source(root, 'passing_actors.jsonl')
    passing = measure_passing(root)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'passing_actor_order': {
                'method': 'measure_passing', 'value': passing,
                'sources': {'passing_actors.jsonl': passing_sha,
                            'directed_roadway_footprints.jsonl': original_sha,
                            'video_frames.jsonl': map_sha, 'trace.jsonl': trace_sha}},
                'right_half_occupancy': {
                'method': 'measure_right_half', 'value': measured,
                'sources': {'video_frames.jsonl': map_sha, 'trace.jsonl': trace_sha,
                            'directed_roadway_footprints.jsonl': original_sha}}},
            'limitations': ['Mapped adjacent-lane boundary and diagnostic CPU sources do not establish median-opening geometry, legal width, exception or physical visibility.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    return report


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected right-half recording description missing')
    value = report['measurements']['right_half_occupancy']['value']
    frames = value['observations']
    channel = root / 'right_half_offset_m.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived right-half channel')
    channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['body_min_right_offset_m']}) + '\n' for row in frames))
    minimum = value['minimum_body_right_offset_m']
    result = {'case_id': report['case_id'],
            'measured_values': {'right_half_occupancy': value},
            'target_checks': [{'target': 'measured directed right-half occupancy',
                               'requested': 'retained full-body lateral offsets',
                               'measured': minimum,
                               'method': 'original Native body corners and directed center boundary',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Original directed geometry joined to frame map; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved right-half measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [{'name': 'right_half_offset_m', 'unit': 'm',
                                    'reference': 'right_half_offset_m.jsonl',
                                    'sha256': sha256(channel.read_bytes()).hexdigest()}],
            'realized_observables': {'right_half_offset_m': {
                'unit': 'm', 'method': 'original Native directed full-body lateral offset',
                'time_window': 'all original frames', 'statistic': 'min',
                'reference': 'right_half_offset_m.jsonl', 'value': minimum,
                'sample_window_s': [frames[0]['time_s'], frames[-1]['time_s']]}},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
    if 'passing_actor_order' in report['measurements']:
        passing = report['measurements']['passing_actor_order']['value']
        path = root / 'passing_relative_longitudinal_m.jsonl'
        if path.exists():
            raise ValueError('Retain prior derived passing channel')
        path.write_text(''.join(json.dumps({'frame': frame, 'time_s': index*.05,
                                           'value': value}) + '\n'
                                for index, (frame, value) in enumerate(zip(
                                    passing['frames'], passing['relative_longitudinal_m']))))
        result['measured_values']['passing_actor_order'] = passing
        result['recording_evidence'].append({'name': 'passing_relative_longitudinal_m',
            'unit': 'm', 'reference': path.name,
            'sha256': sha256(path.read_bytes()).hexdigest()})
        result['realized_observables']['passing_relative_longitudinal_m'] = {
            'unit': 'm', 'method': 'original actor positions projected on directed road',
            'time_window': 'all original frames', 'statistic': 'behind_to_ahead',
            'reference': path.name, 'value': passing['relative_longitudinal_m'][-1],
            'sample_window_s': [0, (len(passing['frames'])-1)*.05]}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior right-half analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
