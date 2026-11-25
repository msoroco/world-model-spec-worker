"""Selected exact pair audit with requested versus measured axis separation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import DELIBERATE, audit as audit_original

ROOT = Path(__file__).resolve().parent


def audit(comparison_id, left, right, allow_diagnostic=False):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    pair = next((row for row in plan['comparisons']
                 if row['comparison_id'] == comparison_id), None)
    if pair is None or comparison_id not in DELIBERATE:
        raise ValueError('undefined exact speed comparison')
    paths = [Path(left).resolve(), Path(right).resolve()]
    variables = [json.loads((path / 'config.json').read_text())['case']['draft_variables']
                 for path in paths]
    changed = {name for name in variables[0]
               if variables[0][name] != variables[1][name]}
    if changed != DELIBERATE[comparison_id]:
        raise ValueError('comparison requested variables differ beyond declared axes')
    proof = audit_original(comparison_id, paths[0], pair['case_ids'][0],
                           paths[1], pair['case_ids'][1], allow_diagnostic)
    return {'format': 'worker-selected-speed-comparison-audit', **proof,
            'declared_differences': sorted(changed),
            'realized_difference_claimed': False,
            'comparison_limit': 'Original site and sign appropriateness require review'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right,
                           args.allow_diagnostic), sort_keys=True))
