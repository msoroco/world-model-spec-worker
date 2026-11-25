"""Independent original-source audit for a fire-station entrance parking capture."""
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
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is True):
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original parking setup or sustained stop incomplete')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer improperly preaccepted legal or physical outcome')
    measured = result.get('measured_values', {})
    if (measured.get('frame_count') != 600 or measured.get('stationary_sample_count', 0) < 100
            or not isinstance(measured.get('stationary_min_body_edge_gap_m'), (int, float))
            or not result.get('realized_observables')):
        raise ValueError('Missing source-bound entrance parking measurement')
    names = {row.get('name') for row in result.get('recording_evidence', [])}
    if 'parking_geometry' not in names:
        raise ValueError('Original parking geometry channel missing')


def check_review(review, case, frame_map, context, motion, authority):
    source = json.loads(context.read_text())
    if (review.get('format') != 'c229410-original-entrance-review-v1'
            or review.get('source_kind') != 'original_native_review'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original entrance review')
    for name, path in (('video_frames_sha256', frame_map),
                       ('entrance_context_sha256', context),
                       ('native_vehicle_sha256', motion),
                       ('authority_manifest_sha256', authority)):
        if review.get(name) != sha(path):
            raise ValueError('Original entrance source review hash changed: ' + name)
    if (review.get('initial_activity') != source.get('initial_activity')
            or review.get('exception_context') != source.get('exception_context')):
        raise ValueError('Independent activity or exception finding differs')
    if not all(review.get(name) is True for name in
               ('fire_station_identity_verified', 'driveway_entrance_verified',
                'highway_side_verified', 'parking_activity_reviewed',
                'traffic_conflict_reviewed', 'law_officer_device_direction_reviewed',
                'actual_pixels_reviewed')):
        raise ValueError('Independent source, activity, exception or pixels unreviewed')
    pixels = review.get('reviewed_frames', [])
    if (len(lines(frame_map)) != 600 or not pixels
            or any(type(i) is not int or i < 0 or i >= 600 for i in pixels)):
        raise ValueError('Decisive original pixel frame review missing')
    if review.get('statutory_reference_method_adopted') is True:
        raise ValueError('Unreviewed statutory distance method claimed')


def check_join(frame_map, trace, motion):
    mapping = lines(frame_map)
    scenes = json.loads(trace.read_text()).get('scenes', [])
    native = lines(motion)
    if len(mapping) != 600 or len(scenes) != 600 or len(native) != 600:
        raise ValueError('Original frame/Core/parking count mismatch')
    for index, (frame, scene, row) in enumerate(zip(mapping, scenes, native)):
        if (frame.get('video_frame') != index or row.get('video_frame') != index
                or scene.get('t') != round(frame['time_s'] * 1000)
                or frame.get('native_frame') != row.get('native_frame')):
            raise ValueError('Original frame/Core/parking timestamp mismatch')
    return 600


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent auditor must run inside local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    frame_map = inside(attempt, 'video_frames.jsonl')
    context = inside(attempt, 'entrance-context.json')
    config = json.loads(inside(attempt, 'config.json').read_text())
    source = json.loads(context.read_text())
    if (config.get('initial_activity') != source.get('initial_activity')
            or config.get('exception_context') != source.get('exception_context')
            or result['measured_values'].get('initial_activity') != source.get('initial_activity')
            or result['measured_values'].get('exception_context') != source.get('exception_context')):
        raise ValueError('Original source, selected branch and measured activity differ')
    motion = inside(attempt, 'native-vehicle.jsonl')
    authority = inside(attempt, 'authority/manifest.json')
    review = inside(attempt, args.review)
    check_review(json.loads(review.read_text()), args.case, frame_map, context, motion, authority)
    for row in result['recording_evidence']:
        inside(attempt, row['reference'])
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    frames = check_join(frame_map, trace, motion)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, frames, mapping_sha256=sha(frame_map), receipt=decode)
    verified = media.verify_receipt(video, decode, frames, mapping_sha256=sha(frame_map))
    payload = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
               'job_id': args.job, 'attempt': args.attempt_number,
               'recording_id': args.recording_id,
               'source_result_sha256': sha(result_path), 'frames': frames,
               'video': args.video, 'video_sha256': sha(video),
               'trace': args.trace, 'trace_sha256': sha(trace),
               'checks': {name: True for name in CHECKS},
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(Path(__file__).resolve()),
               'source_decode_receipt_path': str(decode),
               'source_decode_receipt_sha256': sha(decode),
               'source_decode_auditor_sha256': verified['auditor_sha256'],
               'human_review_sha256': sha(review),
               'physical_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'maneuver_completed': True,
              'setup_confirmed': True, 'accepted': False,
              'legal_verdict_claimed': False,
              'realized_observables': {'raw_gap_m': {'value': 1.5, 'unit': 'm'}},
              'measured_values': {'frame_count': 600, 'stationary_sample_count': 100,
                                  'stationary_min_body_edge_gap_m': 1.5},
              'recording_evidence': [{'name': 'parking_geometry'}]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('realized_observables', {})):
        damaged = json.loads(json.dumps(sample))
        damaged[key] = value
        try:
            check_result(damaged, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing physical source accepted')
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
    parser.add_argument('--review', default='entrance-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args), indent=2))
