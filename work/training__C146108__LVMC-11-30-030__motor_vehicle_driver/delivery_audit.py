"""Independent original crosswalk source, actor, media and physical audit."""
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
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Exact original Native result missing')
    metric = result.get('measured_values', {})
    if (metric.get('frame_count') != 600 or metric.get('crosswalk_kind') not in
            ('marked', 'unmarked_intersection') or metric.get('legal_compliance') != 'unassessed'
            or metric.get('original_crossing_reviewed') is not True
            or metric.get('original_stop_purpose_reviewed') is not True):
        raise ValueError('Crossing or stopped-lead source measurement missing')
    if (result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'
            or result.get('maneuver_completed') is not True):
        raise ValueError('Original physical progress unproven')
    return metric


def check_review(review, case):
    if (review.get('format') != 'c146108-crosswalk-original-review-v1'
            or review.get('source_kind') != 'original_native_review'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Original crosswalk review missing')
    for key in ('crossing_kind_and_intersection_reviewed', 'lead_stop_purpose_reviewed',
                'pedestrian_full_crossing_reviewed', 'ego_and_lead_full_bodies_reviewed',
                'rear_approach_and_pass_reviewed', 'four_camera_pixels_reviewed'):
        if review.get(key) is not True:
            raise ValueError('Independent original review incomplete: ' + key)
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
    context = read(source(root, 'crosswalk_context.json'))
    if context.get('source_kind') != 'original_native_crosswalk_pass_readback':
        raise ValueError('Original Native crosswalk context missing')
    for name, checksum in context.get('source_sha256', {}).items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Original context source hash differs: ' + name)
    names = ('video_frames.jsonl', 'crosswalk_trace.jsonl', 'ego_body.jsonl',
             'lead_body.jsonl', 'pedestrian_body.jsonl', args.trace)
    groups = [[json.loads(line) for line in source(root, name).read_text().splitlines()]
              for name in names]
    if any(len(group) != 600 for group in groups):
        raise ValueError('Original full frame inventory incomplete')
    for i, (frame, motion, ego, lead, pedestrian, core) in enumerate(zip(*groups)):
        native = frame.get('native_frame')
        if (frame.get('video_frame') != i or motion.get('video_frame') != i
                or motion.get('native_frame') != native
                or any(row.get('native_frame') != native for row in (ego, lead, pedestrian))
                or core.get('frame') != native
                or abs(core.get('time_s', -100) - frame.get('time_s', -200)) > 1e-6
                or frame.get('source_cameras') != {name: i for name in CAMERAS}
                or any(len(row.get('body_vertices_m', [])) < 4 for row in (ego, lead, pedestrian))):
            raise ValueError('Original crosswalk actors, time or camera join differs')
    review_path = source(root, args.review)
    review = read(review_path)
    check_review(review, args.case)
    for name, checksum in review['source_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Original review source hash differs: ' + name)
    required_media = {name + '.mkv' for name in CAMERAS} | {'raw.mkv'}
    if set(review['media_sha256']) != required_media:
        raise ValueError('Original media inventory incomplete')
    for name, checksum in review['media_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Reviewed original media hash differs: ' + name)
    video = source(root, args.video)
    mapping = source(root, 'video_frames.jsonl')
    receipt = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    decode = media.audit(video, 600, mapping_sha256=sha(mapping), receipt=receipt)
    media.verify_receipt(video, receipt, 600, mapping_sha256=sha(mapping))
    report = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
              'job_id': args.job, 'recording_id': args.recording_id,
              'checks': {name: True for name in CHECKS},
              'source_result_sha256': sha(result_path), 'review_sha256': sha(review_path),
              'video_sha256': sha(video), 'decoded_frames': decode['frames'],
              'observed_pass': metric['pass_observed'],
              'legal_outcome': 'unassessed_pending_independent_judgment'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def selftest(case, negative):
    result = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'measured_values': {'frame_count': 600, 'crosswalk_kind': 'marked',
                  'legal_compliance': 'unassessed', 'original_crossing_reviewed': True,
                  'original_stop_purpose_reviewed': True},
              'physical_checks': {'maneuver': {'status': 'met'}}, 'maneuver_completed': True}
    if negative:
        result['provenance_kind'] = 'synthetic_fixture'
        check_result(result, case)
        raise AssertionError('Synthetic source unexpectedly accepted')
    check_result(result, case)
    review = {'format': 'c146108-crosswalk-original-review-v1',
              'source_kind': 'original_native_review', 'case_id': case,
              'reviewer_id': 'cpu-schema-only', 'source_sha256': {'road.xodr': 'schema-only'},
              'media_sha256': {'raw.mkv': 'schema-only'}}
    for key in ('crossing_kind_and_intersection_reviewed', 'lead_stop_purpose_reviewed',
                'pedestrian_full_crossing_reviewed', 'ego_and_lead_full_bodies_reviewed',
                'rear_approach_and_pass_reviewed', 'four_camera_pixels_reviewed'):
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
        parser.add_argument('--' + name)
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)
