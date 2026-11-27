"""Independent original-source scooter-pass audit; diagnostics cannot satisfy it."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('participant-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl',
           'road.xodr', 'pass-context.json', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inside(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    metric = result.get('measured_values', {})
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Exact original Native result missing')
    if metric.get('format') != 'c272412-original-pass-measurement-v1' or metric.get('source_kind') != 'native_original' or metric.get('original_native_observed') is not True:
        raise ValueError('Original driver/rider measurement missing')
    if metric.get('original_frame_rate_hz') != 20 or metric.get('abreast_frame_count', 0) < 1:
        raise ValueError('Original pass interval missing')
    if set(metric.get('source_sha256', {})) != set(SOURCES):
        raise ValueError('Original source inventory incomplete')
    if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical pass completion unproven')
    return metric


def check_review(review, case, video, mapping, metric):
    if review.get('format') != 'c272412-original-rider-pass-review-v1' or review.get('case_id') != case or not review.get('reviewer_id') or review.get('source_kind') != 'original_native_review':
        raise ValueError('Original pixel and road review missing')
    if review.get('video_sha256') != sha(video) or review.get('video_frames_sha256') != sha(mapping):
        raise ValueError('Original review video/frame binding differs')
    findings = review.get('findings', {})
    required = ('driver_and_rider_visible', 'rider_electric_scooter_class_confirmed',
                'one_same_direction_lane_confirmed', 'left_pass_confirmed',
                'continuous_three_foot_clearance_confirmed', 'safely_clear_before_return_confirmed',
                'due_care_source_reviewed', 'physical_pass_confirmed')
    if any(findings.get(key) is not True for key in required):
        raise ValueError('Original source finding missing')
    if case.endswith('exception_1_1') or case.endswith('exception_1_2'):
        if findings.get('center_or_no_passing_designation_confirmed') is not True or findings.get('cited_213_217_applicability_reviewed') is not True or findings.get('safe_exception_passage_confirmed') is not True:
            raise ValueError('Conditional center/no-passing authority unreviewed')
    if review.get('decisive_frames', {}).get('first_abreast') != metric['first_abreast_frame'] or review.get('decisive_frames', {}).get('last_abreast') != metric['last_abreast_frame']:
        raise ValueError('Original decisive pass frames differ')


def audit(args):
    from worker_exchange import media
    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain previous independent audit')
    result_path = inside(attempt, 'result.json')
    metric = check_result(read(result_path), args.case)
    for name, digest in metric['source_sha256'].items():
        if sha(inside(attempt, name)) != digest:
            raise ValueError('Original source hash differs: ' + name)
    seal = read(inside(attempt, 'capture-seal.json'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('diagnostic_fixture') is True:
        raise ValueError('Sealed original Native acquisition missing')
    mapping = inside(attempt, 'video_frames.jsonl')
    frame_map = [json.loads(line) for line in mapping.read_text().splitlines()]
    if len(frame_map) != 600 or any(row.get('video_frame') != index or
        set(row.get('camera_native_frames', {})) != set(CAMERAS) for index, row in enumerate(frame_map)):
        raise ValueError('Original four-camera frame map incomplete')
    poses = [json.loads(line) for line in inside(attempt, 'participant-poses.jsonl').read_text().splitlines()]
    if len(poses) != len(frame_map) or any(pose.get('frame') != frame.get('carla_frame') or
        abs(pose.get('time_s', -1) - frame['time_s']) > 1e-6 for pose, frame in zip(poses, frame_map)):
        raise ValueError('Original driver/rider frame join differs')
    for pose in poses:
        if not all(pose.get(actor, {}).get('body_xy_m') for actor in ('ego', 'scooter')):
            raise ValueError('Original participant body history missing')
    video = inside(attempt, args.video)
    trace = inside(attempt, args.trace)
    review = inside(attempt, args.review)
    check_review(read(review), args.case, video, mapping, metric)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode)
    media.verify_receipt(video, decode, 600, mapping_sha256=sha(mapping))
    value = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
             'job_id': args.job, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'video_sha256': sha(video),
             'trace_sha256': sha(trace), 'human_review_sha256': sha(review),
             'checks': {name: True for name in CHECKS},
             'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'measured_values': {'format': 'c272412-original-pass-measurement-v1',
                  'source_kind': 'native_original', 'original_native_observed': True,
                  'original_frame_rate_hz': 20, 'abreast_frame_count': 5,
                  'source_sha256': {name: '0' * 64 for name in SOURCES}},
              'maneuver_completed': True, 'physical_checks': {'maneuver': {'status': 'met'}}}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for name in SOURCES:
        changed = json.loads(json.dumps(sample))
        changed['measured_values']['source_sha256'].pop(name)
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing source accepted: ' + name)
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'original_acquisition_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    for name in ('attempt', 'output', 'video', 'trace', 'review', 'job', 'recording-id'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.self_test:
        selftest(args.case, args.negative)
    else:
        print(json.dumps(audit(args)))
