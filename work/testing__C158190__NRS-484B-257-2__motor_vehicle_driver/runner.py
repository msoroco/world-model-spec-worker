"""Exact-case entrypoint for a reviewed non-through stop intersection."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path


def check(root: Path) -> dict:
    config = json.loads((root / 'config.json').read_text())
    plan = json.loads((root / 'case-plan.json').read_text())
    case = config.get('selected_case_id')
    selected = [row for row in plan['cases'] if row['case_id'] == case]
    if len(selected) != 1 or config.get('case', {}).get('draft_variables') != selected[0]['draft_variables']:
        raise ValueError('exact non-through stop variables differ from frozen plan')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-257-2', 'C158190', 'motor_vehicle_driver'):
        raise ValueError('wrong exact non-through stop identity')
    if config.get('rate_hz') != 20 or config.get('frame_count') != 900 or \
            config.get('duration_s') != 45 or len(config.get('cameras', [])) != 4:
        raise ValueError('wrong four-view original capture profile')
    if set(config.get('supported_case_ids', [])) != {row['case_id'] for row in plan['cases']}:
        raise ValueError('selected construction does not cover all case identities')
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--adapter-module')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = check(root)
    if args.check:
        print(config['selected_case_id'])
        return
    site = args.site or (Path(os.environ['C158190_SITE_PACKET'])
                         if os.environ.get('C158190_SITE_PACKET') else None)
    output = args.output_dir or args.output
    if not site or not output:
        raise ValueError('reviewed original site packet and output are required')
    module = args.adapter_module or os.environ.get('C158190_NATIVE_ADAPTER_MODULE')
    if not module:
        raise ValueError('Native adapter module is required')
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(config, args.host, args.port)
    try:
        print(json.dumps(capture(adapter, config, site, output), sort_keys=True))
    except Exception as error:
        if output.is_dir() and not (output / 'capture-seal.json').exists():
            (output / 'native-run-status.json').write_text(json.dumps({
                'case_id': config['selected_case_id'], 'errors': [str(error)],
                'physical_acceptance_claimed': False}, sort_keys=True) + '\n')
        raise


if __name__ == '__main__':
    main()
