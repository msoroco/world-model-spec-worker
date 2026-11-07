"""Finalize a saved C111331 diagnostic without physical or legal acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from measure_saved import measure
from signal_video_cpu import inspect as inspect_signal_video


def measure_yellow_onset(measurement):
    return measurement['observed_yellow_start_frame']


def measure_phase_at_entry(measurement):
    return measurement['observed_signal_phase_at_entry']


def measure_red_onset(measurement):
    return measurement['observed_red_start_frame']


def measure_body_entry(measurement):
    return measurement['observed_full_body_entry_frame']


def measure_entry_red_margin(measurement):
    return measurement['entry_to_red_margin_frames']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finalize(attempt, output):
    attempt = Path(attempt)
    output = Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    for name in ('construction.json', 'config.json', 'native_samples.jsonl',
                 'video_frames.jsonl', 'trace.jsonl', 'signal_reference.mkv'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if construction['case_id'] != config['case_id'] or construction['law_id'] != 'NRS-484B-307-6a':
        raise ValueError('Exact construction identity differs')
    native = rows(attempt / 'native_samples.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if len(native) != 480 or len(mapping) != 480 or len(trace) != 480:
        raise ValueError('Saved Native/trace/video frame counts differ')
    for i, (n, frame, point) in enumerate(zip(native, mapping, trace)):
        if (n['request_index'] != i or frame['video_frame'] != i or
                n['native_frame'] != frame['native_frame'] or point['frame'] != frame['native_frame'] or
                abs(frame['time_s'] - point['time_s']) > .001):
            raise ValueError('Saved Native/trace/video frame join differs')
    measurement = measure(attempt, config['case_id'], config['candidate_id'])
    if measurement['physical_native_evidence']:
        raise ValueError('Physical Native source needs independent original-source review')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('Pinned FFmpeg executable is required for synthetic video proof')
    video = inspect_signal_video(attempt, attempt / 'signal_reference.mkv', ffmpeg)
    source_hashes = dict(measurement['sources'])
    source_hashes['signal_reference.mkv'] = video['video_sha256']
    report = {'format': 'c111331-saved-signal-entry-report-v1', 'case_id': config['case_id'],
              'selected': False, 'draft_only': True,
              'measurements': {
                  key: {'method': method.__name__, 'value': method(measurement),
                        'sources': source_hashes}
                  for key, method in (
                      ('yellow_warning_onset_frame', measure_yellow_onset),
                      ('observed_signal_phase_at_entry', measure_phase_at_entry),
                      ('red_exhibition_onset_frame', measure_red_onset),
                      ('full_body_intersection_entry_frame', measure_body_entry),
                      ('entry_to_red_margin_frames', measure_entry_red_margin))},
              'measurement_detail': measurement,
              'synthetic_video_proof': video,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for n, frame in zip(native, mapping):
                values = {'native_body_pose': {'center_xy_m': n['native_center_xy_m'],
                                               'body_xy_m': n['native_body_xy_m']},
                          'observed_signal_state': {'phase': n['observed_signal_state'],
                                                    'actor_id': n['signal_actor_id']},
                          'signal_camera_frame_join': {'native_frame': frame['native_frame'],
                                                       'video_frame': frame['video_frame']}}
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': values[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    (attempt / 'road-context.json').write_text(json.dumps({
        'authored_road': {'source': 'road.xodr', 'sha256': sha(attempt / 'road.xodr')}}, indent=2) + '\n')
    (attempt / 'signal-request-context.json').write_text(json.dumps({
        'authored_signal_request': {'source': 'native-requests.jsonl',
                                    'sha256': sha(attempt / 'native-requests.jsonl')}}, indent=2) + '\n')
    evidence.extend([
        {'name': 'authored_road', 'unit': 'structured', 'reference': 'road-context.json'},
        {'name': 'authored_signal_request', 'unit': 'structured',
         'reference': 'signal-request-context.json'}])
    expected = 'yellow' if config['case_suffix'] == 'reference' else 'red'
    observed = measurement['observed_signal_phase_at_entry']
    result = {'case_id': config['case_id'],
              'measured_values': {'signal_phase_at_first_full_body_entry': observed,
                                  'entry_frame': measurement['observed_full_body_entry_frame'],
                                  'red_start_frame': measurement['observed_red_start_frame']},
              'target_checks': [{'target': 'signal phase at first full-body junction entry',
                                 'requested': expected, 'measured': observed,
                                 'method': 'saved Native body/traffic-light frame join',
                                 'tolerance': 'one retained 50 ms frame bracket',
                                 'matched': expected == observed,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['native_samples.jsonl', 'video_frames.jsonl']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full 480-frame synthetic saved window',
              'physical_failure_flags': ['Native signal/body behavior and original pixels unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': ['signal_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'full_body_entry_frame': {
                  'value': measurement['observed_full_body_entry_frame'], 'unit': 'frame',
                  'method': 'saved 480-frame synthetic Native signal/body join',
                  'time_window': '24 s diagnostic', 'statistic': 'first body entry',
                  'reference': 'native_samples.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
