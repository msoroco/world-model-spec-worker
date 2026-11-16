"""Exact indicated-course entrypoint; site source is an explicit Native input."""
import argparse
import json
import os
from pathlib import Path
from native_runner import prepare, run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    if config['selected_case_id'] != 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver__button_indicated_course' or config['rate_hz'] != 20 or config['frames'] != 160:
        raise ValueError('Exact marked-turn construction identity or duration changed')
    if args.check:
        if args.output_dir:
            raise ValueError('Offline check does not create Native output')
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    source = os.environ.get('MARKED_TURN_SITE_SOURCE')
    digest = os.environ.get('MARKED_TURN_SITE_SHA256')
    if not source or not digest:
        raise ValueError('Native capture requires explicit site source and SHA-256')
    plan = prepare(config['selected_case_id'], source, digest)
    run(plan, args.output_dir, args.host, args.port)

if __name__ == '__main__':
    main()
