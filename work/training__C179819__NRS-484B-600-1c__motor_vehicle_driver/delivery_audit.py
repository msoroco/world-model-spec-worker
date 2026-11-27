"""Independent posted-speed original-source delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source(root, name):
    path = (root/name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Exact original Native result missing')
    metric = result.get('measured_values', {})
    if (metric.get('sample_count') != 600 or metric.get('governed_frame_count', 0) < 1
            or metric.get('review_kind') != 'original_source_review'
            or metric.get('legal_verdict_claimed') is not False
            or not metric.get('authority_source') or not metric.get('highway_source')):
        raise ValueError('Original posting, highway extent or measured speed missing')
    if (result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'
            or result.get('maneuver_completed') is not True):
        raise ValueError('Original physical progress unproven')
    return metric


def check_review(review, case):
    if (review.get('format') != 'c179819-posted-speed-original-review-v1'
            or review.get('source_kind') != 'original_native_review'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Original speed-zone review missing')
    for key in ('public_authority_posting_reviewed', 'governed_highway_portion_reviewed',
                'sign_passage_and_direction_reviewed', 'ego_identity_and_velocity_reviewed',
                'four_camera_pixels_reviewed'):
        if review.get(key) is not True:
            raise ValueError('Independent original review incomplete: '+key)
    if not review.get('source_sha256') or not review.get('media_sha256'):
        raise ValueError('Original source basis missing')


def audit(args):
    from worker_exchange import media
    root = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = source(root, 'result.json')
    metric = check_result(read(result_path), args.case)
    context = read(source(root, 'road_context.json'))
    if (context.get('review_kind') != 'original_source_review' or not context.get('reviewer')
            or not context.get('authority_source') or not context.get('highway_source')):
        raise ValueError('Original authority/highway context missing')
    review_path = source(root, args.review)
    review = read(review_path)
    check_review(review, args.case)
    for name, checksum in review['source_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Original review source hash differs: '+name)
    required_media = {name+'.mkv' for name in CAMERAS} | {'raw.mkv'}
    if set(review['media_sha256']) != required_media:
        raise ValueError('Original media inventory incomplete')
    for name, checksum in review['media_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Reviewed original media hash differs: '+name)
    groups = [[json.loads(line) for line in source(root, name).read_text().splitlines()]
              for name in ('video_frames.jsonl', 'native_motion.jsonl', args.trace)]
    if any(len(group) != 600 for group in groups):
        raise ValueError('Original full-frame inventory incomplete')
    for i, (frame, motion, core) in enumerate(zip(*groups)):
        if (frame.get('video_frame') != i or motion.get('video_frame') != i
                or core.get('frame') != frame.get('carla_frame')
                or abs(core.get('time_s', -100)-frame.get('time_s', -200)) > 1e-6
                or frame.get('source_cameras') != {name: i for name in CAMERAS}
                or motion.get('ego_actor_id') is None or motion.get('sign_id') != context.get('sign_id')):
            raise ValueError('Original speed, sign or camera time join differs')
    mapping = source(root, 'video_frames.jsonl')
    video = source(root, args.video)
    receipt = output.with_name('source-decode-'+args.case.rsplit('__', 1)[-1]+'.json')
    decode = media.audit(video, 600, mapping_sha256=sha(mapping), receipt=receipt)
    media.verify_receipt(video, receipt, 600, mapping_sha256=sha(mapping))
    report = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
              'job_id': args.job, 'recording_id': args.recording_id,
              'checks': {name: True for name in CHECKS},
              'source_result_sha256': sha(result_path), 'review_sha256': sha(review_path),
              'video_sha256': sha(video), 'decoded_frames': decode['frames'],
              'governed_frame_count': metric['governed_frame_count'],
              'legal_outcome': 'unassessed_pending_independent_judgment'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def selftest(case, negative):
    result = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'measured_values': {'sample_count': 600, 'governed_frame_count': 400,
                  'review_kind': 'original_source_review', 'authority_source': 'schema-source',
                  'highway_source': 'schema-source', 'legal_verdict_claimed': False},
              'physical_checks': {'maneuver': {'status': 'met'}}, 'maneuver_completed': True}
    if negative:
        result['provenance_kind'] = 'synthetic_fixture'
        check_result(result, case)
        raise AssertionError('Synthetic source unexpectedly accepted')
    check_result(result, case)
    review = {'format': 'c179819-posted-speed-original-review-v1',
              'source_kind': 'original_native_review', 'case_id': case,
              'reviewer_id': 'cpu-schema-only', 'source_sha256': {'road.xodr': 'schema-only'},
              'media_sha256': {'raw.mkv': 'schema-only'}}
    for key in ('public_authority_posting_reviewed', 'governed_highway_portion_reviewed',
                'sign_passage_and_direction_reviewed', 'ego_identity_and_velocity_reviewed',
                'four_camera_pixels_reviewed'):
        review[key] = True
    check_review(review, case)
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'original_acquisition_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    for name in ('attempt', 'output', 'video', 'trace', 'review', 'job', 'recording-id'):
        parser.add_argument('--'+name)
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)
