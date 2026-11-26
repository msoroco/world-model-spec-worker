"""Finalize retained C42417 sources after Native ownership has ended.

This analyzer measures a sampled right signal and preserves synthetic provenance.
It makes no legal or accepted-delivery claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_measure import process as measure_saved
from physical_preparation import assess as assess_motion

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + str(path.relative_to(path.parent)))
    return [json.loads(line) for line in path.read_text().splitlines()]


def decoded_frames(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    answer = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if answer.returncode or not answer.stdout.strip().isdigit():
        raise ValueError('Original camera decode failed: ' + path.name)
    return int(answer.stdout.strip())


def measure_business_signal_distance(attempt, config):
    measured = measure_saved(attempt, config,
        allow_fixture=json.loads((attempt / 'road_geometry.json').read_text()).get('provenance') == 'synthetic_cpu_fixture')
    names = ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl',
             'road_geometry.json', 'control_context.json')
    return {'value': measured['measured_signal_distance_m'],
            'method': 'measure_business_signal_distance',
            'sources': {name: sha(attempt / name) for name in names},
            'detail': measured}


def measure_weather_without_exception(attempt, config):
    sources = rows(attempt / 'native_samples.jsonl')
    weather = {row.get('precipitation') for row in sources}
    if weather != {config['precipitation']}:
        raise ValueError('Original weather source differs')
    return {'value': {'precipitation': weather.pop(), 'weather_exception_applied': False},
            'method': 'measure_weather_without_exception',
            'sources': {name: sha(attempt / name)
                for name in ('native_samples.jsonl', 'road_geometry.json')}}


def derive_channels(attempt, description, samples, mapping, trace):
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=True)
    for channel in description['channels']:
        name = channel['name']
        output = []
        for sample, frame_map, trace_row in zip(samples, mapping, trace):
            values = {
                'sig.turn_indicator': {'right_observed': sample['right_lamp_observed'],
                                       'right_commanded': sample['right_lamp_commanded']},
                'sig.hand_signal': {'observed': False, 'source_kind': 'not_in_authored_indicator_case'},
                'drv.distance_while': {'right_observed': sample['right_lamp_observed'],
                                       'xy_m': sample['ego_center_xy_m']},
                'kin.path_length': {'xy_m': sample['ego_center_xy_m']},
                'drv.turning': {'heading_deg': sample['ego_heading_deg'],
                                'course_change_observed': sample['course_change_observed']},
                'drv.lane_change': {'lane_id': sample.get('lane_id'),
                                    'authored_course': 'right_turn'},
                'env.precipitation': sample['precipitation'],
                'kin.speed': sample['ego_speed_mps'],
                'native_body_pose_control': sample,
                'camera_frame_join': frame_map,
            }
            if name not in values:
                raise ValueError('Unsupported derived channel: ' + name)
            output.append(json.dumps({'time_s': sample['time_s'],
                                      'value': values[name]}, allow_nan=False))
        (folder / (name + '.jsonl')).write_text('\n'.join(output) + '\n')


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    if config['duration_s'] * config['rate_hz'] != 600:
        raise ValueError('Exact 600-frame capture contract changed')
    samples = rows(attempt / 'native_samples.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    bodies = rows(attempt / 'body_history.jsonl')
    if any(len(items) != 600 for items in (samples, mapping, trace, evidence, bodies)):
        raise ValueError('Original source frame counts differ')
    for index, (sample, frame, trace_row, evidence_row, body) in enumerate(
            zip(samples, mapping, trace, evidence, bodies)):
        native_frame = sample['native_frame']
        if frame['video_frame'] != index or any(item != native_frame for item in
            (frame['native_frame'], trace_row['frame'], evidence_row['original_frame'], body['frame'])):
            raise ValueError('Original Native evidence/frame join differs')
        if any(abs(float(item) - sample['time_s']) > 1e-4 for item in
            (frame['time_s'], trace_row['time_s'], evidence_row['recording_time_s'], body['time_s'])):
            raise ValueError('Original Native evidence/time join differs')
    source = measure_saved(attempt, config,
        allow_fixture=json.loads((attempt / 'road_geometry.json').read_text()).get('provenance') == 'synthetic_cpu_fixture')
    physical = assess_motion(attempt)
    video_counts = {name + '.mkv': decoded_frames(attempt / (name + '.mkv')) for name in CAMERAS}
    if any(count != 600 for count in video_counts.values()):
        raise ValueError('Original four-camera frame count differs')
    description = config['recording_description']
    derive_channels(attempt, description, samples, mapping, trace)
    evidence_refs = [{'name': item['name'], 'unit': item['unit'],
        'reference': 'channels/' + item['name'] + '.jsonl'} for item in description['channels']]
    evidence_refs += [{'name': item['name'], 'unit': item['unit'],
        'reference': 'road_geometry.json'} for item in description['context_inputs']]
    provenance = source['measurement']['source_kind']
    actual = source['measured_signal_distance_m']
    target = config['signal_distance_m']
    target_check = {'target': 'continuous sampled right signal distance before course change',
        'requested': target, 'measured': actual, 'method': 'source-joined Native lamp and pose path',
        'tolerance': 1, 'matched': abs(target - actual) <= 1,
        'physical_cause_confirmed': False,
        'cause_evidence': list(source['source_hashes'])}
    result = {'case_id': config['case_id'], 'measured_values':
        {'continuous_right_signal_distance_m': actual}, 'target_checks': [target_check],
        'setup_confirmed': False, 'behavior_attempted': provenance == 'original_native_capture',
        'maneuver_completed': physical['status'] == 'met' and provenance == 'original_native_capture',
        'termination_reason': 'full source window analyzed',
        'physical_failure_flags': ['district_and_indicator_pixels_require_review'] +
            (['synthetic_fixture_not_physical'] if provenance == 'synthetic_cpu_fixture' else []),
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence_refs,
        'realized_observables': {'continuous_right_signal_distance_m':
            {'value': actual, 'unit': 'm', 'method': 'saved Native sampled path',
             'reference': 'native_samples.jsonl', 'time_window': 'preturn interval',
             'statistic': 'path length'}},
        'physical_checks': {'maneuver': {'status': physical['status'],
            'method': physical.get('engineering_completion', 'source-bound right-turn assessment'),
            'sources': physical['source_hashes'], 'details': physical['observed']}},
        'provenance_kind': 'synthetic_cpu_fixture' if provenance == 'synthetic_cpu_fixture' else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c42417-saved-analysis-v1', 'case_id': config['case_id'],
        'measurements': {'business_signal_distance_m': measure_business_signal_distance(attempt, config),
                         'weather_without_exception': measure_weather_without_exception(attempt, config)},
        'source_hashes': source['source_hashes'], 'physical': physical,
        'four_camera_frames': video_counts,
        'scope': 'saved source diagnostic; independent pixel and district review required'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
