"""Exact source-gated C147331 Native entrypoint; --check remains offline."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from outside_lane import CASES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--site', type=Path)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    config = json.loads((folder / 'config.json').read_text())
    case_id = config['selected_case_id']
    suffix = case_id.split('__')[-1]
    if case_id != config['assignment_id'] + '__' + suffix or suffix not in {c.name for c in CASES}:
        raise ValueError('wrong exact lane case')
    if (config['law_id'], config['cell_id'], config['actor'], config['rate_hz'],
            config['frame_count']) != ('NRS-484B-587-2a', 'C147331', 'motor_vehicle_driver', 20, 900):
        raise ValueError('wrong original Native law/cell/profile')
    if args.check:
        print('exact C147331 lane runner static check passed: ' + case_id)
        return
    site_path = args.site or os.environ.get('C147331_REVIEWED_SITE')
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError('reviewed site, CARLA host/port and original output required')
    from reviewed_site import load
    from outside_lane import validate_site
    from lane_native import capture
    try:
        site = load(Path(site_path))
        validate_site(site)
        case = next(c for c in CASES if c.name == suffix)
        capture(args.host, args.port, args.output_dir, site, case, folder)
    except BaseException as error:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'native-run-status.json').write_text(json.dumps({
            'case_id': case_id, 'errors': [type(error).__name__ + ': ' + str(error)],
            'capture_complete': False, 'physical_acceptance_claimed': False}) + '\n')
        raise


if __name__ == '__main__':
    main()
