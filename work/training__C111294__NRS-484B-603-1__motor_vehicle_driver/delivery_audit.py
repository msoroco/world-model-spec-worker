"""Independent original Native speed and traffic delivery audit; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + relative)
    return path


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Original Native result required')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer preaccepted a legal outcome')
    measured = result.get('measured_values', {})
    if measured.get('frames') != 600 or not all(isinstance(measured.get(key), (int, float)) for key in
            ('approach_start_mph', 'preentry_mph', 'crossing_peak_mph', 'measured_decrease_mph')):
        raise ValueError('Missing source-bound approach speed measurement')
    if measured.get('reduction_necessity_legally_verified') is not False:
        raise ValueError('Necessity claimed without independent review')
    names = {row.get('name') for row in result.get('recording_evidence', [])}
    required = {'ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose'}
    if 'weather_probe' in case:
        required.add('weather_parameters')
    if 'pedestrian_probe' in case:
        required.update(('pedestrian_pose', 'pedestrian_hazard'))
    if 'obstruction_probe' in case:
        required.update(('obstruction_pose', 'highway_obstruction'))
    if 'crest_probe' in case:
        required.add('crest_design')
    if not required <= names:
        raise ValueError('Ego, other-traffic or weather recording missing')
    if not result.get('target_checks') or not result.get('realized_observables'):
        raise ValueError('Missing physical target or realized observables')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Observed motion or maneuver incomplete')


def check_join(frame_map, trace):
    frames = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = json.loads(trace.read_text()).get('scenes', [])
    if len(frames) != 600 or len(scenes) != 600:
        raise ValueError('Original frame/Core count mismatch')
    for index, (frame, scene) in enumerate(zip(frames, scenes)):
        if frame.get('video_frame') != index or scene.get('t') != round(frame['time_s'] * 1000):
            raise ValueError('Original frame/Core timestamp mismatch')
    return len(frames)


def check_review(review, attempt, frame_map, trace, case):
    if review.get('format') != 'c111294-603-1-original-source-review-v1' or not review.get('reviewer') or review.get('reviewer') == 'synthetic-cpu-fixture':
        raise ValueError('Independent original source review required')
    if review.get('physical_completion_reviewed') is not True:
        raise ValueError('Independent original physical completion review required')
    if review.get('necessity_legally_resolved') is True or review.get('legal_verdict'):
        raise ValueError('Legal conclusion cannot be embedded in physical review')
    expected = {'video_frames.jsonl': frame_map, 'converted/trace.json': trace}
    for name in ('native_samples.jsonl', 'road.xodr'):
        expected[name] = source(attempt, name)
    if 'weather_probe' in case:
        for name in ('context.json', 'capture/evidence.jsonl'):
            expected[name] = source(attempt, name)
        context = json.loads(expected['context.json'].read_text())
        evidence = [json.loads(line) for line in expected['capture/evidence.jsonl'].read_text().splitlines()]
        if context.get('weather_parameters', {}).get('wetness', 0) <= 0 or len(evidence) != 600 or any(row.get('world', {}).get('weather', {}).get('wetness', 0) <= 0 for row in evidence):
            raise ValueError('Original wet-weather condition unverified')
    if 'pedestrian_probe' in case:
        for name in ('context.json', 'capture/evidence.jsonl'):
            expected[name] = source(attempt, name)
        context = json.loads(expected['context.json'].read_text())
        evidence = [json.loads(line) for line in expected['capture/evidence.jsonl'].read_text().splitlines()]
        samples = [json.loads(line) for line in expected['native_samples.jsonl'].read_text().splitlines()]
        if not context.get('pedestrian_hazard') or len(evidence) != 600 or len(samples) != 600:
            raise ValueError('Original pedestrian hazard context unverified')
        if any(not row.get('world', {}).get('pedestrian', {}).get('position_m') for row in evidence):
            raise ValueError('Pedestrian missing from original evidence')
        if any(row.get('pedestrian_role') != 'pedestrian' or not row.get('pedestrian_position_m') for row in samples):
            raise ValueError('Pedestrian missing from original Native samples')
    if 'obstruction_probe' in case:
        for name in ('context.json', 'capture/evidence.jsonl'):
            expected[name] = source(attempt, name)
        context = json.loads(expected['context.json'].read_text())
        evidence = [json.loads(line) for line in expected['capture/evidence.jsonl'].read_text().splitlines()]
        samples = [json.loads(line) for line in expected['native_samples.jsonl'].read_text().splitlines()]
        if not context.get('highway_obstruction') or len(evidence) != 600 or len(samples) != 600:
            raise ValueError('Original highway obstruction context unverified')
        if any(row.get('original_frame') != i + 100 for i, row in enumerate(evidence)):
            raise ValueError('Highway obstruction frame evidence is not joined')
        if any(row.get('obstruction_blueprint') != 'static.prop.streetbarrier' or
               not row.get('obstruction_position_m') for row in samples):
            raise ValueError('Highway obstruction missing from original Native samples')
    if 'crest_probe' in case:
        for name in ('context.json', 'capture/evidence.jsonl'):
            expected[name] = source(attempt, name)
        context = json.loads(expected['context.json'].read_text())
        evidence = [json.loads(line) for line in expected['capture/evidence.jsonl'].read_text().splitlines()]
        samples = [json.loads(line) for line in expected['native_samples.jsonl'].read_text().splitlines()]
        heights = [row['ego_position_m'][2] for row in samples]
        peak = max(range(20, 400), key=lambda i: heights[i]) if len(heights) == 600 else 0
        if (context.get('crest_design', {}).get('peak_station_m') != 200 or
                len(evidence) != 600 or len(heights) != 600 or peak <= 20 or
                heights[peak] - min(heights[:peak]) < .5 or
                heights[peak] - min(heights[peak + 1:500]) < .5):
            raise ValueError('Original hill crest grade and ego rise/fall unverified')
    for name, path in expected.items():
        if review.get('source_sha256', {}).get(name) != digest(path):
            raise ValueError('Review lacks exact original source hash: ' + name)
    rows = review.get('frames', [])
    if len(rows) != 600 or any(row.get('frame') != i or row.get('ego_and_other_vehicle_reviewed') is not True or
            set(row.get('source_rgb_sha256', {})) != set(VIEWS) for i, row in enumerate(rows)):
        raise ValueError('Original actor/pixel review incomplete')
    if 'pedestrian_probe' in case and any(row.get('pedestrian_reviewed') is not True for row in rows):
        raise ValueError('Original pedestrian review incomplete')
    if 'obstruction_probe' in case and any(row.get('highway_obstruction_reviewed') is not True for row in rows):
        raise ValueError('Original highway obstruction review incomplete')
    if 'crest_probe' in case and any(row.get('hill_crest_reviewed') is not True for row in rows):
        raise ValueError('Original hill crest review incomplete')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    provenance = json.loads(source(attempt, 'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'native' or provenance.get('native_executed') is not True or provenance.get('diagnostic_fixture') is True:
        raise ValueError('Original Native acquisition provenance missing')
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    frame_map = source(attempt, 'video_frames.jsonl')
    trace = source(attempt, args.trace)
    review = json.loads(source(attempt, args.review).read_text())
    check_review(review, attempt, frame_map, trace, args.case)
    frames = check_join(frame_map, trace)
    video = source(attempt, args.video)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, frames, mapping_sha256=digest(frame_map), receipt=decode)
    verified = media.verify_receipt(video, decode, frames, mapping_sha256=digest(frame_map))
    payload = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
               'job_id': args.job, 'attempt': args.attempt_number, 'recording_id': args.recording_id,
               'source_result_sha256': digest(result_path), 'frames': frames,
               'video_sha256': digest(video), 'trace_sha256': digest(trace),
               'checks': {name: True for name in CHECKS},
               'auditor_sha256': digest(Path(__file__)),
               'source_decode_receipt_path': str(decode), 'source_decode_receipt_sha256': digest(decode),
               'source_decode_auditor_sha256': verified['auditor_sha256'],
               'human_review_sha256': digest(source(attempt, args.review)),
               'physical_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'accepted': False, 'legal_verdict_claimed': False, 'setup_confirmed': False,
              'behavior_attempted': True, 'maneuver_completed': True, 'target_checks': [{'target': 'speed_profile', 'matched': True}],
              'realized_observables': {'ego_speed': {'value': 10}},
              'recording_evidence': [{'name': name} for name in (('ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose', 'weather_parameters') if 'weather_probe' in case else ('ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose', 'pedestrian_pose', 'pedestrian_hazard') if 'pedestrian_probe' in case else ('ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose', 'obstruction_pose', 'highway_obstruction') if 'obstruction_probe' in case else ('ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose', 'crest_design') if 'crest_probe' in case else ('ego_pose', 'ego_speed', 'observed_speed', 'other_vehicle_pose'))],
              'measured_values': {'frames': 600, 'approach_start_mph': 28.8, 'preentry_mph': 20.0,
                                  'crossing_peak_mph': 20.0, 'measured_decrease_mph': 8.8,
                                  'reduction_necessity_legally_verified': False}}
    if negative:
        sample['provenance_kind'] = 'synthetic_local_diagnostic'
        check_result(sample, case)
        raise AssertionError('Synthetic fixture accepted')
    check_result(sample, case)
    for key, value in (('recording_evidence', []), ('target_checks', []), ('maneuver_completed', False)):
        changed = json.loads(json.dumps(sample)); changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            continue
        raise AssertionError('Missing source/physical evidence accepted')
    return {'case_id': case, 'source_predicates_tested': True, 'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--video', default='primary.mkv')
    parser.add_argument('--review', default='independent-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    arguments = parser.parse_args()
    print(json.dumps(selftest(arguments.case, arguments.negative) if arguments.self_test else audit(arguments), indent=2))
