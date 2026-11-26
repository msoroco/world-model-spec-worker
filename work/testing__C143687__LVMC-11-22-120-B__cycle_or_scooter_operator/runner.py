"""Exact source-gated bicycle street restriction Native entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from reviewed_site import verify

ASSIGNMENT = 'testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator'
MOTIONS = ('posted_enter', 'posted_stop', 'posted_remain_trail')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASE_MOTION = {'posted_enter': 'enter_roadway',
               'posted_stop': 'stop_before_roadway',
               'posted_remain_trail': 'remain_trail'}


def check_config(config: dict) -> bool:
    roster = {ASSIGNMENT + '__' + name for name in MOTIONS}
    case_id = config.get('selected_case_id')
    if (case_id not in roster or set(config.get('supported_case_ids', [])) != roster or
            config.get('law_id') != 'LVMC-11-22-120-B' or
            config.get('cell_id') != 'C143687' or
            config.get('actor') != 'cycle_or_scooter_operator'):
        raise ValueError('exact bicycle assignment or case mismatch')
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            tuple(c.get('name') for c in config.get('cameras', [])) != CAMERAS or
            config.get('diagnostic_only') is not True):
        raise ValueError('bicycle recording contract mismatch')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if config.get('case', {}).get('motion') != CASE_MOTION[suffix]:
        raise ValueError('selected bicycle motion mismatch')
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
        print('three exact source-gated bicycle constructions passed')
        return
    if args.output_dir is None:
        raise ValueError('Native output directory required')
    try:
        source = os.environ.get('C143687_REVIEWED_SITE_PACKET')
        if not source:
            raise ValueError('original reviewed bicycle site packet path required')
        reviewed = verify(Path(source))
        from native_adapter import execute
        execute(reviewed, config, args.output_dir, args.host, args.port)
    except BaseException as error:
        if args.output_dir.is_dir():
            (args.output_dir / 'native-run-status.json').write_text(
                json.dumps({'errors': [repr(error)],
                            'physical_acceptance_claimed': False}) + '\n',
                encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
