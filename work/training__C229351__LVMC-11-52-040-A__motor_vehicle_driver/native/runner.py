"""Exact six-case road-edge delivery runner."""
import argparse
import json
from pathlib import Path

from capture import capture
from roadside_scene import check as check_scene


def check(config):
    return check_scene(config, Path('road-edge-road.xodr').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error('Original capture needs --output-dir, --host and --port')
        print(json.dumps(capture(config, args.output_dir, args.host, args.port), sort_keys=True))
