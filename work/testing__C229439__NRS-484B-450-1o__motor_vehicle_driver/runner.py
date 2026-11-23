"""Portable exact-case entrypoint for NRS 484B.450(1)(o).

The operator must supply source-sealed site, device and vehicle records before
Native execution. This CPU entrypoint checks identity and case configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parking import validate_sources

ROOT = Path(__file__).resolve().parent


def load_config():
    config = json.loads((ROOT / 'config.json').read_text())
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'NRS-484B-450-1o', 'C229439', 'motor_vehicle_driver'):
        raise ValueError('wrong frozen assignment identity')
    case = config['case']
    if not case['case_id'].startswith('testing__C229439__NRS-484B-450-1o__motor_vehicle_driver__'):
        raise ValueError('wrong exact case identity')
    if case['halt_action'] not in {'park', 'stop', 'stand'} or case['exception'] not in {
            'none', 'traffic_conflict', 'law', 'police_direction', 'device_direction'}:
        raise ValueError('invalid case action or exception')
    if config['rate_hz'] != 20 or config['duration_s'] != 45 or set(config['cameras']) != {'front', 'rear', 'left', 'right'}:
        raise ValueError('capture profile changed')
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site-ref')
    parser.add_argument('--device-ref')
    parser.add_argument('--vehicle-ref')
    args = parser.parse_args()
    config = load_config()
    if args.check:
        print(json.dumps({'case_id': config['case']['case_id'], 'identity_checked': True,
                          'capture_profile_checked': True, 'simulation_started': False}))
        return
    if not all((args.site_ref, args.device_ref, args.vehicle_ref)):
        raise ValueError('Native execution requires source-sealed site, device and vehicle refs')
    refs = [json.loads(Path(path).read_text()) for path in (args.site_ref, args.device_ref, args.vehicle_ref)]
    validate_sources(*refs, config['case'])
    raise ValueError('Concrete CARLA adapter and recording handoff are not yet implemented')


if __name__ == '__main__':
    main()
