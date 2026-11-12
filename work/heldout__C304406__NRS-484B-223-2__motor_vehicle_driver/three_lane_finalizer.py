"""Saved-only three-lane measurement from retained original sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_measurement import measure


PREFIX = 'heldout__C304406__NRS-484B-223-2__motor_vehicle_driver__'
SUFFIXES = {'right_baseline', 'extreme_left', 'center_default',
            'center_passing_clear', 'center_passing_occluded',
            'center_passing_near_traffic', 'center_left_turn',
            'center_allocated_posted', 'center_allocated_unposted'}


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_three_lane_sources(frames_path, context_path):
    return measure(frames_path, context_path)


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    case_id = config.get('selected_case_id')
    if (case_id not in {PREFIX + name for name in SUFFIXES} or
            config.get('law_id') != 'NRS-484B-223-2' or
            config.get('cell_id') != 'C304406' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('Wrong exact three-lane case identity')
    frames_path, frames_sha = _source(root, 'three_lane_frames.jsonl')
    context_path, context_sha = _source(root, 'three_lane_context.json')
    map_path, map_sha = _source(root, 'three_lane_map_readback.json')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    video_path, video_sha = _source(root, 'video_frames.jsonl')
    frames, trace, video = map(_rows, (frames_path, trace_path, video_path))
    if not frames or len(frames) != len(trace) or len(frames) != len(video):
        raise ValueError('Original three-lane frame-map/source length differs')
    for index, (body, motion, image) in enumerate(zip(frames, trace, video)):
        identity = body['frame'], body['time_s']
        if ((motion.get('frame'), motion.get('time_s')) != identity or
                (image.get('carla_frame'), image.get('time_s')) != identity or
                image.get('video_frame') != index):
            raise ValueError('Original three-lane frame-map/source join differs')
    readback = json.loads(map_path.read_text())
    if (readback.get('road_id') != frames[0].get('road_id') or
            not readback.get('map_markings_verified') or
            set(readback.get('lane_ids', {})) != {'right', 'center', 'extreme_left'}):
        raise ValueError('Original three-lane map/marking readback differs')
    measured = measure_three_lane_sources(frames_path, context_path)
    measured['sources'].update({'three_lane_map_readback.json': map_sha,
                                'trace.jsonl': trace_sha,
                                'video_frames.jsonl': video_sha})
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'three_lane_observation': {
                'method': 'measure_three_lane_sources',
                'value': measured, 'sources': measured['sources']}},
            'limitations': ['Map marking readback does not prove physical paint visibility, safe passing distance, posted sign or legal lane status.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected three-lane recording description missing')
    measured = report['measurements']['three_lane_observation']['value']
    observations = measured['observations']
    channel = root / 'three_lane_observation.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived three-lane channel')
    channel.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                           'value': row['body_lane_overlap_fraction']}) + '\n'
                               for row in observations))
    evidence = [{'name': 'three_lane_observation', 'unit': 'body area fraction',
                 'reference': channel.name, 'sha256': sha256(channel.read_bytes()).hexdigest()},
                {'name': 'three_lane_map_readback', 'unit': 'mapped lane geometry',
                 'reference': 'three_lane_map_readback.json',
                 'sha256': sha256((root / 'three_lane_map_readback.json').read_bytes()).hexdigest()}]
    requested_lane = ('right' if report['case_id'].endswith('__right_baseline') else
                      'extreme_left' if report['case_id'].endswith('__extreme_left') else
                      'center')
    return {'case_id': report['case_id'],
            'measured_values': {'three_lane_observation': measured},
            'target_checks': [{'target': 'three marked mapped lanes and selected body occupancy',
                'requested': True,
                'measured': {'maximum_extreme_left_body_overlap': max(
                    row['body_lane_overlap_fraction']['extreme_left'] for row in observations),
                    'maximum_center_body_overlap': max(
                    row['body_lane_overlap_fraction']['center'] for row in observations)},
                'method': 'original map lane polygons and ego body polygons',
                'tolerance': None, 'matched': False,
                'physical_cause_confirmed': False,
                'cause_evidence': 'Saved source geometry; physical markings and behavior pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved three-lane observation complete; physical and legal judgments unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': evidence,
            'realized_observables': {'three_lane_observation': {
                'unit': 'body area fraction',
                'method': 'original 20 Hz lane polygon/body join',
                'time_window': 'all original frames', 'statistic': 'max',
                'reference': channel.name,
                'value': max(row['body_lane_overlap_fraction'][requested_lane]
                             for row in observations),
                'sample_window_s': [observations[0]['time_s'], observations[-1]['time_s']]}},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior three-lane analysis')
    report = analyze(args.attempt)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
