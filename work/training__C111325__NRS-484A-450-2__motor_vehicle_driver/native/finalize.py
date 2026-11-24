"""Saved source measurement for the synthetic crosswalk-stop diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_stop import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_crosswalk_stop(observed):
    return {'value': {key: value for key, value in observed.items() if key != 'legal_verdict'},
            'method': 'measure_crosswalk_stop',
            'sources': observed['source_hashes']}


def frames(path):
    if not path.is_file():
        raise ValueError('Missing original source camera: ' + path.name)
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=nb_read_frames', '-of',
                          'default=noprint_wrappers=1:nokey=1', str(path)],
                         capture_output=True, text=True, check=True, timeout=120)
    if not run.stdout.strip().isdigit():
        raise ValueError('Original camera decode failed: ' + path.name)
    return int(run.stdout.strip())


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain previous finalization; use fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case_id']
    if not case.startswith('training__C111325__NRS-484A-450-2__motor_vehicle_driver__probe_'):
        raise ValueError('Exact case differs')
    observed = measure(attempt, case)
    native = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(mapping) != 600 or any(m.get('native_frame') != n['native_frame'] or
                                  m.get('time_s') != n['time_s'] or
                                  m.get('video_frame') != i
                                  for i, (m, n) in enumerate(zip(mapping, native))):
        raise ValueError('Original frame mapping differs')
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Derived channel directory preexists')
    channels.mkdir()
    values = {'vehicle_body_pose': lambda n, m: n['body_vertices_m'],
              'vehicle_speed': lambda n, m: n['speed_mps'],
              'frame_join': lambda n, m: m}
    if set(values) != {c['name'] for c in config['recording_description']['channels']}:
        raise ValueError('Recording channel declaration differs')
    for name, value in values.items():
        (channels / (name + '.jsonl')).write_text(
            ''.join(json.dumps({'time_s': m['time_s'], 'native_frame': m['native_frame'],
                                'value': value(n, m)}, allow_nan=False) + '\n'
                    for n, m in zip(native, mapping)))
    camera_counts = {name + '.mkv': frames(attempt / (name + '.mkv')) for name in CAMERAS}
    if set(camera_counts.values()) != {600}:
        raise ValueError('Four original source cameras need exactly 600 frames')
    expected = case.endswith('probe_1')
    matched = observed['pre_crosswalk_full_halt_observed'] == expected
    result = {
        'case_id': case,
        'measured_values': {'near_side_crosswalk_stop': {
            key: value for key, value in observed.items() if key != 'legal_verdict'}},
        'target_checks': [{'target': 'full body halt before nearest-side crosswalk',
                           'requested': expected, 'measured': observed['pre_crosswalk_full_halt_observed'],
                           'method': 'joined original 600-frame body and speed measurements',
                           'tolerance': 0, 'matched': matched,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native_samples.jsonl', 'road.xodr']}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'Synthetic saved software stop measured; physical review pending',
        'physical_failure_flags': ['physical_stop_sign_crosswalk_and_pixels_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                'reference': 'channels/' + c['name'] + '.jsonl'}
                               for c in config['recording_description']['channels']],
        'realized_observables': {
            'pre_crosswalk_stop_frames': {'value': observed['longest_pre_crosswalk_stop_frames'],
                                          'unit': 'count', 'method': 'source-joined stopped-frame count',
                                          'time_window': 'before first full-body crosswalk entry',
                                          'statistic': 'longest consecutive run',
                                          'reference': 'native_samples.jsonl'}},
        'provenance_kind': 'synthetic_native_sample', 'accepted': False,
        'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111325-saved-analysis-v1', 'case_id': case,
              'measurements': {'crosswalk_stop': measure_crosswalk_stop(observed)},
              'observed': observed, 'video_frame_counts': camera_counts,
              'derived_channel_sha256': {name: sha(channels / (name + '.jsonl')) for name in values},
              'original_source_sha256': {name: sha(attempt / name) for name in
                                         ('native_samples.jsonl', 'diagnostic-source-manifest.json',
                                          'road.xodr', 'video_frames.jsonl', 'trace.jsonl')},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
