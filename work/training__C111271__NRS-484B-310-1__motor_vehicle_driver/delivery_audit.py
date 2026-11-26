"""Independent original-source review gate for NRS 484B.310(1)."""

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


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original exact-case Native source')
    if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical maneuver unverified')
    facts = result.get('measured_values', {})
    if (facts.get('frames') != 600 or facts.get('stopping_reference') not in
            ('limit_line', 'crosswalk', 'intersection') or
            facts.get('flashing_red_transition_count', 0) < 4):
        raise ValueError('Original flashing-red reference source unverified')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Original source prelabels legal outcome')
    return facts


def check_review(review, case, paths, reference):
    if (review.get('format') != 'worker-c111271-independent-source-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')
            or review.get('reference_kind') != reference):
        raise ValueError('Missing independent original signal and reference review')
    for name, path in paths.items():
        if review.get('source_sha256', {}).get(name) != sha(path):
            raise ValueError('Independent review source changed: ' + name)
    if not all(review.get(name) is True for name in (
            'official_device_reviewed', 'signal_facing_and_flashes_reviewed',
            'reference_hierarchy_reviewed', 'full_stop_and_yield_reviewed',
            'actual_pixels_reviewed')):
        raise ValueError('Independent official-device, stop or pixel review absent')
    if not review.get('source_documentation') or review.get('legal_verdict_claimed') is True:
        raise ValueError('Independent review lacks source documentation')
    if not review.get('reviewed_frames'):
        raise ValueError('Independent original frames absent')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    folder = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    operations = Path(args.operations).resolve()
    if operations not in output.parents or operations not in Path(__file__).resolve().parents:
        raise ValueError('Independent audit output must stay in operations')
    result = json.loads(source(folder, 'result.json').read_text())
    facts = check_result(result, args.case)
    names = ('native.jsonl', 'geometry.json', 'context-survey.json',
             'video_frames.jsonl', 'trace.jsonl') + tuple(v + '.mkv' for v in VIEWS)
    paths = {name: source(folder, name) for name in names}
    review = json.loads(source(folder, args.review).read_text())
    check_review(review, args.case, paths, facts['stopping_reference'])
    native = lines(paths['native.jsonl'])
    frame_map = lines(paths['video_frames.jsonl'])
    trace = lines(paths['trace.jsonl'])
    if len(native) != len(frame_map) or len(trace) != len(native) or len(native) != 600:
        raise ValueError('Original 600-frame source join differs')
    for i, (n, f, t) in enumerate(zip(native, frame_map, trace)):
        if (f.get('video_frame') != i or n.get('native_frame') != f.get('native_frame')
                or t.get('frame') != f.get('native_frame')
                or abs(n.get('time_s', -100) - f.get('time_s', 100)) > 1e-4):
            raise ValueError('Original signal, motion and pixels join differs')
    survey = json.loads(paths['context-survey.json'].read_text())
    if (survey.get('source_kind') != 'original_native_context_survey'
            or survey.get('diagnostic_fixture') is True):
        raise ValueError('Original official-device survey absent')
    decoded = {}
    for view in VIEWS:
        receipt = output.with_name(output.stem + '-' + view + '-decode.json')
        media.audit(paths[view + '.mkv'], 600,
                    mapping_sha256=sha(paths['video_frames.jsonl']), receipt=receipt)
        media.verify_receipt(paths[view + '.mkv'], receipt, 600,
                             mapping_sha256=sha(paths['video_frames.jsonl']))
        decoded[view] = sha(receipt)
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'checks': {name: True for name in
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
              'measured_values': {'frames': 600, 'stopping_reference': 'limit_line',
                                  'flashing_red_transition_count': 59}}
    if negative:
        result['measured_values']['flashing_red_transition_count'] = 0
        check_result(result, case)
        raise AssertionError('Unobserved flashing-red phase accepted')
    check_result(result, case)
    for key, changed in (('provenance_kind', 'synthetic_fixture'),
                         ('accepted', True)):
        alter = json.loads(json.dumps(result))
        alter[key] = changed
        try:
            check_result(alter, case)
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
