"""Synthetic report-shape proof; never an accepted original comparison."""
from __future__ import annotations

import argparse
import json

from comparison_audit import PAIRS, audit_pair
from fire_station_scene import CASES


def mock_report(case):
    sources = {name: 'unit-fixed-' + name for name in
               ('map', 'station', 'entrance', 'highway', 'person', 'authority')}
    if case.circumstance == 'non_fire_station':
        sources['station'] = 'unit-non-fire'
    if case.circumstance == 'private_road':
        sources['highway'] = 'unit-private'
    if case.circumstance in ('traffic_conflict', 'law_compliance',
                             'police_direction', 'official_device_direction'):
        sources['authority'] = 'unit-' + case.circumstance
    sign = -1 if case.side == 'opposite' else 1
    observation = {'vehicle_lateral_min_m': sign*2,
                   'vehicle_lateral_max_m': sign*3}
    return {'format': 'worker-delivery-audit', 'passed': True,
            'protocol_fixture_checked': False,
            'case_id': case.case_id, 'frame_count': 900,
            'physical_acceptance_claimed': True,
            'comparison_record': {
                'source_kind': 'original_native_capture',
                'source_sha256': sources,
                'camera_plan': ['unit-four-view'], 'duration_s': 45,
                'side_request': case.side,
                'activity_request': case.activity,
                'distance_request_ft': case.distance_ft,
                'circumstance_request': case.circumstance,
                'station_is_fire': case.circumstance != 'non_fire_station',
                'highway_public_use': case.circumstance != 'private_road',
                'measurement': {
                    'case_id': case.case_id,
                    'entrance_lateral_m': 4.0,
                    'observations': [observation]*900,
                    'minimum_observed_vertex_to_entrance_m':
                    case.distance_ft*.3048}}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    args = parser.parse_args()
    reports = {case.case_id: mock_report(case) for case in CASES}
    accepted = audit_pair(args.comparison, reports)
    if not accepted['physical_comparison_passed'] or accepted['legal_verdict_claimed']:
        raise ValueError('mock comparison structure failed')
    right = PAIRS[args.comparison][1]
    bad = json.loads(json.dumps(reports))
    bad[right]['comparison_record']['source_sha256']['map'] = 'changed-map'
    try:
        audit_pair(args.comparison, bad)
    except ValueError as error:
        if 'changed fixed original condition' not in str(error):
            raise
        print('synthetic report-shape positive and fixed-source negative pass:',
              args.comparison)
        return
    raise ValueError('changed map accepted')


if __name__ == '__main__':
    main()
