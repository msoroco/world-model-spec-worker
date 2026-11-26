"""Independent source comparison of exact median opening versus divider crossing."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUP = 'opening_vs_divider'
SUFFIXES = ('through_opening', 'across_divider')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    values = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(values) != 600:
        raise ValueError('Comparison lacks 600 original frames')
    return values


def requests():
    result = []
    for suffix in SUFFIXES:
        construction = read(HERE/'native/bundles'/suffix/'construction.json')
        content = next(item['content'] for item in construction['files']
                       if item['path'] == 'request.json')
        result.append(json.loads(content))
    return result


def verify_requests(values):
    first, second = values
    changed = {name for name in set(first)|set(second)
               if first.get(name) != second.get(name)}
    expected = {'case', 'target_crossing_x_m', 'physical_target',
                'route_waypoints_xy_m'}
    if changed != expected:
        raise ValueError('Uncontrolled authored median comparison: '+str(changed))
    if first['source_map'] != second['source_map'] or first['cameras'] != second['cameras'] or first['frames'] != second['frames']:
        raise ValueError('Fixed median road or capture differs')
    if (first['target_crossing_x_m'], second['target_crossing_x_m']) != (0, 12):
        raise ValueError('Exact median crossing stations differ')
    return True


def verify_rows(groups):
    if len(groups) != 2 or any(len(group) != 600 for group in groups):
        raise ValueError('Comparison source count differs')
    first, second = groups
    for i, (a, b) in enumerate(zip(first, second)):
        if a.get('video_frame') != i or b.get('video_frame') != i or a.get('time_s') != i/20 or b.get('time_s') != i/20:
            raise ValueError('Fixed source time differs')
        ae, be = a.get('ego', {}), b.get('ego', {})
        if abs(ae.get('speed_mps', -1)-be.get('speed_mps', -2)) > .25:
            raise ValueError('Fixed crossing speed differs')
        av, bv = ae.get('body_xy_m'), be.get('body_xy_m')
        if not isinstance(av, list) or not isinstance(bv, list) or len(av) != 4 or len(bv) != 4:
            raise ValueError('Full-body comparison source missing')
        for ap, bp in zip(av, bv):
            if abs((bp[0]-ap[0])-12) > .25 or abs(bp[1]-ap[1]) > .25:
                raise ValueError('Crossing location not isolated from body path')
    return True


def audit(folders, output):
    if len(folders) != 2:
        raise ValueError('Exact comparison membership differs')
    output = Path(output)
    if output.exists():
        raise ValueError('Retain previous comparison audit')
    verify_requests(requests())
    groups = []
    metrics = []
    for suffix, folder in zip(SUFFIXES, map(Path, folders)):
        result = read(folder/'result.json')
        metric = result.get('measured_values', {})
        if result.get('case_id') != HERE.name+'__'+suffix or result.get('provenance_kind') != 'native' or metric.get('diagnostic_fixture') is not False:
            raise ValueError('Original Native median comparison required')
        if not metric.get('source_review_sha256') or sha(folder/'source-review.json') != metric['source_review_sha256']:
            raise ValueError('Original median source review missing')
        if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Original physical left turn missing')
        groups.append(rows(folder/'native-median.jsonl'))
        metrics.append(metric)
    verify_rows(groups)
    counts = [metric['occupancy_frames'] for metric in metrics]
    if counts[0]['opening'] < 1 or counts[0]['barrier'] != 0 or counts[1]['barrier'] < 1 or counts[1]['opening'] != 0:
        raise ValueError('Original opening/divider contrast absent')
    value = {'format': 'worker-median-comparison-audit', 'passed': True,
        'comparison': GROUP,
        'case_ids': [HERE.name+'__'+suffix for suffix in SUFFIXES],
        'source_result_sha256': [sha(Path(folder)/'result.json') for folder in folders],
        'fixed_conditions': ['same two directional roadways',
            'same median/opening geometry', 'same left-turn controller policy',
            '600-frame timeline', 'four source cameras'],
        'deliberate_differences': ['12 m crossing station translation'],
        'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(value, indent=2)+'\n')
    return value


def selftest(negative):
    verify_requests(requests())
    groups = [rows(HERE/'native/diagnostic'/suffix/'native-median.jsonl')
              for suffix in SUFFIXES]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][300]['ego']['body_xy_m'][0][1] += 3
        verify_rows(groups)
        raise AssertionError('Changed fixed body path accepted')
    verify_rows(groups)
    print(json.dumps({'format': 'worker-median-comparison-selftest',
        'passed': True, 'comparison': GROUP,
        'case_ids': [HERE.name+'__'+suffix for suffix in SUFFIXES],
        'physical_or_legal_acceptance_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=(GROUP,), required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt', action='append')
    parser.add_argument('--output')
    args = parser.parse_args()
    selftest(args.negative) if args.self_test else audit(args.attempt, args.output)
