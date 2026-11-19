"""Exact C24753 Native runner; the CPU check does not connect to CARLA."""

import argparse
import json
from pathlib import Path

from flashing_yellow_heavy import check_native_config, run_native_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', default='.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    output = Path(args.output_dir)
    config = json.loads((output / 'config.json').read_text())
    if args.check:
        check_native_config(config)
    else:
        run_native_case(output, config, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
