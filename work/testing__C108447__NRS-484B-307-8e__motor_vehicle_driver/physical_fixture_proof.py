"""Synthetic CPU outcome test for the saved property-route completion gate.

The test exercises three evidence outcomes. It makes no Native or legal claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(root, case, kind):
    root = Path(root)
    source = root / 'trace.json'
    config = root / 'config.json'
    sources = {'config.json': sha(config)} if config.is_file() else {}
    if source.is_file():
        sources['trace.json'] = sha(source)
    if kind == 'missing_evidence':
        status, observed = 'unverified', {}
    else:
        trace = json.loads(source.read_text())
        if trace['case_id'] != case:
            raise ValueError('Synthetic fixture case differs')
        rows = trace['ego']
        entry = next((row for row in rows if row['frame'] == trace['destination_entry_frame']), None)
        if entry is None or len(rows) < 3:
            raise ValueError('Synthetic destination entry evidence missing')
        start = (rows[0]['x'], rows[0]['y'])
        destination = (entry['x'], entry['y'])
        observed = {'start_xy_m': list(start), 'destination_entry_xy_m': list(destination),
                    'destination_entry_frame': entry['frame'],
                    'source_trace_sha256': sources['trace.json']}
        status = 'met' if destination != start else 'not_met'
    if kind == 'complete_motion' and status != 'met':
        raise ValueError('Synthetic complete motion fixture lacks displacement')
    if kind == 'incomplete_motion' and status != 'not_met':
        raise ValueError('Synthetic incomplete motion fixture was accepted')
    check = {'status': status, 'method': 'synthetic sampled center displacement to destination entry',
             'sources': sources, 'observed': observed,
             'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    return {'format': 'property-physical-cpu-fixture', 'case_id': case,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'fixture_kind': kind, 'physical_checks': {'maneuver': check},
            'maneuver_completed': status == 'met',
            'realized_observables': observed if status == 'met' else {},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    args.result.write_text(json.dumps(evaluate(args.fixture, args.case, args.kind), indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'fixture_kind': args.kind,
                      'status': json.loads(args.result.read_text())['physical_checks']['maneuver']['status']}))


if __name__ == '__main__':
    main()
