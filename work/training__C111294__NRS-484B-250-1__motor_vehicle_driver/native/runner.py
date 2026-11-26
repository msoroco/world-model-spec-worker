"""Exact C111294 two-highway original capture entrypoint.

The CPU check only verifies the authored request. Native execution requires an
externally owned CARLA endpoint and writes observations into its materialized
case directory. It does not assign a legal outcome.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C111294__NRS-484B-250-1__motor_vehicle_driver'
NATIVE = ROOT / 'work' / ASSIGNMENT / 'native'
if not NATIVE.is_dir():
    NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))

from capture import capture  # noqa: E402
from check import check  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(ROOT)))
        return
    if args.output_dir is None:
        parser.error('Materialized exact-case output directory required')
    capture(ROOT, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
