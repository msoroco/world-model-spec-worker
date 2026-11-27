"""Independent original-source beam delivery audit; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from civil_clock_review import verify as verify_civil_clock
from lighting_trigger_review import verify as verify_incorporated_trigger

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + str(relative))
    return path


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Missing exact original Native beam result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original shoulder/oncoming physical completion missing')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Original beam result improperly claims acceptance or law')
    measured = result.get('measured_values', {})
    if measured.get('frames') != 600 or measured.get('within_500_feet_frames', 0) <= 0:
        raise ValueError('Original approach did not reach measured 500-foot zone')
    if case.endswith('__condition_a') and measured.get('preentry_low_beam_request_frames', 0) <= 0:
        raise ValueError('Original pre-entry low-beam request missing')
    if not {'sig.headlamp', 'rel.oncoming', 'rel.centre_distance', 'env.civil_time',
            'st.shoulder'} <= {row.get('name') for row in result.get('recording_evidence', [])}:
        raise ValueError('Original beam evidence channels incomplete')


def check_review(review, case, sources):
    if review.get('format') != 'c183394-original-beam-optical-review' or \
            review.get('source_kind') != 'independent_original_review' or \
            review.get('case_id') != case or not review.get('reviewer_id'):
        raise ValueError('Independent original beam review missing')
    for name, path in sources.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Original optical review source hash changed: ' + name)
    if review.get('incorporated_NRS_484D_100_trigger_verified') is not True or \
            review.get('adjacent_highway_shoulder_verified') is not True or \
            review.get('oncoming_driver_eye_region_verified') is not True:
        raise ValueError('Original lighting, shoulder or eye context unverified')
    if type(review.get('glaring_rays_in_oncoming_eyes')) is not bool or \
            type(review.get('sufficient_forward_illumination')) is not bool:
        raise ValueError('Original beam optical judgments missing')
    frames = review.get('reviewed_frames')
    if not isinstance(frames, list) or not frames or any(type(i) is not int or i < 0 or i >= 600 for i in frames):
        raise ValueError('Original decisive pixel review missing')


def check_join(frame_map, trace):
    frames = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = json.loads(trace.read_text()).get('scenes', [])
    if len(frames) != 600 or len(scenes) != 600 or any(
            frame.get('video_frame') != index or
            scene.get('t') != round(frame['time_s'] * 1000)
            for index, (frame, scene) in enumerate(zip(frames, scenes))):
        raise ValueError('Original beam frame/Core time join differs')
    return 600


def audit(args):
    from worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent auditor must run inside local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {name: inside(attempt, rel) for name, rel in {
        'frame_map': 'video_frames.jsonl', 'beam_rows': 'beam-rows.jsonl',
        'road_position': 'road-position-source.json',
        'lighting_trigger': 'lighting-trigger-source.json',
        'oncoming_driver': 'oncoming-driver-source.json',
        'eye_region': 'eye-region-source.json',
        'video': args.video}.items()}
    review = inside(attempt, args.review)
    check_review(json.loads(review.read_text()), args.case, paths)
    trigger = json.loads(paths['lighting_trigger'].read_text()).get('lighting_trigger')
    trigger_review = inside(attempt, 'civil-clock-review.json' if trigger == 'night_interval'
                            else 'incorporated-trigger-review.json')
    trigger_value = json.loads(trigger_review.read_text())
    if trigger == 'night_interval':
        verify_civil_clock(trigger_value, attempt, args.case)
    elif trigger in ('poor_visibility', 'official_device'):
        expected = ('1000ft_discernibility' if trigger == 'poor_visibility'
                    else 'official_device_direction')
        if trigger_value.get('branch') != expected:
            raise ValueError('Independent trigger review differs from exact branch')
        verify_incorporated_trigger(trigger_value, attempt, args.case)
    else:
        raise ValueError('Unknown incorporated lighting trigger source')
    for evidence in result['recording_evidence']:
        inside(attempt, evidence['reference'])
    trace = inside(attempt, args.trace)
    count = check_join(paths['frame_map'], trace)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(paths['video'], count, mapping_sha256=sha(paths['frame_map']), receipt=decode)
    verified = media.verify_receipt(paths['video'], decode, count,
                                    mapping_sha256=sha(paths['frame_map']))
    payload = {'format': 'worker-delivery-audit', 'passed': True,
        'case_id': args.case, 'job_id': args.job, 'attempt': args.attempt_number,
        'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
        'frames': count, 'video': args.video, 'video_sha256': sha(paths['video']),
        'trace': args.trace, 'trace_sha256': sha(trace),
        'checks': {name: True for name in CHECKS},
        'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': sha(__file__),
        'source_decode_receipt_path': str(decode),
        'source_decode_receipt_sha256': sha(decode),
        'source_decode_auditor_sha256': verified['auditor_sha256'],
        'human_review_sha256': sha(review),
        'incorporated_trigger_review_sha256': sha(trigger_review),
        'legal_verdict_claimed': False}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
        'setup_confirmed': True, 'maneuver_completed': True,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'measured_values': {'frames': 600, 'within_500_feet_frames': 100,
                            'preentry_low_beam_request_frames': 10},
        'recording_evidence': [{'name': name} for name in
            ('sig.headlamp', 'rel.oncoming', 'rel.centre_distance', 'env.civil_time', 'st.shoulder')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic fixture accepted')
    check_result(sample, case)
    review = {'format': 'c183394-original-beam-optical-review',
        'source_kind': 'independent_original_review', 'case_id': case,
        'reviewer_id': 'cpu-predicate-test',
        'incorporated_NRS_484D_100_trigger_verified': True,
        'adjacent_highway_shoulder_verified': True,
        'oncoming_driver_eye_region_verified': True,
        'glaring_rays_in_oncoming_eyes': False,
        'sufficient_forward_illumination': True, 'reviewed_frames': [200]}
    # Exercise source binding without pretending this synthetic object is an original review.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        source = Path(tmp) / 'source'; source.write_text('diagnostic source\n')
        review['video_sha256'] = sha(source)
        check_review(review, case, {'video': source})
        review['reviewed_frames'] = []
        try:
            check_review(review, case, {'video': source})
        except ValueError:
            pass
        else:
            raise AssertionError('Missing reviewed pixels accepted')
    for key, value in (('maneuver_completed', False), ('measured_values', {})):
        changed = json.loads(json.dumps(sample)); changed[key] = value
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
    parser.add_argument('--video', default='raw.mkv')
    parser.add_argument('--review', default='beam-optical-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    arguments = parser.parse_args()
    print(json.dumps(selftest(arguments.case, arguments.negative) if arguments.self_test else audit(arguments), indent=2))
