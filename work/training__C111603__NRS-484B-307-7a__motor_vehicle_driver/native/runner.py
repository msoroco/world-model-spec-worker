"""CPU check of exact request; original four-camera Native capture remains open."""
import argparse
import json
from request import CASES, check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    if not args.check:
        parser.error('Original Native acquisition has not been implemented in this partial package')
    try:
        config = json.load(open('config.json'))
    except FileNotFoundError:
        config = {}
    print(json.dumps(check(args.case or config.get('case_suffix')), sort_keys=True))


if __name__ == '__main__':
    main()
