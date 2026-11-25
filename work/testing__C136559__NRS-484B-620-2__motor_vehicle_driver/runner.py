"""Exact selected speed-zone entrypoint; Native work requires reviewed sources."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path

from speed_zone import CASES


def check(root):
    config = json.loads((root / 'config.json').read_text())
    selected = config.get('selected_case_id')
    suffix = selected.rsplit('__', 1)[-1] if isinstance(selected, str) else None
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None or selected != config.get('case', {}).get('case_id'):
        raise ValueError('selected exact speed-zone case mismatch')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-620-2', 'C136559', 'motor_vehicle_driver'):
        raise ValueError('wrong speed-zone identity')
    if config.get('frame_count') != 900 or config.get('rate_hz') != 20 or \
            config.get('duration_s') != 45 or len(config.get('cameras', [])) != 4:
        raise ValueError('wrong full original capture profile')
    if config.get('case', {}).get('draft_variables') != {
            'direction': case.direction, 'requested_mph': case.requested_mph,
            'zone_mode': case.zone_mode}:
        raise ValueError('case engineering variables changed')
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--site', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--adapter-module')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = check(root)
    if args.check:
        print(config['selected_case_id'])
        return
    site = args.site or (Path(os.environ['C136559_SITE_PACKET'])
                         if os.environ.get('C136559_SITE_PACKET') else None)
    module = args.adapter_module or os.environ.get('C136559_NATIVE_ADAPTER_MODULE')
    if not site or not module or not args.output_dir:
        raise ValueError('reviewed speed-site packet, Native adapter and output are required')
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(config, args.host, args.port)
    try:
        print(json.dumps(capture(adapter, config, site, args.output_dir), sort_keys=True))
    except Exception as error:
        if args.output_dir.is_dir() and not (args.output_dir / 'capture-seal.json').exists():
            (args.output_dir / 'native-run-status.json').write_text(json.dumps({
                'case_id': config['selected_case_id'], 'errors': [str(error)],
                'physical_acceptance_claimed': False}, sort_keys=True) + '\n')
        raise


if __name__ == '__main__':
    main()
