"""Diagnostic physical completion classes for exact roadway-return cases."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_entry_return import measure_core_join
from prove_physical import lifecycle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def result(attempt, case, kind):
    attempt = Path(attempt)
    if kind == 'complete_motion':
        observed = measure_core_join(attempt, case)
        if not observed['first_entry_road_frame'] or observed['frame_count'] != 1200:
            raise ValueError('Diagnostic roadway-return motion incomplete')
        status = 'met'
        sources = {'native-rows.jsonl': sha(attempt / 'native-rows.jsonl'),
                   'captured-source-hashes.json':
                       sha(attempt / 'captured-source-hashes.json')}
        method = '1200 sealed Native/Core frames with roadway return crossing'
    elif kind == 'incomplete_motion':
        rows = [json.loads(line) for line in
                (attempt / 'native-rows.jsonl').read_text().splitlines()]
        first = rows[400]['vehicle_world_xy_m']
        counterfactual = [{**row, 'vehicle_world_xy_m': first,
                           'vehicle_speed_mps': 0.0} for row in rows]
        if (len(counterfactual) != 1200 or
                any(row['vehicle_world_xy_m'][1] >= -3.5
                    for row in counterfactual)):
            raise ValueError('Stationary counterfactual reached roadway')
        observed = {}
        status = 'not_met'
        sources = {'diagnostic_counterfactual_sha256':
                   hashlib.sha256(json.dumps(counterfactual,
                                             separators=(',', ':')).encode()).hexdigest()}
        method = 'Counterfactual stationary ego against fixed roadway entry'
    else:
        observed = {}
        status = 'unverified'
        sources = {'native-rows.jsonl': None}
        method = 'Missing original Native history prevents completion assessment'
    return {'case_id': case, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                                             'method': method,
                                             'sources': sources}},
            'realized_observables': observed,
            'original_native_observed': False,
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--kind', required=True,
                   choices=('complete_motion', 'incomplete_motion',
                            'missing_evidence', 'lifecycle'))
    args = p.parse_args()
    out = lifecycle() if args.kind == 'lifecycle' else result(
        args.attempt, args.case, args.kind)
    print(json.dumps(out, indent=2))
