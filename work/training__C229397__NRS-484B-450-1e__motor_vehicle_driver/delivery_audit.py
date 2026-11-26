"""Independent original-source crosswalk delivery audit and CPU rejection test."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + relative)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original crosswalk motion or sustained rest incomplete')
    measured = result.get('measured_values', {})
    if (measured.get('frames') != 600 or measured.get('rest_frames', 0) < 1
            or measured.get('source_kind') != 'original_native'):
        raise ValueError('Missing original crosswalk footprint measurement')
    if {'crosswalk_observation', 'exception_authority'} != {
            item.get('name') for item in result.get('recording_evidence', [])}:
        raise ValueError('Missing crosswalk or authority source channel')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Source finalizer preaccepted outcome')


def check_review(review, case, paths):
    if (review.get('format') != 'c229397-crosswalk-original-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original crosswalk review')
    for name, path in paths.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Original review source changed: ' + name)
    if not all(review.get(name) is True for name in
               ('crosswalk_polygon_reviewed', 'vehicle_footprint_reviewed',
                'activity_reviewed', 'traffic_and_direction_sources_reviewed',
                'actual_pixels_reviewed')):
        raise ValueError('Original source/activity/pixels unreviewed')
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(i) is not int or i < 0 or i >= 600 for i in frames):
        raise ValueError('Decisive original pixel frame review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Original review cannot prelabel legal outcome')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    sources = {'video_frames': inside(attempt, 'video_frames.jsonl'),
               'crosswalk': inside(attempt, 'crosswalk-source.json'),
               'actor': inside(attempt, 'actor-sources.jsonl'),
               'camera': inside(attempt, 'camera-frames.jsonl'),
               'exception_context': inside(attempt, 'exception-context.json')}
    check_review(json.loads(inside(attempt, args.review).read_text()), args.case, sources)
    for entry in result['recording_evidence']:
        inside(attempt, entry['reference'])
    mapping = rows(sources['video_frames'])
    actor = rows(sources['actor'])
    camera = rows(sources['camera'])
    if len(mapping) != 600 or len(actor) != 600 or len(camera) != 2400:
        raise ValueError('Original source frame count differs')
    if any(mapping[i].get('video_frame') != i or actor[i].get('native_frame') !=
           mapping[i].get('native_frame') for i in range(600)):
        raise ValueError('Original source time join differs')
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(sources['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(sources['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
        'case_id': args.case, 'job_id': args.job, 'attempt': args.attempt_number,
        'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
        'frames': 600, 'video_sha256': sha(video), 'trace_sha256': sha(trace),
        'checks': {name: True for name in CHECKS},
        'auditor_sha256': sha(Path(__file__).resolve()),
        'source_decode_receipt_sha256': sha(decode),
        'source_decode_auditor_sha256': verified['auditor_sha256'],
        'human_review_sha256': sha(inside(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native',
        'diagnostic_fixture': False, 'setup_confirmed': True,
        'maneuver_completed': True, 'accepted': False,
        'legal_verdict_claimed': False,
        'measured_values': {'frames': 600, 'rest_frames': 100,
                            'source_kind': 'original_native'},
        'recording_evidence': [{'name': 'crosswalk_observation'},
                               {'name': 'exception_authority'}]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('measured_values', {}),
                       ('recording_evidence', [])):
        changed = json.loads(json.dumps(sample))
        changed[key] = value
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
    parser.add_argument('--review', default='crosswalk-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    a = parser.parse_args()
    print(json.dumps(selftest(a.case, a.negative) if a.self_test else audit(a)))
