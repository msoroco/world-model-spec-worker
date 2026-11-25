"""Selected original yield comparison audit with explicit diagnostic separation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import audit as audit_original

ROOT = Path(__file__).resolve().parent
DIFFERENCES = {
    'occupied_vs_approaching': {'through_phase', 'requested_other_station_m'},
    'approach_station_sweep': {'requested_other_station_m'},
    'response_vs_uninterrupted': {'approach_policy'},
}


def audit(comparison_id, left, right, allow_diagnostic):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    pair = next((row for row in plan['comparisons']
                 if row['comparison_id'] == comparison_id), None)
    if pair is None or comparison_id not in DIFFERENCES:
        raise ValueError('undefined exact yield comparison')
    paths = [Path(left).resolve(), Path(right).resolve()]
    variables = [json.loads((path / 'config.json').read_text())['case']['draft_variables']
                 for path in paths]
    changed = {name for name in variables[0]
               if variables[0][name] != variables[1][name]}
    if changed != DIFFERENCES[comparison_id]:
        raise ValueError('comparison requested variables differ beyond declared axes')
    proof = audit_original(paths[0], paths[1], comparison_id, *pair['case_ids'])
    if proof['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('synthetic source cannot establish original comparison')
    return {'format': 'worker-selected-yield-comparison-audit',
            **proof, 'declared_differences': sorted(changed),
            'realized_difference_claimed': False,
            'comparison_limit': pair.get('interpretation_limit',
                                         'No legal judgment from requested variables')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right, args.allow_diagnostic),
                     sort_keys=True))
