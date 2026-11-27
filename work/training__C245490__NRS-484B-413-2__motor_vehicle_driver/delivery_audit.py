"""Independent original signal, course, area, weather and four-view acceptance predicates."""
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
    metrics = result.get('measured_values', {})
    if (not isinstance(metrics.get('observed_continuous_distance_ft'), (int, float))
            or not isinstance(metrics.get('event_frame'), int)
            or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'
            or result.get('maneuver_completed') is not True):
        raise ValueError('Original signal distance or lane transition unproven')
    if any(key in result for key in ('legal_verdict', 'compliant', 'violating')):
        raise ValueError('Analyzer made a legal verdict')
    return metrics


def check_review(review, case):
    if (review.get('format') != 'c245490-original-signal-review-v1'
            or review.get('source_kind') != 'original_native_review'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Independent original source review missing')
    for key in ('district_class_reviewed', 'signal_pixels_reviewed',
                'full_signal_interval_reviewed', 'course_change_reviewed',
                'same_direction_lanes_reviewed', 'full_body_reviewed',
                'weather_reviewed'):
        if review.get(key) is not True:
            raise ValueError('Original source review incomplete: ' + key)
    if not review.get('district_class_basis') or not review.get('signal_visibility_finding'):
        raise ValueError('Original legal-source basis missing')
    if not review.get('source_sha256') or not review.get('media_sha256'):
        raise ValueError('Original review source hashes missing')


def rows(path):
    values = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(values) != 600:
        raise ValueError('Original 600-frame inventory incomplete')
    return values


def audit(args):
    from worker_exchange import media
    root = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = source(root, 'result.json')
    metrics = check_result(read(result_path), args.case)
    frame, signal, body, trace = (rows(source(root, name)) for name in
        ('video_frames.jsonl', 'signal-source.jsonl', 'body_history.jsonl', args.trace))
    for i, (f, s, b, t) in enumerate(zip(frame, signal, body, trace)):
        native = f.get('carla_frame')
        if (f.get('video_frame') != i or s.get('frame') != native
                or b.get('frame') != native or t.get('frame') != native
                or s.get('source_kind') != 'native'
                or abs(s.get('time_s', -100) - f.get('time_s', -200)) > 1e-6
                or abs(t.get('time_s', -100) - f.get('time_s', -200)) > 1e-6
                or len(b.get('body_vertices_m', [])) < 4
                or not isinstance(s.get('native_lane_id'), int)):
            raise ValueError('Original signal, body, lane or time join differs')
    review_path = source(root, args.review)
    review = read(review_path)
    check_review(review, args.case)
    for name, checksum in review['source_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Reviewed source hash differs: ' + name)
    required_media = {name + '.mkv' for name in CAMERAS} | {'raw.mkv'}
    if set(review['media_sha256']) != required_media:
        raise ValueError('Original four-view media inventory incomplete')
    for name, checksum in review['media_sha256'].items():
        if sha(source(root, name)) != checksum:
            raise ValueError('Reviewed original media differs: ' + name)
    decode_path = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    video = source(root, args.video)
    mapping = source(root, 'video_frames.jsonl')
    decode = media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode_path)
    media.verify_receipt(video, decode_path, 600, mapping_sha256=sha(mapping))
    report = {'format': 'worker-delivery-audit', 'passed': True,
              'case_id': args.case, 'job_id': args.job, 'recording_id': args.recording_id,
              'checks': {name: True for name in CHECKS},
              'source_result_sha256': sha(result_path), 'review_sha256': sha(review_path),
              'video_sha256': sha(video), 'decoded_frames': decode['frames'],
              'measured_continuous_signal_ft': metrics['observed_continuous_distance_ft'],
              'legal_outcome': 'pending independent source and statutory review'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def selftest(case, negative):
    result = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'measured_values': {'observed_continuous_distance_ft': 100.0, 'event_frame': 480},
              'physical_checks': {'maneuver': {'status': 'met'}}, 'maneuver_completed': True}
    if negative:
        result['provenance_kind'] = 'synthetic_fixture'
        check_result(result, case)
        raise AssertionError('Synthetic source unexpectedly accepted')
    check_result(result, case)
    review = {'format': 'c245490-original-signal-review-v1', 'source_kind': 'original_native_review',
              'case_id': case, 'reviewer_id': 'cpu-schema-only',
              'district_class_basis': 'schema-only', 'signal_visibility_finding': 'schema-only',
              'source_sha256': {'signal-source.jsonl': 'schema-only'},
              'media_sha256': {'raw.mkv': 'schema-only'}}
    for key in ('district_class_reviewed', 'signal_pixels_reviewed',
                'full_signal_interval_reviewed', 'course_change_reviewed',
                'same_direction_lanes_reviewed', 'full_body_reviewed', 'weather_reviewed'):
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
