"""Independent original-only selected bus/device attempt audit CLI."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit_attempt
from package_spec import CASES, HERE, case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    if args.case not in {case_id(row[0]) for row in CASES}:
        raise ValueError('unknown exact case')
    attempt = Path(args.attempt).resolve()
    name = args.case.removeprefix(HERE.name + '__')
    print(json.dumps(audit_attempt(attempt / 'reviewed-site.json', attempt, name),
                     sort_keys=True))


if __name__ == '__main__':
    main()
