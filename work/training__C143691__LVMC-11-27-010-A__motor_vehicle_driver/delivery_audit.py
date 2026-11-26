"""Independent original trail-delivery audit; CPU selftest proves rejection only."""
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
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact Native trail result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original trail motion incomplete')
    measured = result.get('measured_values', {})
    if (not isinstance(measured.get('occupancy_frames'), int) or
            measured.get('vehicle_blueprint_id') in (None, 'not_recorded')):
        raise ValueError('Missing original source: footprint or vehicle identity')
    if (result.get('physical_acceptance_claimed') is not False or
            result.get('legal_verdict_claimed') is not False):
        raise ValueError('Source finalizer preaccepted trail outcome')
    if {row.get('name') for row in result.get('recording_evidence', [])} != {
            'trail_occupancy', 'trail_source_context'}:
        raise ValueError('Missing original trail recording channels')


def check_review(review, case, paths):
    if (review.get('format') != 'c143691-original-trail-review-v1' or
            review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent trail review')
    for name, path in paths.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Original trail review source changed: ' + name)
    for name in ('official_plan_reviewed', 'city_dedication_reviewed',
                 'sign_content_and_authority_reviewed', 'vehicle_identity_reviewed',
                 'right_of_way_use_reviewed', 'actual_pixels_reviewed',
                 'barrier_clearance_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Independent original trail review incomplete: ' + name)
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600
                         for frame in frames):
        raise ValueError('Decisive original pixel review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Review cannot prelabel legal outcome')


def audit(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime' /
                           'scenario_pipeline'))
    from worker_exchange import media

    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {'poses': source(attempt, 'vehicle-poses.jsonl'),
             'cameras': source(attempt, 'camera-frames.jsonl'),
             'video_frames': source(attempt, 'video_frames.jsonl'),
             'authority': source(attempt, 'trail-authority-context.json'),
             'inventory': source(attempt, 'trail-inventory.json'),
             'road': source(attempt, 'road.xodr')}
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, paths)
    poses = [json.loads(line) for line in paths['poses'].read_text().splitlines()]
    cameras = [json.loads(line) for line in paths['cameras'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['video_frames'].read_text().splitlines()]
    if len(poses) != 600 or len(cameras) != 2400 or len(frames) != 600:
        raise ValueError('Original trail/camera source frame count differs')
    if any(poses[i]['native_frame'] != frames[i]['native_frame'] or
           poses[i]['video_frame'] != i or frames[i]['video_frame'] != i
           for i in range(600)):
        raise ValueError('Original trail/video frame join differs')
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    trace = source(attempt, args.trace)
    video = source(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(paths['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(paths['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'frames': 600,
             'video_sha256': sha(video), 'trace_sha256': sha(trace),
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
              'measured_values': {'occupancy_frames': 600,
                                  'vehicle_blueprint_id': 'vehicle.test'},
              'recording_evidence': [{'name': 'trail_occupancy'},
                                     {'name': 'trail_source_context'}]}
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
    parser.add_argument('--operations')
    parser.add_argument('--output')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--video', default='primary.mkv')
    parser.add_argument('--review', default='trail-original-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative)
                     if args.self_test else audit(args)))
