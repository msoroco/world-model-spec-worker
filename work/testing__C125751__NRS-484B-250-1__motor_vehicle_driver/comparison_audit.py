"""Independent saved-only comparison isolation for median-opening packets."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def audit_pair(left: dict, right: dict, *, variable: str):
    if variable not in {'entry_order', 'signal_state'}:
        raise ValueError('undeclared comparison variable')
    required = ('map_sha256', 'review_sha256', 'crossing_id', 'ego_route_sha256',
                'other_route_sha256', 'camera_plan_sha256', 'duration_frames',
                'ego_blueprint', 'other_blueprint')
    for key in required:
        if not left.get(key) or left.get(key) != right.get(key):
            raise ValueError(f'fixed condition differs or absent: {key}')
    if left.get('case_id') == right.get('case_id'):
        raise ValueError('comparison repeats one case')
    for report in (left, right):
        if report.get('physical_review_pending') is not True:
            raise ValueError('report lacks physical-review boundary')
        for key in ('ego_entry_frame', 'other_entry_frame', 'signal_states_observed'):
            if key not in report:
                raise ValueError(f'measurement absent: {key}')
    if variable == 'entry_order':
        a = left['other_entry_frame'] < left['ego_entry_frame']
        b = right['other_entry_frame'] < right['ego_entry_frame']
        if a == b:
            raise ValueError('declared entry order did not vary')
    else:
        if set(left['signal_states_observed']) == set(right['signal_states_observed']):
            raise ValueError('declared signal state did not vary')
        if ((left['other_entry_frame'] < left['ego_entry_frame']) !=
                (right['other_entry_frame'] < right['ego_entry_frame'])):
            raise ValueError('entry order changed in signal comparison')
    return {'comparison_variable': variable, 'case_ids': [left['case_id'], right['case_id']],
            'fixed_conditions_checked': list(required), 'physical_review_pending': True,
            'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser(description='Audit sealed crossing comparison reports')
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--variable', choices=('entry_order', 'signal_state'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit_pair(json.loads(args.left.read_text()), json.loads(args.right.read_text()),
                        variable=args.variable)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
