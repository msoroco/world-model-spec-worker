"""Selected source-deferred WALK crossing Native entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ASSIGNMENT = 'testing__C150911__NRS-484B-283-1d1__pedestrian'
SUFFIXES = {'walk_facing_yield', 'wait_facing_yield',
            'walk_not_facing_yield', 'walk_facing_no_yield'}
CAMERAS = {'overview': [1920, 1080], 'approach': [1280, 720],
           'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}


def check(root: str | Path) -> dict:
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    spec = json.loads((root / 'case-spec.json').read_text())
    control = json.loads((root / 'controller.json').read_text())
    case_id = config.get('selected_case_id')
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}:
        raise ValueError('selected WALK case identity differs')
    if spec.get('case_id') != case_id or (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-283-1d1', 'C150911', 'pedestrian'):
        raise ValueError('selected WALK law/cell/actor differs')
    cameras = config.get('cameras', [])
    named = {row.get('name'): [row.get('width'), row.get('height')] for row in cameras}
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45
            or len(cameras) != 4 or named != CAMERAS):
        raise ValueError('four-camera 20 Hz WALK capture profile differs')
    expected = {'walk_facing_yield': ('walk', True, True),
                'wait_facing_yield': ('wait', True, True),
                'walk_not_facing_yield': ('walk', False, True),
                'walk_facing_no_yield': ('walk', True, False)}[case_id.split('__')[-1]]
    if (spec.get('requested_signal_at_entry'), spec.get('requested_pedestrian_facing_signal'),
            spec.get('requested_driver_yield')) != expected:
        raise ValueError('selected WALK comparison variables differ')
    speed = control.get('walker_speed_mps')
    if type(speed) not in (int, float) or not 0.3 <= speed <= 1.5:
        raise ValueError('bounded walker speed required')
    return {'case_id': case_id, 'speed': speed,
            'source_gate': 'reviewed original pedestrian signal, crosswalk and driver packet required before Native'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path.cwd())
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--adapter-module')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, 'native_started': False}))
        return
    packet = args.packet or os.environ.get('C150911_WALK_REVIEW_PACKET')
    source_root = args.source_root or os.environ.get('C150911_WALK_SOURCE_ROOT')
    adapter_module = args.adapter_module or os.environ.get('C150911_WALK_ADAPTER_MODULE')
    if not packet or not source_root or not adapter_module:
        raise ValueError('external original WALK packet, source root and adapter required')
    from native_entry import run_native
    print(json.dumps(run_native(packet, source_root, adapter_module,
        selected['case_id'], args.output_dir, selected['speed'],
        host=args.host, port=args.port), sort_keys=True))


if __name__ == '__main__':
    main()
