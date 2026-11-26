"""Independent fixed-source audit of each flashing-red halt contrast."""

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, case):
    folder = Path(attempt)
    result = read(folder / 'result.json')
    config = read(folder / 'config.json')
    geometry = read(folder / 'geometry.json')
    survey = read(folder / 'context-survey.json')
    review = read(folder / 'independent-review.json')
    if (result.get('case_id') != case or config.get('selected_case_id') != case
            or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False
            or survey.get('source_kind') != 'original_native_context_survey'
            or review.get('format') != 'worker-c111271-independent-source-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Comparison lacks independently reviewed original source')
    facts = dict(result.get('measured_values', {}))
    facts['requested_halt'] = config.get('requested_halt')
    facts['signal_head_id'] = geometry.get('signal_head_id')
    facts['official_device_source'] = geometry.get('official_device_source')
    facts['signal_head_facing_source'] = geometry.get('signal_head_facing_source')
    facts['capture_profile'] = json.dumps({key: config.get(key) for key in
        ('rate_hz', 'duration_s', 'cameras')}, sort_keys=True)
    return dict(result, measured_values=facts)


def check(left, right, comparison):
    cases = comparison['case_ids']
    if (left.get('case_id') != cases[0] or right.get('case_id') != cases[1]
            or any(row.get('provenance_kind') != 'native' or
                   row.get('diagnostic_fixture') is not False for row in (left, right))):
        raise ValueError('Comparison lacks two original exact-case Native sources')
    if any(row.get('accepted') is not False or row.get('legal_verdict_claimed') is not False
           for row in (left, right)):
        raise ValueError('Comparison prelabels legal outcome')
    a, b = left.get('measured_values', {}), right.get('measured_values', {})
    fixed = ('stopping_reference', 'stopping_reference_x_m', 'signal_head_id',
             'official_device_source', 'signal_head_facing_source', 'capture_profile')
    if any(a.get(key) is None or a.get(key) != b.get(key) for key in fixed):
        raise ValueError('Undeclared comparison source difference')
    if (a.get('frames') != 600 or b.get('frames') != 600 or
            a.get('flashing_red_transition_count', 0) < 4 or
            b.get('flashing_red_transition_count', 0) < 4):
        raise ValueError('Comparison lacks joined flashing-red source')
    if a.get('requested_halt') is not True or b.get('requested_halt') is not False:
        raise ValueError('Comparison lacks requested halt contrast')
    if comparison.get('deliberate_differences') != ['requested pre-reference halt policy']:
        raise ValueError('Comparison changed declared difference')
    return {'comparison_id': comparison['comparison_id'], 'case_ids': cases,
            'reference_kind': a['stopping_reference'],
            'requested_halt_contrast': [True, False],
            'legal_verdict_claimed': False}


def selftest(comparison, negative):
    facts = {'frames': 600, 'stopping_reference': 'limit_line',
             'stopping_reference_x_m': 48.0, 'signal_head_id': 31,
             'official_device_source': 'original survey',
             'signal_head_facing_source': 'original facing survey',
             'capture_profile': '600 frames, four cameras',
             'flashing_red_transition_count': 59, 'requested_halt': True}
    base = {'provenance_kind': 'native', 'diagnostic_fixture': False,
            'accepted': False, 'legal_verdict_claimed': False}
    left = dict(base, case_id=comparison['case_ids'][0], measured_values=dict(facts))
    right = dict(base, case_id=comparison['case_ids'][1],
                 measured_values=dict(facts, requested_halt=False))
    if negative:
        right['measured_values']['signal_head_id'] = 32
        check(left, right, comparison)
        raise AssertionError('Changed original signal source accepted')
    result = check(left, right, comparison)
    changed = dict(right, provenance_kind='synthetic_fixture')
    try:
        check(left, changed, comparison)
    except ValueError:
        pass
    else:
        raise AssertionError('Diagnostic fixture accepted as original')
    return dict(result, original_capture_attested=False, predicates_tested=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--output')
    args = parser.parse_args()
    plan = read(Path(__file__).with_name('case-plan.json'))
    comparison = next((row for row in plan['comparisons']
                       if row['comparison_id'] == args.comparison), None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
    if args.self_test:
        result = selftest(comparison, args.negative)
    else:
        result = check(source(args.left, comparison['case_ids'][0]),
                       source(args.right, comparison['case_ids'][1]), comparison)
        result.update(format='worker-c111271-original-comparison-audit-v1',
                      left_sha256=sha(Path(args.left) / 'result.json'),
                      right_sha256=sha(Path(args.right) / 'result.json'),
                      auditor_sha256=sha(__file__))
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
