"""Independent original-source audit of roundabout lane and passing contrasts."""
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
            or geometry.get('source_kind') != 'original_native'
            or survey.get('source_kind') != 'original_native_context_survey'
            or review.get('format') != 'worker-c132924-independent-source-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Comparison lacks independently reviewed original source')
    facts = dict(result.get('measured_values', {}))
    facts['geometry'] = {key: geometry.get(key) for key in
        ('direction', 'center_xy_m', 'outer_right_lane_radius_m',
         'inner_left_lane_radius_m', 'same_direction_marked_lanes_source')}
    facts['capture_profile'] = {key: config.get(key) for key in
        ('rate_hz', 'duration_s', 'cameras')}
    suffix = case.rsplit('__', 1)[-1]
    facts['requested_lane'] = 'extreme_right' if suffix == 'probe_a' else 'inner_left'
    facts['post_clearance_target_lane'] = ('extreme_right' if suffix == 'necessary_pass'
                                           else 'inner_left' if suffix == 'post_pass_linger'
                                           else 'not_applicable')
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
    if (not a.get('geometry') or a['geometry'] != b.get('geometry')
            or not a.get('capture_profile') or a['capture_profile'] != b.get('capture_profile')):
        raise ValueError('Undeclared comparison source difference')
    if (a.get('frames') != 600 or b.get('frames') != 600
            or any(row.get('counts', {}).get('follower_behind', 0) < 1
                   for row in (a, b))):
        raise ValueError('Comparison lacks joined immediately following traffic source')
    difference = comparison['deliberate_differences']
    if difference == ['impeding_vehicle_lane_position']:
        if (a.get('requested_lane') != 'extreme_right'
                or b.get('requested_lane') != 'inner_left'
                or a.get('counts', {}).get('extreme_right', 0) < 1
                or b.get('counts', {}).get('inner_left', 0) < 1):
            raise ValueError('Comparison lacks requested lane contrast')
    elif difference == ['post_clearance_target_lane']:
        if (a.get('post_clearance_target_lane') != 'extreme_right'
                or b.get('post_clearance_target_lane') != 'inner_left'
                or a.get('counts', {}).get('after_pass_right', 0) < 1
                or b.get('counts', {}).get('after_pass_left', 0) < 1):
            raise ValueError('Comparison lacks requested post-pass return contrast')
    else:
        raise ValueError('Comparison changed declared difference')
    return {'comparison_id': comparison['comparison_id'], 'case_ids': cases,
            'deliberate_differences': difference, 'legal_verdict_claimed': False}

def selftest(comparison, negative):
    facts = {'frames': 600, 'counts': {'follower_behind': 500,
                                      'extreme_right': 600, 'inner_left': 600,
                                      'after_pass_right': 300, 'after_pass_left': 300},
             'geometry': {'direction': 'counterclockwise',
                          'outer_right_lane_radius_m': [13, 16]},
             'capture_profile': {'rate_hz': 20, 'duration_s': 30},
             'requested_lane': 'extreme_right',
             'post_clearance_target_lane': 'extreme_right'}
    base = {'provenance_kind': 'native', 'diagnostic_fixture': False,
            'accepted': False, 'legal_verdict_claimed': False}
    left = dict(base, case_id=comparison['case_ids'][0], measured_values=dict(facts))
    right_facts = dict(facts)
    if comparison['deliberate_differences'] == ['impeding_vehicle_lane_position']:
        right_facts['requested_lane'] = 'inner_left'
    else:
        right_facts['post_clearance_target_lane'] = 'inner_left'
    right = dict(base, case_id=comparison['case_ids'][1], measured_values=right_facts)
    if negative:
        right['measured_values']['geometry'] = {'direction': 'clockwise'}
        check(left, right, comparison)
        raise AssertionError('Changed original lane geometry accepted')
    result = check(left, right, comparison)
    try:
        check(left, dict(right, provenance_kind='synthetic_fixture'), comparison)
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
        result.update(format='worker-c132924-original-comparison-audit-v1',
                      left_sha256=sha(Path(args.left) / 'result.json'),
                      right_sha256=sha(Path(args.right) / 'result.json'),
                      auditor_sha256=sha(__file__))
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
