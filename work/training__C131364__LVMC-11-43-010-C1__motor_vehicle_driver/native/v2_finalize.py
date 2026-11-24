"""Recorded-only synthetic roundabout route diagnostic; no physical claim."""
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


def measure(root):
    config = json.loads(required(root, 'config.json').read_text())
    route_path = required(root, 'roundabout-track.jsonl')
    frame_path = required(root, 'video_frames.jsonl')
    route, frames = rows(route_path), rows(frame_path)
    if len(route) != len(frames) or len(route) != 600:
        raise ValueError('600 route and camera-frame joins required')
    for camera in CAMERAS:
        path = required(root, camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            capture_output=True, text=True, timeout=120)
        if probe.returncode or probe.stdout.strip() != '600':
            raise ValueError('Complete source camera decode required: ' + camera)
    phases = []
    lane = -1 if config['case_id'].endswith('witness_1') else -2
    for i, (point, frame) in enumerate(zip(route, frames)):
        if (point['frame'] != i or point['lane_id'] != lane or
                frame['video_frame'] != i or frame['native_frame'] != 1000 + i or
                abs(frame['time_s'] - point['time_s']) > 1e-6):
            raise ValueError('Source route/frame join differs at ' + str(i))
        if point['actual_exit_observed'] is not False or point['roundabout_verified'] is not False:
            raise ValueError('Authored source made a physical claim')
        phases.append(point['phase'])
    if not (phases[0] == 'entry' and 'circulation' in phases and phases[-1] == 'exit'):
        raise ValueError('Full entry/circulation/exit span required')
    return {'format': 'c131364-roundabout-saved-cpu-v2', 'frames': 600,
        'requested_lane_id': lane,
        'entry_frames': phases.count('entry'),
        'circulation_frames': phases.count('circulation'),
        'exit_frames': phases.count('exit'),
        'actual_exit_observed': False, 'physical_roundabout_verified': False,
        'lane_occupancy_observed': False, 'native_provenance': False}


def finalize(attempt, output):
    root = Path(attempt).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    measured = measure(root)
    stream = root / 'roundabout-route-observations.jsonl'
    with stream.open('w') as file:
        for point in rows(required(root, 'roundabout-track.jsonl')):
            file.write(json.dumps({'time_s': point['time_s'], 'value': point}) + '\n')
    result = {'case_id': config['case_id'], 'measured_values': {'lane_passage': measured},
        'target_checks': [{'target': 'authored_lane_route', 'requested': True,
            'measured': True, 'method': 'saved source route samples',
            'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': ['roundabout-track.jsonl']}],
        'setup_confirmed': True, 'behavior_attempted': True, 'maneuver_completed': True,
        'termination_reason': 'full synthetic diagnostic duration',
        'physical_failure_flags': ['roundabout_and_lane_occupancy_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'roundabout_route', 'unit': 'structured',
            'reference': stream.name}],
        'realized_observables': {'authored_lane_id': {'value': measured['requested_lane_id'],
            'unit': 'OpenDRIVE lane id', 'method': 'saved source route samples',
            'time_window': '30 s diagnostic', 'statistic': 'constant',
            'reference': 'roundabout-track.jsonl'}},
        'provenance_kind': 'synthetic_cpu', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c131364-saved-analysis-v2', 'case_id': config['case_id'],
        'measurements': {'lane_passage': {'method': 'measure', 'value': measured,
            'sources': {'roundabout-track.jsonl': sha(required(root, 'roundabout-track.jsonl')),
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
