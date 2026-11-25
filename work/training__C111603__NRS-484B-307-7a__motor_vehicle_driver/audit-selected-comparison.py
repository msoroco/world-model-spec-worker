"""Audit all three selected request pairs with a fixed-source negative."""
import argparse
import hashlib
import json
from pathlib import Path

from native.branch_comparison_audit import audit_pair

ROOT = Path(__file__).resolve().parent
PAIRS = {
    'other_traffic_yield': ('controlled_1', 'controlled_2'),
    'pedestrian_yield': ('pedestrian_clearance', 'pedestrian_overlap'),
    'concurrent_indication': ('concurrent_absent', 'concurrent_present'),
}


def rows(short):
    return [json.loads(line) for line in
            (ROOT / f'selected-source-{short}/turn-history.jsonl').read_text().splitlines()]


def check_controlled(first, second):
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Selected controlled source inventory differs')
    for frame, (a, b) in enumerate(zip(first, second)):
        if (a['frame'] != frame or b['frame'] != frame
                or abs(a['time_s'] - frame / 20) > 1e-6
                or abs(b['time_s'] - frame / 20) > 1e-6):
            raise ValueError('Selected controlled frame/time differs')
        for key in ('requested_other_xy_m', 'requested_other_inside_intersection',
                    'requested_arrow', 'other_traffic_lawful_status',
                    'pedestrian_presence_status'):
            if a[key] != b[key]:
                raise ValueError('Fixed comparison source differs: ' + key)
        if a['original_native_observed'] or b['original_native_observed']:
            raise ValueError('Synthetic comparison claimed original Native observation')
    if first[0]['requested_release_frame'] != 320 or second[0]['requested_release_frame'] != 200:
        raise ValueError('Controlled intervention differs')
    return {'branch': 'other_traffic_yield', 'frames': 600,
            'intervention': 'requested_release_frame',
            'first': 320, 'second': 200, 'legal_verdict_claimed': False}


def audit(reject_fixed_drift=False):
    out = []
    for branch, (left, right) in PAIRS.items():
        first, second = rows(left), rows(right)
        if reject_fixed_drift and branch == 'other_traffic_yield':
            second[220] = dict(second[220], requested_other_xy_m=[0.0, 0.0])
        result = (check_controlled(first, second) if branch == 'other_traffic_yield'
                  else audit_pair(first, second, branch))
        result['case_ids'] = [ROOT.name + '__' + left, ROOT.name + '__' + right]
        result['source_sha256'] = {
            name: hashlib.sha256((ROOT / f'selected-source-{name}/turn-history.jsonl').read_bytes()).hexdigest()
            for name in (left, right)}
        out.append(result)
    return {'format': 'worker-selected-comparison-audit', 'passed': True,
            'comparisons': out, 'original_native_observed': False,
            'candidate_review_method': 'primary and fallback1 preserve each pair intervention; source request changes are audited separately',
            'unreviewed_candidates': []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reject-fixed-drift', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.reject_fixed_drift), indent=2))


if __name__ == '__main__':
    main()
