"""Independent original-only audit of one exact bus loading comparison."""
import argparse
import json
from pathlib import Path

from delivery_audit import HERE, audit_attempt, audit_comparisons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((HERE / 'case-plan.json').read_text())
    pair = [item for item in plan['comparisons']
            if item['comparison_id'] == args.comparison]
    if len(pair) != 1:
        raise ValueError('unknown exact comparison')
    reports = {}
    for cid, attempt in zip(pair[0]['case_ids'], (args.left, args.right)):
        name = cid.removeprefix(HERE.name + '__')
        reports[cid] = audit_attempt(attempt / 'reviewed-site.json', attempt, name)
    result = audit_comparisons(reports, args.comparison)
    if len(result) != 1:
        raise ValueError('exact comparison audit missing')
    print(json.dumps(result[0], sort_keys=True))


if __name__ == '__main__':
    main()
