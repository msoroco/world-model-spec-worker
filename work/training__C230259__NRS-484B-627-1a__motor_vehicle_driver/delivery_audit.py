"""Independent original-source review gate for the slow-traffic comparison."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, rel):
    path = (root / rel).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + str(rel))
    return path


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original slow-traffic movement or setup incomplete')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer improperly preaccepted legal or physical outcome')
    measured = result.get('measured_values', {})
    if (measured.get('frame_count') != 600 or
            not isinstance(measured.get('closest_right_body_edge_to_paved_edge_m'), (int, float)) or
            not result.get('realized_observables')):
        raise ValueError('Missing source-bound slow-traffic measurement')
    names = {row.get('name') for row in result.get('recording_evidence', [])}
    if not {'participant_footprints', 'participant_velocity_and_intent'} <= names:
        raise ValueError('Missing original participant observations')


def check_review(review, case, frame_map, context, samples):
    if (review.get('format') != 'c230259-original-slow-traffic-review-v1' or
            review.get('source_kind') != 'original_native_review' or
            review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original slow-traffic review')
    for name, path in (('video_frames_sha256', frame_map),
                       ('slow_traffic_context_sha256', context),
                       ('slow_traffic_trace_sha256', samples)):
        if review.get(name) != sha(path):
            raise ValueError('Original source review hash changed: ' + name)
    if (review.get('public_highway_verified') is not True or
            review.get('one_lane_each_direction_verified') is not True or
            review.get('paved_width_permits_verified') is not True or
            review.get('following_impediment_verified') is not True or
            review.get('lateral_placement_verified') is not True):
        raise ValueError('Independent law-context or body placement review missing')
    pixels = review.get('reviewed_frames', [])
    if (len(frame_map.read_text().splitlines()) != 600 or not pixels or
            any(type(i) is not int or i < 0 or i >= 600 for i in pixels)):
        raise ValueError('Missing reviewed original decisive pixels')


def check_join(frame_map, trace, samples):
    frames = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = json.loads(trace.read_text()).get('scenes', [])
    native = [json.loads(line) for line in samples.read_text().splitlines()]
    if len(frames) != 600 or len(scenes) != 600 or len(native) != 600:
        raise ValueError('Original frame/Core/participant count mismatch')
    for index, (frame, scene, row) in enumerate(zip(frames, scenes, native)):
        if (frame.get('video_frame') != index or row.get('video_frame') != index or
                scene.get('t') != round(frame['time_s'] * 1000) or
                frame.get('native_frame') != row.get('native_frame')):
            raise ValueError('Original frame/Core/participant timestamp mismatch')
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
    context = inside(attempt, 'slow-traffic-context.json')
    samples = inside(attempt, 'slow-traffic-trace.jsonl')
    review = inside(attempt, args.review)
    check_review(json.loads(review.read_text()), args.case, frame_map, context, samples)
    for row in result['recording_evidence']:
        inside(attempt, row['reference'])
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    frames = check_join(frame_map, trace, samples)
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
              'maneuver_completed': True, 'setup_confirmed': True,
              'accepted': False, 'legal_verdict_claimed': False,
              'realized_observables': {'body_edge_m': {'value': 0.6, 'unit': 'm'}},
              'measured_values': {'frame_count': 600,
                                  'closest_right_body_edge_to_paved_edge_m': 0.6},
              'recording_evidence': [{'name': name} for name in
                  ('participant_footprints', 'participant_velocity_and_intent')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_local_diagnostic'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('realized_observables', {})):
        changed = json.loads(json.dumps(sample))
        changed[key] = value
        try:
            check_result(changed, case)
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
    parser.add_argument('--review', default='slow-traffic-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    arguments = parser.parse_args()
    print(json.dumps(selftest(arguments.case, arguments.negative) if arguments.self_test else audit(arguments), indent=2))
