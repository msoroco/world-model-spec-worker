"""Independent source and requested-variable audit for exact red-left pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_source

ROOT = Path(__file__).resolve().parent
DIFFERENCE = {
    'stop_before_turn': 'stop_request',
    'extreme_left_position': 'approach_position',
    'receiving_direction': 'receiving_direction',
    'pedestrian_yield': 'conflict_response_request',
    'traffic_yield': 'conflict_response_request',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id: str, left: Path, right: Path, allow_diagnostic: bool) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    pair = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison_id), None)
    if pair is None:
        raise ValueError('undefined exact comparison')
    cases = pair['case_ids']
    attempts = (left.resolve(), right.resolve())
    records = [audit_source(path, case) for path, case in zip(attempts, cases)]
    if any(row['diagnostic_fixture'] for row in records) and not allow_diagnostic:
        raise ValueError('synthetic source cannot establish original comparison')
    inventories = [json.loads((path / 'original-attempt/inventory.json').read_text())
                   for path in attempts]
    variables = [json.loads((path / 'config.json').read_text())['case']['draft_variables']
                 for path in attempts]
    changed = {key for key in variables[0] if variables[0][key] != variables[1][key]}
    if changed != {DIFFERENCE[comparison_id]}:
        raise ValueError('comparison requested variables differ beyond declared axis')
    for name in ('opendrive', 'official_signal', 'stop_reference'):
        left_file = attempts[0] / 'original-attempt/source-review' / (name + '.txt')
        right_file = attempts[1] / 'original-attempt/source-review' / (name + '.txt')
        if sha(left_file) != sha(right_file):
            raise ValueError('comparison fixed source changed: ' + name)
    if comparison_id != 'receiving_direction' and inventories[0]['site_sha256'] != inventories[1]['site_sha256']:
        raise ValueError('comparison fixed site changed')
    if comparison_id == 'receiving_direction' and inventories[0]['site_sha256'] == inventories[1]['site_sha256']:
        raise ValueError('receiving-direction source was relabelled')
    if inventories[0]['history_sha256'] == inventories[1]['history_sha256']:
        raise ValueError('comparison reuses original history')
    return {'format': 'worker-selected-red-left-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': cases,
            'source_custody': records, 'fixed_source_sha256': {
                name: sha(attempts[0] / 'original-attempt/source-review' / (name + '.txt'))
                for name in ('opendrive', 'official_signal', 'stop_reference')},
            'requested_difference': DIFFERENCE[comparison_id],
            'diagnostic_fixture': any(row['diagnostic_fixture'] for row in records),
            'realized_difference_claimed': False, 'legal_judgment': 'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right, args.allow_diagnostic),
                     sort_keys=True))
