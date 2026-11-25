"""CPU diagnostic outcome fixtures; never an original-site acceptance claim."""
import argparse
import json
from pathlib import Path

from crossing_audit import audit_history


def prove(case_id, kind):
    plan = {'start_xy': [0, 0], 'destination_xy': [10, 10],
            'device_id': 'synthetic-diagonal-device',
            'source_sha256': 'synthetic-fixture-only',
            'exception_484b_290_review': 'unresolved'}
    positions = [[0, 0], [3, 3], [7, 7], [10, 10]]
    if kind == 'incomplete_motion':
        positions[-1] = [7, 7]
    walkers = [{'original_frame': i, 'walker_id': 'synthetic-walker',
                'center_xy': xy} for i, xy in enumerate(positions)]
    devices = [{'original_frame': i, 'device_id': plan['device_id'],
                'source_sha256': plan['source_sha256'],
                'pedestrian_governance': 'diagonal',
                'instruction': 'diagonal_walk'} for i in range(4)]
    if kind == 'missing_evidence':
        devices.pop()
    status = 'unverified'
    observed = {}
    try:
        observed = audit_history(plan, [[2, 2], [8, 2], [8, 8], [2, 8]], walkers, devices)
        if kind == 'complete_motion':
            status = 'met'
    except ValueError as exc:
        observed = {'diagnostic_error': str(exc)}
    if kind == 'incomplete_motion':
        status = 'not_met'
        observed = {'sampled_endpoint_xy': positions[-1], 'destination_xy': plan['destination_xy']}
    return {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                'method': 'synthetic synchronized walker/device frame audit',
                'sources': ['synthetic walker frames', 'synthetic device frames']}},
            'realized_observables': observed if status == 'met' else {},
            'physical_acceptance_claimed': False,
            'legal_conclusion': 'not_assessed'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--fixture', required=True,
                   choices=['complete_motion', 'incomplete_motion', 'missing_evidence'])
    p.add_argument('--output', required=True)
    a = p.parse_args()
    Path(a.output).write_text(json.dumps(prove(a.case, a.fixture), indent=2) + '\n')
    print('synthetic fixture:', a.fixture, 'status:', prove(a.case, a.fixture)['physical_checks']['maneuver']['status'])
