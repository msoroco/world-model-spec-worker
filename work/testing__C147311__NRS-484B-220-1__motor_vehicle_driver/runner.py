"""Source-gated exact one-way Native entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from one_way_direction import CASES
from reviewed_source import verify

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config: dict) -> bool:
    expected = {ASSIGNMENT + '__' + case.name for case in CASES}
    if (config.get('selected_case_id') not in expected or
            set(config.get('supported_case_ids', [])) != expected or
            config.get('law_id') != 'NRS-484B-220-1' or
            config.get('cell_id') != 'C147311' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('exact one-way assignment/case mismatch')
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            tuple(config.get('cameras', [])) != CAMERAS or
            config.get('diagnostic_only') is not True):
        raise ValueError('one-way capture contract mismatch')
    case = next(c for c in CASES if config['selected_case_id'].endswith('__' + c.name))
    if config.get('case', {}).get('variant') != case.name or config['case'].get('lane') != case.lane or config['case'].get('direction') != case.direction:
        raise ValueError('one-way selected variant mismatch')
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text(encoding='utf-8'))
    check_config(config)
    if args.check:
        print('four-case source-gated one-way construction passed')
        return
    if args.output_dir is None:
        raise ValueError('Native output directory required')
    source = os.environ.get('C147311_REVIEWED_SITE_PACKET')
    if not source:
        raise ValueError('original reviewed site packet path required')
    reviewed = verify(Path(source), config['case']['variant'])
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir, Path(source))
    try:
        adapter.execute(reviewed, config)
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
