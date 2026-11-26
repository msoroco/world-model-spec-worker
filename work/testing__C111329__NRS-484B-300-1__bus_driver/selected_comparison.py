"""Independent original-only two-attempt bus/device comparison audit CLI."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit_attempt, audit_comparisons
from package_spec import HERE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    args = parser.parse_args()
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison = next((row for row in plan['comparisons']
                       if row['comparison_id'] == args.comparison), None)
    if comparison is None:
        raise ValueError('unknown exact comparison')
    reports = {}
    for cid, path in zip(comparison['case_ids'], (args.left, args.right)):
        attempt = Path(path).resolve()
        name = cid.removeprefix(HERE.name + '__')
        reports[cid] = audit_attempt(attempt / 'reviewed-site.json', attempt, name)
    print(json.dumps(audit_comparisons(reports, args.comparison)[0], sort_keys=True))


if __name__ == '__main__':
    main()
