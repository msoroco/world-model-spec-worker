"""Synthetic comparison-report shape proof; never original accepted evidence."""
from __future__ import annotations

import argparse
import json

from comparison_audit import AID, PAIRS, audit_pair
from zone_motion import CASES


def mock_report(case) -> dict:
    return {
        'format': 'worker-delivery-audit', 'passed': True,
        'protocol_fixture_checked': False, 'case_id': AID + '__' + case.name,
        'frame_count': 900, 'physical_acceptance_claimed': True,
        'comparison_record': {
            'source_kind': 'original_native_capture',
            'fixed_source_sha256': {name: 'synthetic-fixed-hash'
                                    for name in ('map', 'highway', 'zone_boundary', 'vehicle', 'driver')},
            'camera_plan': ['synthetic-four-view'], 'duration_s': 45,
            'route_variant': case.route, 'designation_status': case.designation,
            'designation_source_sha256': 'synthetic-' + case.designation,
            'marking_source_sha256': 'synthetic-marking' if case.designation == 'active' else 'synthetic-unverified',
            'measurement': {
                'frame_count': 900,
                'overlap_frame_count': 20 if case.route != 'beside' else 0,
                'terminal_center_within': case.route == 'within',
                'official_designation_status': case.designation,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    args = parser.parse_args()
    reports = {AID + '__' + case.name: mock_report(case) for case in CASES}
    accepted = audit_pair(args.comparison, reports)
    if not accepted['physical_comparison_passed'] or accepted['legal_verdict_claimed']:
        raise ValueError('mock comparison structure failed')
    right = AID + '__' + PAIRS[args.comparison][1]
    bad = json.loads(json.dumps(reports))
    bad[right]['comparison_record']['fixed_source_sha256']['zone_boundary'] = 'changed-source'
    try:
        audit_pair(args.comparison, bad)
    except ValueError as error:
        if 'changed fixed original condition' not in str(error):
            raise
        print('synthetic positive and changed-source negative pass:', args.comparison)
        return
    raise ValueError('changed original zone source accepted')


if __name__ == '__main__':
    main()
