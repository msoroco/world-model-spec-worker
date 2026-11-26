"""Derive exact school-zone measurements from sealed saved sources only.

This CPU path never imports CARLA and does not declare physical or legal acceptance.
The output must be separate from the original source directory.
"""
import argparse
import json
from pathlib import Path

from measure_school_zone import CASE, measure


def process(attempt, output, case=CASE):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output == attempt or attempt in output.parents:
        raise ValueError('Derived output must be outside the original source directory')
    if output.exists():
        raise ValueError('Derived output already exists')
    observed = measure(attempt, expected_case=case)
    if observed['physical_acceptance_claimed'] or observed['legal_verdict_claimed']:
        raise ValueError('Saved measurement cannot claim acceptance or legal verdict')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(observed, sort_keys=True, allow_nan=False)+'\n')
    return observed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', default=CASE)
    args = parser.parse_args()
    print(json.dumps(process(args.attempt, args.output, args.case), sort_keys=True, allow_nan=False))
