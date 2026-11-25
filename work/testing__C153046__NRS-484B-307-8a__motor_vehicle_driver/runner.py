"""Exact-case Native entrypoint for the source-gated red-left attempt."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path


def check(root: Path) -> dict:
    config = json.loads((root / 'config.json').read_text())
    case = config['selected_case_id']
    plan = json.loads((root / 'case-plan.json').read_text())
    matches = [row for row in plan['cases'] if row['case_id'] == case]
    if len(matches) != 1 or config['case']['draft_variables'] != matches[0]['draft_variables']:
        raise ValueError('exact red-left case variables differ from frozen plan')
    if (config['law_id'], config['cell_id'], config['actor']) != (
            plan['law_id'], plan['cell_id'], plan['actor']):
        raise ValueError('red-left law/cell/actor differs')
    if config['rate_hz'] != 20 or config['frame_count'] != 900 or len(config['cameras']) != 4:
        raise ValueError('original red-left capture profile differs')
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--adapter-module')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = check(root)
    if args.check:
        print(config['selected_case_id'])
        return
    if not args.site or not args.output:
        raise ValueError('reviewed Native site packet and output are required')
    module_name = args.adapter_module or os.environ.get('C153046_NATIVE_ADAPTER_MODULE')
    if not module_name:
        raise ValueError('Native adapter module is required')
    adapter = importlib.import_module(module_name).create_adapter(config)
    from native_capture import capture
    print(json.dumps(capture(adapter, config, args.site, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
