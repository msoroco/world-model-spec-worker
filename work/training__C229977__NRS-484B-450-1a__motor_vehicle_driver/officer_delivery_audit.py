"""Independent sidewalk and officer-candidate source audit."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original sidewalk source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original sidewalk source: exact Native result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original sidewalk stop motion incomplete')
    measured = result.get('measured_values', {})
    if (not isinstance(measured.get('rest_frames'), int) or
            not isinstance(measured.get('rest_and_overlap_frames'), int) or
            measured.get('officer_candidate_actor_count') not in (0, 1) or
            measured.get('actor_id') is None):
        raise ValueError('Missing original sidewalk source: body/rest measurements')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Selected finalizer preaccepted sidewalk outcome')
    needed = {'vehicle_body_pose', 'vehicle_speed', 'sidewalk_overlap',
              'sidewalk_map_context', 'exception_authority_context',
              'officer_candidate_trajectory'}
    if not needed <= {row.get('name') for row in result.get('recording_evidence', [])}:
        raise ValueError('Missing original sidewalk recording channels')


def check_review(review, case, paths):
    if (review.get('format') != 'c229977-original-officer-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent sidewalk review')
    for name, path in paths.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Sidewalk review source changed: ' + name)
    for name in ('sidewalk_surface_source_reviewed', 'vehicle_body_reviewed',
                 'stop_interval_reviewed', 'exception_authority_reviewed', 'officer_identity_reviewed',
                 'officer_direction_reviewed', 'temporal_compliance_reviewed',
                 'actual_pixels_reviewed', 'physical_completion_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Independent sidewalk review incomplete: ' + name)
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError('Decisive original pixel review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Review cannot prelabel legal outcome')


def audit(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime' / 'scenario_pipeline'))
    from worker_exchange import media

    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {'vehicle_trace': source(attempt, 'vehicle-trace.jsonl'),
             'officer_trace': source(attempt, 'officer-trace.jsonl'),
             'cameras': source(attempt, 'camera-frames.jsonl'),
             'video_frames': source(attempt, 'video_frames.jsonl'),
             'map_packet': source(attempt, 'map-packet.json'),
             'authority_context': source(attempt, 'authority-context.json'),
             'road': source(attempt, 'native-road.xodr')}
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, paths)
    trace = [json.loads(line) for line in paths['vehicle_trace'].read_text().splitlines()]
    officers = [json.loads(line) for line in paths['officer_trace'].read_text().splitlines()]
    cameras = [json.loads(line) for line in paths['cameras'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['video_frames'].read_text().splitlines()]
    if (len(trace) != 600 or len(officers) != 600 or
            len(cameras) != 2400 or len(frames) != 600):
        raise ValueError('Original sidewalk/camera frame count differs')
    if any(trace[i]['native_frame'] != frames[i]['native_frame'] or
           trace[i]['frame'] != i or frames[i]['video_frame'] != i
           for i in range(600)):
        raise ValueError('Original sidewalk/video frame join differs')
    if any(officers[i].get('frame') != i or
           officers[i].get('native_frame') != frames[i]['native_frame'] or
           abs(float(officers[i]['time_s']) - frames[i]['time_s']) > 1e-4
           for i in range(600)):
        raise ValueError('Original officer-candidate/video frame join differs')
    expected_presence = args.case.endswith('_present')
    if any((row.get('actor_id') is not None) is not expected_presence or
           row.get('source_kind') != 'original_native_post_tick' or
           row.get('identity_verified') is not False or
           row.get('direction_observed') is not None
           for row in officers):
        raise ValueError('Original officer candidate source differs from request')
    if measured['officer_candidate_actor_count'] != int(expected_presence):
        raise ValueError('Original officer candidate count differs from request')
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    converted = source(attempt, args.trace)
    video = source(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(paths['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(paths['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'frames': 600,
             'video_sha256': sha(video), 'trace_sha256': sha(converted),
             'checks': {name: True for name in CHECKS},
             'auditor_sha256': sha(Path(__file__).resolve()),
             'source_decode_receipt_sha256': sha(decode),
             'source_decode_auditor_sha256': verified['auditor_sha256'],
             'human_review_sha256': sha(source(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'behavior_attempted': True,
              'maneuver_completed': True, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'measured_values': {'rest_frames': 200,
                                  'rest_and_overlap_frames': 100,
                                  'officer_candidate_actor_count': int(case.endswith('_present')),
                                  'actor_id': 107},
              'recording_evidence': [{'name': name} for name in (
                  'vehicle_body_pose', 'vehicle_speed', 'sidewalk_overlap',
                  'sidewalk_map_context', 'exception_authority_context',
                  'officer_candidate_trajectory')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', []),
                       ('measured_values', {})):
        changed = {**sample, key: value}
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing original source accepted: ' + key)
    return {'case_id': case, 'source_predicates_tested': True,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--video', default='primary.mkv')
    parser.add_argument('--review', default='officer-original-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative)
                     if args.self_test else audit(args)))
