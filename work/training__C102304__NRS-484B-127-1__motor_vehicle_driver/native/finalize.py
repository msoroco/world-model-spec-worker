"""Saved C102304 following finalizer; never asserts a legal verdict."""
import json
import math
from pathlib import Path
import subprocess

from measure_following import measure, sha


def moving_following_interval(folder):
    folder = Path(folder)
    return measure(folder/'native_samples.jsonl', folder/'following_context.json')


def required(folder, name):
    path = Path(folder)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def analysis_report(folder, contract=None):
    folder = Path(folder)
    if contract is None:
        config = json.loads(required(folder, 'config.json').read_text())
        contract = {'case_id': config['case_id'],
                    'requirements': [{'output_key': 'moving_following_interval',
                                      'method': 'moving_following_interval',
                                      'inputs': ['native_samples.jsonl', 'following_context.json']}]}
    values = {}
    for row in contract['requirements']:
        if row['method'] != 'moving_following_interval':
            raise ValueError('Unrecognized C102304 measurement method')
        value = moving_following_interval(folder)
        values[row['output_key']] = {
            'method': row['method'], 'value': value,
            'sources': {name: sha(required(folder, name)) for name in row['inputs']}}
    return {'format': 'worker-analysis-report-v1', 'case_id': contract['case_id'],
            'measurements': values, 'scope': 'source_bound_saved_measurement_without_legal_verdict'}


def rows(folder, name):
    return [json.loads(line) for line in required(folder, name).read_text().splitlines() if line.strip()]


def verify_original_joins(folder, count):
    names = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
             'native_samples.jsonl', 'capture/native/frames.jsonl')
    trace, evidence, mapping, samples, native = (rows(folder, name) for name in names)
    if any(len(source) != count for source in (trace, evidence, mapping, samples, native)):
        raise ValueError('Original trace/evidence/Native/frame counts differ')
    previous_frame, previous_time = -1, -math.inf
    for index, (t, e, m, s, n) in enumerate(zip(trace, evidence, mapping, samples, native)):
        frame, time = m.get('native_frame'), m.get('time_s')
        if type(frame) is not int or type(time) not in (int,float) or frame <= previous_frame or time <= previous_time:
            raise ValueError('Original frame/time order invalid')
        if m.get('video_frame') != index or m.get('carla_frame') != frame:
            raise ValueError('Original camera frame mapping invalid')
        if any(item != frame for item in (t.get('frame'), e.get('original_frame'),
                                          s.get('native_frame'), n.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(item)-time) > 1e-4 for item in
               (t['time_s'], e['recording_time_s'], s['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        evidence_body = {(round(v[0], 3), round(v[1], 3)) for v in e['ego']['body_vertices_m']}
        sample_body = {(round(v[0], 3), round(v[1], 3)) for v in s['ego']['native_body_xy_m']}
        if len(evidence_body) != 4 or evidence_body != sample_body:
            raise ValueError('Original ego body differs from captured evidence')
        previous_frame, previous_time = frame, time
    capture = json.loads(required(folder, 'capture/manifest.json').read_text())
    if capture.get('extraction_confirmed') is not True or capture.get('frames') != count:
        raise ValueError('Original capture extraction incomplete')
    return {'frames': count, 'first_frame': mapping[0]['native_frame'],
            'last_frame': mapping[-1]['native_frame'],
            'source_hashes': {name: sha(Path(folder)/name) for name in names}}


def video_frames(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    probe = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                            '-show_entries','stream=nb_read_frames',
                            '-of','default=noprint_wrappers=1:nokey=1',str(path)],
                           text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if probe.returncode or not probe.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(probe.stdout.strip())


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    count = config['duration_s']*config['rate_hz']
    if count != 900:
        raise ValueError('Full 45-second following window changed')
    joins = verify_original_joins(attempt, count)
    report = analysis_report(attempt)
    observed = report['measurements']['moving_following_interval']['value']
    context = json.loads(required(attempt, 'following_context.json').read_text())
    expected = 10.0 if config['case_suffix'] == 'condition_a' else 25.0
    videos = [name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    video_counts = {name: video_frames(attempt/name) for name in videos}
    if set(video_counts.values()) != {count}:
        raise ValueError('Source camera frame count differs')
    evidence = []
    for channel in config['recording_description']['channels']:
        reference = 'channels/'+channel['name']+'.jsonl'
        required(attempt, reference)
        evidence.append({'name': channel['name'], 'unit': channel['unit'], 'reference': reference})
    for item in config['recording_description']['context_inputs']:
        required(attempt, 'following_context.json')
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': 'following_context.json'})
    median_gap = observed['median_bumper_gap_m']
    result = {'case_id': config['case_id'],
        'measured_values': {'median_bumper_gap_m': median_gap,
                            'median_time_headway_s': observed['median_time_headway_s'],
                            'following_duration_s': observed['following_duration_s']},
        'target_checks': [{'target': 'full-window moving-follow bumper gap',
            'requested': expected, 'measured': median_gap,
            'method': 'original same-lane moving bodies across 900 joined Native frames',
            'tolerance': 2.0, 'matched': abs(expected-median_gap) <= 2.0,
            'physical_cause_confirmed': False,
            'cause_evidence': ['native_samples.jsonl','following_context.json','trace.jsonl']}],
        'setup_confirmed': False,
        'behavior_attempted': context['source_kind'] == 'native_observation',
        'maneuver_completed': (context['source_kind'] == 'native_observation' and
                               observed['following_duration_s'] == 45),
        'termination_reason': 'full original source interval retained',
        'physical_failure_flags': ['public_highway_status_and_pixels_unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'moving_following_gap': {
            'value': median_gap, 'unit': 'm',
            'method': 'median longitudinal bumper gap from original four-vertex Native bodies',
            'time_window': 'entire 45-second original interval', 'statistic': 'median',
            'reference': 'native_samples.jsonl'}},
        'provenance_kind': ('synthetic_local_diagnostic' if context['source_kind'] == 'synthetic_scene_request'
                            else 'native_source_shape_unverified'),
        'accepted': False, 'legal_verdict_claimed': False}
    validate_result(result)
    report.update(format='c102304-saved-following-analysis-v1',
                  candidate_id=config['candidate_id'], original_joins=joins,
                  video_frames=video_counts,
                  scope='saved original-source joins and video decode; no public-highway or legal finding')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output), allow_nan=False))
