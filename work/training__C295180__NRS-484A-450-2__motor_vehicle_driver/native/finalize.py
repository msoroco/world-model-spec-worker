"""Saved source measurement for the exact marked stop-line branch."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_stop_line import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_marked_line_stop(observed, root):
    return {'value': observed,
            'method': 'measure_marked_line_stop',
            'sources': {'native_samples.jsonl': sha(root / 'native_samples.jsonl'),
                        'road.xodr': sha(root / 'road.xodr')}}


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
    if case not in ('training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_a', 'training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_b'):
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
              'frame_join': lambda n, m: m,
              'dev.stop_sign': lambda n, m: {'road_signal_id': 901, 'source': 'road.xodr',
                                             'physical_visibility': 'unverified'},
              'dev.governs': lambda n, m: {'approach_road_id': 1, 'lane_id': -1,
                                          'physical_governing_status': 'unverified'},
              'st.lane_enters': lambda n, m: {'road_id': n['road_id'],
                                              'lane_id': n['lane_id']},
              'drv.approaching': lambda n, m: max(v[1] for v in n['body_vertices_m']) < -7,
              'st.crosswalk': lambda n, m: {'applicable': False, 'source': 'road.xodr'},
              'st.stop_line': lambda n, m: {'reference_y_m': -11, 'source': 'road.xodr',
                                            'physical_rendering': 'unverified'},
              'st.intersection': lambda n, m: {'entry_y_m': -7,
                                               'source': 'crosswalk_geometry.json'},
              'st.sight_distance': lambda n, m: {'applicable': False,
                                                 'measurement': None},
              'rel.visible': lambda n, m: {'applicable': False, 'measurement': None},
              'drv.stopped': lambda n, m: n['speed_mps'] <= .15,
              'drv.crossing_line': lambda n, m: max(v[1] for v in n['body_vertices_m']) >= -11,
              'drv.entering_intersection': lambda n, m:
                  max(v[1] for v in n['body_vertices_m']) >= -7}
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
    expected = case.endswith('condition_a')
    matched = observed['complete_stop_before_line_diagnostic'] == expected
    result = {
        'case_id': case,
        'measured_values': {'marked_stop_line_halt': {
            key: value for key, value in observed.items() if key != 'legal_verdict'}},
        'target_checks': [{'target': 'full body halt before the clearly marked stop line',
                           'requested': expected, 'measured': observed['complete_stop_before_line_diagnostic'],
                           'method': 'joined original 600-frame body and speed measurements',
                           'tolerance': 0, 'matched': matched,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native_samples.jsonl', 'road.xodr']}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'Saved source stop measured; physical review pending',
        'physical_failure_flags': ['physical_stop_sign_crosswalk_and_pixels_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                'reference': 'channels/' + c['name'] + '.jsonl'}
                               for c in config['recording_description']['channels']],
        'realized_observables': {
            'pre_marked_line_stop_frames': {'value': observed['longest_pre_crossing_stopped_run_frames'],
                                          'unit': 'count', 'method': 'source-joined stopped-frame count',
                                          'time_window': 'before first full-body marked-line crossing',
                                          'statistic': 'longest consecutive run',
                                          'reference': 'native_samples.jsonl'}},
        'provenance_kind': observed['source_kind'], 'accepted': False,
        'legal_verdict_claimed': False}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt, result)
    validate_result(result)
    report = {'format': 'c295180-saved-analysis-v1', 'case_id': case,
              'measurements': {'marked_line_stop': measure_marked_line_stop(observed, attempt)},
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
