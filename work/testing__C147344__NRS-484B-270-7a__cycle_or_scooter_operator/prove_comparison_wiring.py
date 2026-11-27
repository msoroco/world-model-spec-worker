"""CPU-only source-shaped comparison wiring; original source review remains local."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from test_comparison_audit import report
from comparison_audit import PAIRS, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    left, right = (report(slug) for slug in PAIRS[args.comparison])
    if args.negative:
        right = copy.deepcopy(right)
        right['observation']['reviewed_road_source_sha256'] = 'd' * 64
        try:
            audit(args.comparison, left, right)
        except ValueError as error:
            if 'fixed original source differs' in str(error):
                print('fixed original source differs: rejected changed road source')
                raise SystemExit(2)
            raise
        raise AssertionError('changed fixed road source accepted')
    result = audit(args.comparison, left, right)
    result['diagnostic_fixture'] = True
    result['scope'] = 'source-shaped CPU comparison wiring only; original source audit remains local'
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
