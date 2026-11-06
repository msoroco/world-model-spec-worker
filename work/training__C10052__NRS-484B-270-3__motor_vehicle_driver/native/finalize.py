"""Saved-only C10052 diagnostic; occupancy and requested context remain distinct."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_facility import measure


def facility_stop_observation(attempt):
    attempt = Path(attempt)
    result = measure(attempt/'native_samples.jsonl', attempt/'road_geometry.json',
                     attempt/'exception_context.json')
    return {'method': 'facility_stop_observation',
            'value': {'max_stopped_overlap_m2': result['max_stopped_overlap_m2'],
                      'mean_stopped_overlap_m2': result['mean_stopped_overlap_m2'],
                      'stop_duration_s': result['stop_duration_s'],
                      'native_facility_design_verified': result['native_facility_design_verified'],
                      'observed_exception_status': result['observed_exception_status'],
                      'yield_duty_measured': result['yield_duty_measured'],
                      'legal_verdict_claimed': False},
            'sources': result['source_sha256']}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_original_joins(attempt, count):
    attempt = Path(attempt)
    trace = rows(attempt/'trace.jsonl')
    evidence = rows(attempt/'capture/evidence.jsonl')
    mapping = rows(attempt/'video_frames.jsonl')
    motion = rows(attempt/'native_samples.jsonl')
    history = rows(attempt/'body_history.jsonl')
    if not all(len(source) == count for source in (trace, evidence, mapping, motion, history)):
        raise ValueError('Original trace/evidence/body/frame counts differ')
    prior_frame, prior_time = -1, -math.inf
    for index, (t, e, m, n, b) in enumerate(zip(trace, evidence, mapping, motion, history)):
        frame, time = m.get('native_frame'), m.get('time_s')
        if (type(frame) is not int or type(time) not in (int, float) or
            frame <= prior_frame or time <= prior_time or m.get('video_frame') != index or
            m.get('carla_frame') != frame):
            raise ValueError('Original frame/time mapping invalid')
        prior_frame, prior_time = frame, time
        if any(item != frame for item in (t.get('frame'), e.get('original_frame'),
                                          n.get('native_frame'), b.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(item)-time) > 1e-4 for item in
               (t['time_s'], e['recording_time_s'], n['time_s'], b['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        captured = {(round(v[0], 5), round(v[1], 5)) for v in e['ego']['body_vertices_m']}
        measured = {(round(v[0], 5), round(v[1], 5)) for v in n['native_body_xy_m']}
        saved = {(round(v[0], 5), round(v[1], 5)) for v in b['body_vertices_m']}
        if len(captured) != 4 or captured != measured or measured != saved:
            raise ValueError('Original full body differs from saved measurement')
    manifest = json.loads((attempt/'capture/manifest.json').read_text())
    if not manifest.get('extraction_confirmed') or manifest.get('frames') != count:
        raise ValueError('Original capture extraction incomplete')
    names = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
             'native_samples.jsonl', 'body_history.jsonl', 'capture/manifest.json')
    return {'frames': count, 'first_frame': mapping[0]['native_frame'],
            'last_frame': mapping[-1]['native_frame'],
            'first_time_s': mapping[0]['time_s'], 'last_time_s': mapping[-1]['time_s'],
            'source_hashes': {name: sha(attempt/name) for name in names}}


def video_frames(path):
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    command = ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
               '-show_entries', 'stream=nb_read_frames',
               '-of', 'default=noprint_wrappers=1:nokey=1', str(path)]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name+' '+result.stderr[-300:])
    return int(result.stdout.strip())


def finalize_full_attempt(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads((attempt/'config.json').read_text())
    count = round(config['duration_s']*config['rate_hz'])
    if count != 480:
        raise ValueError('Expected original 480-frame attempt')
    original = verify_original_joins(attempt, count)
    observed = measure(attempt/'native_samples.jsonl', attempt/'road_geometry.json',
                       attempt/'exception_context.json')
    measurements = {'facility_stop_observation': facility_stop_observation(attempt)}
    videos = [f'{name}.mkv' for name in
              ('overview', 'approach', 'facility', 'driver_reference')]
    counts = {name: video_frames(attempt/name) for name in videos}
    if any(frames != count for frames in counts.values()):
        raise ValueError('Source camera frame count differs from original trace')
    description = config['recording_description']
    recording_evidence = []
    for channel in description['channels']:
        name, reference = channel['name'], 'channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': reference})
    for context in description['context_inputs']:
        reference = ('exception_context.json' if context['name'] == 'requested_exception_context'
                     else 'context.json')
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name': context['name'], 'unit': context['unit'],
                                   'reference': reference})
    requested = {'probe_a': 0.0, 'probe_b': 9.36}[config['case_suffix']]
    overlap = observed['max_stopped_overlap_m2']
    matched = abs(overlap-requested) <= .25 and observed['stop_duration_s'] >= 2.0
    result = {'case_id': config['case_id'],
        'measured_values': {'max_stopped_overlap_m2': overlap,
                            'stop_duration_s': observed['stop_duration_s']},
        'target_checks': [{'target': 'stationary full-body occupancy of proposed bicycle facility',
            'requested': requested, 'measured': overlap,
            'method': 'original Native body/road/lane/speed and surveyed facility polygon',
            'tolerance': 'absolute overlap difference <= 0.25 m2 with 2 s sampled stop',
            'matched': matched, 'physical_cause_confirmed': False,
            'cause_evidence': ['road_geometry.json', 'native_samples.jsonl',
                               'exception_context.json']}],
        'setup_confirmed': observed['native_facility_design_verified'],
        'behavior_attempted': True, 'maneuver_completed': True,
        'termination_reason': 'full original duration retained',
        'physical_failure_flags': ['facility_design_exceptions_yield_and_pixels_unverified']+
            ([] if matched else ['requested_stop_overlap_not_measured']),
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': recording_evidence,
        'realized_observables': {'sampled_stopped_facility_overlap': {
            'value': overlap, 'unit': 'm2',
            'method': 'maximum original sampled stationary full-body polygon area in proposed facility',
            'time_window': 'observed stationary interval', 'statistic': 'maximum',
            'reference': 'native_samples.jsonl',
            'sample_window_s': [observed['stop_first_frame']/20,
                                observed['stop_last_frame']/20]}},
        'provenance_kind': 'native', 'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c10052-full-saved-occupancy-diagnostic-v1',
              'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
              'measurements': measurements, 'original_joins': original,
              'video_frames': counts,
              'scope': 'saved original-source diagnostic; Native facility designation, exception absence, yield and legal outcome unverified'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists():
        raise ValueError('Retain original finalization; use a fresh output')
    observation = facility_stop_observation(attempt)
    report = {'format': 'c10052-synthetic-saved-occupancy-diagnostic-v1',
              'measurements': {'facility_stop_observation': observation},
              'scope': 'saved synthetic original-sample diagnostic; no Native designation, exception finding, yield finding or legal verdict'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    selected = finalize_full_attempt if (Path(args.attempt)/'config.json').is_file() else finalize
    print(json.dumps(selected(args.attempt, args.output)))


if __name__ == '__main__':
    main()
