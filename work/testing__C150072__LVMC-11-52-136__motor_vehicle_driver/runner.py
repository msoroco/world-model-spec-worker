"""Exact access-aisle case entrypoint; original CARLA is lazy and source gated."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from access_aisle import CASES
from site_review import reviewed_site

ROOT = Path(__file__).resolve().parent
AID = 'testing__C150072__LVMC-11-52-136__motor_vehicle_driver'


def config():
    value = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    suffix = value.get('selected_case_id', '').removeprefix(AID + '__')
    if (value.get('assignment_id') != AID or suffix not in {x.case_id for x in CASES}
            or value.get('law_id') != 'LVMC-11-52-136'
            or value.get('cell_id') != 'C150072'
            or value.get('actor') != 'motor_vehicle_driver'
            or value.get('rate_hz') != 20 or value.get('duration_s') != 45):
        raise ValueError('frozen access-aisle case or capture contract differs')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args(argv)
    value = config()
    if args.check:
        print(json.dumps({'case_id': value['selected_case_id'],
                          'capture_contract_checked': True,
                          'reviewed_original_site_required': True}))
        return 0
    if not args.output_dir:
        parser.error('--output-dir required')
    site_env = os.environ.get('C150072_REVIEWED_SITE_PACKET')
    if not site_env:
        raise ValueError('C150072_REVIEWED_SITE_PACKET original reviewed packet required')
    path = Path(site_env).resolve()
    site = reviewed_site(path, value['selected_case_id'])
    from native_aisle import run_native
    run_native(value, site, path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
