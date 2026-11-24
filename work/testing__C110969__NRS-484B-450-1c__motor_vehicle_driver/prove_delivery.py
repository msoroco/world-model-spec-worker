"""Run source-sealed four-view audit on a named diagnostic attempt."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    result = audit(Path(args.attempt), args.case, allow_diagnostic=not args.negative)
    if args.negative:
        raise ValueError('diagnostic fixture was incorrectly accepted')
    if (not result['diagnostic_fixture'] or result['physical_completion'] != 'unverified'
            or result['canonical_delivery_acceptance'] != 'unverified'):
        raise ValueError('diagnostic audit claimed delivery acceptance')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
