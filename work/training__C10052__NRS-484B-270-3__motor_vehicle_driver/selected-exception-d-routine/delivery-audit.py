"""Independent Native electric-scooter exception_d-clearance delivery audit and CPU rejection self-test."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + relative)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is True):
        raise ValueError('Missing original Native exception_d source')
    if result.get('maneuver_completed') is not True:
        raise ValueError('Original exception_d clearance maneuver incomplete')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer claimed acceptance before independent review')
    evidence = {row.get('name') for row in result.get('recording_evidence', [])}
    if not {'exception_context', 'ru.vehicle', 'native_body_pose_control', 'camera_frame_join'} <= evidence:
        raise ValueError('Original exception_d, ego or camera source missing')
    observed = result.get('realized_observables', {})
    if not observed or not result.get('physical_checks', {}).get('maneuver'):
        raise ValueError('Source-bound exception_d physical completion missing')


def check_join(frame_map, exception_d_samples):
    mapping, exception_d = rows(frame_map), rows(exception_d_samples)
    if len(mapping) != 600 or len(exception_d) != 600:
        raise ValueError('Original exception_d/frame count mismatch')
    for index, (frame, sample) in enumerate(zip(mapping, exception_d)):
        if (frame.get('video_frame') != index
                or frame.get('native_frame') != sample.get('native_frame')
                or abs(frame.get('time_s', -100) - sample.get('time_s', 100)) > 1e-6):
            raise ValueError('Original exception_d/frame timestamp mismatch')
    return 600


def check_review(review, case, frame_map, exception_d_samples, geometry, video):
    if (review.get('format') != 'c10052-original-exception_d-review-v1'
            or review.get('case_id') != case
            or review.get('source_kind') != 'original_native_review'
            or not review.get('reviewer_id')):
        raise ValueError('Missing independent original exception_d review')
    for key, path in (('frame_map_sha256', frame_map),
                      ('exception_d_samples_sha256', exception_d_samples),
                      ('exception_d_geometry_sha256', geometry),
                      ('primary_video_sha256', video)):
        if review.get(key) != sha(path):
            raise ValueError('Original review source changed: ' + key)
    if not all(review.get(key) is True for key in (
            'assignment_provenance_reviewed', 'official_duty_reviewed',
            'ego_body_and_lane_reviewed',
            'facility_designation_reviewed', 'exception_context_reviewed',
            'actual_pixels_reviewed')):
        raise ValueError('Original exception_d/facility/pixel review incomplete')
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600
                         for frame in frames):
        raise ValueError('Decisive original pixel frames missing')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    frame_map = source(attempt, 'video_frames.jsonl')
    exception_d = source(attempt, 'exception_d_native_samples.jsonl')
    geometry = source(attempt, 'road_geometry.json')
    video = source(attempt, args.video)
    trace = source(attempt, args.trace)
    review_path = source(attempt, args.review)
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    count = check_join(frame_map, exception_d)
    check_review(json.loads(review_path.read_text()), args.case,
                 frame_map, exception_d, geometry, video)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode.json')
    media.audit(video, count, mapping_sha256=sha(frame_map), receipt=decode)
    media.verify_receipt(video, decode, count, mapping_sha256=sha(frame_map))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'checks': {key: True for key in CHECKS},
             'source_result_sha256': sha(result_path),
             'exception_d_samples_sha256': sha(exception_d), 'review_sha256': sha(review_path),
             'video_sha256': sha(video), 'trace_sha256': sha(trace),
             'decode_receipt_sha256': sha(decode), 'frames': count,
             'auditor_sha256': sha(Path(__file__))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'maneuver_completed': True,
              'accepted': False, 'legal_verdict_claimed': False,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'realized_observables': {'exception_d_clearance_s': 2.25},
              'recording_evidence': [{'name': name} for name in (
                  'exception_context', 'ru.vehicle', 'native_body_pose_control', 'camera_frame_join')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic exception_d evidence accepted')
    check_result(sample, case)
    for key, bad in (('maneuver_completed', False),
                     ('realized_observables', {}),
                     ('recording_evidence', [])):
        damaged = json.loads(json.dumps(sample))
        damaged[key] = bad
        try:
            check_result(damaged, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing exception_d evidence accepted')
    return {'case_id': case, 'source_predicates_tested': True,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--video', default='converted/primary.mkv')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--review', default='original-exception_d-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative)
                     if args.self_test else audit(args), indent=2))
