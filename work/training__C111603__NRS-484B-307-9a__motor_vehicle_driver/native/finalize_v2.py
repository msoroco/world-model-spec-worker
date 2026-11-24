"""Saved-only 9(a) CPU diagnostic from retained actor and signal rows."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decoded(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams',
        'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        text=True, capture_output=True, timeout=120)
    if probe.returncode or probe.stdout.strip() != '600':
        raise ValueError('Complete source camera decode required: ' + path.name)


def measure(root):
    native_path = required(root, 'native-raw-actors.jsonl')
    map_path = required(root, 'video_frames.jsonl')
    native, mapping = rows(native_path), rows(map_path)
    if len(native) != 600 or len(mapping) != 600:
        raise ValueError('600 Native and source-video samples required')
    for name in CAMERAS:
        decoded(required(root, name + '.mkv'))
    headings = []
    for index, (actor, frame) in enumerate(zip(native, mapping)):
        if (actor.get('frame') != index or frame.get('video_frame') != index or
                actor.get('native_frame') != frame.get('native_frame') or
                abs(actor.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6):
            raise ValueError('Native/source camera frame join differs')
        if not str(actor.get('red_state', '')).endswith('Red'):
            raise ValueError('Observed steady red source missing')
        if not str(actor.get('arrow_state', '')).endswith('Green'):
            raise ValueError('Observed green arrow-head source missing')
        if actor.get('red_actor_id') == actor.get('arrow_actor_id'):
            raise ValueError('Native signal heads collapsed')
        if not isinstance(actor.get('ego', {}).get('center_native_xyz_m'), list):
            raise ValueError('Observed ego pose missing')
        if not isinstance(actor.get('other_vehicle', {}).get('center_native_xyz_m'), list):
            raise ValueError('Observed other vehicle pose missing')
        headings.append(actor['ego']['yaw_deg'])
    turn = abs((headings[-1] - headings[0] + 180) % 360 - 180)
    return {'format': 'c111603-arrow-saved-cpu-v2', 'frames': 600,
        'observed_steady_red_frames': 600, 'observed_green_head_frames': 600,
        'observed_heading_change_deg': round(turn, 4),
        'other_vehicle_actor_id': native[0]['other_vehicle']['actor_id'],
        'arrow_pixels_verified': False, 'governing_direction_verified': False,
        'other_traffic_lawfulness_verified': False,
        'native_provenance': False}


def finalize(attempt, output):
    root = Path(attempt).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    measured = measure(root)
    required(root, 'trace.jsonl')
    required(root, 'capture/evidence.jsonl')
    stream = root / 'native-actor-signal-observations.jsonl'
    with stream.open('w') as file:
        for actor in rows(required(root, 'native-raw-actors.jsonl')):
            value = {'ego': actor['ego'], 'other_vehicle': actor['other_vehicle'],
                     'red_state': actor['red_state'], 'arrow_state': actor['arrow_state']}
            file.write(json.dumps({'time_s': actor['time_s'], 'value': value}) + '\n')
    result = {'case_id': config['case_id'], 'measured_values': {'arrow_movement': measured},
        'target_checks': [{'target': 'right_turn_heading_change', 'requested': True,
            'measured': measured['observed_heading_change_deg'] >= 60,
            'method': 'saved Native heading samples',
            'tolerance': 0, 'matched': measured['observed_heading_change_deg'] >= 60,
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-raw-actors.jsonl']}],
        'setup_confirmed': True, 'behavior_attempted': True, 'maneuver_completed': True,
        'termination_reason': 'full synthetic diagnostic duration',
        'physical_failure_flags': ['directional_arrow_pixels_and_governance_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'native_actor_signal_samples',
            'unit': 'structured', 'reference': stream.name}],
        'realized_observables': {'heading_change_deg': {'value': measured['observed_heading_change_deg'],
            'unit': 'deg', 'method': 'saved Native heading samples',
            'time_window': '30 s diagnostic', 'statistic': 'start_to_end',
            'reference': 'native-raw-actors.jsonl'}},
        'provenance_kind': 'synthetic_cpu', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111603-saved-analysis-v2', 'case_id': config['case_id'],
        'measurements': {'arrow_movement': {'method': 'measure', 'value': measured,
            'sources': {'native-raw-actors.jsonl': sha(required(root, 'native-raw-actors.jsonl')),
                        'video_frames.jsonl': sha(required(root, 'video_frames.jsonl'))}}},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
