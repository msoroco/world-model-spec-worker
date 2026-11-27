"""Independent original-source audit predicates for nighttime heavy-vehicle travel."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + relative)
    return path


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original heavy-vehicle movement or requested rest incomplete')
    if result.get('physical_acceptance_claimed') is True or result.get('legal_verdict_claimed') is True:
        raise ValueError('Source finalizer preaccepted physical or legal outcome')
    if not {'ego_pose', 'heavy_vehicle_restricted_street_operation'} <= {
            item.get('name') for item in result.get('recording_evidence', [])}:
        raise ValueError('Missing original heavy-vehicle evidence channel')
    if len(result.get('video_references', [])) != 4 or not result.get('video_frame_map_reference'):
        raise ValueError('Missing synchronized original camera sources')


def check_review(review, case, sources):
    if review.get('format') != 'c394566-original-authority-review-v1' or review.get('case_id') != case or not review.get('reviewer_id'):
        raise ValueError('Missing independent original authority review')
    for name, path in sources.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Original authority source changed: ' + name)
    for name in ('certified_unladen_weight_reviewed', 'residence_district_reviewed',
                 'truck_route_authority_reviewed', 'civil_time_reviewed',
                 'permit_and_conditions_reviewed', 'actual_pixels_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Missing independent source review: ' + name)
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError('Decisive original frame review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Independent review cannot prelabel legal outcome')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    operations = Path(args.operations).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    sources = {'route_rows': inside(attempt, 'original-route-rows.jsonl'),
               'video_frames': inside(attempt, 'video_frames.jsonl'),
               'capture_seal': inside(attempt, 'capture-seal.json'),
               'authority_context': inside(attempt, 'authority-context.json'),
               'weight': inside(attempt, 'weight.source.json'),
               'district': inside(attempt, 'district.source.json'),
               'truck_route': inside(attempt, 'truck_route.source.json'),
               'civil_clock': inside(attempt, 'civil_clock.source.json'),
               'permit': inside(attempt, 'permit.source.json')}
    check_review(json.loads(inside(attempt, args.review).read_text()), args.case, sources)
    for item in result['recording_evidence']:
        inside(attempt, item['reference'])
    actor = lines(sources['route_rows'])
    mapping = lines(sources['video_frames'])
    if len(actor) != 600 or len(mapping) != 600 or any(
            actor[i].get('native_frame') != mapping[i].get('native_frame') or
            actor[i].get('time_s') != mapping[i].get('time_s') for i in range(600)):
        raise ValueError('Original route, camera and time join differs')
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    if len(trace.read_text().splitlines()) != 600:
        raise ValueError('Original trace length differs')
    decode = output.with_name('source-decode-' + args.case.split('__')[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(sources['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600, mapping_sha256=sha(sources['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
             'job_id': args.job, 'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'frames': 600,
             'video_sha256': sha(video), 'trace_sha256': sha(trace),
             'checks': {name: True for name in CHECKS},
             'auditor_sha256': sha(Path(__file__).resolve()),
             'source_decode_receipt_sha256': sha(decode),
             'source_decode_auditor_sha256': verified['auditor_sha256'],
             'human_review_sha256': sha(inside(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'setup_confirmed': True, 'maneuver_completed': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
              'recording_evidence': [{'name': 'ego_pose'},
                                     {'name': 'heavy_vehicle_restricted_street_operation'}],
              'video_references': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl'}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', []),
                       ('video_references', [])):
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
    parser.add_argument('--trace', default='trace.jsonl')
    parser.add_argument('--video', default='overview.mkv')
    parser.add_argument('--review', default='authority-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    options = parser.parse_args()
    print(json.dumps(selftest(options.case, options.negative) if options.self_test else audit(options)))
