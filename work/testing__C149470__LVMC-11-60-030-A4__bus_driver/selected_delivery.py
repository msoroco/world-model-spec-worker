"""Independent original-only delivery audit for one exact bus loading attempt."""
import argparse
import json
from pathlib import Path

from delivery_audit import ASSIGNMENT, audit_attempt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    if not args.case.startswith(ASSIGNMENT + '__'):
        raise ValueError('exact C149470 case required')
    name = args.case.removeprefix(ASSIGNMENT + '__')
    result = audit_attempt(args.attempt / 'reviewed-site.json', args.attempt, name)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
