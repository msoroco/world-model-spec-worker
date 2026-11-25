"""Synthetic physical outcome probes; no original-site acceptance claim."""
import argparse
import json
from pathlib import Path
from saved_measurement import measure


def prove(case_id, fixture):
    plan = {'intersection_polygon': [[0, 0], [10, 0], [10, 10], [0, 10]],
            'start': [-1, -1], 'end': [11, 11], 'route_kind': 'diagonal'}
    points = [[-1, -1], [5, 5], [11, 11]]
    if fixture == 'incomplete_motion':
        points[-1] = [5, 5]
    walkers = [{'original_frame': i, 'walker_id': 'synthetic-walker', 'walker_center_xy': xy}
               for i, xy in enumerate(points)]
    devices = [{'original_frame': i, 'source_sha256': 'a' * 64,
                'official_source': 'synthetic-test-double', 'pedestrian_governance': 'diagonal',
                'state': 'permissive'} for i in range(3)]
    if fixture == 'missing_evidence':
        devices.pop()
    observed = {}
    try:
        observed = measure(plan, walkers, devices)
        status = 'met'
    except ValueError as exc:
        status = 'unverified' if fixture == 'missing_evidence' else 'not_met'
        observed = {'diagnostic_error': str(exc)}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[fixture]
    assert status == expected, (fixture, status, observed)
    return {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                'method': 'saved_measurement.measure on synchronized synthetic walker and device frames',
                'sources': ['synthetic walker history', 'synthetic device history']}},
            'realized_observables': observed if status == 'met' else {},
            'physical_acceptance_claimed': False, 'legal_conclusion': 'not_assessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', required=True,
                        choices=['complete_motion', 'incomplete_motion', 'missing_evidence'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prove(args.case, args.fixture)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print('synthetic fixture', args.fixture, 'status', result['physical_checks']['maneuver']['status'])
