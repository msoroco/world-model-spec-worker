"""Exercise each exact comparison with saved diagnostic analyses."""

import argparse
import json
from pathlib import Path

from comparison_audit import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c229023-7771-owner-nov26'


def main(comparison_id, negative):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    matches = [item for item in plan['comparisons']
               if item['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('unknown exact comparison')
    rows = []
    for case_id in matches[0]['case_ids']:
        name = case_id.removeprefix(HERE.name + '__')
        source = SCRATCH / ('compat-v5-' + name) / 'analysis-report.json'
        rows.append(json.loads(source.read_text()))
    if negative:
        item = next(iter(rows[1]['measurements'].values()))
        item['value']['road_geometry_source_sha256'] = '0' * 64
        for measurement in rows[1]['measurements'].values():
            measurement['value']['road_geometry_source_sha256'] = '0' * 64
    result = audit(plan, comparison_id, *rows)
    if negative:
        raise ValueError('mismatched source basis was accepted')
    print(json.dumps({'comparison_id': comparison_id,
                      'case_ids': result['case_ids'],
                      'deliberate_differences': result['deliberate_differences'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--negative-source-mismatch', action='store_true')
    args = parser.parse_args()
    try:
        main(args.comparison, args.negative_source_mismatch)
    except (ValueError, FileNotFoundError) as error:
        print(str(error))
        raise SystemExit(2)
