"""Source-bound saved pass analysis for C102951; never makes a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_pass import measure
from measure_response import measure_response

REQUIRED = ('native-observed.jsonl', 'road-readback.json', 'video_frames.jsonl',
            'trace.jsonl', 'capture/evidence.jsonl', 'capture/manifest.json')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('st.sight_distance', 'rel.visible', 'kin.speed', 'native_actor_poses',
            'passing_response', 'ego_pose', 'measured_clear_oncoming_distance',
            'roadway_geometry', 'ego_and_overtaken_trajectories',
            'driver_eye_sightline', 'oncoming_trajectories',
            'approaching_vehicle_response', 'overtaken_vehicle_response',
            'pass_completion_and_interference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return path


def rows(path):
    return [json.loads(line) for line in source(path).read_text().splitlines() if line.strip()]


def measure_pass_observables(attempt):
    value = measure(attempt)
    return {'value': value, 'method': 'measure_pass_observables',
            'sources': {name: sha(source(Path(attempt) / name))
                        for name in ('native-observed.jsonl', 'road-readback.json')}}


def measure_response_observables(attempt):
    value = measure_response(attempt)
    return {'value': value, 'method': 'measure_response_observables',
            'sources': {name: sha(source(Path(attempt) / name))
                        for name in ('native-observed.jsonl', 'road-readback.json')}}


def verify_join(attempt, count):
    datasets = {name: rows(Path(attempt) / name) for name in
                ('native-observed.jsonl', 'video_frames.jsonl',
                 'trace.jsonl', 'capture/evidence.jsonl')}
    if any(len(value) != count for value in datasets.values()):
        raise ValueError('Saved source, trace and camera-frame counts differ')
    for index, (observed, frame, trace, evidence) in enumerate(zip(*datasets.values())):
        native = observed['native_frame']
        time = observed['time_s']
        if (observed['frame'] != index or frame['video_frame'] != index
                or frame['native_frame'] != native or frame['carla_frame'] != native
                or trace['frame'] != native or evidence['original_frame'] != native
                or any(abs(float(value) - time) > 1e-4 for value in
                       (frame['time_s'], trace['time_s'], evidence['recording_time_s']))):
            raise ValueError('Original Native, trace and camera-frame join differs')
    capture = json.loads(source(Path(attempt) / 'capture/manifest.json').read_text())
    if capture.get('frames') != count or not capture.get('extraction_confirmed'):
        raise ValueError('Original capture frame coverage incomplete')
    return {'frames': count, 'first_native_frame': datasets['video_frames.jsonl'][0]['native_frame'],
            'last_native_frame': datasets['video_frames.jsonl'][-1]['native_frame'],
            'source_hashes': {name: sha(Path(attempt) / name) for name in REQUIRED}}


def decode_count(path):
    output = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                             '-select_streams', 'v:0', '-show_entries',
                             'stream=nb_read_frames', '-of',
                             'default=noprint_wrappers=1:nokey=1', str(source(path))],
                            capture_output=True, text=True, timeout=180, check=True)
    if not output.stdout.strip().isdigit():
        raise ValueError('Source camera frame count not decoded: ' + path.name)
    return int(output.stdout.strip())


def rebuild_channels(attempt, observed, frames):
    channel_dir = Path(attempt) / 'channels'
    if channel_dir.exists():
        raise ValueError('Derived channels were supplied by a fixture or old processing')
    channel_dir.mkdir()
    channels = {name: [] for name in CHANNELS}
    road = json.loads(source(Path(attempt) / 'road-readback.json').read_text())
    for row, frame in zip(observed, frames):
        time = row['time_s']
        values = {'st.sight_distance': row['driver_eye_clear_m'],
                  'rel.visible': row['sightline_visible'],
                  'kin.speed': row['ego_speed_mps'],
                  'native_actor_poses': {name: [row[name + '_x_m'], row[name + '_y_m']]
                                         for name in ('ego', 'oncoming', 'overtaken')},
                  'passing_response': {name: row[name + '_speed_mps']
                                       for name in ('oncoming', 'overtaken')},
                  'ego_pose': {'x_m': row['ego_x_m'], 'y_m': row['ego_y_m']},
                  'measured_clear_oncoming_distance': row['oncoming_x_m'] - row['ego_x_m'] - 4.4,
                  'roadway_geometry': {'lane_count': road['lane_count'],
                                       'travel_directions': road['travel_directions'],
                                       'centerline_y_m': road['centerline_y_m'],
                                       'highway_status_reviewed': road['highway_status_reviewed']},
                  'ego_and_overtaken_trajectories': {
                      'ego_xy_m': [row['ego_x_m'], row['ego_y_m']],
                      'overtaken_xy_m': [row['overtaken_x_m'], row['overtaken_y_m']]},
                  'driver_eye_sightline': {'source_proxy_clear_m': row['driver_eye_clear_m'],
                                           'source_flag_visible': row['sightline_visible'],
                                           'actual_driver_eye_reviewed': False},
                  'oncoming_trajectories': {'xy_m': [row['oncoming_x_m'], row['oncoming_y_m']],
                                            'speed_mps': row['oncoming_speed_mps']},
                  'approaching_vehicle_response': {'speed_mps': row['oncoming_speed_mps']},
                  'overtaken_vehicle_response': {'speed_mps': row['overtaken_speed_mps']},
                  'pass_completion_and_interference': {
                      'ego_body_left_of_center': row['ego_y_m'] > road['centerline_y_m'],
                      'oncoming_body_gap_m': row['oncoming_x_m'] - row['ego_x_m'] - 4.4,
                      'interference_judgment': None}}
        for name, value in values.items():
            channels[name].append(json.dumps({'time_s': time, 'native_frame': frame['native_frame'],
                                              'value': value}, allow_nan=False))
    for name, lines in channels.items():
        (channel_dir / (name + '.jsonl')).write_text('\n'.join(lines) + '\n')
    return sorted(channels)


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh source and output; do not rewrite an original')
    config = json.loads(source(attempt / 'config.json').read_text())
    if config.get('duration_s') != 30 or config.get('rate_hz') != 20:
        raise ValueError('Selected 600-frame capture contract differs')
    join = verify_join(attempt, 600)
    passing = measure_pass_observables(attempt)
    response = measure_response_observables(attempt)
    observed = rows(attempt / 'native-observed.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    derived = rebuild_channels(attempt, observed, frames)
    counts = {name: decode_count(attempt / (name + '.mkv')) for name in CAMERAS}
    if set(counts.values()) != {600}:
        raise ValueError('Four source cameras do not cover all 600 frames')
    description = config['recording_description']
    evidence = [{'name': channel['name'], 'unit': channel['unit'],
                 'reference': 'channels/' + channel['name'] + '.jsonl'}
                for channel in description['channels']]
    if any(not (attempt / item['reference']).is_file() for item in evidence):
        raise ValueError('Declared recorded channel was not derived')
    synthetic = passing['value']['source_kind'] == 'synthetic_cpu'
    result = {'case_id': config['case_id'],
              'measured_values': {'minimum_pre_return_oncoming_body_gap_m':
                                  passing['value']['minimum_pre_return_oncoming_body_gap_m'],
                                  'minimum_left_phase_driver_eye_clear_m':
                                  passing['value']['minimum_left_phase_driver_eye_clear_m']},
              'target_checks': [{'target': 'left-of-center passing attempt and full source review',
                                 'requested': config['distance_m'],
                                 'measured': passing['value']['entry_oncoming_body_gap_m'],
                                 'method': 'source-bound body gap at original left-of-center entry',
                                 'tolerance': None, 'matched': None,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['native-observed.jsonl', 'road-readback.json']}],
              'setup_confirmed': False, 'behavior_attempted': not synthetic,
              'maneuver_completed': False,
              'termination_reason': 'synthetic source processed' if synthetic else 'original source processed',
              'physical_failure_flags': ['synthetic_fixture_not_physical'] if synthetic else
                                        ['original_sightline_and_safe_operation_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {
                  'oncoming_body_gap': {'value': passing['value']['entry_oncoming_body_gap_m'],
                                        'unit': 'm', 'method': 'original body geometry',
                                        'reference': 'native-observed.jsonl',
                                        'time_window': 'left-of-center entry', 'statistic': 'body gap'}},
              'provenance_kind': 'synthetic_cpu_fixture' if synthetic else 'native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c102951-selected-saved-analysis-v1',
              'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
              'measurements': {'pass_observables': passing,
                               'response_observables': response},
              'source_join': join, 'derived_channels': derived,
              'source_camera_frames': counts,
              'safe_distance_judgment': None, 'interference_judgment': None,
              'legal_verdict': None,
              'scope': 'source-derived CPU compatibility only; original sightline and safe operation require independent review'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == '__main__':
    main()
