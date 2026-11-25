"""Canonical exact-case backing runner; original site packet is supplied locally."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_backing_lifecycle import run
from saved_backing import ASSIGNMENT, CASES, CAMERAS


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / 'config.json').read_text())
    if (config.get('assignment_id') != ASSIGNMENT or
            config.get('law_id') != 'NRS-484B-113-3' or
            config.get('cell_id') != 'C111301' or
            config.get('actor') != 'motor_vehicle_driver' or
            set(config.get('supported_case_ids', [])) != CASES or
            config.get('selected_case_id') not in CASES or
            config.get('duration_s') != 45 or config.get('rate_hz') != 20):
        raise ValueError('exact C111301 runner configuration differs')
    if [item.get('name') for item in config.get('cameras', [])] != list(CAMERAS):
        raise ValueError('canonical four-view backing cameras differ')
    return {'assignment_id': ASSIGNMENT, 'selected_cases': sorted(CASES),
            'source_site_required_at_capture': True,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--case', choices=sorted(CASES))
    args = parser.parse_args()
    verified = check()
    if args.check:
        print(json.dumps(verified, sort_keys=True))
        return
    if not args.output_dir:
        parser.error('--output-dir required for original Native capture')
    output = Path(args.output_dir).resolve()
    selected = args.case or json.loads((output / 'config.json').read_text())['selected_case_id']
    if selected not in CASES:
        raise ValueError('exact backing case selection differs')
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    try:
        receipt = run(client.get_world(), attempt=output, packet_path=output / 'map.json',
                      case_id=selected, control_factory=carla.VehicleControl, carla=carla)
    except BaseException as exc:
        status = output / 'native-run-status.json'
        if not status.exists():
            status.write_text(json.dumps({'errors': [str(exc)], 'case_id': selected,
                                          'capture_complete': False,
                                          'physical_acceptance_claimed': False}, indent=2) + '\n')
        raise
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
