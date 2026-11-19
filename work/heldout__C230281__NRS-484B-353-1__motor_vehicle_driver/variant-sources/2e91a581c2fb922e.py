"""Portable restart-while-red school-bus Native entrypoint; CPU --check never imports CARLA."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from school_bus_native import CASE_ID, check_plan, check_scene, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder/'case-plan.json').read_text())
    config = json.loads((folder/'config.json').read_text())
    check_plan(plan, CASE_ID)
    check_scene(config)
    if config.get('selected_case_id') != CASE_ID or config.get('frames') != 160:
        raise ValueError('Restart school-bus runner config identity/duration differs')
    if not args.check:
        if not args.output_dir:
            parser.error('--output-dir required for Native acquisition')
        run(plan, config, args.output_dir, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
