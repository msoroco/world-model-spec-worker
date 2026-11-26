"""Independent original roundabout lane, follower, pass and pixel delivery gate."""
import argparse
import hashlib
import json
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source(folder, name):
    path = (folder / name).resolve()
    if folder not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original exact-case Native source')
    if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical maneuver unverified')
    facts = result.get('measured_values', {})
    counts = facts.get('counts', {})
    if (facts.get('frames') != 600 or facts.get('rate_hz') != 20
            or counts.get('follower_behind', 0) < 1
            or counts.get('ego_slower_than_follower', 0) < 1
            or sum(counts.get(k, 0) for k in
                   ('extreme_right', 'inner_left', 'outside_or_straddling')) != 600):
        raise ValueError('Original marked-lane and immediately-following traffic source unverified')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Original source prelabels legal outcome')
    return facts

def check_review(review, case, paths):
    if (review.get('format') != 'worker-c132924-independent-source-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original roundabout source review')
    for name, path in paths.items():
        if review.get('source_sha256', {}).get(name) != sha(path):
            raise ValueError('Independent review source changed: ' + name)
    required = ('same_direction_marked_lanes_reviewed', 'extreme_right_lane_reviewed',
                'immediately_following_traffic_reviewed', 'impeding_judgment_reviewed',
                'passing_necessity_reviewed', 'pass_clearance_and_return_reviewed',
                'actual_pixels_reviewed')
    if not all(review.get(name) is True for name in required):
        raise ValueError('Independent roundabout lane, traffic, pass or pixel review absent')
    if not review.get('source_documentation') or review.get('legal_verdict_claimed') is True:
        raise ValueError('Independent review lacks source documentation')
    if not review.get('reviewed_frames'):
        raise ValueError('Independent original frames absent')

def audit(args):
    from scenario_pipeline.worker_exchange import media
    folder, output, operations = (Path(v).resolve() for v in
                                  (args.attempt, args.output, args.operations))
    if operations not in output.parents or operations not in Path(__file__).resolve().parents:
        raise ValueError('Independent audit output must stay in operations')
    result = json.loads(source(folder, 'result.json').read_text())
    check_result(result, args.case)
    names = ('native.jsonl', 'geometry.json', 'context-survey.json',
             'video_frames.jsonl', 'trace.jsonl') + tuple(v + '.mkv' for v in VIEWS)
    paths = {name: source(folder, name) for name in names}
    review = json.loads(source(folder, args.review).read_text())
    check_review(review, args.case, paths)
    geometry = json.loads(paths['geometry.json'].read_text())
    survey = json.loads(paths['context-survey.json'].read_text())
    if (geometry.get('source_kind') != 'original_native'
            or survey.get('source_kind') != 'original_native_context_survey'
            or survey.get('diagnostic_fixture') is True
            or not geometry.get('same_direction_marked_lanes_source')):
        raise ValueError('Original marked same-direction lane survey absent')
    native, frames, trace = (rows(paths[name]) for name in
                             ('native.jsonl', 'video_frames.jsonl', 'trace.jsonl'))
    if len(native) != len(frames) or len(trace) != len(native) or len(native) != 600:
        raise ValueError('Original 600-frame roundabout source join differs')
    for i, (n, f, t) in enumerate(zip(native, frames, trace)):
        if (f.get('video_frame') != i or n.get('native_frame') != f.get('native_frame')
                or t.get('frame') != f.get('native_frame')
                or abs(n.get('time_s', -100) - f.get('time_s', 100)) > 1e-4):
            raise ValueError('Original roundabout motion and pixels join differs')
    decoded = {}
    for view in VIEWS:
        receipt = output.with_name(output.stem + '-' + view + '-decode.json')
        media.audit(paths[view + '.mkv'], 600,
                    mapping_sha256=sha(paths['video_frames.jsonl']), receipt=receipt)
        media.verify_receipt(paths[view + '.mkv'], receipt, 600,
                             mapping_sha256=sha(paths['video_frames.jsonl']))
        decoded[view] = sha(receipt)
    proof = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
             'checks': {name: True for name in
                        ('native_source', 'all_participants', 'time_join',
                         'full_video_decode', 'actual_pixels', 'physical_completion')},
             'source_result_sha256': sha(folder / 'result.json'),
             'independent_review_sha256': sha(folder / args.review),
             'source_decode_receipts': decoded, 'frames': 600,
             'legal_verdict_claimed': False}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof

def selftest(case, negative):
    result = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'accepted': False,
              'legal_verdict_claimed': False,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'measured_values': {'frames': 600, 'rate_hz': 20,
                                  'counts': {'follower_behind': 450,
                                             'ego_slower_than_follower': 450,
                                             'extreme_right': 600,
                                             'inner_left': 0,
                                             'outside_or_straddling': 0}}}
    if negative:
        result['measured_values']['counts']['follower_behind'] = 0
        check_result(result, case)
        raise AssertionError('Unobserved immediately following traffic accepted')
    check_result(result, case)
    for key, changed in (('provenance_kind', 'synthetic_fixture'), ('accepted', True)):
        altered = json.loads(json.dumps(result))
        altered[key] = changed
        try:
            check_result(altered, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid original-source predicate accepted: ' + key)
    return {'case_id': case, 'predicates_tested': True,
            'original_capture_attested': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--operations')
    parser.add_argument('--output')
    parser.add_argument('--review', default='independent-review.json')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
