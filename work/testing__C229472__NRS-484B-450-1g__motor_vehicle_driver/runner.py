"""Exact C229472 roadside-signal Native attempt entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from signal_approach import ASSIGNMENT, CASE_BY_ID, reviewed_packet

ROOT = Path(__file__).resolve().parent


def read_config():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    if (config.get('assignment_id') != ASSIGNMENT or
            config.get('law_id') != 'NRS-484B-450-1g' or
            config.get('cell_id') != 'C229472' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('selected_case_id') not in CASE_BY_ID or
            set(config.get('supported_case_ids', [])) != set(CASE_BY_ID) or
            config.get('rate_hz') != 20 or config.get('duration_s') != 45):
        raise ValueError('exact roadside signal case/capture contract differs')
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args(argv)
    config = read_config()
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'],
                          'capture_contract_checked': True,
                          'original_signal_review_required': True}))
        return 0
    if not args.output_dir:
        parser.error('--output-dir required')
    packet_name = os.environ.get('C229472_REVIEWED_SIGNAL_PACKET')
    if not packet_name:
        raise ValueError('C229472_REVIEWED_SIGNAL_PACKET original reviewed packet required')
    packet_path = Path(packet_name).resolve()
    packet, case, geometry = reviewed_packet(packet_path, config['selected_case_id'])
    from native_signal import run_native
    run_native(config, packet, case, geometry, packet_path,
               Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
