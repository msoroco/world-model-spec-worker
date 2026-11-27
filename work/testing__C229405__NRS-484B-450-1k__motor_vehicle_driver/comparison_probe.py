"""Synthetic report-shape proof; never an accepted original comparison."""
from __future__ import annotations

import argparse
import json

from comparison_audit import AID, PAIRS, audit_pair
from excavation_park import CASES


def mock_report(case):
    width = 5.0 if case.passage == 'open' else 2.0
    return {'format': 'worker-delivery-audit', 'passed': True,
            'protocol_fixture_checked': False, 'case_id': AID + '__' + case.case_id,
            'frame_count': 900, 'physical_acceptance_claimed': True,
            'comparison_record': {
                'source_kind': 'original_native_capture',
                'fixed_source_sha256': {'map': 'synthetic-hash', 'highway': 'synthetic-hash',
                                        'excavation': 'synthetic-hash', 'traffic': 'synthetic-hash'},
                'camera_plan': ['synthetic-four-view'], 'duration_s': 45,
                'requested_relation': case.relation, 'activity': case.activity,
                'passage_probe': case.passage, 'exception': case.exception,
                'measurement': {'frame_count': 900,
                                'minimum_available_passage_width_m': width,
                                'minimum_body_excavation_gap_m': 1.0}}}


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
    bad[right]['comparison_record']['fixed_source_sha256']['excavation'] = 'changed-source'
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
