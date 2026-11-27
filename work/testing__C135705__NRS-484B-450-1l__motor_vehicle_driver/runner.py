"""Source-gated original C135705 parking capture entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from parking import CASES
from site_review import reviewed_site

ROOT = Path(__file__).resolve().parent
AID = 'testing__C135705__NRS-484B-450-1l__motor_vehicle_driver'


def read_config():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    expected = {AID + '__' + case.case_id for case in CASES}
    if (config.get('assignment_id') != AID or
            config.get('selected_case_id') not in expected or
            set(config.get('supported_case_ids', [])) != expected or
            config.get('law_id') != 'NRS-484B-450-1l' or
            config.get('cell_id') != 'C135705' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('rate_hz') != 20 or config.get('duration_s') != 45):
        raise ValueError('exact parking case or capture contract differs')
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
                          'reviewed_original_site_required': True}))
        return 0
    if not args.output_dir:
        parser.error('--output-dir required')
    packet_name = os.environ.get('C135705_REVIEWED_SITE_PACKET')
    if not packet_name:
        raise ValueError('C135705_REVIEWED_SITE_PACKET original reviewed packet required')
    packet_path = Path(packet_name).resolve()
    packet, case = reviewed_site(packet_path, config['selected_case_id'])
    from native_parking import run_native
    run_native(config, packet, case, packet_path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
