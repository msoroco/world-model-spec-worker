"""Independent original-source acceptance audit for the controlled-access lane cases."""

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C179776__NRS-484B-587-2a__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check_result(result, case):
    if (case not in (ASSIGNMENT + '__probe_a', ASSIGNMENT + '__probe_b') or
            result.get('case_id') != case or result.get('provenance_kind') != 'native' or
            result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact original Native result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original controlled-access travel incomplete')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Saved finalizer preaccepted legal outcome')
    if result.get('physical_checks', {}).get('setup', {}).get('status') != 'met' or \
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original setup or travel proof incomplete')
    measured = result.get('measured_values', {})
    count = measured.get('outside_marked_lane_frames')
    if type(count) is not int or count < 0 or count > 600:
        raise ValueError('Original full-body lane measurement missing')
    if case.endswith('probe_a') and count != 0:
        raise ValueError('Marked-lane reference left marked lane')
    if case.endswith('probe_b') and count == 0:
        raise ValueError('Outside-lane case has no measured excursion')
    names = {item.get('name') for item in result.get('recording_evidence', [])}
    if not {'st.controlled_access', 'st.lane', 'st.lane_marking', 'rel.occupies',
            'st.shoulder', 'dev.regulatory_sign', 'drv.responding_emergency'} <= names:
        raise ValueError('Missing original controlled-access observation streams')


def check_review(review, case, paths):
    if (review.get('format') != 'c179776-independent-original-review-v1' or
            review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Independent original pixel and authority review missing')
    for name, path in paths.items():
        if review.get('source_sha256', {}).get(name) != sha(path):
            raise ValueError('Original review source changed: ' + name)
    for name in ('public_authority_verified', 'controlled_access_boundary_verified',
                 'entrance_exit_lanes_reviewed', 'lane_marking_pixels_reviewed',
                 'shoulder_surface_pixels_reviewed', 'vehicle_class_reviewed',
                 'exception_event_reviewed', 'sign_pixels_and_authority_reviewed',
                 'body_footprint_reviewed', 'physical_motion_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Independent original review incomplete: ' + name)
    frames = review.get('decisive_original_frames')
    if not isinstance(frames, list) or not frames or any(type(i) is not int or i < 0 or i >= 600 for i in frames):
        raise ValueError('Decisive original pixel frames missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Original review prelabels legal outcome')


def audit(args):
    import os
    import sys
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    repo = Path(__file__).resolve().parents[2]
    if repo / '.runtime-work' not in output_root.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange import media

    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit output must stay in local operations')
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {name: source(attempt, filename) for name, filename in {
        'designation': 'designation-source.json', 'road': 'road.xodr',
        'native_map': 'native-road-readback.json', 'actors': 'native-raw-actors.jsonl',
        'trace': 'trace.jsonl', 'frames': 'video_frames.jsonl',
        'capture_evidence': 'capture/evidence.jsonl',
        'native_status': 'native-run-status.json', 'capture_seal': 'capture-seal.json',
        'native_exit': 'native-exit.json'}.items()}
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, paths)
    status = json.loads(paths['native_status'].read_text())
    if status.get('frames') != 600 or status.get('errors') or status.get('restoration', {}).get('restored') is not True:
        raise ValueError('Original Native closure or restoration incomplete')
    actors, trace, frames = (rows(paths[name]) for name in ('actors', 'trace', 'frames'))
    if any(len(part) != 600 for part in (actors, trace, frames)):
        raise ValueError('Original 600-frame participant or camera history missing')
    actor_ids = set()
    for i, (a, t, f) in enumerate(zip(actors, trace, frames)):
        if (a.get('video_frame') != i or f.get('video_frame') != i or
                a.get('native_frame') != t.get('frame') or t.get('frame') != f.get('carla_frame') or
                abs(a.get('time_s', -999) - t.get('time_s', 999)) > 1e-4 or
                abs(t.get('time_s', -999) - f.get('time_s', 999)) > 1e-4 or
                set(f.get('camera_native_frames', {})) != set(VIEWS)):
            raise ValueError('Original actor, trace or four-camera frame join differs')
        users = a.get('actors', [])
        if len(users) != 1 or users[0].get('role') != 'ego':
            raise ValueError('Original subject participant missing')
        actor_ids.add(users[0].get('actor_id'))
    if len(actor_ids) != 1 or None in actor_ids:
        raise ValueError('Original subject continuity differs')
    decoded = {}
    for view in VIEWS:
        path = source(attempt, view + '.mkv')
        receipt = output.with_name(output.stem + '-' + view + '-decode.json')
        media.audit(path, 600, mapping_sha256=sha(paths['frames']), receipt=receipt)
        media.verify_receipt(path, receipt, 600, mapping_sha256=sha(paths['frames']))
        decoded[view] = {'video_sha256': sha(path), 'decode_sha256': sha(receipt)}
    proof = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
             'job_id': args.job, 'attempt': args.attempt_number,
             'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
             'original_source_sha256': {name: sha(path) for name, path in paths.items()},
             'full_video_decode': decoded, 'frame_count': 600,
             'checks': {name: True for name in CHECKS},
             'independent_review_sha256': sha(source(attempt, args.review)),
             'auditor_sha256': sha(Path(__file__).resolve()), 'legal_verdict_claimed': False}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'behavior_attempted': True, 'maneuver_completed': True, 'accepted': False,
              'legal_verdict_claimed': False, 'physical_checks': {'setup': {'status': 'met'},
              'maneuver': {'status': 'met'}}, 'measured_values': {
              'outside_marked_lane_frames': 0 if case.endswith('probe_a') else 400},
              'recording_evidence': [{'name': name} for name in ('st.controlled_access',
              'st.lane', 'st.lane_marking', 'rel.occupies', 'st.shoulder',
              'dev.regulatory_sign', 'drv.responding_emergency')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted as original')
    check_result(sample, case)
    for mutation in ({'provenance_kind': 'synthetic_fixture'},
                     {'physical_checks': {'setup': {'status': 'unverified'}}},
                     {'measured_values': {}}, {'recording_evidence': []}):
        try:
            check_result(dict(sample, **mutation), case)
        except ValueError:
            pass
        else:
            raise AssertionError('Incomplete original delivery accepted')
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
    parser.add_argument('--review', default='controlled-access-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative)
                     if args.self_test else audit(args), sort_keys=True))
