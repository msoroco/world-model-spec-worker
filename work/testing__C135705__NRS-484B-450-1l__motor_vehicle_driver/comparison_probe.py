"""Synthetic report-shape test; it is not an original accepted comparison."""
from __future__ import annotations

import argparse
import json

from comparison_audit import AID, PAIRS, audit_pair
from parking import CASES


def mock_report(case):
    lateral = .0 if case.endpoint == 'behind_edge_vehicle' else 2.3
    along = 10.0 if case.endpoint == 'behind_edge_vehicle' else 0.0
    return {'format': 'worker-delivery-audit', 'passed': True,
            'protocol_fixture_checked': False, 'case_id': AID + '__' + case.case_id,
            'frame_count': 900, 'physical_acceptance_claimed': True,
            'comparison_record': {
                'source_kind': 'original_native_capture',
                'fixed_source_sha256': {name: 'synthetic-hash' for name in
                                        ('map', 'highway', 'edge', 'route',
                                         'ego_blueprint', 'edge_blueprint')},
                'camera_plan': ['synthetic-four-view'], 'duration_s': 45,
                'requested_endpoint': case.endpoint, 'activity': case.activity,
                'edge_vehicle_status': 'parked',
                'exception': case.exception_probe,
                'measurement': {
                    'frame_count': 900,
                    'terminal_roadward_lateral_difference_m': lateral,
                    'terminal_along_edge_difference_m': along,
                    'edge_stationary_observed': True, 'ego_halt_observed': True,
                    'exception_source_sha256': ['synthetic-authority']
                        if case.exception_probe else []}}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    args = parser.parse_args()
    reports = {AID + '__' + case.case_id: mock_report(case) for case in CASES}
    accepted = audit_pair(args.comparison, reports)
    if not accepted['physical_comparison_passed'] or accepted['legal_verdict_claimed']:
        raise ValueError('mock comparison structure failed')
    right = AID + '__' + PAIRS[args.comparison][1]
    bad = json.loads(json.dumps(reports))
    bad[right]['comparison_record']['fixed_source_sha256']['edge'] = 'changed-source'
    try:
        audit_pair(args.comparison, bad)
    except ValueError as error:
        if 'changed fixed original condition' not in str(error):
            raise
        print('synthetic report-shape positive and changed-source negative pass:',
              args.comparison)
        return
    raise ValueError('changed source accepted')


if __name__ == '__main__':
    main()
