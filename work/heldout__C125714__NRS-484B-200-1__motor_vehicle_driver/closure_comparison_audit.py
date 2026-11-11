"""Compare original baseline and engineered-closure diagnostic sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from excursion_comparison_audit import _case
from closure_source_audit import audit as audit_closure


def audit(baseline_attempt, closure_attempt):
    baseline_root = Path(baseline_attempt)
    closure_root = Path(closure_attempt)
    baseline = _case(baseline_root, 'baseline_right_east')
    closure = _case(closure_root, 'right_half_closed')
    if baseline['fixed'] != closure['fixed']:
        raise ValueError('Closure comparison fixed construction conditions differ')
    for key in ('frame_count', 'road_id', 'lane_id', 'ego_id'):
        if baseline[key] != closure[key]:
            raise ValueError('Closure comparison route/frame/subject identity differs: ' + key)
    if abs(baseline['minimum_road_width_m'] - closure['minimum_road_width_m']) > .01:
        raise ValueError('Closure comparison roadway width differs')
    if baseline['minimum_body_right_offset_m'] < 0:
        raise ValueError('Closure comparison baseline already crosses left half')
    if closure['first_crossing_frame'] is None:
        raise ValueError('Closure comparison detour does not cross centerline')
    if (baseline_root / 'closure_devices.jsonl').exists():
        raise ValueError('Closure comparison baseline contains closure devices')
    observed = audit_closure(closure_root)
    if observed.get('authority_verified') is not False:
        raise ValueError('Closure comparison authority assertion changed')
    return {
        'format': 'worker-right-half-closure-comparison-audit',
        'case_ids': [baseline['case_id'], closure['case_id']],
        'source_bindings': [baseline, closure],
        'closure_source': observed,
        'fixed_conditions': list(baseline['fixed']),
        'changed_conditions': ['original cone actors', 'requested leftward detour'],
        'scope': 'synthetic source-shaped diagnostic comparison',
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-attempt', required=True)
    parser.add_argument('--closure-attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous closure comparison receipt')
    output.write_text(json.dumps(audit(args.baseline_attempt, args.closure_attempt),
                                 indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
