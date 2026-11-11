"""Saved-only U-turn analysis from retained Native frame and actor sources."""

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from u_turn_measurement import measure


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_original_u_turn(motion_path, context_path):
    return measure(motion_path, context_path)


def measure_mapped_device(device_path, context_path):
    source = json.loads(Path(device_path).read_text())
    context = json.loads(Path(context_path).read_text())
    value = source.get('mapped_no_u_turn_device')
    if (not isinstance(value, dict) or not value.get('landmark_id') or
            value.get('road_id') != context.get('approach_road_id') or
            not isinstance(value.get('source_fields'), dict)):
        raise ValueError('Mapped no-U-turn landmark source differs')
    distance = value.get('distance_to_approach_m')
    if type(distance) not in (int, float) or not isfinite(distance) or distance > 30 or distance < 0:
        raise ValueError('Mapped no-U-turn landmark distance invalid')
    if any(value.get(key) is not None for key in
           ('official_device_status', 'governing_lane_status',
            'pixel_visibility_status')):
        raise ValueError('Unreviewed mapped landmark cannot claim official or visible status')
    label = ' '.join(str(x) for x in value['source_fields'].values()).lower().replace('_', ' ').replace('-', ' ')
    if not any(marker in label for marker in
               ('no u turn', 'u turn prohibited', 'u turn forbidden')):
        raise ValueError('Mapped source does not describe no-U-turn device')
    return value


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config = json.loads(_required(root, 'config.json')[0].read_text())
    case_id = config.get('selected_case_id')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-403-1', 'C230627', 'motor_vehicle_driver') or not (
            isinstance(case_id, str) and case_id.startswith(
                'heldout__C230627__NRS-484B-403-1__motor_vehicle_driver__')):
        raise ValueError('Wrong C230627 exact U-turn identity')
    paths = {name: _required(root, name) for name in (
        'u_turn_motion.jsonl', 'u_turn_context.json', 'video_frames.jsonl',
        'trace.jsonl')}
    motion = _rows(paths['u_turn_motion.jsonl'][0])
    mapping = _rows(paths['video_frames.jsonl'][0])
    trace = _rows(paths['trace.jsonl'][0])
    if not motion or len(motion) != len(mapping) or len(motion) != len(trace):
        raise ValueError('Original U-turn frame inventory differs')
    ego_id = motion[0].get('ego_id')
    if type(ego_id) is not int:
        raise ValueError('Original U-turn ego identity missing')
    for index, (row, frame, capture) in enumerate(zip(motion, mapping, trace)):
        identity = row.get('frame'), row.get('time_s')
        if (row.get('ego_id') != ego_id or frame.get('video_frame') != index or
                (frame.get('carla_frame'), frame.get('time_s')) != identity or
                (capture.get('frame'), capture.get('time_s')) != identity):
            raise ValueError('Original U-turn frame or ego join differs')
    value = measure_original_u_turn(paths['u_turn_motion.jsonl'][0],
                                    paths['u_turn_context.json'][0])
    source_hashes = {name: item[1] for name, item in paths.items()}
    measurements = {'u_turn_observation': {
        'method': 'measure_original_u_turn', 'value': value,
        'sources': source_hashes}}
    if case_id.endswith('__prohibition_403_2'):
        device_path, device_hash = _required(root, 'u_turn_device.json')
        measurements['mapped_no_u_turn_device'] = {
            'method': 'measure_mapped_device',
            'value': measure_mapped_device(device_path, paths['u_turn_context.json'][0]),
            'sources': {'u_turn_device.json': device_hash,
                        'u_turn_context.json': paths['u_turn_context.json'][1]}}
    if write_channels:
        channel = root / 'u_turn_observation.jsonl'
        if channel.exists():
            raise ValueError('Retain prior derived U-turn channel')
        channel.write_text(''.join(json.dumps({
            'frame': observation['frame'], 'time_s': observation['time_s'],
            'value': {'heading_change_deg': observation['heading_change_deg'],
                      'surface_gaps_m': observation['surface_gaps_m']}},
            allow_nan=False) + '\n' for observation in value['observations']))
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': measurements,
            'limitations': ['Source-shaped CPU media does not establish physical U-turn completion, sight lines, cited prohibition applicability or legal safety.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config['case']['recording_description']
    value = report['measurements']['u_turn_observation']['value']
    channel = 'u_turn_observation.jsonl'
    evidence = [{'name': 'u_turn_observation', 'unit': 'structured',
                 'reference': channel, 'sha256': _required(root, channel)[1]},
                {'name': 'participant_roles', 'unit': 'structured context',
                 'reference': 'u_turn_context.json',
                 'sha256': _required(root, 'u_turn_context.json')[1]}]
    if report['case_id'].endswith('__prohibition_403_2'):
        evidence.append({'name': 'mapped_no_u_turn_device',
                         'unit': 'structured context',
                         'reference': 'u_turn_device.json',
                         'sha256': _required(root, 'u_turn_device.json')[1]})
    return {'case_id': report['case_id'],
            'measured_values': {key: item['value'] for key, item in
                                report['measurements'].items()},
            'target_checks': [{'target': 'whole U-turn and surrounding-user safety',
                               'requested': 'retained original motion and context',
                               'measured': value['net_heading_change_deg'],
                               'method': 'joined Native 20 Hz actor bodies, yaw and speed',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Saved source joined; physical and legal outcomes unverified'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved U-turn measurements complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {'net_heading_change_deg': {
                'unit': 'degrees', 'method': 'original ego yaw difference',
                'time_window': 'all original frames', 'statistic': 'last',
                'reference': channel,
                'value': value['net_heading_change_deg'],
                'sample_window_s': [value['observations'][0]['time_s'],
                                    value['observations'][-1]['time_s']]}},
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
        raise ValueError('Retain prior U-turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
