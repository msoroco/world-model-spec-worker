"""Independent source comparison of yield wait versus premature entry."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUP = 'yield_vs_intrusion'
SUFFIXES = ('priority_yield', 'priority_intrusion')


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
    return [read(HERE / 'native/drafts' / suffix / 'primary/config.json')
            for suffix in SUFFIXES]


def verify_requests(values):
    a, b = values
    changed = {name for name in set(a) | set(b) if a.get(name) != b.get(name)}
    if changed != {'case_id', 'requested_yield_action', 'tracks_sha256'}:
        raise ValueError('Uncontrolled authored priority comparison: ' + str(changed))
    if (a.get('requested_yield_action') is not True or
            b.get('requested_yield_action') is not False or
            a.get('frames') != b.get('frames') or
            a.get('source_map') != b.get('source_map') or
            a.get('cameras') != b.get('cameras')):
        raise ValueError('Fixed road, source capture or yielding contrast differs')


def verify_rows(groups):
    if len(groups) != 2 or any(len(group) != 600 for group in groups):
        raise ValueError('Comparison source count differs')
    first, second = groups
    for i, (a, b) in enumerate(zip(first, second)):
        if a.get('frame') != i or b.get('frame') != i or abs(a['time_s'] - b['time_s']) > 1e-6:
            raise ValueError('Fixed original time differs')
        if a.get('other') != b.get('other'):
            raise ValueError('Priority vehicle path or body changed')
        if (a.get('ego', {}).get('body_xyz_m') is None or
                b.get('ego', {}).get('body_xyz_m') is None):
            raise ValueError('Ego full-body evidence missing')
    return True


def audit(folders, output):
    if len(folders) != 2:
        raise ValueError('Exact comparison membership differs')
    output = Path(output)
    if output.exists():
        raise ValueError('Retain previous comparison audit')
    verify_requests(requests())
    groups, metrics = [], []
    for suffix, folder in zip(SUFFIXES, map(Path, folders)):
        result = read(folder / 'result.json')
        metric = result.get('measured_values', {})
        if (result.get('case_id') != HERE.name + '__' + suffix or
                result.get('provenance_kind') != 'native' or
                result.get('diagnostic_fixture') is True or
                metric.get('priority_entered_first_measured') is not True or
                metric.get('right_of_way_legally_determined') is not False or
                not result.get('maneuver_completed')):
            raise ValueError('Original Native priority comparison required')
        groups.append(read(folder / 'actor-history.json')['rows'])
        metrics.append(metric)
    verify_rows(groups)
    if (metrics[0].get('priority_present_at_ego_entry') is not False or
            metrics[1].get('priority_present_at_ego_entry') is not True or
            metrics[0]['ego_front_entry_s'] <= metrics[1]['ego_front_entry_s']):
        raise ValueError('Measured wait versus intrusion contrast absent')
    value = {'format': 'worker-priority-comparison-audit', 'passed': True,
             'comparison': GROUP,
             'case_ids': [HERE.name + '__' + suffix for suffix in SUFFIXES],
             'source_result_sha256': [sha(Path(folder) / 'result.json') for folder in folders],
             'fixed_conditions': ['same two intersecting highways',
                                  'same priority vehicle trajectory and full body',
                                  '600-frame timeline', 'four source cameras'],
             'deliberate_differences': ['ego yield wait versus entry while priority vehicle remains'],
             'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(negative):
    verify_requests(requests())
    groups = [read(HERE / 'native/selected' / suffix / 'primary/sources/actor-history.json')['rows']
              for suffix in SUFFIXES]
    if negative:
        groups = copy.deepcopy(groups)
        groups[1][300]['other']['body_xyz_m'][0][1] += 3
        verify_rows(groups)
        raise AssertionError('Changed priority vehicle body accepted')
    verify_rows(groups)
    a, b = groups
    if a[300]['ego']['center_xyz_m'] == b[300]['ego']['center_xyz_m']:
        raise ValueError('Authored yield contrast absent')
    print(json.dumps({'format': 'worker-priority-comparison-selftest',
                      'passed': True, 'comparison': GROUP,
                      'case_ids': [HERE.name + '__' + suffix for suffix in SUFFIXES],
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
